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

| Task                                                                                                                                     | Status       | Impact    | Effort | Evidence                                                                                                                                                     |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ------------ | --------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| First real deployment: server + DNS, fill every `CHANGEME` in hosts/pbx-prod, provision secrets, install + run the docs/deploy.md verification checklist | 🔵 `BLOCKED` | Critical | 2h     | Repo-side path is complete (template, runbook, eval gate, boot-smoke); blocked on owner inputs — server, domain/DNS, ITSP choice (ROADMAP open question 2), real secrets |
| 0.2.0 release: CHANGELOG cut, tag + GitHub release, repo metadata polish (topics/description)                                             | 🔴 `TODO`    | Medium    | 45min  | Feature set since 0.1.x is release-worthy (secrets, browser E2E, aarch64 CI, deploy path, IVR/conference/monitoring/vmEmail); gitleaks full-history scan clean |

## Medium Impact

| Task                                                               | Status       | Impact | Effort | Evidence                                                                                                                    |
| ------------------------------------------------------------------ | ------------ | ------ | ------ | ---------------------------------------------------------------------------------------------------------------------------- |
| Promote browser E2E CI from manual dispatch (owner call)            | 🔵 `BLOCKED` | Low    | 15min  | `workflow_dispatch` job landed and ran green; periodic/per-push gating is the owner's call (ROADMAP open question 3)          |
