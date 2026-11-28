"""Shared OIDC relying-party session layer for the sibling's loopback apps.

Why this exists: the owner directive (2026-10-28) is that apps do OAuth
natively — no oauth2-proxy, no edge auth chain. The surfaces that gain
native OIDC login (recordings viewer, operator window) embed this module
instead of fronting an oauth2-proxy gate.

Identity model (deliberate, matches the fleet's proven shape): the
identity comes from the IdP's userinfo endpoint fetched DIRECTLY over
TLS with the access token — NOT from a locally-verified id_token. Two
reasons, both already paid for in this fleet: Pocket ID access tokens
carry no profile claims (the Stalwart/webphone lesson), and a stdlib-only
RS256 JOSE implementation would be hand-rolled crypto. The access token
arrives at us straight from the token endpoint over TLS, so userinfo is
authoritative for a confidential client.

Lifecycle: login (302 to the IdP with state+nonce+PKCE-S256) -> callback
(code+verifier exchange, userinfo fetch, group gate, session mint) ->
verified requests (HMAC-signed session cookie) -> logout (clear).

Fail-closed everywhere: any discovery, exchange, state, or group
failure answers a typed error code (`sso_error=<code>`) and NEVER a
session. Discovery is lazy with a bounded timeout and failures are not
cached — a dead IdP costs a login attempt, never the boot.

Secrets: client secret and session HMAC key are read from files at USE
time (a pushed rotation takes effect on the next login without a
restart) with trailing newlines stripped — this reader DEFINES its
shape, unlike oauth2-proxy's raw read (the 2026-10-14 newline burn).

Stdlib only, framework-neutral: apps translate the returned results
into their own response style.
"""

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
from http.cookies import CookieError, SimpleCookie

# The session payload version rises whenever the payload's shape
# changes (v2: the username travels base64-encoded, 2026-11-28), so a
# cookie minted under an older shape is refused by name.
SESSION_VERSION = "v2"
DEFAULT_TTL_SECONDS = 7 * 24 * 3600
DEFAULT_TIMEOUT_SECONDS = 10
STATE_COOKIE_MAX_AGE = 600

# Typed failure codes surfaced to the UI (the webphone sso_error family).
ERROR_CODES = (
    "config",  # misconfigured (missing secret file, empty value)
    "discovery",  # IdP discovery unreachable/invalid
    "exchange",  # token exchange failed
    "userinfo",  # userinfo fetch failed or empty identity
    "group",  # identity lacks the required group
    "state",  # state/nonce mismatch (replay, stale cookie, tamper)
    "unavailable",  # network error talking to the IdP
    "failed",  # anything else
)


class OidcError(Exception):
    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code if code in ERROR_CODES else "failed"
        self.detail = detail


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def read_secret_file(path):
    """Read a secret file, stripping trailing newlines (our contract)."""
    try:
        with open(path, encoding="utf-8") as fh:
            value = fh.read()
    except OSError as exc:
        raise OidcError("config", f"secret file unreadable: {path}") from exc
    value = value.rstrip("\n")
    if not value.strip():
        raise OidcError("config", f"secret file empty: {path}")
    return value


class _Discovery:
    """Lazy OIDC discovery with a bounded timeout; failures uncached."""

    def __init__(self, issuer_url, timeout):
        self.issuer_url = issuer_url.rstrip("/")
        self.timeout = timeout
        self._lock = threading.Lock()
        self._endpoints = None

    def endpoints(self):
        with self._lock:
            if self._endpoints is not None:
                return self._endpoints
        url = f"{self.issuer_url}/.well-known/openid-configuration"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                doc = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise OidcError("discovery", str(exc)) from exc
        try:
            found = {
                "authorization": doc["authorization_endpoint"],
                "token": doc["token_endpoint"],
                "userinfo": doc["userinfo_endpoint"],
            }
        except (KeyError, TypeError) as exc:
            raise OidcError("discovery", f"incomplete document: {exc}") from exc
        if any(not isinstance(url, str) or not url for url in found.values()):
            raise OidcError("discovery", "incomplete document: an endpoint is not a URL string")
        with self._lock:
            self._endpoints = found
        return found


def _identity_claims(userinfo):
    """The identity dictionary from a userinfo answer, or an OidcError.

    The answer crosses a trust boundary, so every claim is checked for
    its type before use. A `groups` value that is not a list never
    satisfies a required group: a bare string would otherwise match by
    substring.
    """
    if not isinstance(userinfo, dict):
        raise OidcError("userinfo", "userinfo answer is not a JSON object")
    username = userinfo.get("preferred_username") or userinfo.get("email") or userinfo.get("sub")
    if not isinstance(username, str) or not username.strip():
        raise OidcError("userinfo", "no usable identity claim")
    claimed_groups = userinfo.get("groups")
    groups = [group for group in claimed_groups if isinstance(group, str)] if isinstance(claimed_groups, list) else []
    email = userinfo.get("email")
    subject = userinfo.get("sub")
    return {
        "username": username,
        "email": email if isinstance(email, str) else "",
        "sub": subject if isinstance(subject, str) else "",
        "groups": groups,
    }


class OidcSessionManager:
    """Embeddable OIDC login for a loopback app behind a TLS edge.

    The app owns its routes; this class answers four questions:
      login_redirect()  -> (url, cookies) for the /oidc/login handler
      handle_callback() -> CallbackResult for the /oidc/callback handler
      identity()        -> {"sub","username","email"} | None per request
      logout_cookies()  -> cookies clearing the session
    """

    def __init__(
        self,
        issuer_url,
        client_id,
        client_secret_file,
        session_secret_file,
        redirect_url,
        required_group=None,
        cookie_name="oidc_session",
        scope="openid profile email",
        ttl_seconds=DEFAULT_TTL_SECONDS,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    ):
        missing = [
            name
            for name, value in [
                ("issuer_url", issuer_url),
                ("client_id", client_id),
                ("client_secret_file", client_secret_file),
                ("session_secret_file", session_secret_file),
                ("redirect_url", redirect_url),
            ]
            if not value
        ]
        if missing:
            raise OidcError("config", f"missing config: {', '.join(missing)}")
        self.client_id = client_id
        self.client_secret_file = client_secret_file
        self.session_secret_file = session_secret_file
        self.redirect_url = redirect_url
        self.required_group = required_group
        self.cookie_name = cookie_name
        self.scope = scope
        self.ttl_seconds = ttl_seconds
        self.discovery = _Discovery(issuer_url, timeout_seconds)
        self.timeout_seconds = timeout_seconds
        self._pending = {}
        self._pending_lock = threading.Lock()

    # ---- login -----------------------------------------------------------

    def login_redirect(self):
        """Start the dance: authorize URL + the browser cookies to set."""
        state = _b64url(secrets.token_bytes(24))
        nonce = _b64url(secrets.token_bytes(24))
        verifier = _b64url(secrets.token_bytes(32))
        challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
        eps = self.discovery.endpoints()
        with self._pending_lock:
            # Bounded store: drop entries older than the state TTL.
            now = time.time()
            self._pending = {k: v for k, v in self._pending.items() if now - v["at"] < STATE_COOKIE_MAX_AGE}
            self._pending[state] = {"nonce": nonce, "verifier": verifier, "at": now}
        query = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_url,
                "scope": self.scope,
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        cookies = [
            f"{self.cookie_name}_state={state}; Path=/; HttpOnly; SameSite=Lax; Max-Age={STATE_COOKIE_MAX_AGE}; Secure",
        ]
        return f"{eps['authorization']}?{query}", cookies

    # ---- callback --------------------------------------------------------

    def handle_callback(self, query, cookies):
        """Finish the dance. Returns CallbackResult(redirect | error code)."""
        params = urllib.parse.parse_qs(query)
        code = (params.get("code") or [""])[0]
        state = (params.get("state") or [""])[0]
        state_cookie = _cookie_value(cookies, f"{self.cookie_name}_state")
        if not code or not state or not state_cookie or state != state_cookie:
            return CallbackResult(error="state")
        with self._pending_lock:
            pending = self._pending.pop(state, None)
        if pending is None:
            return CallbackResult(error="state")
        try:
            identity = self._exchange_and_identify(code, pending["verifier"])
        except OidcError as exc:
            return CallbackResult(error=exc.code)
        if self.required_group and self.required_group not in identity.get("groups", []):
            return CallbackResult(error="group")
        cookie = self._mint_session(identity["username"])
        return CallbackResult(identity=identity, session_cookie=cookie)

    def _exchange_and_identify(self, code, verifier):
        eps = self.discovery.endpoints()
        client_secret = read_secret_file(self.client_secret_file)
        body = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_url,
                "client_id": self.client_id,
                "client_secret": client_secret,
                "code_verifier": verifier,
            }
        ).encode("ascii")
        try:
            req = urllib.request.Request(
                eps["token"],
                data=body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                tokens = json.loads(resp.read().decode("utf-8"))
        except OidcError:
            raise
        except Exception as exc:
            raise OidcError("unavailable", str(exc)) from exc
        if not isinstance(tokens, dict):
            raise OidcError("exchange", "token answer is not a JSON object")
        access_token = tokens.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise OidcError("exchange", "no access_token in response")
        try:
            req = urllib.request.Request(eps["userinfo"], headers={"Authorization": f"Bearer {access_token}"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                userinfo = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise OidcError("unavailable", str(exc)) from exc
        return _identity_claims(userinfo)

    # ---- session ---------------------------------------------------------

    def _session_secret(self):
        return read_secret_file(self.session_secret_file).encode("utf-8")

    def _mint_session(self, username):
        expires = int(time.time()) + self.ttl_seconds
        nonce = _b64url(secrets.token_bytes(12))
        payload = f"{SESSION_VERSION}.{expires}.{_b64url(username.encode('utf-8'))}.{nonce}"
        sig = hmac.new(self._session_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        value = f"{payload}.{sig}"
        return f"{self.cookie_name}={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={self.ttl_seconds}; Secure"

    def identity(self, cookie_header):
        """Verified identity from a request's Cookie header, or None.

        The username travels URL-safe-base64 encoded, so usernames with
        dots, email addresses or non-ASCII characters round-trip. The
        payload version rose with the encoding: a cookie minted under
        the older shape (raw username) fails the version check, whatever
        the old username would decode to, and the user logs in again.
        """
        value = _cookie_value(cookie_header, self.cookie_name)
        if not value:
            return None
        parts = value.split(".")
        if len(parts) != 5 or parts[0] != SESSION_VERSION:
            return None
        payload = ".".join(parts[:4])
        # The HMAC covers the exact cookie payload; verify before decoding
        # anything so no unsigned data is ever parsed.
        expected = hmac.new(self._session_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(parts[4], expected):
            return None
        try:
            expires = int(parts[1])
        except ValueError:
            return None
        if expires <= time.time():
            return None
        try:
            decoded = base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4))
            username = decoded.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError):
            return None
        if not username.strip():
            return None
        return {"username": username}

    def logout_cookies(self):
        return [f"{self.cookie_name}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0; Secure"]


class CallbackResult:
    def __init__(self, identity=None, session_cookie=None, error=None):
        self.identity = identity
        self.session_cookie = session_cookie
        self.error = error


def _cookie_value(cookie_header, name):
    if not cookie_header:
        return None
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except CookieError:
        return None
    morsel = jar.get(name)
    return morsel.value if morsel else None
