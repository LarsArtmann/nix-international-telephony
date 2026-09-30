"""Unit tests for the telnyx-webhooks bridge (modules/telephony/telnyx-webhooks.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest discover -s tests -v

A stub upstream server plays both upstream roles, distinguished by path:
webphone's /hooks/* and Telnyx's /v2/messages. The bridge itself runs
in-process on an ephemeral port; every test talks plain HTTP.
"""

import base64
import importlib.util
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

BRIDGE_PATH = (
    Path(__file__).resolve().parents[1] / "modules" / "telephony" / "telnyx-webhooks.py"
)

spec = importlib.util.spec_from_file_location("telnyx_bridge", BRIDGE_PATH)
assert spec is not None and spec.loader is not None, BRIDGE_PATH
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)

WEBPHONE_SECRET = "test-webphone-shared-secret-0123456789"
TELNYX_KEY = "KEYFAKE0123456789abcdef"


class StubUpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: ClassVar[list] = []
    stub_responses: ClassVar[
        dict
    ] = {}  # path -> (status, payload); default 200 {"data":{"id":"stub-ref"}}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        StubUpstreamHandler.seen.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization", ""),
                "content_type": self.headers.get("Content-Type", ""),
                "body": json.loads(raw) if raw else None,
            }
        )
        status, payload = StubUpstreamHandler.stub_responses.get(
            self.path, (200, {"data": {"id": "stub-ref"}})
        )
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def multipart(fields, files=()):
    """files: (filename, content) or (filename, content, declared_type);
    declared_type None omits the part Content-Type header entirely."""
    boundary = "testboundary7351024"
    parts = []
    for name, value in fields.items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        )
    for file_spec in files:
        filename, content = file_spec[0], file_spec[1]
        declared = file_spec[2] if len(file_spec) > 2 else "application/octet-stream"
        headers = f'--{boundary}\r\nContent-Disposition: form-data; name="attachment"; '
        if declared is not None:
            headers += f'filename="{filename}"\r\nContent-Type: {declared}\r\n\r\n'
        else:
            headers += f'filename="{filename}"\r\n\r\n'
        parts.append(headers.encode() + content + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def http(method, url, data=None, headers=None):
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 - stub/loopback server
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)

        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), StubUpstreamHandler)
        StubUpstreamHandler.seen = []
        StubUpstreamHandler.stub_responses = {}
        threading.Thread(target=self.upstream.serve_forever, daemon=True).start()
        upstream_url = f"http://127.0.0.1:{self.upstream.server_address[1]}"

        credentials = tmp / "credentials"
        credentials.mkdir()
        (credentials / "webphone_secret").write_text(WEBPHONE_SECRET)
        (credentials / "telnyx_key").write_text(TELNYX_KEY)

        bridge.CREDENTIALS_DIR = credentials
        bridge.LOG_FILE = tmp / "inbound.jsonl"
        bridge.TOKEN_FILE = tmp / "receiver-token"
        bridge.TOKEN_FILE.write_text("receiver-token-0123456789")
        bridge.WEBPHONE_URL = upstream_url
        bridge.TELNYX_MESSAGES_API = f"{upstream_url}/v2/messages"
        bridge.TELNYX_WHATSAPP_API = f"{upstream_url}/v2/messages/whatsapp"
        bridge.WHATSAPP_FROM = ""  # WhatsApp lane disabled unless a test enables it
        bridge.SMS_TO_EXTENSION = "1000"
        bridge.FROM_NUMBER = "+15550100000"
        bridge.MEDIA_DIR = tmp / "media"

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), bridge.Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        bridge.PUBLIC_BASE_URL = self.base  # media URLs route back into this bridge

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.upstream.shutdown()
        self.upstream.server_close()
        self.tmp.cleanup()

    # /gateway/message — auth + fail-closed behavior

    def test_gateway_message_requires_bearer(self):
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
        )
        status, payload = http(
            "POST", f"{self.base}/gateway/message", body, {"Content-Type": content_type}
        )
        self.assertEqual(status, 401)
        self.assertIn("Authorization", payload["error"])

    def test_gateway_message_rejects_wrong_secret(self):
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
        )
        status, _ = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}x",
            },
        )
        self.assertEqual(status, 401)

    def test_gateway_message_without_secret_configured_is_actionable_503(self):
        (bridge.CREDENTIALS_DIR / "webphone_secret").unlink()
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
        )
        status, payload = http(
            "POST", f"{self.base}/gateway/message", body, {"Content-Type": content_type}
        )
        self.assertEqual(status, 503)
        self.assertIn("webphone_gateway_secret", payload["error"])

    def test_gateway_message_placeholder_telnyx_key_is_absent(self):
        (bridge.CREDENTIALS_DIR / "telnyx_key").write_text(
            "PLACEHOLDER-OWNER-MUST-REPLACE"
        )
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 502)
        self.assertIn("telnyx_api_key", payload["error"])
        self.assertIn("api-keys", payload["error"])

    def test_gateway_message_roundtrip(self):
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "hello there",
            }
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"provider_ref": "stub-ref"})
        self.assertEqual(len(StubUpstreamHandler.seen), 1)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/messages")
        self.assertEqual(sent["authorization"], f"Bearer {TELNYX_KEY}")
        self.assertEqual(
            sent["body"],
            {"from": "+15550100000", "to": "+1234567890", "text": "hello there"},
        )

    def test_gateway_message_missing_fields(self):
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "body": "hi"}
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("'to'", payload["error"])

    def test_gateway_message_mms_roundtrip(self):
        # An octet-stream part (what pre-2.8 webphone binaries still stamp
        # via Go's CreateFormFile) is typed by magic-byte sniffing: the
        # staged file is served back with the sniffed Content-Type.
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("photo.png", png)],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"provider_ref": "stub-ref"})
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/messages")
        media_urls = sent["body"].get("media_urls")
        self.assertEqual(len(media_urls), 1)
        self.assertTrue(media_urls[0].startswith(f"{self.base}/mms-media/"))
        self.assertTrue(media_urls[0].endswith(".png"))
        self.assertEqual(sent["body"].get("text"), "see attachment")

        # The staged medium is served publicly with its sniffed type.
        with urllib.request.urlopen(media_urls[0], timeout=10) as response:  # nosec B310 - staged media on this host
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Content-Type"), "image/png")
            self.assertEqual(response.read(), png)

    def test_gateway_message_mms_declared_type_wins_over_sniffing(self):
        # webphone >= 2.8 stamps each part with the attachment's own
        # mime: the declared type routes the media, even when the magic
        # bytes alone would sniff differently (this ftyp payload sniffs
        # as video/mp4; the producer honestly declares quicktime/.mov).
        mov = b"\x00\x00\x00\x1cftypqt\x00\x00\x00\x00" + b"\x00" * 16
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "clip",
            },
            files=[("clip.mov", mov, "video/quicktime")],
        )
        status, _payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        media_urls = StubUpstreamHandler.seen[0]["body"]["media_urls"]
        self.assertTrue(media_urls[0].endswith(".mov"))
        with urllib.request.urlopen(media_urls[0], timeout=10) as response:  # nosec B310 - staged media on this host
            self.assertEqual(response.headers.get("Content-Type"), "video/quicktime")

    def test_gateway_message_mms_part_without_content_type_is_sniffed(self):
        # A part carrying NO Content-Type header must not fall back to the
        # email parser's text/plain default — it sniffs like an undeclared
        # part (same lane as the octet-stream legacy producers).
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("photo.png", png, None)],
        )
        status, _payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        media_urls = StubUpstreamHandler.seen[0]["body"]["media_urls"]
        self.assertTrue(media_urls[0].endswith(".png"))

    def test_gateway_message_mms_declared_heic_is_rejected_honestly(self):
        # The HEIC 422 with the fix-the-phone copy fires on the declared
        # type — no magic bytes needed once the producer is honest.
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("photo.heic", b"declared-but-opaque", "image/heic")],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("HEIC", payload["error"])
        self.assertIn("Most Compatible", payload["error"])

    def test_gateway_message_mms_without_text(self):
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "to": "+1234567890", "body": ""},
            files=[("pic.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 16)],
        )
        status, _payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 200)
        sent = StubUpstreamHandler.seen[0]
        self.assertNotIn("text", sent["body"])  # empty text is omitted, not sent as ""
        self.assertEqual(len(sent["body"]["media_urls"]), 1)

    def test_gateway_message_mms_rejects_oversized_total(self):
        # Telnyx MMS hard cap: 1 MB total attachments (600 KB carrier-safe).
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "big",
            },
            files=[("photo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * ((1 << 20) + 1))],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("1 MB", payload["error"])

    def test_gateway_message_mms_rejects_unknown_type(self):
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("payload.exe", b"MZ\x90\x00" + b"\x00" * 16)],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("payload.exe", payload["error"])
        self.assertIn("unsupported type", payload["error"])

    def test_mms_media_endpoint_rejects_bad_names(self):
        for name in (
            "../../etc/passwd",
            "short.png",
            "token-with-a-very-long-name-well-over-sixty-four-charactersx.png",
            "UPPER.png",
            "nonexistent.png",
        ):
            status, _payload = http("GET", f"{self.base}/mms-media/{name}")
            self.assertEqual(status, 404, name)

    def test_sweep_expired_media_removes_old_pairs(self):
        import time as time_module

        url = bridge.store_media(b"\x89PNG\r\n\x1a\n" + b"data", "image/png")
        name = url.rsplit("/", 1)[-1]
        token = name.rsplit(".", 1)[0]
        stale = bridge.MEDIA_DIR / f"{token}.json"
        stale.write_text(
            json.dumps(
                {"mime": "image/png", "created": time_module.time() - 8 * 24 * 3600}
            )
        )
        bridge.sweep_expired_media()
        self.assertFalse((bridge.MEDIA_DIR / name).exists())
        self.assertFalse(stale.exists())

    def test_gateway_message_upstream_500_maps_to_502(self):
        StubUpstreamHandler.stub_responses["/v2/messages"] = (
            500,
            {"errors": [{"detail": "boom"}]},
        )
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "to": "+1234567890", "body": "hi"}
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 502)
        self.assertIn("telnyx rejected the send (HTTP 500)", payload["error"])
        self.assertIn("boom", payload["error"])
        self.assertNotIn('"errors"', payload["error"])

    def test_gateway_message_self_send_rejection_is_humanized(self):
        # 2026-09-21 production burn: sending to the DID itself answers
        # 400 code 40310 "Source and destination cannot be the same
        # number" — the surfaced error must carry that reason, because
        # the webphone displays the bridge's error text verbatim.
        StubUpstreamHandler.stub_responses["/v2/messages"] = (
            400,
            {
                "errors": [
                    {
                        "code": "40310",
                        "title": "Invalid 'to' address",
                        "detail": "Source and destination cannot be the same number: +15550100000",
                    }
                ]
            },
        )
        body, content_type = multipart(
            {"kind": "message", "owner": "1000", "to": "+15550100000", "body": "xxx"}
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 502)
        error = payload["error"]
        self.assertIn("cannot be the same number", error)
        self.assertIn("40310", error)
        self.assertNotIn('{"errors"', error)

    # /gateway/message — WhatsApp lane (whatsapp: destinations)

    def whatsapp_send(self, to, body="hi from whatsapp", files=()):
        fields = {"kind": "message", "owner": "1000", "to": to, "body": body}
        payload, content_type = multipart(fields, files=files)
        return http(
            "POST",
            f"{self.base}/gateway/message",
            payload,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )

    def test_whatsapp_text_roundtrip(self):
        # The channel selector is the destination prefix: a whatsapp:
        # destination rides POST /v2/messages/whatsapp with the
        # whatsapp_message object, from the dedicated WhatsApp number.
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "hello there")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"provider_ref": "stub-ref"})
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/messages/whatsapp")
        self.assertEqual(sent["authorization"], f"Bearer {TELNYX_KEY}")
        self.assertEqual(
            sent["body"],
            {
                "from": "+15550100000",
                "to": "+1234567890",
                "whatsapp_message": {
                    "type": "text",
                    "text": {"body": "hello there", "preview_url": False},
                },
            },
        )

    def test_whatsapp_sanitized_prefix_form_roundtrip(self):
        # webphone's dialable sanitizer keeps letters and drops the colon:
        # 'whatsapp:+49…' arrives as 'whatsapp+49…' and must parse the same.
        bridge.WHATSAPP_FROM = "+15550100000"
        status, _ = self.whatsapp_send("whatsapp+4915112345678")
        self.assertEqual(status, 200)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["to"], "+4915112345678")

    def test_whatsapp_mixed_case_prefix_roundtrip(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, _ = self.whatsapp_send("WhatsApp:+1234567890")
        self.assertEqual(status, 200)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["to"], "+1234567890")

    def test_whatsapp_disabled_is_actionable_502(self):
        # WHATSAPP_FROM empty (WhatsApp not enabled in the module): the
        # send fails closed with the portal setup guidance, never a fake
        # SMS fallback to the same number.
        self.assertEqual(bridge.WHATSAPP_FROM, "")
        status, payload = self.whatsapp_send("whatsapp:+1234567890")
        self.assertEqual(status, 502)
        self.assertIn("whatsapp.enable", payload["error"])
        self.assertIn("messaging.whatsapp.did", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_whatsapp_invalid_destination_is_honest_400(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:hello")
        self.assertEqual(status, 400)
        self.assertIn("+E164", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_whatsapp_image_roundtrip_with_caption(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890", "see the photo", files=[("photo.png", png)]
        )
        self.assertEqual((status, payload), (200, {"provider_ref": "stub-ref"}))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["to"], "+1234567890")
        message = sent["body"]["whatsapp_message"]
        self.assertEqual(message["type"], "image")
        link = message["image"]["link"]
        self.assertTrue(link.startswith(f"{self.base}/mms-media/"))
        self.assertTrue(link.endswith(".png"))
        self.assertEqual(message["image"]["caption"], "see the photo")
        with urllib.request.urlopen(link, timeout=10) as response:  # nosec B310 - staged media on this host
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Content-Type"), "image/png")
            self.assertEqual(response.read(), png)

    def test_whatsapp_pdf_rides_as_document_with_filename(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        pdf = b"%PDF-1.4" + b"\x00" * 16
        status, _ = self.whatsapp_send(
            "whatsapp:+1234567890", "the invoice", files=[("invoice.pdf", pdf)]
        )
        self.assertEqual(status, 200)
        message = StubUpstreamHandler.seen[0]["body"]["whatsapp_message"]
        self.assertEqual(message["type"], "document")
        self.assertTrue(message["document"]["link"].endswith(".pdf"))
        self.assertEqual(message["document"]["filename"], "invoice.pdf")
        self.assertEqual(message["document"]["caption"], "the invoice")

    def test_whatsapp_audio_carries_no_caption(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        mp3 = b"ID3" + b"\x00" * 16
        status, _ = self.whatsapp_send(
            "whatsapp:+1234567890", "a voice note", files=[("note.mp3", mp3)]
        )
        self.assertEqual(status, 200)
        message = StubUpstreamHandler.seen[0]["body"]["whatsapp_message"]
        self.assertEqual(message["type"], "audio")
        self.assertNotIn("caption", message["audio"])

    def test_whatsapp_mms_only_type_rides_as_document(self):
        # WhatsApp has no native kind for gif (or tiff/vcard/mov/…): the
        # medium still sends, honestly, as a document with its filename.
        bridge.WHATSAPP_FROM = "+15550100000"
        gif = b"GIF89a" + b"\x00" * 16
        status, _ = self.whatsapp_send(
            "whatsapp:+1234567890", "funny one", files=[("meme.gif", gif)]
        )
        self.assertEqual(status, 200)
        message = StubUpstreamHandler.seen[0]["body"]["whatsapp_message"]
        self.assertEqual(message["type"], "document")
        self.assertEqual(message["document"]["filename"], "meme.gif")
        self.assertEqual(message["document"]["caption"], "funny one")

    def test_whatsapp_media_without_text_sends_no_caption(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        status, _ = self.whatsapp_send(
            "whatsapp:+1234567890", "", files=[("photo.png", png)]
        )
        self.assertEqual(status, 200)
        message = StubUpstreamHandler.seen[0]["body"]["whatsapp_message"]
        self.assertNotIn("caption", message["image"])

    def test_whatsapp_two_attachments_rejected(self):
        # WhatsApp carries exactly ONE media object per message — the
        # honest 422 beats a silent "send the first, drop the rest".
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890",
            "two photos",
            files=[("a.png", png), ("b.png", png)],
        )
        self.assertEqual(status, 422)
        self.assertIn("exactly one media object", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_whatsapp_text_over_4096_bytes_rejected(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "x" * 4097)
        self.assertEqual(status, 422)
        self.assertIn("4096", payload["error"])

    def test_whatsapp_caption_over_1024_bytes_rejected(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890", "x" * 1025, files=[("photo.png", png)]
        )
        self.assertEqual(status, 422)
        self.assertIn("1024", payload["error"])

    def test_whatsapp_declared_heic_gets_the_iphone_fix_copy(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890",
            "photo",
            files=[("IMG_0001.HEIC", b"declared-but-opaque", "image/heic")],
        )
        self.assertEqual(status, 422)
        self.assertIn("HEIC", payload["error"])
        self.assertIn("Most Compatible", payload["error"])

    def test_whatsapp_unknown_type_rejected(self):
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890",
            "see attachment",
            files=[("payload.exe", b"MZ\x90\x00" + b"\x00" * 16)],
        )
        self.assertEqual(status, 422)
        self.assertIn("unsupported type", payload["error"])

    def test_whatsapp_oversize_image_rejected(self):
        # WhatsApp image cap: 5 MiB (docs-verified 2026-09-30). The
        # honest pre-flight 422 beats Telnyx refusing the fetch later.
        bridge.WHATSAPP_FROM = "+15550100000"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * (5 << 20)
        status, payload = self.whatsapp_send(
            "whatsapp:+1234567890", "big", files=[("photo.png", png)]
        )
        self.assertEqual(status, 422)
        self.assertIn("5 MiB", payload["error"])
        self.assertEqual(StubUpstreamHandler.seen, [])

    def test_whatsapp_window_rejection_carries_guidance(self):
        # Outside the 24-hour customer-service window WhatsApp refuses
        # free-form text (40008 catch-all): the surfaced error must
        # explain the window and the template fix, not look transient.
        StubUpstreamHandler.stub_responses["/v2/messages/whatsapp"] = (
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
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "ping")
        self.assertEqual(status, 502)
        self.assertIn("24 hours", payload["error"])
        self.assertIn("template", payload["error"])

    def test_whatsapp_plain_rejection_has_no_window_guidance(self):
        StubUpstreamHandler.stub_responses["/v2/messages/whatsapp"] = (
            400,
            {"errors": [{"detail": "invalid destination number"}]},
        )
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = self.whatsapp_send("whatsapp:+1234567890", "ping")
        self.assertEqual(status, 502)
        self.assertIn("invalid destination number", payload["error"])
        self.assertNotIn("24 hours", payload["error"])

    def test_sms_lane_unchanged_when_whatsapp_enabled(self):
        # Enabling WhatsApp must not move plain-number traffic: an SMS
        # send with WHATSAPP_FROM set still rides POST /v2/messages.
        bridge.WHATSAPP_FROM = "+15550100000"
        status, _ = self.whatsapp_send("+1234567890", "plain sms")
        self.assertEqual(status, 200)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/v2/messages")
        self.assertEqual(
            sent["body"],
            {"from": "+15550100000", "to": "+1234567890", "text": "plain sms"},
        )

    def test_gateway_health_reports_whatsapp_capability(self):
        status, payload = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(status, 200)
        self.assertIsNone(payload["whatsapp_from"])
        bridge.WHATSAPP_FROM = "+15550100000"
        status, payload = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(payload["whatsapp_from"], "+15550100000")

    def test_parse_destination_table(self):
        cases = [
            ("+1234567890", ("sms", "+1234567890")),
            ("whatsapp:+1234567890", ("whatsapp", "+1234567890")),
            ("whatsapp+1234567890", ("whatsapp", "+1234567890")),
            ("WhatsApp:+4915112345678", ("whatsapp", "+4915112345678")),
            ("whatsapp:", (None, "whatsapp:")),
            ("whatsapp:hello", (None, "whatsapp:hello")),
            ("whatsapp+not-a-number", (None, "whatsapp+not-a-number")),
        ]
        for raw, expected in cases:
            self.assertEqual(bridge.parse_destination(raw), expected, raw)

    # /gateway/fax — honest 503

    def test_gateway_fax_is_honest_503(self):
        status, payload = http(
            "POST",
            f"{self.base}/gateway/fax",
            b"",
            {"Authorization": f"Bearer {WEBPHONE_SECRET}"},
        )
        self.assertEqual(status, 503)
        self.assertIn("fax", payload["error"])

    # inbound: message.received → /hooks/message

    def telnyx_event(self, data):
        return http(
            "POST",
            f"{self.base}/telnyx/webhooks",
            json.dumps({"data": data}).encode(),
            {"Content-Type": "application/json"},
        )

    def test_inbound_message_forwarded(self):
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "in-1",
                    "from": {"phone_number": "+10987654321"},
                    "to": [{"phone_number": "+15550100000", "status": "received"}],
                    "text": "hello from telnyx",
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(len(StubUpstreamHandler.seen), 1)
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/hooks/message")
        self.assertEqual(sent["authorization"], f"Bearer {WEBPHONE_SECRET}")
        self.assertEqual(
            sent["body"],
            {
                "owner": "1000",
                "from": "+10987654321",
                "body": "hello from telnyx",
                "attachments": [],
            },
        )

    def test_inbound_forward_failure_answers_503_for_telnyx_retry(self):
        StubUpstreamHandler.stub_responses["/hooks/message"] = (
            500,
            {"error": "store down"},
        )
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {"id": "in-2", "from": "+10987654321", "text": "retry me"},
            }
        )
        self.assertEqual(status, 503)
        self.assertIn("retry", payload["error"])
        # one retry on 5xx, then give up
        self.assertEqual(len(StubUpstreamHandler.seen), 2)

    def test_inbound_without_secret_configured_answers_503(self):
        (bridge.CREDENTIALS_DIR / "webphone_secret").unlink()
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {"id": "in-3", "from": "+10987654321", "text": "no secret"},
            }
        )
        self.assertEqual(status, 503)
        self.assertIn("webphone_gateway_secret", payload["error"])

    # inbound: WhatsApp message.received → tagged /hooks/message

    def test_inbound_whatsapp_text_forwarded_with_thread_tag(self):
        # The Meta-style body object carries the text; the sender is
        # tagged 'whatsapp+<digits>' so the thread keys identically to
        # the outbound destination the owner types ('whatsapp:+…' →
        # sanitized 'whatsapp+…' inside webphone).
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-1",
                    "type": "WHATSAPP",
                    "from": {"phone_number": "+10987654321"},
                    "to": [{"phone_number": "+15550100000", "status": "received"}],
                    "body": {"type": "text", "text": {"body": "hello from whatsapp"}},
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(
            sent["body"],
            {
                "owner": "1000",
                "from": "whatsapp+10987654321",
                "body": "hello from whatsapp",
                "attachments": [],
            },
        )

    def test_inbound_whatsapp_lowercase_type_also_detected(self):
        status, _ = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-1b",
                    "type": "whatsapp",
                    "from": "+10987654321",
                    "body": {"type": "text", "text": {"body": "lowercase"}},
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(StubUpstreamHandler.seen[0]["body"]["from"], "whatsapp+10987654321")

    def test_inbound_whatsapp_media_and_caption_forwarded(self):
        from unittest import mock

        image = b"\xff\xd8\xff\xe0" + b"\x00" * 8
        with mock.patch.object(
            bridge, "fetch_media", return_value=("image/jpeg", image)
        ):
            status, payload = self.telnyx_event(
                {
                    "event_type": "message.received",
                    "payload": {
                        "id": "wa-2",
                        "type": "WHATSAPP",
                        "from": {"phone_number": "+10987654321"},
                        "body": {
                            "type": "image",
                            "image": {
                                "url": "https://media.example.com/x.jpg",
                                "mime_type": "image/jpeg",
                                "sha256": "…",
                                "caption": "the office",
                            },
                        },
                    },
                }
            )
        self.assertEqual((status, payload["ok"]), (200, True))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["body"], "the office")
        self.assertEqual(len(sent["body"]["attachments"]), 1)
        attachment = sent["body"]["attachments"][0]
        self.assertEqual(attachment["mime_type"], "image/jpeg")
        self.assertEqual(attachment["data_base64"], base64.b64encode(image).decode())

    def test_inbound_whatsapp_envelope_shape_forwarded(self):
        # The other documented shape: plain envelope text + media list
        # (like SMS) with type WHATSAPP — still tagged, still forwarded.
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-3",
                    "type": "WHATSAPP",
                    "from": {"phone_number": "+10987654321"},
                    "text": "envelope text",
                    "media": [{"url": "http://media.example.com/x.jpg"}],
                },
            }
        )
        self.assertEqual((status, payload["ok"]), (200, True))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["from"], "whatsapp+10987654321")
        self.assertEqual(sent["body"]["body"], "envelope text")
        self.assertEqual(sent["body"]["attachments"], [])  # non-https fails fast

    def test_inbound_whatsapp_location_rendered_as_text(self):
        status, _ = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-4",
                    "type": "WHATSAPP",
                    "from": "+10987654321",
                    "body": {
                        "type": "location",
                        "location": {
                            "latitude": "40.7128",
                            "longitude": "-74.0060",
                            "name": "Telnyx HQ",
                            "address": "311 W 43rd St",
                        },
                    },
                },
            }
        )
        self.assertEqual(status, 200)
        body = StubUpstreamHandler.seen[0]["body"]["body"]
        self.assertIn("[location]", body)
        self.assertIn("Telnyx HQ", body)
        self.assertIn("40.7128", body)

    def test_inbound_whatsapp_unsupported_kind_gets_placeholder(self):
        status, _ = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "wa-5",
                    "type": "WHATSAPP",
                    "from": "+10987654321",
                    "body": {"type": "order", "order": {"catalog_id": "x"}},
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            StubUpstreamHandler.seen[0]["body"]["body"], "[WhatsApp order message]"
        )

    def test_inbound_sms_still_untagged(self):
        # Explicit SMS typing must keep the bare E.164 sender — only
        # WHATSAPP-typed payloads get the thread tag.
        status, payload = self.telnyx_event(
            {
                "event_type": "message.received",
                "payload": {
                    "id": "in-4",
                    "type": "SMS",
                    "from": {"phone_number": "+10987654321"},
                    "text": "plain sms",
                },
            }
        )
        self.assertEqual((status, payload["ok"]), (200, True))
        self.assertEqual(StubUpstreamHandler.seen[0]["body"]["from"], "+10987654321")

    # inbound: status events → /hooks/message/status

    def finalized(self, status, errors=None):
        return {
            "event_type": "message.finalized",
            "payload": {
                "id": "out-42",
                "to": [
                    {
                        "phone_number": "+1234567890",
                        "status": status,
                        "errors": errors or [],
                    }
                ],
            },
        }

    def test_status_delivered_forwarded(self):
        status, payload = self.telnyx_event(self.finalized("delivered"))
        self.assertEqual((status, payload), (200, {"ok": True, "forwarded": True}))
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["path"], "/hooks/message/status")
        self.assertEqual(
            sent["body"], {"provider_ref": "out-42", "status": "delivered"}
        )

    def test_status_delivery_failed_forwarded_with_error(self):
        status, payload = self.telnyx_event(
            self.finalized(
                "delivery_failed", [{"detail": "invalid destination number"}]
            )
        )
        self.assertEqual(
            (status, payload["ok"], payload["forwarded"]), (200, True, True)
        )
        sent = StubUpstreamHandler.seen[0]
        self.assertEqual(sent["body"]["status"], "failed")
        self.assertEqual(sent["body"]["error"], "invalid destination number")

    def test_intermediate_status_logged_not_forwarded(self):
        status, payload = self.telnyx_event(self.finalized("sent"))
        self.assertEqual((status, payload), (200, {"ok": True, "forwarded": False}))
        self.assertEqual(StubUpstreamHandler.seen, [])

    # receiver behavior parity

    def test_unknown_event_logged_ok(self):
        status, payload = self.telnyx_event(
            {"event_type": "call.initiated", "payload": {"id": "x"}}
        )
        self.assertEqual((status, payload), (200, {"ok": True}))
        lines = bridge.LOG_FILE.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(
            json.loads(lines[-1])["body"]["data"]["event_type"], "call.initiated"
        )

    def test_receiver_health(self):
        status, payload = http("GET", f"{self.base}/telnyx/webhooks/health")
        self.assertEqual((status, payload), (200, {"ok": True}))

    def test_receiver_oversize_body_is_logged_not_silent(self):
        # 02-33 §f/11: read_body caps /telnyx/webhooks at 1 MiB and an
        # oversized event silently truncated → json-parse-fail → raw-string
        # log with no hint WHY. The cap trip must leave one bridge_log line.
        from unittest import mock

        declared = bridge.MAX_BODY + 4096
        request = urllib.request.Request(
            f"{self.base}/telnyx/webhooks", data=b"x" * declared, method="POST"
        )
        with mock.patch.object(bridge, "bridge_log") as logged:
            with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310 - stub/loopback server
                self.assertEqual(response.status, 200)
            events = [call.args[0] for call in logged.call_args_list]
            self.assertIn("webhook body over cap", events)
        # The truncated event still logs (raw string), as before.
        entry = json.loads(bridge.LOG_FILE.read_text().splitlines()[-1])
        self.assertIsInstance(entry["body"]["raw"], str)

    def test_recent_requires_token(self):
        status, payload = http("GET", f"{self.base}/telnyx/webhooks/recent")
        self.assertEqual(status, 403)
        status, payload = http(
            "GET",
            f"{self.base}/telnyx/webhooks/recent",
            headers={"Authorization": "Bearer receiver-token-0123456789"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["entries"], [])

    def test_gateway_health_reports_capability(self):
        status, payload = http("GET", f"{self.base}/gateway/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["webphone_secret"])
        self.assertTrue(payload["telnyx_api_key"])
        self.assertEqual(payload["sms_to_extension"], "1000")

    # honest limits + boundary observability (SUPERB error-excellence T05-T07)

    def test_gateway_message_oversize_declared_body_is_honest_422(self):
        # T06: a body over the 8 MiB read cap used to be silently TRUNCATED
        # and die as a "malformed multipart" 400 — a lie about the cause.
        # The Content-Length pre-check answers before reading a byte, so
        # the request lies about its size (declared 9 MiB, nothing sent).
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(f"{self.base}/gateway/message")
        sock = socket.create_connection((parsed.hostname, parsed.port), timeout=10)
        request = (
            "POST /gateway/message HTTP/1.1\r\n"
            f"Host: {parsed.hostname}\r\n"
            f"Authorization: Bearer {WEBPHONE_SECRET}\r\n"
            "Content-Type: multipart/form-data; boundary=x\r\n"
            f"Content-Length: {9 << 20}\r\n"
            "Connection: close\r\n\r\n"
        )
        sock.sendall(request.encode())
        response = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            response += chunk
        sock.close()
        status_line = response.split(b"\r\n", 1)[0]
        self.assertTrue(status_line.startswith(b"HTTP/1.1 422 "), status_line)
        payload = json.loads(response.split(b"\r\n\r\n", 1)[1])
        self.assertIn("1 MB", payload["error"])
        self.assertNotIn("malformed multipart", payload["error"])

    def test_gateway_message_heic_gets_the_iphone_fix_copy(self):
        # T07: HEIC is the iPhone camera default and previously sniffed as
        # video/mp4 (ftyp fallback) — staged as .mp4 and doomed at Telnyx.
        # It must name the phone fix, not the generic unsupported wall.
        heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 32
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "photo",
            },
            files=[("IMG_0001.HEIC", heic)],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("IMG_0001.HEIC", payload["error"])
        self.assertIn("Most Compatible", payload["error"])
        self.assertNotIn("unsupported type", payload["error"])

    def test_gateway_message_generic_unsupported_copy_stays(self):
        # The HEIC lane must not eat the generic unsupported-type answer.
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("notes.txt", b"plain text has no magic bytes")],
        )
        status, payload = http(
            "POST",
            f"{self.base}/gateway/message",
            body,
            {
                "Content-Type": content_type,
                "Authorization": f"Bearer {WEBPHONE_SECRET}",
            },
        )
        self.assertEqual(status, 422)
        self.assertIn("unsupported type", payload["error"])
        self.assertNotIn("Most Compatible", payload["error"])

    def test_staged_media_boundary_events_are_logged(self):
        # T05: staging and Telnyx's fetch of an outbound medium are the
        # two points where an MMS silently dies if nobody looks.
        from unittest import mock

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        body, content_type = multipart(
            {
                "kind": "message",
                "owner": "1000",
                "to": "+1234567890",
                "body": "see attachment",
            },
            files=[("photo.png", png)],
        )
        with mock.patch.object(bridge, "bridge_log") as logged:
            status, _ = http(
                "POST",
                f"{self.base}/gateway/message",
                body,
                {
                    "Content-Type": content_type,
                    "Authorization": f"Bearer {WEBPHONE_SECRET}",
                },
            )
            self.assertEqual(status, 200)
            with urllib.request.urlopen(  # nosec B310 - staged media on this host
                StubUpstreamHandler.seen[0]["body"]["media_urls"][0], timeout=10
            ) as response:
                self.assertEqual(response.status, 200)
            events = [call.args[0] for call in logged.call_args_list]
            self.assertIn("staged outbound mms media", events)
            self.assertIn("served staged mms media", events)

    def test_staged_media_miss_is_logged(self):
        from unittest import mock

        name = "a" * 22 + ".png"  # valid shape, never staged
        with mock.patch.object(bridge, "bridge_log") as logged:
            status, _ = http("GET", f"{self.base}/mms-media/{name}")
            self.assertEqual(status, 404)
            events = [call.args[0] for call in logged.call_args_list]
            self.assertIn("staged mms media miss", events)

    def test_inbound_media_fetch_failure_is_logged_and_text_forwards(self):
        # T05: a failed inbound media fetch is a PERMANENT loss of that
        # attachment (Telnyx URLs are ephemeral) — the text must still
        # forward and the loss must be visible to the operator.
        from unittest import mock

        with mock.patch.object(bridge, "bridge_log") as logged:
            status, payload = self.telnyx_event(
                {
                    "event_type": "message.received",
                    "payload": {
                        "id": "in-mms-1",
                        "from": {"phone_number": "+10987654321"},
                        "text": "photo incoming",
                        "media": [
                            {"url": "http://media.example.com/x.png"}
                        ],  # non-https fails instantly, no network
                    },
                }
            )
            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
            sent = StubUpstreamHandler.seen[0]
            self.assertEqual(sent["body"]["attachments"], [])
            self.assertEqual(sent["body"]["body"], "photo incoming")
            events = [call.args[0] for call in logged.call_args_list]
            self.assertIn("inbound mms media fetch failed", events)


if __name__ == "__main__":
    unittest.main()
