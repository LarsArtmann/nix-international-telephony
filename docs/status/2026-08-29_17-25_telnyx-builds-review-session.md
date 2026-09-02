# Status Report: Telnyx Builds Review Session

**Generated:** 2026-08-29 17:25 CEST
**Session scope:** Research + review of `telnyx.com/products/builds` (the "200+ open-source builds" directory), the `team-telnyx` GitHub org, and `agent-signup.md`; grounded against `docs/providers/README.md` + `docs/providers/telnyx.md`.
**Scope discipline honored:** no unrelated research; no code touched; zero repo changes until this report file.

| Done | Partial | Not started | Fucked up |
| ---- | ------- | ----------- | --------- |
| 7    | 3       | 5           | 5         |

---

## a) FULLY DONE

1. **Telnyx Builds product review delivered** (in chat, this session). What Builds is, best ideas ranked, direct relevance table for this repo, critiques. Evidence: review message this session; grounded in primary sources only.
2. **Real Builds catalog extracted.** The page is client-rendered (`BAILOUT_TO_CLIENT_SIDE_RENDERING`); I located the `BuildsExplorer` JS chunk and extracted the embedded generated catalog: `example_count: 488`, `generated_at: 2026-07-14T21:46:10Z`, source repo `team-telnyx/telnyx-code-examples` (153★, active 2026-08-28), per-build schema `folder/title/description/product/language/framework/url`. Evidence: fetched chunk bytes (Fetched 2026-08-29).
3. **Catalog breadth mapped:** core voice primitives in 6–7 languages each; SIP ops builds (programmatic trunk setup, failover routing, load-balancer health checks); AI/agent builds (assistants CRUD, RAG, media-streaming translation/interpreter, warm-transfer briefing, deepfake detector, fax-to-AI); vertical builds (law intake, medical triage, hiring screens); meta/tooling (migrate-from-twilio/elevenlabs/vapi, E911 validator, CDR analytics, number-reputation monitor, edge MCP deploy, x402 funder). Evidence: catalog JSON content (Fetched 2026-08-29).
4. **team-telnyx org reconnaissance** via `gh`: SDKs in 7 languages, `telnyx-cli` (Go), WebRTC SDKs (JS/iOS/Android/Flutter/React Native), and — directly relevant to this stack — maintained forks of **FreeSWITCH, sofia-sip, spandsp**. Evidence: `gh repo list team-telnyx` output (2026-08-29).
5. **`agent-signup.md` fetched and reviewed** (skill-md format): LLM-solvable bot challenge (`/v2/bot_challenge`), Agent Inbox (provider-issued agent mailbox), magic-link flows with 3 fallback paths, no-key demo fast-path via `/.well-known/agent-access.json`, `@telnyx/agent-cli` with `capabilities --json`. Evidence: fetched file (2026-08-29).
6. **Local grounding:** read `docs/providers/README.md` + `docs/providers/telnyx.md`; review tied findings to existing decisions (Telnyx = primary trunk; CV/agent-calling requirement; DIDWW failover + emergency plan; T.38 ❓). No file edits made — intentional (user asked for a review, not edits).
7. **Discrepancy finding:** nav says "200+ open-source builds"; the actual catalog says **488** (generated 2026-07-14, while the repo was updated 2026-08-28 — the site snapshot lags its source).

## b) PARTIALLY DONE

1. **Catalog coverage.** Works: large prefix of the 488 entries read (all categories represented). Remains: the fetch truncated at 100KB mid-catalog (cut off around `real-time-call-intelligence-*`); the tail was never read. Blocker: none — the canonical source is the GitHub repo. Effort: S.
2. **Findings → repo docs.** Works: analysis exists (chat + this report). Remains: nothing persisted into `docs/providers/telnyx.md` (e.g., the fax-builds lead for the open T.38 ❓). Blocker: deliberate scope choice, pending user preference (see g-Q3). Effort: S.
3. **Self-review compliance.** Works: reflection delivered inline (sections d/e below). Remains: the `brutal-self-review` skill's canonical output is a separate `docs/reviews/*.html` — not produced, because the user explicitly requested a single `.md` status report; merged here instead. Effort: S.

## c) NOT STARTED

1. **Any repo change from this session** — intentionally zero until this report file; nothing to revert.
2. **Telnyx T.38 verification.** New lead found (Telnyx ships `fax-to-ai-document-processor` + `fax-to-structured-data-pipeline` builds → a fax capability exists), but the mechanism (T.38 on the trunk vs. API-side fax) is unverified. Still needs a support/portal answer before ordering a fax DID.
3. **HARVEST:** section (f) below is the input for `docs-health` HARVEST into `TODO_LIST.md`/`ROADMAP.md`; not run (waiting on user).
4. **Agent-era tooling evaluation** (MCP endpoint, agent CLI, demo endpoints) against our agent-calling requirement — idea ranked, zero work done.
5. **Machine-readable docs for OUR repo** (llms.txt / generated catalog of modules + VM tests — the "steal this idea" item) — surfaced, not started.

## d) TOTALLY FUCKED UP

1. **`agentic_fetch` sub-agent failed on first use** (`unauthorized: token is expired` — the tool's internal LLM token). Severity: session-only, no data loss. Workaround: plain `fetch` + JS-chunk archaeology + `gh` CLI — ultimately produced _better_ evidence. Root cause: expired auth token in the tool; not fixable from here.
2. **First page fetch returned a nav-only shell** (client-rendered). I nearly started "reviewing" from the meta description alone. Recovered by pulling the data layer out of the JS chunk. Lesson: JS-rendered marketing pages must be reviewed via their data source, not their DOM.
3. **One unverified comparative claim shipped in my review:** "Nobody else in telecom is doing this" (agent-first commerce). I did not check Twilio/Vonage/Bandwidth. This violates the verify-external-claims discipline. Status: retracted here; treat as "first _I've_ seen" unless verified.
4. **Unverified quality claim:** "many AI builds are single-file Flask demos" — judged from titles/descriptions only; I opened **zero** build repos. The production-grade signal (Ed25519 webhook verification, rate limits) _was_ visible in descriptions for core voice/SMS builds, but the quality-skew statement is inference, not evidence.
5. **Imprecise counts:** I reported "~240 of 488 entries seen" without an actual count — the truncation point makes the exact number unknowable from what I kept. Precision-theater risk; fixed wording here.

## e) WHAT WE SHOULD IMPROVE

1. **Steal the Builds pattern for this repo:** machine-readable index (llms.txt / agents.md) of our NixOS modules, VM suites, and ops runbook. Impact: every future AI session (and human) gets a queryable surface; aligns with where buyers/integrators are heading. Fix: generate it (it can be a flake check, like `checks.docs-drift`).
2. **Leads must land in the provider file the same session** (one home per fact). The T.38 lead existed only in chat until now. Fix: when research produces a lead, append it to the provider file marked ❓+"lead", never ✅.
3. **Source discipline for external numbers:** repo convention already demands fetch dates; apply it to claims like build counts ("488, generated 2026-07-14, fetched 2026-08-29").
4. **Fallback-first tooling:** when `agentic_fetch` 401s, go straight to `fetch` + source archaeology instead of retrying; note the failure in the session report (done here).
5. **Comparative claims need comparisons.** "Nobody else does X" requires checking the obvious alternatives or being phrased as personal observation.

## f) Top 50 next things (ranked by impact within groups; feeds `docs-health` HARVEST)

Effort: S <30min · M 30min–2h · L >2h

### Cluster 1 — Telnyx/Builds findings → repo decisions & docs

| #  | Task                                                                                                                                               | Impact | Effort | Category      |
| -- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------ | ------------- |
| 1  | Add "Builds directory" section to `docs/providers/telnyx.md`: catalog facts (488 examples, repo URL, generated 2026-07-14) + the 6 relevant builds | High   | S      | Documentation |
| 2  | Record fax lead in `telnyx.md`: Telnyx ships fax builds ⇒ fax capability exists; mechanism (T.38 trunk vs API) stays ❓                            | High   | S      | Documentation |
| 3  | Ask Telnyx support the T.38 question, citing the fax builds, before ordering any fax DID                                                           | High   | S      | Quality       |
| 4  | Write the CV-integration ADR: FreeSWITCH event socket (path a) vs Telnyx Call Control (path b), using the hiring-screen builds as evidence         | High   | M      | Documentation |
| 5  | Study `sip-load-balancer-health-check` + `sip-failover-routing` builds; spec the DIDWW failover-trunk dialplan feature                             | High   | M      | Feature       |
| 6  | Add `ai-hiring-phone-screen` + `interview-screen-scheduler` as reference implementations under the CV/agent requirement                            | High   | S      | Documentation |
| 7  | Portal-verify Telnyx sub-account/project hierarchy for multi-company separation (❓ in `telnyx.md`)                                                | High   | S      | Quality       |
| 8  | Portal-verify Telnyx per-connection fraud caps/allowlists — parity bar: didlogic max-call-cost                                                     | High   | S      | Quality       |
| 9  | Portal-verify SRTP/TLS per Telnyx connection (❓ in `telnyx.md`)                                                                                   | High   | S      | Quality       |
| 10 | Execute the DID sequencing note: US local day one, DE national week one (KYC-friction order)                                                       | High   | M      | Feature       |
| 11 | Check `telnyx-code-examples` LICENSE before borrowing any build code into our docs                                                                 | Medium | S      | Quality       |
| 12 | Prototype Telnyx no-key demo endpoints (`/.well-known/agent-access.json` fast path) for zero-KYC spikes                                            | Medium | S      | Feature       |
| 13 | Evaluate `@telnyx/agent-cli` (`capabilities --json`) as the CV system's first calling client                                                       | Medium | S      | Feature       |
| 14 | Evaluate the Telnyx MCP endpoint vs raw Call Control as agent integration surface                                                                  | Medium | M      | Feature       |
| 15 | Number portability OUT per country (❓ in `telnyx.md`) — the real lock-in check                                                                    | Medium | S      | Quality       |
| 16 | Record that team-telnyx maintains FreeSWITCH/sofia-sip/spandsp forks (upstream-watch relevance) in `telnyx.md`                                     | Low    | S      | Documentation |
| 17 | Carry the count caveat when quoting "200+ builds" (actual 488, snapshot 2026-07-14)                                                                | Low    | S      | Documentation |
| 18 | Decide repo position on x402/USDC payments: ignore vs track for agent autonomy                                                                     | Low    | S      | Documentation |

### Cluster 2 — Known repo gaps surfaced by comparison (from docs read this session)

| #  | Task                                                                                                                           | Impact   | Effort | Category      |
| -- | ------------------------------------------------------------------------------------------------------------------------------ | -------- | ------ | ------------- |
| 19 | Implement emergency-calling dialplan gap: route 112/911 to the DIDWW trunk (documented in providers README verdict #2)         | Critical | M      | Feature       |
| 20 | Add a VM test asserting the emergency extensions exist in generated XML (mirror the denial-path tests)                         | High     | M      | Quality       |
| 21 | Confirm DIDWW emergency-calling product details (per-country table) — the decision-critical differentiator                     | High     | M      | Quality       |
| 22 | Run a quality A/B on Zadarma budget DIDs before trusting "trial-grade" for real traffic                                        | Medium   | M      | Quality       |
| 23 | Re-verify didlogic per-trunk max-call-cost docs as the model spec for agent-driven outbound caps                               | Medium   | S      | Quality       |
| 24 | Record the trunk decision in ROADMAP.md + retire TODO_LIST rows once purchases start (providers README maintenance rule)       | Medium   | S      | Documentation |
| 25 | Extend question framework §3: "open examples catalog? machine-readable signup? no-key demo endpoints?" as provider-DX criteria | Medium   | S      | Documentation |
| 26 | Schedule next Telnyx re-verification in providers README (current: 2026-08-27/29)                                              | Low      | S      | Documentation |

### Cluster 3 — "Steal the idea" repo work

| #  | Task                                                                                                                              | Impact | Effort | Category      |
| -- | --------------------------------------------------------------------------------------------------------------------------------- | ------ | ------ | ------------- |
| 27 | Add `llms.txt` / `docs/agents.md` making flake options, VM suites, and runbook machine-readable for AI sessions                   | Medium | M      | Documentation |
| 28 | Generate a builds-style index of our VM test suites (name, what it proves, how to run) as a flake-check artifact                  | Medium | M      | Documentation |
| 29 | Upgrade voicemail: use `ai-voicemail-transcription-forwarding` as spec (STT + summary → email/SMS) on top of mod_voicemail mailer | Medium | M      | Feature       |
| 30 | Adopt warm-transfer-ai-briefing / call-whisper patterns for CV human-in-the-loop bridging UX                                      | Medium | M      | Feature       |
| 31 | Use `cdr-usage-analytics-dashboard` build as starting point for our CDR feature (pbx-prod has CDR enabled)                        | Medium | M      | Feature       |
| 32 | Use `e911-address-validator` build as UX reference when the emergency-calling gap closes                                          | Medium | S      | Feature       |
| 33 | Consider `ivr-prompt-generator` to produce IVR prompt audio instead of hand-written TTS strings                                   | Low    | S      | Feature       |
| 34 | Evaluate `storage-voicemail-archive` (S3-compatible) vs our local StateDirectory voicemail storage                                | Low    | S      | Feature       |
| 35 | Prototype `click-to-call-webrtc-with-ai-assist` against our SIP.js webphone as UX comparison                                      | Low    | M      | Feature       |
| 36 | Keep `migrate-from-twilio` in reserve for any legacy Twilio/TeXML import                                                          | Low    | S      | Documentation |
| 37 | Watch deepfake-detector + number-reputation builds for future fraud posture once agent outbound exists                            | Low    | S      | Documentation |
| 38 | Track the team-telnyx `ai` repo (agent CLI source) for releases worth pinning in notes                                            | Low    | S      | Documentation |
| 39 | Conference note-taker pattern if multi-party becomes a requirement                                                                | Low    | S      | Documentation |
| 40 | Shallow-clone `telnyx-code-examples` when the full 488-catalog tail is needed (canonical source)                                  | Low    | S      | Quality       |

### Cluster 4 — Session/process hygiene

| #  | Task                                                                                                                       | Impact | Effort | Category      |
| -- | -------------------------------------------------------------------------------------------------------------------------- | ------ | ------ | ------------- |
| 41 | Soften or verify the "nobody else does agent-first commerce" claim before it enters any repo doc                           | Medium | S      | Quality       |
| 42 | Verify build-quality claims by opening ≥1 representative repo (e.g. `ai-hiring-phone-screen`) before praising/skewing      | Medium | S      | Quality       |
| 43 | Note in AGENTS.md: Telnyx Builds catalog location + JS-chunk extraction method for future sessions                         | Low    | S      | Documentation |
| 44 | Note in AGENTS.md: JS-rendered marketing sites need data-layer archaeology, not DOM fetches                                | Low    | S      | Documentation |
| 45 | Check crush logs for the `agentic_fetch` token expiry (tooling issue to report if recurring)                               | Low    | S      | Cleanup       |
| 46 | End-to-end agent-chain test when KYC lands: signup → key → demo endpoint → real call; document in ops-runbook              | Medium | M      | Quality       |
| 47 | Providers README: add "Agent tooling" row detail to the matrix only if it changes a verdict (avoid drift)                  | Low    | S      | Documentation |
| 48 | Harvest this report's (f) into TODO_LIST.md / ROADMAP.md via docs-health HARVEST                                           | High   | S      | Documentation |
| 49 | Persist session leads (b-2) into `telnyx.md` — same-commit rule                                                            | High   | S      | Documentation |
| 50 | After the trunk decision lands: delete in-chat review knowledge from heads and put it in files (this report is the bridge) | Low    | S      | Documentation |

## g) Questions I cannot figure out myself

1. **CV-system = hiring/curriculum-vitae pipeline?** I inferred this from "CV-system integration, human-in-the-loop" in `docs/providers/README.md` and picked `ai-hiring-phone-screen` / `interview-screen-scheduler` as the flagship references. Tried: repo docs — the term is never expanded. If CV means something else (e.g. a specific internal system), my reference picks change.
2. **Do you already have a Telnyx account (or is US-local-day-one still pending)?** This unblocks the whole portal-verification cluster: T.38 question to support (f-3), sub-accounts (f-7), fraud caps (f-8), SRTP/TLS (f-9), and demo-endpoint prototyping (f-12). I cannot create the account for you (KYC is yours).
3. **Persist now or review first?** Should I (a) write the leads into `docs/providers/telnyx.md` and HARVEST section (f) into `TODO_LIST.md`/`ROADMAP.md` immediately, or (b) hold until you've read this report? The maintenance rules push toward (a); your call on doc churn.

---

_Point-in-time snapshot — annotate, never rewrite. Section (f) is the HARVEST input; it dies here if not routed into `TODO_LIST.md`/`ROADMAP.md`._

---

## Addendum (2026-08-29 18:39 — user answered g-Q1)

**g-Q1 answered:** "CV system" = `~/projects/CV system` — automates Lars's **sales pipeline for software-development services**. Not applicant hiring.

**Consequence:** the review's reference-build mapping (chat table + f-6, feeding f-4) pointed at the wrong cluster. Hiring-screen builds screen _applicants_ — the inverse direction of selling services. Corrected reference cluster for the CV system (all verified to exist in the 488-catalog this session):

| Build                                                                        | Why it fits a dev-services sales pipeline                                                                         |
| ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `autonomous-outbound-sales-agent`                                            | lead qualification + objection handling + meeting booking — the core loop                                         |
| `ai-sales-demo-booking-agent`                                                | qualify inbound, book the call — the funnel entry                                                                 |
| `ai-sales-call-with-live-crm-updates`                                        | live deal intelligence on a call Lars joins — exact human-in-the-loop fit                                         |
| `global-lead-response-engine`                                                | multi-language qualification + live transfer + omnichannel follow-up — matches the DE/CH/PL/HK/US mix             |
| `number-lookup-lead-enrichment`                                              | qualify/score leads before dialing                                                                                |
| `number-warmup-reputation-builder` + `number-reputation-monitor-auto-rotate` | **new, not in the original list** — outbound sales dialing hygiene; spam-flagged caller ID kills a sales pipeline |
| `interview-screen-scheduler`                                                 | still relevant as a _pattern_ (campaign dialer + scoring + calendar booking), direction inverted                  |

**Downstream corrections for HARVEST:**

- f-4 (CV-integration ADR) and f-6 (reference implementations) must use the sales cluster above, not the hiring pair.
- f-23 (didlogic max-call-cost cap parity) **rises in priority**: an agent-driven _outbound sales_ dialer multiplies cost-runaway and anti-spam compliance risk (STIR/SHAKEN, in-country CLI rules — framework Q8/Q36, HK OFCA 2023).
- g-Q2 (Telnyx account?) and g-Q3 (persist/HARVEST now vs wait) remain **open**.

---

## Addendum 2 (2026-08-29 — research executed per user instruction)

Follow-up research cracked the four open ❓s from `docs/providers/telnyx.md` **at OpenAPI-spec level** (public `team-telnyx/openapi` `spec3.json`, fetched 2026-08-29; local grep of the 6.7 MB spec):

| Open item                        | Result                 | Evidence (spec schema / path)                                                                                                                                                                                                                                                                                      |
| -------------------------------- | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| T.38 fax on trunk                | **✅ real trunk T.38** | per-number `t38_fax_gateway_enabled` (Telnyx _accepts_ re-INVITE — matches our mod_spandsp `rxfax`); outbound `t38_reinvite_source` (Telnyx sends re-INVITE by default; requires **Fax-type OVP**); `onnet_t38_passthrough_enabled`; Fax API `SendFaxRequest.t38_enabled` as PBX-free alternative                  |
| SRTP/TLS per connection          | **✅**                 | `sip_transport` enum `udp\|tcp\|tls`; `encrypted_media` on credential/FQDN/IP connections; Call Control `media_encryption` SRTP/DTLS                                                                                                                                                                               |
| Sub-account separation           | **✅ API feature**     | `/v2/managed_accounts` CRUD (own `api_key` per sub-account, `rollup_billing`), `allocatable_global_outbound_channels` pool + `update_global_channel_limit`, `/v2/organizations/users`                                                                                                                              |
| Fraud guardrails vs didlogic bar | **✅ exceeds bar**     | OVP: `daily_spend_limit`, `max_destination_rate` (per-call-cost analog), `concurrent_call_limit`, `whitelisted_destinations`, `calling_window`, `traffic_type`; per-number `inbound_call_screening` (reject/flag, paid). Note: no literal `max_call_cost` field; "Fraud Alerts" is a 10DLC category, not a product |

Also verified this pass:

- `autonomous-outbound-sales-agent-python` opened: genuine Call Control campaign app (`POST /v2/calls`, `call.gather.ended` speech, Number Lookup pre-screen, AI Inference loop, client_state) — the report's d-4 "unverified quality" claim is now partially retired for this build.
- `fax-to-structured-data-pipeline-python` opened: uses the **Fax API** (Fax Application + `fax.received` webhook + media URL) — provider-side fax, distinct from trunk T.38; both paths now documented.
- Telnyx agent surface (`telnyx.com/llms.txt`): `/ai/pricing.json`, `/ai/capabilities.json`, `/ai/sla.json` (99.99% claim), 247 agent skills, MCP apps catalog, `@telnyx/agent-cli`. **Correction to Addendum/earlier review:** the TTS/STT/inference demo endpoints are origin-checked and NOT scriptable; only the SMS demo is scriptable.

**Persisted (same-commit rule):** `docs/providers/telnyx.md` (trunk-fit ❓→✅ TLS/SRTP + T.38; commercial ❓→✅ sub-accounts + guardrails + agent surface; 3 new source rows), `docs/providers/README.md` (matrix fax cell ✅, fax-posture paragraph updated).

**Still open:** g-Q2 (Telnyx account / KYC sequencing), full HARVEST of section (f) into TODO_LIST/ROADMAP (partially overtaken by events — items f-2, f-3, f-7, f-8, f-9 are now DONE by this research).
