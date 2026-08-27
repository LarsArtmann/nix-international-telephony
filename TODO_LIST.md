# TODO List

> Short-term, actionable, bounded work items, verified against the actual code.
> For long-term vision and unrefined ideas, use ROADMAP.md.
> Items are ranked by impact. Status is verified, not assumed.

## Status legend

| Status           | Meaning                                                     |
| ---------------- | ------------------------------------------------------------ |
| 🔴 `TODO`        | Not started. Needs doing.                                   |
| 🟡 `IN_PROGRESS` | Actively being worked on.                                   |
| 🔵 `BLOCKED`     | Cannot proceed, external dependency or decision needed.      |
| 🟢 `DONE`        | Completed. Remove from this list and log in `CHANGELOG.md`.  |

## High Impact

| Task                                                                                                                                                                             | Status         | Impact    | Effort | Evidence                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------- | --------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| First real deployment: server + DNS, fill every `CHANGEME` in hosts/pbx-prod, provision secrets, install + run the docs/deploy.md verification checklist                        | 🔵 `BLOCKED`   | Critical | 2h     | Repo-side path is complete (template, runbook, eval gate); blocked on owner inputs — server, domain/DNS, ITSP choice (ROADMAP open question 2), real secrets   |
| 0.2.0 release: CHANGELOG cut, tag + GitHub release, repo metadata polish (topics/description)                                                                                   | 🔴 `TODO`      | Medium    | 45min  | Feature set since 0.1.x is release-worthy (secrets, browser E2E, aarch64 CI, deploy path); gitleaks full-history scan clean (96 commits, 0 real secrets, 2026-08-27) |

## Medium Impact

| Task                                                                                                                             | Status         | Impact | Effort | Evidence                                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------- | -------------- | ------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| deploy.md truth pass + port-table dedup: add port 80 + 22 rows, exact secret count (4 mandatory + 2 optional), `fs_cli -p "$(cat …)"` note for `*File` operators; make `docs/ops-runbook.md` the single canonical port table deploy.md links to | 🔴 `TODO` | High | 30m | Two drifting port tables today (`docs/deploy.md` §1 vs `docs/ops-runbook.md` health checks; 2026-08-27 report §e)                                     |
| Voicemail deposit/retrieval scripted test: message lands per extension, `*98`+PIN plays it, wrong PIN denied                                                    | 🔴 `TODO`      | Medium | 90min  | Only the fallback-answered path is asserted today; deposit/retrieval flows unscripted (FEATURES voicemail row)                                                    |
| Boot-smoke VM test for the `pbx-prod` host shape (secrets stubbed via tmpfiles, TLS overridden self-signed) — proves the template's unit graph starts on a non-QEMU shape | 🔴 `TODO` | Medium | 75min | `nixosConfigurations.pbx-prod` is eval-forced only, never booted (2026-08-27 report §e; plan M7)                                                                  |
| Negative eval test: setting both `password` and `passwordFile` (extension, gateway, ES, TURN) trips the exactly-one-of assertion | 🔴 `TODO`      | Medium | 35min  | Module asserts it (`modules/telephony/default.nix`); no test exercises the rejection (2026-08-22 06-39 report f.19; plan M8)                                        |
| Drift-alarm check: fail `nix flake check` when TODO_LIST rows duplicate FULLY_FUNCTIONAL FEATURES rows                                                            | 🔴 `TODO`      | Medium | 1h     | Doc drift currently needs archaeology; proposed repeatedly (05-18/06-39 reports)                                                                                 |
| CI step: `nix flake check --all-systems --no-build` (cheap cross-arch eval; catches the drv-context bug class before the arm job burns hours)                   | 🔴 `TODO`      | Medium | 30m    | The 08-24 context bug cost a full arm CI cycle; local dual-gate practice already proven                                                                          |
| Ops docs pack: runbook teaches `wsprobe.py` + browser failure dumps to operators; agenix variant section in `docs/secrets.md`                                    | 🔴 `TODO`      | Medium | 90min  | Strongest debugging tools are invisible to operators (2026-08-24 report §e); sops recipe has no agenix twin                                                       |
| Assert RTP media actually flows in the browser E2E call                                                                           | 🔴 `TODO`      | Low    | 1h     | The suite proves signaling + channel bridging (`show channels count`), not byte flow (`legacyPackages.telephony-browser`)                                          |
| Promote browser E2E CI from manual dispatch (owner call)                                                                          | 🔵 `BLOCKED`   | Low    | 15min  | `workflow_dispatch` job landed in ci.yml; periodic/per-push gating is the owner's call, tracked in ROADMAP open question 3                                        |

## Low Impact

| Task                                                                                                                              | Status    | Impact | Effort | Evidence                                                                                                      |
| --------------------------------------------------------------------------------------------------------------------------------- | --------- | ------ | ------ | -------------------------------------------------------------------------------------------------------------- |
| Repo hygiene bundle: dedupe `sip_server` helper into tests/common.nix, parametrize `wait_for_freeswitch` port, timedelta migration, favicon.ico, CHANGELOG repeated-heading pre-commit lint | 🔴 `TODO` | Low | 90min | Duplicate helper (pbx.nix + dialplan.nix); hardcoded 5060 probe; deprecation noise; 404 favicon; heading decay recurred once |
| Extend docs-health annotation scripts (section scoping, M/B row IDs, post-write shape assertion) and propose upstream to the skill | 🔴 `TODO`  | Low    | 1h     | The 2026-08-27 audit hit all three gaps; the newline bug (d.1 of the audit report) was a direct consequence    |
