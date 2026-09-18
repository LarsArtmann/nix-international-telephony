# Status report 2026-09-18 08:27 — Webphone UI extracted to a dedicated repo

Point-in-time snapshot of the 2026-09-17 → 2026-09-18 session that moved the
webphone UI out of this stack into its own project. Annotate, never rewrite;
archive once every item carries a resolution marker.

## Summary

`github:LarsArtmann/webphone` now exists (public, v0.1.0 release + tag) and
owns the UI: `src/` ES modules (12 files, entry `app/main.js`), a
design-token stylesheet (dark + light), and the esbuild derivation that
bundles pinned sip.js 0.21.2 plus the app into one same-origin script. This
stack consumes it as a flake input; `nixosModules.telephony` defaults
`services.telephony.webphone.package` to it via `mkDefault`;
`packages/webphone/` is deleted. Behavior is a verbatim port plus a visual
uplift; the served DOM and bundle contract is unchanged and asserted.

## Verification evidence (all on final lock `e113394…`)

| Gate | Result | Proves |
| --- | --- | --- |
| webphone repo `nix flake check` | green | package builds (x86_64 + aarch64 eval), treefmt, statix, deadnix |
| 13 app.js + 8 page contract strings | all present in built output | served bundle/page satisfy `tests/webphone.nix` asserts (verified manually AND by the VM suite) |
| `checks.x86_64-linux.telephony-webphone` | green | served contract over real TLS/nginx/sofia |
| `legacyPackages.telephony-browser` | green (`E2E-OK`) | two chromiums register + call through the extracted UI: DTLS-SRTP media, DTMF, blind transfer, reconnect recovery |
| `nix flake check` (full, this repo) | **all checks passed** (exit 0, pipefail-guarded) | every VM suite incl. prod-boot, metal-boot, operator, conference, pre-commit, docs-drift |
| scrub-check | OK, 23 patterns clean | no personal data in the changed trees |

## a) FULLY DONE

| Item | Evidence |
| --- | --- |
| New repo published: flake, derivation, `update.sh`, LICENSE, dprint.json, `.buildflow.yml` | commits `c36b51d`…`1cfe0e3` + BuildFlow's `2821dfe` |
| ES-module restructure, acyclic graph (state.js/auth.js break the calls/ice/connection cycle) | `src/app/*`, bundle contract strings intact |
| UI uplift: tokens, dark+light, LED pill, tactile keys, reduced-motion, focus-visible | `src/style.css`; DOM contract preserved |
| Regression fixes post-review: logout nulls UA handles; persisted lang preselects switcher | `e113394`, telephony lock updated to it |
| Docs in new repo: README, AGENTS (DOM/bundle contract), FEATURES, TODO_LIST, CHANGELOG | repo |
| Telephony wiring: input, wrapper default, explicit test threading, treefmt globs, `.buildflow.yml` exclude, docs (README/AGENTS/DOMAIN_LANGUAGE/FEATURES/lessons) | this repo, `db6082b` tip |
| CHANGELOG entry for the extraction (merged into existing `### Changed`) | `db6082b` |
| GitHub release v0.1.0 + tag | releases/tag/v0.1.0 |
| Both hosts still evaluate (pbx VM app, pbx-prod toplevel) | `nix eval` drv paths |

## b) PARTIALLY DONE

| Item | State | Gap |
| --- | --- | --- |
| Release hygiene | v0.1.0 tagged/released | tag predates the two regression fixes (`e113394`); no v0.1.1 cut, release notes don't mark v0.1.0 affected → open — out-of-repo (webphone repo) |
| Visual QA | design implemented, automated DOM checks pass | nobody has SEEN the rendered page; no screenshots, no dark/light/manual-language eyeball pass → open — out-of-repo (webphone repo; render-and-look pass) |
| BuildFlow on new repo | first run landed (`2821dfe`: managed .gitignore, dprint md reformat) and auto-pushed | run output not reviewed; `.buildflow.yml` skip/exclude semantics unverified on this repo → open — out-of-repo (webphone repo) |
| aarch64 posture | derivation cross-evals; same stance as pre-extraction | no TCG suite run for the input (unchanged limitation, but worth recording in the new repo) → open — out-of-repo (webphone repo) |
| Telephony README update.sh instruction | now says `cd ../webphone && ./package/update.sh` | assumes sibling checkout; breaks for fresh clones → done — clone-agnostic phrasing landed 2026-09-18 (any webphone checkout; sibling is only a convention) |
| TODO_LIST (this repo) | extraction row-material updated where touched | stale fragment "webphone app.js formatting-only review" (P31) not annotated — superseded by the move → done — fragment removed in the 2026-09-18 TODO_LIST rebuild |

## c) NOT STARTED

CI workflow in the webphone repo (its gate is only covered transitively by
this stack's CI); `.badge[hidden]` CSS bug fix (see d); DOMAIN_LANGUAGE.md /
CONTRIBUTING.md / SECURITY.md in the new repo; remote-ref proof
(`nix build github:LarsArtmann/webphone` from a clean context); flake-update
automation for the new input; a11y/tooling audits; everything in the new
repo's TODO_LIST (theme toggle, sip.js 0.22, shortcuts, media keys).
→ routed — the webphone repo owns all of these (UI extracted 2026-09-17/18); the remote-ref proof → open — owner/CI (needs a networked shell)

## d) TOTALLY FUCKED UP

| What | Damage | Lesson |
| --- | --- | --- |
| **MWI badge CSS bug introduced**: `.badge { display: inline-block; }` defeats the `hidden` attribute (author display overrides UA `display:none`) — the badge renders as an empty pill whenever no voicemail panel state exists; suites never see it (phone API off in tests) | live on `main` (pushed), not on users' radar yet; one-line fix queued | author-origin `display` beats `hidden`; UI changes need at least one rendered screenshot, not only DOM asserts |
| **Release before self-review**: v0.1.0 tagged/released, THEN the review pass found two regressions (logout left a stopped agent dialable; lang preselect lost) | the published release is the buggy rev | cut the release AFTER the second-pass review, not before |
| **Missed `tests/prod-boot.nix`** in the "who imports the module directly" sweep (its NODE imports `../modules/telephony`) | one wasted full-gate cycle (~25 min) until `nix flake check` caught the undefined option | when removing an option default, sweep node-level `imports = [...]`, not just file-level |
| **Pipeline-masked exit codes, twice** (`nix build … \| tail; echo $?` is tail's status) — the exact trap recorded in AGENTS.md | nearly declared the browser E2E green on an unknown result; burned round trips | `set -o pipefail` or no pipe, every time |
| **Daemon-interleaved history in the new repo**: my per-task commits swept up daemon-staged files, so messages didn't match contents | fixed by trashing `.git` and re-committing (legal but heavy); risk was zero only because nothing was pushed yet | commit with explicit pathspecs (`git commit -- <paths>`), immediately after staging |

## e) WHAT WE SHOULD IMPROVE

1. **Render-and-look pass is mandatory for UI work** — the badge bug class
   (CSS vs `hidden`, visual regressions) is invisible to DOM asserts.
2. **Sweep node-level imports when touching module defaults** — the
   module-under-test is imported at NODE granularity in fixtures.
3. **Exit-code discipline**: never read `$?` after a piped command; use
   `set -o pipefail` (this session violated a recorded lesson twice).
4. **Pathspec commits** when a commit daemon shares the index.
5. **Review order**: second-pass behavior diff BEFORE tagging/releases.
6. **Contract tests co-located**: the upstream string-asserts should also
   run in the webphone repo so contract drift fails at the source.
7. **Full gate before "done"**: two of three failures (prod-boot,
   changelog headings) were only caught by the full `nix flake check` —
   run it once before reporting success, not after.

## f) NEXT TASKS (prioritized)

| # | Task | Priority | Effort |
| --- | --- | --- | --- |
| 1 | Fix `.badge[hidden] { display: none }` in webphone `src/style.css`; rebuild, push, bump telephony lock | 🔴 High | S | → open — out-of-repo (webphone repo); this repo's lock bump rides the fix |
| 2 | Cut webphone v0.1.1 with the logout/lang fixes; mark v0.1.0 affected in release notes (or re-tag per owner decision) | 🔴 High | S | → open — out-of-repo (webphone repo; owner tag-policy call, see g.1) |
| 3 | Visual QA: `nix run .#vm`, screenshot dark/light × en/de, both views; fix what looks off | 🔴 High | M | → open — out-of-repo (webphone repo) |
| 4 | Verify `nix build github:LarsArtmann/webphone` from a clean context (remote ref proof) | 🔴 High | S | → open — owner/CI (networked shell) |
| 5 | GitHub Actions CI in webphone repo (nix flake check, x86_64) | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 6 | Co-locate the contract asserts: a check in the webphone repo grepping the built bundle/page for the contract strings | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 7 | Review BuildFlow's first-run output on the new repo (log, `.buildflow.yml` semantics) | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 8 | Fix telephony README update.sh instruction to be clone-agnostic | 🟠 Med | S | → done — 2026-09-18 (clone-agnostic phrasing) |
| 9 | Cut telephony v0.3.0 (Unreleased is accumulating: extraction + conference-`#` + scrub gate) | 🟠 Med | S | → open — TODO_LIST blocked row (v0.3.0) |
| 10 | Annotate the stale "webphone app.js formatting-only review" fragment in TODO_LIST | 🟠 Med | S | → done — removed in the 2026-09-18 TODO_LIST rebuild |
| 11 | DOMAIN_LANGUAGE.md for the webphone repo | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 12 | CONTRIBUTING.md + SECURITY.md (nix-ssh-config parity) | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 13 | pre-commit hooks in webphone repo (at least gitleaks + treefmt) | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 14 | Flake-update automation for the `webphone` input (renovate/dependabot) | 🟠 Med | M | → open — ROADMAP theme 5 (repo plumbing) |
| 15 | `update.sh`: assert contract strings after rebuild | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 16 | aarch64 posture documented in webphone repo (eval-only; TCG belongs to the stack) | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 17 | Firefox + Safari sanity (color-mix, :focus-visible, hidden semantics) | 🟠 Med | M | → open — out-of-repo (webphone repo) |
| 18 | axe/Lighthouse a11y audit on the served page | 🟠 Med | M | → open — out-of-repo (webphone repo) |
| 19 | MWI badge: aria-live announcement of unread count | 🟠 Med | S | → open — out-of-repo (webphone repo) |
| 20 | Toasts: visible dismiss affordance (currently click-only) | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 21 | Focus/aria-live handling when the incoming-call banner appears | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 22 | Ringtone/ringback volume + mute, persisted | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 23 | Unified settings panel (lang, theme override, sound) with a `data-theme` hook | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 24 | Manual theme toggle (top TODO_LIST row in webphone repo) | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 25 | Keyboard shortcuts: answer/hangup/mute/hold + visible hints | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 26 | Headset media keys via MediaSession | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 27 | sip.js 0.22 evaluation via `update.sh` (contract strings must survive) | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 28 | PWA evaluation (offline shell; strict-CSP compatible SW) | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 29 | Video-call support evaluation (UI surface decision first) | 🟡 Low | L | → open — out-of-repo (webphone repo) |
| 30 | Opus/DTX SDP preference tuning | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 31 | `window.__pcs` cleanup on session teardown (unbounded Map in long sessions) | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 32 | Wrap SIP delegate callbacks in a guard so one throw can't kill the UI | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 33 | Screenshots in webphone README (after visual QA) | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 34 | Add the webphone repo to telephony README's feature table as a link-out | 🟡 Low | S | → done — README options tour + layout section link the repo (verified 2026-09-18) |
| 35 | docs/deploy.md: confirm no stale webphone-asset instructions remain | 🟡 Low | S | → done — grep-verified 2026-09-18: none remain |
| 36 | Cross-link telephony DOMAIN_LANGUAGE ↔ webphone docs | 🟡 Low | S | → **Won't implement — one home per fact; the flake-input pointer in README/layout already routes readers.** |
| 37 | Make `common.nix`'s `webphonePackage` throw a helpful message instead of an opaque option error when omitted | 🟡 Low | S | → open — ROADMAP theme 5 (test plumbing) |
| 38 | Consider `passthru.tests` smoke test in the webphone derivation (serve via nginx, fetch page) | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 39 | Explicit aarch64 eval check in webphone repo (silence the `--all-systems` warning honestly) | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 40 | Release helper script for the webphone repo (version ↔ CHANGELOG ↔ tag ↔ release) | 🟡 Low | M | → open — out-of-repo (webphone repo) |
| 41 | lychee pass over the new README's links (via buildflow run) | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 42 | jscpd/duplication pass over `src/app` (buildflow now scans it; review findings) | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 43 | i18n: second eyes on the de strings port (verbatim copy, no review pass yet) | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 44 | Rename `#call-btn`/ids audit: document which ids are contract vs internal | 🟡 Low | S | → open — out-of-repo (webphone repo) |
| 45 | Contact import/export (vCard) — WORTH_CONSIDERING, needs a decision | ⚪ Consider | M | → open — out-of-repo (webphone repo) |
| 46 | Multi-device registration indicator (needs operator API support) | ⚪ Consider | L | → open — out-of-repo (webphone repo) |
| 47 | History: filter/search when list grows | ⚪ Consider | M | → open — out-of-repo (webphone repo) |
| 48 | Consider publishing the webphone package to a flake registry / nixpkgs PR | ⚪ Consider | M | → open — out-of-repo (webphone repo) |
| 49 | Extraction meta-lesson (node-level sweep discipline) into docs/lessons/ | ⚪ Consider | S | → done — node-level-sweep section added to docs/lessons/vm-testing.md (2026-09-18) |
| 50 | Demo video of the new UI (website-launch pattern) once visual QA lands | ⚪ Consider | M | → open — ROADMAP theme 3 |

## g) QUESTIONS (cannot answer myself)

1. **Tag policy for the flawed v0.1.0**: cut `v0.1.1` with the regression
   fixes and a note in v0.1.0's release (semver-clean), or re-point
   `v0.1.0` at `e113394` (force-tag; nothing consumes the tag yet)?
   → open — out-of-repo (owner/webphone repo)
2. **MWI badge fix cadence**: push the one-line CSS fix + telephony lock
   bump immediately, or batch it with the theme-toggle/settings work to
   amortize a re-verification cycle?
   → open — out-of-repo (webphone repo; the lock bump rides the fix)
3. **Release rhythm for this stack**: cut `v0.3.0` now (extraction +
   conference-`#` + scrub-gate entries are pending in Unreleased), or let
   Unreleased keep accumulating per your own release cadence?
   → open — TODO_LIST blocked row (v0.3.0)

— End of report. Awaiting instructions.
