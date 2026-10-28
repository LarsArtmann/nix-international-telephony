"""telephony-recordings-view: the native-OAuth recordings browser.

A stdlib-only HTTP service that replaces the nginx autoindex era of
/recordings/: it lists recorded calls and streams them, and it owns its
own OIDC login (Pocket ID) via the shared oidc_session helper — no
oauth2-proxy, no nginx auth_request (owner directive 2026-10-28: apps
do OAuth natively).

Auth model: every path except /healthz and the /oidc/* routes requires
a verified session cookie; without one the request is redirected into
the login dance. Group membership is enforced at login time
(fail-closed); the session then carries only the username.

nginx proxies this app prefix-stripped (proxy_pass with a trailing
slash), so URL_PREFIX (e.g. "/recordings") is what the app puts on its
OWN links and redirects.

Config (environment, all required unless noted):
  RECORDINGS_DIR            directory with the recorded calls
  HTTP_PORT                 loopback bind port
  URL_PREFIX                public path prefix, e.g. /recordings
  OIDC_ISSUER               https://idp.example.test
  OIDC_CLIENT_ID            confidential client id
  OIDC_CLIENT_SECRET_FILE   client secret file (trailing newline ok)
  OIDC_REDIRECT_URL         public callback, e.g.
                            https://pbx.example.test/recordings/oidc/callback
  SESSION_SECRET_FILE       HMAC key file (trailing newline ok)
  OIDC_REQUIRED_GROUP       optional; login denied without membership
  SESSION_COOKIE_NAME       optional, default "recordings_session"
  SESSION_TTL_SECONDS       optional, default 7 days
"""

import html
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oidc_session import CallbackResult, OidcError, OidcSessionManager  # noqa: E402

CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
}
CHUNK = 256 * 1024


def _env(name, default=None):
    value = os.environ.get(name, default)
    if value is None or value == "":
        print(f"FATAL: recordings-view env missing: {name}", file=sys.stderr, flush=True)
        raise SystemExit(2)
    return value


class App:
    def __init__(self):
        self.recordings_dir = _env("RECORDINGS_DIR")
        self.url_prefix = _env("URL_PREFIX", "/recordings").rstrip("/")
        self.manager = OidcSessionManager(
            issuer_url=_env("OIDC_ISSUER"),
            client_id=_env("OIDC_CLIENT_ID"),
            client_secret_file=_env("OIDC_CLIENT_SECRET_FILE"),
            session_secret_file=_env("SESSION_SECRET_FILE"),
            redirect_url=_env("OIDC_REDIRECT_URL"),
            required_group=os.environ.get("OIDC_REQUIRED_GROUP") or None,
            cookie_name=os.environ.get("SESSION_COOKIE_NAME", "recordings_session"),
            ttl_seconds=int(os.environ.get("SESSION_TTL_SECONDS", str(7 * 24 * 3600))),
        )

    # ---- responses -------------------------------------------------------

    def login_location(self):
        return f"{self.url_prefix}/oidc/login"

    def error_page(self, code):
        body = (
            f"<!doctype html><title>Sign-in failed</title>"
            f"<h1>Sign-in failed</h1><p>reason: <code>sso_error={html.escape(code)}</code></p>"
            f'<p><a href="{html.escape(self.login_location())}">Try again</a></p>'
        )
        return 403, [("Content-Type", "text/html; charset=utf-8")], body.encode("utf-8")

    def index_html(self):
        """Shallow listing of the recordings root; subdirs link to ?d=."""
        rows = []
        root = self.recordings_dir
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            entries = []
        for e in entries:
            if e.startswith("."):
                continue
            full = os.path.join(root, e)
            if os.path.isdir(full):
                href = f"{self.url_prefix}/?d={urllib.parse.quote(e)}"
                rows.append(
                    f'<tr class="d"><td colspan="2"><a href="{html.escape(href)}">{html.escape(e)}/</a></td></tr>'
                )
            else:
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                href = f"{self.url_prefix}/file/{urllib.parse.quote(e)}"
                rows.append(
                    f'<tr><td><a href="{html.escape(href)}">{html.escape(e)}</a></td>'
                    f"<td>{size}</td></tr>"
                )
        listing = "\n".join(rows)
        return (
            "<!doctype html><meta charset=\"utf-8\">"
            f"<title>Recordings</title><h1>Recordings</h1>"
            f"<table>{listing}</table>"
        ).encode("utf-8")

    def listing_for(self, rel_dir):
        """Flat listing of one subdirectory (the ?d= links land here)."""
        target = self.safe_path(rel_dir)
        if target is None or not os.path.isdir(target):
            return None
        rows = []
        parent = os.path.dirname(rel_dir.strip("/"))
        back = self.url_prefix + ("/?d=" + urllib.parse.quote(parent) if parent else "/")
        rows.append(f'<tr><td colspan="2"><a href="{html.escape(back)}">../</a></td></tr>')
        try:
            entries = sorted(os.listdir(target))
        except OSError:
            entries = []
        for e in entries:
            if e.startswith("."):
                continue
            full = os.path.join(target, e)
            rel_f = os.path.normpath(os.path.join(rel_dir.strip("/"), e)).lstrip("/")
            if os.path.isdir(full):
                href = f"{self.url_prefix}/?d={urllib.parse.quote(rel_f)}"
                rows.append(
                    f'<tr class="d"><td colspan="2"><a href="{html.escape(href)}">{html.escape(e)}/</a></td></tr>'
                )
            else:
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                href = f"{self.url_prefix}/file/{urllib.parse.quote(rel_f)}"
                rows.append(
                    f'<tr><td><a href="{html.escape(href)}">{html.escape(e)}</a></td><td>{size}</td></tr>'
                )
        body = (
            "<!doctype html><meta charset=\"utf-8\">"
            f"<title>Recordings</title><h1>Recordings</h1>"
            f"<table>{''.join(rows)}</table>"
        ).encode("utf-8")
        return body

    def safe_path(self, rel):
        """Resolve rel under recordings_dir; None on any traversal attempt."""
        clean = rel.lstrip("/")
        if not clean or "\x00" in clean:
            return None
        candidate = os.path.normpath(os.path.join(self.recordings_dir, clean))
        root = os.path.abspath(self.recordings_dir)
        if candidate != root and not candidate.startswith(root + os.sep):
            return None
        return candidate

    def serve_file(self, rel, range_header):
        path = self.safe_path(rel)
        if path is None or not os.path.isfile(path):
            return 404, [("Content-Type", "text/plain")], b"not found"
        ext = os.path.splitext(path)[1].lower()
        ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
        size = os.path.getsize(path)
        start, end = 0, size - 1
        status = 200
        extra = []
        if range_header and range_header.startswith("bytes="):
            spec = range_header[6:].split(",")[0].strip()
            if "-" in spec:
                a, b = spec.split("-", 1)
                if a == "" and b != "":
                    start = max(0, size - int(b))
                    end = size - 1
                elif a != "":
                    start = int(a)
                    end = int(b) if b != "" else size - 1
                if start <= end < size:
                    status = 206
                    extra.append(("Content-Range", f"bytes {start}-{end}/{size}"))
                else:
                    return (
                        416,
                        [("Content-Range", f"bytes */{size}")],
                        b"range not satisfiable",
                    )
        length = end - start + 1
        headers = [
            ("Content-Type", ctype),
            ("Content-Length", str(length)),
            ("Accept-Ranges", "bytes"),
        ] + extra

        def gen():
            with open(path, "rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(CHUNK, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return status, headers, gen


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version = "telephony-recordings-view/1.0"

        def log_message(self, fmt, *args):  # journald-friendly single lines
            sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _send(self, status, headers, body_or_gen):
            self.send_response(status)
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            if callable(body_or_gen):
                for chunk in body_or_gen:
                    self.wfile.write(chunk)
            else:
                self.wfile.write(body_or_gen)

        def _redirect(self, location, cookies=()):
            self.send_response(302)
            self.send_header("Location", location)
            for c in cookies:
                self.send_header("Set-Cookie", c)
            self.end_headers()

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            path = parsed.path
            try:
                if path == "/healthz":
                    self._send(200, [("Content-Type", "text/plain")], b"ok")
                    return
                if path == "/oidc/login":
                    url, cookies = app.manager.login_redirect()
                    self._redirect(url, cookies)
                    return
                if path == "/oidc/callback":
                    result = app.manager.handle_callback(parsed.query, self.headers.get("Cookie"))
                    self._finish_callback(result)
                    return
                if path == "/oidc/logout":
                    self._redirect(app.login_location(), app.manager.logout_cookies())
                    return
                identity = app.manager.identity(self.headers.get("Cookie"))
                if identity is None:
                    self._redirect(app.login_location())
                    return
                if path in ("", "/"):
                    qs = urllib.parse.parse_qs(parsed.query)
                    rel_dir = (qs.get("d") or [""])[0]
                    if rel_dir:
                        body = app.listing_for(rel_dir)
                        if body is None:
                            self._send(404, [("Content-Type", "text/plain")], b"not found")
                            return
                        self._send(
                            200, [("Content-Type", "text/html; charset=utf-8")], body
                        )
                        return
                    self._send(
                        200,
                        [("Content-Type", "text/html; charset=utf-8")],
                        app.index_html(),
                    )
                    return
                if path.startswith("/file/"):
                    rel = urllib.parse.unquote(path[len("/file/"):])
                    status, headers, gen = app.serve_file(
                        rel, self.headers.get("Range")
                    )
                    self._send(status, headers, gen)
                    return
                self._send(404, [("Content-Type", "text/plain")], b"not found")
            except OidcError as exc:
                status, headers, body = app.error_page(exc.code)
                self._send(status, headers, body)
            except BrokenPipeError:
                pass
            except Exception as exc:  # noqa: BLE001 - last-resort fail-closed page
                print(f"recordings-view: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                self._send(500, [("Content-Type", "text/plain")], b"internal error")

        def _finish_callback(self, result):
            if isinstance(result, CallbackResult) and result.error:
                status, headers, body = app.error_page(result.error)
                self._send(status, headers, body)
                return
            self._redirect(f"{app.url_prefix}/", [result.session_cookie])

    return Handler


def main():
    app = App()
    port = int(_env("HTTP_PORT"))
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    print(f"recordings-view: listening on 127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
