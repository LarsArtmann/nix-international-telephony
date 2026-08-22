# Raw WebSocket-to-SIP probe, stdlib only (run with the bare python3).
#
# Performs the full RFC 6455 client dance by hand against two targets:
#   direct:  sofia's ws transport on 127.0.0.1:5066
#   proxied: nginx wss://127.0.0.1/sip (TLS via the stdlib ssl module)
# then sends a hand-rolled REGISTER text frame (masked, browser-style) and
# prints everything that comes back. Localises whether a dropped REGISTER
# dies in the nginx tunnel or inside sofia.
import base64
import os
import socket
import ssl
import struct
import sys
import time

REGISTER = (
    "REGISTER sip:pbx.test SIP/2.0\r\n"
    "Via: SIP/2.0/WSS pbx.test;branch=z9hG4bKprobe\r\n"
    "Max-Forwards: 70\r\n"
    "From: <sip:1000@pbx.test>;tag=probe\r\n"
    "To: <sip:1000@pbx.test>\r\n"
    "Call-ID: {}@pbx.test\r\n"
    "CSeq: 1 REGISTER\r\n"
    "Contact: <sip:1000@pbx.test;transport=ws>\r\n"
    "Allow: REGISTER, INVITE, ACK, CANCEL, BYE\r\n"
    "Content-Length: 0\r\n"
    "\r\n"
).format(os.urandom(4).hex())


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
    except socket.timeout:
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
        send_text_frame(sock, REGISTER)
        print("register frame sent", flush=True)
        for line in read_frames(sock):
            print(f"after-register: {line}", flush=True)
        # Frame-loop liveness: a PING must produce a PONG even if the SIP
        # layer is dead. Distinguishes a dead ws read loop from SIP-layer
        # rejection.
        send_ping_frame(sock)
        print("ping sent", flush=True)
        for line in read_frames(sock):
            print(f"after-ping: {line}", flush=True)
        send_text_frame(sock, REGISTER)
        for line in read_frames(sock):
            print(f"after-register-2: {line}", flush=True)
    except OSError as exc:
        print(f"error: {exc}", flush=True)
    finally:
        try:
            sock.close()
        except OSError:
            pass


def direct():
    return socket.create_connection(("127.0.0.1", 5066), timeout=5)


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
