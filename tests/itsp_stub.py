#!/usr/bin/env python3
"""Loopback ITSP stand-in for the register=false gateway VM tests
(tests/noreg-gateway.nix, tests/noreg-gateway-tcp.nix).

Speaks just enough SIP (UDP by default, TCP with --tcp) to pin the
production trunk shape: an INVITE is challenged exactly once (407 +
Proxy-Authenticate with a fresh nonce), the digest-authed retry is
accepted (200 + SDP pointing media back at us), BYE is confirmed. A
REGISTER from the PBX would prove the gateway is NOT register=false —
it is logged as UNEXPECTED-REGISTER (the test greps for it).

Log contract (one marker per event, append-only):
  LISTEN udp|tcp              startup line (the test asserts the mode)
  CHALLENGE <call-id>          first INVITE answered 407
  DIGEST-INVITE <call-id>      retry carried Proxy-Authorization
  username="<user>"            the digest username (full header kept)
  ACK <call-id> / BYE <call-id> / UNEXPECTED-REGISTER <call-id>
"""

import socket
import sys
import threading
import uuid

PORT = 5060
args = [a for a in sys.argv[1:] if not a.startswith("--")]
USE_TCP = "--tcp" in sys.argv[1:]
LOG_PATH = args[0] if args else "/tmp/itsp.log"


def log(line):
    with open(LOG_PATH, "a", buffering=1) as handle:
        handle.write(line + "\n")


def headers_of(text):
    return text.split("\r\n\r\n", 1)[0].splitlines()


def reply_text(request_lines, status, extra="", body="", content_type=""):
    via = [line for line in request_lines if line.lower().startswith("via:")]
    from_ = next(
        (l for l in request_lines if l.lower().startswith("from:")), "From: <sip:x>"
    )
    to = next((l for l in request_lines if l.lower().startswith("to:")), "To: <sip:x>")
    call_id = next(
        (l for l in request_lines if l.lower().startswith("call-id:")), "Call-ID: x"
    )
    cseq = next(
        (l for l in request_lines if l.lower().startswith("cseq:")), "CSeq: 1 INVITE"
    )
    if ";tag=" not in to:
        to = to.rstrip() + f";tag={uuid.uuid4().hex[:8]}"
    head = (
        [f"SIP/2.0 {status}"]
        + via
        + [from_, to, call_id, cseq, "User-Agent: itsp-stub"]
    )
    if extra:
        head.append(extra)
    if content_type:
        head.append(f"Content-Type: {content_type}")
    head.append(f"Content-Length: {len(body)}")
    text = "\r\n".join(head) + "\r\n\r\n" + body
    return text


def sdp(ip):
    return (
        "v=0\r\n"
        "o=- 4711 4711 IN IP4 " + ip + "\r\n"
        "s=-\r\n"
        "c=IN IP4 " + ip + "\r\n"
        "t=0 0\r\n"
        "m=audio 16000 RTP/AVP 0 101\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=rtpmap:101 telephone-event/8000\r\n"
    )


def handle_message(text, transport, reply_ip, send):
    """Process one SIP message; `send(payload)` answers over the transport."""
    lines = headers_of(text)
    first = lines[0] if lines else ""
    log(f"{transport}<- {first}")
    call_id = next(
        (l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("call-id:")),
        "?",
    )

    if first.startswith("REGISTER"):
        log(f"UNEXPECTED-REGISTER {call_id}")
        send(reply_text(lines, "403 Forbidden").encode())
        return

    if first.startswith("BYE"):
        log(f"BYE {call_id}")
        send(reply_text(lines, "200 OK").encode())
        return

    if first.startswith("ACK"):
        log(f"ACK {call_id}")
        return

    if not first.startswith("INVITE"):
        return

    auth = next(
        (l for l in lines if l.lower().startswith("proxy-authorization:")), None
    )
    if auth is None:
        nonce = uuid.uuid4().hex
        log(f"CHALLENGE {call_id}")
        challenge = (
            'Proxy-Authenticate: Digest realm="itsp.test", nonce="'
            + nonce
            + '", algorithm=MD5'
        )
        send(reply_text(lines, "407 Proxy Authentication Required", extra=challenge).encode())
        return

    log(f"DIGEST-INVITE {call_id}")
    log(auth.strip())
    body = sdp(reply_ip)
    send(
        reply_text(
            lines,
            "200 OK",
            extra="Contact: <sip:itsp@" + reply_ip + ">",
            body=body,
            content_type="application/sdp",
        ).encode()
    )


def sip_messages(buffer):
    """Split a TCP byte stream into complete SIP messages via Content-Length."""
    while b"\r\n\r\n" in buffer:
        head, rest = buffer.split(b"\r\n\r\n", 1)
        length = 0
        for line in head.decode("utf-8", "replace").splitlines():
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1].strip())
        if len(rest) < length:
            break
        body, buffer = rest[:length], rest[length:]
        yield (head + b"\r\n\r\n" + body).decode("utf-8", "replace")
    yield None


log(f"LISTEN {'tcp' if USE_TCP else 'udp'}")

if not USE_TCP:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    while True:
        data, addr = sock.recvfrom(65535)
        handle_message(data.decode("utf-8", "replace"), "udp", addr[0],
                       lambda payload, a=addr: sock.sendto(payload, a))
else:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(8)

    def serve_conn(conn):
        buffer = b""
        peer = conn.getpeername()[0]
        while True:
            try:
                chunk = conn.recv(65535)
            except OSError:
                return
            if not chunk:
                return
            buffer += chunk
            while True:
                head_split = buffer.split(b"\r\n\r\n", 1)
                if len(head_split) < 2:
                    break
                head, rest = head_split
                length = 0
                for line in head.decode("utf-8", "replace").splitlines():
                    if line.lower().startswith("content-length:"):
                        length = int(line.split(":", 1)[1].strip())
                if len(rest) < length:
                    break
                body, buffer = rest[:length], rest[length:]
                text = (head + b"\r\n\r\n" + body).decode("utf-8", "replace")
                handle_message(text, "tcp", peer, lambda payload: conn.sendall(payload))

    while True:
        conn, _ = server.accept()
        threading.Thread(target=serve_conn, args=(conn,), daemon=True).start()
