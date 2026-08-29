# Telnyx

> **Verdict: primary trunk + future agent-calling platform.** The only
> self-serve provider that combines full 5-country DID coverage with a
> complete programmable-voice stack (Call Control API, media streaming,
> AMD, TTS/STT). Price: heavy KYC patience for DE/CH/PL and HK is
> business-only.

- **Type:** US CPaaS + carrier (owns network and IP space — stated on
  their Germany DID page)
- **Model:** self-serve portal + full REST APIs, prepaid
- **Coverage:** 131 countries inbound (their global-coverage claim);
  all five of ours: DE, CH, PL, HK (national only), US

## Numbers & coverage (our 5 countries)

| Country | Local | National | Toll-free | Notes |
| ------- | ----- | -------- | --------- | ----- |
| DE | ✅ | ✅ | ✅ | Address must match the DID area code for local; national only needs a German address matching PoA/ID; toll-free business-only |
| CH | ✅ | — | ✅ | Business-only, local business register extract, ~72h |
| PL | ✅ | — | ✅ | Local address + ID or company papers |
| HK | — | ✅ | ✅ | National (2xxx/3xxx) business-only + HK Tripartite Agreement + HK address proof |
| US | ✅ | — | ✅ | No KYC, instant, E911 available |

Pricing ballpark (their pricing pages, 2026-08): numbers from ~$1/mo
(volume discounts to $0.25 at 5k+), inbound origination from
~$0.0032/min, Voice API base ~$0.002/min + trunk fee, outbound per
destination (DE local ~$0.01–0.03/min, HK ~$0.01–0.05/min,
PL ~$0.03–0.11/min).

## Germany KYC — verified in detail (2026-08-29)

From `support.telnyx.com/en/articles/1311450-germany-did-requirements`:

- **Local, personal:** name + phone + local ID/passport + signed
  Germany registration form. **Address must match the DID area code**
  + utility bill < 3 months. Physical presence in Germany when
  purchasing.
- **Local, business:** representative + company name + local company
  registration certificate + German company registration number +
  signed/stamped registration form.
- **National:** same identity docs; address only has to be in Germany
  and match the PoA/ID — **personal identity is allowed**.
- **Toll-free:** business-only; LOI, PoA, place of birth, service
  usage + marketing description in German.
- **EU exception:** any EU passport/ID counts as "local" for EU
  purchases.
- Validation takes ~72 hours after document upload; inbound stays
  dead until verified.

## Voice trunk fit (FreeSWITCH)

- **SIP trunking with dedicated FreeSWITCH guides**: IP trunk
  (IP-auth) and credentials trunk (registration) both officially
  documented — `support.telnyx.com/en/articles/1616935-freeswitch-ip-trunk-setup`
  and the FreeSWITCH trunk-configurations collection.
- Plugs directly into our `services.telephony.gateways.itsp` shape
  (proxy + username/password, or IP-auth with `allowedCidrs` +
  `firewall.restrictExternalTo` against their source ranges).
- TLS + SRTP: ✅ verified in the public OpenAPI spec (fetched
  2026-08-29): connection `sip_transport` enum is `udp|tcp|tls`, and
  `encrypted_media` exists on credential/FQDN/IP connections (Call
  Control additionally takes per-leg `media_encryption` SRTP/DTLS).
- T.38 fax: ✅ verified in the OpenAPI spec (fetched 2026-08-29) —
  real trunk-level T.38, not just the Fax API: per-number inbound
  `t38_fax_gateway_enabled` (Telnyx ACCEPTS a T.38 re-INVITE —
  exactly what our FreeSWITCH/mod_spandsp `rxfax` path sends);
  outbound `t38_reinvite_source` on credential/FQDN/IP connections
  (Telnyx sends the re-INVITE by default, `customer` = caller sends;
  requires a **Fax-type Outbound Voice Profile**); plus
  `onnet_t38_passthrough_enabled` per connection. The Fax API
  (`SendFaxRequest.t38_enabled`, `fax.received` webhooks + media
  endpoint) is the PBX-free alternative — see the
  `fax-to-structured-data-pipeline` build.
  Fax-type OVP remains the one setting to eyeball in the portal at
  purchase time.

## Programmable voice / agent readiness (the CV integration)

Verified from the developer docs navigation (2026-08-29,
`developers.telnyx.com/docs/voice/programmable-voice`):

- **Voice API (Call Control):** commands + webhooks — programmatic
  origination, bridging, transfers. This is the "agent places a call,
  bridges me in" primitive.
- **TeXML:** Twilio-compatible XML stack (cheap migration path).
- **Real-Time Media Streaming** (websocket audio to an AI service),
  **Conversation Relay**, "Attach an AI Assistant to a Call",
  **Gather Using AI**, noise suppression, deepfake detection.
- **AMD** (answering-machine detection), TTS, STT, call queueing,
  call recordings storage, SIPREC, conferencing.
- They even publish `llms.txt` endpoints "For AI Agents" — the
  platform is explicitly courting agent-driven calling.

This is the strongest match in the field for the long-term vision
(CV system → agent/AI-assisted outbound calls with human-in-the-loop).

Alternative execution path that needs **no** provider API: our own
FreeSWITCH already exposes programmatic origination over the event
socket (`originate user/1000 &bridge(sofia/gateway/itsp/<e164>)`),
covered by our VM tests. Telnyx Call Control is the second engine,
useful when a call should exist entirely outside the PBX.

## Messaging

SMS API including international; US 10DLC/CNAM/STIR-SHAKEN story is
mature (their focus market). A2P pricing per destination — fine as an
adjunct, not a trunk-decider.

## Commercial & account

- Self-serve, no contracts, pay-as-you-go.
- Sub-accounts: ✅ verified in the OpenAPI spec (2026-08-29):
  `/v2/managed_accounts` CRUD (each sub-account gets its own
  `api_key`/`api_token`; `rollup_billing` onto the manager) + an
  allocatable global outbound channel pool
  (`allocatable_global_outbound_channels`,
  `update_global_channel_limit`) + `/v2/organizations/users` (+
  groups) for portal roles. Multi-company separation is an API
  feature, not a portal support ticket.
- Fraud controls: ✅ verified in the OpenAPI spec (2026-08-29) —
  Outbound Voice Profiles carry the guardrail set, which EXCEEDS the
  didlogic per-trunk max-call-cost bar: `daily_spend_limit` (+
  enable flag), `max_destination_rate` (per-minute rate cap — the
  per-call-cost analog), `concurrent_call_limit`,
  `whitelisted_destinations`, `calling_window`, `traffic_type`.
  Per-number `inbound_call_screening` (`reject_calls`/`flag_calls`)
  adds fraud screening at extra monthly cost. Caveat: "Fraud
  Alerts" is only a 10DLC campaign category, not a product. The
  CV-system outbound dialer MUST sit behind such an OVP.
- Agent-machine surface: ✅ verified (2026-08-29) —
  `telnyx.com/llms.txt` (machine-readable `/ai/pricing.json`,
  `/ai/capabilities.json`, `/ai/sla.json` with a 99.99% uptime
  claim, `/ai/rate-limits.json`), `agent-signup.md` (bot-challenge
  signup), `/.well-known/agent-access.json` demo endpoints (⚠️ the
  inference/TTS/STT demos are origin-checked and NOT scriptable;
  only the SMS demo is scriptable), MCP at `api.telnyx.com/v2/mcp`
  (+ per-app endpoints under `/v2/mcp/apps`), 247 agent skills,
  `@telnyx/agent-cli`.

## Risks

- KYC lead time for DE/CH/PL (~72h+, physical-presence rules for DE
  local) and HK business-only — the operational cost of the primary
  pick.
- Number portability out: standard US/CA; international ❓ per
  country.

## Sources & verification status

| Claim | Status | Source |
| ----- | ------ | ------ |
| 5-country coverage, HK national-only | sourced | support.telnyx.com/en/articles/1424680-international-coverage + telnyx.com/global-coverage (researched 2026-08-27) |
| Germany KYC details | ✅ verified | support.telnyx.com/en/articles/1311450-germany-did-requirements (fetched 2026-08-29) |
| CH/PL/HK DID requirements | sourced | support.telnyx.com articles 3739580 / 5466967 / 3739447 (researched 2026-08-27) |
| FreeSWITCH trunk guides | sourced | support.telnyx.com/en/articles/1616935 + FreeSWITCH trunk-configurations collection (2026-08-27) |
| Call Control, TeXML, media streaming, AMD, AI-assistant, llms.txt | ✅ verified | developers.telnyx.com/docs/voice/programmable-voice nav (fetched 2026-08-29) |
| Pricing ballparks | sourced | telnyx.com/pricing/numbers, /pricing/voice-api (2026-08-27) — re-check at purchase |
| T.38 trunk fax, TLS/SRTP, OVP guardrails, managed accounts/organizations | ✅ verified | github.com/team-telnyx/openapi `openapi/spec3.json` (fetched 2026-08-29); fax mechanism corroborated by `fax-to-structured-data-pipeline-python` README in team-telnyx/telnyx-code-examples (fetched 2026-08-29) |
| Agent surface: llms.txt, agent-signup.md, demo endpoints, MCP, agent skills, agent CLI | ✅ verified | telnyx.com/llms.txt + telnyx.com/agent-signup.md (fetched 2026-08-29) |
| Builds catalog: 488 examples incl. outbound-sales + fax builds | ✅ verified | team-telnyx/telnyx-code-examples (catalog snapshot generated 2026-07-14; repo active 2026-08-28; fetched 2026-08-29) |
