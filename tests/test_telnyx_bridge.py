"""Unit contracts of the Telnyx messaging bridge (modules/telephony/telnyx-webhooks.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest discover -s tests -v

A stub upstream server plays both upstream roles, distinguished by path:
webphone's /hooks/* and Telnyx's /v2/messages. The bridge itself runs
in-process on an ephemeral port; every test talks plain HTTP. Inbound
media fetches run against a scripted loopback HTTP(S) server.

The webhook-signature tests sign with an RFC 8032 signer that is
independent of the bridge's decoder (it has its own point encoder) and
pinned to the RFC's own vectors, so each signature is checked against
the standard from both sides.
"""

import atexit
import base64
import contextlib
import errno
import hashlib
import http.client as http_client
import importlib.util
import io
import itertools
import json
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from unittest import mock

BRIDGE_PATH = Path(__file__).resolve().parents[1] / "modules" / "telephony" / "telnyx-webhooks.py"

spec = importlib.util.spec_from_file_location("telnyx_bridge", BRIDGE_PATH)
assert spec is not None and spec.loader is not None, BRIDGE_PATH
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

WEBPHONE_SECRET = "test-webphone-shared-secret-0123456789"
TELNYX_KEY = "KEYFAKE0123456789abcdef"
RECEIVER_TOKEN = "receiver-token-0123456789"


def serve(handler_class, prepare=None):
    """A loopback server on an ephemeral port, in a daemon thread that stops within 50 ms of shutdown().

    prepare(server) may replace its socket before the first accept (the TLS media origin).
    """
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_class)
    if prepare is not None:
        prepare(server)
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    return server


class _Sink(io.RawIOBase):
    """Stands in for a handler's wfile once its socket is gone."""

    def writable(self):
        return True

    def write(self, data):
        return len(data)


class StubUpstreamHandler(BaseHTTPRequestHandler):
    """webphone's /hooks/* and Telnyx's /v2/* in one server, scripted per path.

    stub_responses[path] is (status, payload) or (status, payload, delay_seconds).
    stub_faults[path], when set, is called with the handler instead of
    answering (transport faults).
    """

    protocol_version = "HTTP/1.1"
    seen: ClassVar[list] = []
    stub_responses: ClassVar[dict] = {}  # path -> (status, payload); default 200 {"data":{"id":"stub-ref"}}
    stub_faults: ClassVar[dict] = {}  # path -> callable(handler) that breaks the exchange instead of answering

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw) if raw else None
        except ValueError:  # multipart (fax upload) — keep the raw bytes
            body = raw
        StubUpstreamHandler.seen.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization", ""),
                "content_type": self.headers.get("Content-Type", ""),
                "body": body,
            }
        )
        fault = StubUpstreamHandler.stub_faults.get(self.path)
        if fault is not None:
            fault(self)
            return
        response = StubUpstreamHandler.stub_responses.get(self.path, (200, {"data": {"id": "stub-ref"}}))
        if len(response) > 2:
            time.sleep(response[2])
        self.answer(response[0], response[1])

    def answer(self, status, payload):
        body = json.dumps(payload).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass  # the client gave up first (a timeout test); its side is what is asserted

    def log_message(self, fmt, *args):
        pass


def drop_without_answer(handler):
    """A transport fault: the request arrived, then the connection died before any answer byte."""
    handler.wfile = _Sink()
    handler.close_connection = True
    handler.connection.shutdown(socket.SHUT_RDWR)


def multipart(fields, files=(), file_field="attachment"):
    """files: (filename, content) or (filename, content, declared_type);
    declared_type None omits the part Content-Type header entirely."""
    boundary = "testboundary7351024"
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for file_spec in files:
        filename, content = file_spec[0], file_spec[1]
        declared = file_spec[2] if len(file_spec) > 2 else "application/octet-stream"
        headers = f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; '
        if declared is not None:
            headers += f'filename="{filename}"\r\nContent-Type: {declared}\r\n\r\n'
        else:
            headers += f'filename="{filename}"\r\n\r\n'
        parts.append(headers.encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def http(method, url, data=None, headers=None):
    """(status, parsed JSON body) of one request; a dropped connection raises."""
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 - stub/loopback server
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read() or b"null")
        finally:
            error.close()


def raw_request(method, path, body=b"", headers=None, content_length=None):
    """Wire bytes of a request; content_length overrides the announced size (a lying client)."""
    head = f"{method} {path} HTTP/1.1\r\nHost: 127.0.0.1\r\n"
    head += f"Content-Length: {len(body) if content_length is None else content_length}\r\n"
    for name, value in (headers or {}).items():
        head += f"{name}: {value}\r\n"
    return head.encode("latin-1") + b"\r\n" + body


def raw_exchange(request_bytes, port, timeout=10):
    """Send raw request bytes; return every byte the server sends until it closes."""
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(request_bytes)
        received = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                return received
            received += chunk


# --- Ed25519: an RFC 8032 signer with its own point encoder (the bridge's is under test) ---


def encode_point(point):
    """The 32-byte little-endian Edwards encoding of an extended point: y, plus x's low bit."""
    x, y, z, _ = point
    prime = bridge._ED_P
    z_inverse = pow(z, prime - 2, prime)
    x, y = x * z_inverse % prime, y * z_inverse % prime
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def ed25519_sign(seed, message):
    """RFC 8032 section 5.1.6; returns (public key, signature)."""
    digest = hashlib.sha512(seed).digest()
    scalar = int.from_bytes(digest[:32], "little")
    scalar = (scalar & ((1 << 254) - 8)) | (1 << 254)
    public = encode_point(bridge._ed_mul(bridge._ED_BASE_POINT, scalar))
    nonce = int.from_bytes(hashlib.sha512(digest[32:] + message).digest(), "little") % bridge._ED_L
    nonce_encoded = encode_point(bridge._ed_mul(bridge._ED_BASE_POINT, nonce))
    challenge = int.from_bytes(hashlib.sha512(nonce_encoded + public + message).digest(), "little") % bridge._ED_L
    return public, nonce_encoded + ((nonce + challenge * scalar) % bridge._ED_L).to_bytes(32, "little")


# RFC 8032 section 7.1 Ed25519 test vectors, extracted verbatim from
# rfc-editor.org/rfc/rfc8032.txt on 2026-11-28 (the long-message vectors
# are garbled in the text rendering and are left out).
# (name, secret key, public key, message, signature), all hex
RFC8032_VECTORS = [
    (
        "TEST 1",
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "TEST 2",
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "TEST 3",
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
    (
        "TEST SHA(abc)",
        "833fe62409237b9d62ec77587520911e9a759cec1d19755b7da901b96dca3d42",
        "ec172b93ad5e563bf4932c70e1245034c35467ef2efd4d64ebf819683467e2bf",
        "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
        "dc2a4459e7369633a52b1bf277839a00201009a3efbf3ecb69bea2186c26b58909351fc9ac90b3ecfdfbc7c66431e0303dca179c138ac17ad9bef1177331a704",
    ),
]


# --- the scripted origin the inbound media fetch talks to ---


def respond(handler, status=200, body=b"", content_type="image/png", headers=(), length=None):
    handler.send_response(status)
    for name, value in headers:
        handler.send_header(name, value)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body) if length is None else length))
    handler.end_headers()
    if body:
        handler.wfile.write(body)


def trickle(handler, pieces, interval):
    """Write the pieces with a sleep between them; a client that hung up ends it."""
    try:
        for piece in pieces:
            handler.connection.sendall(piece)
            time.sleep(interval)
    except OSError:
        pass
    handler.close_connection = True


def redirect(location, status=302):
    def route(handler):
        port = handler.server.server_address[1]
        respond(handler, status, headers=[("Location", location.replace("{port}", str(port)))])

    return route


def route_chunked(handler):
    handler.connection.sendall(
        b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n"
    )
    for frame in (b"5\r\nhello\r\n", b"5\r\nworld\r\n"):
        handler.connection.sendall(frame)
        time.sleep(0.02)
    handler.connection.sendall(b"0\r\n\r\n")
    handler.close_connection = True


def route_declared_short(handler):
    """Content-Length 100, then 40 bytes and a close: a truncated body."""
    handler.connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: 100\r\n\r\n" + b"x" * 40)
    handler.close_connection = True


MEDIA_ROUTES = {
    "/final": lambda handler: respond(handler, body=b"final-body"),
    "/typed": lambda handler: respond(handler, body=b"typed", content_type="image/jpeg; charset=binary"),
    "/empty": lambda handler: respond(handler, body=b""),
    "/chunked": route_chunked,
    "/declared-short": route_declared_short,
    "/declared-big": lambda handler: respond(handler, length=100000000),
    "/redirect-final": redirect("/final"),
    "/redirect-relative": redirect("final"),
    "/redirect-chain": redirect("/redirect-final"),
    "/redirect-http": redirect("http://127.0.0.1:{port}/final"),
    "/redirect-private": redirect("https://10.0.0.1/final"),
    "/redirect-loop": redirect("/redirect-loop"),
    "/redirect-no-location": lambda handler: respond(handler, 302),
    "/redirect-300": redirect("/final", status=300),
    "/dribble": lambda handler: trickle(
        handler,
        [b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nConnection: close\r\n\r\n"] + [b"x"] * 800,
        0.05,
    ),
    "/slow-headers": lambda handler: trickle(handler, [b"HTTP/1.1 200 OK\r\n"] + [b"X"] * 400, 0.05),
    "/hang": lambda handler: time.sleep(6),
    "/missing": lambda handler: respond(handler, 404, b"nope"),
    "/partial": lambda handler: respond(handler, 206, b"partial"),
}


class MediaHandler(BaseHTTPRequestHandler):
    """The scripted origin for inbound media fetches; MEDIA_ROUTES maps a path to its behaviour."""

    protocol_version = "HTTP/1.1"
    hits: ClassVar[list] = []

    def do_GET(self):
        MediaHandler.hits.append(self.path)
        MEDIA_ROUTES[self.path](self)

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True  # the fetch under test gave up first; that is its verdict

    def log_message(self, fmt, *args):
        pass


_CERTIFICATE = {}


def certificate():
    """Path of a two-day self-signed certificate for 127.0.0.1; None when the openssl CLI is absent."""
    if "path" not in _CERTIFICATE:
        _CERTIFICATE["path"] = None
        openssl = shutil.which("openssl")
        if openssl is not None:
            directory = tempfile.TemporaryDirectory(prefix="telnyx-bridge-test-cert-")
            atexit.register(directory.cleanup)  # one certificate per test process, removed with it
            _CERTIFICATE["directory"] = directory  # kept alive for the process
            paths = [f"{directory.name}/key.pem", f"{directory.name}/cert.pem"]
            subprocess.run(  # nosec B603 - fixed argv: a throwaway key for the test's own loopback server
                [
                    openssl,
                    "req",
                    "-x509",
                    "-newkey",
                    "ec",
                    "-pkeyopt",
                    "ec_paramgen_curve:prime256v1",
                    "-nodes",
                    "-keyout",
                    paths[0],
                    "-out",
                    paths[1],
                    "-days",
                    "2",
                    "-subj",
                    "/CN=127.0.0.1",
                    "-addext",
                    "subjectAltName=IP:127.0.0.1",
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
            _CERTIFICATE["path"] = Path(paths[1])
    return _CERTIFICATE["path"]


def blackhole():
    """A TCP listener that accepts connections and answers nothing; returns its port."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)

    def hold_one(connection):
        time.sleep(6)
        connection.close()

    def hold():
        while True:
            try:
                connection, _ = listener.accept()
            except OSError:
                return
            threading.Thread(target=hold_one, args=(connection,), daemon=True).start()

    threading.Thread(target=hold, daemon=True).start()
    return listener


# --- the fixture: one bridge, its stubs and clean module state per test ---


class BridgeCase(unittest.TestCase):
    SIGNING_SEED = hashlib.sha256(b"telnyx-signature-test-seed").digest()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.credentials = tmp / "credentials"
        self.credentials.mkdir()
        (self.credentials / "webphone_secret").write_text(WEBPHONE_SECRET)
        (self.credentials / "telnyx_key").write_text(TELNYX_KEY)
        (self.credentials / "webhook_token").write_text(RECEIVER_TOKEN)

        StubUpstreamHandler.seen = []
        StubUpstreamHandler.stub_responses = {}
        StubUpstreamHandler.stub_faults = {}
        MediaHandler.hits = []
        self.upstream = serve(StubUpstreamHandler)
        upstream_url = f"http://127.0.0.1:{self.upstream.server_address[1]}"
        self.media = None

        bridge.CREDENTIALS_DIR = self.credentials
        bridge.LOG_FILE = tmp / "inbound.jsonl"
        bridge.WEBPHONE_URL = upstream_url
        bridge.TELNYX_MESSAGES_API = f"{upstream_url}/v2/messages"
        bridge.TELNYX_WHATSAPP_API = f"{upstream_url}/v2/messages/whatsapp"
        bridge.TELNYX_FAXES_API = f"{upstream_url}/v2/faxes"
        bridge.FAX_CONNECTION_ID = ""  # fax lane disabled unless a test enables it
        bridge.FAX_FROM_NUMBER = ""
        bridge.WHATSAPP_FROM = ""  # WhatsApp lane disabled unless a test enables it
        bridge.SMS_TO_EXTENSION = "1000"
        bridge.FROM_NUMBER = "+15550100000"
        bridge.MEDIA_DIR = tmp / "media"
        bridge.reset_caches()

        self.server = serve(bridge.Handler)
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        bridge.PUBLIC_BASE_URL = self.base  # media URLs route back into this bridge

    def tearDown(self):
        for server in (self.server, self.media, self.upstream):
            if server is not None:
                server.shutdown()
                server.server_close()
        self.tmp.cleanup()

    # media origin

    def start_media(self, tls=False):
        """The scripted media origin; TLS means a certificate the fetch under test is pointed to trust."""
        if self.media is not None:
            self.media.shutdown()
            self.media.server_close()
        if not tls:
            self.media = serve(MediaHandler)
            self.media_origin = f"127.0.0.1:{self.media.server_address[1]}"
            return
        certfile = certificate()
        if certfile is None:
            self.skipTest("the openssl CLI is not available")
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(certfile, certfile.with_name("key.pem"))
        client_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        client_context.load_verify_locations(certfile)
        self.media = serve(
            MediaHandler,
            prepare=lambda server: setattr(
                server, "socket", server_context.wrap_socket(server.socket, server_side=True)
            ),
        )
        self.media_origin = f"127.0.0.1:{self.media.server_address[1]}"
        trust = mock.patch.object(bridge, "media_tls_context", lambda: client_context)
        trust.start()
        self.addCleanup(trust.stop)

    def fetch(self, path, scheme="https", tls=False, cap=bridge.MAX_MEDIA_BYTES, seconds=5, deadline=None, origin=None):
        """((mime, bytes) or None, seconds taken) for one fetch of the media origin.

        The public-address gate lets THIS loopback origin through and stays
        real for every other host (a redirect to 10.0.0.1 is still refused);
        the TLS wrap is skipped unless tls. Everything else is the real path.
        """
        origin = origin or getattr(self, "media_origin", None)
        patches = [mock.patch.object(bridge, "_connect_public", loopback_only(socket.create_connection))]
        if not tls:
            patches.append(mock.patch.object(bridge, "_tls_client_socket", lambda sock, host, deadline: sock))
        started = time.monotonic()
        with contextlib.ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            deadline = started + seconds if deadline is None else deadline
            result = bridge.fetch_media(f"{scheme}://{origin}{path}", cap=cap, deadline=deadline)
        return result, time.monotonic() - started

    # Telnyx webhooks

    def post_webhook(self, body, headers=None):
        """(status, payload) of one POST /telnyx/webhooks; body is sent as the exact bytes given."""
        return http("POST", f"{self.base}/telnyx/webhooks", body, headers)

    def post_signed(self, body, timestamp=None, seed=None, sign=True, headers=None, send=None):
        """A webhook with Telnyx's two signature headers over ``body``.

        ``send`` is what goes on the wire (default: body itself); passing
        something else signs one text and delivers another.
        """
        timestamp = str(int(time.time())) if timestamp is None else timestamp
        sent = {"Content-Type": "application/json", "telnyx-timestamp": timestamp}
        if sign:
            seed = self.SIGNING_SEED if seed is None else seed
            _public, signature = ed25519_sign(seed, timestamp.encode() + b"|" + body)
            sent["telnyx-signature-ed25519"] = base64.b64encode(signature).decode()
        sent.update(headers or {})
        return self.post_webhook(body if send is None else send, sent)

    def install_public_key(self, text):
        (self.credentials / "telnyx_public_key").write_text(text)

    def signing_key_b64(self):
        return base64.b64encode(ed25519_sign(self.SIGNING_SEED, b"")[0]).decode()

    def received_event(self, event_id, text="hello", **extra):
        """A message.received envelope: the event id is data.id, the deduplication key Telnyx documents."""
        payload = {"id": f"message-of-{event_id}", "from": {"phone_number": "+10987654321"}, "text": text}
        payload.update(extra)
        return {"id": event_id, "event_type": "message.received", "payload": payload}

    def post_event(self, event, **header_options):
        return self.post_signed(json.dumps({"data": event}).encode(), **header_options)

    def post_concurrently(self, post, count=2):
        """Run post() in count threads at once; returns their results in call order."""
        results = [None] * count

        def run(index):
            results[index] = post()

        threads = [threading.Thread(target=run, args=(index,)) for index in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(20)
            self.assertFalse(thread.is_alive())
        return results

    # the outbound gateway

    def post_gateway(self, path, fields, files=(), file_field="attachment", authorization=WEBPHONE_SECRET):
        body, content_type = multipart(fields, files=files, file_field=file_field)
        headers = {"Content-Type": content_type}
        if authorization is not None:
            headers["Authorization"] = f"Bearer {authorization}"
        return http("POST", f"{self.base}{path}", body, headers)

    def hook_paths(self):
        return [seen["path"] for seen in StubUpstreamHandler.seen]


def loopback_only(connect):
    """A stand-in gate for tests: this host's own addresses use ``connect``; every other name keeps the real gate."""

    def gated(address, timeout):
        if address[0] in ("127.0.0.1", "localhost", "::1"):
            return connect(address, timeout)
        return real_public_connect(address, timeout)

    real_public_connect = bridge._connect_public
    return gated


def fake_body(content):
    """An HTTPResponse stand-in that records how much every read asked for."""

    class Body:
        def __init__(self):
            self.requests = []  # what every read asked for
            self.returns = []  # what it was given
            self.position = 0

        def read(self, amount):
            self.requests.append(amount)
            piece = content[self.position : self.position + amount]
            self.returns.append(len(piece))
            self.position += len(piece)
            return piece

    return Body()


class BridgeTest(BridgeCase):
    # /gateway/message — auth + fail-closed behavior

    def test_gateway_message_requires_bearer(self):
        body, content_type = multipart({"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"})
        status, payload = http("POST", f"{self.base}/gateway/message", body, {"Content-Type": content_type})
        self.assertEqual(status, 401)
        self.assertIn("Authorization", payload["error"])

    def test_gateway_message_rejects_wrong_secret(self):
        body, content_type = multipart({"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"})
        status, _ = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}x",
            },
        )
        self.assertEqual(status, 401)

    def test_gateway_message_without_secret_configured_is_actionable_503(self):
        (bridge.CREDENTIALS_DIR / "webphone_secret").unlink()
        body, content_type = multipart({"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"})
        status, payload = http("POST", f"{self.base}/gateway/message", body, {"Content-Type": content_type})
        self.assertEqual(status, 503)
        self.assertIn("webphone_gateway_secret", payload["error"])

    def test_gateway_message_placeholder_telnyx_key_is_absent(self):
        (bridge.CREDENTIALS_DIR / "telnyx_key").write_text("PLACEHOLDER-OWNER-MUST-REPLACE")
        body, content_type = multipart({"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"})
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 502)
        self.assertIn("telnyx_api_key", payload["error"])
        self.assertIn("api-keys", payload["error"])

    def test_gateway_message_roundtrip(self):
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "hello there",
            }
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"provider_ref": "stub-ref"})
        self.assertEqual(len(StubUpstreamHandler.seen), 1)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/messages")
        self.assertEqual(sent["authorization"], f"Bearer {TELNYX_KEY}")
        self.assertEqual(
            sent["body"],
            {"from": "+15550100000", "to": "+1234567890", "text": "hello there"},
        )

    def test_gateway_message_missing_fields(self):
        body, content_type = multipart({"kind": "message", "owner": "1000", "body": "hi"})
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("'to'", payload["error"])

    def test_gateway_message_mms_roundtrip(self):
        # An octet-stream part (what pre-2.8 webphone binaries still stamp
        # via Go's CreateFormFile) is typed by magic-byte sniffing: the
        # staged file is served back with the sniffed Content-Type.
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("photo.png", png)],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"provider_ref": "stub-ref"})
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/messages")
        media_urls = sent["body"].get("media_urls")
        self.assertEqual(len(media_urls), 1)
        self.assertTrue(media_urls[0].startswith(f"{self.base}/mms-media/"))
        self.assertTrue(media_urls[0].endswith(".png"))
        self.assertEqual(sent["body"].get("text"), "see attachment")

        # The staged medium is served publicly with its sniffed type.
        with urllib.request.urlopen(media_urls[0], timeout=10) as response:  # nosec B310 - staged media on this host
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Content-Type"), "image/png")
            self.assertEqual(response.read(), png)

    def test_gateway_message_mms_declared_type_wins_over_sniffing(self):
        # webphone >= 2.8 stamps each part with the attachment's own
        # mime: the declared type routes the media, even when the magic
        # bytes alone would sniff differently (this ftyp payload sniffs
        # as video/mp4; the producer honestly declares quicktime/.mov).
        mov = b"\x00\x00\x00\x1cftypqt\x00\x00\x00\x00" + b"\x00" * 16
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "clip",
            },
            files=[("clip.mov", mov, "video/quicktime")],
        )
        status, _payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        media_urls = StubUpstreamHandler.seen[0]["body"]["media_urls"]
        self.assertTrue(media_urls[0].endswith(".mov"))
        with urllib.request.urlopen(media_urls[0], timeout=10) as response:  # nosec B310 - staged media on this host
            self.assertEqual(response.headers.get("Content-Type"), "video/quicktime")

    def test_gateway_message_mms_part_without_content_type_is_sniffed(self):
        # A part carrying NO Content-Type header must not fall back to the
        # email parser's text/plain default — it sniffs like an undeclared
        # part (same lane as the octet-stream legacy producers).
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("photo.png", png, None)],
        )
        status, _payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        media_urls = StubUpstreamHandler.seen[0]["body"]["media_urls"]
        self.assertTrue(media_urls[0].endswith(".png"))

    def test_gateway_message_mms_declared_heic_is_rejected_honestly(self):
        # The HEIC 422 with the fix-the-phone copy fires on the declared
        # type — no magic bytes needed once the producer is honest.
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("photo.heic", b"declared-but-opaque", "image/heic")],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("HEIC", payload["error"])
        self.assertIn("Most Compatible", payload["error"])

    def test_gateway_message_mms_without_text(self):
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "to": "+1234567890", "body": ""},
            files=[("pic.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 16)],
        )
        status, _payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        sent = StubUpstreamHandler.seen[0]
        self.assertNotIn("text", sent["body"])  # empty text is omitted, not sent as ""
        self.assertEqual(len(sent["body"]["media_urls"]), 1)

    def test_gateway_message_mms_rejects_oversized_total(self):
        # Telnyx MMS hard cap: 1 MB total attachments (600 KB carrier-safe).
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "big",
            },
            files=[("photo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * ((1 << 20) + 1))],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("1 MB", payload["error"])

    def test_gateway_message_mms_rejects_unknown_type(self):
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("payload.exe", b"MZ\x90\x00" + b"\x00" * 16)],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("payload.exe", payload["error"])
        self.assertIn("unsupported type", payload["error"])

    def test_mms_media_endpoint_rejects_bad_names(self):
        for name in (
            "../../etc/passwd",
            "short.png",
            "token-with-a-very-long-name-well-over-sixty-four-charactersx.png",
            "UPPER.png",
            "nonexistent.png",
        ):
            status, _payload = http("GET", f"{self.base}/mms-media/{name}")
            self.assertEqual(status, 404, name)

    def test_sweep_expired_media_removes_old_pairs(self):
        import time as time_module

        url = bridge.store_media(b"\x89PNG\r\n\x1a\n" + b"data", "image/png")
        name = url.rsplit("/", 1)[-1]
        token = name.rsplit(".", 1)[0]
        stale = bridge.MEDIA_DIR / f"{token}.json"
        stale.write_text(json.dumps({"mime": "image/png", "created": time_module.time() - 8 * 24 * 3600}))
        bridge.sweep_expired_media()
        self.assertFalse((bridge.MEDIA_DIR / name).exists())
        self.assertFalse(stale.exists())

    def test_gateway_message_upstream_500_maps_to_502(self):
        StubUpstreamHandler.stub_responses["/v2/messages"] = (
            500,
            {"errors": [{"detail": "boom"}]},
        )
        body, content_type = multipart({"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"})
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 502)
        self.assertIn("telnyx rejected the send (HTTP 500)", payload["error"])
        self.assertIn("boom", payload["error"])
        self.assertNotIn('"errors"', payload["error"])

    def test_gateway_message_self_send_rejection_is_humanized(self):
        # 2026-09-21 production burn: sending to the DID itself answers
        # 400 code 40310 "Source and destination cannot be the same
        # number" — the surfaced error must carry that reason, because
        # the webphone displays the bridge's error text verbatim.
        StubUpstreamHandler.stub_responses["/v2/messages"] = (
            400,
            {
                "errors": [
                    {
                        "code": "40310",
                        "title": "Invalid 'to' address",
                        "detail": "Source and destination cannot be the same number: +15550100000",
                    }
                ]
            },
        )
        body, content_type = multipart({"kind": "message", "owner": "1000", "to": "+15550100000", "body": "xxx"})
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 502)
        error = payload["error"]
        self.assertIn("cannot be the same number", error)
        self.assertIn("40310", error)
        self.assertNotIn('{"errors"', error)

    def test_gateway_message_telnyx_4xx_rides_502_envelope_verbatim(self):
        # 2026-09-28/29 +48 thread: a Telnyx 403 policy refusal (40306,
        # no alpha sender on the profile) must reach webphone as the
        # exact envelope string — 502 status, `telnyx rejected the send`
        # prefix, error-code suffix, detail verbatim — because webphone
        # families any 5xx as Transient and renders this text to the
        # user. Full equality pins the contract, not just substrings.
        StubUpstreamHandler.stub_responses["/v2/messages"] = (
            403,
            {
                "errors": [
                    {
                        "code": "40306",
                        "title": "Forbidden",
                        "detail": "The messaging profile doesn't have an associated alphanumeric sender ID",
                    }
                ]
            },
        )
        body, content_type = multipart({"kind": "message", "owner": "1000", "to": "+48724297883", "body": "cześć"})
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 502)
        self.assertEqual(
            payload["error"],
            "telnyx rejected the send (HTTP 403, error 40306): "
            "The messaging profile doesn't have an associated alphanumeric sender ID",
        )

    # /gateway/message — WhatsApp lane (whatsapp: destinations)

    def whatsapp_send(self, to, body="hi from whatsapp", files=()):
        fields = {"kind": "message", "owner": "1000", "to": to, "body": body}
        payload, content_type = multipart(fields, files=files)
        return http(
            "POST",
            f"{self.base}/gateway/message",
            payload,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )

    def test_whatsapp_text_roundtrip(self):
        # The channel selector is the destination prefix: a whatsapp:
        # destination rides POST /v2/messages/whatsapp with the
        # whatsapp_message object, from the dedicated WhatsApp number.
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "hello there")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"provider_ref": "stub-ref"})
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/messages/whatsapp")
        self.assertEqual(sent["authorization"], f"Bearer {TELNYX_KEY}")
        self.assertEqual(
            sent["body"],
            {
                "from": "+15550100000",
                "to": "+1234567890",
                "whatsapp_message": {
                    "type": "text",
                    "text": {"body": "hello there", "preview_url": False},
                },
            },
        )

    def test_whatsapp_sanitized_prefix_form_roundtrip(self):
        # webphone's dialable sanitizer keeps letters and drops the colon:
        # 'whatsapp:+49…' arrives as 'whatsapp+49…' and must parse the same.
        bridge.WHATSAPP_FROM = "+15550100000"
        status, _ = self.whatsapp_send("whatsapp+4915112345678")
        self.assertEqual(status, 200)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["to"], "+4915112345678")

    def test_whatsapp_mixed_case_prefix_roundtrip(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, _ = self.whatsapp_send("WhatsApp:+1234567890")
        self.assertEqual(status, 200)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["to"], "+1234567890")

    def test_whatsapp_disabled_is_actionable_502(self):
        # WHATSAPP_FROM empty (WhatsApp not enabled in the module): the
        # send fails closed with the portal setup guidance, never a fake
        # SMS fallback to the same number.
        self.assertEqual(bridge.WHATSAPP_FROM, "")
        status, payload = self.whatsapp_send("whatsapp:+1234567890")
        self.assertEqual(status, 502)
        self.assertIn("whatsapp.enable", payload["error"])
        self.assertIn("messaging.whatsapp.did", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_whatsapp_invalid_destination_is_honest_400(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:hello")
        self.assertEqual(status, 400)
        self.assertIn("+E164", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_whatsapp_image_roundtrip_with_caption(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "see the photo", files=[("photo.png", png)])
        self.assertEqual((status, payload), (200, {"provider_ref": "stub-ref"}))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["to"], "+1234567890")
        message = sent["body"]["whatsapp_message"]
        self.assertEqual(message["type"], "image")
        link = message["image"]["link"]
        self.assertTrue(link.startswith(f"{self.base}/mms-media/"))
        self.assertTrue(link.endswith(".png"))
        self.assertEqual(message["image"]["caption"], "see the photo")
        with urllib.request.urlopen(link, timeout=10) as response:  # nosec B310 - staged media on this host
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Content-Type"), "image/png")
            self.assertEqual(response.read(), png)

    def test_whatsapp_pdf_rides_as_document_with_filename(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        pdf = b"%PDF-1.4" + b"\x00" * 16
        status, _ = self.whatsapp_send("whatsapp:+1234567890", "the invoice", files=[("invoice.pdf", pdf)])
        self.assertEqual(status, 200)
        message = StubUpstreamHandler.seen[0]["body"]["whatsapp_message"]
        self.assertEqual(message["type"], "document")
        self.assertTrue(message["document"]["link"].endswith(".pdf"))
        self.assertEqual(message["document"]["filename"], "invoice.pdf")
        self.assertEqual(message["document"]["caption"], "the invoice")

    def test_whatsapp_audio_carries_no_caption(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        mp3 = b"ID3" + b"\x00" * 16
        status, _ = self.whatsapp_send("whatsapp:+1234567890", "a voice note", files=[("note.mp3", mp3)])
        self.assertEqual(status, 200)
        message = StubUpstreamHandler.seen[0]["body"]["whatsapp_message"]
        self.assertEqual(message["type"], "audio")
        self.assertNotIn("caption", message["audio"])

    def test_whatsapp_mms_only_type_rides_as_document(self):
        # WhatsApp has no native kind for gif (or tiff/vcard/mov/…): the
        # medium still sends, honestly, as a document with its filename.
        bridge.WHATSAPP_FROM = "+15550100000"
        gif = b"GIF89a" + b"\x00" * 16
        status, _ = self.whatsapp_send("whatsapp:+1234567890", "funny one", files=[("meme.gif", gif)])
        self.assertEqual(status, 200)
        message = StubUpstreamHandler.seen[0]["body"]["whatsapp_message"]
        self.assertEqual(message["type"], "document")
        self.assertEqual(message["document"]["filename"], "meme.gif")
        self.assertEqual(message["document"]["caption"], "funny one")

    def test_whatsapp_media_without_text_sends_no_caption(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        status, _ = self.whatsapp_send("whatsapp:+1234567890", "", files=[("photo.png", png)])
        self.assertEqual(status, 200)
        message = StubUpstreamHandler.seen[0]["body"]["whatsapp_message"]
        self.assertNotIn("caption", message["image"])

    def test_whatsapp_two_attachments_rejected(self):
        # WhatsApp carries exactly ONE media object per message — the
        # honest 422 beats a silent "send the first, drop the rest".
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890",
            "two photos",
            files=[("a.png", png), ("b.png", png)],
        )
        self.assertEqual(status, 422)
        self.assertIn("exactly one media object", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_whatsapp_text_over_4096_bytes_rejected(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "x" * 4097)
        self.assertEqual(status, 422)
        self.assertIn("4096", payload["error"])

    def test_whatsapp_caption_over_1024_bytes_rejected(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "x" * 1025, files=[("photo.png", png)])
        self.assertEqual(status, 422)
        self.assertIn("1024", payload["error"])

    def test_whatsapp_declared_heic_gets_the_iphone_fix_copy(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890",
            "photo",
            files=[("IMG_0001.HEIC", b"declared-but-opaque", "image/heic")],
        )
        self.assertEqual(status, 422)
        self.assertIn("HEIC", payload["error"])
        self.assertIn("Most Compatible", payload["error"])

    def test_whatsapp_unknown_type_rejected(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890",
            "see attachment",
            files=[("payload.exe", b"MZ\x90\x00" + b"\x00" * 16)],
        )
        self.assertEqual(status, 422)
        self.assertIn("unsupported type", payload["error"])

    def test_whatsapp_oversize_image_rejected(self):
        # WhatsApp image cap: 5 MiB (docs-verified 2026-09-30). The
        # honest pre-flight 422 beats Telnyx refusing the fetch later.
        # The fixture monkeypatches the cap (no 5 MB through multipart);
        # the constant pin keeps the real boundary honest.

        bridge.WHATSAPP_FROM = "+15550100000"
        self.assertEqual(bridge.WHATSAPP_MAX_IMAGE_BYTES, 5 << 20)
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
        with mock.patch.object(bridge, "WHATSAPP_MAX_IMAGE_BYTES", 8):
            status, payload = self.whatsapp_send("whatsapp:+1234567890", "big", files=[("photo.png", png)])
        self.assertEqual(status, 422)
        self.assertIn("MiB per image", payload["error"])
        self.assertIn("resize", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_whatsapp_window_rejection_carries_guidance(self):
        # Outside the 24-hour customer-service window WhatsApp refuses
        # free-form text (40008 catch-all): the surfaced error must
        # explain the window and the template fix, not look transient.
        StubUpstreamHandler.stub_responses["/v2/messages/whatsapp"] = (
            400,
            {
                "errors": [
                    {
                        "code": "40008",
                        "title": "WhatsApp error",
                        "detail": "Template not found or not approved for sending",
                    }
                ]
            },
        )
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "ping")
        self.assertEqual(status, 502)
        self.assertIn("24 hours", payload["error"])
        self.assertIn("template", payload["error"])

    def test_whatsapp_plain_rejection_has_no_window_guidance(self):
        StubUpstreamHandler.stub_responses["/v2/messages/whatsapp"] = (
            400,
            {"errors": [{"detail": "invalid destination number"}]},
        )
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "ping")
        self.assertEqual(status, 502)
        self.assertIn("invalid destination number", payload["error"])
        self.assertNotIn("24 hours", payload["error"])

    def test_sms_lane_unchanged_when_whatsapp_enabled(self):
        # Enabling WhatsApp must not move plain-number traffic: an SMS
        # send with WHATSAPP_FROM set still rides POST /v2/messages.
        bridge.WHATSAPP_FROM = "+15550100000"
        status, _ = self.whatsapp_send("+1234567890", "plain sms")
        self.assertEqual(status, 200)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/messages")
        self.assertEqual(
            sent["body"],
            {"from": "+15550100000", "to": "+1234567890", "text": "plain sms"},
        )

    def test_gateway_health_reports_whatsapp_capability(self):
        status, payload = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(status, 200)
        self.assertIsNone(payload["whatsapp_from"])
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(payload["whatsapp_from"], "+15550100000")

    def test_parse_destination_table(self):
        cases = [
            ("+1234567890", ("sms", "+1234567890")),
            ("whatsapp:+1234567890", ("whatsapp", "+1234567890")),
            ("whatsapp+1234567890", ("whatsapp", "+1234567890")),
            ("WhatsApp:+4915112345678", ("whatsapp", "+4915112345678")),
            ("whatsapp:", (None, "whatsapp:")),
            ("whatsapp:hello", (None, "whatsapp:hello")),
            ("whatsapp+not-a-number", (None, "whatsapp+not-a-number")),
        ]
        for raw, expected in cases:
            self.assertEqual(bridge.parse_destination(raw), expected, raw)

    # /gateway/fax — outbound fax through the Telnyx Programmable Fax API

    PDF_BYTES = b"%PDF-1.4 fake fax document bytes"

    def enable_fax_lane(self):
        bridge.FAX_CONNECTION_ID = "234423"
        bridge.FAX_FROM_NUMBER = "+15550100001"

    def post_fax(self, fields=None, files=(("fax.pdf", PDF_BYTES, "application/pdf"),)):
        body, content_type = multipart(
            fields or {"kind": "fax", "owner": "1000", "to": "+15550100002"},
            files,
            file_field="document",
        )
        return http(
            "POST",
            f"{self.base}/gateway/fax",
            body,
            {
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
                "Content-Type": content_type,
            },
        )

    def test_gateway_fax_requires_bearer(self):
        self.enable_fax_lane()
        body, content_type = multipart({"to": "+15550100002"}, file_field="document")
        status, _ = http("POST", f"{self.base}/gateway/fax", body, {"Content-Type": content_type})
        self.assertEqual(status, 401)

    def test_gateway_fax_unconfigured_lane_is_actionable_502(self):
        status, payload = self.post_fax()
        self.assertEqual(status, 502)
        self.assertIn("messaging.fax.enable", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])  # nothing reached upstream

    def test_gateway_fax_roundtrip(self):
        self.enable_fax_lane()
        StubUpstreamHandler.stub_responses["/v2/faxes"] = (
            202,
            {"data": {"id": "0c5e2d1c-9a3b-4d0e-8f1a-2b3c4d5e6f70"}},
        )
        status, payload = self.post_fax()
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"provider_ref": "0c5e2d1c-9a3b-4d0e-8f1a-2b3c4d5e6f70"})
        self.assertEqual(len(StubUpstreamHandler.seen), 1)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/faxes")
        self.assertEqual(sent["authorization"], f"Bearer {TELNYX_KEY}")
        self.assertIn("multipart/form-data", sent["content_type"])
        wire = sent["body"]
        self.assertIsInstance(wire, bytes)
        for expected in (
            b'name="connection_id"\r\n\r\n234423',
            b'name="from"\r\n\r\n+15550100001',
            b'name="to"\r\n\r\n+15550100002',
            b'name="webhook_url"\r\n\r\n' + bridge.PUBLIC_BASE_URL.encode(),
            b'name="contents"; filename="fax.pdf"',
            b"Content-Type: application/pdf",
            self.PDF_BYTES,
        ):
            self.assertIn(expected, wire)

    def test_gateway_fax_missing_to_is_400(self):
        self.enable_fax_lane()
        status, payload = self.post_fax(fields={"kind": "fax", "owner": "1000"})
        self.assertEqual(status, 400)
        self.assertIn("'to'", payload["error"])

    def test_gateway_fax_without_document_is_422(self):
        self.enable_fax_lane()
        status, payload = self.post_fax(files=())
        self.assertEqual(status, 422)
        self.assertIn("PDF document", payload["error"])

    def test_gateway_fax_non_pdf_document_is_422(self):
        self.enable_fax_lane()
        status, payload = self.post_fax(files=(("scan.tiff", b"II*\x00 not a pdf", "image/tiff"),))
        self.assertEqual(status, 422)
        self.assertIn("not a PDF", payload["error"])

    def test_gateway_fax_upstream_4xx_rides_502_envelope(self):
        self.enable_fax_lane()
        StubUpstreamHandler.stub_responses["/v2/faxes"] = (
            422,
            {"errors": [{"code": "10015", "detail": "connection has no fax support"}]},
        )
        status, payload = self.post_fax()
        self.assertEqual(status, 502)
        self.assertIn("telnyx rejected the send (HTTP 422, error 10015)", payload["error"])
        self.assertIn("connection has no fax support", payload["error"])

    def test_gateway_health_reports_fax_capability(self):
        status, payload = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(status, 200)
        self.assertFalse(payload["fax"]["enabled"])
        self.assertIsNone(payload["fax"]["from"])
        self.enable_fax_lane()
        status, payload = http("GET", f"{self.base}/gateway/health")
        self.assertTrue(payload["fax"]["enabled"])
        self.assertEqual(payload["fax"]["from"], "+15550100001")
        self.assertEqual(payload["fax"]["connection_id"], "234423")

    # inbound fax verdicts: fax.delivered / fax.failed → /hooks/fax/status

    def test_fax_delivered_forwards_transmitted_with_pages(self):
        status, payload = self.telnyx_event(
            {
                "event_type": "fax.delivered",
                "payload": {
                    "fax_id": "fax-abc-123",
                    "status": "delivered",
                    "page_count": 3,
                    "to": "+15550100002",
                    "from": "+15550100001",
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["forwarded"])
        hook = StubUpstreamHandler.seen[0]
        self.assertEqual(hook["path"], "/hooks/fax/status")
        self.assertEqual(hook["authorization"], f"Bearer {WEBPHONE_SECRET}")
        self.assertEqual(
            hook["body"],
            {"provider_ref": "fax-abc-123", "status": "transmitted", "pages": 3},
        )

    def test_fax_failed_forwards_failure_reason(self):
        status, payload = self.telnyx_event(
            {
                "event_type": "fax.failed",
                "payload": {
                    "fax_id": "fax-abc-456",
                    "status": "failed",
                    "failure_reason": "The remote side disconnected",
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["forwarded"])
        self.assertEqual(
            StubUpstreamHandler.seen[0]["body"],
            {
                "provider_ref": "fax-abc-456",
                "status": "failed",
                "error": "The remote side disconnected",
            },
        )

    def test_fax_intermediate_events_stay_log_only(self):
        status, payload = self.telnyx_event({"event_type": "fax.queued", "payload": {"fax_id": "fax-abc-789"}})
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"ok": True})  # log-only branch, no forward
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_fax_status_forward_failure_answers_503_for_telnyx_retry(self):
        StubUpstreamHandler.stub_responses["/hooks/fax/status"] = (500, {"no": "pe"})
        status, payload = self.telnyx_event(
            {
                "event_type": "fax.delivered",
                "payload": {"fax_id": "fax-abc-000", "status": "delivered"},
            }
        )
        self.assertEqual(status, 503)
        self.assertIn("fax status forward failed", payload["error"])

    # inbound: message.received → /hooks/message

    def telnyx_event(self, data):
        return http(
            "POST",
            f"{self.base}/telnyx/webhooks",
            json.dumps({"data": data}).encode(),
            {"Content-Type": "application/json"},
        )

    def test_inbound_message_forwarded(self):
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "in-1",
                    "from": {"phone_number": "+10987654321"},
                    "to": [{"phone_number": "+15550100000", "status": "received"}],
                    "text": "hello from telnyx",
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(len(StubUpstreamHandler.seen), 1)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/hooks/message")
        self.assertEqual(sent["authorization"], f"Bearer {WEBPHONE_SECRET}")
        self.assertEqual(
            sent["body"],
            {
                "owner": "1000",
                "from": "+10987654321",
                "body": "hello from telnyx",
                "attachments": [],
            },
        )

    def test_inbound_forward_failure_answers_503_for_telnyx_retry(self):
        StubUpstreamHandler.stub_responses["/hooks/message"] = (
            500,
            {"error": "store down"},
        )
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {"id": "in-2", "from": "+10987654321", "text": "retry me"},
            }
        )
        self.assertEqual(status, 503)
        self.assertIn("retry", payload["error"])
        # one retry on 5xx, then give up
        self.assertEqual(len(StubUpstreamHandler.seen), 2)

    def test_inbound_without_secret_configured_answers_503(self):
        (bridge.CREDENTIALS_DIR / "webphone_secret").unlink()
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {"id": "in-3", "from": "+10987654321", "text": "no secret"},
            }
        )
        self.assertEqual(status, 503)
        self.assertIn("webphone_gateway_secret", payload["error"])

    # inbound: WhatsApp message.received → tagged /hooks/message

    def test_inbound_whatsapp_text_forwarded_with_thread_tag(self):
        # The Meta-style body object carries the text; the sender is
        # tagged 'whatsapp+<digits>' so the thread keys identically to
        # the outbound destination the owner types ('whatsapp:+…' →
        # sanitized 'whatsapp+…' inside webphone).
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-1",
                    "type": "WHATSAPP",
                    "from": {"phone_number": "+10987654321"},
                    "to": [{"phone_number": "+15550100000", "status": "received"}],
                    "body": {"type": "text", "text": {"body": "hello from whatsapp"}},
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(
            sent["body"],
            {
                "owner": "1000",
                "from": "whatsapp+10987654321",
                "body": "hello from whatsapp",
                "attachments": [],
            },
        )

    def test_inbound_whatsapp_lowercase_type_also_detected(self):
        status, _ = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-1b",
                    "type": "whatsapp",
                    "from": "+10987654321",
                    "body": {"type": "text", "text": {"body": "lowercase"}},
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(StubUpstreamHandler.seen[0]["body"]["from"], "whatsapp+10987654321")

    def test_inbound_whatsapp_media_and_caption_forwarded(self):

        image = b"\xff\xd8\xff\xe0" + b"\x00" * 8
        with mock.patch.object(bridge, "fetch_media", return_value=("image/jpeg", image)):
            status, payload = self.telnyx_event(
                {
                    "event_type": "message.received",
                    "payload": {
                        "id": "wa-2",
                        "type": "WHATSAPP",
                        "from": {"phone_number": "+10987654321"},
                        "body": {
                            "type": "image",
                            "image": {
                                "url": "https://media.example.com/x.jpg",
                                "mime_type": "image/jpeg",
                                "sha256": "…",
                                "caption": "the office",
                            },
                        },
                    },
                }
            )
        self.assertEqual((status, payload["ok"]), (200, True))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["body"], "the office")
        self.assertEqual(len(sent["body"]["attachments"]), 1)
        attachment = sent["body"]["attachments"][0]
        self.assertEqual(attachment["mime_type"], "image/jpeg")
        self.assertEqual(attachment["data_base64"], base64.b64encode(image).decode())

    def test_inbound_whatsapp_envelope_shape_forwarded(self):
        # The other documented shape: plain envelope text + media list
        # (like SMS) with type WHATSAPP — still tagged, still forwarded.
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-3",
                    "type": "WHATSAPP",
                    "from": {"phone_number": "+10987654321"},
                    "text": "envelope text",
                    "media": [{"url": "http://media.example.com/x.jpg"}],
                },
            }
        )
        self.assertEqual((status, payload["ok"]), (200, True))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["from"], "whatsapp+10987654321")
        self.assertEqual(sent["body"]["body"], "envelope text")
        self.assertEqual(sent["body"]["attachments"], [])  # non-https fails fast

    def test_inbound_whatsapp_media_fetch_uses_whatsapp_cap(self):
        # WhatsApp inbound media rides the Meta caps (video 16 MB) — the
        # fetch must use the WhatsApp cap, not the 5 MiB MMS cap, or
        # oversized media is a permanent silent loss.

        seen = {}

        def fake_fetch(url, cap=bridge.MAX_MEDIA_BYTES, deadline=None):
            seen["cap"] = cap
            return "image/jpeg", b"\xff\xd8\xff\xe0" + b"\x00" * 8

        with mock.patch.object(bridge, "fetch_media", side_effect=fake_fetch):
            status, _ = self.telnyx_event(
                {
                    "event_type": "message.received",
                    "payload": {
                        "id": "wa-6",
                        "type": "WHATSAPP",
                        "from": "+10987654321",
                        "body": {
                            "type": "image",
                            "image": {"url": "https://media.example.com/big.jpg"},
                        },
                    },
                }
            )
        self.assertEqual(status, 200)
        self.assertEqual(seen["cap"], bridge.WHATSAPP_MAX_INBOUND_MEDIA_BYTES)

    def test_inbound_mms_media_fetch_keeps_5mib_cap(self):

        seen = {}

        def fake_fetch(url, cap=bridge.MAX_MEDIA_BYTES, deadline=None):
            seen["cap"] = cap
            return "image/jpeg", b"\xff\xd8\xff\xe0" + b"\x00" * 8

        with mock.patch.object(bridge, "fetch_media", side_effect=fake_fetch):
            status, _ = self.telnyx_event(
                {
                    "event_type": "message.received",
                    "payload": {
                        "id": "mms-1",
                        "type": "MMS",
                        "from": {"phone_number": "+10987654321"},
                        "text": "mms",
                        "media": [{"url": "https://media.example.com/x.jpg"}],
                    },
                }
            )
        self.assertEqual(status, 200)
        self.assertEqual(seen["cap"], bridge.MAX_MEDIA_BYTES)

    def test_inbound_whatsapp_location_rendered_as_text(self):
        status, _ = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-4",
                    "type": "WHATSAPP",
                    "from": "+10987654321",
                    "body": {
                        "type": "location",
                        "location": {
                            "latitude": "40.7128",
                            "longitude": "-74.0060",
                            "name": "Telnyx HQ",
                            "address": "311 W 43rd St",
                        },
                    },
                },
            }
        )
        self.assertEqual(status, 200)
        body = StubUpstreamHandler.seen[0]["body"]["body"]
        self.assertIn("[location]", body)
        self.assertIn("Telnyx HQ", body)
        self.assertIn("40.7128", body)

    def test_inbound_whatsapp_unsupported_kind_gets_placeholder(self):
        status, _ = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-5",
                    "type": "WHATSAPP",
                    "from": "+10987654321",
                    "body": {"type": "order", "order": {"catalog_id": "x"}},
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(StubUpstreamHandler.seen[0]["body"]["body"], "[WhatsApp order message]")

    def test_inbound_sms_still_untagged(self):
        # Explicit SMS typing must keep the bare E.164 sender — only
        # WHATSAPP-typed payloads get the thread tag.
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "in-4",
                    "type": "SMS",
                    "from": {"phone_number": "+10987654321"},
                    "text": "plain sms",
                },
            }
        )
        self.assertEqual((status, payload["ok"]), (200, True))
        self.assertEqual(StubUpstreamHandler.seen[0]["body"]["from"], "+10987654321")

    # inbound: status events → /hooks/message/status

    def finalized(self, status, errors=None):
        return {
            "event_type": "message.finalized",
            "payload": {
                "id": "out-42",
                "to": [
                    {
                        "phone_number": "+1234567890",
                        "status": status,
                        "errors": errors or [],
                    }
                ],
            },
        }

    def test_status_delivered_forwarded(self):
        status, payload = self.telnyx_event(self.finalized("delivered"))
        self.assertEqual((status, payload), (200, {"ok": True, "forwarded": True}))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/hooks/message/status")
        self.assertEqual(sent["body"], {"provider_ref": "out-42", "status": "delivered"})

    def test_status_delivery_failed_forwarded_with_error(self):
        status, payload = self.telnyx_event(
            self.finalized("delivery_failed", [{"detail": "invalid destination number"}])
        )
        self.assertEqual((status, payload["ok"], payload["forwarded"]), (200, True, True))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["status"], "failed")
        self.assertEqual(sent["body"]["error"], "invalid destination number")

    def test_intermediate_status_logged_not_forwarded(self):
        status, payload = self.telnyx_event(self.finalized("sent"))
        self.assertEqual((status, payload), (200, {"ok": True, "forwarded": False}))
        self.assertEqual(StubUpstreamHandler.seen, [])

    # status events: WhatsApp/Meta envelope (to as a STRING, pinned by
    # message.echo in the Telnyx webhook catalog) must not drop verdicts

    def string_to_finalized(self, statuses=None, status=None, errors=None):
        payload = {
            "id": "out-wa-7",
            "type": "WHATSAPP",
            "direction": "outbound",
            "to": "+1234567890",
        }
        if statuses is not None:
            payload["statuses"] = statuses
        if status is not None:
            payload["status"] = status
        if errors is not None:
            payload["errors"] = errors
        return {"event_type": "message.finalized", "payload": payload}

    def test_status_string_to_statuses_forwarded(self):
        status, payload = self.telnyx_event(
            self.string_to_finalized(statuses=[{"status": "delivered", "recipient_id": "1234567890"}])
        )
        self.assertEqual((status, payload), (200, {"ok": True, "forwarded": True}))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"], {"provider_ref": "out-wa-7", "status": "delivered"})

    def test_status_string_to_flat_failed_forwarded_with_error(self):
        status, payload = self.telnyx_event(
            self.string_to_finalized(status="failed", errors=[{"detail": "not a WhatsApp user"}])
        )
        self.assertEqual((status, payload["ok"], payload["forwarded"]), (200, True, True))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["status"], "failed")
        self.assertEqual(sent["body"]["error"], "not a WhatsApp user")

    def test_status_read_maps_to_delivered(self):
        # Meta reports 'read' after 'delivered'; the webphone hook only
        # accepts delivered|failed, so read must map onto delivered.
        status, payload = self.telnyx_event(self.string_to_finalized(statuses=[{"status": "read"}]))
        self.assertEqual((status, payload["ok"], payload["forwarded"]), (200, True, True))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["status"], "delivered")

    def test_string_to_without_verdict_stays_log_only(self):
        # Tolerance must not invent verdicts: an echo-shaped payload with
        # no statuses carries nothing to forward.
        status, payload = self.telnyx_event(self.string_to_finalized())
        self.assertEqual((status, payload), (200, {"ok": True, "forwarded": False}))
        self.assertEqual(StubUpstreamHandler.seen, [])

    # receiver behavior parity

    def test_unknown_event_logged_ok(self):
        status, payload = self.telnyx_event({"event_type": "call.initiated", "payload": {"id": "x"}})
        self.assertEqual((status, payload), (200, {"ok": True}))
        lines = bridge.LOG_FILE.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[-1])["body"]["data"]["event_type"], "call.initiated")

    def test_receiver_health(self):
        status, payload = http("GET", f"{self.base}/telnyx/webhooks/health")
        self.assertEqual((status, payload), (200, {"ok": True}))

    def test_receiver_oversize_body_is_logged_not_silent(self):
        # 02-33 §f/11: read_body caps /telnyx/webhooks at 1 MiB and an
        # oversized event silently truncated → json-parse-fail → raw-string
        # log with no hint WHY. The cap trip must leave one bridge_log line.

        declared = bridge.MAX_BODY + 4096
        request = urllib.request.Request(f"{self.base}/telnyx/webhooks", data=b"x" * declared, method="POST")
        with mock.patch.object(bridge, "bridge_log") as logged:
            with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 - stub/loopback server
                self.assertEqual(response.status, 200)
            events = [call.args[0] for call in logged.call_args_list]
            self.assertIn("webhook body over cap", events)
        # The truncated event still logs (raw string), as before.
        entry = json.loads(bridge.LOG_FILE.read_text().splitlines()[-1])
        self.assertIsInstance(entry["body"]["raw"], str)

    def test_recent_requires_token(self):
        status, payload = http("GET", f"{self.base}/telnyx/webhooks/recent")
        self.assertEqual(status, 403)
        status, payload = http(
            "GET",
            f"{self.base}/telnyx/webhooks/recent",
            headers={"Authorization": "Bearer receiver-token-0123456789"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["entries"], [])

    def test_gateway_health_reports_capability(self):
        status, payload = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["webphone_secret"])
        self.assertTrue(payload["telnyx_api_key"])
        self.assertEqual(payload["sms_to_extension"], "1000")

    # honest limits + boundary observability (SUPERB error-excellence T05-T07)

    def test_gateway_message_heic_gets_the_iphone_fix_copy(self):
        # T07: HEIC is the iPhone camera default and previously sniffed as
        # video/mp4 (ftyp fallback) — staged as .mp4 and doomed at Telnyx.
        # It must name the phone fix, not the generic unsupported wall.
        heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "photo",
            },
            files=[("IMG_0001.HEIC", heic)],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("IMG_0001.HEIC", payload["error"])
        self.assertIn("Most Compatible", payload["error"])
        self.assertNotIn("unsupported type", payload["error"])

    def test_gateway_message_generic_unsupported_copy_stays(self):
        # The HEIC lane must not eat the generic unsupported-type answer.
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("notes.txt", b"plain text has no magic bytes")],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("unsupported type", payload["error"])
        self.assertNotIn("Most Compatible", payload["error"])

    def test_staged_media_boundary_events_are_logged(self):
        # T05: staging and Telnyx's fetch of an outbound medium are the
        # two points where an MMS silently dies if nobody looks.

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("photo.png", png)],
        )
        with mock.patch.object(bridge, "bridge_log") as logged:
            status, _ = http(
                "POST",
                f"{self.base}/gateway/message",
                body,
                {
                    "Content-Type": content_type,
                    "Authorization": f"Bearer {WEBPHONE_SECRET}",
                },
            )
            self.assertEqual(status, 200)
            with urllib.request.urlopen(  # nosec B310 - staged media on this host
                StubUpstreamHandler.seen[0]["body"]["media_urls"][0], timeout=10
            ) as response:
                self.assertEqual(response.status, 200)
            events = [call.args[0] for call in logged.call_args_list]
            self.assertIn("staged outbound mms media", events)
            self.assertIn("served staged mms media", events)

    def test_staged_media_miss_is_logged(self):

        name = "a" * 22 + ".png"  # valid shape, never staged
        with mock.patch.object(bridge, "bridge_log") as logged:
            status, _ = http("GET", f"{self.base}/mms-media/{name}")
            self.assertEqual(status, 404)
            events = [call.args[0] for call in logged.call_args_list]
            self.assertIn("staged mms media miss", events)

    def test_inbound_media_fetch_failure_is_logged_and_text_forwards(self):
        # T05: a failed inbound media fetch is a PERMANENT loss of that
        # attachment (Telnyx URLs are ephemeral) — the text must still
        # forward and the loss must be visible to the operator.

        with mock.patch.object(bridge, "bridge_log") as logged:
            status, payload = self.telnyx_event(
                {
                    "event_type": "message.received",
                    "payload": {
                        "id": "in-mms-1",
                        "from": {"phone_number": "+10987654321"},
                        "text": "photo incoming",
                        "media": [{"url": "http://media.example.com/x.png"}],  # non-https fails instantly, no network
                    },
                }
            )
            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            sent = StubUpstreamHandler.seen[0]
            self.assertEqual(sent["body"]["attachments"], [])
            self.assertEqual(sent["body"]["body"], "photo incoming")
            events = [call.args[0] for call in logged.call_args_list]
            self.assertIn("inbound mms media fetch failed", events)


class Ed25519Test(unittest.TestCase):
    """The RFC 8032 arithmetic, the public-key parser and the signature check."""

    @staticmethod
    def refuses(public, message, signature):
        return not bridge.ed25519_verify(public, message, signature)

    def test_rfc8032_vectors_verify(self):
        for name, _secret, public, message, signature in RFC8032_VECTORS:
            with self.subTest(name):
                self.assertTrue(
                    bridge.ed25519_verify(bytes.fromhex(public), bytes.fromhex(message), bytes.fromhex(signature))
                )

    def test_test_signer_reproduces_the_rfc8032_vectors(self):
        # The tests' signer is an independent oracle only while it matches
        # the standard byte for byte (it was also cross-checked against
        # OpenSSL 3.5.9 on 2026-11-28; that oracle is not portable into CI).
        for name, secret, public, message, signature in RFC8032_VECTORS:
            with self.subTest(name):
                self.assertEqual(
                    ed25519_sign(bytes.fromhex(secret), bytes.fromhex(message)),
                    (bytes.fromhex(public), bytes.fromhex(signature)),
                )

    def test_generated_keys_round_trip(self):
        for index in range(4):
            message = json.dumps({"data": {"id": f"event-{index}"}}).encode()
            public, signature = ed25519_sign(hashlib.sha256(f"seed {index}".encode()).digest(), message)
            with self.subTest(index):
                self.assertTrue(bridge.ed25519_verify(public, message, signature))
                self.assertTrue(self.refuses(public, message + b" ", signature))

    def test_tampered_signature_message_and_key_are_refused(self):
        public, signature = ed25519_sign(b"seed-a", b"body")
        self.assertTrue(self.refuses(public, b"body", bytes([signature[0] ^ 1]) + signature[1:]))
        self.assertTrue(self.refuses(public, b"body", signature[:32] + bytes([signature[32] ^ 1]) + signature[33:]))
        self.assertTrue(self.refuses(public, b"body!", signature))
        self.assertTrue(self.refuses(public, b"", signature))
        self.assertTrue(self.refuses(bytes([public[0] ^ 1]) + public[1:], b"body", signature))

    def test_non_canonical_and_wrong_length_inputs_are_refused(self):
        public, signature = ed25519_sign(b"seed-b", b"body")
        order = bridge._ED_L
        s_value = int.from_bytes(signature[32:], "little")
        bad_scalars = {
            "s equals the group order": order.to_bytes(32, "little"),
            "s plus the group order": (s_value + order).to_bytes(32, "little"),
            "non-canonical 32-byte s": ((1 << 255) + 1).to_bytes(32, "little"),
        }
        for label, scalar in bad_scalars.items():
            with self.subTest(label):
                self.assertTrue(self.refuses(public, b"body", signature[:32] + scalar))
        bad_points = {
            "non-canonical r (y >= p)": bridge._ED_P.to_bytes(32, "little"),
            "r not on the curve (y = 2)": (2).to_bytes(32, "little"),
        }
        for label, point in bad_points.items():
            with self.subTest(label):
                self.assertTrue(self.refuses(public, b"body", point + signature[32:]))
        for label, bad_signature in {
            "empty": b"",
            "one byte short": signature[:63],
            "one byte long": signature + b"\x00",
        }.items():
            with self.subTest(label):
                self.assertTrue(self.refuses(public, b"body", bad_signature))
        for label, bad_key in {"empty": b"", "short": public[:31], "long": public + b"\x00"}.items():
            with self.subTest(label):
                self.assertTrue(self.refuses(bad_key, b"body", signature))

    def test_curve_denominator_never_vanishes(self):
        # _ed_decode divides by d*y^2 + 1. -1/d is a non-square on this
        # curve, so no y reaches a zero denominator; were that ever false,
        # pow(0, p-2, p) would turn a non-point into x = 0 silently.
        prime = bridge._ED_P
        minus_one_over_d = -pow(bridge._ED_D, prime - 2, prime) % prime
        self.assertEqual(pow(minus_one_over_d, (prime - 1) // 2, prime), prime - 1)

    def test_public_key_spellings(self):
        raw = ed25519_sign(b"seed-c", b"")[0]
        der = bridge.ED25519_SPKI_PREFIX + raw
        standard = base64.b64encode(raw).decode()
        spellings = {
            "raw base64": standard,
            "unpadded base64": standard.rstrip("="),
            "padded with spaces": f"  {standard}  \n",
            "url-safe base64": standard.replace("+", "-").replace("/", "_"),
            "lower-case hex": raw.hex(),
            "upper-case hex": raw.hex().upper(),
            "DER-wrapped base64": base64.b64encode(der).decode(),
            "PEM": "-----BEGIN PUBLIC KEY-----\n" + base64.encodebytes(der).decode() + "-----END PUBLIC KEY-----\n",
        }
        for label, text in spellings.items():
            with self.subTest(label):
                self.assertEqual(bridge.parse_ed25519_public_key(text), raw)

    def test_public_key_refusals_name_the_credential(self):
        raw = ed25519_sign(b"seed-d", b"")[0]
        der = bridge.ED25519_SPKI_PREFIX + raw
        refused = {
            "empty": "",
            "not base64 or hex": "not a key at all!",
            "31 bytes": base64.b64encode(raw[:31]).decode(),
            "33 bytes": base64.b64encode(raw + b"\x00").decode(),
            "DER of another size": base64.b64encode(b"\x30\x00" + der[2:]).decode(),
            # For each of these every signature would verify without the private key.
            "identity element": (1).to_bytes(32, "little").hex(),
            "order-2 point": (bridge._ED_P - 1).to_bytes(32, "little").hex(),
            "order-4 point": bytes(32).hex(),
            "a point that is not on the curve": (2).to_bytes(32, "little").hex(),
        }
        for label, text in refused.items():
            with self.subTest(label):
                with self.assertRaises(bridge.WebhookKeyError) as refusal:
                    bridge.parse_ed25519_public_key(text)
                self.assertIn("telnyx_public_key", str(refusal.exception))


class SignatureStateTest(unittest.TestCase):
    """What the receiver decides from the telnyx_public_key credential."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        bridge.CREDENTIALS_DIR = Path(directory.name)
        bridge.reset_caches()
        self.key_file = bridge.CREDENTIALS_DIR / "telnyx_public_key"
        self.raw = ed25519_sign(b"seed-state", b"")[0]

    def test_absent_empty_and_placeholder_mean_off(self):
        self.assertEqual(bridge.webhook_signature_key(), (None, None))
        self.assertEqual(bridge.signature_state(), "off")
        for text in ("", "\n", "PLACEHOLDER-OWNER-MUST-REPLACE"):
            self.key_file.write_text(text)
            self.assertEqual(bridge.webhook_signature_key(), (None, None), text)
            self.assertEqual(bridge.signature_state(), "off", text)

    def test_a_usable_key_is_required(self):
        self.key_file.write_text(base64.b64encode(self.raw).decode())
        self.assertEqual(bridge.webhook_signature_key(), (self.raw, None))
        self.assertEqual(bridge.signature_state(), "required")

    def test_an_unusable_key_fails_closed_instead_of_turning_verification_off(self):
        self.key_file.write_text("definitely not a key")
        key, error = bridge.webhook_signature_key()
        self.assertIsNone(key)
        self.assertIsInstance(error, bridge.WebhookKeyError)
        self.assertEqual(bridge.signature_state(), "misconfigured")

    def test_a_byte_order_mark_and_surrounding_whitespace_are_tolerated(self):
        self.key_file.write_bytes(b"\xef\xbb\xbf" + base64.b64encode(self.raw) + b"\r\n")
        self.assertEqual(bridge.webhook_signature_key(), (self.raw, None))

    def test_the_parse_is_cached_until_the_credential_text_changes(self):
        self.key_file.write_text(base64.b64encode(self.raw).decode())
        with mock.patch.object(bridge, "parse_ed25519_public_key", wraps=bridge.parse_ed25519_public_key) as parse:
            for _ in range(3):
                bridge.webhook_signature_key()
            self.assertEqual(parse.call_count, 1)
            # A fixed key file takes effect without a restart (the unit keeps running).
            self.key_file.write_text(self.raw.hex())
            self.assertEqual(bridge.webhook_signature_key(), (self.raw, None))
            self.assertEqual(parse.call_count, 2)


class SignatureCheckTest(unittest.TestCase):
    """verify_webhook_signature over the exact bytes, inside the replay window, or a reason."""

    NOW = 1700000000.0

    def setUp(self):
        self.body = b'{\n  "data": {"event_type": "message.received"}\n}'
        self.timestamp = "1700000000"
        _public, signature = ed25519_sign(b"seed-check", self.timestamp.encode() + b"|" + self.body)
        self.signature_b64 = base64.b64encode(signature).decode()
        self.public = ed25519_sign(b"seed-check", b"")[0]

    def headers(self, timestamp=True, signature=True):
        """Telnyx's two headers: True means the genuine value, a string that value, None an absent header."""
        sent = {}
        if timestamp is not None:
            sent[bridge.TIMESTAMP_HEADER] = self.timestamp if timestamp is True else timestamp
        if signature is not None:
            sent[bridge.SIGNATURE_HEADER] = self.signature_b64 if signature is True else signature
        return sent

    def verify(self, headers, body=None, now=NOW):
        with mock.patch.object(bridge.time, "time", return_value=now):
            return bridge.verify_webhook_signature(self.body if body is None else body, headers, self.public)

    def test_verifies_over_the_exact_request_bytes(self):
        self.assertIs(self.verify(self.headers()), True)
        reserialized = json.dumps(json.loads(self.body)).encode()
        self.assertNotEqual(reserialized, self.body)
        self.assertIn("does not match", self.verify(self.headers(), reserialized))

    def test_the_timestamp_window_is_five_minutes_both_ways(self):
        for offset, accepted in (
            (-300, True),
            (-299, True),
            (0, True),
            (299, True),
            (300, True),
            (-301, False),
            (301, False),
        ):
            with self.subTest(offset):
                timestamp = str(int(self.NOW) + offset)
                _public, signature = ed25519_sign(b"seed-check", timestamp.encode() + b"|" + self.body)
                verdict = self.verify(
                    {bridge.SIGNATURE_HEADER: base64.b64encode(signature).decode(), bridge.TIMESTAMP_HEADER: timestamp}
                )
                self.assertEqual(verdict is True, accepted, verdict)

    def test_a_millisecond_epoch_is_read_as_seconds_but_signed_as_sent(self):
        timestamp = "1700000000000"
        _public, signature = ed25519_sign(b"seed-check", timestamp.encode() + b"|" + self.body)
        signed = base64.b64encode(signature).decode()
        self.assertIs(self.verify({bridge.SIGNATURE_HEADER: signed, bridge.TIMESTAMP_HEADER: timestamp}), True)
        # The same signature over the seconds spelling verifies nothing: the header text is signed verbatim.
        self.assertIn("does not match", self.verify(self.headers(signature=signed)))

    def test_missing_headers_are_refused(self):
        for label, headers in {
            "none": {},
            "only the timestamp": self.headers(signature=None),
            "only the signature": self.headers(timestamp=None),
            "empty values": self.headers(timestamp="", signature=""),
        }.items():
            with self.subTest(label):
                self.assertIn("missing", self.verify(headers))

    def test_a_timestamp_that_is_not_a_plain_integer_is_refused(self):
        for label, timestamp in {
            "letters": "abc",
            "underscored": "1_700_000_000",
            "signed": "+1700000000",
            "decimal": "1700000000.0",
            "non-ASCII digits": "\u0651\u0657\u0650\u0650\u0650\u0650\u0650\u0650\u0650\u0650",
        }.items():
            with self.subTest(label):
                self.assertIn("is not an integer", self.verify(self.headers(timestamp=timestamp)))

    def test_a_signature_that_is_not_a_64_byte_base64_blob_is_refused(self):
        for label, (signature, reason) in {
            "not base64": ("!!!", "not base64"),
            "too short": (base64.b64encode(b"short").decode(), "does not match"),
            "too short to decode": ("42", "not base64"),
        }.items():
            with self.subTest(label):
                self.assertIn(reason, self.verify(self.headers(signature=signature)))


class SignatureHttpTest(BridgeCase):
    """POST /telnyx/webhooks with a public key configured."""

    def setUp(self):
        super().setUp()
        self.install_public_key(self.signing_key_b64())
        self.event = self.received_event("evt-signed")

    def signed(self, body=None, **options):
        body = json.dumps({"data": self.event}).encode() if body is None else body
        return self.post_signed(body, **options)

    def test_a_signed_event_is_accepted_and_forwarded(self):
        self.assertEqual(self.signed(), (200, {"ok": True}))
        self.assertEqual(self.hook_paths(), ["/hooks/message"])

    def test_every_unverifiable_delivery_is_refused_before_it_touches_anything(self):
        now = int(time.time())
        other_account = hashlib.sha256(b"another telnyx account").digest()
        body = json.dumps({"data": self.event}).encode()
        deliveries = {
            "unsigned": lambda: self.signed(body, sign=False),
            "another account's key": lambda: self.signed(body, seed=other_account),
            "body changed after signing": lambda: self.post_signed(
                body, timestamp=str(now), send=body.replace(b"hello", b"jello")
            ),
            "stale": lambda: self.signed(body, timestamp=str(now - 600)),
            "from the future": lambda: self.signed(body, timestamp=str(now + 600)),
            "timestamp not an integer": lambda: self.signed(body, timestamp="yesterday"),
            "signature not base64": lambda: self.signed(body, sign=False, headers={"telnyx-signature-ed25519": "!!!"}),
        }
        with mock.patch.object(bridge, "bridge_log") as logged:
            for label, deliver in deliveries.items():
                with self.subTest(label):
                    status, payload = deliver()
                    self.assertEqual(status, 403, payload)
                    self.assertIn("webhook signature rejected", payload["error"])
        self.assertEqual(self.hook_paths(), [])
        self.assertFalse(bridge.LOG_FILE.exists())
        rejections = [
            call.kwargs["reason"] for call in logged.call_args_list if call.args[0] == "webhook signature rejected"
        ]
        self.assertEqual(len(rejections), len(deliveries))
        self.assertTrue(all(rejections), rejections)

    def test_the_signature_covers_the_bytes_as_sent_not_a_reserialized_copy(self):
        body = ('{\n  "data": ' + json.dumps(self.event, indent=1) + "\n}\n").encode()
        self.assertEqual(self.signed(body), (200, {"ok": True}))

    def test_a_millisecond_timestamp_is_accepted(self):
        timestamp = str(int(time.time() * 1000))
        self.assertEqual(self.signed(timestamp=timestamp), (200, {"ok": True}))

    def test_unsigned_log_only_events_are_refused_too(self):
        event = {"id": "evt-call", "event_type": "call.initiated", "payload": {}}
        status, payload = self.post_webhook(json.dumps({"data": event}).encode())
        self.assertEqual(status, 403)
        self.assertIn("webhook signature rejected", payload["error"])

    def test_a_signed_body_that_is_not_json_is_still_received_like_before(self):
        status, _payload = self.signed(b"not json at all")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(bridge.LOG_FILE.read_text())["body"]["raw"], "not json at all")

    def test_every_documented_key_spelling_unlocks_the_same_signatures(self):
        raw = ed25519_sign(self.SIGNING_SEED, b"")[0]
        pem = "-----BEGIN PUBLIC KEY-----\n" + base64.encodebytes(bridge.ED25519_SPKI_PREFIX + raw).decode()
        pem += "-----END PUBLIC KEY-----\n"
        for index, text in enumerate((raw.hex(), base64.b64encode(raw).decode(), pem)):
            self.install_public_key(text)
            with self.subTest(text[:24]):
                # a fresh event id per spelling: the same one would be a redelivery
                self.event = self.received_event(f"evt-spelling-{index}")
                self.assertEqual(self.signed(), (200, {"ok": True}))

    def test_an_unusable_key_fails_every_delivery_closed_until_the_file_is_fixed(self):
        self.install_public_key("copy-pasted the wrong thing")
        with mock.patch.object(bridge, "bridge_log") as logged:
            status, payload = self.signed()
            self.assertEqual(status, 503)
            self.assertIn("key is unusable", payload["error"])
            self.assertIn("telnyx_public_key", payload["error"])
        self.assertEqual([call.args[0] for call in logged.call_args_list], ["webhook key unusable"])
        self.assertEqual(self.hook_paths(), [])
        self.assertFalse(bridge.LOG_FILE.exists())
        status, health = http("GET", f"{self.base}/gateway/health")
        self.assertEqual((status, health["webhook_signature"]), (200, "misconfigured"))
        # Fixed in place: the running unit picks the key up, no restart needed.
        self.install_public_key(self.signing_key_b64())
        self.assertEqual(self.signed(), (200, {"ok": True}))
        _status, health = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(health["webhook_signature"], "required")

    def test_a_placeholder_key_leaves_verification_off_and_says_so(self):
        self.install_public_key("PLACEHOLDER-OWNER-MUST-REPLACE")
        self.assertEqual(self.signed(sign=False), (200, {"ok": True}))
        _status, health = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(health["webhook_signature"], "off")


class SignatureOffTest(BridgeCase):
    """No public key configured (the default): the receiver trusts whoever reaches it."""

    def test_unsigned_events_are_accepted_and_health_reports_off(self):
        status, payload = self.post_event(self.received_event("evt-unsigned"))
        self.assertEqual((status, payload), (200, {"ok": True}))
        status, health = http("GET", f"{self.base}/gateway/health")
        self.assertEqual((status, health["webhook_signature"]), (200, "off"))

    def test_the_peer_address_is_recorded_from_the_header_nginx_overwrites(self):
        # Behind nginx the socket peer is always 127.0.0.1; nginx names the
        # public client in X-Real-IP (a header it rewrites, never forwards).
        event = self.received_event("evt-remote")
        self.post_event(event, headers={"X-Real-IP": "203.0.113.9"})
        self.post_event(event, headers={"X-Real-IP": "2001:db8::1"})
        self.post_event(event, headers={"X-Real-IP": "not an address"})
        self.post_event(event)
        remotes = [json.loads(line)["remote"] for line in bridge.LOG_FILE.read_text().splitlines()]
        self.assertEqual(remotes, ["203.0.113.9", "2001:db8::1", "127.0.0.1", "127.0.0.1"])

    def test_every_handled_event_leaves_one_journal_line_with_its_id_and_outcome(self):
        with mock.patch.object(bridge, "bridge_log") as logged:
            self.post_event(self.received_event("evt-journal"))
            self.post_event(self.received_event("evt-journal"))  # the redelivery
        events = [call for call in logged.call_args_list if call.args[0] == "webhook event"]
        self.assertEqual(len(events), 2)
        first, second = events
        self.assertEqual(
            first.kwargs, {"event_type": "message.received", "event_id": "evt-journal", "http": 200, "detail": "ok"}
        )
        self.assertEqual(second.kwargs["detail"], "ok")


class DeliveryTest(BridgeCase):
    """One inbound message reaches the owner's thread once, whatever Telnyx's retries do."""

    def hook(self, status=200, delay=0.0):
        StubUpstreamHandler.stub_responses["/hooks/message"] = (status, {"ok": status == 200}, delay)

    @staticmethod
    def outcomes(results):
        return [(status, tuple(sorted(payload))) for status, payload in results]

    def test_a_redelivery_of_a_delivered_message_is_not_forwarded_again(self):
        event = self.received_event("evt-dup")
        self.assertEqual(self.post_event(event), (200, {"ok": True}))
        self.assertEqual(self.post_event(event), (200, {"ok": True, "duplicate": True}))
        self.assertEqual(self.hook_paths(), ["/hooks/message"])

    def test_the_message_id_stands_in_when_the_envelope_carries_no_event_id(self):
        event = self.received_event("evt-none")
        del event["id"]
        self.post_event(event)
        self.assertEqual(self.post_event(event), (200, {"ok": True, "duplicate": True}))
        self.assertEqual(self.hook_paths(), ["/hooks/message"])

    def test_without_any_id_nothing_can_be_deduplicated(self):
        event = self.received_event("evt-anonymous")
        del event["id"]
        del event["payload"]["id"]
        self.post_event(event)
        self.assertEqual(self.post_event(event), (200, {"ok": True}))
        self.assertEqual(self.hook_paths(), ["/hooks/message"] * 2)

    def test_a_failed_forward_is_forgotten_so_the_retry_is_forwarded(self):
        self.hook(status=500)
        event = self.received_event("evt-retry")
        status, _payload = self.post_event(event)
        self.assertEqual(status, 503)
        self.hook()  # webphone is back
        self.assertEqual(self.post_event(event), (200, {"ok": True}))
        self.assertEqual(self.hook_paths(), ["/hooks/message"] * 3)  # two attempts on the 5xx, then the delivery
        self.assertEqual(self.post_event(event), (200, {"ok": True, "duplicate": True}))
        self.assertEqual(len(self.hook_paths()), 3)

    def test_a_copy_arriving_mid_forward_waits_for_the_first_outcome(self):
        # Forwarding both would double-post; answering the copy 200 outright
        # would lose the message when the first forward then fails.
        self.hook(delay=0.8)
        first, second = self.post_concurrently(lambda: self.post_event(self.received_event("evt-race")))
        self.assertCountEqual(
            self.outcomes((first, second)),
            [(200, ("ok",)), (200, ("duplicate", "ok"))],
        )
        self.assertEqual(self.hook_paths(), ["/hooks/message"])

    def test_three_copies_at_once_still_forward_once(self):
        self.hook(delay=0.6)
        results = self.post_concurrently(lambda: self.post_event(self.received_event("evt-triple")), count=3)
        self.assertCountEqual(self.outcomes(results), [(200, ("ok",))] + [(200, ("duplicate", "ok"))] * 2)
        self.assertEqual(self.hook_paths(), ["/hooks/message"])

    def test_when_the_first_forward_fails_the_waiting_copy_takes_over(self):
        self.hook(status=500, delay=0.3)
        results = self.post_concurrently(lambda: self.post_event(self.received_event("evt-takeover")))
        self.assertEqual([status for status, _payload in results], [503, 503])
        self.assertEqual(len(self.hook_paths()), 4)  # two attempts by the first copy, two by the second
        self.hook()
        self.assertEqual(self.post_event(self.received_event("evt-takeover")), (200, {"ok": True}))
        self.assertEqual(len(self.hook_paths()), 5)

    def test_a_copy_that_cannot_wait_long_enough_is_answered_503_never_200(self):
        self.hook(delay=0.8)
        event = self.received_event("evt-busy")
        with mock.patch.object(bridge, "DELIVERY_WAIT_SECONDS", 0.2):
            results = self.post_concurrently(lambda: self.post_event(event))
        self.assertCountEqual(self.outcomes(results), [(200, ("ok",)), (503, ("error",))])
        refused = [payload for status, payload in results if status == 503]
        self.assertIn("still being forwarded", refused[0]["error"])
        self.assertEqual(self.hook_paths(), ["/hooks/message"])
        # Telnyx's next attempt finds the delivery recorded.
        self.assertEqual(self.post_event(event), (200, {"ok": True, "duplicate": True}))
        self.assertEqual(len(self.hook_paths()), 1)

    def test_the_delivered_mark_expires(self):
        event = self.received_event("evt-ttl")
        with mock.patch.object(bridge, "DELIVERED_TTL_SECONDS", 0.05):
            self.post_event(event)
            time.sleep(0.1)
            self.assertEqual(self.post_event(event), (200, {"ok": True}))  # no longer inside Telnyx's retry window
        self.assertEqual(self.hook_paths(), ["/hooks/message"] * 2)

    def test_the_delivered_set_is_bounded_and_evicts_the_oldest(self):
        with mock.patch.object(bridge, "DELIVERED_MAX", 2):
            for name in ("a", "b", "c"):
                self.post_event(self.received_event(f"evt-{name}"))
            self.assertEqual(set(bridge._DELIVERED), {"evt-b", "evt-c"})  # the oldest went
            self.assertEqual(bridge.begin_delivery("evt-a"), "forward")
            self.assertEqual(bridge.begin_delivery("evt-b"), "duplicate")
            self.assertEqual(bridge.begin_delivery("evt-c"), "duplicate")

    def test_status_and_fax_verdicts_are_not_deduplicated(self):
        # They are idempotent updates: a redelivery simply posts them again.
        finalized = {"id": "evt-finalized", "event_type": "message.finalized", "payload": {"id": "out-1"}}
        finalized["payload"]["to"] = [{"phone_number": "+1234567890", "status": "delivered"}]
        self.post_event(finalized)
        self.assertEqual(self.post_event(finalized), (200, {"ok": True, "forwarded": True}))
        fax = {"id": "evt-fax", "event_type": "fax.delivered", "payload": {"fax_id": "fax-1"}}
        self.post_event(fax)
        self.assertEqual(self.hook_paths(), ["/hooks/message/status"] * 2 + ["/hooks/fax/status"])

    def test_a_message_without_a_sender_is_received_but_never_forwarded(self):
        event = {"id": "evt-nosender", "event_type": "message.received", "payload": {"id": "m-1", "text": "hi"}}
        self.assertEqual(self.post_event(event), (200, {"ok": True, "forwarded": False}))
        self.assertEqual(self.hook_paths(), [])
        self.assertEqual(len(bridge.LOG_FILE.read_text().splitlines()), 1)

    def test_a_crash_inside_the_forward_releases_the_claim(self):
        event = self.received_event("evt-crash")
        with (
            mock.patch.object(bridge, "forward_inbound_message", side_effect=RuntimeError("boom")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status, payload = self.post_event(event)
            self.assertEqual(status, 503)
            self.assertIn("webhook handling failed", payload["error"])
        self.assertEqual(self.post_event(event), (200, {"ok": True}))
        self.assertEqual(self.hook_paths(), ["/hooks/message"])


class BoundaryTest(BridgeCase):
    """Whatever a caller sends, the bridge answers it and stays up."""

    def test_data_must_be_an_object_when_present(self):
        for body in ({"data": "x"}, {"data": [1]}, {"data": 5}, {"data": True}):
            with self.subTest(body):
                self.assertEqual(
                    self.post_webhook(json.dumps(body).encode()),
                    (400, {"error": "webhook field 'data' must be an object"}),
                )

    def test_bodies_without_an_envelope_are_logged_only(self):
        for body in (b"[]", b'"text"', b"42", b"null", b"{}", b'{"data": null}'):
            with self.subTest(body):
                self.assertEqual(self.post_webhook(body), (200, {"ok": True}))
        self.assertEqual(len(bridge.LOG_FILE.read_text().splitlines()), 6)
        self.assertEqual(self.hook_paths(), [])

    def test_a_body_that_is_not_json_is_logged_as_cut_text(self):
        self.assertEqual(self.post_webhook(b"this is not json"), (200, {"ok": True}))
        entry = json.loads(bridge.LOG_FILE.read_text().splitlines()[-1])
        self.assertEqual(entry["body"], {"raw": "this is not json"})
        # The log feeds the operator's SMS tab and anyone can send non-JSON
        # to the receiver: a large body is kept, but only up to a bound.
        big = b"\xff" + b"x" * bridge.MAX_RAW_LOG_BYTES
        self.post_webhook(big)
        entry = json.loads(bridge.LOG_FILE.read_text().splitlines()[-1])
        self.assertEqual(len(entry["body"]["raw"]), bridge.MAX_RAW_LOG_BYTES)
        self.assertEqual(entry["body"]["raw_truncated"], len(big))
        self.assertNotIn("raw_truncated", json.loads(bridge.LOG_FILE.read_text().splitlines()[0])["body"])

    def test_an_absurdly_nested_body_does_not_crash_the_handler(self):
        self.assertEqual(self.post_webhook(b"[" * 100000 + b"]" * 100000), (200, {"ok": True}))

    def test_malformed_event_shapes_never_crash_the_handler(self):
        received = "message.received"
        sender = {"phone_number": "+10987654321"}
        shapes = {
            "no event type": {"id": "e1", "payload": {}},
            "event type is a number": {"id": "e2", "event_type": 7, "payload": {}},
            "payload is a string": {"id": "e3", "event_type": received, "payload": "oops"},
            "payload is a list": {"id": "e4", "event_type": received, "payload": [1, 2]},
            "sender is a number": {"id": "e5", "event_type": received, "payload": {"from": 5, "text": "x"}},
            "sender without a number": {"id": "e6", "event_type": received, "payload": {"from": {"phone_number": 5}}},
            "media of scalars": {
                "id": "e7",
                "event_type": received,
                "payload": {"from": sender, "media": [1, "a", None, {"url": 5}, {"url": None}]},
            },
            "media is a string": {"id": "e8", "event_type": received, "payload": {"from": sender, "media": "x"}},
            "text is an object": {"id": "e9", "event_type": received, "payload": {"from": sender, "text": {"a": 1}}},
            "whatsapp body of the wrong shape": {
                "id": "e10",
                "event_type": received,
                "payload": {"from": sender, "type": "WHATSAPP", "body": {"type": ["x"]}},
            },
            "whatsapp body type is a list": {
                "id": "e11",
                "event_type": received,
                "payload": {"from": sender, "type": "WHATSAPP", "body": ["text"]},
            },
            "whatsapp location without coordinates": {
                "id": "e12",
                "event_type": received,
                "payload": {"from": sender, "type": "WHATSAPP", "body": {"type": "location", "location": "home"}},
            },
            "whatsapp reaction without emoji": {
                "id": "e13",
                "event_type": received,
                "payload": {"from": sender, "type": "WHATSAPP", "body": {"type": "reaction"}},
            },
            "status to is a number": {"id": "o1", "event_type": "message.finalized", "payload": {"id": "o1", "to": 5}},
            "status entry with a number status": {
                "id": "o2",
                "event_type": "message.finalized",
                "payload": {"id": "o2", "to": [{"phone_number": "+1234567890", "status": 5}]},
            },
            "status errors is a string": {
                "id": "o3",
                "event_type": "message.finalized",
                "payload": {"id": "o3", "to": [{"status": "delivery_failed", "errors": "nope"}]},
            },
            "status detail is an object": {
                "id": "o4",
                "event_type": "message.finalized",
                "payload": {"id": "o4", "to": [{"status": "delivery_failed", "errors": [{"detail": {"deep": True}}]}]},
            },
            "flat status of the wrong type": {
                "id": "o5",
                "event_type": "message.finalized",
                "payload": {"id": "o5", "type": "WHATSAPP", "to": "+1234567890", "statuses": "delivered", "status": 5},
            },
            "status event without an id": {"id": "o6", "event_type": "message.finalized", "payload": {"to": []}},
            "fax page count is text": {
                "id": "f1",
                "event_type": "fax.delivered",
                "payload": {"fax_id": "fax-1", "page_count": "3"},
            },
            "fax failure reason is a number": {
                "id": "f2",
                "event_type": "fax.failed",
                "payload": {"fax_id": "fax-2", "failure_reason": 5},
            },
            "fax event without a fax id": {"id": "f3", "event_type": "fax.failed", "payload": {}},
        }
        for label, event in shapes.items():
            with self.subTest(label):
                status, payload = self.post_event(event)  # a dropped connection raises here
                self.assertIn(status, (200, 400, 503), payload)
                self.assertIsInstance(payload, dict)
        # The shapes that carry a sender and some text still reach the thread.
        self.assertEqual(self.hook_paths().count("/hooks/message"), 7)
        # ... and the two failed verdicts reach it with an honest error text.
        failures = [seen for seen in StubUpstreamHandler.seen if seen["path"] == "/hooks/message/status"]
        self.assertEqual(
            [seen["body"]["error"] for seen in failures], ["carrier reports delivery_failed", "{'deep': True}"]
        )
        faxes = [seen["body"] for seen in StubUpstreamHandler.seen if seen["path"] == "/hooks/fax/status"]
        self.assertEqual(
            faxes[1], {"provider_ref": "fax-2", "status": "failed", "error": "telnyx reports the fax failed"}
        )
        self.assertNotIn("pages", faxes[0])

    def test_an_unexpected_crash_answers_503_and_the_next_request_is_served(self):
        event = self.received_event("evt-crash")
        with (
            mock.patch.object(bridge, "forward_inbound_message", side_effect=RuntimeError("boom")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status, payload = self.post_event(event)
            self.assertEqual(status, 503)
            self.assertEqual(payload, {"error": "webhook handling failed (Telnyx should retry)"})
        # The crash released the claim: Telnyx's retry is forwarded for real.
        self.assertEqual(self.post_event(event), (200, {"ok": True}))
        self.assertEqual(self.hook_paths(), ["/hooks/message"])

    def test_a_gateway_crash_answers_503_that_says_the_send_may_have_gone_out(self):
        fields = {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
        with (
            mock.patch.object(bridge, "telnyx_api_send", side_effect=RuntimeError("boom")),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            status, payload = self.post_gateway("/gateway/message", fields)
        self.assertEqual(status, 503)
        self.assertIn("RuntimeError: boom", payload["error"])
        self.assertIn(bridge.ACTIONABLE_OUTCOME_UNKNOWN, payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_the_log_reader_fails_closed_on_an_empty_or_placeholder_token(self):
        url = f"{self.base}/telnyx/webhooks/recent"
        bearer = {"Authorization": f"Bearer {RECEIVER_TOKEN}"}
        self.assertEqual(http("GET", url, headers=bearer)[0], 200)
        token_file = self.credentials / "webhook_token"
        for content in ("", "\n", "PLACEHOLDER-OWNER-MUST-REPLACE", RECEIVER_TOKEN + " " + RECEIVER_TOKEN):
            with self.subTest(repr(content)):
                token_file.write_text(content)
                self.assertEqual(http("GET", url, headers=bearer)[0], 403)
        token_file.unlink()
        self.assertEqual(http("GET", url, headers=bearer)[0], 403)

    def test_a_token_file_with_a_byte_order_mark_still_matches_the_plain_token(self):
        (self.credentials / "webhook_token").write_text("\ufeff" + RECEIVER_TOKEN + "\r\n")
        self.assertEqual(
            http("GET", f"{self.base}/telnyx/webhooks/recent", headers={"Authorization": f"Bearer {RECEIVER_TOKEN}"})[
                0
            ],
            200,
        )

    def test_a_non_ascii_bearer_never_crashes_the_comparison(self):
        self.assertEqual(
            http("GET", f"{self.base}/telnyx/webhooks/recent", headers={"Authorization": "Bearer t\u00f6ken"})[0], 403
        )
        status, _payload = self.post_gateway(
            "/gateway/message",
            {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"},
            authorization=WEBPHONE_SECRET + "\u00f6",
        )
        self.assertEqual(status, 401)

    def test_a_malformed_telnyx_key_is_actionable_and_never_sent(self):
        for content in ("KEY with a space", "KEY\u00a0with nbsp", "KEY\u4e2d\u6587", "KEY\ttab"):
            with self.subTest(repr(content)):
                (self.credentials / "telnyx_key").write_text(content)
                status, payload = self.post_gateway(
                    "/gateway/message", {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
                )
                self.assertEqual(status, 502)
                self.assertIn("copy-paste", payload["error"])
                self.assertIn("telnyxApiKeyFile", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])
        _status, health = http("GET", f"{self.base}/gateway/health")
        self.assertFalse(health["telnyx_api_key"])

    def test_a_key_file_with_a_byte_order_mark_is_still_a_key(self):
        (self.credentials / "telnyx_key").write_text("\ufeff" + TELNYX_KEY + "\r\n")
        status, _payload = self.post_gateway(
            "/gateway/message", {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(StubUpstreamHandler.seen[0]["authorization"], f"Bearer {TELNYX_KEY}")

    def test_every_refusal_shape_becomes_text_never_a_crash(self):
        shapes = {
            "the documented shape": b'{"errors": [{"code": "40310", "detail": "same number"}]}',
            "errors is an object": b'{"errors": {"detail": "not a list"}}',
            "errors is null": b'{"errors": null}',
            "errors is empty": b'{"errors": []}',
            "errors holds a string": b'{"errors": ["a string"]}',
            "errors holds a number": b'{"errors": [5]}',
            "detail is a number": b'{"errors": [{"detail": 5}]}',
            "detail is empty": b'{"errors": [{"detail": ""}]}',
            "detail at the top level": b'{"detail": "no errors array"}',
            "not json": b"<html>502 Bad Gateway</html>",
            "empty": b"",
        }
        for label, body in shapes.items():
            with self.subTest(label):
                text = bridge.telnyx_rejection(400, body)
                self.assertIsInstance(text, str)
                self.assertTrue(text)
        self.assertEqual(
            bridge.telnyx_rejection(400, shapes["the documented shape"]),
            "telnyx rejected the send (HTTP 400, error 40310): same number",
        )
        self.assertTrue(
            bridge.telnyx_rejection(400, shapes["errors is an object"]).startswith("telnyx api answered 400: ")
        )

    def test_an_upstream_success_without_a_message_id_is_an_honest_502(self):
        for label, answered in {
            "no data": {"ok": True},
            "data is a string": {"data": "accepted"},
            "id is a number": {"data": {"id": 5}},
            "id is empty": {"data": {"id": ""}},
            "not an object": [],
        }.items():
            with self.subTest(label):
                StubUpstreamHandler.stub_responses["/v2/messages"] = (200, answered)
                status, payload = self.post_gateway(
                    "/gateway/message", {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
                )
                self.assertEqual(status, 502)
                self.assertEqual(payload, {"error": "telnyx api response is missing data.id"})

    def test_a_refused_attachment_leaves_nothing_staged(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        fields = {"kind": "message", "owner": "1000", "to": "whatsapp:+1234567890", "body": "x" * 1025}
        status, _payload = self.post_gateway("/gateway/message", fields, files=[("photo.png", png)])
        self.assertEqual(status, 422)  # caption too long: found after the image used to be staged
        fields.update(to="+1234567890", body="two files")
        status, _payload = self.post_gateway(
            "/gateway/message", fields, files=[("a.png", png), ("b.exe", b"MZ\x90\x00" + b"\x00" * 16)]
        )
        self.assertEqual(status, 422)  # the second file is unsupported: neither is staged
        self.assertFalse(bridge.MEDIA_DIR.exists())
        self.assertEqual(StubUpstreamHandler.seen, [])


class HttpSendTest(unittest.TestCase):
    """The retry contract of http_send: what may be repeated and what is reported as uncertain."""

    def setUp(self):
        self.request = urllib.request.Request("http://stub.example/hook", data=b"{}", method="POST")

    @staticmethod
    def http_error(status=500, body=b"later"):
        return urllib.error.HTTPError("http://stub.example/", status, "stubbed", {}, io.BytesIO(body))

    @staticmethod
    def ok_response():
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b"ok"
        return response

    def test_a_send_is_never_repeated_after_a_5xx(self):
        urlopen = mock.Mock(side_effect=[self.http_error()])
        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(bridge.http_send(self.request, safe_to_retry=False), (500, b"later"))
        self.assertEqual(urlopen.call_count, 1)

    def test_an_idempotent_call_retries_a_5xx_once(self):
        urlopen = mock.Mock(side_effect=[self.http_error(), self.ok_response()])
        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(bridge.http_send(self.request), (200, b"ok"))
        self.assertEqual(urlopen.call_count, 2)

    def test_an_idempotent_call_gives_up_after_its_one_retry(self):
        urlopen = mock.Mock(side_effect=[self.http_error(), self.http_error(502, b"still down")])
        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(bridge.http_send(self.request), (502, b"still down"))
        self.assertEqual(urlopen.call_count, 2)

    def test_a_4xx_is_returned_at_once_in_both_modes(self):
        for safe_to_retry in (True, False):
            with self.subTest(safe_to_retry=safe_to_retry):
                urlopen = mock.Mock(side_effect=[self.http_error(403, b"no")])
                with mock.patch("urllib.request.urlopen", urlopen):
                    self.assertEqual(bridge.http_send(self.request, safe_to_retry=safe_to_retry), (403, b"no"))
                self.assertEqual(urlopen.call_count, 1)

    def test_every_error_body_socket_is_released(self):
        for safe_to_retry in (True, False):
            with self.subTest(safe_to_retry=safe_to_retry):
                bodies = [io.BytesIO(b"first"), io.BytesIO(b"second")]
                errors = [urllib.error.HTTPError("http://stub.example/", 503, "x", {}, body) for body in bodies]
                urlopen = mock.Mock(side_effect=errors)
                with mock.patch("urllib.request.urlopen", urlopen):
                    answered = bridge.http_send(self.request, safe_to_retry=safe_to_retry)
                self.assertEqual(answered, (503, b"second" if safe_to_retry else b"first"))
                self.assertEqual(urlopen.call_count, 2 if safe_to_retry else 1)
                self.assertTrue(all(body.closed for body in bodies[: urlopen.call_count]))
                for unused in errors[urlopen.call_count :]:
                    unused.close()  # only the raised ones are the bridge's to release

    def test_an_error_body_that_cannot_be_read_is_empty_not_a_crash(self):
        class unreadable(io.BytesIO):
            def read(self, *args):
                raise http_client.IncompleteRead(b"partial")

        body = unreadable(b"later")
        urlopen = mock.Mock(side_effect=[urllib.error.HTTPError("http://stub.example/", 500, "x", {}, body)])
        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(bridge.http_send(self.request, safe_to_retry=False), (500, b""))
        self.assertTrue(body.closed)

    def test_only_a_refused_or_unroutable_or_unresolved_target_proves_nothing_was_sent(self):
        table = {
            urllib.error.URLError(ConnectionRefusedError(errno.ECONNREFUSED, "refused")): True,
            urllib.error.URLError(OSError(errno.EHOSTUNREACH, "no route to host")): True,
            urllib.error.URLError(OSError(errno.ENETUNREACH, "network unreachable")): True,
            urllib.error.URLError(socket.gaierror(-2, "Name or service not known")): True,
            ConnectionRefusedError(errno.ECONNREFUSED, "refused"): True,
            urllib.error.URLError(TimeoutError("timed out")): False,
            TimeoutError("timed out"): False,
            http_client.RemoteDisconnected(): False,
            ConnectionResetError(errno.ECONNRESET, "reset"): False,
            urllib.error.URLError(BrokenPipeError(errno.EPIPE, "broken pipe")): False,
            http_client.IncompleteRead(b"partial"): False,
        }
        for error, nothing_sent in table.items():
            with self.subTest(repr(error)):
                self.assertEqual(bridge.nothing_sent(error), nothing_sent)

    def test_a_transport_failure_that_proves_nothing_was_sent_is_retried_once(self):
        urlopen = mock.Mock(
            side_effect=[urllib.error.URLError(ConnectionRefusedError(errno.ECONNREFUSED, "refused"))] * 2
        )
        with mock.patch("urllib.request.urlopen", urlopen), self.assertRaises(ConnectionError) as failure:
            bridge.http_send(self.request, safe_to_retry=False)
        self.assertNotIsInstance(failure.exception, bridge.SendOutcomeUnknown)
        self.assertIn("unreachable", str(failure.exception))
        self.assertEqual(urlopen.call_count, 2)

    def test_a_transport_failure_after_the_request_may_have_landed_is_not_repeated(self):
        for error in (
            urllib.error.URLError(TimeoutError("timed out")),
            http_client.RemoteDisconnected(),
            ConnectionResetError(errno.ECONNRESET, "reset"),
        ):
            with self.subTest(repr(error)):
                urlopen = mock.Mock(side_effect=[error])
                with mock.patch("urllib.request.urlopen", urlopen), self.assertRaises(bridge.SendOutcomeUnknown):
                    bridge.http_send(self.request, safe_to_retry=False)
                self.assertEqual(urlopen.call_count, 1)

    def test_an_idempotent_call_retries_transport_failures_too(self):
        urlopen = mock.Mock(side_effect=[urllib.error.URLError(TimeoutError("timed out")), self.ok_response()])
        with mock.patch("urllib.request.urlopen", urlopen):
            self.assertEqual(bridge.http_send(self.request), (200, b"ok"))
        self.assertEqual(urlopen.call_count, 2)

    def test_the_failure_text_names_an_uncertain_outcome(self):
        uncertain = bridge.send_failure(bridge.SendOutcomeUnknown("the connection failed (timed out)"))
        self.assertIn("MAY already be on its way", uncertain)
        self.assertIn("timed out", uncertain)
        certain = bridge.send_failure(ConnectionError("http://stub.example/ unreachable: refused"))
        self.assertIn("telnyx api unreachable", certain)
        self.assertNotIn("MAY already", certain)


class GatewayRetryTest(BridgeCase):
    """The Telnyx sends through the real HTTP path: one attempt, or an honest "may have gone out"."""

    def send_sms(self):
        return self.post_gateway(
            "/gateway/message", {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
        )

    def test_a_telnyx_5xx_costs_exactly_one_attempt_on_every_lane(self):
        for path in ("/v2/messages", "/v2/messages/whatsapp", "/v2/faxes"):
            StubUpstreamHandler.stub_responses[path] = (500, {"errors": [{"detail": "boom"}]})
        status, payload = self.send_sms()
        self.assertEqual((status, payload["error"]), (502, "telnyx rejected the send (HTTP 500): boom"))
        bridge.WHATSAPP_FROM = "+15550100000"
        self.post_gateway(
            "/gateway/message", {"kind": "message", "owner": "1000", "to": "whatsapp:+1234567890", "body": "hi"}
        )
        bridge.FAX_CONNECTION_ID = "234423"
        bridge.FAX_FROM_NUMBER = "+15550100001"
        self.post_gateway(
            "/gateway/fax",
            {"kind": "fax", "owner": "1000", "to": "+15550100002"},
            files=[("fax.pdf", b"%PDF-1.4 x", "application/pdf")],
            file_field="document",
        )
        self.assertEqual(self.hook_paths(), ["/v2/messages", "/v2/messages/whatsapp", "/v2/faxes"])

    def test_a_connection_that_dies_after_the_request_reports_an_uncertain_outcome(self):
        StubUpstreamHandler.stub_faults["/v2/messages"] = drop_without_answer
        status, payload = self.send_sms()
        self.assertEqual(status, 502)
        self.assertIn("MAY already be on its way", payload["error"])
        self.assertIn(bridge.ACTIONABLE_OUTCOME_UNKNOWN, payload["error"])
        self.assertEqual(self.hook_paths(), ["/v2/messages"])  # and never a second attempt

    def test_a_telnyx_timeout_is_uncertain_and_not_repeated(self):
        StubUpstreamHandler.stub_responses["/v2/messages"] = (200, {"data": {"id": "too late"}}, 1.0)
        with mock.patch.object(bridge, "HTTP_TIMEOUT", 0.3):
            status, payload = self.send_sms()
        self.assertEqual(status, 502)
        self.assertIn("MAY already be on its way", payload["error"])
        self.assertEqual(self.hook_paths(), ["/v2/messages"])

    def test_a_refused_telnyx_is_a_plain_outage_not_an_uncertain_send(self):
        # Nobody listens on that port: the first attempt provably sent
        # nothing, so it is repeated once, and the outage is reported as such.
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            dead_port = probe.getsockname()[1]
        bridge.TELNYX_MESSAGES_API = f"http://127.0.0.1:{dead_port}/v2/messages"
        status, payload = self.send_sms()
        self.assertEqual(status, 502)
        self.assertIn("telnyx api unreachable", payload["error"])
        self.assertNotIn("MAY already be on its way", payload["error"])

    def test_a_gateway_timeout_is_uncertain_on_every_lane(self):
        for lane in ("sms", "whatsapp", "fax"):
            with self.subTest(lane):
                StubUpstreamHandler.stub_responses = {
                    path: (200, {"data": {"id": "late"}}, 1.0)
                    for path in ("/v2/messages", "/v2/messages/whatsapp", "/v2/faxes")
                }
                StubUpstreamHandler.seen = []
                bridge.WHATSAPP_FROM = "+15550100000"
                bridge.FAX_CONNECTION_ID = "234423"
                bridge.FAX_FROM_NUMBER = "+15550100001"
                with mock.patch.object(bridge, "HTTP_TIMEOUT", 0.3):
                    if lane == "sms":
                        status, payload = self.send_sms()
                    elif lane == "whatsapp":
                        status, payload = self.post_gateway(
                            "/gateway/message",
                            {"kind": "message", "owner": "1000", "to": "whatsapp:+1234567890", "body": "hi"},
                        )
                    else:
                        status, payload = self.post_gateway(
                            "/gateway/fax",
                            {"kind": "fax", "owner": "1000", "to": "+15550100002"},
                            files=[("fax.pdf", b"%PDF-1.4 x", "application/pdf")],
                            file_field="document",
                        )
                self.assertEqual(status, 502, payload)
                self.assertIn("MAY already be on its way", payload["error"])
                self.assertEqual(len(self.hook_paths()), 1)  # one attempt per lane, never a second


class RequestFramingTest(BridgeCase):
    """An over-cap or unknown request gets exactly one answer, then a clean close."""

    def gateway_request(self, body=b"", content_length=None):
        headers = {
            "Authorization": f"Bearer {WEBPHONE_SECRET}",
            "Content-Type": "multipart/form-data; boundary=x",
        }
        return raw_request("POST", "/gateway/message", body, headers=headers, content_length=content_length)

    @staticmethod
    def split(response):
        head, _, body = response.partition(b"\r\n\r\n")
        return head, body

    def test_an_over_cap_gateway_body_is_refused_before_it_is_read(self):
        # The client lies about its size (declared 9 MiB, nothing sent).
        started = time.monotonic()
        response = raw_exchange(self.gateway_request(content_length=9 << 20), self.port)
        head, body = self.split(response)
        self.assertTrue(head.startswith(b"HTTP/1.1 422 "), head)
        self.assertIn(b"Connection: close", head)
        self.assertEqual(response.count(b"HTTP/1.1 "), 1)  # one answer, not a second parsed from leftover bytes
        payload = json.loads(body)
        self.assertIn("1 MB", payload["error"])
        self.assertNotIn("malformed multipart", payload["error"])
        self.assertLess(time.monotonic() - started, bridge.DRAIN_TIMEOUT_SECONDS + 3)

    def test_an_over_cap_gateway_body_that_is_really_sent_still_gets_its_422(self):
        # 8.5 MiB actually travel. Without the bounded drain the close would
        # reset the connection and the client would never read its answer.
        response = raw_exchange(
            self.gateway_request(b"x" * (bridge.MAX_GATEWAY_BODY + (1 << 19))), self.port, timeout=30
        )
        head, body = self.split(response)
        self.assertTrue(head.startswith(b"HTTP/1.1 422 "), head)
        self.assertEqual(response.count(b"HTTP/1.1 "), 1)
        self.assertIn("8 MiB", json.loads(body)["error"])

    def test_a_peer_that_trickles_an_over_cap_body_is_cut_off_at_the_drain_deadline(self):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=30)
        sock.sendall(self.gateway_request(content_length=9 << 20) + b"x" * 65536)

        def trickle():
            try:
                while True:
                    sock.sendall(b"x")
                    time.sleep(0.05)
            except OSError:
                pass  # the bridge closed the connection: the outcome under test

        threading.Thread(target=trickle, daemon=True).start()
        started = time.monotonic()
        response = b""
        try:
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                response += chunk
        finally:
            sock.close()
        elapsed = time.monotonic() - started
        self.assertTrue(response.startswith(b"HTTP/1.1 422 "), response[:40])
        self.assertEqual(response.count(b"HTTP/1.1 "), 1)
        self.assertLess(elapsed, bridge.DRAIN_TIMEOUT_SECONDS + 2)
        self.assertGreater(elapsed, bridge.DRAIN_TIMEOUT_SECONDS - 0.5)

    def test_an_over_cap_webhook_is_received_once_then_the_connection_closes(self):
        body = b"x" * (bridge.MAX_BODY + 4096)
        request = raw_request("POST", "/telnyx/webhooks", body, headers={"Content-Type": "application/json"})
        response = raw_exchange(request, self.port, timeout=30)
        head, _body = self.split(response)
        self.assertTrue(head.startswith(b"HTTP/1.1 200 "), head)
        self.assertIn(b"Connection: close", head)
        self.assertEqual(response.count(b"HTTP/1.1 "), 1)
        self.assertIn("raw", json.loads(bridge.LOG_FILE.read_text().splitlines()[-1])["body"])

    def test_an_unknown_post_path_is_one_404_and_a_close(self):
        request = raw_request(
            "POST", "/gateway/nothing", b"g" * 100, headers={"Authorization": f"Bearer {WEBPHONE_SECRET}"}
        )
        response = raw_exchange(request, self.port)
        head, _body = self.split(response)
        self.assertTrue(head.startswith(b"HTTP/1.1 404 "), head)
        self.assertIn(b"Connection: close", head)
        self.assertEqual(response.count(b"HTTP/1.1 "), 1)

    def test_ordinary_requests_keep_their_connection_alive(self):
        connection = http_client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            for _ in range(2):
                connection.request("GET", "/telnyx/webhooks/health")
                response = connection.getresponse()
                self.assertEqual((response.status, response.read()), (200, b'{"ok": true}'))
        finally:
            connection.close()


class MediaTargetTest(unittest.TestCase):
    """What fetch_media is willing to dial: the URL alone decides nothing about the host."""

    def test_https_urls_without_userinfo_parse(self):
        self.assertEqual(
            bridge.media_target("https://media.example/a/b.png?x=1&y=%20#fragment"),
            ("media.example", 443, "/a/b.png?x=1&y=%20"),
        )
        self.assertEqual(bridge.media_target("https://Media.Example:8443/x"), ("media.example", 8443, "/x"))
        self.assertEqual(bridge.media_target("https://media.example"), ("media.example", 443, "/"))
        self.assertEqual(bridge.media_target("https://[2606:4700::6810:84e5]/x")[0], "2606:4700::6810:84e5")
        # Characters a URL must not carry raw are percent-encoded; an escape that is already there is left alone.
        self.assertEqual(
            bridge.media_target('https://media.example/a{b}"c.png?sig=ab%2Fcd')[2], "/a%7Bb%7D%22c.png?sig=ab%2Fcd"
        )

    def test_everything_else_is_refused_before_any_socket_opens(self):
        refused = [
            "http://media.example/x.png",
            "ftp://media.example/x",
            "file:///etc/passwd",
            "gopher://media.example/x",
            "//media.example/x",
            "media.example/x",
            "https://user:pass@media.example/x",
            "https://user@media.example/x",
            "https://media.example:70000/x",
            "https://media.example:abc/x",
            "https://m\u00ebdia.example/x",
            "https://media.example/\u00e4.png",
            "https://media.example/a b.png",
            "https://media.example/a\tb",
            "https://media.example/a\x00b",
            "https:///x",
            "https:///",
            "",
            None,
            5,
        ]
        for url in refused:
            with self.subTest(url):
                self.assertIsNone(bridge.media_target(url))


class AddressGateTest(unittest.TestCase):
    """The judgement behind the media gate: which addresses count as public."""

    def test_only_globally_routable_unicast_addresses_are_public(self):
        table = {
            # routable unicast
            "8.8.8.8": True,
            "1.0.0.1": True,
            "93.184.216.34": True,
            "2606:4700::1111": True,
            "2620:fe::fe": True,
            # loopback, private, link-local, CGNAT, unspecified, reserved, documentation
            "127.0.0.1": False,
            "127.8.8.8": False,
            "10.0.0.1": False,
            "192.168.1.1": False,
            "172.16.0.1": False,
            "169.254.169.254": False,  # the cloud metadata address
            "100.64.0.1": False,
            "0.0.0.0": False,
            "240.0.0.1": False,
            "255.255.255.255": False,
            "192.0.2.1": False,
            "198.18.0.1": False,
            "198.51.100.1": False,
            "203.0.113.9": False,
            "::": False,
            "::1": False,
            "fc00::1": False,
            "fd00::1": False,
            "fe80::1": False,
            "fec0::1": False,  # the deprecated site-local space
            "2001:db8::1": False,
            "100::1": False,
            "3fff::1": False,
            # multicast is never a host to fetch from (ipaddress calls it global)
            "224.0.0.1": False,
            "239.255.255.250": False,
            "ff02::1": False,
            "ff0e::1": False,
            # embedded IPv4 forms are judged by the IPv4 they carry
            "::ffff:8.8.8.8": True,
            "::ffff:10.0.0.1": False,
            "::ffff:127.0.0.1": False,
            # 6to4 is deprecated and not globally routed per the IANA registry ipaddress carries
            "2002:0808:0808::": False,
            "2002:0a00:0001::": False,
            "64:ff9b::808:808": True,  # NAT64 of 8.8.8.8
            "64:ff9b::a00:1": False,  # NAT64 of 10.0.0.1
            "64:ff9b:1::a00:1": False,
            # not an address at all
            "garbage": False,
            "": False,
            "media.example": False,
        }
        for text, public in table.items():
            with self.subTest(text):
                self.assertEqual(bridge._is_public_address(text), public)

    def test_a_name_resolving_to_a_private_address_is_refused_before_any_socket_opens(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))]
        with (
            mock.patch.object(bridge.socket, "getaddrinfo", return_value=answers) as resolved,
            mock.patch.object(bridge.socket, "socket") as opened,
            self.assertRaises(PermissionError),
        ):
            bridge._connect_public(("media.example", 443), 5)
        resolved.assert_called_once_with("media.example", 443, 0, socket.SOCK_STREAM)
        opened.assert_not_called()

    def test_one_private_answer_among_public_ones_refuses_the_whole_name(self):
        # A round-robin name that mixes a public and a private address is
        # the classic rebinding trick: the connect must not land on either.
        answers = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (address, 443))
            for address in ("93.184.216.34", "10.0.0.1")
        ]
        with (
            mock.patch.object(bridge.socket, "getaddrinfo", return_value=answers),
            mock.patch.object(bridge.socket, "socket") as opened,
            self.assertRaises(PermissionError),
        ):
            bridge._connect_public(("rebind.example", 443), 5)
        opened.assert_not_called()

    def test_an_answer_that_is_not_an_address_is_refused(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("not-an-address", 443))]
        with (
            mock.patch.object(bridge.socket, "getaddrinfo", return_value=answers),
            mock.patch.object(bridge.socket, "socket") as opened,
            self.assertRaises(PermissionError),
        ):
            bridge._connect_public(("odd.example", 443), 5)
        opened.assert_not_called()

    def test_public_answers_are_tried_in_order_under_the_caller_s_timeout(self):
        addresses = [("93.184.216.34", 443), ("1.0.0.1", 443)]
        infos = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", address) for address in addresses]
        opened = []

        class FakeSocket:
            def __init__(self, *args):
                self.connected = None
                self.timeouts = []
                self.closed = False
                opened.append(self)

            def settimeout(self, value):
                self.timeouts.append(value)

            def connect(self, address):
                self.connected = address
                if address == addresses[0]:
                    raise OSError(errno.ETIMEDOUT, "timed out")

            def close(self):
                self.closed = True

        with (
            mock.patch.object(bridge.socket, "getaddrinfo", return_value=infos),
            mock.patch.object(bridge.socket, "socket", FakeSocket),
        ):
            chosen = bridge._connect_public(("media.example", 443), 7)
        self.assertIs(chosen, opened[1])
        self.assertEqual([sock.connected for sock in opened], addresses)
        self.assertEqual([sock.timeouts for sock in opened], [[7], [7]])
        self.assertEqual([sock.closed for sock in opened], [True, False])

    def test_when_every_address_fails_the_last_error_surfaces(self):
        infos = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("93.184.216.34", 443))]

        class RefusingSocket:
            def __init__(self, *args):
                pass

            def settimeout(self, value):
                pass

            def connect(self, address):
                raise ConnectionRefusedError(errno.ECONNREFUSED, "refused")

            def close(self):
                pass

        with (
            mock.patch.object(bridge.socket, "getaddrinfo", return_value=infos),
            mock.patch.object(bridge.socket, "socket", RefusingSocket),
            self.assertRaises(ConnectionRefusedError),
        ):
            bridge._connect_public(("media.example", 443), 5)

    def test_a_name_that_does_not_resolve_raises_the_resolver_error(self):
        with (
            mock.patch.object(
                bridge.socket, "getaddrinfo", side_effect=socket.gaierror(-2, "Name or service not known")
            ),
            self.assertRaises(socket.gaierror),
        ):
            bridge._connect_public(("no-such-host.invalid", 443), 5)


class ReadCappedTest(unittest.TestCase):
    """The cap bounds what is READ: an unbounded stream costs one byte past it."""

    def test_a_body_within_the_cap_is_returned_and_never_over_asked(self):
        content = b"y" * (300 * 1024)
        cap = len(content) + 5
        body = fake_body(content)
        self.assertEqual(bridge.read_capped(body, cap), content)
        self.assertEqual(body.position, len(content))  # nothing past the body was consumed
        # and no read asks for more than one byte past the cap, nor past a chunk
        # and no read asks for more than a chunk or than the headroom left above what was consumed
        for asked, consumed_before in zip(body.requests, [0, *itertools.accumulate(body.returns)]):
            self.assertLessEqual(asked, min(bridge.MEDIA_FETCH_CHUNK, cap + 1 - consumed_before))

    def test_a_body_over_the_cap_is_refused_one_byte_past_the_cap(self):
        cap = 70 * 1024
        body = fake_body(b"y" * (10 * 1024 * 1024))
        self.assertIsNone(bridge.read_capped(body, cap))
        self.assertEqual(sum(body.requests), cap + 1)
        self.assertLessEqual(max(body.requests), bridge.MEDIA_FETCH_CHUNK)

    def test_an_empty_body_is_not_a_medium(self):
        self.assertIsNone(bridge.read_capped(fake_body(b""), 1024))


class MediaFetchTest(BridgeCase):
    """fetch_media against a scripted loopback origin: the SSRF gate, the cap and one total deadline."""

    def setUp(self):
        super().setUp()
        self.start_media()

    def test_this_host_s_own_services_are_never_contacted(self):
        # THE SSRF pin: a webhook that names the bridge itself, a cloud
        # metadata address or an RFC 1918 host gets nothing, not even a TCP
        # connection (only the gate is the real one here).
        port = self.media.server_address[1]
        for url in (
            f"https://127.0.0.1:{port}/final",
            f"https://localhost:{port}/final",
            f"https://[::1]:{port}/final",
            "https://10.0.0.1/final",
            "https://169.254.169.254/latest/meta-data/",
            "https://192.168.1.1/final",
        ):
            with self.subTest(url):
                self.assertIsNone(bridge.fetch_media(url, deadline=time.monotonic() + 5))
        self.assertEqual(MediaHandler.hits, [])

    def test_a_complete_200_body_is_returned_with_its_media_type(self):
        self.assertEqual(self.fetch("/final")[0], ("image/png", b"final-body"))
        self.assertEqual(self.fetch("/typed")[0], ("image/jpeg", b"typed"))
        self.assertEqual(self.fetch("/chunked")[0], ("image/png", b"helloworld"))

    def test_only_a_complete_200_body_counts(self):
        for path in ("/empty", "/declared-short", "/missing", "/partial", "/redirect-no-location", "/redirect-300"):
            with self.subTest(path):
                result, _seconds = self.fetch(path)
                self.assertIsNone(result)
        # An oversize declaration is refused before a byte of the body is read.
        result, seconds = self.fetch("/declared-big")
        self.assertIsNone(result)
        self.assertLess(seconds, 1.0)

    def test_the_cap_bounds_the_body_with_and_without_a_declared_length(self):
        exact = len(b"final-body")
        self.assertEqual(self.fetch("/final", cap=exact)[0][1], b"final-body")
        self.assertIsNone(self.fetch("/final", cap=exact - 1)[0])
        self.assertEqual(self.fetch("/chunked", cap=10)[0][1], b"helloworld")
        self.assertIsNone(self.fetch("/chunked", cap=9)[0])

    def test_redirects_are_followed_while_they_stay_https_and_public(self):
        for path in ("/redirect-final", "/redirect-relative", "/redirect-chain"):
            with self.subTest(path):
                self.assertEqual(self.fetch(path)[0][1], b"final-body")
                self.assertEqual(MediaHandler.hits[-1], "/final")

    def test_a_redirect_that_leaves_the_rules_ends_the_fetch(self):
        MediaHandler.hits = []
        self.assertIsNone(self.fetch("/redirect-http")[0])
        self.assertEqual(MediaHandler.hits, ["/redirect-http"])  # plain http is never followed
        MediaHandler.hits = []
        self.assertIsNone(self.fetch("/redirect-private")[0])
        self.assertEqual(MediaHandler.hits, ["/redirect-private"])  # and the real gate refuses 10.0.0.1

    def test_a_redirect_loop_ends_after_the_hop_limit(self):
        MediaHandler.hits = []
        self.assertIsNone(self.fetch("/redirect-loop")[0])
        self.assertEqual(MediaHandler.hits, ["/redirect-loop"] * (bridge.MEDIA_MAX_REDIRECTS + 1))

    def test_a_trickling_body_ends_at_the_deadline(self):
        # One byte per 50 ms never trips a socket timeout; only the total deadline ends it.
        result, seconds = self.fetch("/dribble", seconds=0.6)
        self.assertIsNone(result)
        self.assertGreater(seconds, 0.5)
        self.assertLess(seconds, 2.5)

    def test_trickled_headers_end_at_the_deadline(self):
        result, seconds = self.fetch("/slow-headers", seconds=0.6)
        self.assertIsNone(result)
        self.assertGreater(seconds, 0.5)
        self.assertLess(seconds, 2.5)

    def test_a_silent_origin_ends_at_the_deadline(self):
        result, seconds = self.fetch("/hang", seconds=0.6)
        self.assertIsNone(result)
        self.assertGreater(seconds, 0.5)
        self.assertLess(seconds, 2.5)

    def test_one_deadline_bounds_every_medium_of_a_message(self):
        origin = f"https://{self.media_origin}"
        started = time.monotonic()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(bridge, "_connect_public", loopback_only(socket.create_connection)))
            stack.enter_context(mock.patch.object(bridge, "_tls_client_socket", lambda sock, host, deadline_: sock))
            deadline = time.monotonic() + 1.0
            self.assertIsNone(bridge.fetch_media(f"{origin}/dribble", deadline=deadline))
            self.assertIsNone(bridge.fetch_media(f"{origin}/final", deadline=deadline))
        self.assertLess(time.monotonic() - started, 2.0)  # the second medium had nothing left to spend

    def test_the_default_client_context_verifies_certificates_and_host_names(self):
        context = bridge.media_tls_context()
        self.assertIs(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)

    def test_a_verified_tls_origin_is_fetched(self):
        self.start_media(tls=True)
        self.assertEqual(self.fetch("/final", tls=True)[0], ("image/png", b"final-body"))

    def test_an_untrusted_or_a_misnamed_certificate_ends_the_fetch(self):
        self.start_media(tls=True)
        port = self.media.server_address[1]
        with (
            mock.patch.object(bridge, "media_tls_context", ssl.create_default_context),
            mock.patch.object(bridge, "_connect_public", socket.create_connection),
        ):
            self.assertIsNone(bridge.fetch_media(f"https://127.0.0.1:{port}/final", deadline=time.monotonic() + 5))
            misnamed = f"https://localhost:{port}/final"
            self.assertIsNone(bridge.fetch_media(misnamed, deadline=time.monotonic() + 5))
        self.assertEqual(MediaHandler.hits, [])

    def test_a_handshake_that_never_completes_ends_at_the_deadline(self):
        listener = blackhole()
        self.addCleanup(listener.close)
        url = f"https://127.0.0.1:{listener.getsockname()[1]}/final"
        started = time.monotonic()
        with mock.patch.object(bridge, "_connect_public", socket.create_connection):
            self.assertIsNone(bridge.fetch_media(url, deadline=started + 0.6))
        elapsed = time.monotonic() - started
        self.assertGreater(elapsed, 0.5)
        self.assertLess(elapsed, 2.5)

    def test_the_default_deadline_starts_now(self):
        # The deadline argument is optional: fetch_media(url) spends MEDIA_FETCH_SECONDS.
        with (
            mock.patch.object(bridge, "MEDIA_FETCH_SECONDS", 0.5),
            mock.patch.object(bridge, "_connect_public", loopback_only(socket.create_connection)),
            mock.patch.object(bridge, "_tls_client_socket", lambda sock, host, deadline_: sock),
        ):
            started = time.monotonic()
            self.assertIsNone(bridge.fetch_media(f"https://{self.media_origin}/dribble"))
        self.assertLess(time.monotonic() - started, 2.5)


class InboundMediaTest(BridgeCase):
    """How the inbound forward uses the fetch, and what it says about a lost medium."""

    def test_the_fetch_failure_log_line_never_carries_a_signed_url_s_query(self):
        url = "https://media.example/x.png?X-Amz-Signature=SECRETVALUE&X-Amz-Credential=KEYID"
        with (
            mock.patch.object(bridge, "fetch_media", return_value=None),
            mock.patch.object(bridge, "bridge_log") as logged,
        ):
            status, _payload = self.post_event(self.received_event("evt-signed-url", media=[{"url": url}]))
        self.assertEqual(status, 200)
        logged_text = " ".join(f"{call.args} {call.kwargs}" for call in logged.call_args_list)
        self.assertNotIn("SECRETVALUE", logged_text)
        self.assertNotIn("KEYID", logged_text)
        self.assertIn("https://media.example/x.png", logged_text)

    def test_redact_url_drops_the_query_and_any_userinfo(self):
        self.assertEqual(
            bridge.redact_url("https://u:p@media.example:8443/a/b.png?sig=x"), "https://media.example:8443/a/b.png"
        )
        self.assertEqual(bridge.redact_url("https://media.example/x"), "https://media.example/x")
        for not_a_url in (None, 5, "", "::::", "https://:bad/x"):
            with self.subTest(not_a_url):
                self.assertEqual(bridge.redact_url(not_a_url), "")

    def test_no_more_than_the_media_cap_are_fetched_per_message(self):
        media = [{"url": f"https://media.example/{index}.png"} for index in range(bridge.MAX_INBOUND_MEDIA_FILES + 3)]
        with (
            mock.patch.object(bridge, "fetch_media", return_value=("image/png", b"x")) as fetch,
            mock.patch.object(bridge, "bridge_log") as logged,
        ):
            status, _payload = self.post_event(self.received_event("evt-many", media=media))
        self.assertEqual(status, 200)
        self.assertEqual(fetch.call_count, bridge.MAX_INBOUND_MEDIA_FILES)
        lost = next(call for call in logged.call_args_list if call.args[0] == "inbound mms media fetch failed")
        self.assertEqual((lost.kwargs["skipped"], lost.kwargs["forwarded"]), (3, bridge.MAX_INBOUND_MEDIA_FILES))

    def test_every_medium_of_a_message_shares_one_deadline_and_the_lane_cap(self):
        with mock.patch.object(bridge, "fetch_media", return_value=("image/png", b"x")) as fetch:
            self.post_event(
                self.received_event(
                    "evt-mms",
                    type="MMS",
                    media=[{"url": "https://m.example/1.png"}, {"url": "https://m.example/2.png"}],
                )
            )
            first = {call.kwargs["deadline"] for call in fetch.call_args_list}
            self.assertEqual(len(first), 1)
            self.assertEqual({call.kwargs["cap"] for call in fetch.call_args_list}, {bridge.MAX_MEDIA_BYTES})
            fetch.reset_mock()
            self.post_event(
                self.received_event(
                    "evt-wa",
                    type="WHATSAPP",
                    media=[{"url": "https://m.example/1.png"}, {"url": "https://m.example/2.png"}],
                )
            )
            self.assertEqual(len({call.kwargs["deadline"] for call in fetch.call_args_list}), 1)
            self.assertEqual(
                {call.kwargs["cap"] for call in fetch.call_args_list}, {bridge.WHATSAPP_MAX_INBOUND_MEDIA_BYTES}
            )

    def test_fetched_media_ride_as_named_base64_attachments(self):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
        with mock.patch.object(bridge, "fetch_media", return_value=("image/png", png)):
            status, _payload = self.post_event(
                self.received_event(
                    "evt-attach", media=[{"url": "https://media.example/photo one.png?sig=x"}, {"url": 5}]
                )
            )
        self.assertEqual(status, 200)
        encoded = base64.b64encode(png).decode()
        self.assertEqual(
            StubUpstreamHandler.seen[0]["body"]["attachments"],
            [
                {"name": "photo one.png", "mime_type": "image/png", "data_base64": encoded},
                {"name": "media.png", "mime_type": "image/png", "data_base64": encoded},  # a URL that is no string
            ],
        )

    def test_a_fetched_medium_with_an_unexpected_content_type_is_passed_through_as_declared(self):
        with mock.patch.object(bridge, "fetch_media", return_value=("application/octet-stream", b"\x00\x01")):
            status, _payload = self.post_event(
                self.received_event("evt-mime", media=[{"url": "https://media.example/blob"}])
            )
        self.assertEqual(status, 200)
        self.assertEqual(StubUpstreamHandler.seen[0]["body"]["attachments"][0]["mime_type"], "application/octet-stream")


if __name__ == "__main__":
    unittest.main()
