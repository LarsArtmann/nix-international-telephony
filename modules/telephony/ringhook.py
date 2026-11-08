#!/usr/bin/env python3
"""The ring-while-closed hook shim: FreeSWITCH's dialplan -> webphone /hooks/ring.

mod_curl (the dialplan application) cannot hold the webhook secret: the
dialplan XML is store-rendered and world-readable by construction. So the
dialplan posts the compact-JSON ring fact to THIS loopback service and the
shim attaches the Bearer (``webphone_secret``, the SAME credential file the
Telnyx bridge uses) and forwards to the webphone ``/hooks/ring`` lane.

Fire-and-forget by contract (webphone AGENTS: the dialplan must never
depend on push health): every WELL-FORMED ring fact answers 202 regardless
of the forward verdict; a failed forward is logged, never retried (the
push transports prune their own dead devices, and the next call re-arms
everything). A malformed fact answers 400 — that is a dialplan bug, and
the log line is how it gets found.

Wire from FS (mod_curl app grammar source-verified 2026-11-08 against
mod_curl.c: ``content-type <mime> post <data>`` where <data> is ONE
URL-decoded token): compact JSON, quotes percent-encoded by the dialplan —
{"owner":"1001","from":"+49…","call_id":"<uuid>","state":"ring"|"end"}.

Secrets arrive via systemd ``LoadCredential`` (exposed through the
CREDENTIALS_DIRECTORY convention — the same reading the Telnyx bridge
uses), so nothing secret lands in the Nix store or the process env.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# systemd exposes LoadCredential files at /run/credentials/<unit>.service/
# and exports $CREDENTIALS_DIRECTORY pointing there (since v244).
CREDENTIALS_DIR = Path(
    os.environ.get("CREDENTIALS_DIRECTORY")
    or os.environ.get("CREDENTIALS_DIR")
    or "/run/credentials/ringhook.service"
)
SECRET_FILE = CREDENTIALS_DIR / "webphone_secret"

BIND = ("127.0.0.1", int(os.environ.get("PORT", "8071")))
WEBPHONE_URL = os.environ.get("WEBPHONE_URL", "http://127.0.0.1:8080").rstrip("/")

MAX_BODY = 4 << 10  # a ring fact is four short fields; 4 KiB is generous
VALID_STATES = ("ring", "end")
FORWARD_TIMEOUT = 3  # seconds; the webphone lane answers 202 inertly fast


def secret() -> str:
    """The shared webhook secret, read per request (never cached): the
    same discipline the webphone login mode applies to its password
    files, so a rotated secret bites on the next ring without a unit
    restart."""
    try:
        value = SECRET_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    return value


class RingHookHandler(BaseHTTPRequestHandler):
    server_version = "ringhook/1.0"

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        sys.stderr.write("ringhook: %s\n" % (fmt % args))

    def _json_bytes(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - stdlib name
        if self.path == "/ringhook/health":
            self._json_bytes(200, {"ok": True})
            return
        self._json_bytes(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802 - stdlib name
        if self.path != "/ring":
            self._json_bytes(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._json_bytes(400, {"error": "bad length"})
            return
        raw = self.rfile.read(length)
        try:
            fact = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_bytes(400, {"error": "body is not JSON"})
            return
        if not isinstance(fact, dict):
            self._json_bytes(400, {"error": "body is not an object"})
            return
        owner = fact.get("owner")
        state = fact.get("state")
        if (
            not isinstance(owner, str)
            or not owner.isdigit()
            or state not in VALID_STATES
        ):
            self._json_bytes(
                400,
                {"error": "owner must be digits and state ring|end"},
            )
            return
        bearer = secret()
        if not bearer:
            # The credential file is missing/empty: the unit start should
            # have failed on it; if it still happened, fail loudly here.
            self._json_bytes(503, {"error": "webphone_secret credential unreadable"})
            return
        body = json.dumps(fact, separators=(",", ":")).encode()
        request = urllib.request.Request(
            WEBPHONE_URL + "/hooks/ring",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + bearer,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=FORWARD_TIMEOUT) as res:
                verdict = res.status
        except urllib.error.HTTPError as err:
            verdict = err.code
        except OSError as err:
            # Unreachable webphone: logged, answered 202 — the push lane's
            # availability must never ring-block the PBX.
            print(f"ringhook: forward failed: {err}", file=sys.stderr)
            verdict = 0
        print(f"ringhook: forwarded {state} for {owner}: verdict {verdict}", file=sys.stderr)
        self._json_bytes(202, {"ok": True, "verdict": verdict})


if __name__ == "__main__":
    server = ThreadingHTTPServer(BIND, RingHookHandler)
    print(f"ringhook: listening on {BIND[0]}:{BIND[1]} -> {WEBPHONE_URL}/hooks/ring", file=sys.stderr)
    server.serve_forever()
