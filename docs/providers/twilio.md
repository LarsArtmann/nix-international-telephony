# Twilio

> **Verdict: skip as the trunk for our country mix; keep as the
> reference for agent tooling.** Programmable voice is best-in-class,
> but PL has no local voice numbers (mobile-range only), HK has no
> local/national voice DIDs (toll-free only), and German numbers are
> business-only with heavy paperwork.

- **Type:** the CPaaS incumbent (US), self-serve
- **Model:** pay-as-you-go portal + the most complete API surface in
  the industry

## Numbers & coverage (our 5 countries)

From their pricing CSVs and regulatory pages (researched 2026-08-27):

| Country | Local voice | Notes |
| ------- | ----------- | ----- |
| DE | ✅ $1.35/mo, inbound $0.01/min | **Not available to individuals**; Handelsregisterauszug/Gewerbeanmeldung/Tax-ID; address must match the number's locality. Toll-free requires a self-obtained BNetzA allocation letter |
| CH | ✅ $1.15/mo | Regulatory bundle with address |
| PL | ❌ **mobile-range only** ($4/mo) — no reliable local voice DIDs | outbound to PL mobiles pricey ($0.22/min) |
| HK | ❌ **no local/national voice** — toll-free only, $25/mo + $0.0706/min | since Mar 2023 OFCA rules, HK CLI must be Twilio-issued; no HK emergency calling |
| US | ✅ $1.15/mo | mature E911/10DLC/CNAM |

Two of five countries effectively fail → disqualified as our trunk.

## Programmable voice / agent readiness

The industry benchmark: TwiML, REST origination, **Media Streams**
(websocket bidirectional audio), TaskRouter, AMD, conference, voice
intelligence. (Well-established product names; verify current specs
when building.) If we ever build agent calling that must NOT touch
our FreeSWITCH, Twilio Voice is the other credible engine after
Telnyx — but then we accept its number gaps or pair it with another
provider's DIDs, which adds complexity for no gain over Telnyx.

## Commercial & account

- Self-serve, but German entity requirements and the BNetzA toll-free
  self-application make the DE story operationally worse than Telnyx
  (who handle toll-free via LOI/PoA).
- Pricing consistently 1.5–3× Telnyx on equivalent items in our
  earlier comparison.

## When to revisit

- If SMS/WhatsApp become core (their messaging breadth is unmatched).
- If a US-only calling product spins out of the CV system (US local
  numbers + 10DLC + Media Streams is a clean Twilio story).

## Sources & verification status

| Claim | Status | Source |
| ----- | ------ | ------ |
| DE $1.35/mo, business-only, BNetzA toll-free path; CH $1.15; US $1.15 | sourced | assets.cdn.prod.twilio.com/pricing CSVs + twilio.com/en-us/guidelines (researched 2026-08-27) |
| PL mobile-only; HK toll-free-only + OFCA 2023 rules, no HK emergency | sourced | same + twilio.com/en-us/guidelines/hk/voice (researched 2026-08-27) |
| Programmable voice feature set (TwiML, Media Streams, …) | general knowledge | verify at build time |
