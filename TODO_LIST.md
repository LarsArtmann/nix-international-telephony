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
| Open TCP port 80 when `tls.mode = "acme"` + `openFirewall` (or record the owner decision to document it instead): ACME's HTTP-01 challenge is served on 80, which `modules/telephony/edge.nix` never opens — first-boot issuance fails on a default-firewalled host and nginx/webphone/wss stay down | 🔴 `TODO` | Critical | 30m  | `modules/telephony/edge.nix` `allowedTCPPorts` lacks 80; found during the 2026-08-27 self-review (`docs/status/2026-08-27_10-19_real-deployment-path-session.md` §d.1) |
| First real deployment: server + DNS, fill every `CHANGEME` in hosts/pbx-prod, provision secrets, install + run the docs/deploy.md verification checklist                        | 🔵 `BLOCKED`   | Critical | 2h     | Repo-side path is complete (template, runbook, eval gate); blocked on owner inputs — server, domain/DNS, ITSP choice (ROADMAP open question 2), real secrets   |
| Extend `checks.telephony-eval` (regression guards, seconds each): firewall port 80 in acme mode, `apply-candidate-acl localnet.auto`, `wss-binding 127.0.0.1:7443`, one `@TELEPHONY_*@` placeholder per configured `*File` option | 🔴 `TODO` | High | 1h | Pattern proven — the check's first run caught the acme eval bug (`tests/eval.nix`; 2026-08-24/08-27 reports)                                                   |
| 0.2.0 release: CHANGELOG cut, tag + GitHub release, repo metadata polish (topics/description)                                                                                   | 🔴 `TODO`      | Medium    | 45min  | Feature set since 0.1.x is release-worthy (secrets, browser E2E, aarch64 CI, deploy path); gitleaks full-history scan clean (96 commits, 0 real secrets, 2026-08-27) |

## Medium Impact

| Task                                                                                                                             | Status         | Impact | Effort | Evidence                                                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------------- | -------------- | ------ | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| deploy.md truth pass + port-table dedup: add port 80 + 22 rows, exact secret count (4 mandatory + 2 optional), `fs_cli -p "$(cat …)"` note for `*File` operators; make `docs/ops-runbook.md` the single canonical port table deploy.md links to | 🔴 `TODO` | High | 30m | Two drifting port tables today (`docs/deploy.md` §1 vs `docs/ops-runbook.md` health checks; 2026-08-27 report §e)                                     |
| Boot-smoke VM test for the `pbx-prod` host shape (secrets stubbed via tmpfiles, TLS overridden self-signed) — proves the template's unit graph starts on a non-QEMU shape | 🔴 `TODO` | Medium | 45m | `nixosConfigurations.pbx-prod` is eval-forced only, never booted (2026-08-27 report §e)                                                               |
| Negative eval test: setting both `password` and `passwordFile` (extension, gateway, ES, TURN) trips the exactly-one-of assertion | 🔴 `TODO`      | Medium | 30m    | Module asserts it (`modules/telephony/default.nix`); no test exercises the rejection (2026-08-22 06-39 report f.19, still open)                                    |
| Assert RTP media actually flows in the browser E2E call                                                                           | 🔴 `TODO`      | Low    | 1h     | The suite proves signaling + channel bridging (`show channels count`), not byte flow (`legacyPackages.telephony-browser`)                                          |
| Promote browser E2E CI from manual dispatch (owner call)                                                                          | 🔵 `BLOCKED`   | Low    | 15min  | `workflow_dispatch` job landed in ci.yml; periodic/per-push gating is the owner's call, tracked in ROADMAP open question 3                                        |
