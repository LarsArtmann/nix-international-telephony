# Behavior specs (BDD) + end-to-end coverage for the Gemini voice agent.
#
# Why not Ginkgo/Gomega: the agent is a stdlib-Python service
# (modules/telephony/voice-agent.py), not a Go package, so the Go BDD
# stack does not apply. This suite keeps the BDD *intent* — every spec
# names an observable, caller-facing behavior ("the caller is greeted",
# "the model escalates to a human and the call transfers") and asserts
# the outcome a user would notice, never an internal step.
#
# Two layers live here:
#
#   EndToEndCallSpec  drives the REAL service over the REAL protocols: a
#                     real ESLClient socket against a scripted event-socket
#                     peer, a real GeminiClient HTTP call against a stub
#                     API, and the real Agent.run_forever() loop. This is
#                     the layer the contract tests in test_voice_agent.py
#                     deliberately mock out — it is what catches wiring
#                     regressions (framing, subscription, execute
#                     completion, transfer command, transcript writing)
#                     that unit stubs cannot.
#
#   EntrypointSpec    runs the real `main()` in a subprocess to pin the
#                     two FATAL credential branches (exit 2), including
#                     the empty-file-on-disk variant.
#
# Stdlib only, like the service itself.
import base64
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.test_voice_agent import WAV_BYTES, voice_agent, wav_file, write_credential

AGENT_PATH = (
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    + "/modules/telephony/voice-agent.py"
)


class FakeGeminiHttp(threading.Thread):
    """A real loopback HTTP stand-in for the Gemini API.

    Answers by inspecting the request body the way the API contract
    distinguishes the three calls: a response_format means text-to-speech
    (reply with audio), an audio input block means transcription (reply
    with the caller's words), anything else is the chat turn (reply with
    the scripted answer, which may carry an [ACTION: ...] directive)."""

    def __init__(self, transcript="I need to speak with a person", chat_replies=None):
        super().__init__(daemon=True)
        self.transcript = transcript
        self.chat_replies = list(
            chat_replies if chat_replies is not None else ["I can help with that."]
        )
        self.requests = []
        harness = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length))
                harness.requests.append(
                    {"path": self.path, "body": body}
                )
                payload = harness.reply_for(body)
                raw = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, fmt, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]

    @property
    def base(self):
        return f"http://127.0.0.1:{self.port}"

    def reply_for(self, body):
        if "response_format" in body:
            return {
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
        text = None
        for step in body.get("input", []):
            for block in step.get("content", []):
                if isinstance(block, dict) and block.get("type") == "audio":
                    text = self.transcript
        if text is None:
            text = self.chat_replies.pop(0) if self.chat_replies else "I can help."
        return {"output": [{"content": [{"type": "text", "text": text}]}]}

    def run(self):
        self.httpd.serve_forever()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class EslHarness(threading.Thread):
    """A real event-socket peer for the agent.

    Speaks the plain Content-Type framing FreeSWITCH uses, feeds
    scripted events, answers `api` commands and turns every `sendmsg
    <uuid>` execute into the matching CHANNEL_EXECUTE_COMPLETE — writing
    a small WAV for `record` so utterance turns are non-empty. An
    optional record gate holds the first record completion until the
    test releases it, which makes DTMF timing deterministic."""

    def __init__(self, record_bytes=8192):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.port = self.sock.getsockname()[1]
        self.sock.listen(1)
        self.record_bytes = record_bytes
        self.executions = []
        self.api_commands = []
        self.ready = threading.Event()
        self.first_record = threading.Event()
        self.record_gate = None
        self._conn = None
        self._send_lock = threading.Lock()
        self._stop = threading.Event()

    # -- outbound framing

    def _send(self, payload):
        with self._send_lock:
            if self._conn:
                self._conn.sendall(payload)

    def _reply_command(self, text):
        self._send(f"Content-Type: command/reply\nReply-Text: {text}\n\n".encode())

    def _reply_api(self, text):
        body = ("+OK " + text).encode()
        self._send(
            f"Content-Type: api/response\nContent-Length: {len(body)}\n\n".encode() + body
        )

    def send_event(self, fields):
        body = "".join(f"{key}: {value}\n" for key, value in fields.items()).encode()
        self._send(
            f"Content-Type: text/event-plain\nContent-Length: {len(body)}\n\n".encode()
            + body
        )

    # -- inbound

    def _read_command(self):
        data = b""
        while not data.endswith(b"\n\n"):
            chunk = self._conn.recv(4096)
            if not chunk:
                return None
            data += chunk
        return data.decode("utf-8", "replace").strip()

    def _handle_sendmsg(self, command):
        lines = command.split("\n")
        uuid = lines[0].split()[1]
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        app = headers.get("execute-app-name", "")
        arg = headers.get("execute-app-arg", "")
        self.executions.append((uuid, app, arg))
        if app == "record":
            path = arg.split()[0]
            with open(path, "wb") as handle:
                handle.write(wav_file(b"\x00" * self.record_bytes))
        self._reply_command("+OK")
        if app == "record":
            self.first_record.set()
            if self.record_gate is not None:
                self.record_gate.wait(timeout=5)
        self.send_event(
            {
                "Event-Name": "CHANNEL_EXECUTE_COMPLETE",
                "Unique-ID": uuid,
                "Application": app,
                "Application-Data": arg,
            }
        )

    def run(self):
        try:
            self._conn, _ = self.sock.accept()
        except OSError:
            return
        self._send(b"Content-Type: auth/request\n\n")
        self._read_command()  # auth
        self._reply_command("+OK accepted")
        while not self._stop.is_set():
            command = self._read_command()
            if command is None:
                break
            if command.startswith("events "):
                self._reply_command("+OK")
                self.ready.set()
            elif command.startswith("auth "):
                self._reply_command("+OK accepted")
            elif command.startswith("api "):
                text = command[4:].strip()
                self.api_commands.append(text)
                self._reply_api(text)
            elif command.startswith("sendmsg "):
                self._handle_sendmsg(command)

    def await_api(self, predicate, timeout=10):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            match = next((c for c in self.api_commands if predicate(c)), None)
            if match is not None:
                return match
            time.sleep(0.02)
        return None

    def close(self):
        self._stop.set()
        try:
            if self._conn:
                self._conn.close()
        except OSError:
            pass
        self.sock.close()


def agent_env(tmpdir, esl_port, gemini_base, **overrides):
    env = {
        "ESL_HOST": "127.0.0.1",
        "ESL_PORT": str(esl_port),
        "GEMINI_API_BASE": gemini_base,
        "GEMINI_LLM_MODEL": "gemini-3.8-flash",
        "GEMINI_TTS_MODEL": "gemini-3.8-flash-lite-tts",
        "GEMINI_VOICE": "Kore",
        "GEMINI_LANGUAGE": "en-US",
        "AGENT_GREETING": "Hello there",
        "AGENT_TRANSFER_DESTINATION": "2000",
        "AGENT_MAX_TURNS": "20",
        "AGENT_TURN_MAX_SECONDS": "10",
        "AGENT_MAX_CALL_SECONDS": "600",
        "AGENT_TURNS_DIR": os.path.join(tmpdir, "ai-turns"),
        "AGENT_TRANSCRIPTS_DIR": os.path.join(tmpdir, "transcripts"),
        "HTTP_PORT": "18071",
        "CREDENTIALS_DIRECTORY": tmpdir,
        "CREDENTIALS_DIR": "",
    }
    env.update(overrides)
    return env


class EndToEndCallSpec(unittest.TestCase):
    """Real-socket, real-HTTP specs for one inbound call lifecycle.

    Given a running agent over a live event socket and a stub Gemini API,
    when a caller's channel is parked with ai_agent=1, the specs assert
    the caller-visible outcome: a greeting, an answer, and how the call
    ends (transfer to a human, or the model's goodbye)."""

    def _boot(self, tmpdir, gemini_http, esl, gemini_key="real-key", **env_overrides):
        write_credential(tmpdir, "gemini_key", gemini_key)
        write_credential(tmpdir, "esl_pass", "pw")
        write_credential(tmpdir, "system_prompt", "be helpful")
        env = agent_env(tmpdir, esl.port, gemini_http.base, **env_overrides)
        previous = dict(os.environ)
        os.environ.update(env)
        try:
            config = voice_agent.Config()
        finally:
            os.environ.clear()
            os.environ.update(previous)
        agent = voice_agent.Agent(config, voice_agent.GeminiClient(config))
        agent.render_greeting()
        threading.Thread(target=agent.run_forever, daemon=True).start()
        self.assertTrue(esl.ready.wait(timeout=5), "agent never subscribed to events")
        return agent

    def _transcript(self, tmpdir, uuid):
        path = os.path.join(tmpdir, "transcripts", f"{uuid}.jsonl")
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle]

    def test_when_the_model_asks_for_a_human_the_call_transfers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gemini = FakeGeminiHttp(
                transcript="I need to reach support",
                chat_replies=["One moment, connecting you. [ACTION: transfer]"],
            )
            gemini.start()
            esl = EslHarness()
            esl.start()
            try:
                self._boot(tmpdir, gemini, esl)
                esl.send_event(
                    {
                        "Event-Name": "CHANNEL_PARK",
                        "Unique-ID": "uuid-e2e",
                        "variable_ai_agent": "1",
                    }
                )
                transfer = esl.await_api(
                    lambda c: c.startswith("uuid_transfer uuid-e2e"), timeout=15
                )
                self.assertIsNotNone(transfer, "the call never transferred")
                self.assertEqual(transfer, "uuid_transfer uuid-e2e 2000 XML default")
                apps = [app for _, app, _ in esl.executions]
                self.assertGreaterEqual(apps.count("record"), 1)
                self.assertGreaterEqual(apps.count("playback"), 2)  # greeting + reply
                transcript = self._transcript(tmpdir, "uuid-e2e")
                self.assertEqual(transcript[0]["type"], "start")
                roles = [
                    entry["role"] for entry in transcript if entry["type"] == "turn"
                ]
                self.assertEqual(roles, ["caller", "agent"])
                self.assertEqual(transcript[-1]["reason"], "transferred")
            finally:
                esl.close()
                gemini.close()

    def test_when_the_caller_presses_zero_the_call_transfers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gemini = FakeGeminiHttp(chat_replies=["Sure, I can help."] * 20)
            gemini.start()
            esl = EslHarness()
            esl.record_gate = threading.Event()
            esl.start()
            try:
                self._boot(tmpdir, gemini, esl)
                esl.send_event(
                    {
                        "Event-Name": "CHANNEL_PARK",
                        "Unique-ID": "uuid-dtmf",
                        "variable_ai_agent": "1",
                    }
                )
                # The handler is provably blocked inside its first record,
                # so the call is still active when the 0 lands.
                self.assertTrue(esl.first_record.wait(timeout=10))
                esl.send_event(
                    {
                        "Event-Name": "DTMF",
                        "Unique-ID": "uuid-dtmf",
                        "DTMF-Digit": "0",
                    }
                )
                esl.record_gate.set()
                transfer = esl.await_api(
                    lambda c: c.startswith("uuid_transfer uuid-dtmf"), timeout=15
                )
                self.assertIsNotNone(transfer, "DTMF 0 did not transfer the call")
                self.assertEqual(transfer, "uuid_transfer uuid-dtmf 2000 XML default")
            finally:
                esl.close()
                gemini.close()

    def test_when_the_agent_is_unconfigured_the_call_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gemini = FakeGeminiHttp()
            gemini.start()
            esl = EslHarness()
            esl.start()
            try:
                self._boot(
                    tmpdir,
                    gemini,
                    esl,
                    gemini_key="PLACEHOLDER-OWNER-MUST-REPLACE",
                )
                esl.send_event(
                    {
                        "Event-Name": "CHANNEL_PARK",
                        "Unique-ID": "uuid-ph",
                        "variable_ai_agent": "1",
                    }
                )
                transfer = esl.await_api(
                    lambda c: c.startswith("uuid_transfer uuid-ph"), timeout=15
                )
                self.assertIsNotNone(transfer, "fail-closed call did not transfer")
                self.assertEqual(gemini.requests, [], "no Gemini call without a key")
                transcript = self._transcript(tmpdir, "uuid-ph")
                self.assertEqual(transcript[-1]["reason"], "transferred_unconfigured")
            finally:
                esl.close()
                gemini.close()

    def test_park_without_the_agent_flag_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gemini = FakeGeminiHttp()
            gemini.start()
            esl = EslHarness()
            esl.start()
            try:
                self._boot(tmpdir, gemini, esl)
                # Boot renders the greeting (one legitimate API call); the
                # ignored park must not add another.
                baseline = len(gemini.requests)
                esl.send_event(
                    {
                        "Event-Name": "CHANNEL_PARK",
                        "Unique-ID": "uuid-other",
                        "variable_ai_agent": "0",
                    }
                )
                time.sleep(0.5)
                self.assertEqual(esl.executions, [], "a non-agent park must not be driven")
                self.assertEqual(len(gemini.requests), baseline)
            finally:
                esl.close()
                gemini.close()


class EntrypointSpec(unittest.TestCase):
    """The service's start-up contract, exercised through the real
    `main()` in a subprocess: a missing or empty credential is a FATAL
    exit 2 with an actionable journal line (never a silent half-run)."""

    def _run_main(self, tmpdir):
        env = {
            "PATH": os.environ.get("PATH", ""),
            "CREDENTIALS_DIRECTORY": tmpdir,
            "CREDENTIALS_DIR": "",
        }
        return subprocess.run(
            [sys.executable, AGENT_PATH],
            env=env,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_main_without_the_esl_password_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_credential(tmpdir, "gemini_key", "real-key")
            write_credential(tmpdir, "system_prompt", "be helpful")
            result = self._run_main(tmpdir)
        self.assertEqual(result.returncode, 2)
        self.assertIn("FATAL: esl_pass credential missing", result.stdout)

    def test_main_without_the_system_prompt_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_credential(tmpdir, "gemini_key", "real-key")
            write_credential(tmpdir, "esl_pass", "pw")
            result = self._run_main(tmpdir)
        self.assertEqual(result.returncode, 2)
        self.assertIn("FATAL: system_prompt credential missing", result.stdout)

    def test_main_with_an_empty_esl_password_is_fatal(self):
        # An empty file on disk is the same exit-2 family as a missing
        # one; the journal line is the only way to tell them apart.
        with tempfile.TemporaryDirectory() as tmpdir:
            write_credential(tmpdir, "gemini_key", "real-key")
            write_credential(tmpdir, "esl_pass", "   \n")
            write_credential(tmpdir, "system_prompt", "be helpful")
            result = self._run_main(tmpdir)
        self.assertEqual(result.returncode, 2)
        self.assertIn("FATAL: esl_pass credential missing", result.stdout)


if __name__ == "__main__":
    unittest.main()
