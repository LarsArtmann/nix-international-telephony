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

| Task                                                                                   | Status       | Impact | Effort | Evidence                                                                                                                                              |
| -------------------------------------------------------------------------------------- | ------------ | ------ | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Browser E2E WebRTC test (chromium `--use-fake-ui-for-media-stream`, 1000→1001 call)    | 🔵 `BLOCKED` | High   | 1d     | Adds ~1-2 GB to the test closure; awaiting appetite decision (ROADMAP open question 3)                                                                |
| Secrets via sops-nix/agenix (render directory/gateway/event-socket/TURN at activation) | 🔵 `BLOCKED` | High   | 1-2d   | Secrets bake into world-readable store XML/JS (`modules/telephony.nix`, `modules/freeswitch.nix`); tooling decision pending (ROADMAP open question 1) |
| Rename local directory to match the public repo (`nix-international-telephony`)        | 🔵 `BLOCKED` | Low    | 15min  | Breaks active shells/cwd; awaiting user decision (`docs/status/2026-08-21_09-49_…retrospective.md` §g Q1)                                             |

## Medium Impact

| Task                                                                               | Status                 | Impact | Effort | Evidence                                                                                                                          |
| ---------------------------------------------------------------------------------- | ---------------------- | ------ | ------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Split `modules/telephony.nix` (~770 lines) into options + wiring files             | 🟡 `WORTH_CONSIDERING` | Low    | 1h     | nix-review 2026-08-21: only structural finding; current single-file shape is a documented convention, revisit if it keeps growing |

## Low Impact

| Task                                                    | Status    | Impact | Effort | Evidence                                                     |
| ------------------------------------------------------- | --------- | ------ | ------ | ------------------------------------------------------------ |
| aarch64 VM boot (QEMU aarch64 demo VM or native runner) | 🔴 `TODO` | Low    | 1h     | Packages + config build/eval proven; TCG attempt (2026-08-22): kernel boots, root disk device times out under layered emulation — needs native/accelerated runner |
