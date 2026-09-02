# TODO List

> Short-term, actionable, bounded work items, verified against the actual code.
> For long-term vision and unrefined ideas, use ROADMAP.md.
> Items are ranked by impact. Status is verified, not assumed.

## Status legend

| Status           | Meaning                                                     |
| ---------------- | ----------------------------------------------------------- |
| 🔴 `TODO`        | Not started. Needs doing.                                   |
| 🟡 `IN_PROGRESS` | Actively being worked on.                                   |
| 🔵 `BLOCKED`     | Cannot proceed, external dependency or decision needed.     |
| 🟢 `DONE`        | Completed. Remove from this list and log in `CHANGELOG.md`. |

## High Impact

| Task                                                                                                                                                     | Status       | Impact   | Effort | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | -------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| First real deployment: server + DNS, fill every `CHANGEME` in hosts/pbx-prod, provision secrets, install + run the docs/deploy.md verification checklist | 🔵 `BLOCKED` | Critical | 2h     | Repo-side path is complete (template, runbook, eval gate, boot-smoke, disko layout, infra/hcloud.tf); platform decided 2026-08-29 (Hetzner Cloud, pbx.artmann.tech pre-filled); ITSP research done — docs/providers/ recommends Telnyx primary + DIDWW failover; owner decision 2026-08-29: existing numbers (Vodafone DE mobile, Google Voice US, Revolut PL) are KEPT, integrated post-deploy as forwarding aliases into the new DIDs (no ports); blocked on owner: Hetzner token, Telnyx signup + first DIDs (US local, DE national), real secrets |

## Medium Impact

| Task                                                     | Status       | Impact | Effort | Evidence                                                                                                             |
| -------------------------------------------------------- | ------------ | ------ | ------ | -------------------------------------------------------------------------------------------------------------------- |
| Promote browser E2E CI from manual dispatch (owner call) | 🔵 `BLOCKED` | Low    | 15min  | `workflow_dispatch` job landed and ran green; periodic/per-push gating is the owner's call (ROADMAP open question 3) |
