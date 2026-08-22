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

| Task                                                                                          | Status         | Impact | Effort | Evidence                                                                                                                                           |
| ---------------------------------------------------------------------------------------------- | -------------- | ------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.2.0 release: gitleaks full-history scan, CHANGELOG cut, tag + GitHub release                 | 🔴 `TODO`      | Medium | 1h     | Feature set since 0.1.x is release-worthy (secrets, browser E2E, aarch64 CI); history never scanned for secrets before the repo went public          |

## Medium Impact

| Task                                                             | Status    | Impact | Effort | Evidence                                                                                                                                    |
| ---------------------------------------------------------------- | --------- | ------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Assert RTP media actually flows in the browser E2E call          | 🔴 `TODO` | Low    | 1h     | The suite proves signaling + channel bridging (`show channels count`), not byte flow; would have caught nothing new so far (status report §F) |
| Promote browser E2E CI from manual dispatch (owner call)         | 🔵 `BLOCKED` | Low  | 15min  | `workflow_dispatch` job landed in ci.yml (default); periodic/per-push gating is the owner's call, tracked in ROADMAP open question 3           |

## Resolved this cycle (log lines live in CHANGELOG.md)

- sops-nix recipe doc — done (`docs/secrets.md`, source-verified sops facts; docs-only, no flake input).
- README Security section — done (`*File` options documented, links the recipe).
- Eval-level dial-string regression test — done (`checks.telephony-eval`; also caught and fixed `tls.mode = "acme"` failing full system eval).
- A/B-verify the plain ws-binding (:5066) — done (removed; browser E2E green without it).
- Gateway `passwordFile` coverage — done (secrets VM test asserts purity, splice and live REG state machine).
- tests/tls-mode-host.nix — done (registered as the eval fixture behind `checks.telephony-eval`).
- aarch64 CI — accepted as boot-proof-only (`telephony-boot-tcg` under TCG; full suites need a KVM-capable ARM runner — owner hardware call).
- Split `modules/telephony.nix` into `modules/telephony/` — done (options/pbx/web/edge/shared).
- Browser E2E WebRTC test — done (two chromium instances, fake media, 1000→1001 call, `legacyPackages.telephony-browser`).
- File-based secrets for FreeSWITCH/coturn — done (placeholders in the store, `LoadCredential` + `replace-secret` splice, `telephony-secrets` VM test).
- Rename local directory to the public repo name — resolved as won't-do (historical typo is deliberate).
