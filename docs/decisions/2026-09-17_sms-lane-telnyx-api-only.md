# Decision: SMS lane is Telnyx-API-only

Date: 2026-09-17
Status: Decided (ratifies the already-shipped mechanism; owner veto would reopen)
Plan row: P15.1 (round-2 Pareto plan)

## Context

The trunk is voice-only. Telnyx does not deliver its messaging product over
the SIP trunk — inbound SMS arrives as an HTTP webhook (handled by the
private deployment's `telnyx-webhooks.py` receiver), and outbound SMS is a
Telnyx REST API call against a messaging profile. There is no point in the
stack where a SIP MESSAGE method carrying an SMS appears.

Two lanes were on the table:

| Lane                         | What it means                                                                       | Cost                                                                     | Benefit                                              |
| ---------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------- |
| **Telnyx-API-only** (chosen) | The webhook receiver keeps an append-only JSONL store; the PBX renders it read-only | A one-option hook                                                        | Matches where SMS actually lives                     |
| `mod_sms` + chatplan         | FreeSWITCH terminates SMS over SIP, routes via chatplan XML                         | Module config, chatplan DSL, a second routing brain to test and maintain | None — no inbound SIP MESSAGE feed exists to feed it |

## Decision

**Telnyx-API-only.** FreeSWITCH stays SMS-blind; mod_sms/chatplan is
rejected because its entire input path (SIP MESSAGE) never occurs on this
trunk.

The shipped shape:

- `services.telephony.operator.smsMessageStore` (public option): optional
  path to an append-only JSONL file (`received_at`, `from`, `to`, `body`
  per line). The PBX never writes to it.
- The operator window's SMS tab and `/operator-api/sms` render that store
  read-only alongside CDRs.
- The private deployment's webhook receiver is the writer
  (`/var/lib/telnyx-webhooks/inbound.jsonl`).

## Consequences

- No chatplan, no mod_sms load, no SMS routing in the dialplan simulator.
- SMS history lives outside the PBX by design; a future merged
  calls+SMS timeline in the webphone would read both sources (CDR CSV +
  this JSONL) and join client-side. Deferred until someone actually
  texts this number.
- If a second provider ever appears, it adapts by writing the same JSONL
  shape — the option is store-shaped, not Telnyx-shaped.
