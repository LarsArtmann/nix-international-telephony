# Telephony provider evaluations

Point-in-time-but-maintained evaluations of SIP trunk / DID / CPaaS
platforms for this stack. Target country mix: **DE, CH, PL, HK, US**.
Long-term requirement: all-companies telephony on this PBX plus
programmatic, agent-friendly outbound calling (CV-system
integration, human-in-the-loop).

**Facts below were verified 2026-08-27/29; prices drift — re-verify
in the provider portal before purchasing.** Every provider file
carries a per-claim verification table (✅ verified from primary
source / sourced from earlier sourced research / ❓ unverified).

| File | Platform | One-line verdict |
| ---- | -------- | ---------------- |
| [telnyx.md](telnyx.md) | Telnyx | **Primary**: only full 5-country + full programmable-voice combo |
| [didww.md](didww.md) | DIDWW | **Failover trunk + emergency calling** (all 5 countries) |
| [zadarma.md](zadarma.md) | Zadarma | **Budget wildcard**: full coverage, lightest KYC, unproven quality |
| [didlogic.md](didlogic.md) | didlogic | Strong trunk tech + guardrails; DE local = 2 area codes; signups effectively business-gated (auto-declined our personal signup 2026-08-29) |
| [twilio.md](twilio.md) | Twilio | Skip as trunk (PL/HK gaps); agent-tooling reference |
| [bandwidth.md](bandwidth.md) | Bandwidth/Voxbone | Revisit at volume (contract sales) |
| [commpeak.md](commpeak.md) | CommPeak | Plausible third quote; coverage unverifiable publicly |
| [others.md](others.md) | Flowroute, VoIP.ms, sipgate, … | Dismissed for this mix |

## The question framework

The full catalog we ask of any candidate platform. Numbers in
brackets mark the questions that are **decision-critical** for us
right now; the rest matter as the system grows.

### 1. Numbers & coverage

1. [x] Does it cover all five countries (DE, CH, PL, HK, US)?
2. [x] Number types per country: local / national / mobile / toll-free / shared-cost?
3. [x] For DE: any city (area code) or a fixed inventory? Which cities?
4. [x] HK: geographic numbers possible, or national/toll-free only?
5. Per-DID monthly + setup fees, inbound per-minute or flat?
6. Number porting in/out: cost, timeline, coverage?
7. Concurrent channels per number: included lines, burst, extra-line cost?
8. Caller-ID control: our DIDs as outbound CLI, in-country CLI rules (DE, HK OFCA 2023)?
9. Number reservation/hosting (keep without active service)?

### 2. Trunk fit for our FreeSWITCH

10. [x] Standard SIP trunk into an owned PBX (no proprietary box)?
11. [x] Both auth modes: registration AND IP-auth (with source CIDRs for our `allowedCidrs`)?
12. Codecs: G.711a/µ, Opus, G.722? Transcoding or passthrough?
13. TLS signaling + SRTP media supported?
14. SIP REFER (transfers), T.38 fax?
15. Keepalive/NAT behavior for registration trunks (OPTIONS interval)?
16. Media PoPs near our Hetzner DE host (latency)?
17. CPS/channel caps and bursting policy?
18. Official FreeSWITCH documentation?

### 3. Programmable voice & agent readiness (CV integration)

19. [x] REST API to originate calls programmatically?
20. [x] Webhooks for call events (answered, ended, digits)?
21. [x] Bridging primitive for human-in-the-loop (ring my extension first, then the target)?
22. Real-time media streaming (websocket audio) for AI agents?
23. AMD (answering-machine detection) quality + price?
24. TTS/STT built in, or bring-your-own?
25. Call recording API + retrieval for logging calls into the CV system?
26. Conferencing API?
27. CDR export (API/S3/webhook) for billing and audit?
28. Webhook authentication (signed requests) for agent integrations?
29. API rate limits vs automated campaign needs?

### 4. Compliance & KYC

30. [x] Per-country KYC: personal accepted, or business-only? Which documents?
31. [x] Address requirements: in-country, region-matching-area-code, proof age?
32. [x] Activation lead time after docs?
33. Emergency calling (112/911): available, per-country coverage, address registration, cost, dialplan implications?
34. GDPR: DPA available, data residency, EU processing?
35. Licenses: own numbering resources, local carrier licenses (HK!)?
36. STIR/SHAKEN, CNAM, 10DLC (US outbound reputation)?

### 5. Commercial & account

37. [x] Self-serve vs sales-led? Minimum commitments?
38. [x] Prepaid/postpaid, minimum top-up, auto-topup, fraud deposit?
39. Hidden fees: per-trunk, per-channel, E911 surcharge, NRC?
40. Billing increment (per-second after 30/6?)?
41. Fraud controls: per-trunk caps, IP allowlists, max call cost, portal 2FA?
42. Multi-company separation: sub-accounts/projects/API keys per entity?
43. Uptime SLA + status page + incident history?
44. Support channels and 24/7 reality at our spend level?

### 6. Messaging (secondary)

45. SMS in/out per country, sender-ID registration, alphanumeric senders?
46. A2P pricing model (per-operator vs blended) + filtering risk?

### 7. Exit & reliability posture

47. Number portability OUT (the real lock-in)?
48. Data export (CDRs, recordings) on exit?
49. Secondary/redundant SIP endpoints (DNS SRV, multiple PoPs)?
50. Company durability: age, ownership, funding/licenses.

### 8. Fax (if it becomes a requirement)

51. T.38 on the trunk (real fax relay), or only G.711 audio fax
    passthrough (works, but lossy on jittery paths)?
52. Provider-side fax product (fax-enabled numbers, fax-to-email/API),
    or nothing?
53. Outbound fax API (REST, per-page) for sending documents from
    the CV/agent side without touching the PBX?

## Comparison matrix (verified 2026-08-29)

| | DE local | CH | PL | HK | US | Emergency | Fax | Agent API | KYC burden | DID cost/mo |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **Telnyx** | any area code¹ | local² | local+mobile | national² | local, instant | US E911 | ❓ T.38 unverified | ✅ Call Control + media streaming | High (DE/CH/PL) | ~$1–3 |
| **DIDWW** | local+national | local² | local+mobile | national² | local | ✅ **40 countries incl. all 5** | ✅ fax product | SIP only (pair with our FS) | High (reg. matrix) | ~$1–3 +NRC |
| **didlogic** | **Hamm + Würzburg only** + national | local ❓depth | local ❓ | national | local | ❓ none documented | — none documented | API + AI-platform friendly | Medium (≤48h) | ~$4 |
| **Zadarma** | many cities | cities+nat+mobile | local | national (**personal OK**) | local | ❓ none | ❓ | own PBX/CRM stack + API | **Low–Medium** | ~€3–6 |
| **Twilio** | local² (business-only) | local² | **mobile only** | **toll-free only** | local | ❓ varies | ❌ retired (Programmable Fax sunset) | ✅ best-in-class | High | $1.15–25 |
| **Bandwidth** | ✅ | ✅ | ✅ | ✅ | ✅ | US E911 | ❓ | ✅ enterprise APIs | Enterprise | contract |
| **CommPeak** | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ | claims fax support | ❓ | Sales-led | ❓ |

¹ address must match the area code; national numbers accept personal
identity with any German address. ² business-only or restricted per
their regulatory pages.

## Verdict & target architecture

1. **Primary trunk: Telnyx.** Only platform where the full country
   mix *and* the agent-calling stack (Call Control, media streaming,
   AMD, TTS/STT, llms.txt for AI agents) live behind one account.
   Budget ~72h+ per regulated country for KYC; order DIDs early.
2. **Failover trunk + emergency calling: DIDWW.** Same 5-country
   coverage; unique compliant PSAP access in all five — directly
   attacks this repo's documented no-emergency-calling gap (needs a
   dialplan feature: route 112/911 to the DIDWW trunk).
3. **Budget/experimentation DIDs: Zadarma.** Cheapest full coverage
   with personal-friendly KYC (notably the only HK national option
   that accepts a passport). Trial-grade until quality is proven;
   do the entity/GDPR homework before company traffic.
4. **didlogic** stays the quality-termination second quote; its
   per-trunk max-call-cost guardrail is the model for whatever
   agent-driven outbound we build.

**Agent-calling architecture note.** Two execution paths, both valid:
(a) **our FreeSWITCH today** — the event socket already provides
programmatic origination with human-in-the-loop bridging
(`originate user/1000 &bridge(sofia/gateway/itsp/<e164>)`), covered
by VM tests, provider-agnostic; (b) **Telnyx Call Control** for
calls that should live outside the PBX (REST origination, webhooks,
media streaming to AI). The CV system can start against (a) with any
trunk, and adopt (b) when agent autonomy grows. Fraud posture:
agent-driven outbound must always run behind a capped trunk
(didlogic-style max-call-cost) regardless of path.

**Fax posture (asked 2026-08-29).** Self-hosted fax is buildable
without new dependencies: the nixpkgs FreeSWITCH our closure uses
ships `mod_spandsp` (provides the `rxfax`/`txfax`/`t38gateway`
apps — verified in the store path; `mod_fax` is absent, it is the
legacy module). So the PBX can terminate T.38 (or audio-mode) fax
to files + the existing mailer notification once a T.38-capable
trunk and a fax DID exist — DIDWW is the only candidate marketing
an explicit fax product; Telnyx T.38 support is unverified (ask
support before ordering a fax DID there). If fax becomes a real
business need before we build that, a cloud fax API (e.g. InterFAX;
per-page model, ❓ pricing unverified) is the zero-integration
path. Twilio Programmable Fax is retired — `twilio.com/docs/fax`
returns an empty help-center shell (verified 2026-08-29).

**Sequencing note (micro-multinational reality).** KYC cost scales
with jurisdiction count, not with spend — a 5-country one-person
business pays the same compliance as a 5-country enterprise. So
sequence numbers by friction, not by ambition: US local day one
(instant, no docs) to prove the whole stack, DE national in week one
(one passport upload, personal identity), and buy the uncertain
countries (PL/CH/HK) from Zadarma only when a real need appears
(passport-level KYC, €3–6/mo, disposable quality is fine at
low volume). Upgrade a country to Telnyx/DIDWW when it becomes
business-critical — portability means never redoing the paperwork.

## Maintenance

- Before any purchase: re-verify that provider's file against its
  "Sources & verification status" table (prices and regulatory
  requirements drift).
- When a ❓ gets answered in a portal/sales call, replace it with
  the fact + source in the same commit.
- When the trunk decision lands, record the decision (not the
  research) in `ROADMAP.md` open questions and retire the
  corresponding TODO_LIST row.
