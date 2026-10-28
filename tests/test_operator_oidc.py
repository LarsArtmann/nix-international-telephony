"""Unit tests for the operator app's native-OAuth routes
(packages/telephony-operator/api.py, authMode "oidc").

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest tests.test_operator_oidc

Pins the gate contract over a real socket: the oidc routes are reachable
unauthenticated, /api/* answers 401 JSON without a session and passes the
gate with one, the webroot index and static assets are session-gated, and
a group-missing identity answers the typed sso_error page. CONFIG stays
None throughout: no test reaches the FreeSWITCH-backed handlers.
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

API_PATH = (
    Path(__file__).resolve().parents[1] / "packages" / "telephony-operator" / "api.py"
)

# The api.py imports oidc_session from its own directory (the nix build
# installs them side by side); from the source tree the helper lives in
# modules/telephony.
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "modules" / "telephony"))

spec = importlib.util.spec_from_file_location("telephony_operator_api", API_PATH)
assert spec is not None and spec.loader is not None, API_PATH
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

DISCOVERY_DOC = {
    "authorization_endpoint": "https://idp.example.test/authorize",
    "token_endpoint": "https://idp.example.test/token",
    "userinfo_endpoint": "https://idp.example.test/userinfo",
}


class _Json:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


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


# The helper module owns the urlopen call sites (api.py only hosts the
# routes), so the IdP legs are patched there. Importing it directly is
# the same module object api.py's _load_oidc() will import (sys.modules
# cache).
import oidc_session as oidc_helper  # noqa: E402

class OperatorOidcTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        webroot = Path(cls.tmp.name) / "webroot"
        webroot.mkdir()
        (webroot / "index.html").write_text("<html><body>operator window</body></html>")
        (webroot / "operator.css").write_text("body{}")
        cls.client_secret = cls._secret("client-secret-value")
        cls.session_secret = cls._secret("session-hmac-key")
        cls._old = {k: os.environ.get(k) for k in cls._env_keys()}
        os.environ.update(
            {
                "OIDC_ISSUER": "https://idp.example.test",
                "OIDC_CLIENT_ID": "pbx-operator",
                "OIDC_CLIENT_SECRET_FILE": cls.client_secret,
                "SESSION_SECRET_FILE": cls.session_secret,
                "OIDC_REDIRECT_URL": "https://pbx.example.test/operator/oidc/callback",
                "OIDC_REQUIRED_GROUP": "pbx-operator",
                "OPERATOR_WEBROOT": str(webroot),
            }
        )
        api.OPERATOR_WEBROOT = os.environ["OPERATOR_WEBROOT"]
        api.OPERATOR_URL_PREFIX = "/operator"
        api.OIDC = api._load_oidc()

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        cls.tmp.cleanup()

    @staticmethod
    def _env_keys():
        return (
            "OIDC_ISSUER",
            "OIDC_CLIENT_ID",
            "OIDC_CLIENT_SECRET_FILE",
            "SESSION_SECRET_FILE",
            "OIDC_REDIRECT_URL",
            "OIDC_REQUIRED_GROUP",
            "OPERATOR_WEBROOT",
        )

    @staticmethod
    def _secret(value):
        fh = tempfile.NamedTemporaryFile("w", suffix=".secret", delete=False)
        fh.write(value + "\n")
        fh.close()
        return fh.name

    def setUp(self):
        self.server = api.ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def _get(self, path, headers=None):
        req = urllib.request.Request(self.base + path, headers=headers or {})
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=5) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as err:
            try:
                return err.code, dict(err.headers), err.read()
            finally:
                err.close()

    def _dance(self):
        with mock.patch.object(
            api.urllib.request,
            "urlopen",
            side_effect=_fake_urlopen(
                {"sub": "u1", "preferred_username": "lars", "groups": ["pbx-operator"]}
            ),
        ):
            status, headers, _ = self._get("/oidc/login")
            self.assertEqual(status, 302)
            authorize = headers["Location"]
            jar = SimpleCookie()
            jar.load(headers["Set-Cookie"])
            state_value = list(jar.values())[0].value
            state = urllib.parse.parse_qs(urllib.parse.urlsplit(authorize).query)[
                "state"
            ][0]
            status, headers, _ = self._get(
                f"/oidc/callback?code=good&state={state}",
                {"Cookie": f"operator_session_state={state_value}"},
            )
        self.assertEqual(status, 302)
        return headers["Set-Cookie"].split(";")[0]

    def test_load_oidc_requires_full_config(self):
        with mock.patch.dict(
            os.environ, {"OIDC_ISSUER": "https://idp.example.test"}, clear=False
        ):
            for k in self._env_keys():
                if k != "OIDC_ISSUER":
                    os.environ.pop(k, None)
            with self.assertRaises(SystemExit):
                api._load_oidc()

    def test_login_redirects_with_state_cookie(self):
        with mock.patch.object(
            api.urllib.request,
            "urlopen",
            side_effect=_fake_urlopen({"sub": "x", "groups": []}),
        ):
            status, headers, _ = self._get("/oidc/login")
        self.assertEqual(status, 302)
        self.assertIn("operator_session_state=", headers["Set-Cookie"])
        self.assertIn("client_id=pbx-operator", headers["Location"])

    def test_api_gate_401_then_passes_with_session(self):
        status, _, body = self._get("/api/whatever")
        self.assertEqual(status, 401)
        self.assertIn(b"sso_error", body)
        session = self._dance()
        status, _, _ = self._get("/api/whatever", {"Cookie": session})
        self.assertEqual(status, 404)  # past the gate; no such endpoint

    def test_index_and_static_are_session_gated(self):
        status, headers, _ = self._get("/")
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], "/operator/oidc/login")
        status, headers, _ = self._get("/operator.css")
        self.assertEqual(status, 302)
        session = self._dance()
        status, headers, body = self._get("/", {"Cookie": session})
        self.assertEqual(status, 200)
        self.assertIn(b"operator window", body)
        status, headers, body = self._get("/operator.css", {"Cookie": session})
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/css")

    def test_group_denial_is_typed(self):
        with mock.patch.object(
            api.urllib.request,
            "urlopen",
            side_effect=_fake_urlopen(
                {"sub": "u2", "preferred_username": "eve", "groups": ["phone"]}
            ),
        ):
            status, headers, _ = self._get("/oidc/login")
            authorize = headers["Location"]
            jar = SimpleCookie()
            jar.load(headers["Set-Cookie"])
            state_value = list(jar.values())[0].value
            state = urllib.parse.parse_qs(urllib.parse.urlsplit(authorize).query)[
                "state"
            ][0]
            status, _, body = self._get(
                f"/oidc/callback?code=good&state={state}",
                {"Cookie": f"operator_session_state={state_value}"},
            )
        self.assertEqual(status, 403)
        self.assertIn(b"sso_error=group", body)

    def test_healthz_stays_open(self):
        # healthz probes the voicemail DB; CONFIG is None here so the
        # handler errors — but the AUTH gate must not be what stops it:
        # a 500 (probe failure) proves the route was reachable.
        status, _, _ = self._get("/healthz")
        self.assertIn(status, (200, 500, 503))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


if __name__ == "__main__":
    unittest.main()
