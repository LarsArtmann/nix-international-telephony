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

| Task                                                                                              | Status       | Impact | Effort | Evidence                                                                                                                                              |
| ------------------------------------------------------------------------------------------------- | ------------ | ------ | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| Browser E2E WebRTC test (chromium `--use-fake-ui-for-media-stream`, 1000→1001 call)               | 🔵 `BLOCKED` | High   | 1d     | Adds ~1-2 GB to the test closure; awaiting appetite decision (ROADMAP open question 3)                                                                |
| Secrets via sops-nix/agenix (render directory/gateway/event-socket/TURN at activation)            | 🔵 `BLOCKED` | High   | 1-2d   | Secrets bake into world-readable store XML/JS (`modules/telephony.nix`, `modules/freeswitch.nix`); tooling decision pending (ROADMAP open question 1) |
| Rename local directory to match the public repo (`nix-international-telephony`)                   | 🔵 `BLOCKED` | Low    | 15min  | Breaks active shells/cwd; awaiting user decision (`docs/status/2026-08-21_09-49_…retrospective.md` §g Q1)                                             |

## Medium Impact

| Task                                                                               | Status    | Impact | Effort | Evidence                                                                                                                |
| ---------------------------------------------------------------------------------- | --------- | ------ | ------ | ----------------------------------------------------------------------------------------------------------------------- |
| Verify CI green directly (`gh run list`/`gh run watch`) and cite it in FEATURES.md | 🔴 `TODO` | Med    | 15min  | FEATURES.md CI row rests on report testimony (`docs/status/2026-08-21_09-40_…release.md` §5), never observed first-hand |
| Split `modules/telephony.nix` (~770 lines) into options + wiring files             | 🟡 `WORTH_CONSIDERING` | Low | 1h | nix-review 2026-08-21: only structural finding; current single-file shape is a documented convention, revisit if it keeps growing |

## Low Impact

| Task                                                                                        | Status    | Impact | Effort | Evidence                                                                                                         |
| ------------------------------------------------------------------------------------------- | --------- | ------ | ------ | ---------------------------------------------------------------------------------------------------------------- |
| aarch64 validation (cross or native runner)                                                 | 🔴 `TODO` | Low    | 2h     | flake `systems` declares it; never built                                                                       |
| VM demo polish: forward 443 to host, print URL + demo passwords on console                  | 🔴 `TODO` | Low    | 30min  | `hosts/pbx/default.nix` sets no `forwardPorts`                                                                   |
| Webphone resilience: auto-reconnect, registration refresh, remember-me                      | 🔴 `TODO` | Low    | 3h     | `app.js` disconnect handler only flips status to offline on disconnect                                                      |
| Webphone call features: multi-call, DTMF keypad, history, duration, ringback                | 🔴 `TODO` | Low    | 1d     | `app.js` rejects second incoming call; no keypad/history                                                 |
| Content-Security-Policy header for the webphone vhost                                       | 🔴 `TODO` | Low    | 30min  | No `add_header` in the nginx vhost (`tls` options)                                             |
| sip.js update script (`packages/webphone/update.sh`)                                        | 🔴 `TODO` | Low    | 30min  | 0.21.2 pinned by hand (pinned sip.js tarball in `packages/webphone`)                                                     |
| Split `tests/pbx.nix` into named tests (webphone/dialplan/tls) for bisect                   | 🔴 `TODO` | Low    | 2h     | Single monolithic test file                                                                                      |
| systemd hardening review (freeswitch, telephony-tls units)                                  | 🔴 `TODO` | Low    | 1h     | Only an `ExecStartPre` mkdir exists (`turn` options)                                            |
| Split `ext-sip-ip` / `ext-rtp-ip` options                                                   | 🔴 `TODO` | Low    | 1h     | Both derive from the same `externalIp` var (`natAddress` wiring)                                    |
| Ops docs: runbook (fs_cli cheat-sheet, cert rotation, gateway debug) + architecture diagram | 🔴 `TODO` | Low    | 3h     | README covers usage only                                                                                         |
| Encode doc-lifecycle rules in AGENTS.md + harden TODO/FEATURES citations to option names    | 🔴 `TODO` | Low    | 1h     | Audit retrospective §e.3-4 (`docs/status/2026-08-21_09-49_…retrospective.md`); `file:line` cites rot on refactor |
| Run `nix flake check --all-systems` once to evaluate the aarch64 outputs                    | 🔴 `TODO` | Low    | 30min  | x86_64 gate skips them (flake `systems`); declared but never evaluated                                         |
