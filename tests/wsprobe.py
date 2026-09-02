# Raw WebSocket-to-SIP probe, stdlib only (run with the bare python3).
#
# Performs the full RFC 6455 client dance by hand against two targets:
#   direct:  sofia's wss transport on 127.0.0.1:7443 (TLS via stdlib ssl)
#   proxied: nginx wss://127.0.0.1/sip (also TLS)
# then sends hand-rolled REGISTER text frames (masked, browser-style) and
# prints everything that comes back. FreeSWITCH drops REGISTERs whose Via
# transport token mismatches the connection transport, so Via/WSS is the
# real client behaviour to verify (Via/WS on wss is the negative control).
import base64
import os
import socket
import ssl
import struct
import sys

REGISTER_TEMPLATE = (
    "REGISTER sip:pbx.test SIP/2.0\r\n"
    "Via: SIP/2.0/{via_transport} pbx.test;branch=z9hG4bK{branch}\r\n"
    "Max-Forwards: 70\r\n"
    "From: <sip:1000@pbx.test>;tag={tag}\r\n"
    "To: <sip:1000@pbx.test>\r\n"
    "Call-ID: {callid}@pbx.test\r\n"
    "CSeq: 1 REGISTER\r\n"
    "Contact: <sip:1000@pbx.test;transport=ws>\r\n"
    "Allow: REGISTER, INVITE, ACK, CANCEL, BYE\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
)


def handshake(sock, host, path="/sip"):
    key = base64.b64encode(os.urandom(16)).decode()
    request = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Protocol: sip\r\n"
        "\r\n"
    )
    sock.sendall(request.encode())
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response += chunk
    return response.split(b"\r\n\r\n")[0].decode(errors="replace")


def send_text_frame(sock, text):
    payload = text.encode()
    mask = os.urandom(4)
    header = bytearray([0x81])  # FIN + text frame
    length = len(payload)
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", length)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", length)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(bytes(header) + mask + masked)


def send_ping_frame(sock):
    mask = os.urandom(4)
    sock.sendall(bytes([0x89, 0x80]) + mask)  # FIN + PING, empty masked payload


def read_frames(sock, seconds=3):
    sock.settimeout(seconds)
    out = []
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                out.append("<connection closed>")
                break
            out.append(repr(chunk[:400]))
    except TimeoutError:
        if not out:
            out.append("<timeout, no frames>")
    except OSError as exc:
        out.append(f"<os error: {exc}>")
    return out


def probe(name, connect):
    print(f"--- {name} ---", flush=True)
    sock = connect()
    sock.settimeout(5)
    try:
        print(f"handshake: {handshake(sock, 'pbx.test')!r}", flush=True)
        nonce = os.urandom(4).hex()
        # Via/WSS is what SIP.js sends from an https page (the case that
        # must work); Via/WS on a wss connection is the mirror control of
        # the transport-mismatch drop this probe was built to catch.
        for via_transport in ("WSS", "WS"):
            register = REGISTER_TEMPLATE.format(
                via_transport=via_transport,
                branch=f"probe{nonce}{via_transport.lower()}",
                tag=f"probe{via_transport.lower()}{nonce[:4]}",
                callid=f"{nonce}-{via_transport.lower()}",
            )
            send_text_frame(sock, register)
            print(f"register frame sent (Via/{via_transport})", flush=True)
            for line in read_frames(sock):
                print(f"after-register-{via_transport}: {line}", flush=True)
        # Frame-loop liveness: a PING must produce a PONG even if the SIP
        # layer is dead. Distinguishes a dead ws read loop from SIP-layer
        # rejection.
        send_ping_frame(sock)
        print("ping sent", flush=True)
        for line in read_frames(sock):
            print(f"after-ping: {line}", flush=True)
    except OSError as exc:
        print(f"error: {exc}", flush=True)
    finally:
        try:
            sock.close()
        except OSError:
            pass


def direct():
    raw = socket.create_connection(("127.0.0.1", 7443), timeout=5)
    # sofia presents its own (self-generated or ACME) certificate.
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context.wrap_socket(raw, server_hostname="pbx.test")


def proxied():
    raw = socket.create_connection(("127.0.0.1", 443), timeout=5)
    # The vhost serves the runtime self-signed certificate.
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context.wrap_socket(raw, server_hostname="pbx.test")


if __name__ == "__main__":
    targets = sys.argv[1:] or ["direct", "proxied"]
    for target in targets:
        probe(target, direct if target == "direct" else proxied)
    print("WSPROBE-DONE", flush=True)
