# Decision: MMS is HTTP-API-only, Won't-implement for now

Date: 2026-09-17
Status: Decided
Plan row: P20.1 (round-2 Pareto plan)

## Context

MMS has no SIP/FreeSWITCH story at all: there is no SIP standard for
multimedia messaging, mod_sms carries text only, and providers (Telnyx
included) deliver MMS exclusively through their HTTP APIs — inbound media
arrives as expiring https:// links in webhook payloads, outbound is an API
call with media URLs attached.

The PBX therefore has no lever to pull, and inventing one would mean
proxying provider media into FreeSWITCH for zero users. The realistic
future trigger is: someone sends a picture to the DID, the webhook receiver
logs it, and a human wants to see it in the operator window.

## Decision

**HTTP-API-only, and not implemented now.** If the need materializes, the
shape is the SMS-lane pattern: the webhook receiver persists media metadata
(+ fetched copies — provider links expire) into a JSONL store, and the
operator window gains a media tab. The PBX itself stays out of it.

## Consequences

- No MMS code, options, or tests in this repo today; the question is
  closed until a concrete need appears.
- ROADMAP.md carries the posture note (raw-idea lane) so future sessions
  do not re-derive this analysis.
- The SMS decision doc (`2026-09-17_sms-lane-telnyx-api-only.md`) is the
  template to copy if the trigger ever fires.
