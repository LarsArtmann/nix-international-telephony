# Status: webphone relock 3928dbd1 — session report

- **Snapshot:** 2026-10-05 07:20 CEST
- **Scope:** this session only — the webphone relock ritual (`52f4d212` → `3928dbd1`), the browser E2E flake fight, two daemon-race recoveries, and the runbook lesson. No repo-wide audit was run; §f items noticed in passing are labeled as such.
- **Tree state at snapshot:** clean, `main` ahead of origin by 2 (0048d35 relock + e860627 runbook lesson), unpushed. Full `nix flake check`: **all checks passed**.

## a) FULLY DONE

- Relock ritual executed end to end per docs/ops-runbook.md ladder, all six gates green:
  - Gate 1 relock: webphone `52f4d212b` → `3928dbd1f` (20 commits; the relock chased one commit beyond the surveyed tip — upstream main moved mid-ritual).
  - Gate 2 binary proof: `nix build -L .#webphone` → webphone-2.8.0, in-build go checks pass, no vendorHash issue (delta had no go.mod movement).
  - Gate 3 fast gates: `nix fmt` clean (0 changed), `nix flake check --no-build` green.
  - Gate 4 VM suites: telephony-webphone, telephony-fax, telephony-fax-feed — all EXIT=0 (after correcting my own invocation: real check names, pipefail).
  - Gate 5 browser E2E: green with full marker trail (E2E-OK, THEME-CHECK-DONE, CONTACTS-ROUNDTRIP-OK) after flake attribution (see d/e).
  - Gate 6 full gate: `nix flake check` — all checks passed (EXIT=0).
- Pre-flight done properly: lock-doctor run, origin/main ancestry proven for the surveyed tip, delta shape surveyed BEFORE touching the lock (no .templ changes, no go.mod changes, healthz delta additive-only for our unwired-passkey shape, session response wire-identical via omitempty).
- Attribution discipline held: browser E2E red twice → proven red at the pre-relock base `52f4d212` under the same host load → relock exonerated → green on retry when load fell (91 → 46).
- Hand-authored commits landed (pre-commit hooks green both times):
  - `0048d35` relock: webphone 52f4d212 -> 3928dbd1 (flake.lock + CHANGELOG in ONE commit, old→new revs, why, ladder record, nixpkgs-untouched note).
  - `e860627` docs(runbook): browser E2E flake signature + base-attribution mechanics.
- lock-guard green in both forms (script + checks.x86_64-linux.lock-guard), markers_check clean (72 files, 0 findings).
- Upstream CI verdict for the locked rev `3928dbd1`: **success** (checked at snapshot time).
- Two daemon races recovered without loss (soft-reset + re-author), per the documented remedy.
- Runbook gained the durable lesson (flake signature + base-attribution mechanics), committed, prettier-clean.

## b) PARTIALLY DONE

- CI verdict watch for the two new commits → open (no runs exist yet: the commits are unpushed; the three visible runs are the documented infra-cancel class on older commits). The airtight verdict command from AGENTS.md must run after push.
- Section (f) harvest into TODO_LIST.md/ROADMAP.md → open (waiting for instructions, per this session's directive).
- Sibling webphone checkout carries an uncommitted docs file (other session's lane) → left untouched deliberately; flagging for the owner, → open on their side.
- lock-doctor's "CI verdict for HEAD" line refers to 9a21893 (now superseded by the two local commits) → informational, resolves at push.

## c) NOT STARTED

- Push of `0048d35` + `e860627` (owner act — never push without explicit request).
- Everything in §f below except items completed in-session.
- Any passkey product decision (the stack still never wires `auth.passkey.*`; upstream's passkey train keeps growing while our deployments keep the two-check healthz surface).

## d) TOTALLY FUCKED UP

Nothing shipped broken — the tree is green end to end. But full honesty about what went wrong in-session:

- I shipped a pipeline-masking bug mid-session: `nix build ... | tail -5 && echo GREEN` bound the `&&` to `tail`, so two NONEXISTENT check names printed "GREEN" after failing. I caught it, re-verified with `set -o pipefail` and true exit codes, but this is exactly the pipeline-masking failure class my own lessons file warns about. It should never have been written that way.
- I guessed a check name instead of listing checks first (`telephony-webphone-fax` vs the real `telephony-fax`), and the runbook's gate-4 shorthand (`-fax`, `-fax-feed`) invited exactly that trip. Cost: two failed invocations and a masked-exit scare.
- I fumbled the flake.lock rev extraction twice (python TypeError, then a gojq type error — `.root` is the string node-id `"root"`, not an object) before getting it right, when lock-doctor had already printed the answer.
- The daemon beat me twice (once mid-diagnosis, once splitting flake.lock and CHANGELOG.md into two commits). Recovery worked both times, but the race is structural: nothing prevents it, only manual soft-reset discipline does.
- Repo-level rot observed, not caused by this session: nixpkgs moved `b4fd65b` → `c59305bab` (2026-10-02/03) through the still-unsolved unidentified local sweep, unattributed — lock-guard only watches webphone. The browser E2E then met the moved chromium substrate for the first time today (last run 2026-10-01) and flaked. Four days of drift, zero signals: the suite lives outside `checks`, so nothing gates or schedules it.

## e) WHAT WE SHOULD IMPROVE

- Exit-code hygiene: `set -o pipefail` as the first line of EVERY multi-command nix loop, no exceptions — maskings are silent liars.
- List before invoke: `nix flake show` (or check the runbook row) before running any check attr by guessed name.
- Shrink the relock→commit window structurally: pre-draft the CHANGELOG entry BEFORE gate 1 so the final sequence is edit→add→commit in seconds. Better: a `scripts/relock-commit` helper that chains lock-update + CHANGELOG-edit + commit atomically; best: PMA-side exclusion of flake.lock/CHANGELOG.md from heuristic commits (owner decision — see §g Q3).
- Attribution mechanics: `git show <base>:flake.lock > flake.lock` beats `git restore` (restore is a no-op if the daemon already committed the new lock — it silently "succeeded" at nothing today). The /tmp snapshot-before-restore dance belongs in one helper script.
- Browser E2E must stop rotting silently: either a scheduled CI lane or a standing weekly ritual row; today proved nixpkgs/chromium drift reaches it within days and nothing notices.
- Theme FOUC check hardening: it stalled at two different points on identical code under load ~91 — add a load precondition (defer when load > threshold), a wider settle budget, one built-in retry, and dump `__wpTheme` counters + chromedriver-theme.log into the stall DIAG block (both were missing from diagnostics).
- Relock pre-flight should re-fetch origin and recheck ancestry immediately before `nix flake lock` — upstream main moved mid-ritual today (19 → 20 commits between survey and lock).
- AGENTS.md one-liner pointing at the new runbook flake-signature section (pointer only — the runbook owns the detail).

## f) NEXT — up to 50 things to get done (impact-sorted, this session's observations; → open unless marked)

**Tier 1 — do now (this week)**
1. Push `0048d35` + `e860627` → open (owner)
2. Run the airtight CI verdict check after push; cancelled = infra class, 3-rerun cap → open
3. HARVEST this §f into TODO_LIST.md/ROADMAP.md (docs-health HARVEST) after instructions → open
4. Fix runbook gate-4 row to full check names (`telephony-fax`, `telephony-fax-feed`) — I tripped on the shorthand today → open (trivial)
5. Replace deprecated `nix flake lock --update-input webphone` with `nix flake update webphone` in runbook/AGENTS/lessons → open (trivial)
6. Add stall-DIAG capture of `__wpTheme` counters to the browser E2E diagnostics block → open
7. Add chromedriver-theme.log to the stall DIAG block (only -1000/-1001 are dumped) → open
8. PMA: exclude flake.lock + CHANGELOG.md from heuristic auto-commits (two races today; owner config) → open (owner)
9. Pre-draft CHANGELOG text before gate 1 in the relock ritual (runbook one-liner) → open (trivial)
10. Re-fetch + re-verify ancestry immediately before `nix flake lock` (runbook pre-flight amendment) → open (trivial)

**Tier 2 — hardening (this month)**
11. Solve the unidentified local `nix flake update` sweeps (documented unknown since 2026-10-03; nixpkgs moved again 10-02→03) → open (owner knowledge needed)
12. Decide lock-guard scope: webphone-only by design, or extend to nixpkgs/home-manager? → open (owner)
13. Browser E2E: scheduled CI lane OR standing weekly ritual row (it rots silently outside checks) → open (owner policy)
14. Theme check robustness: load precondition + wider settle budget + one retry → open
15. `scripts/relock-attribution` helper: snapshot base/new locks + safe restore in one command → open
16. AGENTS.md pointer line to the runbook flake-signature section → open (trivial)
17. Explain the two divergent flake-parts nodes in flake.lock (`flake-parts_2` 3 commits behind the other) — potential split brain → open
18. nixpkgs 1745 behind nixos-unstable (lock-doctor today): plan a pinned bump lane with its own ritual → open
19. home-manager input 152 behind → open
20. Re-verify `scripts/heal-pre-commit-hook.sh` guard after next pull (standing ritual) → open
21. Watch daemon-race frequency (2 today + 7s precedent); if rising, escalate to PMA issue → open
22. `docs/DOMAIN_LANGUAGE.md`: add "base-attribution / attribution run" as ritual vocabulary → open

**Tier 3 — documented backlog items re-confirmed open during this session (from AGENTS.md, not re-researched)**
23. Owner toggle "Allow GitHub Actions to create and approve pull requests" for the flake-update bot (Sep/Oct runs died on it) → open (owner)
24. Delete stale `chore/flake-update-2026-09` branch on origin → open (owner)
25. a0c78ca pattern-flagged DID literal in PUSHED history — history surgery decision → open (owner)
26. CDR mid-ring ORIGINATOR_CANCEL question — live-host reproduction (documented TODO track) → open
27. BuildFlow#25 (max-time config keys) still open upstream → open
28. BuildFlow#26 (FOD-hash advisory) still open upstream → open
29. BuildFlow#27 (mainProgram data carve-out) still open upstream → open
30. BuildFlow#28 (findings-gate ignore mechanism for port-collision noise) still open upstream → open
31. pma#341 (dead skip_hooks config) still open → open
32. git-hooks.nix#754 (non-convergent hook healing) still open upstream → open
33. nix-ssh-config#5 (unmerged flake-lock update branch) still open → open
34. vulnix ~68-advisory build-closure noise class — keep documented-ignored or push for upstream ignore mechanism → open (low)

**Tier 4 — product/roadmap fuel (ROADMAP, not TODO_LIST)**
35. Passkey login for pbx-prod: upstream's passkey train is mature (250+ commits since v2.8.0) while our stack never wires `auth.passkey.*` — product decision → open (owner)
36. Cut a release: CHANGELOG [Unreleased] carries several dated entries; tag vX.Y.Z after CI green → open (owner)
37. CDR visibility: live-host verification of cancelled-leg Master.csv rows (documented next step from the 2026-09-30/10-03 probes) → open
38. Consider a fast browser E2E variant (theme-check-only suite) for relock rituals — full suite is ~7 min and mostly redundant when only JS moved → open
39. lock-doctor: also print upstream CI verdict for the TARGET rev (it only checks this repo's HEAD today) → open
40. Runbook: document that the relock may chase a NEWER tip than surveyed (main moves mid-ritual; today 19→20) → open
41. Consider `nix flake update --recursive`-style lane documentation for the monthly bot PR review flow → open (low)
42. Sibling webphone checkout: owner should commit/discard the dirty docs file there (other lane) → open (owner)
43. Upstream webphone: tags still trail main (v2.8.0 + 253 commits, version literal unchanged) — keep citing revs; no action, standing rule → acknowledged
44. Measure whether two attribution browser-E2E runs (base + new) should share the VM store path to halve attribution cost → open (low)
45. Add `set -o pipefail` guidance to docs/lessons/vm-testing.md command examples → open (trivial)
46. Pre-commit: changelog-headings hook proved itself twice today — no action → acknowledged (preserve)
47. scrub-check canary after next hook heal (standing ritual) → open
48. Re-run lock-doctor after the bot's next monthly PR to confirm the webphone exclusion still holds → open
49. Evaluate moving gate-2 (`nix build .#webphone`) earlier than gate-1 in the docs — binary proof is possible pre-relock via the input rev; would catch vendorHash rot before touching the lock → open (low)
50. After HARVEST: annotate this snapshot's §f rows with routed verdicts (`→ routed to TODO_LIST` etc.) per the marker convention → open (post-harvest)

## g) Questions I cannot figure out myself

1. **The unidentified local `nix flake update` sweeps:** documented unknown since 2026-10-03 (three sweeps that day, no scheduler/timer matched, crush-daily and PMA ruled out), and nixpkgs moved again `b4fd65b` → `c59305bab` on 10-02/03 the same way. Do YOU run these by hand (another terminal/machine), or is there a lane neither of us has found? Related: should lock-guard stay webphone-only, or is unattributed nixpkgs movement acceptable by design?
2. **Browser E2E policy:** it lives in `legacyPackages`, outside `checks` and CI — today showed nixpkgs/chromium drift rots it silently within days (last green 2026-10-01, first run since was today, red-twice-then-green). Scheduled CI lane (cost: ~7 min VM per run, flaky under host load) or keep it ritual-only with a weekly calendar row? This is a cost/policy call only you can make.
3. **PMA daemon exclusion:** two more heuristic-commit races today (it committed the relock mid-diagnosis, then split flake.lock from CHANGELOG across two commits). Are you willing to exclude `flake.lock` (and possibly `CHANGELOG.md`) from PMA's heuristic auto-commits in projects-management-automation — or should the ritual keep relying on soft-reset recovery?
