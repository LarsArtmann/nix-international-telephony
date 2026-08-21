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

| Task                                                                                         | Status         | Impact | Effort | Evidence                                                                                                                     |
| -------------------------------------------------------------------------------------------- | -------------- | ------ | ------ | ---------------------------------------------------------------------------------------------------------------------------- |
| SIP-level VM tests: scripted REGISTER, gateway REG state, 403/503 denial paths                | 🔴 `TODO`      | High   | 4h     | `tests/pbx.nix` never registers an endpoint, never checks gateway state or denial dialplan responses                            |
| Behavioural VM tests: recording file appears, voicemail fallback, `config.js` JSON parse, ports 5061/5080 | 🔴 `TODO` | High   | 3h     | `tests/pbx.nix:68-90` covers echo + serving only; gaps listed in `docs/status/2026-08-21_09-19_…retrospective.md` §f35-f40       |
| Browser E2E WebRTC test (chromium `--use-fake-ui-for-media-stream`, 1000→1001 call)           | 🔵 `BLOCKED`   | High   | 1d     | Adds ~1-2 GB to the test closure; awaiting appetite decision (ROADMAP open question 3)                                         |
| Secrets via sops-nix/agenix (render directory/gateway/event-socket/TURN at activation)        | 🔵 `BLOCKED`   | High   | 1-2d   | Secrets bake into world-readable store XML/JS (`modules/telephony.nix:170-183`, `modules/freeswitch.nix`); tooling decision pending (ROADMAP open question 1) |
| Rename local directory to match the public repo (`nix-international-telephony`)              | 🔵 `BLOCKED`   | Low    | 15min  | Breaks active shells/cwd; awaiting user decision (`docs/status/2026-08-21_09-49_…retrospective.md` §g Q1) |

## Medium Impact

| Task                                                                        | Status    | Impact | Effort | Evidence                                                                     |
| --------------------------------------------------------------------------- | --------- | ------ | ------ | ---------------------------------------------------------------------------- |
| Fix `sounds.nix` `meta.license` raw string → `lib.licenses.*`               | 🔴 `TODO` | Med    | 10min  | `packages/sounds.nix:29` uses the raw string `"MPL-1.1"`                     |
| TURN REST auth (`use-auth-secret` + ephemeral credentials in `config.js`)   | 🔴 `TODO` | Med    | 4h     | Static `user=` line in `modules/telephony.nix:472-474`; creds served publicly |
| `tls.mode = "acme"`: wire `security.acme` + provision cert for FS port 5061 | 🔴 `TODO` | Med    | 3h     | Enum lacks `acme` (`modules/telephony.nix:329-333`); README example untested  |
| Multiple gateways (`attrsOf`) with per-gateway routes/priority              | 🔴 `TODO` | Med    | 1d     | Gateway is a single `nullOr submodule` (`modules/telephony.nix:252-259`)      |
| Recordings browsing: nginx `location /recordings` + basic auth + retention  | 🔴 `TODO` | Med    | 3h     | Files land on disk only; no serving location (`modules/telephony.nix:447-463`) |
| CDR: configure `mod_cdr_csv` rotation (+ optional DB sink)                  | 🔴 `TODO` | Med    | 2h     | Module loaded (`modules/freeswitch.nix:188`) but vanilla-default, unconfigured |
| Restrict inbound ITSP to provider IPs (`apply-inbound-acl` option + firewall CIDR for 5080) | 🔴 `TODO` | Med | 2h | `modules/freeswitch.nix:336` hardcodes `none`; `modules/telephony.nix:482` opens 5080 broadly |
| `extraConfigFiles` escape hatch (attrsOf path → `configDir` passthrough)    | 🔴 `TODO` | Med    | 1h     | No such option; anything unmodelled currently requires forking the generator |
| Run the `nix-review` skill checklist against the flake                      | 🔴 `TODO` | Med    | 1h     | Never run; planned as `docs/status/2026-08-21_08-34_…scaffold.md` §9.50       |
| Verify CI green directly (`gh run list`/`gh run watch`) and cite it in FEATURES.md | 🔴 `TODO` | Med | 15min | FEATURES.md CI row rests on report testimony (`docs/status/2026-08-21_09-40_…release.md` §5), never observed first-hand |

## Low Impact

| Task                                                                        | Status    | Impact | Effort | Evidence                                                                     |
| --------------------------------------------------------------------------- | --------- | ------ | ------ | ---------------------------------------------------------------------------- |
| pre-commit config (nixfmt/statix/deadnix/gitleaks)                          | 🔴 `TODO` | Low    | 1h     | None in repo                                                                 |
| aarch64 validation (cross or native runner)                                 | 🔴 `TODO` | Low    | 2h     | `flake.nix:29-32` declares it; never built                                    |
| VM demo polish: forward 443 to host, print URL + demo passwords on console  | 🔴 `TODO` | Low    | 30min  | `hosts/pbx/default.nix` sets no `forwardPorts`                                |
| Webphone resilience: auto-reconnect, registration refresh, remember-me      | 🔴 `TODO` | Low    | 3h     | `app.js:127-128` only flips status to offline on disconnect                   |
| Webphone call features: multi-call, DTMF keypad, history, duration, ringback | 🔴 `TODO` | Low   | 1d     | `app.js:130-134` rejects second incoming call; no keypad/history             |
| Content-Security-Policy header for the webphone vhost                       | 🔴 `TODO` | Low    | 30min  | No `add_header` in the nginx vhost (`modules/telephony.nix:447-463`)          |
| sip.js update script (`packages/webphone/update.sh`)                        | 🔴 `TODO` | Low    | 30min  | 0.21.2 pinned by hand (`packages/webphone/default.nix:9-12`)                 |
| Split `tests/pbx.nix` into named tests (webphone/dialplan/tls) for bisect   | 🔴 `TODO` | Low    | 2h     | Single monolithic test file                                                   |
| systemd hardening review (freeswitch, telephony-tls units)                  | 🔴 `TODO` | Low    | 1h     | Only an `ExecStartPre` mkdir exists (`modules/telephony.nix:410-412`)         |
| Split `ext-sip-ip` / `ext-rtp-ip` options                                   | 🔴 `TODO` | Low    | 1h     | Both derive from the same `externalIp` var (`modules/freeswitch.nix:175-176`) |
| Ops docs: runbook (fs_cli cheat-sheet, cert rotation, gateway debug) + architecture diagram | 🔴 `TODO` | Low | 3h | README covers usage only                                                      |
| Encode doc-lifecycle rules in AGENTS.md + harden TODO/FEATURES citations to option names | 🔴 `TODO` | Low | 1h | Audit retrospective §e.3-4 (`docs/status/2026-08-21_09-49_…retrospective.md`); `file:line` cites rot on refactor |
| Run `nix flake check --all-systems` once to evaluate the aarch64 outputs     | 🔴 `TODO` | Low    | 30min  | x86_64 gate skips them (`flake.nix:29-32`); declared but never evaluated      |
