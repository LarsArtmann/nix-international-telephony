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
   ``/gateway/fax`` (honest 503: fax over Telnyx is not wired yet).
   Attachments are MMS: each file is type-sniffed (magic bytes, never
   the client's Content-Type), capped at 1 MB total (Telnyx MMS hard
   cap; 600 KB is the carrier-safe size), stored under
   ``/var/lib/telnyx-webhooks/media`` behind an unguessable token, and
   sent as Telnyx ``media_urls`` pointing at
   ``PUBLIC_BASE_URL/mms-media/<token>.<ext>`` — Telnyx fetches the
   media at send time, so the URL must be public (nginx exposes it).
   Stored media is swept after ``MEDIA_TTL`` (7 days).

Secrets arrive via systemd ``LoadCredential`` (exposed through the
systemd-provided ``$CREDENTIALS_DIR``, i.e.
``/run/credentials/telnyx-webhooks.service/``):

- ``webphone_secret`` — shared with webphone's
  ``WEBPHONE_GATEWAY__WEBHOOK_SECRET``; gates the ``/gateway/*`` endpoints
  (Bearer) and signs the forwarded ``/hooks/*`` calls.
- ``telnyx_key`` — Telnyx V2 API key. A ``PLACEHOLDER*`` value counts as
  absent: outbound fails closed with an actionable 503 until a real key
  is dropped into the file behind the module's ``telnyxApiKeyFile``
  option.
- ``webhook_token`` — bearer token gating the ``GET /telnyx/webhooks/recent``
  reader.

Environment (the telephony module's ``services.telephony.messaging``
options set these; sentinels shown — the module always provides the
deployment's ``FROM_NUMBER`` and ``PUBLIC_BASE_URL``):

- ``WEBPHONE_URL`` (http://127.0.0.1:8080)
- ``SMS_TO_EXTENSION`` (1000) — owner extension for inbound SMS/MMS
- ``FROM_NUMBER`` (empty sentinel) — outbound CLI, the messaging DID
- ``PUBLIC_BASE_URL`` (http://127.0.0.1 sentinel) — public origin Telnyx
  fetches outbound MMS media from (the module derives https://<domain>)
- ``PORT`` (8069) — loopback listen port
- ``MEDIA_DIR`` (/var/lib/telnyx-webhooks/media) — outbound MMS staging
"""

import base64
import datetime
import hmac
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.request
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG_FILE = Path("/var/lib/telnyx-webhooks/inbound.jsonl")
# systemd exposes LoadCredential files at /run/credentials/<unit>.service/
# and exports $CREDENTIALS_DIR pointing there — always prefer the env var
# (the unit-named directory includes the ".service" suffix, easy to miss).
CREDENTIALS_DIR = Path(
    os.environ.get("CREDENTIALS_DIR") or "/run/credentials/telnyx-webhooks.service"
)
TOKEN_FILE = CREDENTIALS_DIR / "webhook_token"

BIND = ("127.0.0.1", int(os.environ.get("PORT", "8069")))
WEBPHONE_URL = os.environ.get("WEBPHONE_URL", "http://127.0.0.1:8080").rstrip("/")
SMS_TO_EXTENSION = os.environ.get("SMS_TO_EXTENSION", "1000")
FROM_NUMBER = os.environ.get("FROM_NUMBER", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1").rstrip("/")
MEDIA_DIR = Path(os.environ.get("MEDIA_DIR", "/var/lib/telnyx-webhooks/media"))
TELNYX_MESSAGES_API = "https://api.telnyx.com/v2/messages"

MAX_BODY = 1 << 20  # Telnyx webhook bodies
MAX_GATEWAY_BODY = 8 << 20  # webphone multipart (text + attachments)
MAX_MEDIA_BYTES = 5 << 20  # inbound MMS media fetch cap
MAX_OUTBOUND_MEDIA_BYTES = 1 << 20  # Telnyx MMS total-attachment cap (600 KB safest)
MEDIA_TTL_SECONDS = 7 * 24 * 3600  # outbound media only has to outlive the send
MEDIA_NAME_RE = re.compile(r"[A-Za-z0-9_-]{16,64}\.[a-z0-9]{2,5}")
HTTP_TIMEOUT = 10
HTTP_RETRIES = 1  # one retry on 5xx / transport errors

# The MMS types Telnyx accepts, mapped to the storage extension. Type
# comes from magic-byte sniffing (sniff_mime), never client metadata.
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
    try:
        expected = TOKEN_FILE.read_text().strip()
    except OSError:
        return False
    return hmac.compare_digest(headers.get("Authorization", ""), f"Bearer {expected}")


def bearer_token(headers):
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    return auth[len("Bearer ") :].strip()


def http_json(method, url, payload=None, headers=None, timeout=HTTP_TIMEOUT):
    """Request with one retry on 5xx/transport errors. Returns (status, body).

    Raises only when the final transport attempt fails; HTTP-level errors
    are returned as (code, body) so callers can decide what to surface.
    """
    data = json.dumps(payload).encode() if payload is not None else None
    last_transport_error = None
    for attempt in range(HTTP_RETRIES + 1):
        request = urllib.request.Request(url, data=data, method=method)
        if headers:
            for key, value in headers.items():
                request.add_header(key, value)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            body = error.read()
            if error.code >= 500 and attempt < HTTP_RETRIES:
                last_transport_error = f"HTTP {error.code}"
                continue
            return error.code, body
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_transport_error = str(error)
    raise ConnectionError(f"{url} unreachable: {last_transport_error}")


def fetch_media(url):
    """Fetch one inbound MMS medium, size-capped. Returns (mime, bytes) or None."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    request = urllib.request.Request(
        url, headers={"User-Agent": "telephony-bridge/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            content = response.read(MAX_MEDIA_BYTES + 1)
            mime = (
                (response.headers.get("Content-Type") or "application/octet-stream")
                .split(";")[0]
                .strip()
            )
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    if len(content) > MAX_MEDIA_BYTES:
        return None
    return mime, content


def media_name(url, mime):
    tail = url.rsplit("/", 1)[-1].split("?")[0]
    if tail:
        return tail[:80]
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
    if data.startswith(b"ID3") or (
        len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0
    ):
        return "audio/mpeg"
    if data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand.startswith(
            (b"heic", b"heix", b"hevc", b"heim", b"heis", b"hevx", b"mif1", b"msf1")
        ):
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
    location. A sidecar .json carries the sniffed mime + creation time.
    """
    token = secrets.token_urlsafe(16)
    extension = MMS_MEDIA_EXTENSIONS[mime]
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    (MEDIA_DIR / f"{token}.{extension}").write_bytes(content)
    (MEDIA_DIR / f"{token}.json").write_text(
        json.dumps({"mime": mime, "created": time.time()})
    )
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


def forward_inbound_message(payload):
    """message.received → webphone /hooks/message. Returns (ok, error)."""
    secret = credential("webphone_secret")
    if not secret:
        return False, ACTIONABLE_SECRET_MISSING
    attachments = []
    fetch_failures = []
    for media in payload.get("media") or []:
        if not isinstance(media, dict):
            continue
        fetched = fetch_media(media.get("url"))
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
        "from": phone_number(payload.get("from")),
        "body": payload.get("text") or "",
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
    for entry in payload.get("to") or []:
        if not isinstance(entry, dict):
            continue
        status = entry.get("status")
        if isinstance(status, str):
            statuses.add(status)
        for error in entry.get("errors") or []:
            if isinstance(error, dict):
                detail = error.get("detail") or error.get("title") or error.get("code")
                if detail:
                    errors.append(str(detail))
    if TELEPHONE_STATUS_DELIVERED in statuses:
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


def handle_telnyx_event(data):
    """Route one parsed Telnyx webhook body. Returns (http_status, payload)."""
    event_type = data.get("event_type") or ""
    payload = data.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    if event_type == "message.received":
        ok, error = forward_inbound_message(payload)
        if not ok:
            return 503, {
                "error": f"inbound forward failed (Telnyx should retry): {error}"
            }
        return 200, {"ok": True}
    if event_type in ("message.finalized", "message.delivery_updated"):
        forwarded, error = forward_message_status(payload)
        if error:
            return 503, {
                "error": f"status forward failed (Telnyx should retry): {error}"
            }
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
        )
    except ConnectionError as error:
        return None, f"telnyx api unreachable: {error}"
    if status not in range(200, 300):
        return None, telnyx_rejection(status, body)
    try:
        provider_ref = json.loads(body)["data"]["id"]
    except (ValueError, KeyError, TypeError):
        return None, "telnyx api response is missing data.id"
    return provider_ref, None


def parse_multipart(content_type, raw):
    """Parse multipart/form-data into (fields: dict, files).

    files is a list of (filename, part_content_type, bytes) — the part
    Content-Type is captured but NOT trusted for routing decisions
    (Go's CreateFormFile writes application/octet-stream; sniff instead).
    The email parser handles what Go's mime/multipart writes; malformed
    input raises ValueError.
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
            files.append((filename, part.get_content_type(), content))
        else:
            fields[name] = content.decode("utf-8", "replace")
    return fields, files


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
    for filename, _, content in files:
        mime = sniff_mime(content)
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
    """webphone /gateway/message → Telnyx API. Returns (http_status, payload)."""
    to = (fields.get("to") or "").strip()
    body = fields.get("body") or ""
    if not to:
        return 400, {"error": "multipart field 'to' (destination number) is required"}
    if not body and not files:
        return 400, {"error": "multipart field 'body' (message text) is required"}
    media_urls = []
    if files:
        media_urls, error_response = stage_mms_media(files)
        if error_response is not None:
            return error_response
        sweep_expired_media()
    provider_ref, error = telnyx_send_message(to, body, media_urls)
    if provider_ref is None:
        return 502, {"error": error}
    return 200, {"provider_ref": provider_ref}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_media(self, code, content_type, body):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, max-age=86400")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self, cap):
        length = min(int(self.headers.get("Content-Length", "0") or 0), cap)
        return self.rfile.read(length) if length else b""

    def gateway_authorized(self):
        secret = credential("webphone_secret")
        if not secret:
            self.send_json(503, {"error": ACTIONABLE_SECRET_MISSING})
            return False
        presented = bearer_token(self.headers)
        if presented is None or not hmac.compare_digest(presented, secret):
            self.send_json(
                401,
                {
                    "error": "missing or invalid Authorization: Bearer <webphone gateway secret>"
                },
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
        # Truncation honesty (mirrors the /gateway/message pre-check):
        # read_body caps at MAX_BODY, so an oversized event silently
        # truncates, json-parse fails, and the entry lands as a raw
        # string. Telnyx retries the exact same bytes, so a 4xx would
        # not help — one journald line names the real cause instead.
        try:
            declared_length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            declared_length = 0
        if declared_length > MAX_BODY:
            bridge_log(
                "webhook body over cap",
                declared=declared_length,
                cap=MAX_BODY,
            )
        raw = self.read_body(MAX_BODY)
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
        if isinstance(body, dict):
            status, payload = handle_telnyx_event(body.get("data") or {})
        else:
            status, payload = 200, {"ok": True}
        self.send_json(status, payload)

    def handle_gateway_message(self):
        if not self.gateway_authorized():
            return
        # Content-Length pre-check (SUPERB error-excellence T06): reading
        # with a cap silently TRUNCATES an oversized body, and the parser
        # then dies as a "malformed multipart" 400 — a lie about what went
        # wrong. The declared size is known before the first byte is read.
        try:
            declared_length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            declared_length = 0
        if declared_length > MAX_GATEWAY_BODY:
            self.send_json(
                422,
                {
                    "error": f"request body is {declared_length / (1 << 20):.1f} MiB, "
                    "but the gateway reads at most 8 MiB per request, and Telnyx "
                    "MMS carries at most 1 MB of attachments per message (600 KB "
                    "is the carrier-safe size): send fewer or smaller attachments"
                },
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
        self.send_json(
            503,
            {
                "error": "fax delivery over Telnyx is not wired yet (needs a "
                "Telnyx fax application + number); this send is marked failed "
                "in the webphone UI on purpose — no silent fake success"
            },
        )

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
                    "webphone_secret": credential("webphone_secret") is not None,
                    "telnyx_api_key": telnyx_api_key() is not None,
                    "webphone_url": WEBPHONE_URL,
                    "sms_to_extension": SMS_TO_EXTENSION,
                    "from_number": FROM_NUMBER,
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
            sidecar = json.loads(
                (MEDIA_DIR / f"{name.rsplit('.', 1)[0]}.json").read_text()
            )
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
        f"mms_media={PUBLIC_BASE_URL}/mms-media (dir {MEDIA_DIR}) "
        f"webphone_secret={'present' if credential('webphone_secret') else 'MISSING'} "
        f"telnyx_key={'present' if telnyx_api_key() else 'absent (outbound 503)'}",
        flush=True,
    )
    ThreadingHTTPServer(BIND, Handler).serve_forever()


if __name__ == "__main__":
    main()
