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
| First real deployment: server + DNS, fill every `CHANGEME` in hosts/pbx-prod, provision secrets, install + run the docs/deploy.md verification checklist                        | 🔵 `BLOCKED`   | Critical | 2h     | Repo-side path is complete (template, runbook, eval gate, boot-smoke); blocked on owner inputs — server, domain/DNS, ITSP choice (ROADMAP open question 2), real secrets   |
| 0.2.0 release: CHANGELOG cut, tag + GitHub release, repo metadata polish (topics/description)                                                                                   | 🔴 `TODO`      | Medium    | 45min  | Feature set since 0.1.x is release-worthy (secrets, browser E2E, aarch64 CI, deploy path, IVR/conference/monitoring); gitleaks full-history scan clean |

## Medium Impact

| Task                                                                                                                             | Status         | Impact | Effort | Evidence                                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------- | -------------- | ------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Assert RTP media actually flows in the browser E2E call (media stats / getStats, not just channel bridging)                      | 🔴 `TODO`      | Low    | 1h     | The suite proves signaling + bridging (`show channels count`), not byte flow (`legacyPackages.telephony-browser`)                                                 |
| Browser E2E depth: wrong-password leg asserts the on-screen `#login-error`, reconnect drill (kill nginx -> backoff -> re-register -> call works), DTMF keypad UI case | 🔴 `TODO` | Medium | 75min  | The webphone now surfaces error reasons in the pill and login error (M19) — the browser suite should pin them                                                       |
| `*97` no-record dial: VM-test the generated `extension_norecord_*` twins (dial `*97<ext>`, assert no WAV lands for that call)    | 🔴 `TODO`      | Low    | 30m    | Generator emits the twins (eval-verified); behaviour not yet scripted                                                                                             |
| vm-to-email end-to-end test with a real mailer (msmtp catch-all in the VM)                                                       | 🔴 `TODO`      | Low    | 1h     | `vmEmail` option emits `vm-mailto` (eval-verified); sending needs a mailer_app config + test harness                                                              |
| Promote browser E2E CI from manual dispatch (owner call)                                                                          | 🔵 `BLOCKED`   | Low    | 15min  | `workflow_dispatch` job landed and ran green on 2026-08-27; periodic/per-push gating is the owner's call (ROADMAP open question 3)                                 |

## Low Impact

| Task                                                                                                                              | Status    | Impact | Effort | Evidence                                                                                                      |
| --------------------------------------------------------------------------------------------------------------------------------- | --------- | ------ | ------ | -------------------------------------------------------------------------------------------------------------- |
| IVR `*`/`#` key entries and multi-digit keys: VM coverage (current suite covers 1/2 digits + fallback)                            | 🔴 `TODO` | Low    | 30m    | Generator handles them; only plain digits are scripted                                                          |
