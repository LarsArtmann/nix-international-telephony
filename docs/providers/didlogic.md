# didlogic

> **Verdict: strong trunk technology, thin German local inventory.**
> Real carrier (own ASN, 12 PoPs), excellent trunk guardrails, AI-
> platform-friendly — but German *local* numbers come in exactly two
> area codes. Use as a second quote / quality-termination option, not
> the primary numbers source.

- **Type:** wholesale voice carrier since 2006, own ASN (AS13006),
  12 physical PoPs, direct Tier-1 peering — not a reseller (their
  infrastructure pages)
- **Certifications:** ISO/IEC 27001:2022 (TÜV AUSTRIA), ISO 9001
- **Model:** self-serve signup (no credit card to start), prepaid,
  24h profile compliance validation on signup

## Numbers & coverage (our 5 countries)

| Country | Local | National | Toll-free | Notes |
| ------- | ----- | -------- | --------- | ----- |
| DE | ⚠️ **Hamm (02381) + Würzburg (0931) only** | ✅ (+49) | ✅ (0800) | Verified on their Germany page 2026-08-29 |
| CH | ✅ listed | — | ✅ | Area-code depth ❓ — check portal |
| PL | ✅ listed | — | ✅ | Area-code depth ❓ — check portal |
| HK | — | ✅ (+852) | ✅ (800) | Verified on their HK page 2026-08-29 |
| US | ✅ | — | ✅ | Trivially covered |

"140+ countries" total, "delivered over SIP to any PBX" (numbers
page). Activation: most numbers within 8h, documentation-required
orders up to 48h (their FAQ, verified 2026-08-29). Number porting in
80+ countries.

## Voice trunk fit (FreeSWITCH) — the strong part

Verified 2026-08-29 from `didlogic.com/voice/sip-trunks/sip-trunking/`:

- **Both auth modes:** SIP registration **and** IP authentication
  ("useful for SBCs, dialers... that connect by static IP").
- **Per-trunk guardrails (rare and excellent):** IP allowlists,
  concurrent-channel caps, max call length, **max call cost per
  trunk** — anti-fraud controls that matter once agent-driven
  outbound exists.
- SIP REFER (live call transfer), CLI rotation (caller-ID pools),
  TLS signaling + SRTP media, no per-channel or per-trunk fees,
  elastic capacity on request.
- Portal + REST API provisioning (API reference v1/v2 on
  `docs.didlogic.com`; e.g. list/create/update SIP accounts).
- Sales engineer outreach + **free test DID and trial credits** —
  we can smoke-test the trunk before paying.

## Programmable voice / agent readiness (the CV integration)

- No native Twilio-style call-control/media-streaming API documented.
  ❓ (Their nav markets "bring your own carrier" to Vapi/ElevenLabs/
  Retell/LiveKit — i.e., they are the SIP layer under someone else's
  agent runtime.)
- Like DIDWW: front it with our FreeSWITCH and originate over the
  event socket. The max-call-cost guardrail makes it a *safe* trunk
  for agent campaigns.
- AMD, HLR lookups, dialer-friendly routing marketed for outbound
  teams (trunking page).

## Messaging

A2P SMS priced **per destination operator** (not blended), inbound
as fixed monthly per SMS-enabled number (SMS rates page structure
verified 2026-08-29; exact figures JS-gated). Consistent with
wholesale-direct-route economics; German A2P termination tolls make
anyone look "expensive" there. Irrelevant for our voice-only stack.

## Commercial & account

- Monthly rental + per-minute inbound per number (pricing page
  model); exact figures JS-gated — earlier research ballparked local
  from ~$4/mo. ❓ pull exact numbers from the portal before deciding.
- Account levels/tiers exist (their account-levels page) — ❓ volume
  discounts unverified.

## Risks

- German local inventory (2 area codes) is disqualifying if a
  specific German city number matters.
- Marketing site is thin on regulatory matrices (vs Telnyx/DIDWW
  per-country doc pages) — KYC specifics surface only at order time.
- Website is heavily JS; public verification is structurally limited
  (documented here so future sessions don't mistake silence for
  absence).

## Sources & verification status

| Claim | Status | Source |
| ----- | ------ | ------ |
| Own ASN AS13006, 12 PoPs, ISO 27001/9001, since 2006 | ✅ verified | didlogic.com network/security pages (fetched 2026-08-29) |
| Trunk features: IP+registration auth, per-trunk caps (channels/length/cost), REFER, CLI rotation, TLS/SRTP, no channel fees, API | ✅ verified | didlogic.com/voice/sip-trunks/sip-trunking/ (fetched 2026-08-29) |
| DE local = 02381 + 0931 only; national +49; 0800 | ✅ verified | didlogic.com/virtual-phone-numbers/germany/ (fetched 2026-08-29) |
| HK national +852, toll-free 800; FAQ activation 8h/48h | ✅ verified | didlogic.com/virtual-phone-numbers/hong-kong/ (fetched 2026-08-29) |
| CH/PL numbers listed, US covered | sourced | earlier research 2026-08-27 + numbers country grid 2026-08-29 |
| SMS per-operator pricing model | ✅ verified | didlogic.com/pricing/wholesale-international-voice/sms-rates/ (fetched 2026-08-29) |
| Free test DID + trial credits, 24h validation, no-CC signup | ✅ verified | trunking page (fetched 2026-08-29) |
| Exact per-country pricing | ❌ unverified | JS-gated; portal needed |
