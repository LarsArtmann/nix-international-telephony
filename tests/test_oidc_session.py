"""Unit tests for the shared OIDC session helper
(modules/telephony/oidc_session.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest tests.test_oidc_session

Pins the fail-closed contract: typed error codes on every failure path
(config/discovery/exchange/userinfo/group/state/unavailable), the PKCE
S256 authorize shape, single-use state, identity from userinfo (never a
locally-verified id_token), HMAC session round-trip with tamper/expiry
refusal, and the secret-file shape (trailing newlines stripped, empty
refused).
"""

import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "modules" / "telephony" / "oidc_session.py"

spec = importlib.util.spec_from_file_location("oidc_session", MODULE_PATH)
assert spec is not None and spec.loader is not None, MODULE_PATH
oidc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oidc)

DISCOVERY_DOC = {
    "authorization_endpoint": "https://idp.example.test/authorize",
    "token_endpoint": "https://idp.example.test/token",
    "userinfo_endpoint": "https://idp.example.test/userinfo",
}

TOKEN_RESPONSE = {"access_token": "at-123", "token_type": "Bearer"}
USERINFO_OK = {
    "sub": "usr_1",
    "preferred_username": "lars",
    "email": "lars@example.test",
    "groups": ["pbx-recordings", "phone"],
}
USERINFO_NO_GROUP = {"sub": "usr_2", "preferred_username": "eve", "groups": ["phone"]}


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._payload


def _manager(**overrides):
    if "client_secret_file" not in overrides:
        fh = tempfile.NamedTemporaryFile("w", suffix=".secret", delete=False)
        fh.write("client-secret-value\n")
        fh.close()
        overrides["client_secret_file"] = fh.name
    if "session_secret_file" not in overrides:
        fh = tempfile.NamedTemporaryFile("w", suffix=".key", delete=False)
        fh.write("session-hmac-key\n")
        fh.close()
        overrides["session_secret_file"] = fh.name
    args = {
        "issuer_url": "https://idp.example.test",
        "client_id": "client-x",
        "redirect_url": "https://pbx.example.test/gate/x/callback",
    }
    args.update(overrides)
    return oidc.OidcSessionManager(**args)


class ConfigTest(unittest.TestCase):
    def test_missing_field_raises_config_error(self):
        with self.assertRaises(oidc.OidcError) as caught:
            _manager(client_id="")
        self.assertEqual(caught.exception.code, "config")

    def test_secret_file_strips_trailing_newline(self):
        with tempfile.NamedTemporaryFile("w", suffix=".secret", delete=False) as fh:
            fh.write("s3cret-value\n")
            path = fh.name
        self.assertEqual(oidc.read_secret_file(path), "s3cret-value")

    def test_secret_file_empty_is_config_error(self):
        with tempfile.NamedTemporaryFile("w", suffix=".secret", delete=False) as fh:
            fh.write("\n")
            path = fh.name
        with self.assertRaises(oidc.OidcError) as caught:
            oidc.read_secret_file(path)
        self.assertEqual(caught.exception.code, "config")

    def test_secret_file_missing_is_config_error(self):
        with self.assertRaises(oidc.OidcError) as caught:
            oidc.read_secret_file("/nonexistent/nope")
        self.assertEqual(caught.exception.code, "config")


class DiscoveryTest(unittest.TestCase):
    def test_discovery_shapes_endpoints(self):
        mgr = _manager()
        with mock.patch.object(
            oidc.urllib.request, "urlopen", return_value=_FakeResponse(DISCOVERY_DOC)
        ):
            eps = mgr.discovery.endpoints()
        self.assertEqual(eps["token"], "https://idp.example.test/token")

    def test_discovery_failure_is_typed_and_uncached(self):
        mgr = _manager()
        responses = [OSError("boom"), _FakeResponse(DISCOVERY_DOC)]
        with mock.patch.object(oidc.urllib.request, "urlopen", side_effect=responses):
            with self.assertRaises(oidc.OidcError) as caught:
                mgr.discovery.endpoints()
            self.assertEqual(caught.exception.code, "discovery")
            eps = mgr.discovery.endpoints()
        self.assertEqual(eps["userinfo"], "https://idp.example.test/userinfo")

    def test_discovery_incomplete_document_is_typed(self):
        mgr = _manager()
        with mock.patch.object(
            oidc.urllib.request, "urlopen", return_value=_FakeResponse({" issuer": "x"})
        ):
            with self.assertRaises(oidc.OidcError) as caught:
                mgr.discovery.endpoints()
        self.assertEqual(caught.exception.code, "discovery")


class LoginRedirectTest(unittest.TestCase):
    def test_login_redirect_carries_pkce_and_state_cookie(self):
        mgr = _manager()
        with mock.patch.object(
            oidc.urllib.request, "urlopen", return_value=_FakeResponse(DISCOVERY_DOC)
        ):
            url, cookies = mgr.login_redirect()
        self.assertTrue(url.startswith("https://idp.example.test/authorize?"))
        for fragment in (
            "response_type=code",
            "client_id=client-x",
            "code_challenge_method=S256",
            "state=",
            "nonce=",
            "scope=openid+profile+email",
        ):
            self.assertIn(fragment, url)
        self.assertEqual(len(cookies), 1)
        self.assertIn("HttpOnly", cookies[0])
        self.assertIn("_state=", cookies[0])


class CallbackTest(unittest.TestCase):
    def _login(self, mgr):
        with mock.patch.object(
            oidc.urllib.request, "urlopen", return_value=_FakeResponse(DISCOVERY_DOC)
        ):
            url, cookies = mgr.login_redirect()
        state = url.split("state=")[1].split("&")[0]
        return state, cookies[0].split("=")[1].split(";")[0]

    def _happy_urlopen(self, userinfo=USERINFO_OK):
        def fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req
            if "openid-configuration" in str(url):
                return _FakeResponse(DISCOVERY_DOC)
            if str(url).endswith("/token"):
                return _FakeResponse(TOKEN_RESPONSE)
            if str(url).endswith("/userinfo"):
                self._userinfo_seen_auth = req.headers.get("Authorization")
                return _FakeResponse(userinfo)
            raise AssertionError(f"unexpected url {url}")

        return fake_urlopen

    def test_state_mismatch_is_typed_error(self):
        mgr = _manager()
        result = mgr.handle_callback("code=c&state=other", "oidc_session_state=notother")
        self.assertEqual(result.error, "state")

    def test_unknown_state_is_typed_error(self):
        mgr = _manager()
        result = mgr.handle_callback("code=c&state=ghost", "oidc_session_state=ghost")
        self.assertEqual(result.error, "state")

    def test_happy_path_mints_session_and_identity(self):
        mgr = _manager(required_group="pbx-recordings")
        state, cookie = self._login(mgr)
        self._userinfo_seen_auth = None
        with mock.patch.object(
            oidc.urllib.request, "urlopen", side_effect=self._happy_urlopen()
        ):
            result = mgr.handle_callback(f"code=good&state={state}", f"oidc_session_state={cookie}")
        self.assertIsNone(result.error)
        self.assertEqual(result.identity["username"], "lars")
        self.assertIn("pbx-recordings", result.identity["groups"])
        self.assertEqual(self._userinfo_seen_auth, "Bearer at-123")
        self.assertIn(f"{mgr.cookie_name}=", result.session_cookie)

    def test_missing_group_is_typed_error(self):
        mgr = _manager(required_group="pbx-recordings")
        state, cookie = self._login(mgr)
        with mock.patch.object(
            oidc.urllib.request, "urlopen", side_effect=self._happy_urlopen(USERINFO_NO_GROUP)
        ):
            result = mgr.handle_callback(f"code=good&state={state}", f"oidc_session_state={cookie}")
        self.assertEqual(result.error, "group")

    def test_state_is_single_use(self):
        mgr = _manager()
        state, cookie = self._login(mgr)
        with mock.patch.object(
            oidc.urllib.request, "urlopen", side_effect=self._happy_urlopen()
        ):
            first = mgr.handle_callback(f"code=good&state={state}", f"oidc_session_state={cookie}")
            second = mgr.handle_callback(f"code=good&state={state}", f"oidc_session_state={cookie}")
        self.assertIsNone(first.error)
        self.assertEqual(second.error, "state")

    def test_exchange_failure_is_typed(self):
        mgr = _manager()
        state, cookie = self._login(mgr)

        def failing(req, timeout=None):
            raise OSError("idp down")

        with mock.patch.object(oidc.urllib.request, "urlopen", side_effect=failing):
            result = mgr.handle_callback(f"code=good&state={state}", f"oidc_session_state={cookie}")
        self.assertEqual(result.error, "unavailable")


class SessionTest(unittest.TestCase):
    def test_round_trip(self):
        mgr = _manager()
        cookie = mgr._mint_session("lars")
        identity = mgr.identity(f"{mgr.cookie_name}={cookie.split('=', 1)[1].split(';')[0]}")
        self.assertEqual(identity, {"username": "lars"})

    def test_tampered_signature_refused(self):
        mgr = _manager()
        cookie = mgr._mint_session("lars")
        value = cookie.split("=", 1)[1].split(";")[0]
        bad = value[:-4] + "0000"
        self.assertIsNone(mgr.identity(f"{mgr.cookie_name}={bad}"))

    def test_expired_session_refused(self):
        mgr = _manager(ttl_seconds=1)
        cookie = mgr._mint_session("lars")
        value = cookie.split("=", 1)[1].split(";")[0]
        time.sleep(1.1)
        self.assertIsNone(mgr.identity(f"{mgr.cookie_name}={value}"))

    def test_garbage_refused(self):
        mgr = _manager()
        self.assertIsNone(mgr.identity(f"{mgr.cookie_name}=garbage"))
        self.assertIsNone(mgr.identity(None))
        self.assertIsNone(mgr.identity("other=1"))

    def test_wrong_key_refused(self):
        mgr = _manager()
        cookie = mgr._mint_session("lars")
        value = cookie.split("=", 1)[1].split(";")[0]
        fh = tempfile.NamedTemporaryFile("w", suffix=".key", delete=False)
        fh.write("different-key\n")
        fh.close()
        mgr2 = _manager(session_secret_file=fh.name)
        self.assertIsNone(mgr2.identity(f"{mgr.cookie_name}={value}"))

    def test_logout_clears(self):
        mgr = _manager()
        cookies = mgr.logout_cookies()
        self.assertIn("Max-Age=0", cookies[0])


if __name__ == "__main__":
    unittest.main()
