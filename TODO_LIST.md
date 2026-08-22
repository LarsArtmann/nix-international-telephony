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
| README Security section: document `*File` options replacing the "secrets land in the store" limitation | 🔴 `TODO`   | High   | 30min  | Status report 2026-08-22 §C: README still describes the pre-`*File` trade-off                                                                      |
| Eval-level regression test: directory dial-string template must use single-dollar runtime vars | 🔴 `TODO`   | Medium | 30min  | The over-escaping bug was only catchable by the browser E2E suite; a generated-XML assert catches it in seconds (status report 2026-08-22 §E.4)    |

## Medium Impact

| Task                                                             | Status         | Impact | Effort | Evidence                                                                                                                                     |
| ----------------------------------------------------------------- | -------------- | ------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| aarch64 CI green on KVM-less GitHub arm runners                  | 🟡 `IN_PROGRESS` | Low    | -      | `telephony-boot-tcg` (minimal boot suite, `kvm` feature dropped) runs same-arch TCG; CI green on runs 32570862334 + 32571156312. Full suites cannot fit the driver's fixed 300s shell window; boot-proof-only unless ARM hardware appears |
| A/B-verify the plain ws-binding (:5066) and remove it if unnecessary | 🔴 `TODO`  | Medium | 30min  | Added on the outbound-transport hypothesis before the real dial-string fix landed; never re-tested without it (status report 2026-08-22 §B)   |
| Add gateway `passwordFile` coverage to the secrets suite         | 🔴 `TODO`      | Medium | 30min  | Only extension/event-socket/TURN file modes are asserted today                                               |
| tests/tls-mode-host.nix: register in flake checks or delete      | 🔴 `TODO`      | Low    | 15min  | File exists but is wired into no flake output (predates this session)                                        |
| Decide browser-E2E CI gating once its stability is proven        | 🔵 `BLOCKED`   | Low    | 15min  | Suite is green locally (`nix build -L .#telephony-browser`) and kept out of the default gate (closure cost); awaiting user call on CI gating   |

## Resolved this cycle (log lines live in CHANGELOG.md)

- Split `modules/telephony.nix` into `modules/telephony/` — done (options/pbx/web/edge/shared).
- Browser E2E WebRTC test — done (two chromium instances, fake media, 1000→1001 call, `legacyPackages.telephony-browser`).
- File-based secrets for FreeSWITCH/coturn — done (placeholders in the store, `LoadCredential` + `replace-secret` splice, `telephony-secrets` VM test).
- Rename local directory to the public repo name — resolved as won't-do (historical typo is deliberate).
