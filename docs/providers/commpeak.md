# CommPeak

> **Verdict: plausible second quote, not a first trunk.** Claims
> DIDs from 75+ countries with self-serve-ish onboarding, but
> per-country coverage (especially HK voice) is not publicly
> verifiable — their pricing pages 404 and the country list lives
> behind the portal/sales chat.

- **Type:** wholesale voice + DID provider (UK-rooted), also SMS,
  dialer services, AMD, HLR
- **Model:** free trial signup, then sales-engineer-led onboarding
  ("contact our sales team... we'll help you decide")

## Numbers & coverage (our 5 countries)

❓ Unverified for the exact DE/CH/PL/HK/US matrix. Marketing page
(fetched 2026-08-29) states "DID numbers from over 75 countries"
with local/mobile/toll-free/non-geographic/vanity types, concurrent
channel options, and portal analytics — but no country list.
Their DID page also claims fax support ("SMS, fax, and local and
international calls") — ❓ fax details unverified.
`commpeak.com/prices` returned 404 on 2026-08-29.

## Voice trunk fit / agent readiness

- SIP trunking + termination are their core (wholesale A-Z);
  ❓ auth modes, TLS/SRTP, guardrails unverified.
- AMD + HLR + dialer routing marketed — outbound-campaign flavored.

## When to revisit

When we want a third competitive quote for termination rates
(they present as genuinely wholesale-priced); bring the checklist
from `README.md` to the sales call and make them fill it in.

## Sources & verification status

| Claim | Status | Source |
| ----- | ------ | ------ |
| 75+ countries claim, number types, sales-led onboarding | ✅ verified (as their claims) | commpeak.com/did-numbers (fetched 2026-08-29) |
| Pricing pages missing/blocked | ✅ verified | /prices → 404 (2026-08-29) |
| 5-country matrix, HK voice, trunk specifics | ❓ unverified | portal/sales needed |
