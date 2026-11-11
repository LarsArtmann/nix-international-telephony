# Status Report: The 18:47 BuildFlow Red Driven to Green (sweep #4 heal, cue policy, ruff 44 → 0, docs gates)

**Date:** 2026-11-11 00:54 CET
**Session span:** ~19:00–20:45 CET 2026-11-10 (one continuous run), report written 00:54
**Starting point:** HEAD `a772faf` (the fourth sweep, committed by the daemon 19:01; lock-guard RED), BuildFlow run of 18:47 exit 1 with ruff 44 errors, cue-vet error, three docs-gates red, nix-build mass-killed
**End state (session):** full `nix flake check` GREEN locally (~20:40, all VM suites), ruff/format/mypy/bandit/pytest green, 365 stdlib tests green, docs-gates all five green, markers/rendering green, lock-guard green. Hand-authored commits `276b3d7` (relock restore) + `9f0273b` (closeout) + sibling-repo `f0ed5f5` (cue-policy).
**State at write time (post-session, other lanes):** the tree moved forward through hand-authored relock commits (`f480048` the v2.13.0 release relock, then the release-lineage completion, terminal pin `c5074bf8`); a history rewrite unwound my amended relock commit back to the heuristic `c404978` (content intact; §d7). My gate health checks at 00:54: lock-guard PASS, markers PASS.

---

## a) FULLY DONE (verified green this session)

1. **Fourth sweep healed, attribution landed.** BuildFlow's own `nix-flake-update` repair step moved the tracked webphone input `6936be2` → `433ca171` (ungated tip past the ladder-proven voicemail relock) and the daemon landed it as `a772faf`. Lock restored to `6936be2`, CHANGELOG sweep bullet appended, hand-authored `relock:` commit passed the lock-move-guard hook; `scripts/lock_guard.py` green before and after.
2. **cue-vet: 1 error → 0 findings.** Two-part fix: the fleet schema in `~/projects/cue-policy` widened the runner allowlist to `ubuntu-latest | ubuntu-24.04-arm` (commit `f0ed5f5`, `cue vet -c .` self-check green) so `check-aarch64` keeps its native arm64 TCG boot lane; `.github/workflows/ci.yml` gained the fleet-required top-level `permissions: contents: read` (the runs-on conflict had masked it — cue reports one error at a time).
3. **BuildFlow result-cache trap discovered and documented:** single-step reruns serve cached detector verdicts across external-file edits (the cue fix stayed "red" until `--no-result-cache-for cue-vet`); recorded in the CHANGELOG Fixed entry.
4. **ruff 44 → 0** with the full fleet user config (direct `ruff check .`): 7× EXE001 via `chmod +x` on shebang'd scripts/stubs; BLE001 narrowed to `CookieError` in `oidc_session.py` and `# noqa`-annotated on the three deliberate reader/route guards in `text-agent.py`; SIM115 tempfile dances rewritten as context managers (5 sites); RUF059/RUF015/F841 dead-binding cleanups (13 sites); UP031 percent-format → f-string; RUF046 redundant `int()` dropped; ISC004 implicit concat parenthesized; TRY004 non-object request bodies now raise `TypeError` with the route handler catching it as 400; SIM102 combined; B017 narrowed to `SipError`; N999 quieted with file-level pragmas on the two VM-deployed hyphenated scripts (their names are suite contracts — renaming would churn every suite + history doc for a scripts-not-modules false positive). `ruff format --check` green; `ruff format .` applied once (1 file reflowed).
5. **All 365 stdlib tests green after the fixes** (150.8s, `python3 -m unittest discover -s tests -t .`); mypy, bandit and pytest buildflow steps green; `ruff-config-check` verified NOT-APPLICABLE (no repo-level ruff config, by design — the exit 1 is the not-applicable verdict, not a failure).
6. **docs-gates all five gates green** (`freshness`, `audit-all`, `annotate`, `routing`, `cadence`): the newest handoff's one unharvested item (push transports) genuinely harvested into a TODO_LIST row, and the historical annotate/audit backlog pinned with fleet-pattern ratchets in a new `.docs-gates.json` (`annotate_max: 48`, `audit_max: 111` — same mechanism as webphone's 203/72; BuildFlow skips the gates outright).
7. **The hereditary markers red healed a sixth time:** the 15:48 dprint sweep (`3f25884`) had truncated the 2026-10-07 snapshot's row-1 Category cell again (file count 146 → 144, the per-item f:1 verdicts 3 → 1); restored by append from the `91fa748` peak text (count recovery clears both monotonicity findings); `markers_check` and `rendering_audit` green over 109 files; `docs-drift` and doc-counts green (365 stable).
8. **nix-checker verified at the documented green shape:** 2 accepted NAT 5060 sourcePort errors + 4 accepted sounds.nix infos + 2 accepted privileged-port warnings; its bare single-step invocation fails only because it lacks the pipeline's budget. No code action needed.
9. **The nix side proven, not assumed:** `nix fmt` clean; six cheap wired gates built green (`telephony-eval`, `treefmt`, `doc-counts`, `lock-guard`, `markers-check`, `catalog-export`); then the FULL `nix flake check -L` went green locally (~20:40, every VM suite) — proving the 18:47 nix-build mass-kills were the 1m50 step deadline and 0s CPU starvation under load, not code.
10. **dprint-format re-probed and now idempotent:** no files changed on rerun, markers stayed green — the one-time normalization of the two status docs is stable, and the restored cell survives the formatter.
11. **Same-window CHANGELOG bookkeeping:** the fourth-sweep bullet in the existing sweep incident entry, plus a full `### Fixed` section naming every verdict above; landed in the same commit as the last fix; the local full-gate verdict appended after it existed.
12. **Push-transports TODO row added** (the harvest): `push.ntfy` / `push.fcm` option-surface work, routed from the handoff's item.

## b) PARTIALLY DONE

1. **The literal `buildflow` run was not re-driven to a 48/48 artifact** — every failing lane was fixed and verified individually, and the nix side has a local full-gate green, but a fresh full pipeline run (fast mode still kills mid-VM-build by budget) was deliberately not spent; CI's `nix flake check` remains the system gate.
2. **The docs-gates historical debt is ratcheted, not burned down** — `annotate_max: 48` tolerates 26 F/spacing sites (several are the deliberate `code`s plural style in living files), 11 A/evidence verdict gaps, 4 phantom-tag E/ref claims, 3 G/uniform cell strikes, 1 C/path missing-file cite; `audit_max: 111` tolerates historical unharvested items, untriaged for genuine openness.
3. **N999 is quieted, not resolved** — the two hyphenated script names stay (suite + docs contracts); pragmas silence the rule; a rename with full reference migration was scoped and judged not worth the churn this session.
4. **Everything is local-only** — this repo's session commits and the cue-policy commit are unpushed; CI has not validated the changed `ci.yml`, and the arm64 label has never run a job yet.
5. **The buildflow ruff verdict-flip mystery is unresolved** — at 19:41 `buildflow -s ruff-check-fix` passed while direct `ruff check .` showed all 44; I made the code green under the strictest observable config instead of root-causing the invocation difference (pinned 0.16.2 vs profile 0.17.3 rule selection suspected, unproven).

## c) NOT STARTED

1. Push + CI validation of this repo (workflow change included) and of cue-policy.
2. First live run of `check-aarch64` on the `ubuntu-24.04-arm` label (org arm-runner availability untested).
3. Gate-0 `nix build` proof for the discarded sweep tip `433ca171` (the 268c091 precedent recorded one "for the record"; here the restoration was recorded without it).
4. AGENTS.md memory updates for this session's discoveries (result-cache trap, repair-tool-as-sweep-source, docs-gates ratchet adoption, dprint idempotency).
5. The annotate backlog burn-down (fix-vs-exempt decisions per class).
6. A repo-level ruff config ownership decision (see §g).

## d) TOTALLY FUCKED UP (honest list)

1. **Pipe-ate-my-exit-code on the very first lock-guard run** — `| tail` then `$?` printed 0 while the gate printed FAIL; the house reflex exists verbatim for this and I still hit it once (caught immediately by reading the output, but the reflex failed).
2. **Misread the cue conflict direction at first glance** — I assumed ci.yml (`ubuntu-latest`) violated a pro-arm policy and nearly "fixed" the job backwards; reading the schema flipped it (policy mandated ubuntu-latest; the JOB was the intentional deviant).
3. **My SIM102 edit shipped a syntax error** — I replaced only through the inner `if` without reading the full nested block; the `_hold` closure sat one indentation level deeper and the file stopped parsing. Ruff caught it; I should have (view-then-edit the whole block, always).
4. **My batch-fix script died on its own stale line index** — an in-memory block rewrite shifted lines before a line-numbered edit asserted; nothing was written (assert-first saved it), and the eventual fix exposed a second unused variable the first pass had created. The rework cost two extra cycles.
5. **The daemon raced me twice** (this repo and cue-policy): staged content landed as heuristic commits seconds before my hand-authored `git commit` in both repos; both recovered by amending the unpushed HEAD per the runbook, but staging immediately after the final edit would have avoided the dance entirely.
6. **Wasted calls:** four edit-without-View rejections, one no-op multiedit (identical old/new), a JSON parse crash on buildflow findings output (trailing regression text), a wrong-directory grep.
7. **A post-session history rewrite unwound my amended relock commit** (`276b3d7` gone; the lock restore now rides the heuristic `c404978`, my closeout re-authored as `73aebd1`) — not my action and the content + gates are intact, but the hand-authored marker message on the restore is lost; whoever rewound it traded the ritual marker for history shape. Flagged for the sweep-executor file, not reverted (never revert others' work).
8. **The 18:47 run's own repair step was the fourth sweep's executor** — a repair tool mutating the lock is a sweep source I had not on the threat model; caught only because the session-start ritual diffs the lock.

## e) WHAT WE SHOULD IMPROVE

1. **Stage and hand-commit immediately in daemon territory** — the amend dance is avoidable; edit → stage → commit in one window, every time.
2. **View the whole structural block before replacing any of it** (SIM102 lesson); the edit tool's exact-match safety does not protect against partial-context rewrites.
3. **Pin lint config ownership per repo** — the 44-finding surprise came from a fleet user-level ruff config this repo does not carry; verdicts should not depend on which machine ran them.
4. **Trust direct gate runs over cached step verdicts** — `--no-result-cache-for` is now a reflex for every single-step rerun after any external-file edit.
5. **Exit codes as reflex, again** — it bit once this session despite being codified twice in the runbook.
6. **Newly adopted fleet gates deserve a budgeted adoption session** — docs-gates was red-on-arrival here; the honest fix was harvest + ratchet, and that pattern should be the documented default for the next repo that meets it.
7. **Memory updates are moment-of-discovery work** — deferring them created §c4.

## f) NEXT — up to 50 things, in priority order

1. Update AGENTS.md with this session's four lessons (BuildFlow result-cache staleness; repair-tool-as-sweep-source; docs-gates ratchet adoption pattern; dprint now idempotent on snapshots).
2. Push this repo (session commits + tonight's release-lineage relocks) and watch CI validate the changed `ci.yml`.
3. Push cue-policy (`f0ed5f5`) so the fleet allowlist widening reaches other consumers.
4. Dispatch/observe `check-aarch64` on `ubuntu-24.04-arm` — first live proof of the label (org arm-runner availability is untested).
5. Root-cause the buildflow ruff verdict-flip (step passes while direct ruff flagged 44; version-skew hypothesis) — see the config-ownership TODO row.
6. Decide repo-level ruff config ownership (own `ruff.toml` replicating the fleet selection vs user-config dependence) — TODO row added.
7. Annotate backlog burn-down: fix-vs-exempt per class (F/spacing style sites, A/evidence verdict gaps, the four phantom-tag E/ref sites, G/uniform cell strikes, C/path missing-file cite) and shrink `annotate_max` — TODO row added.
8. Gate-0 `nix build` proof for the discarded sweep tip `433ca171` (for-the-record, 268c091 precedent), or explicitly close the question.
9. Append the post-session history-rewrite observation (restore commit riding a marker-less heuristic) to the sweep-executor hunt row's evidence.
10. Consider excluding `docs/status/**` from the dprint markdown corpus (fleet config) so snapshot churn ends structurally, not just empirically.
11. Add cadence knobs to `.docs-gates.json` explicitly (mirroring webphone's block) so the fleet defaults changing underneath cannot re-red cadence.
12. Consider a CI job running the docs-gates battery (markers-history job precedent) so gate regressions land as CI red.
13. Run one full `buildflow --build-mode full --max-time 60m` on the quiet machine for a 48/48 artifact (optional; the local full flake check already covers the nix side).
14. Triage `audit_max: 111` for genuinely-open historical items (e.g. the ESL presence-coverage gap and the Lens UI vhost decision already have TODO rows; confirm, then shrink the pin).
15. Verify the four phantom-tag E/ref sites (is the hash a commit mislabeled as a tag?) and append correction records if honest.
16. Execute the existing sweep-executor hunt row: per-process audit instrumentation (auditd or a nix wrapper) for the mystery `nix flake update` executions; tonight's repair-tool attribution narrows but does not close it.
17. First real deployment close-out lane (owner hands-on steps; repo side metal-boot-proven) — existing BLOCKED row.
18. fspbx trial verdict sign-off (owner) — existing BLOCKED row.
19. Warsaw DID re-purchase + KYC window (owner) — existing BLOCKED row.
20. Telnyx API key rotation (owner) — existing BLOCKED row.
21. Fill or delete the scrub-patterns OWNER TO ADD placeholders (owner) — existing BLOCKED row.
22. Promote browser E2E CI cadence (periodic/per-push; owner call) — existing BLOCKED row.
23. Wire sops-nix into an example host (owner-gated) — existing BLOCKED row.
24. GitHub residual-exposure appetite after the history rewrite (owner) — existing BLOCKED row.
25. Fix the global `core.hooksPath` landmine via home-manager — existing BLOCKED row.
26. CI posture: branch protection + required checks (owner; workflow change) — existing BLOCKED row.
27. nixpkgs upstream lane: draft the CPUSchedulingPolicy/config-dir ask (verify-before-filing first) — existing BLOCKED row.
28. Refresh the webphone capability audit re-score at the new release pin (the pin moved twice tonight: v2.13.0 lineage).
29. ASR transcription owner decision (the audit's one open capability gap) — existing owner-gated item.
30. Execute the harvested push-transports row (`push.ntfy` / `push.fcm` option surface) — the row this session added.
31. `retentionDays` facade option (T13; only if a policy applies) — existing row.
32. Per-DID named identities (owner-gated) — existing row.
33. Docs batch remainder: hook-strip + go-git long-form into the operating lessons file — existing TODO row.
34. Ops/test depth batch (verify-live livez gates, operator version endpoint consumption, missed-call ring shape, cdr-visibility row-shape assert, synthetic-DID convention doc) — existing TODO row.
35. pma go-commit hook gating: the structural fix for the daemon hook-bypass class + the flake.lock exclude_pathspecs lever — existing TODO row.
36. crush-config lessons: add the round-11 sweep lessons by commit — existing TODO row.
37. go-cqrs-lite#120 relock-and-rerun for the passkey enroll leg — existing BLOCKED row.
38. Root-cause the load-sensitive logout-assert from the handoff report (suite settle-wait vs upstream bug) — routed item.
39. Retention purge / backup staging verification after tonight's release pin moves (the derived backup set rides the new pin).
40. Re-run the full local `nix flake check` after tonight's relock train (my green was proven at the pre-v2.13.0 pin; the relock commits carry their own ritual verdicts).
41. Explicitly re-verify the aarch64 lane after the runner-label change lands in CI (the local gate omits aarch64-linux).
42. Update the AGENTS.md daemon-sweep paragraph with the repair-tool attribution (folds into item 1 if done together).
43. Sweep the CHANGELOG fourth-sweep bullet's executor note into the lessons file's 2026-11-10 entry (one-clause append).
44. Confirm `ruff format` idempotency across the full tree after the daemon's next sweeps (one `ruff format --check` in the next session ritual).

## g) QUESTIONS FOR THE OWNER

1. **Push authorization and timing:** may I push this repo (session fixes + tonight's relock train) and cue-policy now? The changed `ci.yml` only proves itself on CI, and the arm64 label's first live run needs the push — but pushing also publishes the workflow change and the fleet policy widening.
2. **Rule-F style intent:** is the fleet's spaces-around-inline-code rule the intended end-state for prose (meaning the deliberate "`code`s" plural style in CHANGELOG/README/lessons gets reworded), or should this repo exempt rule F and keep the style?
3. **Annotate backlog appetite:** burn the 48 pinned annotate findings down now (content verdict surgery on archived snapshots, incl. appending correction records for the four phantom-tag sites), or keep them ratcheted indefinitely and only fix net-new?
