#!/usr/bin/env python3
"""In-VM stub Telnyx for the messaging suite's WhatsApp arms.

A stdlib HTTP server that plays the two API surfaces the bridge calls
outbound, so the VM test proves the REAL wiring (unit → bridge →
loopback HTTP) instead of unit-test mocks:

  POST /v2/messages          -> 200 {"data": {"id": "stub-sms-<n>"}}
  POST /v2/messages/whatsapp -> 200 {"data": {"id": "stub-wa-<n>"}}
                                ... unless the request text carries the
                                magic marker WINDOW_CLOSED, then the real
                                40008 window-refusal shape
  GET  /healthz              -> 200 {"ok": true}

Every request is appended (JSONL) to the --log file: method, path and
parsed body, so the suite asserts WHAT the bridge sent, not just that it
did. Run on loopback only — it is a test double, never a production
surface:

    python3 /etc/telnyx_stub.py --port 4545 --log /tmp/telnyx-stub.jsonl
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser = argparse.ArgumentParser(description="stub Telnyx API")
parser.add_argument("--port", type=int, default=4545)
parser.add_argument("--log", default="/tmp/telnyx-stub.jsonl")
args = parser.parse_args()

LOG = Path(args.log)
counter = [0]


class StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *a):
        pass

    def reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self.reply(200, {"ok": True})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"raw": raw.decode("utf-8", "replace")}
        with LOG.open("a") as handle:
            handle.write(
                json.dumps({"method": "POST", "path": self.path, "body": body}) + "\n"
            )
        counter[0] += 1
        if "whatsapp" in self.path and "WINDOW_CLOSED" in json.dumps(body):
            self.reply(
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
            return
        self.reply(200, {"data": {"id": f"stub-{counter[0]}"}})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", args.port), StubHandler).serve_forever()
