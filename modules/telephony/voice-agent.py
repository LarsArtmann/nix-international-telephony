#!/usr/bin/env python3
"""telephony-agent: the Gemini AI voice agent.

A loopback stdlib service that turns inbound FreeSWITCH calls into
conversations with Google's Gemini models:

  1. The dialplan answers the caller, (optionally) starts the full-call
     stereo recording like every other dialplan path, stamps
     ai_agent=1 and parks the channel.
  2. This service sees the CHANNEL_PARK event and drives the call over
     the event socket: it plays a TTS-rendered greeting, then loops
     "record one caller utterance -> transcribe (audio input) ->
     answer (chat) -> speak the answer (Gemini 3.8 text-to-speech)"
     until the caller or the model ends the call ([ACTION: end]) or
     asks for a human ([ACTION: transfer] -> uuid_transfer to
     AGENT_TRANSFER_DESTINATION).
  3. Every turn is appended to a JSONL transcript next to the call
     recording; the per-turn audio files are deleted after
     transcription (the full-call recording is the permanent record).
  4. GET /health (loopback only) reports liveness, call counters and
     the credential state without exposing conversation data.

Honest limits (v1): turn-based, not full duplex. There is no barge-in;
a caller waits for the current record/playback step to finish before a
DTMF-0 transfer or a new utterance is honored. Endpointing is the
record app's silence detector, not semantic VAD.

Credentials ride $CREDENTIALS_DIRECTORY (systemd LoadCredential; see
Config.creds_dir for the resolution order):
  gemini_key     - Gemini API key; a PLACEHOLDER* value fails closed
                   (greeting + honest not-configured message, then
                   transfer to the human destination when configured)
  esl_pass       - FreeSWITCH event-socket password
  system_prompt  - the agent's brain, read at unit start; a prompt edit
                   plus `systemctl restart telephony-agent` reprograms
                   the agent

Contracts are pinned by tests/test_voice_agent.py (stdlib unittest).
"""

import base64
import json
import os
import queue
import socket
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG_PREFIX = "telephony-agent"

# The spoken persona always rides the owner's prompt: these two lines are
# the machine protocol (transfer/end directives) and must stay out of the
# owner-editable brain file so reprogramming can never orphan the actions.
SYSTEM_PREAMBLE = (
    "You are a friendly voice assistant speaking on a live phone call. "
    "Keep replies short and natural; this is spoken audio, not chat. "
    "If the caller asks for a human or needs something you cannot do, "
    "end your reply with the exact directive [ACTION: transfer]. "
    "When the conversation is complete, end your reply with [ACTION: end]. "
    "Never say the directives out loud."
)


def log(message):
    print(f"[{LOG_PREFIX}] {time.strftime('%H:%M:%S')} {message}", flush=True)


def env(name, default=None):
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def env_int(name, default):
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


class Config:
    def __init__(self):
        self.esl_host = env("ESL_HOST", "127.0.0.1")
        self.esl_port = env_int("ESL_PORT", 8021)
        self.api_base = env(
            "GEMINI_API_BASE",
            "https://generativelanguage.googleapis.com/v1beta",
        ).rstrip("/")
        self.llm_model = env("GEMINI_LLM_MODEL", "gemini-3.8-flash")
        self.tts_model = env("GEMINI_TTS_MODEL", "gemini-3.8-flash-lite-tts")
        self.voice = env("GEMINI_VOICE", "Kore")
        self.language = env("GEMINI_LANGUAGE", "en-US")
        self.greeting = env("AGENT_GREETING", "Hello, how can I help you?")
        self.transfer_destination = env("AGENT_TRANSFER_DESTINATION", "")
        self.max_turns = env_int("AGENT_MAX_TURNS", 20)
        self.turn_max_seconds = env_int("AGENT_TURN_MAX_SECONDS", 10)
        self.max_call_seconds = env_int("AGENT_MAX_CALL_SECONDS", 600)
        self.silence_threshold = env_int("AGENT_SILENCE_THRESHOLD", 300)
        self.silence_hits = env_int("AGENT_SILENCE_HITS", 70)
        self.turns_dir = env(
            "AGENT_TURNS_DIR", "/var/lib/telephony/recordings/ai-turns"
        )
        self.transcripts_dir = env(
            "AGENT_TRANSCRIPTS_DIR",
            "/var/lib/telephony/recordings/transcripts",
        )
        self.http_port = env_int("HTTP_PORT", 8070)
        # $CREDENTIALS_DIRECTORY is the variable systemd actually exports
        # (since v244). $CREDENTIALS_DIR was never a systemd variable —
        # reading it alone made every credential silently read as absent
        # and the agent FATAL "esl_pass credential missing" on every start
        # (2026-10-01 outage). The unit-named path is the stable fallback
        # systemd.exec(5) documents for system services.
        creds = (
            os.environ.get("CREDENTIALS_DIRECTORY")
            or os.environ.get("CREDENTIALS_DIR")
            or "/run/credentials/telephony-agent.service"
        )
        self.creds_dir = creds
        self.api_key = self._credential("gemini_key")
        self.esl_password = self._credential("esl_pass") or env("ESL_PASSWORD", "")
        self.system_prompt = self._credential("system_prompt") or ""
        self.api_key_placeholder = self.api_key is None or self.api_key.startswith(
            "PLACEHOLDER"
        )

    def _credential(self, name):
        path = os.path.join(self.creds_dir, name) if self.creds_dir else None
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError as error:
            log(f"credential {name} unreadable: {error}")
            return None


# ---------------------------------------------------------------- audio


def wav_header(
    num_samples, sample_rate, bits_per_sample=16, audio_format=1, channels=1
):
    byte_rate = sample_rate * channels * bits_per_sample // 8
    block_align = channels * bits_per_sample // 8
    data_size = num_samples * block_align
    return (
        b"RIFF"
        + struct.pack("<I", 36 + data_size)
        + b"WAVE"
        + b"fmt "
        + struct.pack(
            "<IHHIIHH",
            16,
            audio_format,
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
        )
        + b"data"
        + struct.pack("<I", data_size)
    )


def ensure_wav(data, mime, default_rate=24000):
    """Normalize an API audio payload to a WAV file FreeSWITCH can play.

    FreeSWITCH resamples on playback, so the original rate does not need
    converting; only headerless raw payloads (audio/l16, audio/mulaw)
    need a header synthesized.
    """
    if data[:4] == b"RIFF":
        return data
    mime = (mime or "").lower()
    rate = default_rate
    for part in mime.replace(";", " ").split():
        if part.startswith("rate="):
            try:
                rate = int(part.split("=", 1)[1])
            except ValueError:
                pass
    if "mulaw" in mime:
        return wav_header(len(data), 8000, bits_per_sample=8, audio_format=7) + data
    return wav_header(len(data) // 2, rate) + data


# ---------------------------------------------------------------- gemini


def walk_collect(obj, wanted_type):
    """Collect payload fields of one item type from any response shape.

    The documented CreateInteraction response nests model output under
    steps[].content[] with type-tagged blocks, but the walker deliberately
    ignores the envelope: model shapes drift, and a shape-tolerant reader
    turns that drift into a logged warning instead of a failed call.
    """
    found = []

    def visit(node):
        if isinstance(node, dict):
            node_type = (
                node.get("type") or node.get("mimeType") or node.get("mime_type")
            )
            if node_type == wanted_type:
                data = node.get("text") or node.get("data")
                if data:
                    found.append((data, node.get("mime_type") or node.get("mimeType")))
            inline = node.get("inlineData") or node.get("inline_data")
            if isinstance(inline, dict) and inline.get("data"):
                found.append(
                    (inline["data"], inline.get("mimeType") or inline.get("mime_type"))
                )
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(obj)
    return found


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, config):
        self.config = config

    def _request(self, payload, timeout=60):
        request = urllib.request.Request(
            f"{self.config.api_base}/interactions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.config.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            raise GeminiError(f"HTTP {error.code}: {detail}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise GeminiError(f"request failed: {error}") from error

    def _audio_content(self, wav_bytes):
        return {
            "type": "audio",
            "mime_type": "audio/wav",
            "data": base64.b64encode(wav_bytes).decode("ascii"),
            "sample_rate": 8000,
            "channels": 1,
        }

    def transcribe(self, wav_bytes):
        payload = {
            "model": self.config.llm_model,
            "input": [
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": "Transcribe this phone-audio utterance "
                            "verbatim. Reply with the transcript text only.",
                        },
                        self._audio_content(wav_bytes),
                    ],
                }
            ],
            "store": False,
        }
        texts = walk_collect(self._request(payload), "text")
        if not texts:
            raise GeminiError("transcription response carried no text")
        return texts[0][0].strip()

    def chat(self, system_prompt, turns):
        steps = []
        for role, text in turns:
            step_type = "user_input" if role == "caller" else "model_output"
            # Consecutive same-side turns merge into one step (the API
            # alternates user_input/model_output steps).
            if steps and steps[-1]["type"] == step_type:
                steps[-1]["content"][0]["text"] += f"\n{text}"
            else:
                steps.append(
                    {
                        "type": step_type,
                        "content": [{"type": "text", "text": text}],
                    }
                )
        if not steps or steps[-1]["type"] == "model_output":
            steps.append(
                {
                    "type": "user_input",
                    "content": [{"type": "text", "text": "(continue)"}],
                }
            )
        payload = {
            "model": self.config.llm_model,
            "input": steps,
            "system_instruction": f"{SYSTEM_PREAMBLE}\n\n{system_prompt}",
            "store": False,
        }
        texts = walk_collect(self._request(payload), "text")
        if not texts:
            raise GeminiError("chat response carried no text")
        return self._split_action(texts[-1][0].strip())

    def _split_action(self, text):
        action = None
        for directive in ("[action: transfer]", "[action: end]"):
            position = text.lower().rfind(directive)
            if position >= 0:
                action = directive[len("[action: ") : -1]
                text = (text[:position] + text[position + len(directive) :]).strip()
        return text, action

    def speak(self, text):
        payload = {
            "model": self.config.tts_model,
            "input": [
                {
                    "type": "user_input",
                    "content": [{"type": "text", "text": text}],
                }
            ],
            "response_format": {
                "type": "audio",
                "mime_type": "audio/wav",
                "sample_rate": 8000,
            },
            "generation_config": {
                "speech_config": [
                    {
                        "voice": self.config.voice,
                        "language": self.config.language,
                    }
                ]
            },
            "store": False,
        }
        audios = walk_collect(self._request(payload), "audio")
        if not audios:
            raise GeminiError("speech response carried no audio")
        data, mime = audios[0]
        return ensure_wav(base64.b64decode(data), mime)


# ---------------------------------------------------------------- esl


class ESLClient:
    """Inbound event-socket client: plain auth, `events plain`, api and
    sendmsg commands, with a reader thread fanning replies and events
    into queues so handlers can wait on execute completions."""

    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.sock = None
        self.file = None
        self.events = queue.Queue()
        self.replies = queue.Queue()
        self.connected = threading.Event()
        self._send_lock = threading.Lock()
        self._reader = None
        self._execute_waiters = []
        self._execute_lock = threading.Lock()

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        self.sock.settimeout(None)
        self.file = self.sock.makefile("rb")
        content_type, _, _ = self._read_frame()
        if content_type != "auth/request":
            raise GeminiError(f"unexpected ESL greeting: {content_type}")
        self._send_raw(f"auth {self.password}\n\n")
        content_type, headers, body = self._read_frame()
        if (
            content_type != "command/reply"
            or "+ok" not in headers.get("reply-text", body).lower()
        ):
            raise GeminiError(f"ESL auth refused: {body.strip()}")
        self._send_raw(
            "events plain CHANNEL_PARK CHANNEL_HANGUP CHANNEL_EXECUTE_COMPLETE DTMF\n\n"
        )
        content_type, headers, body = self._read_frame()
        if (
            content_type != "command/reply"
            or "+ok" not in headers.get("reply-text", body).lower()
        ):
            raise GeminiError(f"ESL event subscription refused: {body.strip()}")
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self.connected.set()
        log(f"event socket connected {self.host}:{self.port}")

    def _read_frame(self):
        headers = {}
        while True:
            line = self.file.readline()
            if not line:
                raise ConnectionError("ESL closed the connection")
            line = line.decode("utf-8", "replace").strip()
            if not line:
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        body = b""
        length = int(headers.get("content-length", "0") or 0)
        if length:
            body = self.file.read(length)
        return headers.get("content-type", ""), headers, body.decode("utf-8", "replace")

    def _read_loop(self):
        try:
            while True:
                content_type, _, body = self._read_frame()
                if content_type == "text/event-plain":
                    event = self._parse_event(body)
                    if not self._resolve_execute(event):
                        self.events.put(event)
                elif content_type in (
                    "command/reply",
                    "api/response",
                    "text/event-json",
                ):
                    self.replies.put((content_type, body))
        except (ConnectionError, OSError, ValueError):
            self.connected.clear()
            log("event socket disconnected")

    def _parse_event(self, body):
        event = {}
        for line in body.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                event[key.strip()] = value.strip()
        return event

    def _send_raw(self, payload):
        with self._send_lock:
            self.sock.sendall(payload.encode("utf-8"))

    def command(self, text, timeout=15):
        """Send `api <text>` and return the response body."""
        self._send_raw(f"api {text}\n\n")
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"no reply to api {text.split()[0]}")
            try:
                content_type, body = self.replies.get(timeout=remaining)
            except queue.Empty:
                continue
            if content_type == "api/response":
                return body
            if content_type == "command/reply":
                return body

    # -- execute-completion routing
    #
    # run_forever's dispatch loop and each call's handler thread both used
    # to read this client's single events queue. A CHANNEL_EXECUTE_COMPLETE
    # could therefore be consumed by the dispatch loop (which ignores it)
    # while the handler that issued the sendmsg waited for it forever --
    # "sendmsg execute never completes", the parked-channel failure. The
    # reader thread now routes an execute completion to a registered waiter
    # first, and only queues unmatched events for the dispatch loop, so the
    # two consumers can no longer steal from each other.

    def _register_execute_waiter(self, matcher):
        entry = (matcher, {"event": None}, threading.Event())
        with self._execute_lock:
            self._execute_waiters.append(entry)
        return entry

    def _clear_execute_waiter(self, entry):
        with self._execute_lock:
            self._execute_waiters = [w for w in self._execute_waiters if w is not entry]

    def _resolve_execute(self, event):
        if event.get("Event-Name") != "CHANNEL_EXECUTE_COMPLETE":
            return False
        with self._execute_lock:
            waiters = list(self._execute_waiters)
        for matcher, holder, signal in waiters:
            if matcher(event):
                holder["event"] = event
                signal.set()
                return True
        return False

    def sendmsg_execute(self, uuid, app, arg, timeout=120, abort=None):
        """Run one application on a channel and block until
        CHANNEL_EXECUTE_COMPLETE confirms it finished. `abort` (a
        threading.Event, the call's hung-up flag) breaks the wait early
        so a dead call cannot pin its handler until the timeout."""

        def matches(event):
            return (
                event.get("Event-Name") == "CHANNEL_EXECUTE_COMPLETE"
                and event.get("Unique-ID") == uuid
                and event.get("Application", "").lower() == app.lower()
                and (
                    not arg
                    or event.get("Application-Data", "").startswith(arg.split()[0])
                )
            )

        entry = self._register_execute_waiter(matches)
        _, holder, signal = entry
        try:
            self._send_raw(
                f"sendmsg {uuid}\n"
                "call-command: execute\n"
                f"execute-app-name: {app}\n"
                f"execute-app-arg: {arg}\n"
                "event-lock: true\n\n"
            )
            deadline = time.monotonic() + timeout
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"{app} never completed on {uuid}")
                if signal.wait(timeout=min(remaining, 0.25)):
                    return holder["event"]
                if abort is not None and abort.is_set():
                    raise ConnectionError(f"call {uuid} hung up during {app}")
        finally:
            self._clear_execute_waiter(entry)

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass
        self.connected.clear()


# ---------------------------------------------------------------- calls


class CallState:
    def __init__(self, uuid, config):
        self.uuid = uuid
        self.config = config
        self.turns = []
        self.transfer_requested = threading.Event()
        self.hungup = threading.Event()
        self.started = time.monotonic()


class Agent:
    def __init__(self, config, gemini):
        self.config = config
        self.gemini = gemini
        self.esl = None
        self.active = {}
        self.calls_total = 0
        self.last_error = None
        self.greeting_wav = None
        self.lock = threading.Lock()

    # -- lifecycle

    def render_greeting(self):
        if self.config.api_key_placeholder:
            log(
                "gemini_api_key is missing or PLACEHOLDER: agent runs in fail-closed mode"
            )
            return False
        for attempt in (1, 2, 3):
            try:
                self.greeting_wav = self.gemini.speak(self.config.greeting)
                log(
                    f"greeting rendered ({len(self.greeting_wav)} bytes, attempt {attempt})"
                )
                return True
            except GeminiError as error:
                self.last_error = f"greeting render: {error}"
                log(f"{self.last_error} (attempt {attempt}/3)")
                time.sleep(2 * attempt)
        return False

    def health(self):
        with self.lock:
            return {
                "agent": "telephony-agent",
                "esl": getattr(self.esl, "connected", None) is not None
                and self.esl.connected.is_set(),
                "calls_active": len(self.active),
                "calls_total": self.calls_total,
                "key": "placeholder" if self.config.api_key_placeholder else "present",
                "greeting_rendered": self.greeting_wav is not None,
                "last_error": self.last_error,
            }

    # -- esl plumbing

    def run_forever(self):
        backoff = 5
        while True:
            self.esl = ESLClient(
                self.config.esl_host, self.config.esl_port, self.config.esl_password
            )
            try:
                self.esl.connect()
                backoff = 5
                while True:
                    event = self.esl.events.get(timeout=30)
                    self._dispatch(event)
            except queue.Empty:
                continue
            except (ConnectionError, OSError, TimeoutError, GeminiError) as error:
                self.last_error = f"event socket: {error}"
                log(f"{self.last_error}; reconnecting in {backoff}s")
                self.esl.close()
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)

    def _dispatch(self, event):
        name = event.get("Event-Name", "")
        uuid = event.get("Unique-ID", "")
        if name == "CHANNEL_PARK" and event.get("variable_ai_agent") == "1":
            if uuid in self.active:
                return
            call = CallState(uuid, self.config)
            with self.lock:
                self.active[uuid] = call
                self.calls_total += 1
            threading.Thread(
                target=self._handle_call, args=(call,), daemon=True
            ).start()
        elif name in ("DTMF", "DTMF_ADVANCED"):
            # DTMF-Digit is the header switch_channel.c stamps on
            # SWITCH_EVENT_DTMF; DTMF-String stays a defensive fallback.
            digit = event.get("DTMF-Digit") or event.get("DTMF-String") or ""
            if digit.startswith("0"):
                call = self.active.get(uuid)
                if call:
                    call.transfer_requested.set()
        elif name in ("CHANNEL_HANGUP", "CHANNEL_DESTROY") and uuid in self.active:
            call = self.active.get(uuid)
            if call:
                call.hungup.set()
            log(f"caller hung up: {uuid}")

    # -- the conversation

    def _handle_call(self, call):
        config = self.config
        transcript_path = None
        try:
            os.makedirs(config.transcripts_dir, exist_ok=True)
            os.makedirs(config.turns_dir, exist_ok=True)
            transcript_path = os.path.join(config.transcripts_dir, f"{call.uuid}.jsonl")
            self._transcribe_line(
                transcript_path,
                {
                    "type": "start",
                    "ts": int(time.time()),
                    "uuid": call.uuid,
                    "models": [config.llm_model, config.tts_model],
                },
            )
            deadline = call.started + config.max_call_seconds
            if config.api_key_placeholder or self.greeting_wav is None:
                log(f"call {call.uuid}: agent not configured, playing fallback")
                self._finish_call(call, transcript_path, reason="not_configured")
                return
            self._play(call, self.greeting_wav)
            empty_turns = 0
            pending_transfer = False
            turns = 0
            while turns < config.max_turns and time.monotonic() < deadline:
                if call.transfer_requested.is_set():
                    break
                turn_path = self._record_turn(call, turns)
                turns += 1
                caller_text = ""
                if turn_path:
                    try:
                        # transcribe() carries the audio inline (base64), so
                        # the recorded file is read to bytes here — passing
                        # the path made the real GeminiClient crash on every
                        # first utterance (the FakeGemini stub masked it).
                        with open(turn_path, "rb") as handle:
                            caller_text = self.gemini.transcribe(handle.read())
                    except (GeminiError, OSError) as error:
                        self.last_error = f"transcribe: {error}"
                        log(f"call {call.uuid}: {self.last_error}")
                if turn_path and os.path.exists(turn_path):
                    try:
                        os.remove(turn_path)
                    except OSError:
                        pass
                if not caller_text.strip():
                    empty_turns += 1
                    if empty_turns >= 3:
                        self._speak_line(
                            call, "I did not hear anything. Thank you and goodbye."
                        )
                        self._hangup(call)
                        self._transcribe_line(
                            transcript_path, {"type": "end", "reason": "silence"}
                        )
                        return
                    continue
                empty_turns = 0
                call.turns.append(("caller", caller_text))
                self._transcribe_line(
                    transcript_path,
                    {"type": "turn", "role": "caller", "text": caller_text},
                )
                try:
                    reply_text, action = self.gemini.chat(
                        config.system_prompt, call.turns
                    )
                except GeminiError as error:
                    self.last_error = f"chat: {error}"
                    log(f"call {call.uuid}: {self.last_error}")
                    self._speak_line(
                        call,
                        "Sorry, I had trouble understanding. "
                        + (
                            "Let me transfer you."
                            if config.transfer_destination
                            else "Goodbye."
                        ),
                    )
                    self._route_transfer_or_end(call, transcript_path, forced=True)
                    return
                call.turns.append(("agent", reply_text))
                self._transcribe_line(
                    transcript_path,
                    {"type": "turn", "role": "agent", "text": reply_text},
                )
                if action == "transfer":
                    self._speak_line(call, reply_text or "One moment, connecting you.")
                    pending_transfer = True
                    break
                if action == "end":
                    self._speak_line(call, reply_text or "Thank you and goodbye.")
                    self._hangup(call)
                    self._transcribe_line(
                        transcript_path, {"type": "end", "reason": "agent_end"}
                    )
                    return
                self._speak_line(call, reply_text)
            if call.transfer_requested.is_set() or pending_transfer:
                self._route_transfer_or_end(call, transcript_path)
            else:
                self._speak_line(call, "That is all the time we have. Goodbye.")
                self._hangup(call)
                self._transcribe_line(
                    transcript_path, {"type": "end", "reason": "turn_or_time_limit"}
                )
        except Exception as error:  # noqa: BLE001 - one bad call must not kill the agent
            self.last_error = f"call {call.uuid}: {error}"
            log(self.last_error)
            try:
                if transcript_path:
                    self._transcribe_line(
                        transcript_path, {"type": "end", "reason": f"error: {error}"}
                    )
            except OSError:
                pass
        finally:
            with self.lock:
                self.active.pop(call.uuid, None)

    def _route_transfer_or_end(self, call, transcript_path, forced=False):
        if self.config.transfer_destination:
            self._transfer(call)
            self._transcribe_line(
                transcript_path, {"type": "end", "reason": "transferred"}
            )
        elif not forced:
            self._speak_line(call, "Thank you and goodbye.")
            self._hangup(call)
            self._transcribe_line(
                transcript_path, {"type": "end", "reason": "transfer_unavailable"}
            )
        else:
            self._hangup(call)
            self._transcribe_line(
                transcript_path, {"type": "end", "reason": "error_farewell"}
            )

    def _finish_call(self, call, transcript_path, reason):
        if self.config.transfer_destination:
            self._transfer(call)
            reason = "transferred_unconfigured"
        else:
            # Fail-closed with zero Gemini involvement: a tone, then
            # goodbye. No API key means no speech, not a broken promise.
            self._broadcast(call, None)
            self._hangup(call)
        self._transcribe_line(transcript_path, {"type": "end", "reason": reason})

    def _record_turn(self, call, index):
        path = os.path.join(self.config.turns_dir, f"{call.uuid}_{index}.wav")
        self.esl.sendmsg_execute(
            call.uuid,
            "record",
            f"{path} {self.config.turn_max_seconds} "
            f"{self.config.silence_threshold} {self.config.silence_hits}",
            timeout=self.config.turn_max_seconds + 30,
            abort=call.hungup,
        )
        try:
            if os.path.getsize(path) > 1600:
                return path
        except OSError:
            pass
        return None

    def _play(self, call, wav_bytes):
        self._broadcast(call, wav_bytes)

    def _speak_line(self, call, text):
        if not text:
            return
        try:
            wav = self.gemini.speak(text)
        except GeminiError as error:
            self.last_error = f"speak: {error}"
            log(f"call {call.uuid}: {self.last_error}")
            self._broadcast(call, None)
            return
        self._broadcast(call, wav)

    def _broadcast(self, call, wav_bytes):
        """Play WAV bytes on the answer leg via playback of a temp file."""
        if wav_bytes is None:
            self.esl.sendmsg_execute(
                call.uuid,
                "playback",
                "tone_stream://%(1000,1000,440,480)",
                timeout=30,
                abort=call.hungup,
            )
            return
        path = os.path.join(self.config.turns_dir, f"{call.uuid}_reply.wav")
        with open(path, "wb") as handle:
            handle.write(wav_bytes)
        try:
            self.esl.sendmsg_execute(
                call.uuid, "playback", path, timeout=90, abort=call.hungup
            )
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def _transfer(self, call):
        destination = self.config.transfer_destination
        log(f"call {call.uuid}: transferring to {destination}")
        self.esl.command(f"uuid_transfer {call.uuid} {destination} XML default")

    def _hangup(self, call):
        log(f"call {call.uuid}: hanging up")
        self.esl.command(f"uuid_kill {call.uuid} normal_clearing")

    def _transcribe_line(self, path, payload):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- health


def start_health_server(agent):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] != "/health":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(agent.health()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            log("health: " + (fmt % args))

    server = ThreadingHTTPServer(("127.0.0.1", agent.config.http_port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"health endpoint on 127.0.0.1:{agent.config.http_port}/health")
    return server


def main():
    config = Config()
    if not config.esl_password:
        log("FATAL: esl_pass credential missing")
        return 2
    if not config.system_prompt:
        log("FATAL: system_prompt credential missing")
        return 2
    agent = Agent(config, GeminiClient(config))
    agent.render_greeting()
    start_health_server(agent)
    agent.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
