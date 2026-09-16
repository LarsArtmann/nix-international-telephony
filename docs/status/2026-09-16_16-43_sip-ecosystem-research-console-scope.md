# Status Report — SIP Ecosystem Research & Console Scoping

Point-in-time snapshot: **2026-09-16 16:43 CEST**. Scope: this session only —
a research/advisory thread (Go SIP projects → best-of-breed stack → LiveKit →
PBX GUIs → console concept). **No production code was touched**; artifacts
produced: one research doc + this report.

Skill-format overrides (deliberate, user-mandated): `.md` instead of the
status-report skill's HTML default, and the self-review folded into this one
file instead of a separate `docs/reviews/` HTML. No manual commit (auto-commit
daemon owns commits).

## a) FULLY DONE

1. **Go SIP ecosystem surveyed, evidence-grade** (GitHub API, 2026-09-16):
   `emiago/sipgo` ⭐1,068 · v1.5.0 · active; `emiago/diago` ⭐410 + gophone/
   diagox/sipgox siblings; `jart/gosip` ⭐538 (µLaw/SSE, v0.1);
   `ghettovoice/gosip` ⭐526; `miconda/sipexer` ⭐419; ESL libs
   (`percipia/eslgo`, `cgrates/fsock` active; `0x19/goesl` stale);
   `gonicus/gofaxip` ⭐140 (T.38 posture-relevant). Confirmed `pion/sip` is
   gone (404) and sipgo's go.mod carries zero pion deps.
2. **Language-agnostic best-of-breed map verified**: Kamailio 6.0.8
   (released today), rtpengine mr26.2.1.1, FreeSWITCH **v1.11.3** (2026-08-28),
   Asterisk 23.5.0, drachtio(-server/-srf), Fonoster ⭐8.1k + routr ⭐1.7k,
   LiveKit/mediasoup/Janus all pushed within a day; browser libs: SIP.js
   (`onsip/SIP.js`, ours, alive) vs JsSIP.
3. **LiveKit question closed**: verified NOT used (flake inputs enumerated;
   sole mention is `docs/providers/didlogic.md`); why-not documented
   (SFU≠PBX; browser leg already solved; Nix cost) + explicit revisit
   conditions (voice-AI agents / multi-party video).
4. **`docs/research/2026-09-16_sip-ecosystem-survey.md` created** —
   verification-status table per the verify-external-claims skill (verified
   vs reputation vs not-checked rows), staged with `git add`.
5. **PBX GUI landscape verified**: FusionPBX ⭐1,058 active; FS PBX
   (`nemerald-voip/fspbx`) ⭐233 · Laravel+Vue · Apache-2.0 · Debian
   curl-bash installer (README read raw); Kazoo core **stale since 2025-02**;
   dSIPRouter (Kamailio-only); `freeswitch_exporter` ⭐71.
6. **FusionPBX-vs-FreeSWITCH layer model explained** (engine vs cockpit,
   FreePBX name-trap) — verified C vs PHP via API.
7. **FS PBX vs this repo compared** on evidence (full FEATURES.md read +
   fspbx README): FS PBX = our feature set + GUI − declarative − tests −
   Nix fit; adopting it replaces the repo rather than extending it.
8. **Console concept scoped, then corrected to repo grain**: after the user
   caught the templ/HTMX/Tailwind import (see d1), verified the repo has
   zero of that tooling and zero Go builds; corrected design =
   `packages/console/` (buildGoModule + embed.FS + vanilla html/css/js
   matching webphone) + `modules/telephony/console.nix` + nginx `/console`
   basic-auth (recordings pattern) + ESL via LoadCredential.
9. **Pre-existing uncommitted changes noticed and left untouched**:
   `flake.nix`, `tests/backup.nix` modified before/during this session by
   another actor (not this session); flagged, not reverted.

## b) PARTIALLY DONE

1. **Console scope**: concept, file layout, integration points, milestones
   1-4 defined — but zero code/options written and no owner approval yet.
2. **Research doc coverage**: Go survey + layer map + LiveKit verdict are in;
   the later GUI comparison (FusionPBX/FS PBX/Kazoo) and console decision
   exist only in chat, not captured in any doc.
3. **Known verification gaps inside the research doc** (labeled there):
   OpenSIPS current version not captured (no GitHub Releases); LiveKit
   "Docker-first" inferred from missing releases endpoint only; nixpkgs
   LiveKit packaging never checked.
4. **FreeSWITCH version drift**: upstream v1.11.3 discovered; the version
   this repo's nixpkgs pin (nixos-unstable) actually ships was never
   checked — our engine version is unknown to this session.

## c) NOT STARTED

- `packages/console/` (main.go, default.nix, assets/) — nothing exists.
- `modules/telephony/console.nix` + `console.*` options + nginx location.
- Any TODO_LIST/ROADMAP/FEATURES capture of this session's outcomes
  (deliberate: this report first; harvest awaits owner instructions).
- UI/GUI comparison appended to research docs.

## d) TOTALLY FUCKED UP (advisory errors; nothing repo-broken)

1. **The templ + HTMX + Tailwind prescription.** Recommended a stack that
   exists in the owner's _other_ projects (templ-components) for THIS repo,
   which has none of it — caught by the user ("y-- where!?!"), verified and
   corrected same turn. Root cause: pattern-matched "Lars + Go + web UI"
   from cross-project memory instead of inspecting the repo's grain first.
2. **Two `agentic_fetch` calls failed** (tool-side json unmarshal) on the
   second turn — burned a round trip; `gh api` (which then carried the whole
   session flawlessly) should have been the first move for GitHub facts.
3. **From-memory repo guesses produced 404s** (`emiago/digo`, `wnark/gosip`,
   `0x6f6775/go-freeswitch-esl`, `onsi/SIP.js`, `FreePBX/freepbx`) — all
   caught by API verification before reaching any artifact, but search-first
   would have cost fewer queries than guess-then-verify.
4. **Sloppy phrasing**: "MIT-ish yours" in the FS PBX comparison table —
   this repo's top-level LICENSE was never verified.

## e) WHAT WE SHOULD IMPROVE (self-review answers, honest)

- **Forgot**: checking the nixpkgs-pin FreeSWITCH version once upstream
  drift surfaced; revisiting the fresh research doc at thread end to fold in
  the GUI-comparison turn; verifying the repo LICENSE before citing it.
- **Stupid-we-do-anyway (session-level)**: trusting cross-project stack
  memory over repo inspection; reaching for generic fetch tools before
  `gh api` for GitHub-verifiable facts.
- **Did I lie**: no; audit found one borderline — "pion/sip no longer
  exists" is 404-observed (deleted vs made-private is indistinguishable);
  the doc phrasing hedges this acceptably.
- **Ghost systems / split brains**: none created; one risk — the console
  decision lives only in chat until research/TODO capture it (b2/c).
- **Removed something useful**: no.
- **Tests**: no new code → no new tests owed this session; the console MUST
  ship with a VM suite from milestone 1 (auth 401 path, rendered data,
  ESL-secret splicing) — non-negotiable given this repo's CI gate.
- **Less stupid going forward**: (1) grep the repo before prescribing any
  tooling; (2) `gh api` first for GitHub facts; (3) end-of-thread pass over
  docs created mid-thread to absorb later-turn learnings.

## f) Next things (session-derived; ~30 quality items, not padded to 50)

_Console workstream (gated on g1):_

1. Owner decision: approve console milestone 1 (status page)
2. `packages/console/`: buildGoModule skeleton + embed.FS + zero-deps Go
3. Decide vendorHash strategy (zero deps → empty hash)
4. `modules/telephony/console.nix`: options (`enable`, `listenAddress`,
   `passwordFile`), hardened DynamicUser unit, `telephony` group
5. ESL wiring reusing `eventSocketPasswordFile` via LoadCredential
6. nginx `= /console` location + basic auth (recordings pattern, `{PLAIN}`)
7. Status data: trunk REG-state, registrations, active channels
8. VM suite `tests/console.nix` (auth + rendered status + secret splicing)
9. Milestone 2: voicemail list + browser WAV playback (sharing pattern)
10. Milestone 3: CDR table (parse `Master.csv` read-only)
11. Milestone 4: click-to-dial (`originate`) + webphone polish
12. Polling first; SSE only if the page demands it; htmx single-file only if
    vanilla JS grows past comfort
13. Webphone: persistent call history, contacts from the directory
14. Console + webphone: one login or two? (owner UX call, see g2)

_Research follow-ups:_

15. Append GUI comparison (FusionPBX/FS PBX/Kazoo + console decision) to
    research docs — or second dated file (g3)
16. Check nixpkgs (nixos-unstable) freeswitch version vs upstream v1.11.3
17. Verify OpenSIPS current version via tags endpoint if SBC research resumes
18. `sipexer` into the devShell for SIP endpoint probing
19. `freeswitch_exporter` + Grafana observability spike (optional, dismissed
    for console but still valid for metrics)
20. `gofaxip` spike against the docs/providers fax posture
21. HARVEST this report into TODO_LIST/ROADMAP once owner answers g1-g3
22. Re-verify the research doc's stars/dates before any purchase/build
    decision built on them (they rot)

_Noticed pre-existing TODO_LIST rows (not this session's work, still open):_

23. Backups + alerting sink (restic/Hetzner, OnFailure routing) — existing row
24. Real-disk-boot VM test (disko image through target bus) — existing row
25. AGENTS.md headroom migration (at doctor cap) — existing row
26. BuildFlow ergonomics probes (env var, dev/fast default) — existing row

_Session hygiene:_

27. Verify the repo's top-level LICENSE (cited unverified in d4)
28. Trace origin of the pre-existing `flake.nix` + `tests/backup.nix`
    modifications before building on top of them
29. DOMAIN_LANGUAGE entry for "console" if it becomes a real concept
30. If console lands: aarch64/TCG sizing of its VM test (fixed 300s window)

## g) Questions for the owner (cannot be figured out from the repo)

1. **Build the console?** Approve milestone 1 (status page) in this repo —
   config stays 100% Nix, console strictly read-only over ESL/files?
2. **Who is the console for?** Just you (shared basic-auth password,
   recordings-style) or end users too (per-extension accounts → auth design
   changes significantly)?
3. **Research doc continuity:** append the GUI comparison as a follow-up
   section to today's research doc, or start a second dated file?

— END OF REPORT. Waiting for instructions.
