# Contracts for the supervised text-message agent (modules/telephony/
# text-agent.py): the credential-resolution order and the two FATAL
# branches, the per-contact state store (tail cap, kill-switch counter,
# draft lifecycle incl. TTL + supersede), the JSONL tailer (resume,
# copytruncate rotation, dedupe), the Gemini request/parse shapes
# against a stub Interactions server (fenced JSON, confidence clamping),
# the bridge sender (multipart + bearer, honest failure mapping), the
# autopilot mode matrix with the full safety stack (confidence, VIP,
# suppression, kill-switch, escalation, signature), missed-call
# detection over fake ESL events, the review API end to end (auth,
# approve/edit/discard, on-demand draft, translate, suppression,
# presence, memory), the briefing assembly + sendmail-style pipe, and
# the lens-context fallback. Stdlib only, like the service itself.

import importlib.util
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

AGENT_PATH = (
    Path(__file__).resolve().parents[1] / "modules" / "telephony" / "text-agent.py"
)

spec = importlib.util.spec_from_file_location("text_agent", AGENT_PATH)
assert spec is not None and spec.loader is not None, AGENT_PATH
text_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(text_agent)


class FakeGemini:
    """Scripted draft/translate stand-in for autopilot tests."""

    def __init__(self, drafts=None, translations=None):
        self.drafts = list(drafts or [])
        self.translations = list(translations or [])
        self.prompts = []

    def draft(self, prompt):
        self.prompts.append(prompt)
        if not self.drafts:
            return {"text": "stub reply", "en_gloss": "stub reply",
                    "language": "en", "confidence": 95}
        return self.drafts.pop(0)

    def translate(self, text, to_language, tone):
        self.translations.append((text, to_language, tone))
        return f"translated({text})"


class StubBridge:
    """Loopback /gateway/message stand-in with bearer auth."""

    def __init__(self, reply_status=200, reply_body=None, expect_secret="gw-secret"):
        self.requests = []
        self.reply_status = reply_status
        self.reply_body = reply_body or {"provider_ref": "ref-1"}
        self.expect_secret = expect_secret
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length).decode("utf-8", "replace")
                outer.requests.append(
                    {
                        "path": self.path,
                        "auth": self.headers.get("Authorization"),
                        "content_type": self.headers.get("Content-Type"),
                        "body": body,
                    }
                )
                authorized = self.headers.get("Authorization") == \
                    f"Bearer {outer.expect_secret}"
                status = outer.reply_status if authorized else 401
                payload = json.dumps(outer.reply_body if authorized else
                                     {"error": "bad secret"}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, fmt, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        self.httpd.shutdown()


def base_env(tmpdir, **overrides):
    env = {
        "HTTP_PORT": "0",
        "TEXTAGENT_STATE_DIR": str(tmpdir),
        "TEXTAGENT_MODE": "drafts",
        "TEXTAGENT_WEBHOOK_LOG": "",
        "TEXTAGENT_LENS_URL": "",
        "CREDENTIALS_DIRECTORY": "",
        "CREDENTIALS_DIR": "",
    }
    env.update({key: str(value) for key, value in overrides.items()})
    return env


def make_config(tmpdir, **overrides):
    with mock.patch.dict(os.environ, base_env(tmpdir, **overrides)):
        return text_agent.Config()


class StubGeminiServer:
    """Loopback Interactions-API stand-in: one scripted text reply."""

    def __init__(self, reply):
        outer = self
        outer.reply = reply
        outer.requests = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                outer.requests.append(
                    {
                        "key": self.headers.get("x-goog-api-key"),
                        "body": json.loads(self.rfile.read(length)),
                    }
                )
                payload = {
                    "output": {
                        "content": [{"type": "text", "text": outer.reply}]
                    }
                }
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()


class ConfigTests(unittest.TestCase):
    def test_credential_resolution_order(self):
        # $CREDENTIALS_DIRECTORY (the only variable systemd actually
        # exports) beats $CREDENTIALS_DIR beats the unit-path fallback —
        # the 2026-10-01 outage contract.
        with tempfile.TemporaryDirectory() as first, \
                tempfile.TemporaryDirectory() as second:
            Path(first, "shared_secret").write_text("from-credentials-dir")
            Path(second, "shared_secret").write_text("from-override")
            env = base_env(
                tempfile.mkdtemp(),
                CREDENTIALS_DIRECTORY=first,
                CREDENTIALS_DIR=second,
            )
            with mock.patch.dict(os.environ, env):
                self.assertEqual(
                    text_agent.Config().shared_secret, "from-credentials-dir"
                )
            # Empty primary falls through to the explicit override.
            env["CREDENTIALS_DIRECTORY"] = ""
            with mock.patch.dict(os.environ, env):
                self.assertEqual(
                    text_agent.Config().shared_secret, "from-override"
                )

    def test_placeholder_key_detected(self):
        with tempfile.TemporaryDirectory() as creds, \
                tempfile.TemporaryDirectory() as state:
            Path(creds, "gemini_key").write_text("PLACEHOLDER-REPLACE-ME")
            Path(creds, "system_prompt").write_text("brain")
            Path(creds, "shared_secret").write_text("secret")
            with mock.patch.dict(
                os.environ,
                base_env(state, CREDENTIALS_DIRECTORY=creds),
            ):
                config = text_agent.Config()
                self.assertTrue(config.api_key_placeholder)
                self.assertFalse(config.gateway_secret)

    def test_signature_substitutes_owner(self):
        config = make_config(tempfile.mkdtemp(), TEXTAGENT_OWNER_NAME="Lars")
        self.assertIn("Lars", config.signature())
        self.assertIn("STOP", config.signature())

    def test_empty_credentials_read_as_none(self):
        config = make_config(tempfile.mkdtemp())
        self.assertIsNone(config.shared_secret)
        self.assertIsNone(config.system_prompt)

    def test_after_hours_window(self):
        config = make_config(
            tempfile.mkdtemp(),
            TEXTAGENT_WORKING_START="09:00",
            TEXTAGENT_WORKING_END="18:00",
        )
        autopilot = text_agent.Autopilot(config, None, None, None, None, None)
        self.assertFalse(autopilot.after_hours(12 * 60))  # mid-day: working
        self.assertTrue(autopilot.after_hours(20 * 60))   # evening: after
        self.assertTrue(autopilot.after_hours(6 * 60))    # early: after
        # A window that wraps midnight stays honest in both directions.
        wrapping = make_config(
            tempfile.mkdtemp(),
            TEXTAGENT_WORKING_START="18:00",
            TEXTAGENT_WORKING_END="09:00",
        )
        wrapped = text_agent.Autopilot(wrapping, None, None, None, None, None)
        self.assertTrue(wrapped.after_hours(12 * 60))
        self.assertFalse(wrapped.after_hours(21 * 60))


class FatalBranchTests(unittest.TestCase):
    def test_missing_shared_secret_fatals(self):
        config = make_config(tempfile.mkdtemp())
        with mock.patch.object(text_agent, "Config", return_value=config):
            with self.assertRaises(SystemExit) as raised:
                text_agent.main()
            self.assertEqual(raised.exception.code, 2)

    def test_missing_system_prompt_fatals(self):
        with tempfile.TemporaryDirectory() as creds, \
                tempfile.TemporaryDirectory() as state:
            Path(creds, "shared_secret").write_text("secret")
            env = base_env(state, CREDENTIALS_DIRECTORY=creds)
            with mock.patch.dict(os.environ, env):
                config = text_agent.Config()
            self.assertIsNotNone(config.shared_secret)
            self.assertIsNone(config.system_prompt)
            with mock.patch.object(text_agent, "Config", return_value=config):
                with self.assertRaises(SystemExit) as raised:
                    text_agent.main()
                self.assertEqual(raised.exception.code, 2)


class StateStoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.state = text_agent.StateStore(self.dir)

    def test_conversation_tail_cap(self):
        for index in range(60):
            self.state.append_message(
                "4917012345678",
                {"ts": f"t{index}", "direction": "in", "text": f"m{index}"},
                tail=50,
            )
        conversation = self.state.conversation("4917012345678")
        self.assertEqual(len(conversation["messages"]), 50)
        self.assertEqual(conversation["messages"][0]["text"], "m10")

    def test_human_outbound_resets_kill_switch(self):
        self.state.mark_auto_sent("4917012345678", 3)
        self.state.mark_auto_sent("4917012345678", 3)
        frozen = self.state.mark_auto_sent("4917012345678", 3)
        self.assertIsNotNone(frozen)
        self.state.append_message(
            "4917012345678",
            {"ts": "t", "direction": "out", "text": "human reply",
             "by_ai": False},
        )
        conversation = self.state.conversation("4917012345678")
        self.assertIsNone(conversation["frozen"])
        self.assertEqual(conversation["consecutive_auto"], 0)

    def test_ai_outbound_does_not_reset(self):
        self.state.append_message(
            "4917012345678",
            {"ts": "t", "direction": "out", "text": "ai", "by_ai": True},
        )
        conversation = self.state.conversation("4917012345678")
        self.assertEqual(conversation["consecutive_auto"], 0)

    def test_draft_lifecycle_and_ttl_sweep(self):
        draft = self.state.create_draft(
            {"id": "d1", "contact": "4917012345678", "status": "pending",
             "created_at": text_agent.now_iso(), "text": "hi",
             "confidence": 90}
        )
        self.assertEqual([d["id"] for d in self.state.list_drafts()], ["d1"])
        path = Path(self.dir, "drafts", "d1.json")
        original_mtime = os.path.getmtime(path)
        os.utime(path, (original_mtime - 7200, original_mtime - 7200))
        flipped = self.state.sweep_expired_drafts(3600)
        self.assertEqual(flipped, 1)
        self.assertEqual(self.state.draft("d1")["status"], "expired")

    def test_suppression_roundtrip(self):
        self.state.suppress("4917012345678", "STOP", "STOP please")
        self.assertIn("4917012345678", self.state.suppression())
        self.assertTrue(self.state.unsuppress("4917012345678"))
        self.assertNotIn("4917012345678", self.state.suppression())
        self.assertFalse(self.state.unsuppress("4917012345678"))

    def test_preferences_learn_and_cap(self):
        for index in range(12):
            self.state.record_correction(
                "4917012345678", f"draft {index}", f"final {index}"
            )
        rules = self.state.preferences("4917012345678")["rules"]
        self.assertEqual(len(rules), 10)
        self.assertEqual(rules[-1]["approved"], "final 11")
        # identical text learns nothing
        self.assertIsNone(
            self.state.record_correction("4917012345678", "same", "same")
        )

    def test_memory_set_append(self):
        self.state.set_memory("4917012345678", ["first"])
        notes = self.state.memory("4917012345678")
        notes.append("second")
        self.state.set_memory("4917012345678", notes)
        self.assertEqual(self.state.memory("4917012345678"),
                         ["first", "second"])

    def test_resume_clears_freeze(self):
        self.state.freeze("4917012345678", "test")
        self.state.resume("4917012345678")
        self.assertIsNone(self.state.conversation("4917012345678")["frozen"])


class JsonlTailerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.state = text_agent.StateStore(self.dir)
        self.path = os.path.join(self.dir, "inbound.jsonl")
        self.events = []
        self.tailer = text_agent.JsonlTailer(
            self.path, self.state, self.events.append, poll_seconds=0.01
        )

    def write(self, records):
        with open(self.path, "a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record) + "\n")

    def test_resume_and_dedupe(self):
        self.write([{"id": "e1", "event_type": "message.received"}])
        self.tailer.poll_once()
        self.assertEqual(len(self.events), 1)
        # Second poll sees the same line: deduped, nothing new.
        self.tailer.poll_once()
        self.assertEqual(len(self.events), 1)
        self.write([{"id": "e2", "event_type": "message.received"},
                    {"id": "e1", "event_type": "message.received"}])
        self.tailer.poll_once()
        self.assertEqual(len(self.events), 2)
        # A fresh tailer (restart) resumes at the offset and dedupes by id.
        reborn = text_agent.JsonlTailer(
            self.path, self.state, self.events.append, poll_seconds=0.01
        )
        reborn.poll_once()
        self.assertEqual(len(self.events), 2)

    def test_copytruncate_rotation_resets(self):
        self.write([{"id": "e1"}])
        self.tailer.poll_once()
        # copytruncate: the writer truncates and refills the SAME file —
        # and a busy night can refill it PAST the old offset, so neither
        # size-shrink nor inode change fires. The first-line parse guard
        # catches the mid-line seek and re-reads from the top (dedupe
        # absorbs the overlap).
        os.remove(self.path)
        self.write([{"id": "evt-noticeably-longer-2"}])
        self.tailer.poll_once()
        self.assertEqual(
            sorted(event["id"] for event in self.events),
            ["e1", "evt-noticeably-longer-2"],
        )

    def test_truncated_and_refilled_past_offset(self):
        self.write([{"id": "e1"}])
        self.tailer.poll_once()
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"id": "a-far-longer-refill-1"}) + "\n")
            handle.write(json.dumps({"id": "a-far-longer-refill-2"}) + "\n")
        self.tailer.poll_once()
        self.assertEqual(
            sorted(event["id"] for event in self.events),
            ["a-far-longer-refill-1", "a-far-longer-refill-2"],
        )

    def test_malformed_lines_skipped(self):
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write("not json\n")
            handle.write(json.dumps({"id": "ok1"}) + "\n")
        self.tailer.poll_once()
        self.assertEqual(len(self.events), 1)


class ExtractJsonTests(unittest.TestCase):
    def test_plain_object(self):
        self.assertEqual(
            text_agent.extract_json_object('{"reply": "hi"}'),
            {"reply": "hi"},
        )

    def test_fenced_object_with_prose(self):
        self.assertEqual(
            text_agent.extract_json_object(
                'Sure!\n```json\n{"reply": "hi", "confidence": 88}\n```\ndone'
            ),
            {"reply": "hi", "confidence": 88},
        )

    def test_nested_braces_in_strings(self):
        self.assertEqual(
            text_agent.extract_json_object('{"reply": "use {braces} freely"}'),
            {"reply": "use {braces} freely"},
        )

    def test_no_object_raises(self):
        with self.assertRaises(text_agent.GeminiError):
            text_agent.extract_json_object("no json here")


class GeminiClientTests(unittest.TestCase):
    def setUp(self):
        self.server = StubGeminiServer(
            '```json\n{"reply": "Guten Tag", "en_gloss": "Good day", '
            '"language": "de", "confidence": 91}\n```'
        )

    def tearDown(self):
        self.server.stop()

    def client(self):
        config = make_config(
            tempfile.mkdtemp(),
            GEMINI_API_BASE=f"http://127.0.0.1:{self.server.port}",
        )
        config.api_key = "test-key"
        return text_agent.GeminiClient(config), config

    def test_draft_request_and_parse(self):
        client, config = self.client()
        with mock.patch.object(config, "system_prompt_text",
                               return_value="PERSONA"):
            result = client.draft("the prompt")
        self.assertEqual(result["text"], "Guten Tag")
        self.assertEqual(result["language"], "de")
        self.assertEqual(result["confidence"], 91)
        request = self.server.requests[0]
        self.assertEqual(request["key"], "test-key")
        self.assertIn("PERSONA", request["body"]["system_instruction"])
        self.assertIn("JSON", request["body"]["system_instruction"])
        self.assertEqual(request["body"]["store"], False)

    def test_confidence_clamped(self):
        self.server.reply = '{"reply": "hi", "confidence": 250}'
        client, _ = self.client()
        self.assertEqual(client.draft("p")["confidence"], 100)
        self.server.reply = '{"reply": "hi", "confidence": "bogus"}'
        self.assertEqual(client.draft("p")["confidence"], 0)

    def test_missing_reply_raises(self):
        self.server.reply = '{"en_gloss": "no reply field"}'
        client, _ = self.client()
        with self.assertRaises(text_agent.GeminiError):
            client.draft("p")


class BridgeSenderTests(unittest.TestCase):
    def test_send_posts_multipart_with_bearer(self):
        bridge = StubBridge()
        try:
            config = make_config(tempfile.mkdtemp(),
                                 TEXTAGENT_BRIDGE_URL=bridge.url)
            config.gateway_secret = "gw-secret"
            sender = text_agent.BridgeSender(config)
            reference = sender.send("4917012345678", "hello there")
            self.assertEqual(reference, "ref-1")
            request = bridge.requests[0]
            self.assertEqual(request["path"], "/gateway/message")
            self.assertEqual(request["auth"], "Bearer gw-secret")
            self.assertIn("multipart/form-data", request["content_type"])
            self.assertIn("+4917012345678", request["body"])
            self.assertIn("hello there", request["body"])
        finally:
            bridge.stop()

    def test_refusal_maps_to_gateway_error(self):
        bridge = StubBridge(reply_status=422,
                            reply_body={"error": "too big"})
        try:
            config = make_config(tempfile.mkdtemp(),
                                 TEXTAGENT_BRIDGE_URL=bridge.url)
            config.gateway_secret = "gw-secret"
            sender = text_agent.BridgeSender(config)
            with self.assertRaises(text_agent.GatewayError) as raised:
                sender.send("4917012345678", "x")
            self.assertEqual(raised.exception.status, 502)
            self.assertIn("422", str(raised.exception))
        finally:
            bridge.stop()

    def test_missing_secret_fails_closed_503(self):
        config = make_config(tempfile.mkdtemp(),
                             TEXTAGENT_BRIDGE_URL="http://127.0.0.1:1")
        config.gateway_secret = None
        with self.assertRaises(text_agent.GatewayError) as raised:
            text_agent.BridgeSender(config).send("4917012345678", "x")
        self.assertEqual(raised.exception.status, 503)


class AutopilotHarness(unittest.TestCase):
    """Shared fixture: real state + fake gemini + stub bridge."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.state = text_agent.StateStore(self.dir)
        self.gemini = FakeGemini()
        self.bridge = StubBridge()
        self.presence = text_agent.Presence(self.state)
        self.config = make_config(tempfile.mkdtemp())
        self.config.gateway_secret = "gw-secret"
        self.config.bridge_url = self.bridge.url
        # The FakeGemini stand-in replaces the HTTP client, so the harness
        # carries a configured-key posture (the fail-closed branch has its
        # own tests through the real client).
        self.config.api_key = "test-key"
        self.config.api_key_placeholder = False
        self.lens = text_agent.LensContext(self.config)
        self.autopilot = text_agent.Autopilot(
            self.config, self.state, self.gemini, text_agent.BridgeSender(
                self.config), self.lens, self.presence
        )

    def tearDown(self):
        self.bridge.stop()

    def inbound(self, contact="4917012345678", text="Wann kommst du?",
                message_id="m1"):
        # Production flow: the event glue records the message BEFORE the
        # draft trigger reads the history.
        self.state.append_message(contact, {
            "ts": text_agent.now_iso(), "direction": "in", "text": text,
            "message_id": message_id,
        })
        self.autopilot.handle_inbound(contact, text, message_id)


class AutopilotDraftsModeTests(AutopilotHarness):
    def test_drafts_mode_never_sends(self):
        self.inbound()
        drafts = self.state.list_drafts()
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["status"], "pending")
        self.assertEqual(self.bridge.requests, [])

    def test_off_mode_records_nothing(self):
        self.config.mode = "off"
        self.inbound()
        self.assertEqual(self.state.list_drafts(), [])
        self.assertEqual(self.gemini.prompts, [])

    def test_draft_carries_gloss_and_language(self):
        self.gemini.drafts = [{
            "text": "Morgen!", "en_gloss": "Tomorrow!",
            "language": "de", "confidence": 95,
        }]
        self.inbound()
        draft = self.state.list_drafts()[0]
        self.assertEqual(draft["en_gloss"], "Tomorrow!")
        self.assertEqual(draft["language"], "de")

    def test_newer_draft_supersedes_older(self):
        self.inbound(message_id="m1")
        self.inbound(message_id="m2")
        statuses = {d["id"]: d["status"] for d in
                    self.state.list_drafts(statuses=("pending", "superseded"))}
        self.assertEqual(sorted(statuses.values()),
                         ["pending", "superseded"])

    def test_prompt_contains_history_memory_preferences(self):
        self.state.set_memory("4917012345678", ["prefers mornings"])
        self.state.record_correction("4917012345678", "du", "Sie")
        self.inbound()
        prompt = self.gemini.prompts[0]
        self.assertIn("prefers mornings", prompt)
        self.assertIn("corrected to", prompt)
        self.assertIn("Wann kommst du?", prompt)


class AutopilotSafetyStackTests(AutopilotHarness):
    def setUp(self):
        super().setUp()
        self.config.mode = "full"
        self.config.confidence_threshold = 80

    def test_confident_draft_auto_sends_with_signature(self):
        self.inbound()
        self.assertEqual(len(self.bridge.requests), 1)
        body = self.bridge.requests[0]["body"]
        self.assertIn("STOP", body)
        draft = self.state.list_drafts(statuses=("sent",))[0]
        self.assertEqual(draft["sent_by"], "ai")
        conversation = self.state.conversation("4917012345678")
        self.assertEqual(conversation["consecutive_auto"], 1)

    def test_low_confidence_stays_pending(self):
        self.gemini.drafts = [{"text": "unsure reply", "en_gloss": "",
                               "language": "en", "confidence": 40}]
        self.inbound()
        self.assertEqual(len(self.bridge.requests), 0)
        self.assertEqual(self.state.list_drafts()[0]["status"], "pending")

    def test_vip_never_auto(self):
        self.config.vip_numbers = ["4917012345678"]
        self.inbound()
        self.assertEqual(len(self.bridge.requests), 0)
        self.assertEqual(self.state.list_drafts()[0]["status"], "pending")

    def test_stop_keyword_suppresses_and_blocks(self):
        self.inbound(text="STOP")
        self.assertIn("4917012345678", self.state.suppression())
        self.assertEqual(self.state.list_drafts(), [])
        self.inbound(text="hello?")
        self.assertEqual(self.state.list_drafts(), [])
        self.assertEqual(len(self.bridge.requests), 0)

    def test_polish_stop_keyword_normalized(self):
        self.inbound(text="Rezygnuję!")
        self.assertIn("4917012345678", self.state.suppression())

    def test_kill_switch_freezes_after_max_auto(self):
        self.config.max_auto_per_conversation = 2
        self.inbound(message_id="m1")
        self.inbound(message_id="m2")
        self.assertEqual(len(self.bridge.requests), 2)
        conversation = self.state.conversation("4917012345678")
        self.assertIsNotNone(conversation["frozen"])
        # Frozen: further inbound drafts nothing at all.
        self.inbound(message_id="m3")
        self.assertEqual(len(self.bridge.requests), 2)
        # Human resume + human outbound unfreezes.
        self.state.resume("4917012345678")
        self.inbound(message_id="m4")
        self.assertEqual(len(self.bridge.requests), 3)

    def test_escalation_pattern_freezes(self):
        self.autopilot.request_escalation_check(
            "4917012345678", "I want to talk to a real human please"
        )
        frozen = self.state.conversation("4917012345678")["frozen"]
        self.assertIsNotNone(frozen)
        self.assertIn("human", frozen)

    def test_gateway_failure_keeps_draft_pending(self):
        self.bridge.reply_status = 500
        self.bridge.reply_body = {"error": "boom"}
        self.inbound()
        draft = self.state.list_drafts(statuses=("pending",))[0]
        self.assertIn("bridge refused", draft["send_error"])


class AutopilotAfterHoursTests(AutopilotHarness):
    def setUp(self):
        super().setUp()
        self.config.mode = "after-hours"
        self.config.confidence_threshold = 80
        # Config parsed 09:00-18:00 into minutes at construction.

    def test_working_hours_owner_present_drafts_only(self):
        self.presence.touch_owner()
        with mock.patch.object(text_agent, "minutes_now", return_value=12 * 60):
            self.inbound()
        self.assertEqual(len(self.bridge.requests), 0)

    def test_working_hours_busy_owner_autos(self):
        self.presence.touch_owner()
        self.presence.channel_up("uuid-1")
        with mock.patch.object(text_agent, "minutes_now", return_value=12 * 60):
            self.inbound()
        self.assertEqual(len(self.bridge.requests), 1)

    def test_after_hours_autos_even_without_presence(self):
        with mock.patch.object(text_agent, "minutes_now", return_value=22 * 60):
            self.inbound()
        self.assertEqual(len(self.bridge.requests), 1)

    def test_vacation_flag_autos_during_day(self):
        self.state.set_presence_overrides(vacation=True)
        self.presence.touch_owner()
        with mock.patch.object(text_agent, "minutes_now", return_value=12 * 60):
            self.inbound()
        self.assertEqual(len(self.bridge.requests), 1)


class MissedCallTests(AutopilotHarness):
    def test_ringout_triggers_missed_call_draft(self):
        events = []
        listener = text_agent.EsIListener(
            self.config, self.presence,
            lambda caller, uuid: events.append(caller),
        )
        listener._handle({
            "Event-Name": "CHANNEL_CREATE",
            "Unique-ID": "call-1",
            "Call-Direction": "inbound",
            "Caller-Caller-ID-Number": "+4917012345678",
        })
        self.assertTrue(self.presence.snapshot()["busy"])
        listener._handle({"Event-Name": "CHANNEL_ANSWER", "Unique-ID": "call-1"})
        listener._handle({
            "Event-Name": "CHANNEL_HANGUP_COMPLETE", "Unique-ID": "call-1",
        })
        self.assertEqual(events, [])  # answered: not missed
        listener._handle({
            "Event-Name": "CHANNEL_CREATE",
            "Unique-ID": "call-2",
            "Call-Direction": "inbound",
            "Caller-Caller-ID-Number": "+491709999999",
        })
        listener._handle({
            "Event-Name": "CHANNEL_HANGUP_COMPLETE", "Unique-ID": "call-2",
        })
        self.assertEqual(events, ["491709999999"])
        self.assertFalse(self.presence.snapshot()["busy"])

    def test_missed_call_draft_mentions_ringout(self):
        self.autopilot.handle_missed_call("4917012345678", "call-9")
        prompt = self.gemini.prompts[0]
        self.assertIn("rang out", prompt)
        self.assertEqual(self.state.list_drafts()[0]["trigger"],
                         "missedcall:call-9")

    def test_transcript_enrichment_when_present(self):
        self.config.transcripts_dir = tempfile.mkdtemp()
        Path(self.config.transcripts_dir, "call-7.jsonl").write_text(
            json.dumps({"type": "caller", "text": "hallo?"}) + "\n" +
            json.dumps({"type": "agent", "text": "Guten Tag"}) + "\n"
        )
        self.autopilot.handle_missed_call("4917012345678", "call-7")
        self.assertIn("hallo?", self.gemini.prompts[0])

    def test_suppressed_caller_skipped(self):
        self.state.suppress("4917012345678", "STOP", "STOP")
        self.autopilot.handle_missed_call("4917012345678", "call-9")
        self.assertEqual(self.gemini.prompts, [])


class LensContextTests(unittest.TestCase):
    def test_timeline_filters_contact_newest_first(self):
        rows = [
            {"from_number": "+4917012345678", "to_number": "+1555",
             "started_at": "2026-10-12T10:00:00Z", "direction": "inbound",
             "duration_secs": 120},
            {"from_number": "+1555", "to_number": "+4917012345678",
             "started_at": "2026-10-11T09:00:00Z", "direction": "outbound",
             "duration_secs": 60},
            {"from_number": "+1111", "to_number": "+2222",
             "started_at": "2026-10-12T12:00:00Z", "direction": "inbound",
             "duration_secs": 5},
        ]

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = ("\n".join(json.dumps(row) for row in rows)).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            config = make_config(
                tempfile.mkdtemp(),
                TEXTAGENT_LENS_URL=f"http://127.0.0.1:{httpd.server_address[1]}",
            )
            lens = text_agent.LensContext(config)
            timeline = lens.timeline("4917012345678")
            self.assertEqual(len(timeline), 2)
            self.assertEqual(timeline[0]["started_at"],
                             "2026-10-12T10:00:00Z")
        finally:
            httpd.shutdown()

    def test_down_lens_degrades_to_empty(self):
        config = make_config(tempfile.mkdtemp(),
                             TEXTAGENT_LENS_URL="http://127.0.0.1:9")
        lens = text_agent.LensContext(config)
        self.assertEqual(lens.timeline("4917012345678"), [])


class ReviewApiTests(AutopilotHarness):
    def setUp(self):
        super().setUp()
        self.api = text_agent.ReviewApi(
            self.config, self.state, self.autopilot, self.presence,
            self.gemini
        )
        self.server = text_agent.serve(self.api, 0)
        self.port = self.server.server_address[1]
        self.config.shared_secret = "review-secret"

    def tearDown(self):
        self.server.shutdown()
        super().tearDown()

    def call(self, method, path, payload=None, authorize=True):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Authorization": "Bearer review-secret"} if authorize
            else {},
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_health_open_and_honest(self):
        status, payload = self.call("GET", "/health", authorize=False)
        self.assertEqual(status, 200)
        # The harness carries no Gemini key but a gateway secret — health
        # must report exactly that state, never a rosy lie.
        self.assertFalse(payload["api_key_configured"])
        self.assertTrue(payload["gateway_secret_configured"])
        self.assertEqual(payload["mode"], "drafts")
        self.assertFalse(payload["presence"]["esl_connected"])

    def test_auth_required(self):
        status, _ = self.call("GET", "/reviews", authorize=False)
        self.assertEqual(status, 401)

    def test_reviews_list_includes_presence_and_mode(self):
        self.inbound()
        status, payload = self.call("GET", "/reviews")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["drafts"]), 1)
        self.assertIn("presence", payload)
        self.assertEqual(payload["mode"], "drafts")

    def test_approve_sends_and_records(self):
        self.inbound()
        draft_id = self.state.list_drafts()[0]["id"]
        status, payload = self.call(
            "POST", f"/reviews/{draft_id}/approve"
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "sent")
        self.assertEqual(payload["sent_by"], "human")
        self.assertEqual(len(self.bridge.requests), 1)
        self.assertNotIn("STOP", self.bridge.requests[0]["body"])

    def test_approve_with_edit_learns_correction(self):
        self.inbound()
        draft_id = self.state.list_drafts()[0]["id"]
        status, payload = self.call(
            "POST", f"/reviews/{draft_id}/approve",
            {"text": "Morgen um 10!"},
        )
        self.assertEqual(status, 200)
        rules = self.state.preferences("4917012345678")["rules"]
        self.assertEqual(rules[-1]["approved"], "Morgen um 10!")

    def test_discard_and_double_approve_rejected(self):
        self.inbound()
        draft_id = self.state.list_drafts()[0]["id"]
        status, _ = self.call("POST", f"/reviews/{draft_id}/discard")
        self.assertEqual(status, 200)
        status, payload = self.call("POST", f"/reviews/{draft_id}/approve")
        self.assertEqual(status, 409)

    def test_ondemand_draft_and_translate(self):
        status, payload = self.call(
            "POST", "/draft", {"to": "+4917012345678"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "pending")
        status, payload = self.call(
            "POST", "/translate",
            {"text": "see you tomorrow", "to": "de", "tone": "formal"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload["text"], "translated(see you tomorrow)")

    def test_translate_fails_closed_without_key(self):
        self.config.api_key_placeholder = True
        status, payload = self.call(
            "POST", "/translate", {"text": "hi", "to": "de"},
        )
        self.assertEqual(status, 503)

    def test_suppression_surface(self):
        self.state.suppress("4917012345678", "STOP", "STOP")
        status, listing = self.call("GET", "/suppression")
        self.assertIn("4917012345678", listing)
        status, payload = self.call(
            "POST", "/suppression/4917012345678/reset"
        )
        self.assertEqual(status, 200)
        self.assertNotIn("4917012345678", self.state.suppression())

    def test_presence_toggle_and_conversation_view(self):
        status, payload = self.call("POST", "/presence", {"dnd": True})
        self.assertTrue(payload["overrides"]["dnd"])
        self.state.append_message("4917012345678", {
            "ts": text_agent.now_iso(), "direction": "in",
            "text": "Hallo?",
        })
        status, payload = self.call("GET", "/conversations/4917012345678")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["messages"]), 1)
        self.assertFalse(payload["suppressed"])

    def test_memory_surface(self):
        self.call("POST", "/conversations/4917012345678/memory",
                  {"append": "lives in Berlin"})
        status, payload = self.call("GET", "/conversations/4917012345678")
        self.assertEqual(payload["memory"], ["lives in Berlin"])

    def test_resume_surface(self):
        self.state.freeze("4917012345678", "test freeze")
        status, payload = self.call(
            "POST", "/conversations/4917012345678/resume"
        )
        self.assertEqual(status, 200)
        self.assertIsNone(self.state.conversation("4917012345678")["frozen"])

    def test_briefing_404_before_assembly(self):
        status, _ = self.call("GET", "/briefing/latest")
        self.assertEqual(status, 404)

    def test_gateway_down_keeps_draft_pending_via_api(self):
        self.bridge.reply_status = 503
        self.bridge.reply_body = {"error": "no key"}
        self.inbound()
        draft_id = self.state.list_drafts()[0]["id"]
        status, payload = self.call("POST", f"/reviews/{draft_id}/approve")
        self.assertEqual(status, 502)
        self.assertEqual(self.state.draft(draft_id)["status"], "pending")


class EventGlueTests(AutopilotHarness):
    def handler(self):
        env = dict(os.environ)
        env["TEXTAGENT_OWN_DID"] = "+15550100000"
        with mock.patch.dict(os.environ, env):
            return text_agent.make_event_handler(self.config, self.state,
                                                 self.autopilot)

    def test_message_received_drafts(self):
        self.handler()({
            "id": "evt-1",
            "event_type": "message.received",
            "data": {
                "id": "msg-1",
                "from": {"phone_number": "+4917012345678"},
                "text": "Hallo?",
            },
        })
        conversation = self.state.conversation("4917012345678")
        self.assertEqual(conversation["messages"][0]["direction"], "in")
        self.assertEqual(len(self.state.list_drafts()), 1)

    def test_own_ai_send_not_duplicated(self):
        handler = self.handler()
        self.inbound()
        draft = self.state.list_drafts(statuses=("sent", "pending"))[0]
        # Simulate the send having happened through _send_draft:
        self.state.update_draft(draft["id"], status="sent",
                                provider_ref="msg-out-1")
        self.state.append_message("4917012345678", {
            "ts": text_agent.now_iso(), "direction": "out",
            "text": "reply", "by_ai": True, "provider_ref": "msg-out-1",
        })
        handler({
            "id": "evt-2",
            "event_type": "message.sent",
            "data": {
                "id": "msg-out-1",
                "from": {"phone_number": "+15550100000"},
                "to": {"phone_number": "+4917012345678"},
                "text": "reply",
            },
        })
        conversation = self.state.conversation("4917012345678")
        outbound = [m for m in conversation["messages"]
                    if m["direction"] == "out"]
        self.assertEqual(len(outbound), 1)

    def test_human_outbound_recorded_once(self):
        handler = self.handler()
        event = {
            "id": "evt-3",
            "event_type": "message.sent",
            "data": {
                "id": "human-1",
                "from": {"phone_number": "+15550100000"},
                "to": {"phone_number": "+4917012345678"},
                "text": "ich rufe dich an",
            },
        }
        handler(event)
        handler(event)  # Telnyx retries: dedupe holds
        conversation = self.state.conversation("4917012345678")
        self.assertEqual(len(conversation["messages"]), 1)

    def test_foreign_outbound_ignored(self):
        handler = self.handler()
        handler({
            "id": "evt-4",
            "event_type": "message.sent",
            "data": {
                "id": "x-1",
                "from": {"phone_number": "+15559999999"},
                "to": {"phone_number": "+4917012345678"},
            },
        })
        self.assertEqual(self.state.conversation("4917012345678")["messages"],
                         [])


class BriefingTests(AutopilotHarness):
    def test_assemble_counts_and_needs_you(self):
        self.inbound()
        self.state.freeze("4917012345678", "needs a human")
        self.state.suppress("491709999999", "STOP", "STOP")
        briefing = text_agent.Briefing(self.config, self.state, self.autopilot)
        digest = briefing.assemble()
        self.assertEqual(digest["pending_drafts"], 1)
        self.assertEqual(digest["needs_human"], 1)
        self.assertEqual(digest["suppressed"], 1)
        self.assertIn("needs a human", digest["markdown"])
        latest = self.state._read(
            self.state._path("briefing", "latest.json"), {})
        self.assertEqual(latest["pending_drafts"], 1)

    def test_mailer_pipe_invoked_sendmail_style(self):
        script = Path(self.dir, "fake-mailer.sh")
        outbox = Path(self.dir, "outbox.txt")
        script.write_text(
            "#!/bin/sh\ncat >> " + str(outbox) + "\n"
        )
        script.chmod(0o755)
        self.config.mailer_command = str(script)
        self.config.briefing_from = "pbx@example.com"
        self.config.briefing_to = "owner@example.com"
        briefing = text_agent.Briefing(self.config, self.state, self.autopilot)
        digest = briefing.assemble()
        self.assertTrue(briefing.mail(digest))
        mailed = outbox.read_text()
        self.assertIn("To: owner@example.com", mailed)
        self.assertIn("Morning briefing", mailed)

    def test_mailer_failure_is_honest_not_fatal(self):
        self.config.mailer_command = "/nonexistent/mailer"
        self.config.briefing_from = "a@b.c"
        self.config.briefing_to = "d@e.f"
        briefing = text_agent.Briefing(self.config, self.state, self.autopilot)
        self.assertFalse(briefing.mail(briefing.assemble()))


class MultipartTests(unittest.TestCase):
    def test_encode_multipart_roundtrip_fields(self):
        body, content_type = text_agent.encode_multipart(
            {"to": "+4917012345678", "body": "line one\nline two"}
        )
        self.assertIn("boundary=", content_type)
        self.assertIn(b'name="to"', body)
        self.assertIn(b"+4917012345678", body)
        self.assertIn(b"line one", body)


if __name__ == "__main__":
    unittest.main()
