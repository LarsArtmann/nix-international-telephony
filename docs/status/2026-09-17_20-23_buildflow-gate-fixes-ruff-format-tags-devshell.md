# Status Report — BuildFlow gate fixes: ruff, treefmt, devShell pinning, stale release tags

**Snapshot:** 2026-09-17 20:23 · main `190a6b8` (clean, synced with origin) ·
scope: this session's run only ("fix" on a failing BuildFlow/full-check log).

**Trigger.** The pasted log showed: `ruff-check-fix` failing (8 findings, 4
auto-fixed, 4 manual), `checks.format` (treefmt/prettier) failing on
`operator.js`, `nix-build` killed at the 5-minute budget, repeated
"binary X not in project devShell" warnings, and `git sync` rejecting
`v0.1.0`/`v0.2.0` ("would clobber existing tag").

---

## a) FULLY DONE

1. **Ruff `PLW1510` ×3** — explicit `check=False` on the three
   `subprocess.run` calls in `packages/telephony-operator/api.py`
   (`fs_cli_cmd`, health `units`, health `cert`); returncode is handled
   manually at every site, and the `# nosec B603` comments stayed on the
   issue line (bandit green).
2. **Ruff `DTZ005`** — `dialplan_sim.py` `_when_from_args` now uses
   `time.localtime()` instead of naive `datetime.datetime.now()`.
   Semantics preserved exactly (FreeSWITCH evaluates `${year}`/`${hour}`
   etc. against server-local time; the `--when` help says so) with no
   suppression comment.
3. **ruff-check-fix step green** — EXIT 0, the original pipeline failure
   is gone. mypy, bandit, prettier, todo-check steps all EXIT 0; the full
   fast-mode `buildflow` pipeline ends EXIT 0 with no findings-gate trip.
4. **Pre-existing ruff-format drift** in `api.py` (`read_cdr_rows` list
   comprehension) found via the verify loop and repaired with
   `buildflow -s ruff-format --fix` (detect → repair → verify clean).
5. **treefmt/prettier format check** — verified resolved, not re-fixed:
   the daemon had already committed BuildFlow's earlier prettier repair
   (`e07add9`); the failing `treefmt-check` in the pasted run had raced a
   stale git-tree source. `nix fmt` reports 0 changes;
   `nix build .#checks.x86_64-linux.format` EXIT 0.
6. **todo-check gate (found during verification)** — removed a leftover
   `AUDIO-DEBUG` print in `api.py`'s voicemail-audio 404 branch (new since
   the user's runs; added by a parallel session's daemon commits). It
   tripped todo-check at error severity AND dumped per-user message
   uuids/paths into the service journal. No test asserts on it (the
   operator suite prints the journal only as failure diagnostics).
7. **devShell lint-binary pinning** — `ruff`, `bandit`, `mypy`, `dprint`,
   `prettier`, `vulnix` added to `devShells.default`, pinned to the flake's
   nixpkgs. Kills the `nix run nixpkgs#X` registry fallback (moving
   revision vs pinned nixpkgs — the same version-skew class as the
   documented oxfmt/prettier war in `.buildflow.yml`). Verified inside
   `nix develop`: all six resolve to `/nix/store/...` from the flake
   input; the "not in project devShell" warnings no longer appear.
8. **AGENTS.md updated** — the "BuildFlow noise is DECIDED" paragraph now
   records the 2026-09-17 devShell pinning decision and its rationale.
9. **Release tags repaired (user-approved force-push)** — remote
   `v0.1.0`/`v0.2.0` still pointed at the pre-scrub history (identical
   trees, but their parent chains anchored the rewritten-away history —
   which contained an unredacted personal DID per the scrub gate's own
   header — and broke every `git fetch --tags`). Force-moved with
   `--force-with-lease` pinned to the exact expected remote objects:
   `v0.1.0 → 83e2f25`, `v0.2.0 → 28a98e5` (both ancestors of main).
   `git fetch --prune --tags` now EXIT 0; both GitHub releases intact.
10. **Verification battery** — operator VM suite green twice (the second
    time via forced `--rebuild` after catching a cached-green), package
    `.#telephony-operator` builds, hermetic `checks.pre-commit` builds
    (includes scrub-check tree scan), and the format check above.

## b) PARTIALLY DONE

1. **Full `nix flake check` (the CI gate) NOT run this session.** Only
   targeted derivations were proven: format, pre-commit, operator VM,
   operator package. Unproven here: `docs-drift` against the parallel
   session's FEATURES/TODO edits, and every other VM suite. Rationale at
   the time: the tree was moving (daemon + parallel session), so a full
   gate on a moving tree proves little — but that means "CI green" is
   still an assumption, not a fact.
2. **Full-mode BuildFlow not re-run** with the documented
   `--build-mode full --max-time 60m` after the fixes; only fast mode.
   The `nix-build` step the user saw killed at 5m remains unproven
   end-to-end locally (CI will exercise it).
3. **Bandit findings in the new operator files** (B404 subprocess import,
   B607 ×2 partial paths `systemctl`/`openssl`, B405/B314 `xml.etree`)
   remain detect-only warnings. The codebase's decided bandit-cleanliness
   pattern (curated inline `# nosec` / defusedxml) was not extended to
   these new files.

## c) NOT STARTED (noticed this session, deliberately untouched)

1. Parallel session's doc edits (AGENTS.md lessons, FEATURES, TODO_LIST,
   CHANGELOG, ops-runbook, README) — respected as not-mine.
2. `tests/operator.nix` keeps its own `AUDIO-DEBUG-TEST` prints (failure
   diagnostics only; defensible, but same smell class as the removed one).
3. nix-checker remainders (FOD-hash advisories, inline-hash extraction,
   sounds.nix mainProgram) — accepted remainder per AGENTS.md.
4. vulnix 66 advisories, shellcheck 12 findings (SC1083 etc. in
   scripts/), lychee 47 (archived-snapshot "no files" warnings),
   flake-meta-checker mainProgram — pre-existing accepted/known noise.
5. Browser E2E suite (`legacyPackages.telephony-browser`) not run.

## d) TOTALLY FUCKED UP!

Nothing destructive or unrecoverable — but three honest stumbles:

1. **Cached-green trap, caught late.** The first re-run of the operator
   VM check after the debug-print removal returned instantly with empty
   output (= fully cached) and I initially presented it as proof. Only a
   suspicion-driven `nix build --rebuild` gave real evidence. The lesson
   (verify the instrument actually measured) exists in global AGENTS.md;
   I repeated the mistake before applying it.
2. **Pipeline masking, self-inflicted.** `buildflow ... | tail` reported
   `EXIT=0` while the output contained a real findings-gate ERROR
   (todo-check) — exactly the `set -o pipefail` class of lesson. Caught
   by reading the text, but the command shape was wrong first.
3. **Wasted round trip on the question tool** (wrong parameter name,
   rejected call) before asking the tag question. Minor, avoidable.

Also worth owning: **my fixes are entombed in heuristic daemon commits**
("chore: auto-commit N changed file(s)") — the user never said "commit",
so the harness contract was honored, but git history tells no story about
the ruff/devShell/tag work. AGENTS.md already documents the fix
(commit per task when authorized).

## e) WHAT WE SHOULD IMPROVE!

1. **Racing checks on a moving tree.** Git-tree flake source + auto-commit
   daemon + parallel sessions let a check evaluate a stale source (the
   pasted treefmt failure). Rule of thumb: after multi-session churn,
   re-run gates on a quiesced tree before believing red OR green.
2. **Post-surgery checklist gap.** The 2026-09-03 history scrub force-pushed
   branches but left remote tags anchoring the pre-scrub history for ~2
   weeks. "After history surgery: force-move tags in the SAME session,
   then `git fetch --tags` from a scratch clone to prove it" belongs in
   the operating lessons.
3. **Debug prints reach main in minutes** via the daemon, bypassing
   pre-commit. A cheap `-DEBUG`-print ban hook (or daemon-side hooks)
   would have caught the AUDIO-DEBUG print before it tripped a gate.
4. **todo-checker finding UX.** Its message was a string fragment
   (`rows={len(rows)} sought=...`) with no marker name — the finding was
   real but the reason was invisible. BuildFlow feedback candidate.
5. **Registry-fallback tool skew is a fleet-wide pattern** — now fixed
   here; other LarsArtmann repos with `.buildflow.yml` likely show the
   same "nix run nixpkgs#X" warnings.
6. **5-minute full runs keep biting** (AGENTS.md documents 60m; the user's
   run died mid-`nix-build` again). A BuildFlow guard that refuses
   `--build-mode full` under a tiny `--max-time` would prevent the class.

## f) Next tasks (impact-sorted brainstorm — ROADMAP/TODO fuel, not commitments)

1. Run full `nix flake check` on the quiesced tree; fix whatever docs-drift
   says about the parallel session's FEATURES/TODO edits.
2. Run `buildflow --build-mode full --max-time 60m` once, end-to-end.
3. Watch CI on GitHub (`gh run watch`) for the pushed daemon commits.
4. Curate the 5 bandit findings in operator files (inline nosec with
   rationale, matching the codebase pattern).
5. Decide defusedxml vs trusted-input documentation for
   `dialplan_sim.py` `ET.parse` (B314, Medium).
6. Absolute paths (or nosec rationale) for `systemctl`/`openssl` calls
   (B607 ×2).
7. Tidy or bless the `AUDIO-DEBUG-TEST` prints in `tests/operator.nix`.
8. CHANGELOG entry for today's lint/devShell/tag fixes (none was written).
9. HARVEST this report's (f) list into TODO_LIST/ROADMAP (docs-health).
10. Add the post-history-surgery tag checklist to `docs/lessons/operating.md`.
11. Host-side unit tests for `dialplan_sim.py` logic (currently VM-only
    coverage; the simulator is pure string/xml logic).
12. Re-run `scripts/scrub-check.sh --history --strict` after commits settle.
13. Extract FOD hashes to `hash.nix` files per nix-checker suggestion
    (sounds.nix ×2, webphone).
14. Triage the 66 vulnix advisories against the last known state (drift,
    not net-new, expected — confirm).
15. Fix the 12 shellcheck findings in `scripts/` (SC1083 brace literals
    in `ahead-check.sh`, `scrub-check.sh` etc.).
16. Consider adding `ruff` to treefmt so Python formatting has ONE owner
    (today: buildflow ruff-format + flake treefmt are separate sources).
17. Add a pre-commit hook banning `*-DEBUG` prints under `packages/`.
18. Verify dprint actually has a purpose here (config? files?) or skip
    the step — it currently runs without visible targets.
19. Fleet sweep: pin lint binaries in devShells of other BuildFlow-covered
    repos (same one-block fix as today's).
20. File BuildFlow feedback: todo-checker message should name the matched
    marker; findings-gate output should print exit-code-safe summaries.
21. Add a BuildFlow guard/warning for `--build-mode full` with
    `--max-time` too small to survive nix-build.
22. Schedule a `telephony-browser` E2E run after the operator UI churn
    settles (it is deliberately outside `checks`).
23. Consider `fetch.pruneTags` + tag `--force-with-lease` defaults in
    local git config so future tag surgery self-heals clones.
24. Confirm the GitHub release pages now render the new tag targets
    (`gh release view v0.1.0 --json targetCommittish`).
25. Re-check `git log --all` reachability: confirm nothing local still
    references pre-scrub objects after tag moves.
26. Add an `operators` section note to README dev docs: lint binaries now
    ship in `nix develop` (no `nix run nixpkgs#` fallback needed).
27. Optional strict pass: `buildflow --fail-on warning` occasionally to
    keep detect-only noise totals (72 bandit lines etc.) trending down.
28. Review whether `_when_from_args` should accept an explicit
    `--tz`/UTC-anchored mode now that it is tz-rule-clean (simulating
    non-UTC deployments).

## g) Questions I can NOT figure out myself

1. **Was the `AUDIO-DEBUG` print an active debugging aid for a parallel
   session/browser-E2E work?** I removed it as gate-tripping leftover; if
   someone was mid-debug on another machine, they'll want to know it's
   gone (and re-add it scoped, not on main).
2. **Harvest now or leave the snapshot standalone?** Should I run the
   docs-health HARVEST of section (f) into TODO_LIST/ROADMAP immediately,
   or do you want to prune the list first?
3. **Bandit policy for the operator package:** switch XML parsing to
   `defusedxml` (adds a runtime dependency to a deliberately
   stdlib-only service) or document the dialplan XML as trusted input
   (it is flake-generated, not user-supplied) and nosec it?

---

_Point-in-time snapshot. Annotate, never rewrite; archive once every item
carries a resolution marker. Format note: written as Markdown per explicit
user request (overrides the status-report skill's HTML default)._
