#!/usr/bin/env python3
"""FreeSWITCH directory bridge: answers mod_xml_curl directory lookups
with the session-derived SIP credentials webphone's internal directory
endpoint holds.

Contract (the two sides of the seam):

- FreeSWITCH posts form-encoded ``user``/``domain``/``action``
  (``sip_auth`` at REGISTER, ``group_call`` for ring groups) to
  ``POST /fs-directory``.
- mod_xml_curl (FreeSWITCH 1.11.1) speaks HTTP Basic ONLY — its
  ``auth-scheme`` parser knows basic/digest/NTLM/GSS/any and SILENTLY
  IGNORES anything else (verified in v1.11.1 source, 2026-10-12: a
  ``bearer`` value silently degrades to Basic with no log line). The
  binding therefore renders ``gateway-credentials = webphone:<secret>``
  and the bridge accepts Basic with the PASSWORD equal to the shared
  secret (username is cosmetic). The Bearer form stays accepted for
  curl probes and any future FS that grows real bearer support — both
  carry the SAME secret webphone derives under.
- The bridge proxies the user to webphone's
  ``GET /internal/directory/<user>`` (Bearer: the SAME secret) and
  renders the answered credentials as a FreeSWITCH directory XML
  document.
- Anyone webphone does not know (no live session, unknown extension) or
  ANY webphone unreachability answers the ``not-found`` document —
  FreeSWITCH then falls through to the next configured binding (the
  module's static fallback). The bridge NEVER invents a credential and
  NEVER answers from its own state: revocation stays webphone's truth
  (logout kills the derived credential at the next REGISTER), and a
  webphone outage degrades exactly like a not-found.

Fail-closed posture: the endpoint answers only on the loopback bind,
with the correct credential (systemd ``LoadCredential``), and with a
configured webphone URL. Any half configuration disables the service —
a directory that half-works is worse than one that is down.
"""

import base64
import hashlib
import hmac
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WEBPHONE_URL = os.environ.get("WEBPHONE_URL", "").rstrip("/")
PORT = int(os.environ.get("PORT", "8071"))
TIMEOUT = float(os.environ.get("WEBPHONE_TIMEOUT", "3"))


def load_credential(name: str) -> str:
    """Read one systemd credential; PLACEHOLDER* counts as absent (the
    module's honest-placeholder convention) and an absent secret disables
    the gate (every request then answers 503 — fail closed)."""
    directory = os.environ.get("CREDENTIALS_DIRECTORY", "")
    try:
        with open(os.path.join(directory, name), "rb") as fh:
            value = fh.read().decode("utf-8").strip()
    except OSError:
        return ""
    if value.startswith("PLACEHOLDER"):
        return ""
    return value


DIRECTORY_SECRET = load_credential("webphone_directory_secret")


def constant_time_equal(provided: str, want: str) -> bool:
    provided_digest = hashlib.sha256(provided.encode()).digest()
    want_digest = hashlib.sha256(want.encode()).digest()
    return hmac.compare_digest(provided_digest, want_digest)


def authorized(header: str) -> bool:
    """True when the Authorization header carries the shared secret:
    ``Basic base64(user:secret)`` (what mod_xml_curl actually sends) or
    ``Bearer secret`` (curl probes / future FS). Everything else fails
    closed; comparisons stay constant-time on digests."""
    if header.startswith("Basic "):
        try:
            decoded = base64.b64decode(header[len("Basic ") :]).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        _user, sep, password = decoded.partition(":")
        if not sep:
            return False
        return constant_time_equal(password, DIRECTORY_SECRET)
    if header.startswith("Bearer "):
        return constant_time_equal(header[len("Bearer ") :], DIRECTORY_SECRET)
    return False


def query_webphone(extension: str):
    """Ask webphone for the extension's live derived credentials. Returns
    the credential list, or None on ANY failure (unknown, unreachable,
    non-200) — None means the not-found fall-through."""
    if not WEBPHONE_URL:
        return None
    url = f"{WEBPHONE_URL}/internal/directory/{urllib.parse.quote(extension, safe='')}"
    request = urllib.request.Request(url)
    request.add_header("Authorization", f"Bearer {DIRECTORY_SECRET}")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    credentials = payload.get("credentials")
    if not isinstance(credentials, list):
        return None
    return [c for c in credentials if isinstance(c, str) and c]


def xml_escape(value: str) -> str:
    return html.escape(value, quote=True)


def directory_document(domain: str, user: str, credentials) -> str:
    """The FreeSWITCH directory answer: one document, one user, the
    first derived credential as the password (webphone lists one per
    live session; any of them is valid, the first is deterministic)."""
    password = xml_escape(credentials[0])
    a1 = xml_escape(a1_hash(user, domain, credentials[0]))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<document type="freeswitch/xml">\n'
        '  <section name="directory" description="Dynamic Directory">\n'
        f'    <domain name="{xml_escape(domain)}">\n'
        f'      <user id="{xml_escape(user)}">\n'
        "        <params>\n"
        f'          <param name="password" value="{password}"/>\n'
        f'          <param name="a1-hash" value="{a1}"/>\n'
        "        </params>\n"
        "      </user>\n"
        "    </domain>\n"
        "  </section>\n"
        "</document>\n"
    )


def a1_hash(user: str, domain: str, password: str) -> str:
    digest = hashlib.md5(f"{user}:{domain}:{password}".encode()).hexdigest()
    return digest


def not_found_document() -> str:
    """The fall-through answer: FreeSWITCH continues with the next
    binding (the module's static fallback)."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<document type="freeswitch/xml">\n'
        '  <section name="directory" description="Not Found">\n'
        "    <not-found/>\n"
        "  </section>\n"
        "</document>\n"
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "fs-directory/1.0"

    def log_message(self, fmt, *args):  # JSON-ish single line to the journal
        print(self.log_date_time_string(), fmt % args, flush=True)

    def _fail_closed(self) -> bool:
        if not DIRECTORY_SECRET or not WEBPHONE_URL:
            self.send_response(503)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"fs-directory not configured\n")
            return True
        return False

    def do_GET(self):
        if self._fail_closed():
            return
        if self.path.split("?")[0] != "/health":
            self.send_response(404)
            self.end_headers()
            return
        body = b'{"status":"ok"}\n'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self._fail_closed():
            return
        if self.path.split("?")[0] != "/fs-directory":
            self.send_response(404)
            self.end_headers()
            return
        provided = self.headers.get("Authorization") or ""
        if not authorized(provided):
            self.send_response(401)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        form = urllib.parse.parse_qs(
            self.rfile.read(min(length, 64 * 1024)).decode("utf-8", "replace")
        )
        user = (form.get("user") or [""])[0]
        domain = (form.get("domain") or [""])[0]
        if not user or not domain:
            self.send_response(400)
            self.end_headers()
            return
        credentials = query_webphone(user)
        # Journal the ANSWER SHAPE (never the values): this one line
        # decides "webphone still lists a dead session" vs "sofia accepted
        # an unknown user" when a revoked credential still registers.
        print(
            self.log_date_time_string(),
            f"directory query user={user} domain={domain} credentials={len(credentials or [])}",
            flush=True,
        )
        if credentials:
            body = directory_document(domain, user, credentials).encode("utf-8")
        else:
            body = not_found_document().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/xml")
        self.send_header("Content-Length", str(len(body)))
        # Every REGISTER re-queries: the answer must never be cached by
        # anything between FreeSWITCH and the bridge (revocation latency).
        # BOTH 200 shapes ride this one response — the credential
        # document AND the not-found fall-through — so this single header
        # covers both; no other path serves a cacheable directory answer.
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    bind = ("127.0.0.1", PORT)
    server = ThreadingHTTPServer(bind, Handler)
    print(f"fs-directory listening on http://{bind[0]}:{bind[1]}", flush=True)
    server.serve_forever()
