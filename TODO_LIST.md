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

| Task                                                                                          | Status         | Impact | Effort | Evidence                                                                                                                                           |
| ---------------------------------------------------------------------------------------------- | -------------- | ------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| sops-nix recipe doc (age keygen, `.sops.yaml`, `sops.secrets` incl. `owner = "turnserver"` for coturn) on top of the landed `*File` options | 🟡 `IN_PROGRESS` | Medium | 2h     | Module-side support landed (`passwordFile`/`authSecretFile`/`eventSocketPasswordFile`, `telephony-secrets` VM test green); recipe doc queued behind the user's integration-depth answer |

## Medium Impact

| Task                                                             | Status         | Impact | Effort | Evidence                                                                                                                                     |
| ----------------------------------------------------------------- | -------------- | ------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| aarch64 CI green on KVM-less GitHub arm runners                  | 🟡 `IN_PROGRESS` | Low    | -      | `telephony-boot-tcg` (minimal boot suite, `kvm` feature dropped) runs same-arch TCG; full suites cannot fit the driver's fixed 300s shell window. Local x86 gate green; first boot-tcg CI run in flight |
| Decide browser-E2E CI gating once its stability is proven        | 🔵 `BLOCKED`   | Low    | 15min  | Suite is green locally (`nix build -L .#telephony-browser`) and kept out of the default gate (closure cost); awaiting user call on CI gating   |

## Resolved this cycle (log lines live in CHANGELOG.md)

- Split `modules/telephony.nix` into `modules/telephony/` — done (options/pbx/web/edge/shared).
- Browser E2E WebRTC test — done (two chromium instances, fake media, 1000→1001 call, `legacyPackages.telephony-browser`).
- File-based secrets for FreeSWITCH/coturn — done (placeholders in the store, `LoadCredential` + `replace-secret` splice, `telephony-secrets` VM test).
- Rename local directory to the public repo name — resolved as won't-do (historical typo is deliberate).
