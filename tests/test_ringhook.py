"""Unit tests for the ring-while-closed hook shim (modules/telephony/ringhook.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest discover -s tests -v

A stub upstream server plays webphone's /hooks/ring lane; the shim runs
in-process on an ephemeral port. The contract under test: every WELL-FORMED
ring fact answers 202 (fire-and-forget — the dialplan must never depend on
push health), malformed facts answer 400, a missing credential answers 503,
and the forward carries the Bearer webphone presented.
"""

import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

SHIM_PATH = (
    Path(__file__).resolve().parents[1] / "modules" / "telephony" / "ringhook.py"
)
# The vendored upstream wire contract (tests/ring-wire-contract.json,
# provenance inside): the field-for-field lock this suite enforces. A
# webphone relock that touches internal/server/hooks/ must refresh it
# (relock ritual gate 5) — this test then fails loudly if the shim's
# forward and the vendored contract drift apart.
WIRE_CONTRACT_PATH = Path(__file__).resolve().parent / "ring-wire-contract.json"
WIRE_CONTRACT = json.loads(WIRE_CONTRACT_PATH.read_text(encoding="utf-8"))
CONTRACT_FIELDS = set(WIRE_CONTRACT["fields"])

spec = importlib.util.spec_from_file_location("ringhook", SHIM_PATH)
assert spec is not None and spec.loader is not None, SHIM_PATH
shim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shim)

WEBPHONE_SECRET = "test-webhook-secret-0123456789"


class StubWebphoneHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: ClassVar[list] = []
    status: ClassVar[int] = 202  # webphone's inert 202 posture

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        StubWebphoneHandler.seen.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization", ""),
                "content_type": self.headers.get("Content-Type", ""),
                "body": json.loads(raw) if raw else None,
            }
        )
        body = b"{}"
        self.send_response(StubWebphoneHandler.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def http(method, url, data=None, headers=None):
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 - stub/loopback server
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


class RingHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)

        StubWebphoneHandler.seen = []
        StubWebphoneHandler.status = 202
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), StubWebphoneHandler)
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()

        credentials = tmp / "credentials"
        credentials.mkdir()
        (credentials / "webphone_secret").write_text(WEBPHONE_SECRET)

        shim.CREDENTIALS_DIR = credentials
        shim.SECRET_FILE = credentials / "webphone_secret"
        shim.WEBPHONE_URL = f"http://127.0.0.1:{self.upstream.server_address[1]}"

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), shim.RingHookHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.upstream.shutdown()
        self.upstream.server_close()
        self.tmp.cleanup()

    def post(self, body: bytes):
        return http(
            "POST",
            self.base + "/ring",
            data=body,
            headers={"Content-Type": "application/json"},
        )

    def test_health_endpoint(self):
        status, payload = http("GET", self.base + "/ringhook/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_unknown_paths_404(self):
        status, _ = http("GET", self.base + "/nope")
        self.assertEqual(status, 404)
        status, _ = http(
            "POST",
            self.base + "/nope",
            data=b'{"owner":"1000","state":"ring"}',
            headers={"Content-Type": "application/json"},
        )
        # A POST to a non-/ring path is a dialplan bug: 404, not a silent 202.
        self.assertEqual(status, 404)
        self.assertEqual(StubWebphoneHandler.seen, [])

    def test_ring_fact_forwards_signed_and_answers_202(self):
        fact = {
            "owner": "1000",
            "from": "+4915112345678",
            "call_id": "abc-123",
            "state": "ring",
        }
        status, payload = self.post(json.dumps(fact).encode())
        self.assertEqual(status, 202)
        self.assertEqual(payload["ok"], True)
        self.assertEqual(len(StubWebphoneHandler.seen), 1)
        seen = StubWebphoneHandler.seen[0]
        self.assertEqual(seen["path"], "/hooks/ring")
        self.assertEqual(seen["authorization"], f"Bearer {WEBPHONE_SECRET}")
        self.assertEqual(seen["content_type"], "application/json")
        self.assertEqual(seen["body"], fact)

    def test_forwarded_payload_matches_vendored_wire_contract(self):
        # Field-for-field lock against tests/ring-wire-contract.json: the
        # shim's forward carries EXACTLY the four RingRequest fields, byte
        # per byte on the known-good path. If this fails after a webphone
        # relock, the wire contract moved upstream — refresh the vendored
        # file (and re-diff the dialplan template) per its _provenance.
        self.assertEqual(CONTRACT_FIELDS, {"owner", "from", "call_id", "state"})
        fact = {field: f"value-{field}" for field in sorted(CONTRACT_FIELDS)}
        fact["owner"] = "1000"
        fact["state"] = "ring"
        status, _ = self.post(json.dumps(fact).encode())
        self.assertEqual(status, 202)
        seen = StubWebphoneHandler.seen[0]
        self.assertEqual(set(seen["body"]), CONTRACT_FIELDS)
        self.assertEqual(seen["body"], fact)
        # The doc-example trap (contract _doc_example_trap): auth rides
        # the Bearer header only — a secret never rides the fact body,
        # and the contract fields contain no such key.
        self.assertNotIn("secret", seen["body"])
        self.assertTrue(seen["authorization"].startswith("Bearer "))

    def test_end_fact_forwards_too(self):
        fact = {
            "owner": "1000",
            "from": "+4915112345678",
            "call_id": "abc-123",
            "state": "end",
        }
        status, _ = self.post(json.dumps(fact).encode())
        self.assertEqual(status, 202)
        self.assertEqual(StubWebphoneHandler.seen[0]["body"]["state"], "end")

    def test_malformed_facts_answer_400_without_forwarding(self):
        for bad in (
            b"not json at all",
            b'["an","array"]',
            b'{"owner":"abc","state":"ring"}',
            b'{"owner":"1000","state":"sneaky"}',
            b'{"state":"ring"}',
        ):
            with self.subTest(body=bad):
                status, _ = self.post(bad)
                self.assertEqual(status, 400)
        self.assertEqual(StubWebphoneHandler.seen, [])

    def test_dead_webphone_still_answers_202(self):
        # Unreachable upstream: logged, answered 202 — the push lane's
        # availability must never ring-block the PBX.
        shim.WEBPHONE_URL = "http://127.0.0.1:1"  # nothing listens there
        fact = {
            "owner": "1000",
            "from": "+4915112345678",
            "call_id": "abc-123",
            "state": "ring",
        }
        status, payload = self.post(json.dumps(fact).encode())
        self.assertEqual(status, 202)
        self.assertEqual(payload["verdict"], 0)

    def test_missing_credential_answers_503(self):
        shim.SECRET_FILE = Path(self.tmp.name) / "credentials" / "absent"
        fact = {
            "owner": "1000",
            "from": "+4915112345678",
            "call_id": "abc-123",
            "state": "ring",
        }
        status, _ = self.post(json.dumps(fact).encode())
        self.assertEqual(status, 503)
        self.assertEqual(StubWebphoneHandler.seen, [])


if __name__ == "__main__":
    unittest.main()
