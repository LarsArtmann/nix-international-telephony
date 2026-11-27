"""Telnyx webhook receiver + webphone messaging bridge.

Three hats on one loopback port (127.0.0.1:8069):

1. Receiver (original behavior): ``POST /telnyx/webhooks`` logs every
   Telnyx event as JSON lines; ``GET /telnyx/webhooks/health`` and the
   token-protected ``GET /telnyx/webhooks/recent`` expose the log.
2. Inbound bridge: Telnyx ``message.received`` events are normalized and
   forwarded to the webphone's ``POST /hooks/message``; the status events
   ``message.finalized`` / ``message.delivery_updated`` become
   ``POST /hooks/message/status``. A forwarding failure answers Telnyx
   with 503 so Telnyx retries; the event is logged either way.
3. Outbound gateway: webphone's webhook gateway mode (gateway.mode =
   "webhook", webhook_url = http://127.0.0.1:8069/gateway) posts
   multipart to ``/gateway/message`` (routed to the Telnyx Messages API,
   answered with ``{"provider_ref": <telnyx message id>}``) and
   ``/gateway/fax`` (routed to the Telnyx Programmable Fax API
   ``POST /v2/faxes`` with the PDF as the multipart ``contents`` file —
   the API accepts the document itself, no media staging; answered with
   the fax id as provider_ref; requires the fax lane env
   ``FAX_CONNECTION_ID`` + ``FAX_FROM_NUMBER``, else an actionable 502).
   The final fax webhooks ``fax.delivered`` / ``fax.failed`` forward to
   webphone ``POST /hooks/fax/status`` as transmitted/failed verdicts
   (the per-fax webhook_url override pins them to this receiver);
   intermediate fax.* events stay log-only. Attachments are MMS: each file's type is the part's honest
   Content-Type when the producer sends one (webphone >= 2.8 does), with
   magic-byte sniffing as the fallback for producers that stamp the
   octet-stream default; the total is capped at 1 MB (Telnyx MMS hard
   cap; 600 KB is the carrier-safe size), stored under
   ``/var/lib/telnyx-webhooks/media`` behind an unguessable token, and
   sent as Telnyx ``media_urls`` pointing at
   ``PUBLIC_BASE_URL/mms-media/<token>.<ext>`` — Telnyx fetches the
   media at send time, so the URL must be public (nginx exposes it).
   Stored media is swept after ``MEDIA_TTL`` (7 days).

   WhatsApp lane: a destination of ``whatsapp:+<E164>`` routes the send
   through the Telnyx WhatsApp API (``POST /v2/messages/whatsapp``)
   instead of SMS. The channel selector is the destination prefix —
   webphone's sanitizer keeps letters in numbers (dial mnemonics), so
   ``whatsapp:+49…`` arrives as ``whatsapp+49…`` and threads key
   identically in both directions (inbound WhatsApp senders are tagged
   with the same prefix). Free-form text and ONE medium (image, video,
   audio, or document with the body text as caption) ride the 24-hour
   customer-service window: WhatsApp refuses free-form sends outside it,
   and the surfaced rejection carries the window/template guidance.
   Template sends are not wired (template selection needs portal-side
   content, not free text); the lane fails closed until
   ``WHATSAPP_FROM`` names a WhatsApp-enabled number.

Call outcomes are deliberately NOT a bridge concern (webphone issue
   #6): voice CDRs flow FreeSWITCH to webphone's phone API directly, and
   a call's disposition is the operator's post-call verdict confirmed in
   webphone (never derived from CDR shapes on either side) — it reaches
   the Kith journal through webphone's own authenticated CRM write. No
   Telnyx call event is bridged here, and none should be.

Secrets arrive via systemd ``LoadCredential`` (exposed through the
systemd-provided ``$CREDENTIALS_DIRECTORY``, i.e.
``/run/credentials/telnyx-webhooks.service/``):

- ``webphone_secret`` — shared with webphone's
  ``WEBPHONE_GATEWAY__WEBHOOK_SECRET``; gates the ``/gateway/*`` endpoints
  (Bearer) and signs the forwarded ``/hooks/*`` calls.
- ``telnyx_key`` — Telnyx V2 API key. A ``PLACEHOLDER*`` value counts as
  absent: outbound fails closed with an actionable 503 until a real key
  is dropped into the file behind the module's ``telnyxApiKeyFile``
  option.
- ``webhook_token`` — bearer token gating the ``GET /telnyx/webhooks/recent``
  reader. An empty or ``PLACEHOLDER*`` token fails closed (403).
- ``telnyx_public_key`` (optional, ``messaging.webhookPublicKeyFile``) — the
  account's Ed25519 public key (Telnyx portal: Keys & Credentials -> Public
  Key). Present, ``POST /telnyx/webhooks`` accepts an event only when its
  ``telnyx-signature-ed25519`` header verifies over
  ``{telnyx-timestamp}|{raw body}`` with a timestamp inside five minutes;
  anything else answers 403. Absent, the receiver trusts every caller.

Webhook signatures follow Telnyx's "Receiving Webhooks for Messaging"
page (developers.telnyx.com, read 2026-11-27): the signed string is the
timestamp header, a pipe and the EXACT request bytes, the signature is
base64 Ed25519, and timestamps older than five minutes are refused. The
verifier below is the RFC 8032 reference arithmetic on stdlib integers
(the unit runs a plain python3); RFC 8032 test vectors pin it in
tests/test_telnyx_bridge.py. Telnyx also documents duplicate deliveries
as normal (a lost 2xx makes it retry), so an inbound event id that was
forwarded successfully is not forwarded again.

Environment (the telephony module's ``services.telephony.messaging``
options set these; sentinels shown — the module always provides the
deployment's ``FROM_NUMBER`` and ``PUBLIC_BASE_URL``):

- ``WEBPHONE_URL`` (http://127.0.0.1:8080)
- ``SMS_TO_EXTENSION`` (1000) — owner extension for inbound SMS/MMS
- ``FROM_NUMBER`` (empty sentinel) — outbound CLI, the messaging DID
- ``WHATSAPP_FROM`` (empty sentinel) — WhatsApp-enabled from-number;
   empty means the WhatsApp lane fails closed with setup guidance
- ``FAX_CONNECTION_ID`` (empty sentinel) — Telnyx connection id the
   fax lane sends with; empty disables the lane (actionable 502)
- ``FAX_FROM_NUMBER`` (empty sentinel) — E.164 from-number for faxes;
   empty disables the lane (actionable 502)
- ``PUBLIC_BASE_URL`` (http://127.0.0.1 sentinel) — public origin Telnyx
  fetches outbound MMS media from (the module derives https://<domain>)
- ``PORT`` (8069) — loopback listen port
- ``MEDIA_DIR`` (/var/lib/telnyx-webhooks/media) — outbound MMS staging
"""

import base64
import datetime
import errno
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG_FILE = Path("/var/lib/telnyx-webhooks/inbound.jsonl")
# systemd exposes LoadCredential files at /run/credentials/<unit>.service/
# and exports $CREDENTIALS_DIRECTORY pointing there — that is the variable
# systemd has always exported (since v244). $CREDENTIALS_DIR was never a
# systemd variable; it stays accepted only for explicit overrides. The
# unit-named directory includes the ".service" suffix, easy to miss.
CREDENTIALS_DIR = Path(
    os.environ.get("CREDENTIALS_DIRECTORY")
    or os.environ.get("CREDENTIALS_DIR")
    or "/run/credentials/telnyx-webhooks.service"
)
TOKEN_FILE = CREDENTIALS_DIR / "webhook_token"
PUBLIC_KEY_FILE = CREDENTIALS_DIR / "telnyx_public_key"

BIND = ("127.0.0.1", int(os.environ.get("PORT", "8069")))
WEBPHONE_URL = os.environ.get("WEBPHONE_URL", "http://127.0.0.1:8080").rstrip("/")
SMS_TO_EXTENSION = os.environ.get("SMS_TO_EXTENSION", "1000")
FROM_NUMBER = os.environ.get("FROM_NUMBER", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1").rstrip("/")
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", "/var/lib/telnyx-webhooks/media"))
# API base is env-overridable so an in-VM stub Telnyx (tests/messaging.nix)
# can exercise the REAL outbound wiring; production keeps the real host.
TELNYX_API_BASE = os.environ.get("TELNYX_API_BASE", "https://api.telnyx.com/v2")
TELNYX_MESSAGES_API = TELNYX_API_BASE + "/messages"
TELNYX_WHATSAPP_API = TELNYX_API_BASE + "/messages/whatsapp"
TELNYX_FAXES_API = TELNYX_API_BASE + "/faxes"
WHATSAPP_FROM = os.environ.get("WHATSAPP_FROM", "")
FAX_CONNECTION_ID = os.environ.get("FAX_CONNECTION_ID", "")
FAX_FROM_NUMBER = os.environ.get("FAX_FROM_NUMBER", "")
WHATSAPP_CHANNEL = "whatsapp"
# Thread-key tag both directions: webphone's dialable sanitizer keeps
# letters (mnemonics) and strips the colon, so 'whatsapp:+49…' and the
# tagged inbound sender both collapse to 'whatsapp+49…' — one thread.
WHATSAPP_TAG = "whatsapp+"
WHATSAPP_ADDRESS_RE = re.compile(r"\+[0-9]{6,15}")
WHATSAPP_MAX_TEXT_BYTES = 4096
WHATSAPP_MAX_CAPTION_BYTES = 1024
WHATSAPP_MAX_IMAGE_BYTES = 5 << 20  # WhatsApp image cap (video/audio/doc caps sit above the gateway read cap)
# Inbound WhatsApp media rides the Meta caps (video 16 MB) — Telnyx MMS
# stays at MAX_MEDIA_BYTES. The webphone hook accepts a 40 MiB body, so
# one 16 MiB medium survives the base64 inflation (~22 MiB) end to end.
WHATSAPP_MAX_INBOUND_MEDIA_BYTES = 16 << 20
# WhatsApp media kinds by (sniffed or declared) mime: (type, caption
# allowed). Mimes the MMS set carries but WhatsApp has no native kind
# for (gif, tiff, vcard, mov, …) ride as documents — WhatsApp documents
# accept arbitrary files and keep the filename.
WHATSAPP_MEDIA_KINDS = {
    "image/jpeg": ("image", True),
    "image/png": ("image", True),
    "video/mp4": ("video", True),
    "application/pdf": ("document", True),
    "audio/mpeg": ("audio", False),
    "audio/ogg": ("audio", False),
    "audio/amr": ("audio", False),
}

MAX_BODY = 1 << 20  # Telnyx webhook bodies
MAX_GATEWAY_BODY = 8 << 20  # webphone multipart (text + attachments)
MAX_MEDIA_BYTES = 5 << 20  # inbound MMS media fetch cap
MAX_OUTBOUND_MEDIA_BYTES = 1 << 20  # Telnyx MMS total-attachment cap (600 KB safest)
MEDIA_TTL_SECONDS = 7 * 24 * 3600  # outbound media only has to outlive the send
MEDIA_NAME_RE = re.compile(r"[A-Za-z0-9_-]{16,64}\.[a-z0-9]{2,5}")
HTTP_TIMEOUT = 10
# Retries exist for IDEMPOTENT calls only (the webphone hook forwards).
# An SMS, WhatsApp or fax send is never repeated on a 5xx or a timeout:
# the peer may have accepted the first attempt, and a second attempt
# would deliver the customer's message twice.
HTTP_RETRIES = 1
TRANSPORT_ERRORS = (
    urllib.error.URLError,
    http.client.HTTPException,
    TimeoutError,
    OSError,
)
# A refused connection, a failed name lookup or an unreachable network
# are the only transport errors that PROVE no request byte reached the
# peer. Resets and timeouts can strike after the peer acted on the request.
NOTHING_SENT_ERRNOS = frozenset({errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH})

# Inbound media: Telnyx supplies the URL inside a webhook. The fetch
# never follows a redirect, never talks to a non-public address, and
# reads under one total deadline (a socket timeout alone lets a peer
# dribble one byte per timeout window forever).
MEDIA_FETCH_CHUNK = 64 << 10
MEDIA_FETCH_SECONDS = 30

# Telnyx webhook signatures (see the module docstring).
SIGNATURE_HEADER = "telnyx-signature-ed25519"
TIMESTAMP_HEADER = "telnyx-timestamp"
SIGNATURE_TOLERANCE_SECONDS = 300
ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")

# Event ids of inbound messages that were forwarded successfully.
# Telnyx redelivers when a 2xx is lost, and a redelivery must not land
# twice in the owner's thread. Failures are never remembered, so a
# failed forward still gets Telnyx's retry.
DELIVERED_TTL_SECONDS = 900
DELIVERED_MAX = 4096
_DELIVERED = {}
_DELIVERED_LOCK = threading.Lock()

# The MMS types Telnyx accepts, mapped to the storage extension. The
# type is the part's declared Content-Type when honest, else
# magic-byte sniffing (sniff_mime) for octet-stream producers.
MMS_MEDIA_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/bmp": "bmp",
    "image/webp": "webp",
    "image/tiff": "tif",
    "video/mp4": "mp4",
    "video/3gpp": "3gp",
    "video/quicktime": "mov",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/amr": "amr",
    "audio/ogg": "ogg",
    "text/vcard": "vcf",
    "application/pdf": "pdf",
}

TELEPHONE_STATUS_DELIVERED = "delivered"
TELEPHONE_STATUS_FAILED = {"delivery_failed", "failed"}

ACTIONABLE_KEY_MISSING = (
    "telnyx_api_key is not configured: create a Telnyx V2 API key at "
    "https://portal.telnyx.com/#/app/api-keys, write it to "
    "/var/lib/telephony-secrets/telnyx_api_key (owner, root, 0600), then "
    "run: systemctl restart telnyx-webhooks"
)
ACTIONABLE_SECRET_MISSING = (
    "webphone_secret credential is missing: write the shared gateway "
    "secret to /var/lib/telephony-secrets/webphone_gateway_secret "
    "(must equal WEBPHONE_GATEWAY__WEBHOOK_SECRET in webphone_env), then "
    "run: systemctl restart telnyx-webhooks"
)
ACTIONABLE_WHATSAPP_DISABLED = (
    "WhatsApp is not configured on this deployment: set services.telephony"
    ".messaging.whatsapp.enable = true and messaging.whatsapp.did to a "
    "number registered for WhatsApp (Telnyx portal: Messaging -> WhatsApp, "
    "embedded signup with a Meta Business Manager account; verify the "
    "number by VOICE call — SMS codes often never arrive on virtual "
    "numbers), then redeploy"
)
ACTIONABLE_FAX_DISABLED = (
    "the fax lane is not configured on this deployment: set services."
    "telephony.messaging.fax.enable = true with messaging.fax.connectionId "
    "(the Telnyx connection to send with) and messaging.fax.from (an "
    "E.164 number, ideally the same number as the gateway's faxDid), "
    "then redeploy"
)
ACTIONABLE_OUTCOME_UNKNOWN = (
    "Telnyx did not confirm the send, so the message MAY already be on its "
    "way: check the thread for it before sending again"
)


def credential(name):
    """Read a LoadCredential file; None when absent or unreadable."""
    try:
        return (CREDENTIALS_DIR / name).read_text().strip()
    except OSError:
        return None


def telnyx_api_key():
    key = credential("telnyx_key")
    if not key or key.startswith("PLACEHOLDER"):
        return None
    return key


def placeholder_or_absent(value):
    """The credential convention: missing, empty and PLACEHOLDER* all mean off."""
    return not value or value.startswith("PLACEHOLDER")


class WebhookKeyError(Exception):
    """The telnyx_public_key credential exists but cannot be used as a key."""


class SendOutcomeUnknown(ConnectionError):
    """A send reached the point where Telnyx may have accepted it, then the transport failed."""

    def __init__(self, detail):
        super().__init__(detail)


# --- Ed25519 (RFC 8032, section 5.1) on stdlib integers ---
# Extended twisted-Edwards coordinates: a point is (X, Y, Z, T) with
# x = X/Z, y = Y/Z, T = XY/Z. The reference arithmetic, nothing cleverer.

_ED_P = 2**255 - 19
_ED_L = 2**252 + 27742317777372353535851937790883648493
_ED_D = -121665 * pow(121666, _ED_P - 2, _ED_P) % _ED_P
_ED_SQRT_MINUS_1 = pow(2, (_ED_P - 1) // 4, _ED_P)
_ED_IDENTITY = (0, 1, 1, 0)


def _ed_add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _ED_P
    b = (y1 + x1) * (y2 + x2) % _ED_P
    c = 2 * t1 * _ED_D * t2 % _ED_P
    d = 2 * z1 * z2 % _ED_P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _ED_P, g * h % _ED_P, f * g % _ED_P, e * h % _ED_P)


def _ed_mul(point, scalar):
    result = _ED_IDENTITY
    while scalar:
        if scalar & 1:
            result = _ed_add(result, point)
        point = _ed_add(point, point)
        scalar >>= 1
    return result


def _ed_equal(p, q):
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    return (x1 * z2 - x2 * z1) % _ED_P == 0 and (y1 * z2 - y2 * z1) % _ED_P == 0


def _ed_decode(encoded):
    """The point of a 32-byte little-endian Edwards encoding.

    Raises ValueError for a wrong length, a non-canonical y (>= p), a y
    with no square root (not on the curve), or a set sign bit on x = 0.
    """
    if len(encoded) != 32:
        raise ValueError("a point encoding is 32 bytes")
    y = int.from_bytes(encoded, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    if y >= _ED_P:
        raise ValueError("y is not canonical")
    x2 = (y * y - 1) * pow(_ED_D * y * y + 1, _ED_P - 2, _ED_P) % _ED_P
    x = pow(x2, (_ED_P + 3) // 8, _ED_P)
    if (x * x - x2) % _ED_P:
        x = x * _ED_SQRT_MINUS_1 % _ED_P
    if (x * x - x2) % _ED_P:
        raise ValueError("the point is not on the curve")
    if x == 0 and sign:
        raise ValueError("x = 0 carries no sign bit")
    if x & 1 != sign:
        x = _ED_P - x
    return (x, y, 1, x * y % _ED_P)


_ED_BASE_POINT = _ed_decode(bytes.fromhex("58" + "66" * 31))


def ed25519_verify(public_key, message, signature):
    """True when signature is a valid RFC 8032 Ed25519 signature of message."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        public_point = _ed_decode(public_key)
        r_point = _ed_decode(signature[:32])
    except ValueError:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _ED_L:
        return False
    digest = hashlib.sha512(signature[:32] + public_key + message).digest()
    k = int.from_bytes(digest, "little") % _ED_L
    return _ed_equal(_ed_mul(_ED_BASE_POINT, s), _ed_add(r_point, _ed_mul(public_point, k)))


def parse_ed25519_public_key(text):
    """The 32 raw key bytes from a credential.

    Accepted spellings: base64 (standard or url-safe) of the raw key, of
    the DER SubjectPublicKeyInfo wrapper, or PEM; hex of the raw key.
    Raises WebhookKeyError for anything else, including a key that is not
    a point of the prime-order subgroup (for such a key, signatures can
    be forged without the private key).
    """
    body = "".join(line.strip() for line in text.splitlines() if line.strip() and not line.startswith("-----"))
    if re.fullmatch(r"[0-9a-fA-F]{64}", body):
        # 64 hex digits are also legal base64 (of 48 bytes): read them as hex.
        raw = bytes.fromhex(body)
    else:
        # altchars accepts the standard and the url-safe alphabet in one go.
        padded = body + "=" * (-len(body) % 4)
        try:
            raw = base64.b64decode(padded, altchars=b"-_", validate=True)
        except ValueError:
            raise WebhookKeyError(
                "the telnyx_public_key credential is not base64 or hex; paste the "
                "Ed25519 public key from the Telnyx portal (Keys & Credentials -> Public Key)"
            ) from None
    if len(raw) == 44 and raw.startswith(ED25519_SPKI_PREFIX):
        raw = raw[12:]
    if len(raw) != 32:
        raise WebhookKeyError(
            f"the telnyx_public_key credential decodes to {len(raw)} bytes, expected 32 "
            "(the Ed25519 public key from the Telnyx portal, Keys & Credentials -> Public Key)"
        )
    try:
        point = _ed_decode(raw)
    except ValueError as error:
        raise WebhookKeyError(f"the telnyx_public_key credential is not a valid Ed25519 key ({error})") from None
    if not _ed_equal(_ed_mul(point, _ED_L), _ED_IDENTITY):
        raise WebhookKeyError("the telnyx_public_key credential is not a point of the Ed25519 subgroup")
    return raw


_PUBLIC_KEY_CACHE = {}


def reset_caches():
    """Forget the parsed public key and the delivered-event ids (tests, reload)."""
    _PUBLIC_KEY_CACHE.clear()
    with _DELIVERED_LOCK:
        _DELIVERED.clear()


def webhook_signature_key():
    """(key, error): key None and error None means verification is off.

    error is a WebhookKeyError when the credential exists but is unusable:
    the receiver then refuses every event (fail closed) until the key is
    fixed. The credential cannot change while the unit runs, so the
    parse result is cached.
    """
    text = credential("telnyx_public_key")
    if text is None or placeholder_or_absent(text):
        return None, None
    cached = _PUBLIC_KEY_CACHE.get(text)
    if cached is None:
        try:
            cached = (parse_ed25519_public_key(text), None)
        except WebhookKeyError as error:
            cached = (None, error)
        _PUBLIC_KEY_CACHE[text] = cached
    return cached


def signature_state():
    """'required', 'misconfigured' or 'off' (the startup line and the gateway health card)."""
    key, error = webhook_signature_key()
    if error is not None:
        return "misconfigured"
    return "required" if key is not None else "off"


def verify_webhook_signature(raw_body, headers, public_key):
    """True, or a short string naming why the event is refused."""
    signature = headers.get(SIGNATURE_HEADER)
    timestamp = headers.get(TIMESTAMP_HEADER)
    if not isinstance(signature, str) or not isinstance(timestamp, str) or not signature or not timestamp:
        return f"missing {SIGNATURE_HEADER} or {TIMESTAMP_HEADER} header"
    try:
        signed_at = int(timestamp.strip())
    except ValueError:
        return f"{TIMESTAMP_HEADER} is not an integer"
    if signed_at > 10**11:  # a millisecond epoch, should Telnyx ever send one
        signed_at /= 1000
    if abs(time.time() - signed_at) > SIGNATURE_TOLERANCE_SECONDS:
        return f"{TIMESTAMP_HEADER} is outside the {SIGNATURE_TOLERANCE_SECONDS // 60} minute window"
    signed = timestamp.encode("latin-1") + b"|" + raw_body
    # Several signatures may travel in one header during a key rotation.
    for candidate in signature.split(","):
        try:
            decoded = base64.b64decode(candidate.strip(), validate=True)
        except ValueError:
            continue
        if ed25519_verify(public_key, signed, decoded):
            return True
    return "the signature does not match this account's public key"


def already_delivered(event_id):
    """True when this inbound event id was forwarded successfully within DELIVERED_TTL_SECONDS."""
    now = time.monotonic()
    with _DELIVERED_LOCK:
        expires = _DELIVERED.get(event_id)
        if expires is None:
            return False
        if expires < now:
            del _DELIVERED[event_id]
            return False
        return True


def remember_delivered(event_id):
    now = time.monotonic()
    with _DELIVERED_LOCK:
        for seen_id, expires in list(_DELIVERED.items()):
            if expires < now:
                del _DELIVERED[seen_id]
        if len(_DELIVERED) >= DELIVERED_MAX:
            oldest = min(_DELIVERED, key=_DELIVERED.get)
            del _DELIVERED[oldest]
        _DELIVERED[event_id] = now + DELIVERED_TTL_SECONDS


def append_entry(entry):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as handle:
        handle.write(json.dumps(entry) + "\n")


def last_entries(limit):
    if not LOG_FILE.exists():
        return []
    entries = []
    for line in LOG_FILE.read_text().splitlines()[-limit:]:
        try:
            entries.append(json.loads(line))
        except ValueError:
            continue
    return entries


def bridge_log(event, **fields):
    """One journald line per boundary event (SUPERB error-excellence T05).

    Logs only — never changes behavior. stdout + flush lands in the
    systemd journal next to the request lines log_message already prints.
    """
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    print(f"telnyx-webhooks: {event}{' ' + details if details else ''}", flush=True)


def token_valid(headers):
    """True only for a configured, non-placeholder token presented byte-exact.

    An empty or PLACEHOLDER* token file closes the reader (403): the
    placeholder text lives in the world-readable store, so honouring it
    would publish the log to anyone who reads the module.
    """
    try:
        expected = TOKEN_FILE.read_text().strip()
    except OSError:
        return False
    if placeholder_or_absent(expected):
        return False
    presented = headers.get("Authorization", "").encode("utf-8")
    return hmac.compare_digest(presented, f"Bearer {expected}".encode("utf-8"))


def bearer_token(headers):
    auth = headers.get("Authorization", "")
    if not isinstance(auth, str) or not auth.startswith("Bearer "):
        return None
    return auth[len("Bearer ") :].strip()


def secret_matches(presented, expected):
    """Constant-time equality of two secrets, whatever bytes the peer sent.

    hmac.compare_digest refuses non-ASCII str arguments, and a header
    may carry any byte; the comparison therefore runs on UTF-8 bytes.
    """
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def nothing_sent(error):
    """True when a transport error proves the peer received no request bytes."""
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    if isinstance(reason, socket.gaierror):
        return True
    return isinstance(reason, OSError) and reason.errno in NOTHING_SENT_ERRNOS


def http_send(request, safe_to_retry=True, timeout=HTTP_TIMEOUT):
    """One HTTP exchange. Returns (status, body).

    safe_to_retry fits idempotent calls (the webphone hook forwards): a
    5xx or any transport error is retried HTTP_RETRIES times. Without it
    (the Telnyx sends) a 5xx is returned as-is and only a transport
    error that proves no byte reached the peer is retried; any other
    transport failure raises SendOutcomeUnknown, because the peer may
    already have acted on the request. A failure that survives its
    retries raises ConnectionError.
    """
    last_error = "no attempt made"
    for attempt in range(HTTP_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - caller-pinned http(s) URL, never file:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            if safe_to_retry and error.code >= 500 and attempt < HTTP_RETRIES:
                last_error = f"HTTP {error.code}"
                continue
            return error.code, body
        except TRANSPORT_ERRORS as error:
            last_error = str(error) or type(error).__name__
            if not safe_to_retry and not nothing_sent(error):
                raise SendOutcomeUnknown(f"the connection failed ({last_error})") from None
            if attempt >= HTTP_RETRIES:
                break
    raise ConnectionError(f"{request.full_url} unreachable: {last_error}")


def http_json(method, url, payload=None, headers=None, timeout=HTTP_TIMEOUT, safe_to_retry=True):
    """JSON request; see http_send for the retry contract."""
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode() if payload is not None else None, method=method
    )
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    return http_send(request, safe_to_retry=safe_to_retry, timeout=timeout)


def http_post_multipart(url, fields, files, headers=None, timeout=HTTP_TIMEOUT, safe_to_retry=True):
    """Multipart/form-data POST; see http_send for the retry contract.

    fields: dict of scalar form fields; files: (field, filename,
    content_type, bytes) tuples.
    """
    boundary = "telnyx-bridge-" + secrets.token_hex(16)
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for field, filename, content_type, content in files:
        parts.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
                f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n'
            ).encode()
            + content
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(url, data=b"".join(parts), method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    return http_send(request, safe_to_retry=safe_to_retry, timeout=timeout)


def _is_public_address(text):
    """True for a routable address; embedded IPv4 forms are judged by the IPv4 they carry."""
    address = ipaddress.ip_address(text)
    if address.version == 6:
        embedded = [address.ipv4_mapped, address.sixtofour]
        if address.teredo is not None:
            embedded.extend(address.teredo)
        embedded = [str(part) for part in embedded if part is not None]
        if embedded:
            return all(_is_public_address(part) for part in embedded)
    return address.is_global


def _connect_public(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """socket.create_connection that talks to the host's public addresses only.

    The name is resolved, judged and connected in ONE step, so it cannot
    answer a public address to a check and a private one to the connect,
    and every address it resolves to must be public. The unit runs
    without a proxy, so proxies and tunnels are deliberately not handled.
    """
    host, port = address[:2]
    infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    if not infos or not all(_is_public_address(info[4][0]) for info in infos):
        raise PermissionError(f"refusing to connect to non-public host {host}")
    last_error = None
    for family, socktype, proto, _, sockaddr in infos:
        sock = socket.socket(family, socktype, proto)
        try:
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            sock.connect(sockaddr)
            return sock
        except OSError as error:
            last_error = error
            sock.close()
    raise last_error


class _PublicHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _connect_public


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _PublicHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_PublicHTTPSConnection, req, context=self._context)


MEDIA_OPENER = urllib.request.build_opener(_NoRedirect, _PublicHTTPSHandler)


def fetch_media(url, cap=MAX_MEDIA_BYTES):
    """Fetch one inbound medium, size- and time-capped.

    Telnyx names the URL inside a webhook. Returns (mime, bytes), or None
    when the URL is not a plain https URL, the host is not public, the
    peer redirects or fails, or the read exceeds ``cap`` bytes or
    MEDIA_FETCH_SECONDS.
    """
    if not isinstance(url, str) or not url.isascii():
        return None
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or parts.username is not None:
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "telephony-bridge/1.0"})
    deadline = time.monotonic() + MEDIA_FETCH_SECONDS
    chunks = []
    remaining = cap + 1
    try:
        with MEDIA_OPENER.open(request, timeout=HTTP_TIMEOUT) as response:
            mime = (response.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
            declared = response.headers.get("Content-Length") or ""
            if declared.isdigit() and int(declared) > cap:
                return None
            while remaining > 0 and time.monotonic() < deadline:
                chunk = response.read(min(MEDIA_FETCH_CHUNK, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
    except TRANSPORT_ERRORS:
        return None
    content = b"".join(chunks)
    if len(content) > cap:
        return None
    return mime, content


def media_name(url, mime):
    """A filesystem-safe display name for an inbound medium."""
    tail = urllib.parse.unquote(url.rsplit("/", 1)[-1].split("?")[0])[:80] if isinstance(url, str) else ""
    tail = re.sub(r"[/\\\x00-\x1f\x7f]", "_", tail)
    if tail:
        return tail
    return "media." + (mime.split("/")[-1] if "/" in mime else "bin")


def sniff_mime(data):
    """Detect an MMS-supported media type from magic bytes. None = unknown."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"BM") and len(data) > 14:
        return "image/bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if data.startswith(b"#!AMR"):
        return "audio/amr"
    if data.startswith(b"ID3") or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand.startswith((b"heic", b"heix", b"hevc", b"heim", b"heis", b"hevx", b"mif1", b"msf1")):
            # iPhone High Efficiency photos: honest type, deliberately NOT
            # in MMS_MEDIA_EXTENSIONS — stage_mms_media answers with the
            # fix-the-phone copy instead of the generic unsupported wall.
            return "image/heic"
        if brand.startswith((b"3gp", b"3g2")):
            return "video/3gpp"
        return "video/mp4"
    head = data[:64].lstrip(b"\xef\xbb\xbf \t\r\n").upper()
    if head.startswith(b"BEGIN:VCARD"):
        return "text/vcard"
    return None


def store_media(content, mime):
    """Stage one outbound MMS medium; return its public URL.

    Files live behind an unguessable token (secrets.token_urlsafe) —
    that token plus TLS is the access control for the public nginx
    location. A sidecar .json carries the resolved mime + creation time.
    """
    token = secrets.token_urlsafe(16)
    extension = MMS_MEDIA_EXTENSIONS[mime]
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    (MEDIA_DIR / f"{token}.{extension}").write_bytes(content)
    (MEDIA_DIR / f"{token}.json").write_text(json.dumps({"mime": mime, "created": time.time()}))
    bridge_log("staged outbound mms media", mime=mime, bytes=len(content))
    return f"{PUBLIC_BASE_URL}/mms-media/{token}.{extension}"


def sweep_expired_media():
    """Delete media (sidecar + blob) older than MEDIA_TTL_SECONDS."""
    now = time.time()
    if not MEDIA_DIR.is_dir():
        return
    for sidecar in MEDIA_DIR.glob("*.json"):
        try:
            created = json.loads(sidecar.read_text()).get("created", 0)
        except (ValueError, OSError):
            created = 0
        if now - created <= MEDIA_TTL_SECONDS:
            continue
        token = sidecar.stem
        sidecar.unlink(missing_ok=True)
        for blob in MEDIA_DIR.glob(f"{token}.*"):
            blob.unlink(missing_ok=True)


def phone_number(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        number = value.get("phone_number")
        if isinstance(number, str):
            return number
    return ""


def dict_list(value):
    """The list-of-objects shape Telnyx uses for media, to, statuses and errors.

    Anything else (a string, a number, an object, a list of scalars) is
    an empty list: a malformed field must never crash the handler.
    """
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def text_of(value):
    """The value when it is a string, else the empty string."""
    return value if isinstance(value, str) else ""


def is_whatsapp_payload(payload):
    return str(payload.get("type") or "").upper() == "WHATSAPP"


def whatsapp_thread_address(number):
    """The Remote key webphone stores for WhatsApp threads.

    Outbound, the owner types 'whatsapp:+49…' and webphone's dialable
    sanitizer stores 'whatsapp+49…' (letters kept, colon dropped); the
    inbound sender must tag to the SAME key or one conversation splits
    into two threads.
    """
    return WHATSAPP_TAG + number.lstrip("+")


def whatsapp_inbound_content(payload):
    """(text, media_entries) from an inbound WhatsApp payload.

    Telnyx documents two shapes (both pinned by tests): the messaging
    envelope — payload.text plus payload.media — and the Meta-style
    payload.body object whose 'type' names the content: text
    (body.text.body), image/video/audio/document/sticker (url +
    mime_type + caption), location, contacts, interactive, reaction.
    Anything else still forwards as an honest bracketed placeholder —
    the thread must see that SOMETHING arrived.
    """
    parts = []
    media_entries = []
    envelope_text = payload.get("text")
    if isinstance(envelope_text, str) and envelope_text:
        parts.append(envelope_text)
    for entry in dict_list(payload.get("media")):
        media_entries.append(entry)
    body = payload.get("body")
    if isinstance(body, dict):
        kind = body.get("type")
        content = body.get(kind) if isinstance(kind, str) else None
        content = content if isinstance(content, dict) else {}
        if kind == "text":
            inner = content.get("body")
            if isinstance(inner, str) and inner:
                parts.append(inner)
        elif kind in ("image", "video", "audio", "document", "sticker"):
            url = content.get("url") or content.get("link")
            if isinstance(url, str) and url:
                media_entries.append({"url": url})
            caption = content.get("caption")
            if isinstance(caption, str) and caption:
                parts.append(caption)
        elif kind == "location":
            label = " ".join(str(value) for value in (content.get("name"), content.get("address")) if value)
            where = f"({content.get('latitude')}, {content.get('longitude')})"
            parts.append("[location] " + " ".join(piece for piece in (label, where) if piece))
        elif kind == "contacts":
            parts.append("[contact card]")
        elif kind == "reaction":
            parts.append(f"[reaction] {content.get('emoji', '')}".rstrip())
        elif kind:
            parts.append(f"[WhatsApp {kind} message]")
    return "\n".join(parts), media_entries


def forward_inbound_message(payload):
    """message.received → webphone /hooks/message. Returns (ok, error)."""
    secret = credential("webphone_secret")
    if not secret:
        return False, ACTIONABLE_SECRET_MISSING
    whatsapp = is_whatsapp_payload(payload)
    media_cap = WHATSAPP_MAX_INBOUND_MEDIA_BYTES if whatsapp else MAX_MEDIA_BYTES
    if whatsapp:
        text, media_entries = whatsapp_inbound_content(payload)
        sender = whatsapp_thread_address(phone_number(payload.get("from")))
    else:
        text = text_of(payload.get("text"))
        media_entries = dict_list(payload.get("media"))
        sender = phone_number(payload.get("from"))
    attachments = []
    fetch_failures = []
    for media in media_entries:
        fetched = fetch_media(media.get("url"), cap=media_cap)
        if fetched is None:
            fetch_failures.append(str(media.get("url"))[:120])
            continue
        mime, content = fetched
        attachments.append(
            {
                "name": media_name(media.get("url", ""), mime),
                "mime_type": mime,
                "data_base64": base64.b64encode(content).decode(),
            }
        )
    if fetch_failures:
        # Telnyx media URLs are ephemeral: a fetch that fails here is a
        # PERMANENT loss of that attachment (the text still forwards) —
        # the operator must see it (SUPERB error-excellence T05).
        bridge_log(
            "inbound mms media fetch failed",
            skipped=len(fetch_failures),
            forwarded=len(attachments),
            first=fetch_failures[0],
        )
    body = {
        "owner": SMS_TO_EXTENSION,
        "from": sender,
        "body": text,
        "attachments": attachments,
    }
    try:
        status, response = http_json(
            "POST",
            f"{WEBPHONE_URL}/hooks/message",
            body,
            {"Authorization": f"Bearer {secret}"},
        )
    except ConnectionError as error:
        return False, str(error)
    if status not in range(200, 300):
        return (
            False,
            f"webphone /hooks/message answered {status}: {response[:200].decode('utf-8', 'replace')}",
        )
    return True, None


def message_status_entries(payload):
    """Final-verdict candidate entries from a status-event payload.

    Telnyx documents two envelopes: the SMS shape (payload.to as a LIST
    of {phone_number, status, errors}) and the WhatsApp/Meta shape
    (payload.to as a STRING address echo — pinned by message.echo in the
    webhook catalog — with verdicts in payload.statuses or a flat
    payload.status). A string `to` must not silently drop delivery
    verdicts: the forwarder reads every shape.
    """
    entries = []
    to = payload.get("to")
    if isinstance(to, str):
        entries.extend(dict_list(payload.get("statuses")))
        status = payload.get("status")
        if isinstance(status, str):
            entries.append({"status": status, "errors": payload.get("errors") or []})
        return entries
    return dict_list(to)


def forward_message_status(payload):
    """message.finalized / message.delivery_updated → /hooks/message/status.

    Returns (forwarded, error): forwarded is False (no error) when the
    event maps to no final verdict (queued/sent/… are logged only).
    """
    message_id = payload.get("id")
    if not isinstance(message_id, str) or not message_id:
        return False, "payload carries no message id"
    statuses = set()
    errors = []
    for entry in message_status_entries(payload):
        status = entry.get("status")
        if isinstance(status, str):
            statuses.add(status)
        for error in dict_list(entry.get("errors")):
            detail = error.get("detail") or error.get("title") or error.get("code")
            if detail:
                errors.append(text_of(detail) or str(detail))
    if statuses & {TELEPHONE_STATUS_DELIVERED, "read"}:
        # Meta reports 'read' after delivered; the webphone hook accepts
        # only delivered|failed, so read maps onto delivered.
        verdict, error_text = TELEPHONE_STATUS_DELIVERED, None
    elif statuses & TELEPHONE_STATUS_FAILED:
        verdict = "failed"
        error_text = "; ".join(errors) or "carrier reports delivery_failed"
    else:
        return False, None  # intermediate status: nothing to forward
    secret = credential("webphone_secret")
    if not secret:
        return False, ACTIONABLE_SECRET_MISSING
    body = {"provider_ref": message_id, "status": verdict}
    if error_text:
        body["error"] = error_text
    try:
        status, response = http_json(
            "POST",
            f"{WEBPHONE_URL}/hooks/message/status",
            body,
            {"Authorization": f"Bearer {secret}"},
        )
    except ConnectionError as transport_error:
        return False, str(transport_error)
    if status not in range(200, 300):
        return (
            False,
            f"webphone /hooks/message/status answered {status}: {response[:200].decode('utf-8', 'replace')}",
        )
    return True, None


def forward_fax_status(payload, event_type):
    """fax.delivered / fax.failed → webphone /hooks/fax/status.

    Returns (forwarded, error): forwarded is False (no error) when the
    event carries no verdict we forward (intermediate fax.* events are
    handled log-only by the dispatcher and never reach here).
    """
    fax_id = payload.get("fax_id")
    if not isinstance(fax_id, str) or not fax_id:
        return False, "payload carries no fax id"
    if event_type == "fax.delivered":
        body = {"provider_ref": fax_id, "status": "transmitted"}
        pages = payload.get("page_count")
        if isinstance(pages, int):
            body["pages"] = pages
    else:
        body = {
            "provider_ref": fax_id,
            "status": "failed",
            "error": text_of(payload.get("failure_reason")) or "telnyx reports the fax failed",
        }
    secret = credential("webphone_secret")
    if not secret:
        return False, ACTIONABLE_SECRET_MISSING
    try:
        status, response = http_json(
            "POST",
            f"{WEBPHONE_URL}/hooks/fax/status",
            body,
            {"Authorization": f"Bearer {secret}"},
        )
    except ConnectionError as transport_error:
        return False, str(transport_error)
    if status not in range(200, 300):
        return (
            False,
            f"webphone /hooks/fax/status answered {status}: {response[:200].decode('utf-8', 'replace')}",
        )
    return True, None


def handle_telnyx_event(data):
    """Route one parsed Telnyx webhook envelope. Returns (http_status, payload)."""
    event_type = text_of(data.get("event_type"))
    payload = data.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    if event_type == "message.received":
        event_id = text_of(data.get("id"))
        if not phone_number(payload.get("from")):
            # Nothing names a sender, so there is no thread to file it under.
            return 200, {"ok": True, "forwarded": False}
        if event_id and already_delivered(event_id):
            return 200, {"ok": True, "duplicate": True}
        ok, error = forward_inbound_message(payload)
        if not ok:
            return 503, {"error": f"inbound forward failed (Telnyx should retry): {error}"}
        if event_id:
            remember_delivered(event_id)
        return 200, {"ok": True}
    if event_type in ("message.finalized", "message.delivery_updated"):
        forwarded, error = forward_message_status(payload)
        if error:
            return 503, {"error": f"status forward failed (Telnyx should retry): {error}"}
        return 200, {"ok": True, "forwarded": forwarded}
    if event_type in ("fax.delivered", "fax.failed"):
        forwarded, error = forward_fax_status(payload, event_type)
        if error:
            return 503, {"error": f"fax status forward failed (Telnyx should retry): {error}"}
        return 200, {"ok": True, "forwarded": forwarded}
    # Every other event (call.*, message.queued sent, …) stays log-only.
    return 200, {"ok": True}


def telnyx_rejection(status, body):
    """Humanize a Telnyx API refusal: prefer errors[0].detail (+code) over a
    raw JSON dump — this string rides the bridge's 502 error payload, which
    the webphone shows the user verbatim (2026-09-21 self-send burn)."""
    fallback = f"telnyx api answered {status}: {body[:300].decode('utf-8', 'replace')}"
    try:
        first = json.loads(body).get("errors", [])[0]
    except (ValueError, IndexError, AttributeError, TypeError):
        return fallback
    detail = (first or {}).get("detail")
    if not detail:
        return fallback
    code = first.get("code")
    suffix = f", error {code}" if code else ""
    return f"telnyx rejected the send (HTTP {status}{suffix}): {detail}"


def send_failure(error):
    """The user-facing error for a Telnyx send that never got an HTTP answer."""
    if isinstance(error, SendOutcomeUnknown):
        return f"telnyx api unreachable ({error}); {ACTIONABLE_OUTCOME_UNKNOWN}"
    return f"telnyx api unreachable: {error}"


def telnyx_send_message(to, text, media_urls=()):
    """Send an SMS/MMS via the Telnyx API. Returns (provider_ref, error)."""
    key = telnyx_api_key()
    if key is None:
        return None, ACTIONABLE_KEY_MISSING
    payload = {"from": FROM_NUMBER, "to": to}
    if text:
        payload["text"] = text
    if media_urls:
        payload["media_urls"] = list(media_urls)
    try:
        status, body = http_json(
            "POST",
            TELNYX_MESSAGES_API,
            payload,
            {"Authorization": f"Bearer {key}"},
            safe_to_retry=False,
        )
    except ConnectionError as error:
        return None, send_failure(error)
    if status not in range(200, 300):
        return None, telnyx_rejection(status, body)
    try:
        provider_ref = json.loads(body)["data"]["id"]
    except (ValueError, KeyError, TypeError):
        return None, "telnyx api response is missing data.id"
    return provider_ref, None


def telnyx_send_fax(to, pdf):
    """Send a fax via the Telnyx Programmable Fax API. Returns (provider_ref, error).

    The API takes the document itself as a multipart 'contents' file
    (no media staging, no public URL — unlike MMS); the per-fax
    webhook_url override pins the delivered/failed events to this
    stack's receiver independent of portal-side fax application
    wiring.
    """
    if not FAX_CONNECTION_ID or not FAX_FROM_NUMBER:
        return None, ACTIONABLE_FAX_DISABLED
    key = telnyx_api_key()
    if key is None:
        return None, ACTIONABLE_KEY_MISSING
    fields = {
        "connection_id": FAX_CONNECTION_ID,
        "from": FAX_FROM_NUMBER,
        "to": to,
        "webhook_url": PUBLIC_BASE_URL + "/telnyx/webhooks",
    }
    try:
        status, body = http_post_multipart(
            TELNYX_FAXES_API,
            fields,
            [("contents", "fax.pdf", "application/pdf", pdf)],
            {"Authorization": f"Bearer {key}"},
            safe_to_retry=False,
        )
    except ConnectionError as error:
        return None, send_failure(error)
    if status not in range(200, 300):
        return None, telnyx_rejection(status, body)
    try:
        provider_ref = json.loads(body)["data"]["id"]
    except (ValueError, KeyError, TypeError):
        return None, "telnyx api response is missing data.id"
    return provider_ref, None


def parse_destination(to_field):
    """(channel, address) from a gateway 'to' field; channel None = invalid.

    The channel selector is a literal 'whatsapp' prefix ahead of the
    +E164 address ('whatsapp:+49…' typed, 'whatsapp+49…' after
    webphone's sanitizer — both parse). Everything else is SMS, exactly
    as before the WhatsApp lane existed.
    """
    raw = (to_field or "").strip()
    if raw.lower().startswith("whatsapp"):
        address = raw[len("whatsapp") :].lstrip(":").strip()
        if not WHATSAPP_ADDRESS_RE.fullmatch(address):
            return None, raw
        return WHATSAPP_CHANNEL, address
    return "sms", raw


def whatsapp_rejection_guidance(rejection):
    """Append the 24-hour-window explanation to a WhatsApp rejection.

    WhatsApp refuses free-form sends outside the customer-service
    window with the 40008 catch-all; the fix (approved template) is
    portal-side, so the user-facing error must say so instead of
    looking like a transient failure worth retrying.
    """
    lowered = rejection.lower()
    if "template" in lowered or "window" in lowered or "24-hour" in lowered or "24 hour" in lowered:
        return (
            rejection + " — WhatsApp only accepts free-form replies within 24 hours of "
            "the contact's last message; outside that window only a "
            "pre-approved template (managed in the Telnyx portal, "
            "Messaging -> WhatsApp) can start the conversation"
        )
    return rejection


def build_whatsapp_message(text, files):
    """Compose the Telnyx whatsapp_message object. Returns (object, error_response)."""
    if len(files) > 1:
        return None, (
            422,
            {
                "error": "WhatsApp carries exactly one media object per message "
                f"(got {len(files)} attachments): send each file as its own "
                "message, or use plain numbers to send them as one MMS"
            },
        )
    text_bytes = len(text.encode("utf-8"))
    if not files:
        if not text:
            return None, (
                400,
                {"error": "multipart field 'body' (message text) is required"},
            )
        if text_bytes > WHATSAPP_MAX_TEXT_BYTES:
            return None, (
                422,
                {
                    "error": f"message text is {text_bytes} bytes, but WhatsApp "
                    f"allows at most {WHATSAPP_MAX_TEXT_BYTES}: shorten the message "
                    "or send the long part as a document attachment"
                },
            )
        return {"type": "text", "text": {"body": text, "preview_url": False}}, None
    filename, declared, content = files[0]
    mime = declared or sniff_mime(content)
    if mime == "image/heic":
        return None, (
            422,
            {
                "error": f"attachment {filename or '<unnamed>'} is an iPhone "
                "High Efficiency photo (HEIC), which WhatsApp cannot carry: on "
                "the iPhone set Settings → Camera → Formats → Most Compatible "
                "and send the photo again (it becomes a JPG), or convert it to "
                "JPG before attaching"
            },
        )
    if mime not in MMS_MEDIA_EXTENSIONS:
        return None, (
            422,
            {
                "error": f"attachment {filename or '<unnamed>'} has an "
                "unsupported type for WhatsApp; allowed: jpeg, png, gif, bmp, "
                "webp, tiff, mp4, 3gp, mov, mp3, wav, amr, ogg, vcard, pdf"
            },
        )
    kind, caption_allowed = WHATSAPP_MEDIA_KINDS.get(mime, ("document", True))
    if kind == "image" and len(content) > WHATSAPP_MAX_IMAGE_BYTES:
        return None, (
            422,
            {
                "error": f"image is {len(content) / (1 << 20):.1f} MiB, but "
                f"WhatsApp allows at most {WHATSAPP_MAX_IMAGE_BYTES >> 20} MiB "
                "per image: resize it or send it as a PDF document"
            },
        )
    media = {"link": store_media(content, mime)}
    if kind == "document":
        media["filename"] = filename or ("attachment." + MMS_MEDIA_EXTENSIONS[mime])
    if caption_allowed and text:
        if len(text.encode("utf-8")) > WHATSAPP_MAX_CAPTION_BYTES:
            return None, (
                422,
                {
                    "error": f"caption is {len(text.encode('utf-8'))} bytes, "
                    "but WhatsApp allows at most 1024 bytes of caption with "
                    "media: shorten the text (audio carries no caption at all)"
                },
            )
        media["caption"] = text
    return {"type": kind, kind: media}, None


def telnyx_send_whatsapp(to, whatsapp_message):
    """Send a WhatsApp message via the Telnyx API. Returns (provider_ref, error)."""
    if not WHATSAPP_FROM:
        return None, ACTIONABLE_WHATSAPP_DISABLED
    key = telnyx_api_key()
    if key is None:
        return None, ACTIONABLE_KEY_MISSING
    payload = {"from": WHATSAPP_FROM, "to": to, "whatsapp_message": whatsapp_message}
    try:
        status, body = http_json(
            "POST",
            TELNYX_WHATSAPP_API,
            payload,
            {"Authorization": f"Bearer {key}"},
            safe_to_retry=False,
        )
    except ConnectionError as error:
        return None, whatsapp_rejection_guidance(send_failure(error))
    if status not in range(200, 300):
        return None, whatsapp_rejection_guidance(telnyx_rejection(status, body))
    try:
        provider_ref = json.loads(body)["data"]["id"]
    except (ValueError, KeyError, TypeError):
        return None, "telnyx api response is missing data.id"
    return provider_ref, None


def parse_multipart(content_type, raw):
    """Parse multipart/form-data into (fields: dict, files).

    files is a list of (filename, declared_type_or_None, bytes). The
    part Content-Type is the declared type when the producer sent an
    honest one; None means absent or application/octet-stream (what
    Go's CreateFormFile used to stamp on every part), which the caller
    resolves by sniffing. The email parser handles what Go's
    mime/multipart writes; malformed input raises ValueError.
    """
    header = b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n"
    message = BytesParser(policy=email_policy).parsebytes(header + raw)
    if not message.is_multipart():
        raise ValueError("request is not multipart/form-data")
    fields = {}
    files = []
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not isinstance(name, str):
            continue
        filename = part.get_filename()
        content = part.get_payload(decode=True) or b""
        if filename:
            files.append((filename, honest_part_type(part), content))
        else:
            fields[name] = content.decode("utf-8", "replace")
    return fields, files


def honest_part_type(part):
    """The part's declared Content-Type, or None when absent/generic.

    get_content_type() would lie "text/plain" for parts without the
    header, so presence is checked on the raw header first.
    application/octet-stream is the multipart default Go's CreateFormFile
    stamped on every file part, so it counts as undeclared.
    """
    if not part.get("Content-Type"):
        return None
    declared = part.get_content_type()
    return None if declared == "application/octet-stream" else declared


def stage_mms_media(files):
    """Validate + store attachments; return (media_urls, error_response).

    error_response is a (status, payload) tuple the caller returns as-is.
    """
    total = sum(len(content) for _, _, content in files)
    if total > MAX_OUTBOUND_MEDIA_BYTES:
        return None, (
            422,
            {
                "error": f"attachments total {total / (1 << 20):.2f} MiB, "
                "but Telnyx MMS allows at most 1 MB per message (600 KB is "
                "the carrier-safe size): resize or remove files and send again"
            },
        )
    media_urls = []
    for filename, declared, content in files:
        # Honest declared type (webphone >= 2.8) wins; sniffing remains
        # the fallback for producers that stamp octet-stream.
        mime = declared or sniff_mime(content)
        if mime == "image/heic":
            return None, (
                422,
                {
                    "error": f"attachment {filename or '<unnamed>'} is an iPhone "
                    "High Efficiency photo (HEIC), which MMS cannot carry: on the "
                    "iPhone set Settings → Camera → Formats → Most Compatible and "
                    "send the photo again (it becomes a JPG), or convert it to JPG "
                    "before attaching"
                },
            )
        if mime not in MMS_MEDIA_EXTENSIONS:
            return None, (
                422,
                {
                    "error": f"attachment {filename or '<unnamed>'} has an "
                    "unsupported type for MMS; allowed: jpeg, png, gif, bmp, "
                    "webp, tiff, mp4, 3gp, mov, mp3, wav, amr, ogg, vcard, pdf"
                },
            )
        media_urls.append(store_media(content, mime))
    return media_urls, None


def handle_gateway_message(fields, files):
    """webphone /gateway/message → Telnyx API (SMS/MMS or WhatsApp). Returns (http_status, payload)."""
    to = (fields.get("to") or "").strip()
    body = fields.get("body") or ""
    if not to:
        return 400, {"error": "multipart field 'to' (destination number) is required"}
    channel, address = parse_destination(to)
    if channel is None:
        return 400, {
            "error": f"destination '{to}' selects WhatsApp but carries no "
            "+E164 number after the prefix: use whatsapp:+<number> (or a "
            "plain number for SMS)"
        }
    if not body and not files:
        return 400, {"error": "multipart field 'body' (message text) is required"}
    if channel == WHATSAPP_CHANNEL:
        whatsapp_message, error_response = build_whatsapp_message(body, files)
        if error_response is not None:
            return error_response
        if files:
            sweep_expired_media()
        provider_ref, error = telnyx_send_whatsapp(address, whatsapp_message)
        if provider_ref is None:
            return 502, {"error": error}
        return 200, {"provider_ref": provider_ref}
    media_urls = []
    if files:
        media_urls, error_response = stage_mms_media(files)
        if error_response is not None:
            return error_response
        sweep_expired_media()
    provider_ref, error = telnyx_send_message(address, body, media_urls)
    if provider_ref is None:
        return 502, {"error": error}
    return 200, {"provider_ref": provider_ref}


def handle_gateway_fax_send(fields, files):
    """webphone /gateway/fax → Telnyx Programmable Fax API. Returns (http_status, payload)."""
    to = (fields.get("to") or "").strip()
    if not to:
        return 400, {"error": "multipart field 'to' (destination fax number) is required"}
    if not files:
        return 422, {"error": "a fax needs its PDF document: attach the file (multipart file part 'document')"}
    if len(files) > 1:
        return 422, {"error": f"a fax carries exactly one document (got {len(files)} file parts)"}
    filename, _, pdf = files[0]
    if not pdf.startswith(b"%PDF"):
        return 422, {
            "error": f"document {filename or '<unnamed>'} is not a PDF: fax "
            "documents must be PDF files (a TIFF or image must be converted "
            "first)"
        }
    provider_ref, error = telnyx_send_fax(to, pdf)
    if provider_ref is None:
        return 502, {"error": error}
    return 200, {"provider_ref": provider_ref}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # A peer that stops mid-request must not hold its thread forever.
    timeout = 60

    def send_json(self, code, payload, close=False):
        body = json.dumps(payload).encode()
        if close:
            # The request body was not read to its end, so the keep-alive
            # framing is lost: end the connection instead of parsing the
            # leftover body bytes as a second request.
            self.close_connection = True
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if close:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def send_media(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def declared_length(self):
        """The Content-Length the peer announced; 0 when absent or unreadable."""
        try:
            return max(0, int(self.headers.get("Content-Length", "0") or 0))
        except ValueError:
            return 0

    def read_body(self, cap):
        length = min(self.declared_length(), cap)
        return self.rfile.read(length) if length else b""

    def gateway_authorized(self):
        secret = credential("webphone_secret")
        if not secret:
            self.send_json(503, {"error": ACTIONABLE_SECRET_MISSING})
            return False
        presented = bearer_token(self.headers)
        if presented is None or not secret_matches(presented, secret):
            self.send_json(
                401,
                {"error": "missing or invalid Authorization: Bearer <webphone gateway secret>"},
            )
            return False
        return True

    def do_POST(self):
        if self.path == "/telnyx/webhooks":
            self.handle_telnyx_webhooks()
        elif self.path == "/gateway/message":
            self.handle_gateway_message()
        elif self.path == "/gateway/fax":
            self.handle_gateway_fax()
        else:
            self.send_json(404, {"error": "not found"})

    def handle_telnyx_webhooks(self):
        over_cap = self.declared_length() > MAX_BODY
        if over_cap:
            # Truncation honesty: read_body caps at MAX_BODY, so an oversized
            # event truncates and lands as a raw string. Telnyx retries the
            # exact same bytes, so a 4xx would not help; one journald line
            # names the real cause instead.
            bridge_log("webhook body over cap", declared=self.declared_length(), cap=MAX_BODY)
        raw = self.read_body(MAX_BODY)
        key, key_error = webhook_signature_key()
        if key_error is not None:
            bridge_log("webhook key unusable", error=str(key_error))
            self.send_json(
                503,
                {"error": f"webhook signature verification is on but its key is unusable: {key_error}"},
                close=over_cap,
            )
            return
        if key is not None:
            verdict = verify_webhook_signature(raw, self.headers, key)
            if verdict is not True:
                bridge_log(
                    "webhook signature rejected",
                    reason=verdict,
                    remote=self.client_address[0],
                )
                self.send_json(403, {"error": f"webhook signature rejected: {verdict}"}, close=over_cap)
                return
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"raw": raw.decode("utf-8", "replace")}
        append_entry(
            {
                "received_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "remote": self.client_address[0],
                "body": body,
            }
        )
        status, payload = self.route_webhook_body(body)
        self.send_json(status, payload, close=over_cap)

    def route_webhook_body(self, body):
        """(status, payload) for one logged webhook body."""
        if not isinstance(body, dict):
            return 200, {"ok": True}  # no envelope: logged only
        data = body.get("data")
        if data is None:
            return 200, {"ok": True}
        if not isinstance(data, dict):
            return 400, {"error": "webhook field 'data' must be an object"}
        try:
            return handle_telnyx_event(data)
        except Exception as error:  # noqa: BLE001 - one bad event must not drop Telnyx's connection
            print(traceback.format_exc(), end="", flush=True)
            bridge_log(
                "webhook handler crashed",
                event_type=text_of(data.get("event_type")),
                error=f"{type(error).__name__}: {error}",
            )
            return 503, {"error": "webhook handling failed (Telnyx should retry)"}

    def handle_gateway_message(self):
        if not self.gateway_authorized():
            return
        # Content-Length pre-check: reading with a cap silently TRUNCATES
        # an oversized body, and the parser then dies as a "malformed
        # multipart" 400, a lie about what went wrong. The declared size is
        # known before the first byte is read.
        declared_length = self.declared_length()
        if declared_length > MAX_GATEWAY_BODY:
            self.send_json(
                422,
                {
                    "error": f"request body is {declared_length / (1 << 20):.1f} MiB, "
                    "but the gateway reads at most 8 MiB per request, and Telnyx "
                    "MMS carries at most 1 MB of attachments per message (600 KB "
                    "is the carrier-safe size): send fewer or smaller attachments"
                },
                close=True,
            )
            return
        raw = self.read_body(MAX_GATEWAY_BODY)
        try:
            fields, files = parse_multipart(self.headers.get("Content-Type", ""), raw)
        except ValueError as error:
            self.send_json(400, {"error": f"malformed multipart body: {error}"})
            return
        status, payload = handle_gateway_message(fields, files)
        self.send_json(status, payload)

    def handle_gateway_fax(self):
        if not self.gateway_authorized():
            return
        # Same honest pre-read pre-check as /gateway/message. The bridge
        # reads at most 8 MiB per request; Telnyx's own multipart upload
        # caps at 20 MB / 350 pages, so an oversized-here document is
        # oversized for the API too.
        declared_length = self.declared_length()
        if declared_length > MAX_GATEWAY_BODY:
            self.send_json(
                422,
                {
                    "error": f"request body is {declared_length / (1 << 20):.1f} MiB, "
                    "but the gateway reads at most 8 MiB per request (Telnyx "
                    "accepts fax documents up to 20 MB / 350 pages — split or "
                    "downscale the scan)"
                },
                close=True,
            )
            return
        raw = self.read_body(MAX_GATEWAY_BODY)
        try:
            fields, files = parse_multipart(self.headers.get("Content-Type", ""), raw)
        except ValueError as error:
            self.send_json(400, {"error": f"malformed multipart body: {error}"})
            return
        status, payload = handle_gateway_fax_send(fields, files)
        self.send_json(status, payload)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/telnyx/webhooks/health":
            self.send_json(200, {"ok": True})
            return
        if path.startswith("/mms-media/"):
            self.handle_mms_media(path[len("/mms-media/") :])
            return
        if path == "/gateway/health":
            self.send_json(
                200,
                {
                    "ok": True,
                    "webhook_signature": signature_state(),
                    "webphone_secret": credential("webphone_secret") is not None,
                    "telnyx_api_key": telnyx_api_key() is not None,
                    "webphone_url": WEBPHONE_URL,
                    "sms_to_extension": SMS_TO_EXTENSION,
                    "from_number": FROM_NUMBER,
                    "whatsapp_from": WHATSAPP_FROM or None,
                    "fax": {
                        "enabled": bool(FAX_CONNECTION_ID and FAX_FROM_NUMBER),
                        "from": FAX_FROM_NUMBER or None,
                        "connection_id": FAX_CONNECTION_ID or None,
                    },
                },
            )
            return
        if path == "/telnyx/webhooks/recent":
            if not token_valid(self.headers):
                self.send_json(403, {"error": "forbidden"})
                return
            limit = 20
            for part in query.split("&"):
                if part.startswith("limit="):
                    try:
                        limit = max(1, min(200, int(part[6:])))
                    except ValueError:
                        pass
            self.send_json(200, {"entries": last_entries(limit)})
            return
        self.send_json(404, {"error": "not found"})

    def handle_mms_media(self, name):
        """Serve one staged outbound MMS medium (Telnyx fetches at send time)."""
        if not MEDIA_NAME_RE.fullmatch(name):
            self.send_json(404, {"error": "not found"})
            return
        try:
            sidecar = json.loads((MEDIA_DIR / f"{name.rsplit('.', 1)[0]}.json").read_text())
            content = (MEDIA_DIR / name).read_bytes()
        except (OSError, ValueError):
            # A miss here means the TTL sweep deleted the medium before
            # Telnyx fetched it (the MMS send then fails on Telnyx's side)
            # — or nothing was ever staged under this token.
            bridge_log("staged mms media miss", name=name)
            self.send_json(404, {"error": "not found"})
            return
        bridge_log("served staged mms media", name=name, mime=sidecar.get("mime"))
        self.send_media(200, sidecar.get("mime") or "application/octet-stream", content)

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} {fmt % args}", flush=True)


def main():
    sweep_expired_media()
    print(
        f"telnyx-webhooks: listening on {BIND[0]}:{BIND[1]}, "
        f"webphone={WEBPHONE_URL} owner_ext={SMS_TO_EXTENSION} from={FROM_NUMBER} "
        f"whatsapp={WHATSAPP_FROM or 'disabled (whatsapp: destinations 502)'} "
        f"fax={FAX_FROM_NUMBER or 'disabled (gateway fax 502)'} via connection "
        f"{FAX_CONNECTION_ID or '-'} "
        f"mms_media={PUBLIC_BASE_URL}/mms-media (dir {MEDIA_DIR}) "
        f"webphone_secret={'present' if credential('webphone_secret') else 'MISSING'} "
        f"telnyx_key={'present' if telnyx_api_key() else 'absent (outbound 503)'} "
        f"webhook_signature={signature_state()}",
        flush=True,
    )
    ThreadingHTTPServer(BIND, Handler).serve_forever()


if __name__ == "__main__":
    main()
