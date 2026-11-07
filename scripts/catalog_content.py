"""Content tables for the telephony catalog exporter.

scripts/export-catalog.py owns STRUCTURE only (frontmatter shapes, render
order, selftest, CLI); this module owns the CONTENT it renders: DOMAIN,
SERVICES, EVENTS, FLOWS, ADRS. Pure data, no imports — catalog content
changes land here, renderer changes stay out.
"""

# --------------------------------------------------------------------------
# Domain
# --------------------------------------------------------------------------

DOMAIN = {
    "id": "telephony",
    "name": "Telephony",
    # The domain id is SHARED with the pbx-lens source, and the union keeps
    # one body/summary (first source wins) while the `services:` list unions.
    # Agreeing on the identity text is the federation-correct move: a third
    # distinct summary would deepen the finding the hub's collision baseline
    # already carries for "domains/telephony/index.mdx|summary". This source
    # contributes MEMBERSHIP, not a renamed domain.
    "summary": "Call capture, enrichment, and retention across the pbx.artmann.tech stack.",
    "services": ["pbx", "pbx-voice-agent", "pbx-voicemail"],
    "body": """
Inbound calls land on a **DID lane**: one FreeSWITCH gateway per number,
each carrying its own priority and ACL, all of them rendering into the
`public` dialplan context as a `public_did_<gateway>` entry. From there the
stack has exactly three ways to answer, and the routing decision is a single
declarative knob per lane (`answerDids` intercept, else `didDestination`):

1. **A human** — a ring group offering the call to every member at once
   (`timeoutSec`), optionally behind a `timeWindow` (days + hours, with an
   `afterHoursDestination`).
2. **The voice agent** — a turn-based Gemini agent driving the parked
   channel over the FreeSWITCH event socket, with a transfer-to-human edge.
3. **Voicemail** — mod_voicemail deposit into the ring group's
   `voicemailMember` mailbox, then the transcript mailer.

Every answered call is recorded (WAV under `/var/lib/telephony/recordings`,
kept forever by default), and the call-history index reads the CDR, the
messaging webhook log and the agent transcripts.

<NodeGraph />

The two flows below are the honest pair: `inbound-call-routing` is the
intended ladder, and `inbound-call-unrecorded-loss` is the branch that has
no edge today — a call the agent answered, the owner never heard, and no
mailbox ever recorded.
""",
}


# --------------------------------------------------------------------------
# Services
# --------------------------------------------------------------------------

SERVICES = [
    {
        "id": "pbx",
        "name": "FreeSWITCH PBX",
        "summary": (
            "Generated FreeSWITCH configuration: one gateway lane per DID, "
            "ring groups with time windows, and the dialplan that decides "
            "who answers."
        ),
        "receives": ["call.invited"],
        "sends": ["call.ringgroup.offered", "call.abandoned.unrecorded"],
        "body": """
A NixOS-rendered FreeSWITCH configuration (`modules/telephony/pbx.nix`) plus
the upstream `services.freeswitch` unit. No FusionPBX/FreePBX: the XML is
generated from Nix, so every routing decision is reviewable in the same diff
as the number it applies to.

## Inbound path

Each `gateways.<name>` stanza renders a gateway plus a
`public_did_<name>` context entry. The lane carries the DID, a `priority`,
`allowedCidrs` (the provider's edge addresses, so an unlisted source is
rejected before any dialplan runs) and `didDestination` — an extension or a
ring group. Telnyx lanes run `register = false` (NOREG): the trunk is
permanently UP and each INVITE digest-authenticates on its own, which is what
survived the provider's nonce-rotation behaviour.

`services.telephony.agent.answerDids` intercepts a lane BEFORE its
`didDestination` is consulted, which is why adding or removing the agent from
a number is a one-line, per-lane decision.

## Answering a human

A ring group (`ringGroups.<id>`) rings all members simultaneously for
`timeoutSec`, then falls through to the `voicemailMember` mailbox (default:
the first member). `timeWindow` adds a schedule: `days`, `startHour`,
`endHour` and an optional `afterHoursDestination` (an extension, a ring
group, an IVR, or any dialplan destination) for evenings and weekends. The
window is evaluated in the host time zone.

## Recordings and state

`recording.enable` (default true) writes a stereo WAV per answered call;
`recording.retentionDays = null` keeps them forever. CDR lands as CSV under
the FreeSWITCH state tree, which the PBX host stages for backup.

## Dialplan surfaces

Extension dialling, an optional declarative IVR menu per extension
(`greetingSound` plus digit routes), a loopback read-only operator API, and
the voicemail keypad (`*98`) ride the same generated context.
""",
    },
    {
        "id": "pbx-voice-agent",
        "name": "PBX Voice Agent",
        "summary": (
            "Turn-based Gemini voice agent that answers designated DIDs over "
            "the FreeSWITCH event socket and transfers to a human on request."
        ),
        "receives": ["call.invited"],
        "sends": ["call.agent.answered"],
        "body": """
A loopback stdlib service (`modules/telephony/agent.nix`, extension `9100`)
that owns a parked channel over ESL and answers it in turns:

1. The greeting plays to completion (v1 has no barge-in — a caller who
   starts talking over it is dropped until it ends, which is why the
   greeting is configured as ONE short sentence).
2. Each turn records the caller with the media bug (`uuid_record`) and gates
   the window on agent-side speech energy, so a silent or empty take closes
   fast instead of burning a model round trip.
3. Transcribe + answer uses the Gemini flash tier with audio input; speech
   uses the Gemini 3.8 TTS tier.
4. DTMF `0`, or a spoken transfer request, bridges to
   `agent.transferDestination` (typically a ring group).

## Per-DID behaviour

`answerDids` selects which lanes the agent owns. `languageByDid` and
`greetingByDid` override the language and the greeting per number — the
prerequisite for answering a non-English lane at all.

## Failure modes that matter

- An unusable model does not degrade gracefully: a 503 or a hung call kills
  every turn, and only the journal says so. Pin `llmModel` away from a
  model that answers unhealthy.
- A PLACEHOLDER API key fails closed to the transfer destination.
- `maxCallSeconds` is a hard cap. There is **no hand-off edge to voicemail**
  — see the `inbound-call-unrecorded-loss` flow.
- The health endpoint is loopback-only, so a dead agent is invisible to
  every external monitor.
""",
    },
    {
        "id": "pbx-voicemail",
        "name": "PBX Voicemail",
        "summary": (
            "mod_voicemail deposit boxes with a transcript-pipelined mailer: "
            "WAV plus transcript to the extension's vmEmail."
        ),
        "receives": ["call.ringgroup.offered"],
        "sends": ["call.voicemail.deposited", "call.voicemail.notified"],
        "body": """
mod_voicemail, configured through the extension surface: `vmPassword`
(defaults to the extension number) and `vmEmail` (mod_voicemail's
`vm-mailto`). A ring group names which member's mailbox answers its
unanswered calls via `voicemailMember`.

## The mailer

`voicemail.mailerCommand` is FreeSWITCH's core `mailer-app`: it receives the
full RFC 5322 message on stdin and is invoked sendmail-style as
`mailerCommand -f <from> -t <to>`. `null` keeps the compiled-in `sendmail`
default, which stock NixOS hosts do not have — **without a mailer, vmEmail
messages silently go nowhere.** A transcript-pipelining wrapper (the host's
`telephony-voicemail-mailer`) prepends a Gemini transcript part ahead of the
WAV and rewrites the From header to one identity.

## State

Messages live in `/var/lib/private/freeswitch/db/voicemail_default.db` with
WAVs in the FreeSWITCH storage tree; the host registers both for backup
staging. Retrieval is the webphone voicemail panel (`/phone-api`),
`*98` keypad access, or the mail.

## The deposit leg is the weakest link

The deposit path is the only answer that works when nothing else does, and it
depends on storage permissions, a working mailer identity and a reachable
notification address. Operator evidence (pbx-artmann) has recorded deposits
failing while the mailbox tree existed and the mailer identity was refused at
DATA — treat "voicemail is enabled" and "voicemail works" as two different
claims, and prove the deposit before promising the surface.
""",
    },
]


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------

EVENTS = [
    {
        "id": "call.invited",
        "name": "Call Invited",
        "summary": "An inbound INVITE was accepted on a DID lane and entered the public dialplan.",
        "producer": "pbx",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["call_id", "did", "gateway", "direction", "received_at"],
            "properties": {
                "call_id": {
                    "type": "string",
                    "description": "FreeSWITCH channel UUID for the inbound leg.",
                },
                "did": {
                    "type": "string",
                    "description": "Dialled number in E.164 without the leading plus.",
                },
                "gateway": {
                    "type": "string",
                    "description": "Gateway lane that accepted the call (its public_did_<name> context).",
                },
                "direction": {"type": "string", "enum": ["inbound"]},
                "received_at": {"type": "string", "format": "date-time"},
                "caller_number": {
                    "type": ["string", "null"],
                    "description": "Asserted caller identity; null when the provider withheld it.",
                },
            },
        },
        "body": """
The routing entry point: a call is on a lane and the dialplan has not yet
decided who answers. Every other event in this domain is downstream of it.

`caller_number` is the asserted identity, not a verified one — the number a
caller claims is only as trustworthy as the carrier's attestation, which this
stack does not currently record.
""",
    },
    {
        "id": "call.agent.answered",
        "name": "Call Answered By Agent",
        "summary": "The voice agent took the call and owns the channel until transfer or hangup.",
        "producer": "pbx-voice-agent",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["call_id", "did", "extension", "language", "answered_at"],
            "properties": {
                "call_id": {"type": "string"},
                "did": {"type": "string"},
                "extension": {
                    "type": "string",
                    "description": "Agent extension that answered (default 9100).",
                },
                "language": {
                    "type": "string",
                    "description": "Language resolved for this DID (languageByDid, else the default).",
                },
                "answered_at": {"type": "string", "format": "date-time"},
                "model": {
                    "type": "string",
                    "description": "LLM id serving the conversation turns.",
                },
            },
        },
        "body": """
The agent answered, so from here the call is a conversation rather than a
ring. `language` is the resolved per-DID language — a number answered in a
language the caller does not speak is a routing defect, not a voice defect.

The event says the agent ANSWERED. It does not say the agent could THINK: a
dead model produces a call that is answered, silent, and eventually hung up.
""",
    },
    {
        "id": "call.ringgroup.offered",
        "name": "Call Offered To Ring Group",
        "summary": "A ring group started offering the call to its members for timeoutSec.",
        "producer": "pbx",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "call_id",
                "ring_group",
                "members",
                "timeout_secs",
                "offered_at",
            ],
            "properties": {
                "call_id": {"type": "string"},
                "ring_group": {
                    "type": "string",
                    "description": "Ring group extension, e.g. 2000.",
                },
                "members": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Extensions rung simultaneously.",
                },
                "timeout_secs": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Seconds to ring before falling through to voicemail.",
                },
                "offered_at": {"type": "string", "format": "date-time"},
                "within_time_window": {
                    "type": ["boolean", "null"],
                    "description": "Whether the call arrived inside the group's timeWindow; null when no window is configured.",
                },
            },
        },
        "body": """
A group rings all members at once and falls through to the voicemail member
when the timer expires. `within_time_window` is the honest version of "are we
open": null means the group rings around the clock, and a `false` here should
correspond to an `afterHoursDestination` in the lane's configuration.

`members` is the configured set, not the reachable set. A member with no
registered endpoint rings a phantom for the whole timeout, which is why the
gap between configured and reachable is the first thing to check when callers
report "it rang forever".
""",
    },
    {
        "id": "call.voicemail.deposited",
        "name": "Voicemail Deposited",
        "summary": "mod_voicemail stored a message (WAV, plus transcript when available) in an extension mailbox.",
        "producer": "pbx-voicemail",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["call_id", "mailbox", "duration_secs", "deposited_at"],
            "properties": {
                "call_id": {"type": "string"},
                "mailbox": {
                    "type": "string",
                    "description": "Extension owning the mailbox that took the message.",
                },
                "duration_secs": {"type": "number", "minimum": 0},
                "deposited_at": {"type": "string", "format": "date-time"},
                "transcript_available": {
                    "type": "boolean",
                    "description": "True when a transcript rode along with the WAV.",
                },
            },
        },
        "body": """
The deposit is the call's durable evidence: without it, a call that reached
no human left nothing behind. `duration_secs` near zero is the caller hanging
up on the greeting — a funnel signal, not a message.
""",
    },
    {
        "id": "call.voicemail.notified",
        "name": "Voicemail Notified",
        "summary": "The transcript mailer submitted the deposit to the mailbox owner's address.",
        "producer": "pbx-voicemail",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "call_id",
                "mailbox",
                "recipient",
                "transport",
                "accepted",
                "notified_at",
            ],
            "properties": {
                "call_id": {"type": "string"},
                "mailbox": {"type": "string"},
                "recipient": {
                    "type": "string",
                    "format": "email",
                    "description": "The extension's vmEmail address.",
                },
                "transport": {"type": "string", "enum": ["smtp"]},
                "accepted": {
                    "type": "boolean",
                    "description": "True only when the relay accepted the message (SMTP 2xx).",
                },
                "notified_at": {"type": "string", "format": "date-time"},
            },
        },
        "body": """
A deposit nobody hears is a lost call with extra steps, so notification is a
first-class outcome rather than a side effect of the mailer.

`accepted` is deliberately the relay's verdict, not "we invoked sendmail". A
sending identity the relay refuses (unverified sender domain) fails at DATA
after the deposit already succeeded — which surfaces here as `false` while
`call.voicemail.deposited` stays true. Watch for that pair: it is the
signature of a working mailbox with a broken notifier.
""",
    },
    {
        "id": "call.abandoned.unrecorded",
        "name": "Call Ended Unrecorded",
        "summary": "The call ended with neither a human nor a mailbox record — an invisible lost call.",
        "producer": "pbx",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["call_id", "did", "answered_by", "reason", "ended_at"],
            "properties": {
                "call_id": {"type": "string"},
                "did": {"type": "string"},
                "answered_by": {
                    "type": "string",
                    "enum": ["agent", "ring-group", "none"],
                    "description": "Who held the channel before it dropped.",
                },
                "reason": {
                    "type": "string",
                    "description": "Terminating cause, e.g. agent-model-unavailable, agent-turn-cap, voicemail-deposit-failed.",
                },
                "ended_at": {"type": "string", "format": "date-time"},
            },
        },
        "body": """
The event that should never be the only trace of a call: the channel ended
without a human and without a deposit, so the caller's intent exists nowhere
except the CDR.

This is the observable form of a design gap rather than a transport failure —
an agent that owns a call has no voicemail edge, so a model outage, an absent
API key or the turn cap all terminate silently. Emitting this event (or
badging it in the call index) turns "we think we lost a few calls" into a
number.
""",
    },
]


# --------------------------------------------------------------------------
# Flows
# --------------------------------------------------------------------------

FLOWS = [
    {
        "id": "inbound-call-routing",
        "name": "Inbound Call Routing",
        "summary": (
            "A did is dialled, the lane decides between agent and ring group, "
            "and an unanswered call becomes a voicemail deposit plus a notification."
        ),
        "body": """
The intended ladder, per DID lane. Steps 5 and 7 are alternatives selected by
the lane's `answerDids` intercept and its ring group's `timeWindow` — the
flow is drawn linearly because that is the diagram format, not because both
branches run.

The three declarative knobs that change this picture are
`agent.answerDids` (does the agent own this number),
`ringGroups.<id>.timeWindow` with `afterHoursDestination` (does a human even
ring after hours), and `ringGroups.<id>.voicemailMember` (whose mailbox takes
the fall-through).
""",
        "steps": [
            (
                "externalSystem",
                "Caller dials the DID",
                "Caller / PSTN",
                "Places an inbound call to a published number.",
            ),
            ("message", "Call invited", None, None),
            (
                "service",
                "Lane gateway accepts the INVITE (public_did_<gateway>, allowedCidrs)",
                None,
                None,
            ),
            (
                "service",
                "Destination decision: agent.answerDids intercept, else didDestination",
                None,
                None,
            ),
            (
                "service",
                "Agent branch: the voice agent answers in the DID's language",
                None,
                None,
            ),
            ("message", "Agent answered", None, None),
            (
                "service",
                "Human branch: ring group rings its members for timeoutSec (inside the timeWindow)",
                None,
                None,
            ),
            ("message", "Call offered to the ring group", None, None),
            (
                "service",
                "No answer, or after the hours window: mod_voicemail takes the deposit",
                None,
                None,
            ),
            ("message", "Voicemail deposited", None, None),
            (
                "service",
                "Transcript mailer renders the RFC 5322 message (transcript + WAV)",
                None,
                None,
            ),
            ("message", "Voicemail notified", None, None),
            (
                "externalSystem",
                "Mail relay accepts the notification",
                "SMTP relay",
                "Forwards the deposit notification to the mailbox owner.",
            ),
        ],
        "refs": {
            2: {"message": "call.invited"},
            3: {"service": "pbx"},
            4: {"service": "pbx"},
            5: {"service": "pbx-voice-agent"},
            6: {"message": "call.agent.answered"},
            7: {"service": "pbx"},
            8: {"message": "call.ringgroup.offered"},
            9: {"service": "pbx-voicemail"},
            10: {"message": "call.voicemail.deposited"},
            11: {"service": "pbx-voicemail"},
            12: {"message": "call.voicemail.notified"},
        },
    },
    {
        "id": "inbound-call-unrecorded-loss",
        "name": "Inbound Call Unrecorded Loss",
        "summary": (
            "The branch with no edge: the agent answered, the model failed, and "
            "neither a human nor a mailbox ever held the call."
        ),
        "body": """
The defect this catalog exists to make visible. An agent-owned lane has no
voicemail fall-through: when the model is unhealthy, the API key is absent, or
`maxCallSeconds` expires, the parked channel is released and the call leaves
only a CDR row.

Compare with `inbound-call-routing`: every human-facing failure in that flow
lands in a mailbox. This flow ends in nothing, which is strictly worse than a
plain voicemail box.

Closing it is one edge (on any agent failure, hand the channel back to the
ring group's voicemail member) plus a notification when the fall-through
itself fails.
""",
        "steps": [
            (
                "externalSystem",
                "Caller dials an agent-owned DID",
                "Caller / PSTN",
                "Places an inbound call to a number the agent answers.",
            ),
            ("message", "Call invited", None, None),
            ("service", "The voice agent answers the call", None, None),
            (
                "service",
                "The model is unavailable, the key is missing, or maxCallSeconds expires",
                None,
                None,
            ),
            (
                "service",
                "No voicemail edge exists: the parked channel is released",
                None,
                None,
            ),
            ("message", "Call ended unrecorded", None, None),
            (
                "service",
                "Nothing to retrieve: no mailbox write, no notification",
                None,
                None,
            ),
        ],
        "refs": {
            2: {"message": "call.invited"},
            3: {"service": "pbx-voice-agent"},
            4: {"service": "pbx-voice-agent"},
            5: {"service": "pbx-voice-agent"},
            6: {"message": "call.abandoned.unrecorded"},
            7: {"service": "pbx"},
        },
    },
]


# --------------------------------------------------------------------------
# ADR
# --------------------------------------------------------------------------

ADRS = [
    {
        "id": "call-routing-layering",
        "name": "Call routing layering: mailbox floor, agent ceiling",
        "summary": (
            "Voicemail is the universal fallback on every number; the voice "
            "agent is a front door only on numbers whose lane and language it "
            "can actually serve."
        ),
        "status": "proposed",
        "date": "2026-11-06",
        "applies_to": ["pbx", "pbx-voice-agent", "pbx-voicemail"],
        "body": """
## Context

Three answering surfaces exist per DID lane (human ring group, voice agent,
voicemail) and the routing knobs are per-lane. Operator evidence from the
pbx.artmann.tech deployment:

- The ring group's human leg is weaker than the configuration suggests: a
  browser-tab endpoint (the webphone) is the only device on the primary
  extension, and a second member can exist with no registered device at all.
- The voice agent is turn-based with no barge-in, owns the call until
  transfer or hangup, and has no fall-through to a mailbox.
- The voicemail deposit is the only path that works when everything else is
  down, and it has its own two-leg failure mode (storage, then notification).
- `timeWindow`/`afterHoursDestination` exists, so "when nobody is available"
  is expressible declaratively; it was simply never configured.

## Decision

- Voicemail is enabled as the FLOOR on every number: every lane must have a
  path to a mailbox, including agent-owned lanes.
- The agent is a CEILING, never a replacement: enable `answerDids` only for
  lanes where (a) the greeting language is set per DID via `languageByDid`,
  and (b) a transfer destination reaches a human who can actually answer.
- Human-first numbers use the ring group plus `timeWindow`; the agent or a
  mailbox is the `afterHoursDestination`, not the day-time default.
- Any agent failure path must terminate in a deposit. A call the agent cannot
  serve is a voicemail, not a hangup.

## Consequences

- Every number needs a working deposit + notification before it is published;
  "voicemail is enabled" without a proven deposit is a false promise.
- Voicemail storage grows without bound (recordings are kept forever by
  default), so enabling it everywhere is a disk and backup-window decision,
  not a free one.
- Agent spend is bounded to the lanes that opt in, instead of every
  wrong-number and robocall.
- Closing the agent-to-mailbox edge is upstream work in this module, not a
  host setting.
""",
    },
]
