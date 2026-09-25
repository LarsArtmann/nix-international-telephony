# Status: webphone relock vendorHash breakage, oxfmt/treefmt war, binfmt host outage

- **Written**: 2026-09-25 04:05 CEST
- **Scope**: continuation session 2026-09-24 ~18:00 → 2026-09-25 ~04:05 CEST, resuming from `docs/status/2026-09-24_13-38_todo-blitz-docs-gates-operator-nat-backup.md`. Repo-side work from that report is DONE; this session was the verification tail (canonical full BuildFlow run + `nix flake check`) and turned into three incident fixes plus one host-side blocker.
- **TL;DR**: The 13:52 flake relock imported an upstream-broken webphone rev; fixed by forward-relocking to the first green rev. BuildFlow's full-mode formatter re-broke `checks.format`; fixed with a webroot exclusion. Bandit's repo-wide 84 "findings" were mostly banner noise; curated to zero real findings. Then the host rebooted and every nix build now fails on a missing `/run/binfmt` — root fix required, both final gates still outstanding. The reboot also destroyed the unpushed webphone fix commit in `/tmp/webphone` (see d1).

## Timeline

| Time (CEST) | Event |
| --- | --- |
| 24 Sep 13:52 | Daemon commit `8105834` lands a `flake.lock` change moving webphone `1776c3e` → `a74f8e6` (actor unknown — see g1) |
| 24 Sep ~13:38 | Prior session halted with all VM suites green at the then-locked `1776c3e` |
| 18:04 | Full BuildFlow run 1: `webphone-2.6.0.drv` fails — go-modules proxy missing zips for `go-error-family` v0.10.2, `cqrs-htmx/v4` v4.12.0, `go-sse` v0.6.1, `httputil` v1.3.0. Killed to stop the cascade |
| 18:10 | Root cause: upstream `a74f8e6` bumped deps with a stale `vendorHash`; upstream fixed it one auto-commit later (`94ae28d`, vendorHash-only diff, verified via GitHub compare). Relocked → `94ae28d`; `nix build .#webphone` green |
| 18:12 | `telephony-webphone` and `telephony-tls-turn` suites green at the new rev (1776c3e..94ae28d source delta: dep bumps, 61 MB upload cap, 500-redaction, templ views — no `config.js`/`SharedContact` changes, so the stack-side capitalized asserts stay valid) |
| 18:13–18:39 | Full BuildFlow run 2 (exit 69): `checks.format` (treefmt) RED — buildflow's format step had rewritten `operator.js` into oxfmt style before the check built (the two-formatters-one-file-set war). 34 success / 6 failed (format + cascades) |
| 18:41–18:49 | Fix: `exclude: packages/telephony-operator/webroot/**` added to `.buildflow.yml` (pattern proven in the webphone repo); `nix fmt` restored treefmt-canonical `operator.js`. Daemon committed |
| ~18:45 | Triage: nix-checker 8 findings = 4 FOD-hash (accepted remainder) + 4 port-collision false positives (QEMU guest 443 vs fail2ban jail 443; NAT suite's deliberate tcp+udp 5060 pair). bandit 84 findings = 80 banner/log lines + 4 real in `tests/browser-e2e.py` (B101 assert + three B108 `/tmp` marker paths) |
| 19:00 | `AGENTS.md` accepted-remainder extended with the port-collision class (daemon commit `af9761d`); bandit annotations committed; bandit repo-wide now 0 findings |
| ~03:00 | Full BuildFlow run 3 fails instantly at `nix develop`: `getting attributes of path "/run/binfmt": No such file or directory` |
| 03:05–04:00 | Host forensics (below). Also discovered: the reboot wiped `/tmp/webphone` — unpushed commit `31a8604` (SharedContact json tags + regression test) is LOST |

## Host outage (blocker, needs root on evo-x2)

- Uptime shows boot at ~22:35 on 24 Sep; every sandboxed nix build fails since.
- `/etc/nix/nix.conf` (root-managed): `extra-sandbox-paths = /run/binfmt /nix/store/…-qemu-aarch64-binfmt-P`.
- binfmt_misc itself is healthy: `aarch64-linux` registered and `status` = enabled; `systemd-binfmt.service` finished OK at boot.
- The current generation's `tmpfiles.d` contains NO binfmt rules. nixpkgs' `binfmt.nix` adds `/run/binfmt` to the nix sandbox paths (line ~283) and creates the directory + interpreter symlinks via tmpfiles rules (lines ~296-299) as one unit — this generation carries the first half without the second: internally inconsistent, hand-rolled, or wiped by a host-config override.
- Extra rot risk: the qemu entry in `extra-sandbox-paths` is a hard store path — a future GC of that path breaks builds again even with `/run/binfmt` restored.
- Remediation (owner, root):
  ```bash
  sudo mkdir -p /run/binfmt
  sudo ln -s "$(ls -d /nix/store/*-qemu-aarch64-binfmt-*/bin/qemu-aarch64 2>/dev/null | head -1)" /run/binfmt/aarch64-linux
  ```
  Proper fix: host config uses `boot.binfmt.emulatedSystems` so tmpfiles rules are module-managed (and survive reboots), or drops aarch64 emulation and removes `/run/binfmt` from `extra-sandbox-paths`.
- After the fix, the two outstanding gates are: `nix develop -c buildflow --build-mode full --max-time 60m` and `nix flake check`. Everything they cover is individually green; run 2's only real failure (`checks.format`) is fixed.

## a) FULLY DONE

1. Webphone relock breakage root-caused and fixed: lock forward-pinned to `94ae28d` (first green rev); `nix build .#webphone` green; `telephony-webphone` green; `telephony-tls-turn` green. Upstream delta verified as non-breaking for every wire contract our suites assert.
2. Formatter war closed for good: `.buildflow.yml` excludes the treefmt-owned webroot from BuildFlow's formatters; `nix fmt` clean; `checks.format` failure mode (run 2's only real red) eliminated at the root, matching the proven webphone-repo pattern.
3. Bandit repo-wide signal restored to zero real findings: `tests/browser-e2e.py` annotated at the four true locations (matching the file's existing `# nosec` style), compile + ruff-format verified, superfluous-nosec warning at line 62 remains as documented cosmetic noise.
4. nix-checker triage complete: 4 FOD-hash advisories (already accepted) + 4 new port-collision advisories judged false positives and documented in the `AGENTS.md` accepted-remainder sentence (daemon-committed `af9761d`).
5. Host outage root-caused to the missing `/run/binfmt` tmpfiles half with concrete, tested-by-inspection remediation commands (fix itself is root-gated).
6. Loss assessment for `/tmp/webphone` completed: commit `31a8604` confirmed destroyed by the reboot; recovery fully specified (see d1/c2).
7. Repo tree clean; every change this session daemon-committed (`dea4f46`…`af9761d`); `git status` empty.

## b) PARTIALLY DONE

1. The canonical verification tail: run 1 and run 3 died on external breakage (upstream vendorHash; host binfmt), run 2 completed with the format failure now fixed. The full pipeline has NOT yet finished green on this host — blocked by c1.
2. `AGENTS.md` accuracy: the accepted-remainder sentence is updated, but the "BuildFlow noise is DECIDED" bullet still doesn't record that markdown-lint/gitleaks/codespell are *skipped by build mode `full`* (the prior belief that they run only in full mode is refuted by tonight's run output).
3. Record-keeping of the prior snapshot: `docs/status/2026-09-24_13-38_…` now carries at least two refuted claims (stale "locked rev 1776c3e"; full-mode-only lint belief) and the operator.js formatting story has since changed twice — not yet annotated with resolution arrows per the annotate-only rule.
4. CHANGELOG: tonight's fixes (relock to `94ae28d`, webroot exclusion, bandit curation, port-collision remainder) have no `[Unreleased]` entries yet — done-work-logged convention currently unmet.

## c) NOT STARTED

1. The two final gates themselves (full BuildFlow green run, single `nix flake check`) — hard-blocked on the host `/run/binfmt` root fix.
2. Redo of the lost webphone SharedContact fix in a durable clone: `internal/domain/contact.go` json tags (`name`/`number` lowercase) + `TestConfigJSContactsWireKeys` in `internal/server/configjs_test.go` (mutate via the variadic `mutate` arg on `Deps.Shared`, not cfg); `go test ./...`; full spec is in the prior session's report. The bug is confirmed still present at `94ae28d` (the dep-bump commits don't touch it), so the fix is still wanted.
3. `CHANGELOG.md` entries for this session (see b4) and TODO_LIST evidence refresh on the BLOCKED webphone row (now "fix lost to reboot, redo pending, bug still live at 94ae28d").
4. Annotating the 13:38 snapshot (see b3).
5. Cheap post-fix re-verification sweep: `python3 tests/drift_alarm.py --self-test`, `scripts/scrub-check.sh --history --strict` over tonight's daemon commits, one gitleaks pass, `nix fmt` idempotency check.
6. CI confirmation that tonight's lock + exclusion keep `ubuntu-latest` green (next push).
7. lessons capture: "input tracking upstream main means a lock update can import upstream breakage — forward-pin to the first green rev and say so in the commit" (candidate for `docs/lessons/operating.md`).

## d) TOTALLY FUCKED UP

1. **Lost the unpushed upstream fix.** The handoff named `/tmp/webphone` fragility as risk #2; I verified commit `31a8604` intact at ~18:05 and then did nothing to secure it durably (a `git bundle`, a clone to `~/projects`, even a patch file in the repo-adjacent space). The host rebooted the same night and wiped it. Verification without mitigation was theater. The bug (SharedContact json tags) ships silently broken client-side at current upstream `94ae28d`, and the regression test with it. Redo required — the spec survives in the prior report, but that is cold comfort.
2. **Trusted the stale handoff over cheap ground truth.** The handoff said "locked rev 1776c3e"; I launched a 25-minute pipeline before checking `git log -- flake.lock` (two commands, ~5 seconds) which would have exposed the 13:52 relock immediately. Cost: a killed run and a confusing first failure.
3. **Planned around an unverified gate assumption.** I expected markdown-lint/gitleaks/codespell to run in the canonical full run; they are skipped BY build mode `full`. A one-line check of run output at 18:04 already showed the truth; I carried the wrong model from the handoff until run 2's summary forced it.
4. **Raced the daemon twice without watching it.** The daemon committed the relock (`dea4f46`, 18:12) and later the oxfmt-mangled `operator.js` mid-investigation; I reconstructed provenance after the fact instead of polling `git log` during long runs. Provenance confusion cost real time in both incidents.
5. **Left the record wrong overnight.** Knowing the 13:38 snapshot was refuted in two places, I deferred the annotation arrows — the annotate-only rule exists precisely so stale claims don't mislead the next session (it misled *this* one).

## e) WHAT WE SHOULD IMPROVE

1. Pre-flight ritual before any 25-60 min pipeline: `git log -- flake.lock` (recent movers), `uptime` (mid-session reboots), `nix flake metadata` for tracked inputs, tree clean. Seconds vs. a dead run.
2. Every "risk verified" gets a mitigation or an explicit accepted-risk note in the same breath — verified-but-unmitigated is how `31a8604` died.
3. Treat `/tmp` as ephemeral by policy: any unpushed work lives in `~/projects` or as a `git bundle` within minutes of creation, not at session end.
4. During long background runs, watch the daemon (`git log` every check-in) — it is a second author working concurrently.
5. Correct refuted snapshot claims in the same session that refutes them; annotation arrows are cheap.
6. Host config hygiene: module-managed `boot.binfmt.emulatedSystems` instead of hand-rolled `nix.conf` sandbox paths (hard store paths rot under GC — tonight's second breakage class waiting to happen).
7. Consider `nix flake update <input>` (new syntax) over the deprecated `--update-input` alias used tonight.
8. `nix-hash-fix` at 81% historical failure with 0 findings each time is a candidate for `skip_steps` like the webphone repo's documented precedent — owner call.
9. BuildFlow's system-profile binary staleness advisory (7e1fbfe vs HEAD 0b2dccd) still needs an owner-side rebuild/switch to clear.

## f) NEXT (prioritized, ~40 items)

**Unblock the gates**
1. Root-fix `/run/binfmt` on evo-x2 (commands above) or drop aarch64 emulation + `extra-sandbox-paths` entry.
2. Align the host config so the binfmt tmpfiles rules are module-managed (survive reboots).
3. Remove or `?`-optionalize the hard qemu store path in `extra-sandbox-paths` (GC-rot).
4. Re-run `nix develop -c buildflow --build-mode full --max-time 60m` → expect green (bandit 0 real findings; format war excluded; webphone fixed).
5. Run `nix flake check` end-to-end.
6. Watch the next CI run (`ubuntu-latest`) for the relock + exclusion.
7. Re-run `nix build .#checks.x86_64-linux.telephony-nat` once post-fix as an overnight-drift canary.

**Redo the lost upstream fix**
8. Clone webphone to `~/projects/webphone` (durable), redo the SharedContact json tags.
9. Re-add `TestConfigJSContactsWireKeys` (via the variadic `mutate` arg on `Deps.Shared`).
10. `go test ./...` green in that repo.
11. Leave unpushed pending owner instruction (g3); record the durable location in the TODO_LIST BLOCKED row.
12. After owner push + relock: flip `tests/webphone.nix` asserts to lowercase (existing BLOCKED row).

**Record-keeping (this session's debts)**
13. CHANGELOG `[Unreleased]`: relock to `94ae28d` (upstream vendorHash fix), webroot exclusion, bandit curation, port-collision remainder.
14. TODO_LIST: update the webphone BLOCKED row evidence (fix lost to reboot; redo pending; bug live at `94ae28d`).
15. Annotate `docs/status/2026-09-24_13-38_…`: stale lock rev claim; md-lint/gitleaks/codespell claim; operator.js formatting claim.
16. `AGENTS.md`: record that markdown-lint/gitleaks/codespell are skipped by build mode `full`.
17. Lessons: "tracked-main input + lock update can import upstream breakage; forward-pin to first green rev" → `docs/lessons/operating.md`.
18. Lessons: `/tmp` durability policy → global lessons reference candidate.
19. After gates pass: harvest this report's open items into TODO_LIST rows where repo-owned.

**Verification sweep (cheap, post-gates)**
20. `python3 tests/drift_alarm.py --self-test` (post-AGENTS.md edit).
21. `scripts/scrub-check.sh --history --strict` over tonight's daemon commits.
22. One gitleaks pass on the same range.
23. `nix fmt` twice → idempotent (no diff on second run).
24. `nix develop -c pre-commit run --all-files`.
25. Confirm `buildflow` (fast) run leaves the webroot untouched (exclusion effective in fix mode, not just detect).
26. Confirm bandit stays 0 via `buildflow -s bandit-check --format finding`.

**Upstream / owner decisions**
27. Answer g1 (who relocked at 13:52) — determines whether lock drift needs a guard.
28. Decide g2 (aarch64 emulation: keep module-managed, or drop).
29. Decide g3 (push path for the redone webphone fix).
30. BuildFlow binary refresh (owner switch) to clear the staleness advisory.
31. Owner call: `nix-hash-fix` → skip_steps (81% failure, 0 findings, webphone precedent).
32. Owner call (later): tag-pin webphone instead of floating main if relock incidents recur — contradicts the 2026-09-18 tracks-main decision, so only as a considered exception.

**Guardrails worth considering**
33. Pre-commit (or CI) check: flake.lock changes require a CHANGELOG line mentioning the input (makes relocks reviewable).
34. CI job step: `nix flake metadata` diff of tracked inputs vs. main, surfaced in PR checks (visibility for silent lock moves).
35. A tiny `scripts/doctor-host.sh` capturing the known host breakage classes (binfmt dir, store-path sandbox pins, buildflow binary staleness) — run before long pipelines.
36. Document the full-run gate matrix in `AGENTS.md` Commands section: what full mode skips (md-lint/gitleaks/codespell/pytest-test) so no session re-derives it.
37. Consider `BUILDFLOW_NO_RESULT_CACHE=1` only for single-step re-triage; keep cache for full runs (documented tonight for future sessions).
38. When NVD/vulnix replacement lands upstream, revisit the accepted-remainder sentence (vulnix arm).
39. Periodic: re-check `telephony-prod-boot` still boot-proves after upstream view changes (first real deployment still pending).
40. Periodic: re-verify `docs/providers/` claims before any purchase (standing rule, unchanged).

## g) QUESTIONS (cannot answer myself)

1. **Who or what relocked the webphone input at 13:52 yesterday** (daemon commit `8105834`)? Manual `nix flake update` by you, or an automation/timer? If automation, relock incidents like tonight's vendorHash breakage need a guard; if manual, I'll treat lock moves as intentional and stop treating the handoff's lock state as ground truth.
2. **Do you want aarch64 emulation kept on evo-x2?** If yes, I'd point the host config at module-managed `boot.binfmt.emulatedSystems` (self-healing tmpfiles, no hard store-path pins); if no, `extra-sandbox-paths` loses `/run/binfmt` and builds get simpler. Either is a host-config (root) change only you can apply.
3. **Push path for the redone SharedContact fix:** shall I redo it in a durable `~/projects/webphone` clone and hold it unpushed until you say so (current standing rule), or — given it is a real user-facing bug (shared contacts silently dropped from the dial typeahead) — do you want it pushed upstream directly this time?
