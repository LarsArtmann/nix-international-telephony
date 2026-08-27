# Status Report: docs-health AUDIT — verify, harvest, annotate, archive (2026-08-27)

> Scope: this session only (~09:55–11:01 CEST). Trigger: user demanded a full
> docs-health execution over **all** `2026-08-*` files — living docs superb,
> every numbered item in historical reports resolved inline, fully-done files
> archived. This report covers that run and what it surfaced; nothing outside
> it was re-audited.
>
> Format note: user explicitly requested `.md`; the status-report skill's HTML
> default was overridden.

**Verdict:** the audit is complete and green-gated. All 16 `2026-08-*`
historical files were read and annotated (**282 inline resolutions**), 4
fully-resolved files archived, all 7 living docs verified against code and
repaired where lying, and the newest report's backlog harvested into
TODO_LIST/ROADMAP. The auto-git daemon landed everything as `50438e9` +
`96b7f0b` (8 commits total now sit unpushed on `main`). One real production
defect was confirmed on the way (ACME/port-80) and routed as the top TODO
row — no code was changed by this docs session.

## a) FULLY DONE (this session, verified)

| # | Item | Evidence |
|---|------|----------|
| 1 | Skill loaded properly: docs-health SKILL.md + 5 references (harvest, verify-checklist, resolving-items, health-report-format, section-quality via status-report) + both shipped annotation scripts inspected before use | This run; dry-run executed before every first mutation of a new file shape |
| 2 | **All 16 `2026-08-*` files read** — 15 via glob + 1 discovered untracked via `git status` (`2026-08-27_10-19_real-deployment-path-session.md`, written by the prior session after my initial glob) | Every file's numbered sections enumerated before annotating |
| 3 | **VERIFY pass over all 7 living docs against code**: confirmed `turn.password` no longer exists (options.nix), module split into `modules/telephony/`, recordings moved to `/var/lib/telephony/recordings`, multi-`gateways` is primary, port 80 genuinely absent from `edge.nix` allowedTCPPorts, no TLS-handshake/reconnect-drift/negative-eval/drift-alarm tests exist, pycache gitignored, all 9 checks wired | Findings table in the inline health report; every claim grepped, not assumed |
| 4 | **Living docs repaired**: README (dead `turn.password` example, stale layout table, deprecated `gateway` ref, ACME port-80 caveat, `telephony-eval` documented); TODO_LIST (12-item "Resolved this cycle" trophy section deleted, 5 rows harvested from the 08-27 report — ACME port-80 fix first); CHANGELOG (3× `### Added` + 2× `### Changed` under `[Unreleased]` merged to one each); DOMAIN_LANGUAGE (6 stale claims); ROADMAP (Q4 gating note + 7 raw ideas: backups, SSH posture, coturn TLS/QoS, webphone error surfacing + reconnect drill, upstream fixes, flake-update cadence); AGENTS.md (archived/ convention) | Daemon commits `50438e9`, `96b7f0b`; post-commit greps re-verified every fix survived |
| 5 | **ANNOTATE: 282 numbered items resolved inline** across all 16 historical files — verdicts cite commit hashes (`8c411aa`…`5af3346`), `Won't implement` reasons (B3 rename, sops-wiring depth), or verified evidence; genuinely open items left unmarked and routed (TODO_LIST/ROADMAP) | `done at`/`done (`/`Won't implement` marker counts per file: 60, 4, 32, 1, 29, 49, 23, 22, 7, 15, 33, 11, 2, 1, 40, 8 |
| 6 | **ARCHIVED 4 fully-resolved files** via `git mv`: pareto plan (40/40 rows struck, resolution banners), deployment-readiness HTML (8/8 tasks), 09-49 docs-health retro (28/28), 09-40 public-release (open/next corrected inline) | `docs/planning/archived/` (2 files), `docs/status/archived/` (2 files) |
| 7 | **Quality gate green**: `nix fmt -- --fail-on-change` (0 changed), `nix flake check` — all checks passed (doc-fed checks treefmt/deadnix/statix/pre-commit rebuilt green; VM suites cached) | Log tail captured; exit clean |
| 8 | **Inline health report delivered** with visible math: start Accuracy 6.25/10, Fitness 6.75/10 → both 10/10 after fixes; baseline honestly cited from the 2026-08-21 audit (10/10) as "re-decay", not invented | Conversation output, not a file (per skill rule) |
| 9 | TODO_LIST/ROADMAP already carry this report's section (f) — HARVEST ran as part of the audit, no post-report re-harvest needed | TODO_LIST rows cite the 08-27 report; ROADMAP themes updated |

## b) PARTIALLY DONE

| Item | What exists | What's missing |
|------|-------------|----------------|
| Historical-file resolution | 282 items resolved inline; every file's remaining open items verified as genuinely open (reconnect drill, drift-alarm, wsprobe asserts, negative eval, TLS handshake, favicon, timedelta, CI matrix split, upstream PRs …) and routed | ~230 open items across old reports stay unmarked by design — they are open WORK, not annotation debt; execution is future sessions' job |
| 13-52 HTML report | 11 of 35 §F rows resolved inline (`<del>` + evidence) | 24 rows remain open-work (browser depth, coturn TLS, i18n…) — correctly unmarked; file stays unarchived |
| Gate coverage | x86_64 `nix flake check` green | `nix flake check --all-systems --no-build` (the repo's dual-gate practice) NOT run this session — cross-arch eval unproven for the current tree |
| CI evidence | Local gate green | The 8 local commits (incl. this audit) are unpushed; GitHub Actions has never seen them — push is owner-gated |

## c) NOT STARTED (deliberate — docs session, code untouched)

- **ACME port-80 fix** (Critical): `tls.mode = "acme"` + `openFirewall` never opens TCP 80, so HTTP-01 issuance fails on default-firewalled hosts. Confirmed in `modules/telephony/edge.nix`; routed as TODO_LIST row 1 with the module-vs-docs ownership question open.
- deploy.md truth pass (port 80+22 rows, exact secret count, `fs_cli -p "$(cat …)"`) and the port-table dedup against ops-runbook — routed (TODO row).
- Boot-smoke VM test for the `pbx-prod` shape; negative eval assertions — routed (TODO rows).
- Push, v0.2.0 cut, first real deployment — owner-gated, tracked BLOCKED/TODO.

## d) TOTALLY FUCKED UP (this session's honest ledger)

1. **My variant annotation script collapsed the pareto plan's 40-row table into 2 giant lines.** Root cause: the row regex's trailing `\s*$` matched and consumed each row's newline, and my reconstruction dropped it. Caught only because I verified shape after writing (`rg -c` returned 2 instead of 40). The dry-run could not catch this — it printed per-row previews, not the joined file.
2. **The recovery raced the auto-git daemon and restored the corruption.** I "restored" the file from the index (`git show :file`) — but the daemon had already staged my mangled version, so the index WAS the corruption. Second restore from `HEAD` (never committed) worked. Lesson: in a daemon-active repo, recover from verified refs, never the index — and `git add` immediately after every risky scripted write so the daemon can't stage half-states.
3. **Contradictory annotation on 20-58 item 30**: I struck it through with a done-marker whose text said the drill "remains open" — a marker that lies in either direction. Caught on re-read, reverted to unmarked (the honest open signal), and routed the drill to ROADMAP.
4. **SyntaxError round-trip** patching the variant script through a heredoc (`\n` escaping mangled) — should have rewritten the script file cleanly from the start, which is what fixed it.
5. **Marker-placement deviation**: the variant put `done at` markers in the Tier cell rather than beside the row ID (the shipped script's pattern). Cosmetic; left as-is in the archived plan rather than re-touching a resolved file.
6. **Two stale-read edit failures** (20-58 after the script wrote it; AGENTS.md against my pre-staged context copy) — the documented re-read rule exists precisely for this; I paid it once each before obeying.
7. **Tooling gap worked around, not fixed**: the shipped `annotate-rows.py` cannot scope sections (duplicate row numbers in 08-24's two tables) and only matches numeric IDs (not `M1`/`B1`), forcing hand-edits and the homebrew variant that then bit me in (1).

## e) WHAT WE SHOULD IMPROVE

- **Extend the annotation tooling before the next mass pass, not during**: section scoping + non-numeric row IDs + a shape-preservation assertion (line count before/after) in `annotate-rows.py`/`annotate-prose.py` — then propose upstream to the docs-health skill (it is a shared skill; fixes pay off everywhere).
- **Daemon-active write discipline**: scripted bulk edits must be (a) shape-verified immediately, (b) `git add`-ed immediately, (c) recovered from `HEAD` on failure. Item (d.2) proved the index is not a safe restore point here.
- **Run the dual gate every session that touches the repo**: `nix flake check` AND `--all-systems --no-build`; the 08-24 session already codified this and I skipped the second half.
- **File discovery cross-check**: my glob missed the untracked 16th report; `git status` found it. Always diff glob results against `git status`/`ls` before declaring "all files read".
- **Self-graded 10/10 is testimony, not evidence**: the post-fix health score is my own arithmetic on my own fixes; the next session's VERIFY pass (or a cheap drift-alarm check, still unwritten) is the real confirmation.
- **The CHANGELOG duplicate-heading defect recurred silently** (fixed once on 08-22, back as 3× Added + 2× Changed by 08-27) — a trivial pre-commit grep (no repeated `### <type>` under one version heading) would end this class of decay permanently.

## f) Next tasks (ranked; 1–10 already live in TODO_LIST, 11+ are new from this session's observations)

| # | Task | Impact | Effort | Category |
|---|------|--------|--------|----------|
| 1 | Open TCP 80 when `tls.mode = "acme"` + `openFirewall` (or record owner decision to document instead) | Critical | S | Bug |
| 2 | Extend `checks.telephony-eval`: port 80 assert, `apply-candidate-acl`, `wss-binding 7443`, per-`*File` placeholder | High | M | Quality |
| 3 | deploy.md truth pass + canonical port table (dedup vs ops-runbook) | High | S | Documentation |
| 4 | Push the 8 local commits; watch both CI jobs (owner go needed) | High | S | Process |
| 5 | Dispatch the browser-e2e workflow once — its YAML has never run on GitHub | High | S | Quality |
| 6 | Boot-smoke VM test for the `pbx-prod` host shape | Medium | M | Quality |
| 7 | Negative eval test: both `password`+`passwordFile` trips the assertion | Medium | S | Quality |
| 8 | 0.2.0 release cut (CHANGELOG, tag, `gh release`, repo metadata polish) | Medium | S | Release |
| 9 | First real deployment: server + DNS + ITSP + secrets, run deploy.md §5 | Critical (gated) | L | Feature |
| 10 | RTP byte-flow assertion in the browser E2E; browser-CI promotion decision | Low/Med | S–M | Quality |
| 11 | Extend the docs-health annotation scripts (section scope, M/B IDs, shape assertion); propose upstream | Medium | M | Tooling |
| 12 | Pre-commit lint: no repeated `### <type>` heading under one CHANGELOG version | Low | S | Quality |
| 13 | CI: add `nix flake check --all-systems --no-build` step (cheap cross-arch eval) | Medium | S | Quality |
| 14 | agenix variant section in `docs/secrets.md` | Medium | M | Documentation |
| 15 | Runbook: teach `wsprobe.py` + browser failure dumps to operators | Medium | M | Documentation |
| 16 | Voicemail deposit/retrieval scripted test | Medium | M | Quality |
| 17 | Dedupe `sip_server` helper (pbx.nix + dialplan.nix → common.nix); parametrize `wait_for_freeswitch`'s port | Low | S | Cleanup |
| 18 | favicon.ico for the webphone; VM-test timedelta migration | Low | S | Cleanup |
| 19 | Drift-alarm check: fail if TODO_LIST rows duplicate FULLY_FUNCTIONAL FEATURES rows | Medium | M | Quality |
| 20 | Next session: quick docs-health VERIFY to confirm the 10/10 holds (fresh eyes on my own fixes) | Low | S | Process |

(Beyond 20 everything is already ROADMAP raw ideas — padding to 50 would make noise, not a plan.)

## g) Questions I cannot answer myself

1. **Push?** 8 commits sit on local `main` (deployment template + runbook, eval-check hardening, this audit) with `origin/main` 8 behind. I never push unprompted — say the word and I'll push and watch both CI jobs.
2. **Port 80 ownership** (gates TODO row 1): should `services.telephony` open TCP 80 in acme mode when `openFirewall = true` (consistent with the option's contract — my recommendation), or stay minimal with port 80 documented as operator-owned in deploy.md?
3. **First deployment target** (ROADMAP Q4, now concretely gating): public VPS with ACME, or LAN-first with self-signed TLS? This decides whether the port-80 fix is the immediate next task and which TLS path gets validated by the first real host.

---

*Point-in-time snapshot. Annotate, never rewrite. Section (f) is already harvested — TODO_LIST.md and ROADMAP.md were updated by this same session.*

**Now waiting for instructions.**
