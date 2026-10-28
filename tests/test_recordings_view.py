"""Unit tests for the native-OAuth recordings browser
(packages/telephony-recordings-view/recordings_view.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest tests.test_recordings_view

Pins: the traversal-safe path resolver, the listing shapes, Range
streaming (200/206/416), and the auth contract over a REAL socket —
unauthenticated requests redirect into the login dance, the full OIDC
callback (mocked IdP legs) mints a session that unlocks the listing and
file streaming, and a group-missing identity answers the typed
sso_error=group page.
"""

import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from http.cookies import SimpleCookie
from pathlib import Path
from unittest import mock

APP_PATH = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "telephony-recordings-view"
    / "recordings_view.py"
)

# The app imports oidc_session from its own directory (the nix build
# installs them side by side); from the source tree the helper lives in
# modules/telephony.
import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules" / "telephony"))

spec = importlib.util.spec_from_file_location("recordings_view", APP_PATH)
assert spec is not None and spec.loader is not None, APP_PATH
rv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rv)

DISCOVERY_DOC = {
    "authorization_endpoint": "https://idp.example.test/authorize",
    "token_endpoint": "https://idp.example.test/token",
    "userinfo_endpoint": "https://idp.example.test/userinfo",
}


def _write_secret(value):
    fh = tempfile.NamedTemporaryFile("w", suffix=".secret", delete=False)
    fh.write(value + "\n")
    fh.close()
    return fh.name


class Env:
    """A recordings tree + the app env; used directly and by the server."""

    def __init__(self, required_group="pbx-recordings"):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "2026" / "10").mkdir(parents=True)
        (root / "2026" / "10" / "call-abc.wav").write_bytes(b"RIFF" + b"\x00" * 200)
        (root / "note.txt").write_text("hello")
        self.client_secret = _write_secret("client-secret-value")
        self.session_secret = _write_secret("session-hmac-key")
        self._old_env = {}
        self.env = {
            "RECORDINGS_DIR": str(root),
            "HTTP_PORT": "0",
            "URL_PREFIX": "/recordings",
            "OIDC_ISSUER": "https://idp.example.test",
            "OIDC_CLIENT_ID": "pbx-recordings",
            "OIDC_CLIENT_SECRET_FILE": self.client_secret,
            "OIDC_REDIRECT_URL": "https://pbx.example.test/recordings/oidc/callback",
            "SESSION_SECRET_FILE": self.session_secret,
            "OIDC_REQUIRED_GROUP": required_group,
        }

    def __enter__(self):
        self._old_env = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        return self

    def __exit__(self, *exc):
        for k, v in self._old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


class SafePathTest(unittest.TestCase):
    def test_traversal_refused(self):
        with Env() as env:
            app = rv.App()
            self.assertIsNone(app.safe_path("../../etc/passwd"))
            self.assertIsNone(app.safe_path("/etc/passwd"))
            self.assertIsNone(app.safe_path("a/../../b"))

    def test_valid_path_resolves_inside(self):
        with Env():
            app = rv.App()
            resolved = app.safe_path("2026/10/call-abc.wav")
            self.assertTrue(resolved.startswith(os.path.abspath(app.recordings_dir)))


class ListingTest(unittest.TestCase):
    def test_index_lists_dirs_and_files(self):
        with Env():
            app = rv.App()
            body = app.index_html()
            self.assertIn("2026/", body)
            self.assertIn("note.txt", body)

    def test_listing_for_subdir_and_traversal(self):
        with Env():
            app = rv.App()
            body = app.listing_for("2026/10")
            self.assertIn("call-abc.wav", body)
            self.assertIn("../", body)
            self.assertIsNone(app.listing_for("../.."))


class ServeFileTest(unittest.TestCase):
    def test_full_and_range_serves(self):
        with Env():
            app = rv.App()
            status, headers, gen_fn = app.serve_file("2026/10/call-abc.wav", None)
            body = b"".join(gen_fn())
            self.assertEqual(status, 200)
            self.assertEqual(dict(headers)["Content-Type"], "audio/wav")
            self.assertEqual(len(body), 204)

            status, headers, gen_fn = app.serve_file("2026/10/call-abc.wav", "bytes=0-99")
            body = b"".join(gen_fn())
            self.assertEqual(status, 206)
            self.assertEqual(len(body), 100)
            self.assertIn("Content-Range", dict(headers))

            status, headers, body = app.serve_file("2026/10/call-abc.wav", "bytes=99999-")
            self.assertEqual(status, 416)

            status, headers, body = app.serve_file("missing.wav", None)
            self.assertEqual(status, 404)


def _fake_urlopen(userinfo):
    def fake(req, timeout=None):
        url = str(req.full_url if hasattr(req, "full_url") else req)
        if "openid-configuration" in url:
            return _Json(DISCOVERY_DOC)
        if url.endswith("/token"):
            return _Json({"access_token": "at-1"})
        if url.endswith("/userinfo"):
            return _Json(userinfo)
        raise AssertionError(url)

    return fake


class _Json:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


class HttpFlowTest(unittest.TestCase):
    """The auth contract over a real socket, IdP legs mocked."""

    def _serve(self):
        app = rv.App()
        server = rv.ThreadingHTTPServer(("127.0.0.1", 0), rv.make_handler(app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def _get(self, url, headers=None):
        req = urllib.request.Request(url, headers=headers or {})
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as err:
            try:
                return err.code, dict(err.headers), err.read()
            finally:
                err.close()

    def test_healthz_and_auth_redirect(self):
        with Env():
            base = self._serve()
            status, headers, body = self._get(base + "/healthz")
            self.assertEqual(status, 200)
            status, headers, body = self._get(base + "/")
            self.assertEqual(status, 302)
            self.assertEqual(headers["Location"], "/recordings/oidc/login")

    def test_full_login_dance_unlocks_content(self):
        with Env() as env:
            base = self._serve()
            with mock.patch.object(
                rv.urllib.request, "urlopen", side_effect=_fake_urlopen(
                    {"sub": "u1", "preferred_username": "lars", "groups": ["pbx-recordings"]}
                )
            ):
                status, headers, _ = self._get(base + "/oidc/login")
                self.assertEqual(status, 302)
                authorize = headers["Location"]
                self.assertIn("code_challenge_method=S256", authorize)
                state_cookie = SimpleCookie()
                state_cookie.load(headers["Set-Cookie"])
                state_value = list(state_cookie.values())[0].value
                state = urllib.parse.parse_qs(urllib.parse.urlsplit(authorize).query)["state"][0]
                self.assertEqual(state, state_value)

                status, headers, body = self._get(
                    base + f"/oidc/callback?code=good&state={state}",
                    {"Cookie": f"recordings_session_state={state_value}"},
                )
            self.assertEqual(status, 302)
            self.assertEqual(headers["Location"], "/recordings/")
            session_cookie = headers["Set-Cookie"].split(";")[0]

            status, headers, body = self._get(base + "/", {"Cookie": session_cookie})
            self.assertEqual(status, 200)
            page = body.decode()
            self.assertIn("2026/", page)

            status, headers, body = self._get(
                base + "/?d=2026/10", {"Cookie": session_cookie}
            )
            self.assertEqual(status, 200)
            self.assertIn("call-abc.wav", body.decode())

            status, headers, body = self._get(
                base + "/file/2026/10/call-abc.wav", {"Cookie": session_cookie}
            )
            self.assertEqual(status, 200)
            self.assertEqual(len(body), 204)

    def test_group_denial_is_typed(self):
        with Env(required_group="pbx-recordings"):
            base = self._serve()
            with mock.patch.object(
                rv.urllib.request, "urlopen", side_effect=_fake_urlopen(
                    {"sub": "u2", "preferred_username": "eve", "groups": ["phone"]}
                )
            ):
                status, headers, _ = self._get(base + "/oidc/login")
                authorize = headers["Location"]
                state_cookie = SimpleCookie()
                state_cookie.load(headers["Set-Cookie"])
                state_value = list(state_cookie.values())[0].value
                state = urllib.parse.parse_qs(urllib.parse.urlsplit(authorize).query)["state"][0]
                status, headers, body = self._get(
                    base + f"/oidc/callback?code=good&state={state}",
                    {"Cookie": f"recordings_session_state={state_value}"},
                )
            self.assertEqual(status, 403)
            self.assertIn("sso_error=group", body.decode())


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


if __name__ == "__main__":
    unittest.main()
