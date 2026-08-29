# DIDWW

> **Verdict: failover trunk + emergency calling.** Equal 5-country
> coverage, carrier-grade posture, holds HK operator licenses — and is
> the only candidate with a compliant **emergency-calling service in
> all five of our countries**, which addresses this repo's known
> no-112/911 gap.

- **Type:** wholesale voice/DID carrier (Lithuania/EU-rooted,
  carrier-oriented)
- **Model:** self-serve prepaid ($30 minimum top-up) + REST API; also
  has a sales-led enterprise side
- **Coverage:** 93 countries, 5659 areas — "licensed or directly
  partnered with a local carrier in every country" (their claim)
- **Notable:** acquired Hong Kong national telecom operator licenses
  (Jan 2024, their news post) — unusual depth for the HK market

## Numbers & coverage (our 5 countries)

All five present on both the numbers coverage and the SIP-trunking
country list (verified 2026-08-29 via `didww.com/voice/global-sip-trunking`):

| Country | Local | National | Mobile | Toll-free | Emergency calling |
| ------- | ----- | -------- | ------ | --------- | ----------------- |
| DE | ✅ | ✅ | — | ✅ | ✅ (Local) |
| CH | ✅ | — | — | ✅ | ✅ (Local) |
| PL | ✅ | — | ✅ | ✅ | ✅ (Local) |
| HK | — | ✅ | — | ✅ | ✅ (National) |
| US | ✅ | — | — | ✅ | ✅ (Local) |

Also offers shared-cost and UIFN numbers. Number porting in 41
countries, marketed as free of charge.

## Emergency calling (differentiator)

Verified 2026-08-29 (`didww.com/services/emergency-calling`): PSAP
access in **40 countries** — Germany, Switzerland, Poland, Hong Kong,
USA all on the list. Model: register/validate addresses in their
panel, low one-time service setup fee, calls to PSAPs free, ISO 27001
data handling. This is a PSTN-replacement-grade feature none of the
other candidates document (Telnyx E911 is US-flavored; Zadarma/didlogic
document nothing). Caveat: emergency calling for OUR users means the
PBX dialplan must route 112/911 to the DIDWW trunk with the right
identity — a dialplan feature we do not generate yet (see ROADMAP).

## Voice trunk fit (FreeSWITCH)

- Local SIP trunking (57 countries per their June-2026 expansion) +
  A-Z termination; per-country trunk pages exist for all five of ours.
- Trunk authentication: ❓ IP-auth vs registration split not confirmed
  on public pages — their trunk model is configured in-panel (SIP URI,
  priority/weight); verify in portal before wiring
  `services.telephony.gateways.itsp`.
- Capacity model: flat-rate, pay-per-minute, or hybrid channels
  (their Capacity service).
- Fax (T.38) supported as a product ("virtual fax numbers worldwide
  via SIP trunking" — their site nav, fetched 2026-08-29); the only
  candidate of the seven marketing an explicit fax product.

## Programmable voice / agent readiness (the CV integration)

- DIDWW REST API (v3) for numbers, trunks, CDR export + webhooks —
  sourced from earlier research (doc.didww.com); provisioning-grade,
  not call-control-grade.
- **No Twilio-style programmable voice/media streaming documented.**
  For agent-driven calls you front the trunk with your own FreeSWITCH
  (ours) and drive origination over the event socket — which is
  exactly our architecture. Fine as failover trunk, not as the
  agent-call engine.
- They sell phone.systems™ (their cloud PBX with CRM integrations +
  Operator API) — irrelevant to us, we run our own, but it signals
  where their product energy goes.

## Compliance & KYC

Regulatory matrix per country (their Regulatory Requirements pages,
researched 2026-08-27): DE/CH/PL/HK all "registration required"
(docs similar to Telnyx's — address-in-country, ID/company papers;
HK national needs the Tripartite Agreement); US not required.

## Commercial & account

- Prepaid, $30 minimum top-up; NRC (one-time, = 1 month MRC, waived
  when bought via API) + MRC per number; outbound per-minute, no
  monthly minimum (sourced 2026-08-27).
- Exact per-country MRC: price list is gated (email form) — ❓ get a
  quote before committing.
- ISO 27001; claimed network uptime 99.998%.

## Risks

- Wholesale orientation: portal UX and support are
  carrier-flavored; expect less hand-holding than Telnyx.
- Pricing opacity (quote-gated) — budget needs a quote round.

## Sources & verification status

| Claim | Status | Source |
| ----- | ------ | ------ |
| All 5 countries on SIP trunking + emergency lists | ✅ verified | didww.com/voice/global-sip-trunking, didww.com/services/emergency-calling (fetched 2026-08-29) |
| Emergency calling: 40 countries, PSAP model, free PSAP calls, setup fee | ✅ verified | didww.com/services/emergency-calling (fetched 2026-08-29) |
| 93 countries / 5659 areas, licensed-or-partnered claim, 99.998% uptime | ✅ verified (their claims) | didww.com emergency page footer sections (2026-08-29) |
| HK operator licenses | sourced | news.didww.com 2024-01-23 post (researched 2026-08-27) |
| Regulatory matrix DE/CH/PL/HK required, US not | sourced | didww.com/resources/regulatory-requirements/* (researched 2026-08-27) |
| Prepaid $30 min, NRC/MRC model, porting 41 countries | sourced | doc.didww.com billing pages (researched 2026-08-27) |
| Trunk auth modes, REST API v3 details | ❓ unverified | needs portal/doc confirmation |
