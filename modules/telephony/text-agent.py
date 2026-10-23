#!/usr/bin/env python3
"""The supervised text-message agent (services.telephony.textagent).

A loopback stdlib-Python service that gives the AI a presence on SMS
while keeping the human in command. One process, four cooperating
parts:

  * Conversation-state reader: tails the messaging bridge's webhook
    JSONL (every Telnyx event, both directions) into per-contact
    conversation state — resume-safe across restarts and logrotate
    copytruncate, deduplicated by event id.
  * Gemini draft engine: on a new inbound (or an on-demand request,
    or a missed call) assembles a prompt from the system-prompt
    credential, conversation history, learned per-contact
    preferences, contact memory and (optionally) the pbx-lens call
    timeline, then asks for a JSON reply: text in the contact's
    language, an English gloss, the detected language and a
    confidence self-score. Every draft is logged as a transcript-style
    JSONL line (the audit trail).
  * Review API: loopback HTTP guarded by a bearer shared secret (the
    webphone holds the same file): list / approve / edit / discard
    drafts, on-demand draft for the compose box, translate + tone
    transforms, suppression list and reset, per-contact memory and
    preferences, presence toggles, the daily briefing, GET /health.
  * Autopilot: per the mode matrix (off / drafts / after-hours /
    full) drafts may become autonomous sends through the bridge's
    outbound gateway — only when confidence clears the threshold,
    the contact is neither suppressed, VIP-frozen nor kill-switch
    frozen, and every autonomous send carries the honest identity
    signature. The safety gates (STOP suppression, loop kill-switch,
    VIP protection) ship WITH the autonomy, never after it.

Presence rides the FreeSWITCH event socket (busy while any channel
is up; DND/vacation toggles persist) and missed calls (ring-out
without answer) become follow-up drafts with optional agent-
transcript enrichment.

Honest limits (v1): drafts are synchronous Gemini calls; there is no
media understanding (MMS attachments count as "media" markers, not
content); the briefing mailer is an optional sendmail-style pipe, the
digest itself always lands on the review API.

Conventions (load-bearing, shared with voice-agent.py and
telnyx-webhooks.py): stdlib only; secrets ride
$CREDENTIALS_DIRECTORY (resolution order: $CREDENTIALS_DIRECTORY ->
explicit $CREDENTIALS_DIR override -> /run/credentials/<unit>; the
phantom-variable burn of 2026-10-01); a PLACEHOLDER* API key fails
closed with zero API calls; every user-facing error names the fix.
"""

import calendar
import email.utils
import hashlib
import hmac
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG_PREFIX = "telephony-textagent"

MAX_API_BODY = 1 << 20  # review-API request cap (drafts/edits are text)
MAX_GATEWAY_BODY = 1 << 20  # outbound text is tiny; keep the honest cap

# The autopilot ladder. The env value is the DEFAULT; the review API can
# pin a runtime override (state/mode.json) so the owner can switch
# behaviour from the webphone without a redeploy.
MODES = ("off", "drafts", "after-hours", "full")

# The machine protocol rides the fixed preamble, the persona rides the
# owner-editable brain file — same split as the voice agent, so
# reprogramming the prompt can never orphan the output contract.
DRAFT_PREAMBLE = (
    "You draft SMS replies on behalf of an account owner. You answer "
    "in the contact's language. You reply ONLY with a single JSON "
    'object: {"reply": string, "en_gloss": string, "language": string, '
    '"confidence": number} — reply is the SMS to send (concise, plain '
    "text, no emojis unless the contact uses them), en_gloss is a "
    "one-line English translation of reply (identical text when the "
    "conversation is English), language is the BCP-47 primary subtag "
    "of reply, confidence is your 0-100 self-score for how confident "
    "you are this reply is appropriate and safe to send. When unsure, "
    "say so honestly inside the reply or lower confidence below 50 — "
    "never invent facts."
)

TRANSLATE_PREAMBLE = (
    "You translate and re-tone SMS drafts. Reply ONLY with a single "
    'JSON object: {"text": string} — text is the transformed message. '
    "Preserve meaning, keep SMS length, no commentary."
)

# Heuristic language seeds: the model decides, this only feeds the
# prompt when the heuristic is confident enough to help.
POLISH_MARKERS = re.compile(r"[ąćęłńóśźż]", re.IGNORECASE)
GERMAN_MARKERS = re.compile(
    r"\b(nicht|danke|guten|hallo|bitte|termin|heute|morgen|schon|noch|sehr)\b",
    re.IGNORECASE,
)

# Counterparty-escalation patterns (the kill-switch's second arm): a
# contact repeatedly asking for a human is a frozen conversation, not
# a prompt variation.
HUMAN_REQUEST_PATTERNS = [
    re.compile(
        r"\b(real|human|person|owner|operator)\b.*\b(talk|speak|please|human)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(human|echte[nr]?|mensch|inhaber)\b", re.IGNORECASE),
    re.compile(r"\b(cz\w*owiek|cz\w*owieka|w\w?a[śs]ciciela)\b", re.IGNORECASE),
]


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


def env_list(name, default):
    raw = os.environ.get(name, "")
    if not raw.strip():
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def normalize_contact(number):
    """Canonical contact key: digits only, E.161 without the plus is
    ambiguous across sources (Telnyx sends +E164, FreeSWITCH events
    vary), so the plus is stripped everywhere and re-added on send."""
    return re.sub(r"[^\d]", "", number or "")


def with_plus(contact):
    return f"+{contact}" if contact and not contact.startswith("+") else contact


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"


def parse_hhmm(value, fallback_minutes):
    match = re.match(r"^(\d{1,2}):(\d{2})$", value or "")
    if not match:
        return fallback_minutes
    hours, minutes = int(match.group(1)), int(match.group(2))
    if hours > 23 or minutes > 59:
        return fallback_minutes
    return hours * 60 + minutes


def minutes_now():
    local = time.localtime()
    return local.tm_hour * 60 + local.tm_min


class Config:
    def __init__(self):
        self.http_port = env_int("HTTP_PORT", 8071)
        self.api_base = env(
            "GEMINI_API_BASE",
            "https://generativelanguage.googleapis.com/v1beta",
        ).rstrip("/")
        self.llm_model = env("GEMINI_LLM_MODEL", "gemini-3.8-flash")
        self.llm_fallbacks = []
        seen_models = {self.llm_model}
        for model in env_list("GEMINI_LLM_FALLBACKS", []):
            if model and model not in seen_models:
                seen_models.add(model)
                self.llm_fallbacks.append(model)
        # Non-final fallback attempts get a shorter leash: a hung model
        # (the 2026-10-23 3.8-flash class) must not eat the whole draft
        # window before the standby is tried.
        self.llm_attempt_timeout = env_int("GEMINI_LLM_ATTEMPT_TIMEOUT", 25)
        self.owner_name = env("TEXTAGENT_OWNER_NAME", "")
        self.languages = env_list("TEXTAGENT_LANGUAGES", ["en", "de", "pl"])
        self.history_messages = env_int("TEXTAGENT_HISTORY_MESSAGES", 20)
        self.draft_ttl = env_int("TEXTAGENT_DRAFT_TTL", 86400)
        self.mode = env("TEXTAGENT_MODE", "drafts")
        self.working_start = parse_hhmm(env("TEXTAGENT_WORKING_START", "09:00"), 540)
        self.working_end = parse_hhmm(env("TEXTAGENT_WORKING_END", "18:00"), 1080)
        self.confidence_threshold = env_int("TEXTAGENT_CONFIDENCE_THRESHOLD", 80)
        self.signature_template = env(
            "TEXTAGENT_SIGNATURE",
            "(automated reply for {owner} — reply STOP to opt out)",
        )
        self.max_auto_per_conversation = env_int("TEXTAGENT_MAX_AUTO", 3)
        self.vip_numbers = [
            normalize_contact(number) for number in env_list("TEXTAGENT_VIP", [])
        ]
        self.opt_out_keywords = env_list(
            "TEXTAGENT_OPT_OUT_KEYWORDS",
            [
                "STOP",
                "STOPALL",
                "UNSUBSCRIBE",
                "CANCEL",
                "END",
                "QUIT",
                "STOPP",
                "REZYGNUJĘ",
                "REZYGNUJE",
            ],
        )
        self.briefing_hour = env_int("TEXTAGENT_BRIEFING_HOUR", 8)
        self.missed_call_enabled = env("TEXTAGENT_MISSED_CALL", "1") == "1"
        self.missed_call_grace = env_int("TEXTAGENT_MISSED_CALL_GRACE", 300)
        self.lens_url = env("TEXTAGENT_LENS_URL", "")
        self.lens_context_days = env_int("TEXTAGENT_LENS_CONTEXT_DAYS", 90)
        self.webhook_log = env("TEXTAGENT_WEBHOOK_LOG", "")
        self.transcripts_dir = env("TEXTAGENT_TRANSCRIPTS_DIR", "")
        self.bridge_url = env("TEXTAGENT_BRIDGE_URL", "")
        self.esl_host = env("ESL_HOST", "127.0.0.1")
        self.esl_port = env_int("ESL_PORT", 8021)
        self.esl_password = env("ESL_PASSWORD", "")
        self.state_dir = env("TEXTAGENT_STATE_DIR", "/var/lib/telephony-textagent")
        self.mailer_command = env("TEXTAGENT_MAILER_COMMAND", "")
        self.briefing_from = env("TEXTAGENT_BRIEFING_FROM", "")
        self.briefing_to = env("TEXTAGENT_BRIEFING_TO", "")
        creds = (
            os.environ.get("CREDENTIALS_DIRECTORY")
            or os.environ.get("CREDENTIALS_DIR")
            or "/run/credentials/telephony-textagent.service"
        )
        self.creds_dir = creds
        self.api_key = self._credential("gemini_key")
        self.system_prompt = self._credential("system_prompt")
        self.shared_secret = self._credential("shared_secret")
        self.gateway_secret = self._credential("gateway_secret")
        self.esl_password = self._credential("esl_pass") or self.esl_password
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

    def signature(self):
        owner = self.owner_name or "the owner"
        return self.signature_template.replace("{owner}", owner)

    def system_prompt_text(self):
        # Re-read per draft: an edit plus a restart reprograms the agent
        # (same contract as the voice agent's brain file).
        if self.system_prompt is None:
            return ""
        try:
            with open(
                os.path.join(self.creds_dir, "system_prompt"), encoding="utf-8"
            ) as handle:
                return handle.read().strip()
        except OSError:
            return self.system_prompt


# ---------------------------------------------------------------- state


class StateStore:
    """Per-contact derived state under the service state dir.

    Layout (all JSON, atomic tmp+rename writes, one lock):
      conversations/<contact>.json   rolling message tail + counters
      drafts/<id>.json               one file per draft lifecycle
      suppression.json               opted-out contacts
      memory/<contact>.json          shared contact memory notes
      preferences/<contact>.json     learned corrections
      presence.json                  DND/vacation toggles
      tailer.json                    JSONL read offsets + seen ids
      briefing/latest.json + <date>.md
      audit.jsonl                    one line per draft/send decision
    """

    def __init__(self, base):
        self.base = base
        self.lock = threading.RLock()
        for name in (
            "conversations",
            "drafts",
            "memory",
            "preferences",
            "briefing",
        ):
            os.makedirs(os.path.join(base, name), exist_ok=True)

    def _path(self, *parts):
        return os.path.join(self.base, *parts)

    def _write(self, path, payload):
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
            handle.write("\n")
        os.replace(tmp, path)

    def _read(self, path, default):
        try:
            with open(path, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return default

    def audit(self, kind, **fields):
        record = {"ts": now_iso(), "kind": kind}
        record.update(fields)
        with self.lock:
            try:
                with open(self._path("audit.jsonl"), "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError as error:
                log(f"audit write failed: {error}")

    # -- autopilot mode override

    def mode_override(self):
        payload = self._read(self._path("mode.json"), {})
        mode = payload.get("mode") if isinstance(payload, dict) else None
        return mode if mode in MODES else None

    def set_mode_override(self, mode):
        with self.lock:
            if mode is None:
                try:
                    os.unlink(self._path("mode.json"))
                except FileNotFoundError:
                    pass
                return None
            self._write(self._path("mode.json"), {"mode": mode, "set_at": now_iso()})
            return mode

    # -- conversations

    def conversation(self, contact):
        with self.lock:
            return self._read(
                self._path("conversations", f"{contact}.json"),
                {
                    "contact": contact,
                    "messages": [],
                    "consecutive_auto": 0,
                    "frozen": None,
                },
            )

    def _save_conversation(self, data):
        with self.lock:
            self._write(self._path("conversations", f"{data['contact']}.json"), data)

    def append_message(self, contact, message, tail=50):
        with self.lock:
            data = self.conversation(contact)
            data["contact"] = contact
            data["messages"].append(message)
            data["messages"] = data["messages"][-tail:]
            if message.get("direction") == "out" and not message.get("by_ai"):
                data["consecutive_auto"] = 0
                if data.get("frozen"):
                    data["frozen"] = None
            self._save_conversation(data)
            return data

    def mark_auto_sent(self, contact, max_auto):
        """Bump the kill-switch counter after an autonomous send;
        returns the frozen reason when the switch arms."""
        with self.lock:
            data = self.conversation(contact)
            data["consecutive_auto"] = int(data.get("consecutive_auto", 0)) + 1
            frozen = None
            if data["consecutive_auto"] >= max_auto:
                frozen = (
                    f"kill-switch: {data['consecutive_auto']} autonomous sends "
                    "without a human outbound"
                )
                data["frozen"] = frozen
            self._save_conversation(data)
            return frozen

    def freeze(self, contact, reason):
        with self.lock:
            data = self.conversation(contact)
            data["frozen"] = reason
            self._save_conversation(data)

    def resume(self, contact):
        with self.lock:
            data = self.conversation(contact)
            data["frozen"] = None
            data["consecutive_auto"] = 0
            self._save_conversation(data)

    # -- drafts

    def _draft_path(self, draft_id):
        return self._path("drafts", f"{draft_id}.json")

    def create_draft(self, draft):
        with self.lock:
            self._write(self._draft_path(draft["id"]), draft)
            self.audit(
                "draft",
                **{k: draft.get(k) for k in ("id", "contact", "trigger", "confidence")},
            )
            return draft

    def draft(self, draft_id):
        with self.lock:
            return self._read(self._draft_path(draft_id), None)

    def update_draft(self, draft_id, **fields):
        with self.lock:
            draft = self.draft(draft_id)
            if draft is None:
                return None
            draft.update(fields)
            self._write(self._draft_path(draft_id), draft)
            return draft

    def list_drafts(self, statuses=None):
        wanted = set(statuses or ("pending",))
        found = []
        with self.lock:
            try:
                names = os.listdir(self._path("drafts"))
            except OSError:
                names = []
            for name in names:
                if not name.endswith(".json"):
                    continue
                draft = self._read(self._path("drafts", name), None)
                if draft and draft.get("status") in wanted:
                    found.append(draft)
        found.sort(key=lambda item: item.get("created_at", ""))
        return found

    def sweep_expired_drafts(self, ttl):
        cutoff = time.time() - ttl
        flipped = 0
        with self.lock:
            for draft in self.list_drafts(statuses=("pending",)):
                try:
                    mtime = os.path.getmtime(self._draft_path(draft["id"]))
                except OSError:
                    continue
                if mtime < cutoff:
                    self.update_draft(
                        draft["id"], status="expired", expired_at=now_iso()
                    )
                    flipped += 1
        return flipped

    # -- suppression

    def suppression(self):
        with self.lock:
            return self._read(self._path("suppression.json"), {})

    def suppress(self, contact, keyword, raw):
        with self.lock:
            data = self.suppression()
            data[contact] = {"since": now_iso(), "keyword": keyword, "raw": raw}
            self._write(self._path("suppression.json"), data)
            self.audit("suppressed", contact=contact, keyword=keyword)

    def unsuppress(self, contact):
        with self.lock:
            data = self.suppression()
            if contact in data:
                del data[contact]
                self._write(self._path("suppression.json"), data)
                self.audit("suppression_reset", contact=contact)
                return True
            return False

    # -- memory + preferences

    def memory(self, contact):
        with self.lock:
            return self._read(self._path("memory", f"{contact}.json"), [])

    def set_memory(self, contact, notes):
        with self.lock:
            self._write(self._path("memory", f"{contact}.json"), list(notes))

    def preferences(self, contact):
        with self.lock:
            return self._read(
                self._path("preferences", f"{contact}.json"), {"rules": []}
            )

    def record_correction(self, contact, original, final):
        """Teachable corrections (idea 8): a human edit between the
        draft and the approved text becomes a preference rule. v1
        learns whole-message replacements as style hints (kept capped);
        the prompt renders them as 'the human changed X to Y'."""
        if not original or not final or original.strip() == final.strip():
            return None
        with self.lock:
            data = self.preferences(contact)
            rule = {
                "draft": original.strip()[:400],
                "approved": final.strip()[:400],
                "learned_at": now_iso(),
            }
            data["rules"] = (data.get("rules", []) + [rule])[-10:]
            self._write(self._path("preferences", f"{contact}.json"), data)
            self.audit("correction_learned", contact=contact)
            return rule

    def reset_preferences(self, contact):
        with self.lock:
            self._write(self._path("preferences", f"{contact}.json"), {"rules": []})

    # -- presence

    def presence_overrides(self):
        with self.lock:
            return self._read(
                self._path("presence.json"), {"dnd": False, "vacation": False}
            )

    def set_presence_overrides(self, **flags):
        with self.lock:
            data = self.presence_overrides()
            data.update(flags)
            self._write(self._path("presence.json"), data)
            return data

    # -- tailer bookkeeping

    def tailer_state(self):
        with self.lock:
            return self._read(
                self._path("tailer.json"), {"offset": 0, "seen": [], "inode": None}
            )

    def save_tailer_state(self, offset, seen, inode=None):
        with self.lock:
            self._write(
                self._path("tailer.json"),
                {"offset": offset, "seen": seen, "inode": inode},
            )

    # -- briefing

    def save_briefing(self, digest):
        with self.lock:
            self._write(self._path("briefing", "latest.json"), digest)
            date = time.strftime("%Y-%m-%d")
            try:
                with open(
                    self._path("briefing", f"{date}.md"), "w", encoding="utf-8"
                ) as handle:
                    handle.write(digest.get("markdown", ""))
            except OSError as error:
                log(f"briefing markdown write failed: {error}")


# ---------------------------------------------------------------- reader


class JsonlTailer:
    """Tail the receiver's inbound.jsonl with offset resume.

    The receiver appends forever and logrotate uses copytruncate, so
    rotation detection needs three guards: size shrink (the plain
    copytruncate case), inode change (logrotate move/create), and the
    mid-line-seek case — a busy night can truncate AND refill the file
    past the old offset, where the first line read at the stale offset
    fails to parse. On any suspicion the tailer re-reads from the top;
    the id dedupe absorbs the overlap. The tiny loss window is the
    accepted copytruncate trade (same contract as the receiver's own
    rotation note)."""

    def __init__(self, path, state, on_event, poll_seconds=2.0):
        self.path = path
        self.state = state
        self.on_event = on_event
        self.poll_seconds = poll_seconds
        self.seen = set(state.tailer_state()["seen"])
        self.stop = threading.Event()

    def _dispatch(self, raw_line):
        try:
            event = json.loads(raw_line)
        except ValueError:
            return False
        if not isinstance(event, dict):
            return False
        identity = (
            event.get("id")
            or event.get("data", {}).get("id")
            or hashlib.sha1(raw_line.encode("utf-8", "replace")).hexdigest()
        )
        if identity in self.seen:
            return True
        self.seen.add(identity)
        if len(self.seen) > 5000:
            self.seen = set(list(self.seen)[-2500:])
        try:
            self.on_event(event)
        except Exception as error:
            # One bad event never kills the reader.
            log(f"event handler error: {error}")
        return True

    def _read_pass(self, offset):
        """Read from offset; returns (new_offset, clean_start)."""
        with open(self.path, encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            first = True
            for line in handle:
                if first:
                    first = False
                    if offset > 0:
                        try:
                            json.loads(line)
                        except ValueError:
                            if line.strip():
                                # Seeking into the middle of a line:
                                # rotation hid behind a refill — signal.
                                return offset, False
                self._dispatch(line)
            offset = handle.tell()
        return offset, True

    def poll_once(self):
        bookkeeping = self.state.tailer_state()
        offset = bookkeeping["offset"]
        inode = bookkeeping.get("inode")
        if not os.path.exists(self.path):
            return 0
        try:
            stat = os.stat(self.path)
        except OSError:
            return offset
        if inode is not None and stat.st_ino != inode:
            offset = 0  # logrotate replaced the file
        if stat.st_size < offset:
            offset = 0  # copytruncate shrank it
        try:
            new_offset, clean = self._read_pass(offset)
            if not clean and offset > 0:
                # Mid-line seek: re-read from the top, dedupe absorbs it.
                new_offset, _ = self._read_pass(0)
            offset = new_offset
        except OSError as error:
            log(f"webhook log read failed: {error}")
            return offset
        self.state.save_tailer_state(offset, list(self.seen)[-500:], stat.st_ino)
        return offset

    def run(self):
        log(f"tailing {self.path}")
        while not self.stop.is_set():
            try:
                self.poll_once()
            except Exception as error:
                # The reader survives anything a malformed log can throw.
                log(f"tailer error: {error}")
            self.stop.wait(self.poll_seconds)


# ---------------------------------------------------------------- gemini


class GeminiError(RuntimeError):
    pass


def walk_collect_text(obj):
    found = []

    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "text" and node.get("text"):
                found.append(node["text"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(obj)
    return found


def extract_json_object(text):
    """Best-effort JSON object extraction: models occasionally wrap
    the object in code fences or prose; the first balanced object
    wins, and failure raises GeminiError with the raw excerpt."""
    if not text:
        raise GeminiError("model reply was empty")
    stripped = re.sub(r"```(?:json)?", "", text).strip()
    start = stripped.find("{")
    while start >= 0:
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(stripped)):
            char = stripped[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(stripped[start : index + 1])
                    except ValueError:
                        break
        start = stripped.find("{", start + 1)
    raise GeminiError(f"model reply carried no JSON object: {stripped[:200]}")


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

    def _models(self):
        return [self.config.llm_model, *self.config.llm_fallbacks]

    def _interact(self, preamble, prompt, timeout=60):
        # A high-demand model answers 503 or HANGS (both seen live on
        # gemini-3.8-flash, 2026-10-23). Try the configured standby
        # chain: non-final attempts get the short leash, the last one the
        # full window; the honest last error is what surfaces.
        models = self._models()
        failures = []
        for index, model in enumerate(models):
            last = index == len(models) - 1
            attempt_timeout = (
                timeout
                if last
                else min(timeout, max(5, self.config.llm_attempt_timeout))
            )
            payload = {
                "model": model,
                "input": [
                    {
                        "type": "user_input",
                        "content": [{"type": "text", "text": prompt}],
                    }
                ],
                "system_instruction": preamble,
                "store": False,
            }
            try:
                texts = walk_collect_text(
                    self._request(payload, timeout=attempt_timeout)
                )
            except GeminiError as error:
                failures.append(f"{model}: {error}")
                if not last:
                    log(f"model {model} failed ({error}); trying {models[index + 1]}")
                continue
            if not texts:
                failures.append(f"{model}: response carried no text")
                if not last:
                    log(f"model {model} answered no text; trying {models[index + 1]}")
                continue
            return texts[-1].strip()
        raise GeminiError("; ".join(failures) or "no model configured")

    def draft(self, prompt):
        reply = self._interact(
            f"{DRAFT_PREAMBLE}\n\n{self.config.system_prompt_text()}", prompt
        )
        parsed = extract_json_object(reply)
        text = str(parsed.get("reply", "")).strip()
        if not text:
            raise GeminiError("draft JSON carried no reply text")
        try:
            confidence = max(
                0, min(100, int(round(float(parsed.get("confidence", 0)))))
            )
        except (TypeError, ValueError):
            confidence = 0
        return {
            "text": text,
            "en_gloss": str(parsed.get("en_gloss", "")).strip(),
            "language": str(parsed.get("language", "en")).strip()[:8] or "en",
            "confidence": confidence,
        }

    def translate(self, text, to_language, tone):
        tone_instruction = {
            "shorter": " Make it noticeably shorter.",
            "formal": " Use a more formal register.",
            "casual": " Use a more casual, friendly register.",
        }.get(tone or "", "")
        prompt = (
            f"Translate this SMS draft into {to_language or "the contact's language"}."
            f"{tone_instruction}\n---\n{text}\n---"
        )
        reply = self._interact(TRANSLATE_PREAMBLE, prompt)
        parsed = extract_json_object(reply)
        translated = str(parsed.get("text", "")).strip()
        if not translated:
            raise GeminiError("translate JSON carried no text")
        return translated


def detect_language_hint(text):
    """Heuristic seed for the prompt (the model makes the call): Polish
    diacritics are decisive, German function words are a strong hint."""
    if not text:
        return None
    if POLISH_MARKERS.search(text):
        return "pl"
    if GERMAN_MARKERS.search(text):
        return "de"
    return None


# ---------------------------------------------------------------- outbound


class GatewayError(RuntimeError):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def encode_multipart(fields):
    boundary = f"textagent-{hashlib.sha1(json.dumps(fields).encode()).hexdigest()[:24]}"
    lines = []
    for name, value in fields.items():
        lines.append(f"--{boundary}")
        lines.append(f'Content-Disposition: form-data; name="{name}"')
        lines.append("")
        lines.append(value)
    lines.append(f"--{boundary}--")
    body = ("\r\n".join(lines)).encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"


class BridgeSender:
    """Outbound path: the SAME loopback gateway the webphone uses
    (POST /gateway/message, bearer gateway secret) — MMS staging,
    Telnyx rejections and honest limits all come along for free."""

    def __init__(self, config):
        self.config = config

    def send(self, contact, text):
        if not self.config.gateway_secret:
            raise GatewayError(
                "gateway secret credential missing — the unit's LoadCredential "
                "source does not exist or is unreadable; autonomous sends and "
                "approvals stay pending until it is fixed",
                status=503,
            )
        body, content_type = encode_multipart({"to": with_plus(contact), "body": text})
        request = urllib.request.Request(
            f"{self.config.bridge_url}/gateway/message",
            data=body,
            headers={
                "Content-Type": content_type,
                "Authorization": f"Bearer {self.config.gateway_secret}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:500]
            raise GatewayError(
                f"bridge refused: HTTP {error.code}: {detail}", status=502
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            raise GatewayError(f"bridge unreachable: {error}", status=502) from error
        return payload.get("provider_ref")


# ---------------------------------------------------------------- lens


class LensContext:
    """Call-history context from the loopback lens (idea 37): one
    export.jsonl sweep, client-side filtered to the contact. A down
    lens degrades to no context — never a failed draft."""

    def __init__(self, config):
        self.config = config
        self.cached_at = 0
        self.cache = []
        self.lock = threading.Lock()

    def _refresh(self):
        after = time.strftime(
            "%Y-%m-%d",
            time.gmtime(time.time() - self.config.lens_context_days * 86400),
        )
        url = f"{self.config.lens_url}/api/export.jsonl?after={after}"
        request = urllib.request.Request(url)
        rows = []
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                for line in response.read().decode("utf-8", "replace").splitlines():
                    if not line.strip():
                        continue
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            log(f"lens context unavailable: {error}")
        with self.lock:
            self.cache = rows
            self.cached_at = time.time()

    def timeline(self, contact, limit=6):
        if not self.config.lens_url:
            return []
        with self.lock:
            fresh = time.time() - self.cached_at < 900
            rows = list(self.cache)
        if not fresh:
            self._refresh()
            with self.lock:
                rows = list(self.cache)
        matched = []
        for row in rows:
            if row.get("export_incomplete"):
                continue
            if (
                normalize_contact(str(row.get("from_number", ""))) == contact
                or normalize_contact(str(row.get("to_number", ""))) == contact
            ):
                matched.append(row)
        matched.sort(key=lambda row: str(row.get("started_at", "")), reverse=True)
        return matched[:limit]


# ---------------------------------------------------------------- esl


class EsIListener:
    """Event-socket listener for presence + missed calls.

    Subscribes to CHANNEL_CREATE / CHANNEL_ANSWER /
    CHANNEL_HANGUP_COMPLETE only — this service never issues commands,
    so the client is a deliberate subset of the voice agent's ESL
    machinery. Reconnects with backoff; presence degrades to
    schedule-only while disconnected."""

    def __init__(self, config, presence, on_missed_call):
        self.config = config
        self.presence = presence
        self.on_missed_call = on_missed_call
        self.stop = threading.Event()
        self.sock = None

    def _read_frame(self, file_handle):
        headers = {}
        while True:
            line = file_handle.readline()
            if not line:
                raise ConnectionError("ESL closed the connection")
            line = line.decode("utf-8", "replace").strip()
            if not line:
                break
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        length = int(headers.get("content-length", "0") or 0)
        body = file_handle.read(length) if length else b""
        return (headers.get("content-type", ""), body.decode("utf-8", "replace"))

    def _send(self, payload):
        self.sock.sendall(payload.encode("utf-8"))

    def run(self):
        backoff = 5
        while not self.stop.is_set():
            try:
                self._session()
                backoff = 5
            except (ConnectionError, OSError, ValueError) as error:
                self.presence.esl_connected = False
                log(f"event socket down ({error}); retrying in {backoff}s")
                self.stop.wait(backoff)
                backoff = min(backoff * 2, 120)

    def _session(self):
        config = self.config
        self.sock = socket.create_connection(
            (config.esl_host, config.esl_port), timeout=10
        )
        self.sock.settimeout(None)
        file_handle = self.sock.makefile("rb")
        content_type, _ = self._read_frame(file_handle)
        if content_type != "auth/request":
            raise ConnectionError(f"unexpected ESL greeting: {content_type}")
        self._send(f"auth {config.esl_password}\n\n")
        content_type, body = self._read_frame(file_handle)
        if "ok" not in body.lower():
            raise ConnectionError(f"ESL auth refused: {body.strip()[:120]}")
        self._send(
            "events plain CHANNEL_CREATE CHANNEL_ANSWER CHANNEL_HANGUP_COMPLETE\n\n"
        )
        content_type, body = self._read_frame(file_handle)
        if "ok" not in body.lower():
            raise ConnectionError(f"ESL subscription refused: {body.strip()[:120]}")
        self.presence.esl_connected = True
        log("event socket connected (presence + missed calls)")
        while not self.stop.is_set():
            content_type, body = self._read_frame(file_handle)
            if content_type != "text/event-plain":
                continue
            event = {}
            for line in body.splitlines():
                if ": " in line:
                    key, value = line.split(": ", 1)
                    event[key.strip()] = value.strip()
            self._handle(event)

    def _handle(self, event):
        name = event.get("Event-Name", "")
        uuid = event.get("Unique-ID", "")
        if name == "CHANNEL_CREATE":
            self.presence.channel_up(uuid)
            direction = (event.get("Call-Direction") or "").lower()
            if direction == "inbound":
                self.presence.track_inbound(
                    uuid,
                    normalize_contact(event.get("Caller-Caller-ID-Number", "")),
                )
        elif name == "CHANNEL_ANSWER":
            self.presence.channel_answered(uuid)
        elif name == "CHANNEL_HANGUP_COMPLETE":
            answered = self.presence.channel_down(uuid)
            if answered is False and self.config.missed_call_enabled:
                caller = self.presence.inbound_caller(uuid)
                if caller:
                    self.on_missed_call(caller, uuid)


class Presence:
    """Presence state: busy while any channel is up, DND/vacation
    toggles persisted, owner desk activity from review-API touches."""

    def __init__(self, state):
        self.state = state
        self.esl_connected = False
        self._lock = threading.Lock()
        self._channels = {}
        self._owner_last_seen = 0.0
        self._inbound = {}

    def channel_up(self, uuid):
        with self._lock:
            self._channels[uuid] = {"answered": False}

    def track_inbound(self, uuid, caller):
        with self._lock:
            self._inbound[uuid] = caller

    def inbound_caller(self, uuid):
        with self._lock:
            return self._inbound.pop(uuid, None)

    def channel_answered(self, uuid):
        with self._lock:
            if uuid in self._channels:
                self._channels[uuid]["answered"] = True

    def channel_down(self, uuid):
        """Returns False when an inbound channel ended unanswered."""
        with self._lock:
            entry = self._channels.pop(uuid, None)
            return bool(entry and entry.get("answered"))

    def touch_owner(self):
        with self._lock:
            self._owner_last_seen = time.time()

    def owner_at_desk(self, within=900):
        with self._lock:
            return (time.time() - self._owner_last_seen) < within

    def snapshot(self):
        with self._lock:
            busy = bool(self._channels)
        overrides = self.state.presence_overrides()
        return {
            "busy": busy,
            "dnd": bool(overrides.get("dnd")),
            "vacation": bool(overrides.get("vacation")),
            "owner_at_desk": self.owner_at_desk(),
            "esl_connected": self.esl_connected,
        }


# ---------------------------------------------------------------- autopilot


class Autopilot:
    """The mode matrix and the safety stack around it."""

    def __init__(self, config, state, gemini, sender, lens, presence):
        self.config = config
        self.state = state
        self.gemini = gemini
        self.sender = sender
        self.lens = lens
        self.presence = presence
        # The env mode is the DEFAULT; a runtime override (set through
        # the review API from the webphone) wins until it is reset.
        self.default_mode = config.mode
        self.mode_override = state.mode_override() if state is not None else None
        self.mode = self.mode_override or self.default_mode

    def mode_source(self):
        return "runtime" if self.mode_override else "config"

    def set_mode(self, mode):
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r} — one of {', '.join(MODES)}")
        self.mode_override = mode
        self.mode = mode
        if self.state is not None:
            self.state.set_mode_override(mode)
            self.state.audit("mode_changed", mode=mode, source="runtime")
        log(f"autopilot mode set to {mode} (runtime override)")
        return mode

    def reset_mode(self):
        self.mode_override = None
        self.mode = self.default_mode
        if self.state is not None:
            self.state.set_mode_override(None)
            self.state.audit("mode_reset", mode=self.mode, source="config")
        log(f"autopilot mode reset to the configured {self.mode}")
        return self.mode

    def mode_payload(self):
        return {
            "mode": self.mode,
            "mode_source": self.mode_source(),
            "default_mode": self.default_mode,
            "modes": list(MODES),
        }

    def is_suppressed(self, contact):
        return contact in self.state.suppression()

    def is_vip(self, contact):
        return contact in self.config.vip_numbers

    def after_hours(self, now_minutes=None):
        minutes = now_minutes if now_minutes is not None else minutes_now()
        start, end = self.config.working_start, self.config.working_end
        if start == end:
            return True
        if start < end:
            return not (start <= minutes < end)
        # window wraps midnight (e.g. 18:00-09:00)
        return not (minutes >= start or minutes < end)

    def auto_eligible(self, contact):
        """The full gate stack; returns (eligible, reason)."""
        if self.mode in ("off", "drafts"):
            return False, f"mode={self.mode} never auto-sends"
        if self.is_suppressed(contact):
            return False, "contact opted out (STOP)"
        conversation = self.state.conversation(contact)
        if conversation.get("frozen"):
            return False, conversation["frozen"]
        if self.is_vip(contact):
            return False, "VIP contact: human approval required"
        if self.mode == "after-hours":
            snapshot = self.presence.snapshot()
            if snapshot["owner_at_desk"] and not (
                snapshot["busy"] or snapshot["dnd"] or snapshot["vacation"]
            ):
                return False, "the owner is at the desk right now — draft only"
            if not (
                self.after_hours()
                or snapshot["busy"]
                or snapshot["dnd"]
                or snapshot["vacation"]
            ):
                return False, "working hours and the owner is reachable — draft only"
        return True, ""

    def build_prompt(self, contact, trigger, note=None):
        config = self.config
        conversation = self.state.conversation(contact)
        history = conversation.get("messages", [])[-config.history_messages :]
        owner = config.owner_name or "the account owner"
        lines = [
            f"You are drafting an SMS reply for {owner}.",
            f"Contact: {with_plus(contact)}",
            f"Trigger: {trigger}.",
            f"Household languages: {', '.join(config.languages)}.",
        ]
        if note:
            lines.append(f"Context: {note}")
        preferences = self.state.preferences(contact).get("rules", [])
        if preferences:
            lines.append("Learned preferences (the human changed drafts like this):")
            for rule in preferences[-5:]:
                lines.append(
                    f'- draft "{rule["draft"][:200]}" was corrected to '
                    f'"{rule["approved"][:200]}"'
                )
        memory = self.state.memory(contact)
        if memory:
            lines.append("Contact memory (human-confirmed notes):")
            for note_text in memory[-8:]:
                lines.append(f"- {str(note_text)[:200]}")
        timeline = self.lens.timeline(contact)
        if timeline:
            lines.append("Recent call history with this contact (newest first):")
            for row in timeline:
                when = str(row.get("started_at", ""))[:16]
                direction = row.get("direction", "?")
                duration = row.get("duration_secs", "?")
                lines.append(
                    f"- {when} {direction} call, {duration}s"
                    f"{' (AI)' if row.get('is_ai') else ''}"
                )
        if history:
            lines.append("Conversation (oldest first, direction in/out):")
            for message in history:
                marker = "->" if message.get("direction") == "out" else "<-"
                who = (
                    "AI"
                    if message.get("by_ai")
                    else ("owner" if message.get("direction") == "out" else "contact")
                )
                text = str(message.get("text", ""))[:500]
                lines.append(f"{marker} {who}: {text}")
        hint = None
        for message in reversed(history):
            if message.get("direction") == "in" and message.get("text"):
                hint = detect_language_hint(message["text"])
                break
        if hint:
            lines.append(
                f'The contact appears to write in language "{hint}" '
                f"— answer in it unless the history says otherwise."
            )
        lines.append("Draft the reply now.")
        return "\n".join(lines)

    def generate_draft(self, contact, trigger, note=None):
        if self.config.api_key_placeholder:
            raise GeminiError(
                "the Gemini API key is a placeholder — push the real key "
                "(push-secrets) and restart the unit; inbound recording and "
                "the review surfaces keep working, drafting fails closed"
            )
        prompt = self.build_prompt(contact, trigger, note)
        result = self.gemini.draft(prompt)
        draft_id = hashlib.sha1(
            f"{contact}:{trigger}:{time.time_ns()}".encode()
        ).hexdigest()[:16]
        draft = {
            "id": draft_id,
            "contact": contact,
            "trigger": trigger,
            "text": result["text"],
            "en_gloss": result["en_gloss"],
            "language": result["language"],
            "confidence": result["confidence"],
            "status": "pending",
            "created_at": now_iso(),
        }
        self.state.create_draft(draft)
        # Latest wins: a fresh draft for a contact supersedes the older
        # pending one (a reply drafted now is better evidence than a
        # reply drafted three messages ago).
        for stale in self.state.list_drafts():
            if stale["id"] != draft_id and stale["contact"] == contact:
                self.state.update_draft(
                    stale["id"], status="superseded", superseded_by=draft_id
                )
        return draft

    def suppress_if_opt_out(self, contact, text):
        first_line = (text or "").strip().splitlines()[0].strip() if text else ""
        keyword = first_line.upper().replace("!", "").replace(".", "")
        for candidate in self.config.opt_out_keywords:
            if keyword == candidate.upper():
                self.state.suppress(contact, candidate, (text or "")[:200])
                return True
        return False

    def maybe_send_automatically(self, draft):
        contact = draft["contact"]
        eligible, reason = self.auto_eligible(contact)
        if not eligible:
            self.state.audit(
                "auto_skipped", contact=contact, draft=draft["id"], reason=reason
            )
            return draft, reason
        if draft.get("confidence", 0) < self.config.confidence_threshold:
            reason = (
                f"confidence {draft.get('confidence')} below threshold "
                f"{self.config.confidence_threshold}"
            )
            self.state.audit(
                "auto_skipped", contact=contact, draft=draft["id"], reason=reason
            )
            return draft, reason
        text = draft["text"]
        signature = self.config.signature()
        if signature and signature not in text:
            text = f"{text}\n{signature}"
        return self._send_draft(draft, text, by_ai=True)

    def _send_draft(self, draft, text, by_ai):
        contact = draft["contact"]
        try:
            provider_ref = self.sender.send(contact, text)
        except GatewayError as error:
            self.state.audit(
                "send_failed",
                contact=contact,
                draft=draft["id"],
                by_ai=by_ai,
                error=str(error),
            )
            updated = self.state.update_draft(
                draft["id"], status="pending", send_error=str(error)
            )
            return updated or draft, str(error)
        updated = self.state.update_draft(
            draft["id"],
            status="sent",
            sent_text=text,
            sent_at=now_iso(),
            sent_by="ai" if by_ai else "human",
            provider_ref=provider_ref,
            send_error=None,
        )
        self.state.append_message(
            contact,
            {
                "ts": now_iso(),
                "direction": "out",
                "text": text,
                "by_ai": by_ai,
                "provider_ref": provider_ref,
            },
        )
        if by_ai:
            frozen = self.state.mark_auto_sent(
                contact, self.config.max_auto_per_conversation
            )
            if frozen:
                self.state.audit("kill_switch_armed", contact=contact, reason=frozen)
        return updated or draft, None

    def handle_inbound(self, contact, text, message_id):
        if self.suppress_if_opt_out(contact, text):
            log(f"opt-out recorded for {contact}")
            return
        if self.is_suppressed(contact):
            self.state.audit("inbound_suppressed", contact=contact)
            return
        if self.mode == "off":
            return
        try:
            draft = self.generate_draft(contact, f"inbound:{message_id or 'event'}")
        except GeminiError as error:
            log(f"draft for {contact} failed: {error}")
            self.state.audit("draft_failed", contact=contact, error=str(error))
            return
        draft, skip_reason = self.maybe_send_automatically(draft)
        if skip_reason:
            log(f"draft {draft['id']} pending for {contact}: {skip_reason}")

    def handle_missed_call(self, caller, uuid):
        if not caller or self.is_suppressed(caller):
            return
        if self.mode == "off":
            return
        note = "The contact just tried to call and it rang out unanswered."
        transcript = self._transcript_excerpt(uuid)
        if transcript:
            note += (
                f" An AI voice agent answered part of the call; excerpt: {transcript}"
            )
        try:
            draft = self.generate_draft(caller, f"missedcall:{uuid}", note=note)
        except GeminiError as error:
            log(f"missed-call draft for {caller} failed: {error}")
            self.state.audit(
                "draft_failed",
                contact=caller,
                trigger=f"missedcall:{uuid}",
                error=str(error),
            )
            return
        self.state.audit("missed_call_draft", contact=caller, draft=draft["id"])
        self.maybe_send_automatically(draft)

    def _transcript_excerpt(self, uuid):
        if not self.config.transcripts_dir:
            return ""
        path = os.path.join(self.config.transcripts_dir, f"{uuid}.jsonl")
        try:
            with open(path, encoding="utf-8") as handle:
                turns = []
                for line in handle:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if record.get("type") in ("caller", "agent"):
                        text = str(record.get("text", ""))[:200]
                        if text:
                            turns.append(f"{record['type']}: {text}")
                return " | ".join(turns[-6:])
        except OSError:
            return ""

    def request_escalation_check(self, contact, inbound_text):
        """The kill-switch's second arm: a contact asking for a human
        freezes the conversation for autonomous paths immediately."""
        if not inbound_text:
            return
        for pattern in HUMAN_REQUEST_PATTERNS:
            if pattern.search(inbound_text):
                reason = "contact asked for a human (escalation pattern)"
                self.state.freeze(contact, reason)
                self.state.audit("kill_switch_armed", contact=contact, reason=reason)
                return


# ---------------------------------------------------------------- briefing


class Briefing:
    """The daily digest: overnight traffic, AI answers, needs-you,
    missed calls, opt-outs, backup verdict — served on the review API
    and optionally mailed sendmail-style."""

    def __init__(self, config, state, autopilot):
        self.config = config
        self.state = state
        self.autopilot = autopilot
        self.stop = threading.Event()
        self._last_date = None

    def assemble(self):
        state = self.state
        suppression = state.suppression()
        drafts = state.list_drafts(statuses=("pending",))
        sent = state.list_drafts(statuses=("sent",))
        recent_sent = [
            d for d in sent if (time.time() - _parse_iso_age(d.get("sent_at"))) < 86400
        ]
        auto_sent = [d for d in recent_sent if d.get("sent_by") == "ai"]
        conversations = []
        try:
            names = os.listdir(state._path("conversations"))
        except OSError:
            names = []
        needs_human = []
        for name in names:
            if not name.endswith(".json"):
                continue
            conversation = state._read(state._path("conversations", name), {})
            if conversation.get("frozen"):
                needs_human.append(
                    f"- {with_plus(conversation.get('contact', '?'))}: "
                    f"{conversation['frozen']}"
                )
        owner = self.config.owner_name or "the owner"
        lines = [
            f"# Morning briefing for {owner} — {time.strftime('%Y-%m-%d')}",
            "",
            f"- Pending drafts waiting for review: **{len(drafts)}**",
            f"- Sent in the last 24h: {len(recent_sent)} "
            f"({len(auto_sent)} autonomous, {len(recent_sent) - len(auto_sent)} approved)",
            f"- Conversations needing a human: {len(needs_human)}",
            f"- Opted-out contacts: {len(suppression)}",
        ]
        for draft in drafts[:10]:
            lines.append(
                f"- Draft for {with_plus(draft.get('contact', '?'))} "
                f"(confidence {draft.get('confidence', '?')}%): "
                f'"{(draft.get("text") or "")[:120]}"'
            )
        if needs_human:
            lines.append("")
            lines.append("## Needs you")
            lines.extend(needs_human[:10])
        if suppression:
            lines.append("")
            lines.append("## Opt-outs")
            for contact, entry in list(suppression.items())[:10]:
                lines.append(
                    f"- {with_plus(contact)} opted out {entry.get('since', '?')} "
                    f"(keyword: {entry.get('keyword', '?')})"
                )
        digest = {
            "generated_at": now_iso(),
            "pending_drafts": len(drafts),
            "sent_24h": len(recent_sent),
            "auto_sent_24h": len(auto_sent),
            "needs_human": len(needs_human),
            "suppressed": len(suppression),
            "markdown": "\n".join(lines) + "\n",
        }
        state.save_briefing(digest)
        return digest

    def mail(self, digest):
        config = self.config
        if not (config.mailer_command and config.briefing_to):
            return False
        message = (
            f"From: {config.briefing_from or config.briefing_to}\n"
            f"To: {config.briefing_to}\n"
            f"Subject: Morning briefing {time.strftime('%Y-%m-%d')}\n"
            f"Date: {email.utils.formatdate()}\n"
            f"Message-ID: <{int(time.time())}.textagent@localhost>\n"
            "Content-Type: text/plain; charset=utf-8\n"
            "\n"
            f"{digest['markdown']}\n"
        )
        try:
            result = subprocess.run(
                [
                    config.mailer_command,
                    "-f",
                    config.briefing_from or config.briefing_to,
                    "-t",
                    config.briefing_to,
                ],
                input=message.encode("utf-8"),
                capture_output=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            log(f"briefing mail failed: {error}")
            return False
        if result.returncode != 0:
            log(
                f"briefing mailer exited {result.returncode}: "
                f"{result.stderr.decode('utf-8', 'replace')[:200]}"
            )
            return False
        return True

    def run(self):
        while not self.stop.is_set():
            local = time.localtime()
            if local.tm_hour == self.config.briefing_hour:
                date = time.strftime("%Y-%m-%d")
                if date != self._last_date:
                    self._last_date = date
                    digest = self.assemble()
                    mailed = self.mail(digest)
                    log(
                        f"briefing assembled (pending={digest['pending_drafts']}, "
                        f"mailed={mailed})"
                    )
            self.stop.wait(600)


def _parse_iso_age(stamp):
    """Seconds since an ISO-UTC stamp; unparseable stamps read as ancient."""
    try:
        parsed = time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return float("inf")
    return calendar.timegm(parsed)


# ---------------------------------------------------------------- review api


class ReviewApi:
    def __init__(self, config, state, autopilot, presence, gemini):
        self.config = config
        self.state = state
        self.autopilot = autopilot
        self.presence = presence
        self.gemini = gemini
        self.started = time.time()

    def health(self):
        conversation_count = 0
        try:
            conversation_count = len(
                [
                    name
                    for name in os.listdir(self.state._path("conversations"))
                    if name.endswith(".json")
                ]
            )
        except OSError:
            pass
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - self.started),
            "api_key_configured": not self.config.api_key_placeholder,
            "gateway_secret_configured": bool(self.config.gateway_secret),
            "system_prompt_configured": bool(self.config.system_prompt),
            "mode": self.autopilot.mode,
            "mode_source": self.autopilot.mode_source(),
            "default_mode": self.autopilot.default_mode,
            "presence": self.presence.snapshot(),
            "conversations": conversation_count,
            "pending_drafts": len(self.state.list_drafts()),
            "suppressed": len(self.state.suppression()),
        }


class ApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    api: ReviewApi = None  # injected by serve()

    def log_message(self, fmt, *args):
        print(f"[{LOG_PREFIX}] api {fmt % args}", flush=True)

    def send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            declared = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            declared = 0
        if declared > MAX_API_BODY:
            raise ValueError("request body too large")
        raw = self.rfile.read(declared) if declared else b""
        if not raw:
            return {}
        payload = json.loads(raw.decode("utf-8", "replace"))
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def authorized(self):
        secret = self.api.config.shared_secret
        if not secret:
            self.send_json(
                503,
                {
                    "error": "shared secret credential missing — the unit's "
                    "LoadCredential source does not exist; fix the "
                    "secret file and restart the unit",
                },
            )
            return False
        presented = None
        header = self.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            presented = header[len("Bearer ") :].strip()
        if presented is None or not hmac.compare_digest(presented, secret):
            self.send_json(
                401,
                {
                    "error": "missing or invalid Authorization: "
                    "Bearer <textagent shared secret>"
                },
            )
            return False
        self.api.presence.touch_owner()
        return True

    def route(self, method):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        segments = [segment for segment in path.split("/") if segment]
        try:
            if method == "GET":
                if path == "/health":
                    return self.send_json(200, self.api.health())
                if not self.authorized():
                    return
                if path == "/reviews":
                    return self.handle_reviews()
                if path == "/briefing/latest":
                    digest = self.api.state._read(
                        self.api.state._path("briefing", "latest.json"), None
                    )
                    if digest is None:
                        return self.send_json(
                            404,
                            {
                                "error": "no briefing assembled yet — it "
                                "lands daily at the configured hour"
                            },
                        )
                    return self.send_json(200, digest)
                if path == "/suppression":
                    return self.send_json(200, self.api.state.suppression())
                if len(segments) == 2 and segments[0] == "conversations":
                    return self.handle_conversation_get(segments[1])
                return self.send_json(404, {"error": "not found"})
            if method != "POST" or not self.authorized():
                if method != "POST":
                    return self.send_json(405, {"error": "method not allowed"})
                return
            if path == "/draft":
                return self.handle_draft()
            if path == "/translate":
                return self.handle_translate()
            if path == "/presence":
                return self.handle_presence()
            if path == "/mode":
                return self.handle_mode()
            if len(segments) == 3 and segments[0] == "reviews":
                return self.handle_review_action(segments[1], segments[2])
            if (
                len(segments) == 3
                and segments[0] == "suppression"
                and segments[2] == "reset"
            ):
                return self.handle_suppression_reset(segments[1])
            if (
                len(segments) == 3
                and segments[0] == "conversations"
                and segments[2] in ("memory", "resume", "preferences")
            ):
                return self.handle_conversation_post(segments[1], segments[2])
            return self.send_json(404, {"error": "not found"})
        except ValueError as error:
            return self.send_json(400, {"error": str(error)})
        except GeminiError as error:
            return self.send_json(503, {"error": str(error)})
        except GatewayError as error:
            return self.send_json(error.status, {"error": str(error)})
        except Exception as error:
            # One broken route never takes the API down.
            log(f"route error on {method} {path}: {error!r}")
            return self.send_json(500, {"error": f"internal error: {error}"})

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def handle_reviews(self):
        drafts = self.api.state.list_drafts()
        suppression = self.api.state.suppression()
        frozen = []
        try:
            names = os.listdir(self.api.state._path("conversations"))
        except OSError:
            names = []
        for name in names:
            if not name.endswith(".json"):
                continue
            conversation = self.api.state._read(
                self.api.state._path("conversations", name), {}
            )
            if conversation.get("frozen"):
                frozen.append(
                    {
                        "contact": conversation.get("contact"),
                        "reason": conversation["frozen"],
                    }
                )
        payload = {
            "drafts": drafts,
            "frozen": frozen,
            "suppressed": [
                {"contact": contact, **entry} for contact, entry in suppression.items()
            ],
            "presence": self.api.presence.snapshot(),
            "mode": self.api.autopilot.mode,
            "mode_source": self.api.autopilot.mode_source(),
            "default_mode": self.api.autopilot.default_mode,
            "modes": list(MODES),
        }
        self.send_json(200, payload)

    def handle_review_action(self, draft_id, action):
        payload = self.read_json()
        wanted = self.api.state.draft(draft_id)
        if wanted is None:
            return self.send_json(404, {"error": f"no draft {draft_id}"})
        if wanted.get("status") != "pending":
            return self.send_json(
                409,
                {"error": f"draft {draft_id} is {wanted.get('status')}, not pending"},
            )
        if action == "discard":
            updated = self.api.state.update_draft(
                draft_id, status="discarded", discarded_at=now_iso()
            )
            return self.send_json(200, updated)
        if action == "approve":
            text = (payload.get("text") or wanted.get("text") or "").strip()
            if not text:
                return self.send_json(400, {"error": "approve needs text"})
            if (payload.get("text") or "").strip() and payload["text"].strip() != (
                wanted.get("text") or ""
            ).strip():
                self.api.state.record_correction(
                    wanted["contact"], wanted.get("text", ""), payload["text"]
                )
            updated, error = self.api.autopilot._send_draft(wanted, text, by_ai=False)
            if error:
                return self.send_json(502, {"error": error, "draft": updated})
            return self.send_json(200, updated)
        if action == "edit":
            text = (payload.get("text") or "").strip()
            if not text:
                return self.send_json(400, {"error": "edit needs text"})
            self.api.state.record_correction(
                wanted["contact"], wanted.get("text", ""), text
            )
            updated = self.api.state.update_draft(
                draft_id, text=text, edited_at=now_iso()
            )
            return self.send_json(200, updated)
        return self.send_json(404, {"error": f"unknown action {action}"})

    def handle_draft(self):
        payload = self.read_json()
        contact = normalize_contact(payload.get("to", ""))
        if not contact:
            return self.send_json(400, {"error": "to (contact number) is required"})
        draft = self.api.autopilot.generate_draft(
            contact, "ondemand", note=payload.get("hint")
        )
        return self.send_json(200, draft)

    def handle_translate(self):
        payload = self.read_json()
        text = (payload.get("text") or "").strip()
        if not text:
            return self.send_json(400, {"error": "text is required"})
        if self.api.config.api_key_placeholder:
            raise GeminiError(
                "the Gemini API key is a placeholder — translation needs the "
                "real key (push-secrets + restart)"
            )
        translated = self.api.gemini.translate(
            text, payload.get("to", ""), payload.get("tone", "")
        )
        return self.send_json(200, {"text": translated})

    def handle_presence(self):
        payload = self.read_json()
        flags = {}
        if "dnd" in payload:
            flags["dnd"] = bool(payload["dnd"])
        if "vacation" in payload:
            flags["vacation"] = bool(payload["vacation"])
        updated = self.api.state.set_presence_overrides(**flags)
        return self.send_json(
            200,
            {
                "overrides": updated,
                "presence": self.api.presence.snapshot(),
            },
        )

    def handle_mode(self):
        """Runtime autopilot switch: the webphone's drafts panel posts
        here. `{"mode": "off"|"drafts"|"after-hours"|"full"}` pins an
        override; `{"reset": true}` drops it and returns to the
        configured default. Safety gates (suppression, VIP, kill
        switch, confidence) are unchanged by a mode flip."""
        payload = self.read_json()
        if payload.get("reset"):
            mode = self.api.autopilot.reset_mode()
        else:
            mode = self.api.autopilot.set_mode(str(payload.get("mode", "")).strip())
        body = self.api.autopilot.mode_payload()
        body["mode"] = mode
        return self.send_json(200, body)

    def handle_suppression_reset(self, contact):
        contact = normalize_contact(contact)
        if self.api.state.unsuppress(contact):
            return self.send_json(200, {"contact": contact, "reset": True})
        return self.send_json(404, {"error": f"{contact} was not suppressed"})

    def handle_conversation_get(self, contact):
        contact = normalize_contact(contact)
        conversation = self.api.state.conversation(contact)
        self.send_json(
            200,
            {
                "contact": contact,
                "messages": conversation.get("messages", []),
                "frozen": conversation.get("frozen"),
                "consecutive_auto": conversation.get("consecutive_auto", 0),
                "memory": self.api.state.memory(contact),
                "preferences": self.api.state.preferences(contact).get("rules", []),
                "suppressed": contact in self.api.state.suppression(),
                "vip": self.api.autopilot.is_vip(contact),
            },
        )

    def handle_conversation_post(self, contact, action):
        contact = normalize_contact(contact)
        if action == "resume":
            self.api.state.resume(contact)
            return self.send_json(200, {"contact": contact, "resumed": True})
        payload = self.read_json()
        if action == "memory":
            if "notes" in payload:
                if not isinstance(payload["notes"], list):
                    return self.send_json(400, {"error": "notes must be a list"})
                self.api.state.set_memory(contact, payload["notes"])
            elif payload.get("append"):
                notes = self.api.state.memory(contact)
                notes.append(str(payload["append"])[:500])
                self.api.state.set_memory(contact, notes)
            elif payload.get("clear"):
                self.api.state.set_memory(contact, [])
            return self.send_json(200, {"memory": self.api.state.memory(contact)})
        if action == "preferences":
            if payload.get("reset"):
                self.api.state.reset_preferences(contact)
            return self.send_json(
                200,
                {"preferences": self.api.state.preferences(contact).get("rules", [])},
            )
        return self.send_json(404, {"error": "not found"})


def serve(api, port):
    ApiHandler.api = api
    server = ThreadingHTTPServer(("127.0.0.1", port), ApiHandler)
    thread = threading.Thread(
        target=server.serve_forever, daemon=True, name="review-api"
    )
    thread.start()
    return server


# ---------------------------------------------------------------- inbound event glue


def make_event_handler(config, state, autopilot):
    own_did = normalize_contact(env("TEXTAGENT_OWN_DID", ""))

    def normalize(event):
        """Extract (event_type, payload) from a receiver JSONL line.

        The receiver logs the whole Telnyx envelope:
        {"received_at", "remote", "body": {"data": {"event_type",
        "payload": {...}}}}. The raw {"data": {...}} top-level shape is
        accepted too (unit fixtures and any future producer)."""
        raw_body = event.get("body") if isinstance(event.get("body"), dict) else {}
        data = (
            raw_body.get("data")
            if isinstance(raw_body.get("data"), dict)
            else event.get("data")
        )
        if not isinstance(data, dict):
            data = {}
        event_type = (
            data.get("event_type") or event.get("event_type") or event.get("type") or ""
        )
        payload = data.get("payload") if isinstance(data.get("payload"), dict) else data
        return str(event_type), payload if isinstance(payload, dict) else {}

    def known_provider_ref(reference):
        # An outbound we see in the JSONL matches OUR send when the
        # provider_ref was recorded on a draft (AI or approved). Owner
        # sends through webphone carry refs we never recorded.
        if not reference:
            return None
        for draft in state.list_drafts(statuses=("sent",)):
            if draft.get("provider_ref") == reference:
                return draft
        return None

    def on_event(event):
        event_type, data = normalize(event)
        if event_type == "message.received":
            contact = normalize_contact(
                (data.get("from") or {}).get("phone_number", "")
                or str(data.get("from_number", ""))
            )
            text = data.get("text", "") or ""
            message_id = data.get("id", "")
            if not contact:
                return
            # Payload-id dedupe under the envelope: a Telnyx retry writes
            # a NEW line (new received_at) whose sha differs — the tail's
            # message_id check is the real guard.
            if message_id:
                existing = state.conversation(contact)
                if any(
                    m.get("message_id") == message_id
                    for m in existing.get("messages", [])
                ):
                    return
            state.append_message(
                contact,
                {
                    "ts": now_iso(),
                    "direction": "in",
                    "text": text,
                    "media": bool(data.get("media", [])),
                    "message_id": message_id,
                },
            )
            autopilot.request_escalation_check(contact, text)
            autopilot.handle_inbound(contact, text, message_id)
        elif event_type in (
            "message.sent",
            "message.finalized",
            "message.delivery_updated",
        ):
            # Outbound legs: from == our DID. Attribute AI sends via the
            # recorded provider_ref; everything else is a human send
            # (webphone compose), which also resets the kill-switch.
            sender = normalize_contact(
                (data.get("from") or {}).get("phone_number", "")
                or str(data.get("from_number", ""))
            )
            contact = normalize_contact(
                ((data.get("to") or [{}])[0] or {}).get("phone_number", "")
                if isinstance(data.get("to"), list)
                else (data.get("to") or {}).get("phone_number", "")
                or str(data.get("to_number", ""))
            )
            if not contact or (own_did and sender != own_did):
                return
            if event_type == "message.sent" and data.get("id"):
                draft = known_provider_ref(data.get("id"))
                if draft is not None:
                    return  # already recorded at send time by _send_draft
            status = data.get("status") or data.get("to_status", "")
            existing = state.conversation(contact)
            reference = data.get("id", "")
            already = any(
                message.get("provider_ref") == reference and reference
                for message in existing.get("messages", [])
            )
            if already:
                return
            state.append_message(
                contact,
                {
                    "ts": now_iso(),
                    "direction": "out",
                    "text": data.get("text", "") or "",
                    "by_ai": False,
                    "provider_ref": reference,
                    "status": status,
                },
            )

    return on_event


# ---------------------------------------------------------------- main


def fatal(message):
    print(f"[{LOG_PREFIX}] FATAL: {message}", flush=True)
    raise SystemExit(2)


def main():
    config = Config()
    if config.shared_secret is None or not config.shared_secret:
        fatal("shared_secret credential missing")
    if config.system_prompt is None or not config.system_prompt:
        fatal("system_prompt credential missing")
    os.makedirs(config.state_dir, exist_ok=True)
    state = StateStore(config.state_dir)
    gemini = GeminiClient(config)
    sender = BridgeSender(config)
    lens = LensContext(config)
    presence = Presence(state)
    autopilot = Autopilot(config, state, gemini, sender, lens, presence)

    api = ReviewApi(config, state, autopilot, presence, gemini)
    server = serve(api, config.http_port)
    standby = " via " + ",".join(config.llm_fallbacks) if config.llm_fallbacks else ""
    log(
        f"review API on 127.0.0.1:{config.http_port} "
        f"(mode={autopilot.mode} [{autopilot.mode_source()}], "
        f"model={config.llm_model}{standby}, "
        f"key={'placeholder' if config.api_key_placeholder else 'configured'})"
    )

    if config.webhook_log:
        tailer = JsonlTailer(
            config.webhook_log, state, make_event_handler(config, state, autopilot)
        )
        threading.Thread(target=tailer.run, daemon=True, name="jsonl-tail").start()
    if config.esl_password:
        listener = EsIListener(config, presence, autopilot.handle_missed_call)
        threading.Thread(target=listener.run, daemon=True, name="esl-listener").start()
    else:
        log(
            "no event-socket password: presence degrades to schedule-only, "
            "missed-call follow-ups disabled"
        )

    briefing = Briefing(config, state, autopilot)
    threading.Thread(target=briefing.run, daemon=True, name="briefing").start()

    def sweep_forever():
        while True:
            time.sleep(3600)
            try:
                state.sweep_expired_drafts(config.draft_ttl)
            except OSError as error:
                log(f"draft sweep failed: {error}")

    threading.Thread(target=sweep_forever, daemon=True, name="draft-sweep").start()

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
