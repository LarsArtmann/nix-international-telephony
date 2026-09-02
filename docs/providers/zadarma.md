# Zadarma

> **Verdict: budget wildcard — full 5-country coverage with the
> lightest KYC, at consumer prices.** City-level German and Swiss
> inventory at ~€2–4/mo, HK national numbers with **passport-level**
> KYC (personal OK, no Tripartite mentioned). Trade-off: route
> quality and enterprise reliability are unproven — good for early
> experimentation and low-stakes numbers, not (yet) the primary
> trunk.

- **Type:** consumer/SMB VoIP provider (SIP trunk + free cloud PBX +
  CRM + AI voice agent products)
- **Model:** fully self-serve, prepaid top-ups, no contracts
- **Jurisdiction/entity:** ❓ unverified (site defaults to PLN;
  verify the contracting entity and GDPR DPA before business use)

## Numbers & coverage (our 5 countries)

Verified 2026-08-29 from their per-country tariff pages (prices in
PLN as geo-detected; the site supports EUR/USD display):

| Country | Inventory                                                                             | Monthly fee                                               | KYC                                                                                                    |
| ------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| DE      | many cities (Berlin 030, Cologne 0221, Frankfurt 069, Düsseldorf, Essen, …) + 0800    | 16 zł (~€3.7); yearly billing 8 zł + 28 zł one-time setup | per city page (❓ verify — DE page shows fees without doc footnotes)                                   |
| CH      | cities (Zurich 044, Geneva 022, Basel, Bern, Lausanne, …) + national 058 + mobile 078 | 18 zł (~€4.2)                                             | company reg **or** passport/ID + address proof; some numbers require an address in the number's region |
| PL      | local                                                                                 | 14 zł (~€3.3)                                             | ❓ verify on PL page                                                                                   |
| HK      | national (prefix "5") + 800 toll-free                                                 | 25.5 zł (~€6)                                             | **company reg OR passport/ID + address proof ≤6 months — personal accepted**                           |
| US      | local (per-city pages, e.g. New York)                                                 | 13.4 zł (~€3.1)                                           | ❓ verify                                                                                              |

Every number includes **2 concurrent lines**; more lines cost extra.
**Incoming calls are free** (except toll-free), which is flat-rate
per-number rather than per-minute inbound — attractive for inbound
DIDs. Number porting (MNP) offered. SMS requires the number to be
prepaid ≥3 months.

## Voice trunk fit (FreeSWITCH)

- SIP-based by construction ("PC, SIP gate, office PBX, mobile, or
  any SIP device" — their pages) and they sell an explicit
  **SIP-trunk** product (`zadarma.com/en/services/calls/sip-trunk/`).
- ❓ Trunk auth mode (registration vs IP), codec list, TLS/SRTP
  support: not verified — read their SIP-trunk setup docs before
  wiring `services.telephony.gateways.itsp`.
- ❓ Guardrails (channel caps, max call cost): not documented at the
  trunk level I could verify — assume none until proven.

## Programmable voice / agent readiness (the CV integration)

- Public **API documentation** (`zadarma.com/en/support/api/`) —
  provisioning + PBX control scope ❓.
- They market their own AI voice agent, click-to-call widget, speech
  analytics — a closed product stack, not an open call-control API
  like Telnyx Call Control.
- Realistic role in our architecture: cheap DIDs terminating onto
  our FreeSWITCH; agent logic stays in our stack (event-socket
  origination).
- Fax: ❓ no fax product in their site navigation (checked
  2026-08-29); T.38 trunk behavior unknown.

## Messaging

SMS product exists (3-month prepay gate for enabling on a number);
A2P quality/registration story ❓. Not a factor for our voice-first
stack.

## Commercial & account

- Prepaid, per-number fees above; outbound calls billed per their
  price plans regardless of the number.
- Free tier exists around their PBX product — irrelevant but note
  their pricing psychology is consumer-grade (fine).

## Risks

- **Quality unknown**: no public ASR/latency/uptime figures; budget
  providers often ride mixed-quality routes. Test with their cheap
  numbers before trusting business traffic to it.
- Company/GDPR posture unverified — required homework before
  routing company calls through them (DPA, data location).
- 2-line default per number could cap concurrent inbound; extra
  lines are paid and possibly manual.

## Sources & verification status

| Claim                                                         | Status                  | Source                                                           |
| ------------------------------------------------------------- | ----------------------- | ---------------------------------------------------------------- |
| DE city inventory + 16 zł/mo + setup 28 zł + 0800             | ✅ verified             | zadarma.com/en/tariffs/numbers/germany/ (fetched 2026-08-29)     |
| CH cities/national/mobile + 18 zł + KYC footnotes             | ✅ verified             | zadarma.com/en/tariffs/numbers/switzerland/ (fetched 2026-08-29) |
| HK national 25.5 zł + passport-OK KYC + toll-free             | ✅ verified             | zadarma.com/en/tariffs/numbers/hong-kong/ (fetched 2026-08-29)   |
| PL 14 zł, US 13.4 zł country rows                             | ✅ verified             | zadarma.com/en/tariffs/numbers/ index (fetched 2026-08-29)       |
| 2 lines per number, free incoming, SMS 3-month prepay         | ✅ verified             | tariff pages (2026-08-29)                                        |
| SIP trunk product, API docs, MNP porting, PBX/CRM/AI products | ✅ verified (existence) | site navigation (2026-08-29)                                     |
| Trunk auth/codec/guardrail specifics                          | ❓ unverified           | setup docs needed                                                |
| Route quality, entity/GDPR, support quality                   | ❓ unverified           | trial needed                                                     |
