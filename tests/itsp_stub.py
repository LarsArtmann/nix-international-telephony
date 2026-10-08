#!/usr/bin/env python3
"""Loopback ITSP stand-in for the register=false gateway VM test
(tests/noreg-gateway.nix).

Speaks just enough UDP SIP to pin the production trunk shape:
an INVITE is challenged exactly once (407 + Proxy-Authenticate with a
fresh nonce), the digest-authed retry is accepted (200 + SDP pointing
media back at us), BYE is confirmed. A REGISTER from the PBX would
prove the gateway is NOT register=false — it is logged as
UNEXPECTED-REGISTER (the test greps for it).

Log contract (one marker per event, append-only):
  CHALLENGE <call-id>          first INVITE answered 407
  DIGEST-INVITE <call-id>      retry carried Proxy-Authorization
  username="<user>"            the digest username (full header kept)
  ACK <call-id> / BYE <call-id> / UNEXPECTED-REGISTER <call-id>
"""
import socket
import sys
import uuid

PORT = 5060
LOG_PATH = sys.argv[1] if len(sys.argv) > 1 else "/tmp/itsp.log"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))


def log(line):
    with open(LOG_PATH, "a", buffering=1) as handle:
        handle.write(line + "\n")


def headers_of(text):
    return text.split("\r\n\r\n", 1)[0].splitlines()


def reply_text(request_lines, status, extra="", body="", content_type=""):
    via = [line for line in request_lines if line.lower().startswith("via:")]
    from_ = next((l for l in request_lines if l.lower().startswith("from:")), "From: <sip:x>")
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


challenged = set()

while True:
    data, addr = sock.recvfrom(65535)
    text = data.decode("utf-8", "replace")
    lines = headers_of(text)
    first = lines[0] if lines else ""
    call_id = next(
        (l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("call-id:")),
        "?",
    )

    if first.startswith("REGISTER"):
        log(f"UNEXPECTED-REGISTER {call_id}")
        sock.sendto(reply_text(lines, "403 Forbidden").encode(), addr)
        continue

    if first.startswith("BYE"):
        log(f"BYE {call_id}")
        sock.sendto(reply_text(lines, "200 OK").encode(), addr)
        continue

    if first.startswith("ACK"):
        log(f"ACK {call_id}")
        continue

    if not first.startswith("INVITE"):
        continue

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
        sock.sendto(
            reply_text(lines, "407 Proxy Authentication Required", extra=challenge).encode(),
            addr,
        )
        continue

    log(f"DIGEST-INVITE {call_id}")
    log(auth.strip())
    body = sdp(addr[0])
    sock.sendto(
        reply_text(
            lines,
            "200 OK",
            extra="Contact: <sip:itsp@" + addr[0] + ">",
            body=body,
            content_type="application/sdp",
        ).encode(),
        addr,
    )
