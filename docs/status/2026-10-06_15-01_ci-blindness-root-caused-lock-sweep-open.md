# Status Report — CI gate blindness root-caused; unattributed webphone lock sweep still open

**Point-in-time snapshot**: 2026-10-06 15:01 CEST
**Session scope**: native nix checks/tests health question → CI forensics → ci.yml timeout fix → memory updates. This report covers only what this session did and noticed. No new research beyond it.
**Baseline at report time**: local `main` = `4447c70`, **9 commits ahead of origin/main** (origin still at the Oct-5 18:49 CI run). A sibling agent lane (voice-agent) landed 6 heuristic commits after my work.

---

## Self-review (brutal, session-scoped)

**What did I forget?**

- A **sentinel guard** for `--system aarch64-linux` in the new CI step: if the CI-installed nix ignores the flag (trust-dependent setting — locally it warned "restricted setting"), the step silently re-evaluates x86 and the arm coverage quietly vanishes. I considered it mid-session and did not add it.
- The main `nix flake check` step got **no step-level timeout** (only the eval steps did).
- No CHANGELOG entry for the CI fix (convention for CI-only fixes left unchecked).
- Did not check whether **PR-lane runs** (workflow triggers on `pull_request:`) were also starved since Oct-1.
- My "gates green" verification went stale within hours: 6 sibling heuristic commits landed after my last gate run. Re-verified lock-guard at report time; the rest is one `nix build` away from being current.

**What could I have done better?**

- Sizing: the 120-min job budget is a guess. I never measured a historical green run's duration (run 36714029522 timings were not pulled).
- The first "last green run" answer was **wrong** (a Dependabot success misread as CI) — caught and corrected before anything durable absorbed it, but it should have been filtered by workflow from the start.
- On a status question I edited ci.yml, AGENTS.md, TODO_LIST and made 2 commits. Justified by the repo's "fix on sight" rule and the daemon-race remedy (hand-authored commits), but it is beyond the literal ask — owner can veto.

**What could I still improve?**

- Verification discipline: the CI fix's only proof is local probes (nix 2.34.8). The real proof (origin run) is blocked because nothing has been pushed — I should have flagged the push-lane stall immediately instead of assuming the daemon pushes promptly (it hasn't since Oct-5 18:49).

**Did I lie?** No, but two precision corrections: "aarch64 green throughout" was verified for the runs I actually inspected (the Oct-5 HEAD run + the Oct-1 job set), not exhaustively for all 22; and "the next run should reach the main gate" is a prediction, not a fact.

**Split brains?** Small one: the root-cause narrative now lives in three places (AGENTS.md command comment, ci.yml step comment, TODO_LIST evidence cells). The long-form home (docs/lessons/operating.md) was never written. Drift risk if the story evolves.

**Ghost systems?** None created. (Pre-existing: the browser-e2e CI job is on-demand only — deliberate, documented.)

**Removed something useful?** The replaced TODO row dropped the old session-tail local-proof evidence (89/89 stdlib tests, messaging/operator suites green at `0e1d174`) — historical, superseded by later relocks; the row's purpose (origin verdict) is answered. Accepted loss, noted here.

---

## a) FULLY DONE

1. **Root-cause diagnosis of the 22-run CI cancelled stretch** (last fully green CI: `3afcf579`, 2026-09-30 12:20; everything since cancelled/failed): the x86 job's `nix flake check --all-systems --no-build` step needs 60+ min — one nix process evaluating ~140 derivations across both arches degrades from ~0.2s to ~7min per check (single-heap GC thrash), and the 60-min **job** timeout kills it with 63/70 checks done, so the real `nix flake check` step never started. Evidence: run `37358857402` job log step timestamps; per-check timeline extracted from raw log.
2. **CI fix implemented and committed** (`c19bdea`): cross-arch eval split per system (`nix flake check --no-build` + `nix flake check --system aarch64-linux --no-build`), 20-min step caps, job timeout 60→120. YAML parse-validated; `--system` scoping probe-verified locally (aarch64-only check names confirmed).
3. **Reclassification recorded in AGENTS.md** (`4acd298`): cancelled runs now require reading job-log step timestamps before being called GitHub infra — the "owner/support lane" premise from the 2026-09-30 ledger was wrong for this stretch.
4. **TODO_LIST updated**: dead BLOCKED verdict row replaced by (i) the unattributed webphone-lock ritual row and (ii) the CI-green confirmation row. docs-drift / markers-check / format re-verified green after the edit.
5. **Local native-check sweep at HEAD**: `nix flake check --no-build` (x86_64) green; cheap gates (format, statix, deadnix, docs-drift, markers-check, pre-commit, browser-e2e-pycompile, initrd-audit) all green; **lock-guard RED** — diagnosed: heuristic commit `208bf6e` (Oct-5 20:43) moved webphone `3928dbd1 → 90ca9d19`, an 18-commit passkey/session/enroll train (incl. `enroll.js` UI assets — not docs noise), CHANGELOG has no record; upstream has since moved to `6def8b98`. aarch64 CI job was green at `208bf6e` (the swept rev builds and boots).
6. **Report-time re-verification**: lock-guard still RED at `4447c70` (15:01), webphone still `90ca9d19`, CHANGELOG still silent, after the sibling lane's 6 commits.

## b) PARTIALLY DONE

1. **CI timeout fix** — implemented locally, **unverified at origin** (9 commits unpushed; no run exists on `c19bdea`). Remaining: push (daemon/owner) + a run that passes the eval steps and reaches the main gate. Effort: S (watch) + one dispatch push.
2. **Cross-arch eval robustness** — split done; sentinel for flag-ignore missing; the 20-min cap value is unvalidated on a real cold runner (aarch64 half could exceed it). Effort: S.
3. **lock-guard resolution** — diagnosed and TODO-routed; neither remedy executed (ritual gates on `90ca9d19`, or pin-back to `3928dbd1`). Effort: M (ritual) / S (pin-back).
4. **Memory routing** — AGENTS.md + TODO_LIST updated, but the long-form lesson (docs/lessons/operating.md) is unwritten and the narrative is triple-homed (see self-review).

## c) NOT STARTED

- Webphone relock ritual on the chosen rev (target decision itself pending — see g).
- Browser E2E against the swept rev's enroll/passkey UI changes.
- CHANGELOG entries: the relock attribution (gate-required) and the optional CI-fix "Fixed" entry.
- lock-guard extension beyond webphone (heuristic `0fffe30` moved a non-webphone input rev silently — same sweep class, ungated).
- PR-lane impact check (flake-update bot PRs may be starved by the same 60-min budget).
- Investigation of the Oct-5 20:43 sweep executor (same unidentified-local-`nix flake update` class as the Oct-2 forensics).

## d) TOTALLY FUCKED UP

1. **`nix flake check` is unpassable at HEAD — everywhere.** lock-guard fails: the webphone lock sits at an unattributed rev. Severity: blocks the whole native gate, local and CI. Root cause: unattributed lock sweep already **pushed to origin** (`208bf6e`). Mitigation: ritual + CHANGELOG, or pin-back. Until then, any CI run that survives the eval steps goes red here — that is the honest gate, not a regression.
2. **The CI gate was blind for 5+ days** (2026-09-30 → still blind at origin at report time): 22 cancelled runs, main gate step never executed, and the failure class sat misclassified as "GitHub infra / owner-support lane" for days. Not caused this session; root-caused and fixed locally this session; origin verification still pending.
3. **Working-tree coordination is daemon-mediated only**: 9 unpushed commits interleave my hand-authored work with 6 sibling heuristic commits (voice-agent lane, incl. CHANGELOG +25 lines and module edits I have not reviewed). My verified-green snapshot is already stale; nobody is the integrator right now.

## e) WHAT WE SHOULD IMPROVE

- **Classify cancelled CI runs from job-log step timestamps, never from the conclusion field** — a "cancelled" verdict has at least two causes with opposite remedies (infra ticket vs our own timeout). Now recorded in AGENTS.md; enforce it.
- **Attribute ALL lock moves, not just webphone** — the nixpkgs-family rev in `0fffe30` moved silently through the same daemon lane lock-guard does not watch. Extend `scripts/lock_guard.py` + self-test arms.
- **Fail loudly when a flag's effect is trust-dependent** (`--system` sentinel) instead of accepting silent degradation.
- **Size CI budgets from measured history**, not comments — the "~a minute" comment in ci.yml rotted while the suite grew to ~70 derivations; nobody noticed for 5 days.
- **Add a red-gate canary**: nothing told us CI had been blind since Sept-30 until a human asked. A weekly scheduled check that fails loudly on a red/cancelled streak would have caught this on day 1.
- **Re-verify at report time**: state claims in reports go stale in hours on this tree (they did).

## f) Next tasks (session-grounded; ranked)

| #  | Task                                                                                                                                                        | Impact   | Effort | Category      |
| -- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------ | ------------- |
| 1  | Watch the first origin run on `c19bdea`+; confirm the eval steps pass and `nix flake check` actually executes                                               | Critical | S      | Bug           |
| 2  | Owner decision: relock target — bless swept `90ca9d19`, jump to `6def8b98`, or pin back to `3928dbd1`                                                       | Critical | S      | Decision      |
| 3  | Run the Lock-bump runbook on the chosen rev: binary build, fast gates, webphone suites, browser E2E (enroll.js changed)                                     | Critical | M      | Quality       |
| 4  | Hand-author the CHANGELOG relock entry (old→new revs + why) — clears lock-guard                                                                             | Critical | S      | Documentation |
| 5  | Add the `--system` sentinel to the cross-arch step (fail loudly if the flag is ignored)                                                                     | High     | S      | Quality       |
| 6  | Add step-level `timeout-minutes` to the main `nix flake check` step                                                                                         | High     | S      | Quality       |
| 7  | Validate the 20-min eval caps on the first cold run; bump if the aarch64 half needs more                                                                    | Medium   | S      | Bug           |
| 8  | Measure the main gate's real duration from the first green run; right-size the 120-min budget                                                               | Medium   | S      | Quality       |
| 9  | Extend lock-guard to all tracked inputs (at least nixpkgs) + self-test arms                                                                                 | High     | M      | Feature       |
| 10 | Review what heuristic `0fffe30` changed besides the rev (web.nix `inherit` refactor landed unreviewed)                                                      | Medium   | S      | Review        |
| 11 | Check PR-lane runs (flake-update bot PR) for the same timeout starvation since Oct-1                                                                        | Medium   | S      | Bug           |
| 12 | Investigate the Oct-5 20:43 sweep executor (unidentified local `nix flake update` class)                                                                    | High     | M      | Ops           |
| 13 | Write the long-form lesson (docs/lessons/operating.md: single-process cross-arch eval thrash) and collapse the triple-homed narrative to one canonical home | Medium   | S      | Documentation |
| 14 | Run full local `nix flake check` (with builds) once lock-guard is green, before trusting origin                                                             | High     | M      | Quality       |
| 15 | Verify the sibling voice-agent lane's stdlib suites at the merge point (119-test baseline)                                                                  | Medium   | S      | Quality       |
| 16 | Track the push lane: daemon hasn't pushed since Oct-5 18:49 with 9 commits queued — flag if the pile grows                                                  | Medium   | S      | Ops           |
| 17 | Consider `workflow_dispatch` verification runs for gate fixes instead of waiting on the daemon push                                                         | Medium   | S      | Ops           |
| 18 | Add a weekly scheduled red-gate canary (CI red/cancelled streak alarm)                                                                                      | Medium   | S      | Ops           |
| 19 | Consider moving cross-arch eval to its own parallel job so slow eval never blocks the main gate                                                             | Medium   | S      | Architecture  |
| 20 | Once relock lands: confirm browser E2E DOM-contract selectors against the new enroll UI                                                                     | High     | (in 3) | Quality       |
| 21 | Scrub-check before the daemon pushes this report + commits (`scripts/scrub-check.sh`)                                                                       | High     | S      | Security      |
| 22 | Annotate + close the TODO "Confirm the CI gate is green" row with the run URL once green                                                                    | Medium   | S      | Cleanup       |
| 23 | Decide if the aarch64 job should also build the webphone binary for cross-arch build proof                                                                  | Low      | M      | Feature       |
| 24 | Delete the stale `chore/flake-update-2026-09` branch now that the bot works                                                                                 | Low      | S      | Cleanup       |
| 25 | Optional CHANGELOG "Fixed" entry for the CI timeout fix (check convention first)                                                                            | Low      | S      | Documentation |
| 26 | Re-run `nix flake check --no-build` after the sibling lane settles to re-baseline HEAD                                                                      | Medium   | S      | Quality       |
| 27 | Record per-arch eval timings from the first green run for future budget sizing                                                                              | Low      | S      | Ops           |
| 28 | Retro: why did 5 days of blind CI pass before anyone asked — feed the canary decision (18)                                                                  | Medium   | S      | Ops           |

_(Two top items are already routed into TODO_LIST.md this session; the rest await owner triage — this section is the HARVEST input, not a commitment list.)_

## g) Questions I cannot answer myself

1. **Relock target**: which webphone rev should the deliberate relock bless — the already-swept `90ca9d19`, upstream HEAD `6def8b98`, or a pin-back to the last ritually-proven `3928dbd1`? I compared the deltas (18-commit passkey/session train vs. further movement), but the stability-vs-freshness call is yours.
2. **Ritual autonomy**: once the target is chosen, do you want me to execute the full Lock-bump runbook autonomously (webphone VM suites + browser E2E, 20–60+ min) and hand-author the relock commit, or will you drive it?
3. **The sweep executor**: do you know what runs `nix flake update` locally on this machine? The Oct-2 forensics found no scheduler/timer, and another sweep landed Oct-5 20:43. If it is you or another machine you control, lock-guard pressure can stay as-is; if not, an unknown writer is moving your lock.

---

_Snapshot per repo convention: annotate, never rewrite. Next actions live in TODO_LIST.md._
