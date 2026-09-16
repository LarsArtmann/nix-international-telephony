# SIP / Telephony Ecosystem Survey

Point-in-time research snapshot: **2026-09-16**. Origin: the questions
"any good Go-based SIP project?", "what is best regardless of language?",
and "people love LiveKit — are we using it, and if not why not?".

All GitHub figures below (stars, push dates, release tags) were pulled from
the GitHub REST API (`gh api repos/<name>`, `.../releases/latest`,
`.../search/repositories`) on **2026-09-16** and will rot — re-verify before
building decisions on them, same discipline as `docs/providers/`.

## Verification status

| Claim class                                                        | Status        | Source                                                                                  |
| ------------------------------------------------------------------ | ------------- | --------------------------------------------------------------------------------------- |
| Stars / push dates / archived flags for every repo listed          | ✅ Verified   | `gh api repos/<owner>/<name>` + `search/repositories`, 2026-09-16                       |
| Release tags: Kamailio 6.0.8, Asterisk 23.5.0, FreeSWITCH v1.11.3, | ✅ Verified   | `gh api repos/<name>/releases/latest`, 2026-09-16                                       |
| rtpengine mr26.2.1.1, sipgo v1.5.0                                 | ✅ Verified   | same                                                                                    |
| `pion/sip` no longer exists (404); sipgo has zero pion deps        | ✅ Verified   | `gh api repos/pion/sip` → 404; `sipgo/contents/go.mod` read (gobwas/ws, icholy/digest)  |
| jart/gosip capabilities (SSE mixing, asm µLaw, SRV/NAPTR failover) | ✅ Verified   | repo README read via API, 2026-09-16                                                    |
| OpenSIPS latest version                                            | ❌ Not captured | repo has no GitHub Releases endpoint; activity only (pushed 2026-09-11)               |
| LiveKit "Docker-first" distribution                                | ⚠️ Inference  | `livekit/sip` `releases/latest` → 404; no other channel checked                         |
| jart = Justine Tunney; miconda = Kamailio co-founder               | ⚠️ Reputation | widely-known identity claims, not re-verified this session                              |
| jambonz = "the go-to open-source AI-voice stack"                   | ⚠️ Reputation | ecosystem reputation; only `jambonz/jambonz-api-server` (⭐24) queried directly          |
| LiveKit packaged in nixpkgs                                        | ❓ Not checked | never evaluated                                                                         |

## The layer map (best-of-breed, language-agnostic)

"Best" is per-layer. The canonical open-source production stack is:
**Kamailio (+ rtpengine) in front of a FreeSWITCH or Asterisk core.**

### Signaling / SBC (routing, TLS, topology hiding, fraud control)

- **Kamailio** — the gold standard SIP proxy/router; carrier-scale.
  `kamailio/kamailio` ⭐2,949 · **6.0.8** (released 2026-09-16) · pushed same day.
- **OpenSIPS** — the #2, similar DNA (both trace to the OpenSER split).
  `OpenSIPS/opensips` ⭐1,525 · pushed 2026-09-11.

### Media proxy / RTP handling

- **rtpengine** (Sipwise) — *the* standard media proxy: NAT traversal,
  SRTP↔RTP bridging, WebRTC offload. `sipwise/rtpengine` ⭐988 ·
  **mr26.2.1.1** (2026-08-21). Kamailio+rtpengine in front of the PBX is
  the canonical production pattern.

### PBX / media server

- **FreeSWITCH** — best media engine + conferencing; **this repo's core**.
  `signalwire/freeswitch` ⭐5,154 · **v1.11.3** (2026-08-28) · pushed 2026-09-16.
- **Asterisk** — bigger ecosystem, easier classic-PBX ergonomics; neither
  is beaten in its niche. `asterisk/asterisk` ⭐3,542 · **23.5.0** (2026-08-27).

### Programmable / CPaaS (call apps, voice AI)

- **jambonz** — drachtio + rtpengine + Node feature server; the reputation
  pick for AI-voice call flows. `drachtio/drachtio-server` ⭐331
  ("SIP call processing server controlled via Node.js", pushed 2026-08-20);
  `drachtio-srf` pushed 2026-09-14.
- **Fonoster + routr** — "open-source alternative to Twilio" (its own
  description) + "programmable SIP server". `fonoster/fonoster` ⭐8,112
  (pushed 2026-09-14) · `fonoster/routr` ⭐1,708 (pushed 2026-09-08).
  Modern, but younger than jambonz.

### WebRTC SFU (only if outgrowing 1:1 calls)

- **LiveKit** `livekit/livekit` ⭐20,950 · **mediasoup** ⭐7,367 ·
  **Janus** `meetecho/janus-gateway` ⭐9,164 — all pushed within a day of
  the snapshot.

### Clients / endpoint libraries

- **pjproject** (`pjsip/pjproject` ⭐2,688) — the native softphone/media
  library everything embeds.
- Browser: **SIP.js** (`onsip/SIP.js` ⭐2,096, pushed 2026-06-15 — this
  repo's webphone, alive) · **JsSIP** (`versatica/JsSIP` ⭐2,602).

## Go SIP ecosystem

| Project                     | What it is                                                        | Status (2026-09-16)                    |
| --------------------------- | ----------------------------------------------------------------- | -------------------------------------- |
| `emiago/sipgo`              | The go-to Go SIP library: UA, transactions, dialogs, UDP/TCP/TLS/WS; absorbed the pion/sip niche (zero pion deps, verified via go.mod) | ⭐1,068 · v1.5.0 (2026-08-18) · pushed 2026-09-13 |
| `emiago/diago`              | High-level VOIP app layer on sipgo (calls, registrations, media API). Siblings: `gophone` (CLI softphone, ⭐110), `diagox` (SIP↔WebRTC ingress/egress, ⭐33), `sipgox` ⭐77 | ⭐410 · pushed 2026-09-11 |
| `jart/gosip`                | Single-binary PSTN calling; SSE audio mixing, asm µLaw (only codec), comfort noise, SRV/NAPTR failover; opinionated, v0.1 | ⭐538 · pushed 2026-06-23 |
| `ghettovoice/gosip`         | Classic full SIP stack (UA, proxy, registrar, session router)      | ⭐526 · pushed 2026-08-22, historically sporadic |
| `livekit/sip`               | SIP↔WebRTC bridge into LiveKit rooms                              | ⭐468 · pushed 2026-09-16 · no GitHub Releases (Docker-first, inferred) |
| `miconda/sipexer`           | Modern CLI SIP tool (handy for ops probes)                        | ⭐419 · pushed 2026-09-11 |
| `cloudwebrtc/go-sip-ua`     | Go UA for client/b2bua                                            | ⭐236 · stale since 2024-08 |
| `panjjo/gosip`              | GB28181 sipserver (video-surveillance niche)                      | ⭐436 · pushed 2024-10 |
| `marv2097/siprocket`        | Fast SIP/SDP parser only                                          | ⭐74 |

**There is no mature full PBX in Go** — FreeSWITCH/Asterisk keep that role.
The Go ecosystem is strongest for *building call-processing services*
around (or instead of) a PBX.

### Go ↔ FreeSWITCH integration (relevant to this repo)

- `percipia/eslgo` ⭐141 (pushed 2026-09-09) — best-maintained ESL wrapper;
  `cgrates/fsock` ⭐75 (pushed 2026-09-07) also active.
- `0x19/goesl` ⭐142 stale (2023-08); `fiorix/go-eventsocket` ⭐138 (2024-09).
- `gonicus/gofaxip` ⭐140 (pushed 2026-04-20) — T.38-over-IP backend for
  HylaFAX using FreeSWITCH; directly relevant to the mod_spandsp fax
  posture (docs/providers/).

## LiveKit: are we using it? No — deliberately.

**Verified absence (2026-09-16):** `flake.nix` inputs are exactly
`nixpkgs`, `nix-ssh-config`, `flake-parts`, `treefmt-nix`,
`git-hooks-nix`, `disko`. The only repo mention of LiveKit is
`docs/providers/didlogic.md` (section "Programmable voice / agent
readiness"), where it appears as *someone else's* agent runtime that
BYOC DID providers sit under — not part of our stack.

**Why not:**

1. Different problem. LiveKit is a WebRTC SFU (distribute media to many
   receivers; human+AI rooms). It is not a PBX: no voicemail, IVR, ring
   groups, CDR, gateway auth — all of that lives in FreeSWITCH here, and
   multi-party audio is already covered by `mod_conference` (VM-tested,
   `tests/conference.nix`).
2. The browser leg is solved. SIP.js → nginx `wss` → sofia `wss`-binding
   works and is browser-E2E-tested. Adding LiveKit inserts a second media
   stack plus its SIP bridge between browser and PBX: two ICE/TLS/NAT
   surfaces for zero gain at 1:1 PSTN-call scale.
3. Nix cost. LiveKit + its SIP agent would be new flake inputs to package
   and harden — against the no-FusionPBX-style-additions spirit of this
   repo.

**When it would earn its place:** voice-AI agents on real calls (the
Retell/Vapi-style pipeline the provider docs anticipate) or multi-party
video. LiveKit Agents + `livekit/sip` fronting or replacing FreeSWITCH
for the agent leg is what the hype is about. Revisit only if that becomes
a roadmap item — not before.

## Bottom line

- The FreeSWITCH + SIP.js + coturn core is best-of-breed; nothing here to
  be jealous of.
- The one layer we deliberately don't have is **Kamailio + rtpengine as
  an SBC front door** — worth it only when pbx-prod faces hostile
  internet traffic at real scale.
- If a Go sidecar for call logic is ever wanted: **sipgo** (+ **diago**
  for higher level) is the starting point.
