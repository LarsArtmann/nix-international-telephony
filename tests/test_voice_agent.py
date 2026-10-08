# Contracts for the Gemini AI voice agent (modules/telephony/
# voice-agent.py): WAV normalization, the shape-tolerant Gemini response
# walker, the request shapes the service sends, the ESL client against a
# fake event socket, and the call loop's decisions (fail-closed without
# a real API key, transfer on [ACTION: transfer] / DTMF 0, hangup on
# [ACTION: end], silence and turn caps) against stub collaborators.
# Stdlib only, like the service itself.

import base64
import importlib.util
import json
import os
import socket
import struct
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

AGENT_PATH = (
    Path(__file__).resolve().parents[1] / "modules" / "telephony" / "voice-agent.py"
)

spec = importlib.util.spec_from_file_location("voice_agent", AGENT_PATH)
assert spec is not None and spec.loader is not None, AGENT_PATH
voice_agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice_agent)


WAV_BYTES = b"RIFF" + struct.pack("<I", 36) + b"WAVE" + b"\x00" * 8


def wav_file(content, sample_rate=8000, audio_format=1, bits=16):
    header = voice_agent.wav_header(
        len(content) // (bits // 8), sample_rate, bits, audio_format
    )
    return header + content


class FakeGemini:
    """Scripted stand-in for GeminiClient inside Agent-loop tests."""

    def __init__(self, replies=None):
        self.replies = list(replies or [])
        self.calls = []

    def transcribe(self, wav_bytes):
        self.calls.append(("transcribe", wav_bytes[:4]))
        return self.replies.pop(0) if self.replies else "hello"

    def chat(self, system_prompt, turns):
        self.calls.append(("chat", system_prompt, tuple(turns)))
        text = self.replies.pop(0) if self.replies else "I can help."
        return voice_agent.GeminiClient._split_action(self, text)

    def speak(self, text, language=None):
        self.calls.append(("speak", text, language))
        return WAV_BYTES


class StubEsl:
    """Records the event-socket commands the agent issues and fakes the
    record app (writes a small WAV so the turn is non-empty)."""

    def __init__(self, record_bytes=8192):
        self.commands = []
        self.executions = []
        self.record_bytes = record_bytes

    def sendmsg_execute(self, uuid, app, arg, timeout=120, abort=None):
        self.executions.append((uuid, app, arg))
        if app == "record":
            path = arg.split()[0]
            with open(path, "wb") as handle:
                handle.write(wav_file(b"\x00" * self.record_bytes))

    def command(self, text):
        self.commands.append(text)
        return "+OK"


def agent_config(tmpdir, **overrides):
    env = {
        "ESL_HOST": "127.0.0.1",
        "ESL_PORT": "8021",
        "GEMINI_API_BASE": "http://gemini.test",
        "AGENT_GREETING": "Hello there",
        "AGENT_TRANSFER_DESTINATION": overrides.pop("transfer_destination", "2000"),
        "AGENT_MAX_TURNS": str(overrides.pop("max_turns", 20)),
        "AGENT_TURN_MAX_SECONDS": "10",
        "AGENT_MAX_CALL_SECONDS": "600",
        "AGENT_TURNS_DIR": os.path.join(tmpdir, "ai-turns"),
        "AGENT_TRANSCRIPTS_DIR": os.path.join(tmpdir, "transcripts"),
        "HTTP_PORT": "18070",
        "CREDENTIALS_DIR": str(tmpdir),
    }
    env.update(overrides)
    return env


def write_credential(tmpdir, name, content):
    with open(os.path.join(tmpdir, name), "w", encoding="utf-8") as handle:
        handle.write(content)


class CredentialsDirResolutionTest(unittest.TestCase):
    """systemd exports $CREDENTIALS_DIRECTORY (since v244) — it has never
    exported $CREDENTIALS_DIR. Reading the phantom name alone made every
    credential resolve as absent and the agent FATAL "esl_pass credential
    missing" (exit 2) on every start — the 2026-10-01 evening outage.
    Pin the resolution order: primary variable, legacy override, stable
    unit path."""

    def test_primary_systemd_variable_resolves(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_credential(tmpdir, "esl_pass", "sekret\n")
            write_credential(tmpdir, "system_prompt", "brain\n")
            env = agent_config(tmpdir)
            env["CREDENTIALS_DIR"] = ""
            env["CREDENTIALS_DIRECTORY"] = str(tmpdir)
            with mock.patch.dict(os.environ, env):
                config = voice_agent.Config()
        self.assertEqual(config.esl_password, "sekret")
        self.assertEqual(config.system_prompt, "brain")

    def test_primary_variable_wins_over_legacy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_credential(tmpdir, "esl_pass", "sekret\n")
            env = agent_config(tmpdir)
            env["CREDENTIALS_DIRECTORY"] = "/nonexistent-credentials"
            with mock.patch.dict(os.environ, env):
                config = voice_agent.Config()
        self.assertEqual(config.esl_password, "")

    def test_stable_unit_path_fallback(self):
        env = agent_config("/nonexistent-agent-config-tmpdir")
        env["CREDENTIALS_DIR"] = ""
        env["CREDENTIALS_DIRECTORY"] = ""
        with mock.patch.dict(os.environ, env):
            config = voice_agent.Config()
        self.assertEqual(config.creds_dir, "/run/credentials/telephony-agent.service")


def run_call(agent, call):
    thread = threading.Thread(target=agent._handle_call, args=(call,), daemon=True)
    thread.start()
    thread.join(timeout=10)
    return thread


class WavTest(unittest.TestCase):
    def test_riff_passthrough(self):
        self.assertEqual(voice_agent.ensure_wav(WAV_BYTES, "audio/wav"), WAV_BYTES)

    def test_l16_gets_a_header(self):
        payload = b"\x01\x02" * 50
        wav = voice_agent.ensure_wav(payload, "audio/l16;rate=16000")
        self.assertEqual(wav[:4], b"RIFF")
        self.assertEqual(struct.unpack("<H", wav[24:26])[0], 16000)
        self.assertEqual(wav[44:], payload)

    def test_mulaw_gets_an_eight_k_format7_header(self):
        payload = b"\xd5" * 30
        wav = voice_agent.ensure_wav(payload, "audio/mulaw")
        self.assertEqual(struct.unpack("<H", wav[20:22])[0], 7)
        self.assertEqual(struct.unpack("<I", wav[24:28])[0], 8000)
        self.assertEqual(wav[44:], payload)

    def test_header_sizes(self):
        header = voice_agent.wav_header(100, 8000)
        self.assertEqual(len(header), 44)
        self.assertEqual(struct.unpack("<I", header[40:44])[0], 200)
        self.assertEqual(struct.unpack("<I", header[28:32])[0], 16000)


class WalkerTest(unittest.TestCase):
    def test_interactions_text_shape(self):
        reply = {
            "output": [
                {"content": [{"type": "text", "text": "Answer one"}]},
                {"content": [{"type": "text", "text": "Answer two"}]},
            ]
        }
        self.assertEqual(voice_agent.walk_collect(reply, "text")[0][0], "Answer one")

    def test_interactions_steps_envelope_shape(self):
        # The documented CreateInteraction response: model output lives in
        # steps[].content[] with type-tagged content blocks.
        reply = {
            "steps": [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": "Answer one"}],
                },
                {
                    "type": "model_output",
                    "content": [
                        {
                            "type": "audio",
                            "data": "QUJD",
                            "mime_type": "audio/wav",
                            "sample_rate": 8000,
                        }
                    ],
                },
            ]
        }
        self.assertEqual(voice_agent.walk_collect(reply, "text")[0][0], "Answer one")
        self.assertEqual(
            voice_agent.walk_collect(reply, "audio")[0], ("QUJD", "audio/wav")
        )

    def test_generatecontent_inline_audio_shape(self):
        reply = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"inlineData": {"mimeType": "audio/wav", "data": "QUJD"}}
                        ]
                    }
                }
            ]
        }
        found = voice_agent.walk_collect(reply, "audio")
        self.assertEqual(found[0], ("QUJD", "audio/wav"))

    def test_audio_type_shape(self):
        reply = {
            "output": [
                {
                    "content": [
                        {"type": "audio", "data": "QUJD", "mime_type": "audio/wav"}
                    ]
                }
            ]
        }
        self.assertEqual(
            voice_agent.walk_collect(reply, "audio")[0], ("QUJD", "audio/wav")
        )

    def test_no_match_is_empty(self):
        self.assertEqual(voice_agent.walk_collect({"output": []}, "text"), [])


class ActionSplitTest(unittest.TestCase):
    def test_transfer_directive_is_stripped_and_detected(self):
        text, action = voice_agent.GeminiClient._split_action(
            self, "Let me get someone for you. [ACTION: transfer]"
        )
        self.assertEqual(action, "transfer")
        self.assertEqual(text, "Let me get someone for you.")

    def test_end_directive(self):
        text, action = voice_agent.GeminiClient._split_action(
            self, "Goodbye. [action: end]"
        )
        self.assertEqual(action, "end")
        self.assertEqual(text, "Goodbye.")

    def test_plain_reply_has_no_action(self):
        text, action = voice_agent.GeminiClient._split_action(self, "Sure, one moment.")
        self.assertIsNone(action)
        self.assertEqual(text, "Sure, one moment.")


class GeminiHttpTest(unittest.TestCase):
    """Request shapes against a real loopback HTTP server."""

    def setUp(self):
        self.requests = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                server.requests.append(
                    {
                        "path": self.path,
                        "key": self.headers.get("x-goog-api-key"),
                        "body": json.loads(self.rfile.read(length)),
                    }
                )
                body = json.dumps(server.next_reply).encode()
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

    def tearDown(self):
        self.httpd.shutdown()

    def client(self):
        with mock.patch.dict(
            os.environ,
            {
                "GEMINI_API_BASE": f"http://127.0.0.1:{self.port}",
                "GEMINI_LLM_MODEL": "gemini-3.8-flash",
                "GEMINI_TTS_MODEL": "gemini-3.8-flash-lite-tts",
                "GEMINI_VOICE": "Kore",
                "GEMINI_LANGUAGE": "en-US",
                "CREDENTIALS_DIR": "",
            },
        ):
            config = voice_agent.Config()
        config.api_key = "test-key"
        return voice_agent.GeminiClient(config)

    def test_transcribe_sends_audio_content_and_reads_text(self):
        self.next_reply = {
            "output": [{"content": [{"type": "text", "text": "  hello there "}]}]
        }
        transcript = self.client().transcribe(WAV_BYTES)
        self.assertEqual(transcript, "hello there")
        sent = self.requests[0]
        self.assertEqual(sent["path"], "/interactions")
        self.assertEqual(sent["key"], "test-key")
        self.assertEqual(sent["body"]["model"], "gemini-3.8-flash")
        step = sent["body"]["input"][0]
        self.assertEqual(step["type"], "user_input")
        content = step["content"]
        self.assertEqual(content[1]["type"], "audio")
        self.assertEqual(content[1]["mime_type"], "audio/wav")
        self.assertEqual(content[1]["sample_rate"], 8000)
        self.assertEqual(content[1]["channels"], 1)
        self.assertEqual(
            base64.b64decode(content[1]["data"]),
            WAV_BYTES,
        )
        self.assertNotIn("response_modalities", sent["body"])
        self.assertIs(sent["body"]["store"], False)

    def test_chat_builds_alternating_steps_and_parses_action(self):
        self.next_reply = {
            "output": [
                {
                    "content": [
                        {"type": "text", "text": "Connecting you. [ACTION: transfer]"}
                    ]
                }
            ]
        }
        text, action = self.client().chat(
            "be helpful",
            [("caller", "hi"), ("agent", "hello"), ("caller", "get me a human")],
        )
        self.assertEqual(action, "transfer")
        self.assertEqual(text, "Connecting you.")
        body = self.requests[0]["body"]
        steps = body["input"]
        self.assertIn("be helpful", body["system_instruction"])
        self.assertIn(voice_agent.SYSTEM_PREAMBLE, body["system_instruction"])
        self.assertEqual(
            [s["type"] for s in steps],
            ["user_input", "model_output", "user_input"],
        )
        self.assertIs(body["store"], False)

    def test_speak_requests_wav_eight_k_and_returns_wav(self):
        self.next_reply = {
            "output": [
                {
                    "content": [
                        {
                            "type": "audio",
                            "data": base64.b64encode(WAV_BYTES).decode(),
                            "mime_type": "audio/wav",
                        }
                    ]
                }
            ]
        }
        wav = self.client().speak("hello")
        self.assertEqual(wav, WAV_BYTES)
        body = self.requests[0]["body"]
        self.assertEqual(body["model"], "gemini-3.8-flash-lite-tts")
        self.assertEqual(body["input"][0]["type"], "user_input")
        self.assertEqual(body["response_format"]["type"], "audio")
        self.assertEqual(body["response_format"]["mime_type"], "audio/wav")
        self.assertEqual(body["response_format"]["sample_rate"], 8000)
        self.assertEqual(
            body["generation_config"]["speech_config"],
            [{"voice": "Kore", "language": "en-US"}],
        )
        self.assertIs(body["store"], False)

    def test_http_error_raises_gemini_error(self):
        self.next_reply = {}
        with mock.patch.object(voice_agent.urllib.request, "urlopen") as fake:
            fake.side_effect = voice_agent.urllib.error.HTTPError(
                "url", 503, "boom", {}, None
            )
            with self.assertRaises(voice_agent.GeminiError):
                self.client().speak("hi")

    def test_empty_response_raises(self):
        self.next_reply = {"output": []}
        with self.assertRaises(voice_agent.GeminiError):
            self.client().speak("hi")


class GoldenRequestBodyTest(GeminiHttpTest):
    """F72: the COMPLETE wire bodies as goldens. The field-by-field
    suites above catch wrong values; these catch shape drift — a renamed
    key, a dropped `store: false`, a changed response_format — that
    leaves every individual assertion green. When one of these fails,
    regenerate the golden DELIBERATELY (the API contract changed), never
    by reflex."""

    def test_transcribe_body_is_golden(self):
        self.next_reply = {
            "output": [{"content": [{"type": "text", "text": "hello"}]}]
        }
        self.client().transcribe(WAV_BYTES)
        self.assertEqual(
            self.requests[0]["body"],
            {
                "model": "gemini-3.8-flash",
                "input": [
                    {
                        "type": "user_input",
                        "content": [
                            {
                                "type": "text",
                                "text": "Transcribe this phone-audio utterance "
                                "verbatim. Reply with the transcript text only.",
                            },
                            {
                                "type": "audio",
                                "mime_type": "audio/wav",
                                "data": base64.b64encode(WAV_BYTES).decode(),
                                "sample_rate": 8000,
                                "channels": 1,
                            },
                        ],
                    }
                ],
                "store": False,
            },
        )

    def test_chat_body_is_golden(self):
        self.next_reply = {
            "output": [{"content": [{"type": "text", "text": "Hi."}]}]
        }
        self.client().chat("be helpful", [("caller", "hello")])
        self.assertEqual(
            self.requests[0]["body"],
            {
                "model": "gemini-3.8-flash",
                "input": [
                    {
                        "type": "user_input",
                        "content": [{"type": "text", "text": "hello"}],
                    }
                ],
                "system_instruction": f"{voice_agent.SYSTEM_PREAMBLE}\n\nbe helpful",
                "store": False,
            },
        )

    def test_speak_body_is_golden(self):
        self.next_reply = {
            "output": [
                {
                    "content": [
                        {
                            "type": "audio",
                            "data": base64.b64encode(WAV_BYTES).decode(),
                            "mime_type": "audio/wav",
                        }
                    ]
                }
            ]
        }
        self.client().speak("hello")
        self.assertEqual(
            self.requests[0]["body"],
            {
                "model": "gemini-3.8-flash-lite-tts",
                "input": [
                    {
                        "type": "user_input",
                        "content": [{"type": "text", "text": "hello"}],
                    }
                ],
                "response_format": {
                    "type": "audio",
                    "mime_type": "audio/wav",
                    "sample_rate": 8000,
                },
                "generation_config": {
                    "speech_config": [{"voice": "Kore", "language": "en-US"}]
                },
                "store": False,
            },
        )

    def test_speak_body_is_golden_in_the_mapped_language(self):
        self.next_reply = {
            "output": [
                {
                    "content": [
                        {
                            "type": "audio",
                            "data": base64.b64encode(WAV_BYTES).decode(),
                            "mime_type": "audio/wav",
                        }
                    ]
                }
            ]
        }
        self.client().speak("guten tag", "de-DE")
        self.assertEqual(
            self.requests[0]["body"]["generation_config"],
            {"speech_config": [{"voice": "Kore", "language": "de-DE"}]},
        )


class ConfigTest(unittest.TestCase):
    def test_placeholder_key_detection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_credential(tmpdir, "gemini_key", "PLACEHOLDER-OWNER-MUST-REPLACE")
            write_credential(tmpdir, "esl_pass", "pw")
            write_credential(tmpdir, "system_prompt", "be nice")
            with mock.patch.dict(os.environ, agent_config(tmpdir)):
                config = voice_agent.Config()
        self.assertTrue(config.api_key_placeholder)
        self.assertEqual(config.esl_password, "pw")
        self.assertEqual(config.system_prompt, "be nice")

    def test_real_key_and_env_password_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_credential(tmpdir, "gemini_key", "real-key")
            write_credential(tmpdir, "system_prompt", "be nice")
            env = agent_config(tmpdir)
            env.pop("CREDENTIALS_DIR", None)
            os.environ["CREDENTIALS_DIR"] = tmpdir
            env["ESL_PASSWORD"] = "inline-demo-pass"
            with mock.patch.dict(os.environ, env):
                config = voice_agent.Config()
            self.assertFalse(config.api_key_placeholder)
            self.assertEqual(config.esl_password, "inline-demo-pass")


class FakeEslServer(threading.Thread):
    """Minimal event-socket stand-in: auth, subscribe, api replies and
    CHANNEL_EXECUTE_COMPLETE emission for sendmsg executes."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.stop = threading.Event()

    def run(self):
        conn, _ = self.sock.accept()
        conn.sendall(b"Content-Type: auth/request\n\n")
        self._read_command(conn)
        conn.sendall(b"Content-Type: command/reply\nReply-Text: +OK accepted\n\n")
        while not self.stop.is_set():
            command = self._read_command(conn)
            if command is None:
                break
            if command.startswith(("auth ", "events ")):
                conn.sendall(b"Content-Type: command/reply\nReply-Text: +OK\n\n")
            elif command.startswith("api "):
                body = "+OK " + command[4:].strip()
                conn.sendall(
                    f"Content-Type: api/response\nContent-Length: {len(body)}\n\n".encode()
                    + body.encode()
                )
            elif command.startswith("sendmsg "):
                uuid = command.split()[1]
                body = (
                    f"Event-Name: CHANNEL_EXECUTE_COMPLETE\nUnique-ID: {uuid}\n"
                    "Application: playback\nApplication-Data: /tmp/x.wav\n"
                )
                conn.sendall(
                    b"Content-Type: command/reply\nReply-Text: +OK\n\n"
                    + f"Content-Type: text/event-plain\nContent-Length: {len(body)}\n\n".encode()
                    + body.encode()
                )

    def _read_command(self, conn):
        data = b""
        while not data.endswith(b"\n\n"):
            chunk = conn.recv(4096)
            if not chunk:
                return None
            data += chunk
        return data.decode().strip()

    def close(self):
        self.stop.set()
        try:
            socket.create_connection(("127.0.0.1", self.port), timeout=1).close()
        except OSError:
            pass
        self.sock.close()


class EslClientTest(unittest.TestCase):
    def test_auth_subscribe_command_and_execute(self):
        server = FakeEslServer()
        server.start()
        client = voice_agent.ESLClient("127.0.0.1", server.port, "secret")
        client.connect()
        self.assertTrue(client.connected.is_set())
        self.assertEqual(client.command("status"), "+OK status")
        done = client.sendmsg_execute("uuid-1", "playback", "/tmp/x.wav", timeout=5)
        self.assertEqual(done["Unique-ID"], "uuid-1")
        client.close()
        server.close()
        server.join(timeout=2)


class AgentLoopTest(unittest.TestCase):
    def make_agent(self, tmpdir, env_overrides=None, gemini=None):
        env = agent_config(tmpdir, **(env_overrides or {}))
        write_credential(tmpdir, "gemini_key", "real-key")
        write_credential(tmpdir, "esl_pass", "pw")
        write_credential(tmpdir, "system_prompt", "be helpful")
        with mock.patch.dict(os.environ, env):
            config = voice_agent.Config()
        agent = voice_agent.Agent(config, gemini or FakeGemini())
        agent.esl = StubEsl()
        agent.greeting_wav = WAV_BYTES
        agent.greeting_wavs = {None: WAV_BYTES}
        return agent

    def read_transcript(self, tmpdir, uuid):
        path = os.path.join(tmpdir, "transcripts", f"{uuid}.jsonl")
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def test_full_conversation_records_transcribes_answers_and_stores(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gemini = FakeGemini(
                [
                    "what city are you in?",
                    "We ship there. Anything else?",
                    "the airport, please",
                    "Sending you to the front desk. [ACTION: transfer]",
                ]
            )
            agent = self.make_agent(tmpdir, gemini=gemini)
            run_call(agent, voice_agent.CallState("uuid-full", agent.config))
            records = [app for _, app, _ in agent.esl.executions]
            self.assertEqual(records.count("record"), 2)
            self.assertEqual(records.count("playback"), 3)  # greeting + two replies
            transfer_commands = [
                c for c in agent.esl.commands if c.startswith("uuid_transfer")
            ]
            self.assertEqual(
                transfer_commands, ["uuid_transfer uuid-full 2000 XML default"]
            )
            self.assertEqual(agent.active, {})
            transcript = self.read_transcript(tmpdir, "uuid-full")
            self.assertEqual(transcript[0]["type"], "start")
            roles = [
                entry.get("role") for entry in transcript if entry["type"] == "turn"
            ]
            self.assertEqual(roles, ["caller", "agent", "caller", "agent"])
            self.assertEqual(transcript[-1]["reason"], "transferred")
            turn_files = os.listdir(os.path.join(tmpdir, "ai-turns"))
            self.assertEqual(
                turn_files, [], "per-turn WAVs must be deleted after transcription"
            )

    def test_agent_end_directive_hangs_up(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gemini = FakeGemini(["hello", "Goodbye now. [ACTION: end]"])
            agent = self.make_agent(tmpdir, gemini=gemini)
            run_call(agent, voice_agent.CallState("uuid-end", agent.config))
            self.assertIn("uuid_kill uuid-end normal_clearing", agent.esl.commands)
            transcript = self.read_transcript(tmpdir, "uuid-end")
            self.assertEqual(transcript[-1]["reason"], "agent_end")

    def test_placeholder_key_fails_closed_with_transfer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = agent_config(tmpdir)
            write_credential(tmpdir, "gemini_key", "PLACEHOLDER-OWNER-MUST-REPLACE")
            write_credential(tmpdir, "esl_pass", "pw")
            write_credential(tmpdir, "system_prompt", "be helpful")
            with mock.patch.dict(os.environ, env):
                config = voice_agent.Config()
            agent = voice_agent.Agent(config, FakeGemini())
            agent.esl = StubEsl()
            agent.greeting_wav = None
            run_call(agent, voice_agent.CallState("uuid-ph", agent.config))
            self.assertEqual(
                agent.esl.commands[-1], "uuid_transfer uuid-ph 2000 XML default"
            )
            self.assertEqual(
                agent.gemini.calls, [], "no Gemini call may happen without a key"
            )

    def test_three_silent_turns_end_the_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self.make_agent(tmpdir)
            agent.esl.record_bytes = 0  # record app produces nothing
            run_call(agent, voice_agent.CallState("uuid-silent", agent.config))
            self.assertIn("uuid_kill uuid-silent normal_clearing", agent.esl.commands)
            records = [app for _, app, _ in agent.esl.executions]
            self.assertEqual(records.count("record"), 3)
            api_calls = [
                c for c in agent.gemini.calls if c[0] in ("transcribe", "chat")
            ]
            self.assertEqual(api_calls, [], "silence must never reach the Gemini API")

    def test_turn_cap_stops_the_conversation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self.make_agent(tmpdir, env_overrides={"max_turns": 2})
            run_call(agent, voice_agent.CallState("uuid-cap", agent.config))
            records = [app for _, app, _ in agent.esl.executions]
            self.assertEqual(records.count("record"), 2)
            self.assertIn("uuid_kill uuid-cap normal_clearing", agent.esl.commands)

    def test_max_call_seconds_deadline_ends_the_call(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self.make_agent(
                tmpdir, env_overrides={"AGENT_MAX_CALL_SECONDS": "0"}
            )
            run_call(agent, voice_agent.CallState("uuid-deadline", agent.config))
            # The deadline is already past when the loop is first checked:
            # zero turns, the farewell, the hangup — never a hung channel.
            records = [app for _, app, _ in agent.esl.executions]
            self.assertEqual(records.count("record"), 0)
            self.assertIn(
                "uuid_kill uuid-deadline normal_clearing", agent.esl.commands
            )
            transcript = self.read_transcript(tmpdir, "uuid-deadline")
            self.assertEqual(transcript[-1]["reason"], "turn_or_time_limit")

    def test_two_concurrent_calls_run_independently(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Uniform script: ANY pop order ends the call on its first
            # chat — the shared FIFO is consumed nondeterministically
            # under threads, so per-call lines would be flaky.
            gemini = FakeGemini(["turning now. [ACTION: end]"] * 6)
            agent = self.make_agent(tmpdir, gemini=gemini)
            calls = [
                voice_agent.CallState(f"uuid-parallel-{n}", agent.config)
                for n in (1, 2)
            ]
            threads = [
                threading.Thread(target=agent._handle_call, args=(call,), daemon=True)
                for call in calls
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=10)
            self.assertEqual(agent.active, {})
            for call in calls:
                self.assertIn(
                    f"uuid_kill {call.uuid} normal_clearing", agent.esl.commands
                )
                transcript = self.read_transcript(tmpdir, call.uuid)
                self.assertEqual(transcript[-1]["reason"], "agent_end")

    def test_health_reports_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self.make_agent(tmpdir)
            agent.active["x"] = voice_agent.CallState("x", agent.config)
            agent.calls_total = 7
            health = agent.health()
            self.assertEqual(health["calls_active"], 1)
            self.assertEqual(health["calls_total"], 7)
            self.assertEqual(health["key"], "present")
            self.assertTrue(health["greeting_rendered"])

    def test_health_endpoint_serves_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self.make_agent(tmpdir)
            server = voice_agent.start_health_server(agent)
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{agent.config.http_port}/health", timeout=5
                ) as response:
                    body = json.loads(response.read())
                self.assertEqual(body["agent"], "telephony-agent")
            finally:
                server.shutdown()


class DispatchTest(unittest.TestCase):
    def test_park_dispatch_starts_handler_and_dtmf_sets_transfer(self):
        # The stub ESL serves record/playback instantly, so the call loop
        # can run to its turn cap and hang up BEFORE a DTMF dispatched
        # right after the park event reaches the handler — a real race
        # that made this spec flaky (~1 run in 5). Gate the first record
        # on the DTMF having been dispatched: the call is then provably
        # still active when the transfer request lands.
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AgentLoopTest.make_agent(unittest.TestCase(), tmpdir)
            in_first_record = threading.Event()
            release_record = threading.Event()

            class GatedEsl(StubEsl):
                def sendmsg_execute(self, uuid, app, arg, timeout=120, abort=None):
                    if app == "record" and not in_first_record.is_set():
                        in_first_record.set()
                        release_record.wait(timeout=5)
                    super().sendmsg_execute(
                        uuid, app, arg, timeout=timeout, abort=abort
                    )

            agent.esl = GatedEsl()
            agent._dispatch(
                {
                    "Event-Name": "CHANNEL_PARK",
                    "Unique-ID": "uuid-d",
                    "variable_ai_agent": "1",
                }
            )
            self.assertTrue(in_first_record.wait(timeout=5))
            agent._dispatch(
                {"Event-Name": "DTMF", "Unique-ID": "uuid-d", "DTMF-String": "0"}
            )
            release_record.set()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and "uuid-d" in agent.active:
                time.sleep(0.05)
            self.assertIn("uuid_transfer uuid-d 2000 XML default", agent.esl.commands)

    def test_non_agent_park_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AgentLoopTest.make_agent(unittest.TestCase(), tmpdir)
            agent._dispatch(
                {
                    "Event-Name": "CHANNEL_PARK",
                    "Unique-ID": "uuid-other",
                    "variable_ai_agent": "0",
                }
            )
            time.sleep(0.2)
            self.assertEqual(agent.active, {})

    def test_hangup_event_sets_the_call_flag(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = AgentLoopTest.make_agent(unittest.TestCase(), tmpdir)
            call = voice_agent.CallState("uuid-h", agent.config)
            agent.active["uuid-h"] = call
            agent._dispatch({"Event-Name": "CHANNEL_HANGUP", "Unique-ID": "uuid-h"})
            self.assertTrue(call.hungup.is_set())


if __name__ == "__main__":
    unittest.main()


class ReloadSpec(unittest.TestCase):
    """The SIGHUP body (Agent.reload_config): a failed boot render
    recovers without a restart, a refreshed prompt credential goes live,
    and the previous greeting survives a still-failing retry."""

    def _agent(self, tmpdir, flaky):
        write_credential(tmpdir, "gemini_key", "real-key")
        write_credential(tmpdir, "esl_pass", "pw")
        write_credential(tmpdir, "system_prompt", "first prompt")
        with mock.patch.dict(os.environ, agent_config(tmpdir)):
            config = voice_agent.Config()
        return voice_agent.Agent(config, flaky)

    def test_reload_recovers_a_failed_boot_render(self):
        class FlakyGemini(FakeGemini):
            def __init__(self):
                super().__init__()
                self.down = True

            def speak(self, text, language=None):
                if self.down:
                    raise voice_agent.GeminiError("HTTP 503: edge down")
                return super().speak(text, language)

        with tempfile.TemporaryDirectory() as tmpdir:
            flaky = FlakyGemini()
            agent = self._agent(tmpdir, flaky)
            # Retry sleeps make a failed render slow; patch them out.
            with mock.patch.object(voice_agent.time, "sleep"):
                self.assertFalse(agent.render_greeting())
            self.assertIsNone(agent.greeting_wav)

            flaky.down = False
            with mock.patch.object(voice_agent.time, "sleep"):
                agent.reload_config()
            self.assertIsNotNone(agent.greeting_wav, "reload must recover the greeting")
            self.assertTrue(agent.health()["greeting_rendered"])

    def test_reload_picks_up_a_refreshed_prompt_and_keeps_the_old_greeting_on_failure(self):
        class AlwaysDown(FakeGemini):
            def speak(self, text, language=None):
                raise voice_agent.GeminiError("HTTP 500: still down")

        with tempfile.TemporaryDirectory() as tmpdir:
            flaky = AlwaysDown()
            agent = self._agent(tmpdir, flaky)
            self.assertEqual(agent.config.system_prompt, "first prompt")

            rendered = {"kept": None}

            class OnceOk(FakeGemini):
                def speak(self, text, language=None):
                    if rendered["kept"] is None:
                        rendered["kept"] = True
                        return super().speak(text, language)
                    raise voice_agent.GeminiError("HTTP 500: down again")

            agent.gemini = OnceOk()
            self.assertTrue(agent.render_greeting())
            write_credential(tmpdir, "system_prompt", "second prompt")
            agent.gemini = flaky
            with mock.patch.object(voice_agent.time, "sleep"):
                agent.reload_config()
            self.assertEqual(
                agent.config.system_prompt,
                "second prompt",
                "a refreshed credential copy must go live on reload",
            )
            self.assertIsNotNone(
                agent.greeting_wav,
                "a failed reload render must keep the previous greeting",
            )


class BilingualByDidTest(unittest.TestCase):
    """agent.languageByDid/greetingByDid: a DID-mapped call speaks, replies
    and falls back in its own language; unmapped calls keep the default."""

    def make_agent(self, tmpdir, env_extra=None):
        env = agent_config(
            tmpdir,
            **{
                "AGENT_LANGUAGES_BY_DID": '{"+17195551234": "de-DE"}',
                "AGENT_GREETINGS_BY_DID": '{"+17195551234": "Guten Tag"}',
                **(env_extra or {}),
            },
        )
        write_credential(tmpdir, "gemini_key", "real-key")
        write_credential(tmpdir, "esl_pass", "pw")
        write_credential(tmpdir, "system_prompt", "be helpful")
        with mock.patch.dict(os.environ, env):
            config = voice_agent.Config()
        agent = voice_agent.Agent(config, FakeGemini())
        agent.esl = StubEsl()
        agent.greeting_wavs = {None: WAV_BYTES, "+17195551234": WAV_BYTES}
        agent.greeting_wav = WAV_BYTES
        return agent

    def test_did_mapped_language_localizes_speak_and_fallbacks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Plain reply, then the turn cap: the farewell must come out
            # German while an unmapped call stays English.
            agent = self.make_agent(tmpdir, env_extra={"AGENT_MAX_TURNS": "1"})
            run_call(agent, voice_agent.CallState("uuid-de", agent.config, did="+17195551234"))
            spoke = [(c[1], c[2]) for c in agent.gemini.calls if c[0] == "speak"]
            self.assertTrue(spoke, "agent must have spoken")
            for text, lang in spoke:
                self.assertEqual(lang, "de-DE")
            self.assertIn("Auf Wiederhoeren", spoke[-1][0])

            agent_en = self.make_agent(tmpdir, env_extra={"AGENT_MAX_TURNS": "1"})
            run_call(agent_en, voice_agent.CallState("uuid-en", agent_en.config))
            spoke_en = [
                (c[1], c[2]) for c in agent_en.gemini.calls if c[0] == "speak"
            ]
            self.assertEqual(spoke_en[-1][1], "en-US")
            self.assertIn("Goodbye", spoke_en[-1][0])

    def test_did_mapped_prompt_carries_the_language_directive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self.make_agent(tmpdir, env_extra={"AGENT_MAX_TURNS": "1"})
            run_call(agent, voice_agent.CallState("uuid-de2", agent.config, did="+17195551234"))
            chats = [c for c in agent.gemini.calls if c[0] == "chat"]
            self.assertEqual(len(chats), 1)
            self.assertIn("Always hold this conversation in de-DE", chats[0][1])

            agent_plain = self.make_agent(tmpdir, env_extra={"AGENT_MAX_TURNS": "1"})
            run_call(
                agent_plain, voice_agent.CallState("uuid-plain", agent_plain.config)
            )
            chats_plain = [c for c in agent_plain.gemini.calls if c[0] == "chat"]
            self.assertEqual(chats_plain[0][1], agent_plain.config.system_prompt)

    def test_render_greeting_renders_each_did_entry_in_its_language(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self.make_agent(tmpdir)
            self.assertTrue(agent.render_greeting())
            speak_calls = [
                (c[1], c[2]) for c in agent.gemini.calls if c[0] == "speak"
            ]
            self.assertEqual(
                speak_calls,
                [
                    ("Hello there", "en-US"),
                    ("Guten Tag", "de-DE"),
                ],
            )
            self.assertEqual(agent.greeting_wavs["+17195551234"], WAV_BYTES)
            self.assertEqual(agent.greeting_wav, WAV_BYTES)

    def test_dispatch_reads_the_did_channel_variables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = self.make_agent(tmpdir)
            agent._dispatch(
                {
                    "Event-Name": "CHANNEL_PARK",
                    "Unique-ID": "uuid-var",
                    "variable_ai_agent": "1",
                    "variable_ai_agent_did": "+17195551234",
                    "variable_ai_agent_lang": "fr-FR",
                }
            )
            call = agent.active["uuid-var"]
            self.assertEqual(call.did, "+17195551234")
            # The explicit channel variable outranks the DID mapping.
            self.assertEqual(call.language, "fr-FR")
            call.hungup.set()
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and "uuid-var" in agent.active:
                time.sleep(0.02)

    def test_malformed_mapping_env_degrades_to_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = agent_config(
                tmpdir, **{"AGENT_LANGUAGES_BY_DID": "not json at all"}
            )
            write_credential(tmpdir, "gemini_key", "real-key")
            write_credential(tmpdir, "esl_pass", "pw")
            write_credential(tmpdir, "system_prompt", "be helpful")
            with mock.patch.dict(os.environ, env):
                config = voice_agent.Config()
            self.assertEqual(config.languages_by_did, {})



class WalkCollectMatrixTest(unittest.TestCase):
    """F87: the shape-tolerant reader over a matrix of envelope shapes —
    steps/content nesting, bare lists, camelCase and snake_case mimeType,
    inlineData blocks, and the degenerate inputs (None, scalars, empty)."""

    def test_text_matrix(self):
        wc = voice_agent.walk_collect
        for obj, want in [
            (None, []),
            (42, []),
            ("text", []),
            ([], []),
            ({}, []),
            ([{"type": "text", "text": "a"}], [("a", None)]),
            ({"steps": [{"content": [{"type": "text", "text": "hi"}]}]}, [("hi", None)]),
            # Empty payloads are skipped, not collected as (None, mime).
            ([{"type": "text", "text": ""}], []),
            ([{"type": "text"}], []),
        ]:
            self.assertEqual(wc(obj, "text"), want, f"input: {obj!r}")

    def test_audio_matrix(self):
        wc = voice_agent.walk_collect
        for obj, want in [
            (
                [{"type": "audio", "data": "QUJD", "mime_type": "audio/wav"}],
                [("QUJD", "audio/wav")],
            ),
            (
                [{"type": "audio", "data": "QUJD", "mimeType": "audio/wav"}],
                [("QUJD", "audio/wav")],
            ),
            (
                {"inlineData": {"data": "REM=", "mimeType": "audio/wav"}},
                [("REM=", "audio/wav")],
            ),
            (
                {"inline_data": {"data": "REM=", "mime_type": "audio/wav"}},
                [("REM=", "audio/wav")],
            ),
        ]:
            self.assertEqual(wc(obj, "audio"), want, f"input: {obj!r}")

    def test_execute_timeout_message_names_app_and_uuid(self):
        """F88: a stuck application must fail LOUDLY — the TimeoutError
        names the app and the channel, so the call handler's log line is
        diagnosable without a journal dive."""
        client = voice_agent.ESLClient.__new__(voice_agent.ESLClient)
        sent = []

        client._register_execute_waiter = lambda matches: voice_agent.ExecuteWaiter(
            matches
        )
        client._clear_execute_waiter = lambda entry: None
        client._send_raw = sent.append

        with self.assertRaises(TimeoutError) as raised:
            client.sendmsg_execute("uuid-stuck", "playback", "/tmp/x.wav", timeout=0)

        self.assertIn("playback", str(raised.exception))
        self.assertIn("uuid-stuck", str(raised.exception))
        self.assertTrue(any("sendmsg uuid-stuck" in str(s) for s in sent))
