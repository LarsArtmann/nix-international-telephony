# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Production-shape boot smoke (`checks.telephony-prod-boot`,
  `tests/prod-boot.nix`): the `hosts/pbx-prod` template (hardened sshd,
  file-based secrets, CDR, nginx webphone, coturn) booted as a VM with
  stubbed secrets and self-signed TLS — sofia bound on a real interface,
  nginx served the webphone over TLS, the spliced file secrets
  authenticated a scripted REGISTER, and nothing `CHANGEME`-shaped
  leaked into the runtime config. The template was eval-forced only
  before; now its unit graph provably starts.
- Negative eval assertions in `checks.telephony-eval`: setting both
  sides of a plain/`*File` secret pair (event socket, extension,
  gateway, TURN) is proven to trip the exactly-one-of assertion AND
  block the toplevel build — the rejection paths were never exercised
  before.
- Doc drift alarm (`checks.docs-drift`, `tests/drift_alarm.py`): a
  TODO_LIST row duplicating a `FULLY_FUNCTIONAL` FEATURES row fails
  the gate (two shared stable identifiers, or one option-style
  identifier); verified to fire on injected duplicates.
- Production host template `hosts/pbx-prod` (`nixosConfigurations.pbx-prod`):
  the deployable counterpart to the demo VM — real disk/bootloader
  fixtures, file-based secrets only (`*File` options, no credential in the
  store), `tls.mode = "acme"`, CDR, commented ITSP gateway + ACL posture,
  and hardened keys-only SSH (no root login). `nix flake check` evaluates
  its toplevel, so the template cannot rot; every operator decision is a
  marked `CHANGEME`.
- Deployment runbook (`docs/deploy.md`): prerequisites table (server, DNS,
  ITSP, ports), placeholder checklist, secrets provisioning (sops-nix or
  manual runtime files with a single `secretsDir` knob), three install
  paths (nixos-anywhere, NixOS installer, `nixos-rebuild --target-host`),
  a post-deploy verification checklist, day-2/rollback notes and an honest
  known-gaps list. README gained a "Deploying for real" section; the
  misleading deploy hint in the demo host header now points at `.#pbx-prod`.
- Eval-only regression check (`checks.telephony-eval`, `tests/eval.nix`):
  forces a full NixOS evaluation of every `tls.mode` variant
  (self-signed/manual/acme via the `tests/tls-mode-host.nix` fixture)
  and greps the generated directory XML for the dial-string's
  single-dollar runtime dial variables — the over-escaped
  `$${dialed_user}` pre-processor form breaks every `user/N` bridge and
  was previously only catchable by the browser E2E suite. First run
  caught a real bug (see Fixed). Extended to also assert the internal
  profile's `wss-binding 127.0.0.1:7443` and
  `apply-candidate-acl localnet.auto` (the two WebRTC lifelines), the
  acme-only TCP-80 firewall policy, and — via the all-`*File`
  `tests/file-secrets-host.nix` fixture — exactly one `@TELEPHONY_*@`
  placeholder per configured secret-file option in the generated XML.
- Gateway `passwordFile` coverage in the `telephony-secrets` VM test:
  store purity for the provider secret, runtime splice into
  `sip_profiles/external.xml`, and a live gateway REG state machine off
  the spliced config.
- sops-nix recipe (`docs/secrets.md`): age key setup, `.sops.yaml`, the
  exact `sops.secrets` shape (including `owner = "turnserver"` for
  coturn) and verification steps; option defaults verified against the
  sops-nix module source. Docs-only by design — no flake input added.
- CI `check` job gained a `nix flake check --all-systems --no-build` step:
  cross-arch eval breakage (the drv string-context bug class) is caught
  in about a minute, before the aarch64 job spends an hour building.
- Manual browser-E2E CI job (`workflow_dispatch` in ci.yml): runs
  `legacyPackages.telephony-browser` on demand; promotion to
  periodic/per-push gating stays an owner call.
- Runbook: listening-port reference table and a wss health check
  (`ss -ltn | grep 7443`) plus a webphone-failure troubleshooting note
  about the silent Via-transport drop.
- File-based secrets for everything that used to bake into the
  world-readable store: `eventSocketPasswordFile`,
  `extensions.<n>.passwordFile`, `gateways.<n>.passwordFile` and
  `turn.authSecretFile` (exactly-one-of with their plain counterparts is
  asserted). The generated FreeSWITCH XML carries `@TELEPHONY_*@`
  placeholders; the freeswitch unit assembles a private
  `/var/lib/freeswitch/conf` copy at start and splices the real values
  from systemd `LoadCredential` files (`replace-secret`), and coturn
  consumes its native `static-auth-secret-file`. Manager-agnostic by
  design (sops-nix/agenix only need to render the runtime files);
  covered by the `telephony-secrets` VM test (store purity, runtime
  privacy/modes, mixed plain/file registrations, TURN allocation).
- Browser E2E suite (`legacyPackages.telephony-browser`, deliberately
  outside the `checks` gate for its ~1-2 GB chromium closure): two
  headless chromium instances with fake media register as extensions
  1000/1001 through the nginx wss proxy and complete a real WebRTC call
  (DTLS-SRTP), asserted server-side via fs_cli while up. Failures dump
  browser console, the webphone's event log, chromedriver logs, nginx
  access logs, a raw WebSocket-to-SIP probe and sofia's siptrace journal.
- Minimal boot VM suite (`telephony-boot`) proving
  kernel -> systemd -> freeswitch -> sofia with the smallest closure;
  its `telephony-boot-tcg` variant drops the `kvm` system feature and
  runs same-arch TCG in CI on GitHub's KVM-less arm runners
  (`ubuntu-24.04-arm`). Full VM suites cannot pass the test driver's
  fixed 300s serial-shell connect window under TCG.
- `telephony-secrets` and `telephony-boot` single-node checks (see
  above); the shared `tests/common.nix` boot helper now also waits for
  the event-socket listener (8021) before any `fs_cli` use — sofia
  profiles coming up does not mean mod_event_socket accepts yet.
- Hardened SSH on the example host: the new `nix-ssh-config` flake input
  (post-quantum, keys-only sshd) is wired into `nixosConfigurations.pbx`
  with the tracked operator keys authorized and keyboard-interactive
  disabled (NixOS + PAM would otherwise accept Unix account passwords,
  breaking keys-only); the demo VM forwards host port 2222 to the guest
  sshd. Covered by a new `telephony-ssh` VM test asserting the effective
  sshd config, a real key-based login negotiating the
  `mlkem768x25519` hybrid kex, and the password/root denial paths.
- Per-component NixOS VM test suites for fast bisect: `telephony-dialplan`,
  `telephony-webphone` and `telephony-tls-turn` (single-node, on shared
  `tests/common.nix` fixtures) alongside the multi-node `telephony`
  integration check.
- Operator runbook (`docs/ops-runbook.md`): service inventory, fs_cli
  cheat-sheet, health checks, certificate rotation per `tls.mode`, gateway
  REG-state debugging table, recordings/TURN credential rotation and
  emergency actions; plus a Mermaid architecture diagram in the README.
- Pre-commit hooks via git-hooks.nix: entering `nix develop` installs
  nixfmt, statix, deadnix and gitleaks (wrapped from nixpkgs) as git
  pre-commit hooks; the generated `.pre-commit-config.yaml` store symlink
  is gitignored.
- Recordings serving (`recording.serve.enable`): nginx directory listing
  of recorded calls at `https://<domain>/recordings/` behind HTTP basic
  auth (`basicAuthUser` + `basicAuthPasswordFile`, the htpasswd is
  rendered at runtime). VM-tested: 401 without/wrong credentials, listing
  with correct ones.
- Recordings retention (`recording.retentionDays`): daily timer deletes
  WAV files older than the window (`null` keeps them forever). VM-tested
  with an aged file.
- `extraConfigFiles`: escape hatch merging operator-supplied files into
  the generated FreeSWITCH config (keys are config-relative paths and
  override generated files on collision; validated against path traversal).
- systemd hardening for the telephony units: the root oneshots now run
  under `ProtectSystem=strict` (writing only to a tmpfiles-precreated
  `/var/lib/telephony`), `NoNewPrivileges` and restricted address
  families; freeswitch gains `NoNewPrivileges`/`ProtectHome` and an
  address-family set including `AF_NETLINK`, which sofia's interface
  enumeration requires (without it the first inbound INVITE stalls).
- Webphone multi-call and resilience: concurrent calls with hold/focus
  switching, a DTMF keypad (application/dtmf-relay INFO), call history
  and per-call duration timer, locally generated ringback, automatic
  transport reconnection with exponential backoff and re-registration,
  and opt-in "remember extension" (never the password). All sip.js API
  use verified against the pinned 0.21.2 type definitions.
- `natSipAddress`/`natRtpAddress`: advertise different public addresses
  in SIP vs SDP (asymmetric NAT, SIP edge proxies); each falls back to
  `natAddress` (or the local address when that is null).
- Content-Security-Policy header on the webphone vhost (same-origin
  plus `wss:` for the SIP proxy, everything else denied; asserted in the
  VM test).
- Demo VM polish: host port 443 forwarded into the VM and a console
  banner on every root shell listing URLs, extensions, demo passwords
  and the fs_cli invocation.
- `packages/webphone/update.sh`: repins the bundled sip.js tarball to a
  given npm version (default: latest), recomputes the hash and rebuilds
  the esbuild bundle as a smoke test.
- Multiple ITSP gateways (`services.telephony.gateways`) with per-gateway
  inbound DIDs and least-cost routing: outbound calls fail over across
  gateways in ascending priority. The single `gateway` option remains as a
  deprecated alias. VM-tested with two fictitious trunks.
- `cdr.enable`: CSV call detail records under `/var/lib/freeswitch/cdr-csv`
  (VM-tested).
- `tls.mode = "acme"`: wires `security.acme` for the domain and provisions
  the certificate to FreeSWITCH's SIP-over-TLS listener (agent.pem/cafile.pem
  plus a renewal path unit); `tls.acmeEmail` is required.
- `gateway.allowedCidrs` option: restricts inbound ITSP calls to the
  provider's addresses via a generated `acl.conf.xml` and
  `apply-inbound-acl` on the external profile (VM-tested).
- Scripted SIP client (`tests/sip.py`, stdlib only) and SIP-level VM tests:
  REGISTER with digest auth (MD5/SHA-256), wrong-password rejection,
  multi-device registrations, answered INVITE with PCMU media, gateway REG
  state, toll-allow denial (603), no-gateway 503, unknown-number 404,
  inbound-ACL rejection on 5080.
- Behavioural VM tests: call recording leaves a growing WAV (and none when
  disabled), ring-group voicemail fallback answers, `*98` is answered by
  voicemail check, `config.js` parses as strict JSON with TURN credentials,
  ports 5061/5080 (TCP+UDP) are listening.
- `config.js` body is now strict JSON after the JS assignment wrapper.
- Documentation set built and verified against the code by a docs-health
  audit: TODO_LIST.md, FEATURES.md, ROADMAP.md and docs/DOMAIN_LANGUAGE.md.

### Changed

- `modules/telephony.nix` split into `modules/telephony/` (options, pbx,
  web, edge, shared derived values) with unchanged option semantics.
- `tls.mode = "acme"` now delegates certificate wiring to the nginx
  vhost's `enableACME` (HTTP-01 challenge location, nginx group and
  reloads included) instead of a hand-rolled `security.acme.certs`
  entry.
- Removed the loopback plain-ws listener (5066): an A/B run of the
  browser E2E suite without it stayed green, disproving the
  outbound-transport hypothesis it was added on — after the dial-string
  fix, sofia bridges to WS-registered contacts over the wss transport
  alone. The internal profile now binds 5060/5061/7443 only.
- The webphone WebSocket path is now TLS end to end: nginx terminates the
  browser's `wss://` and proxies TLS to FreeSWITCH's new `wss-binding`
  on `127.0.0.1:7443` instead of a plain-ws hop (see Fixed).
- FreeSWITCH no longer runs under `SCHED_FIFO` (nixpkgs unit default):
  the upstream unit grants realtime priority with no RT time budget, so
  a runaway task could starve the whole host. This stack needs no
  realtime guarantees, so the module forces normal CFS scheduling —
  hardening only, unrelated to the boot flake fixed below.
- VM tests dump process-level diagnostics (blocked syscall, wchan, thread
  count, unit state, journal tail) when FreeSWITCH fails to come up,
  instead of aborting with a bare port timeout.
- Recordings moved from FreeSWITCH's private `/var/lib/freeswitch/recordings`
  to the shared `/var/lib/telephony/recordings` (group-readable, required
  for serving/retention); migrate existing hosts with
  `mv /var/lib/freeswitch/recordings/. /var/lib/telephony/recordings/`.
- `freeswitch-sounds` now declares `meta.license` as `lib.licenses.mpl11`
  (matching nixpkgs' FreeSWITCH packaging) instead of a raw string; the
  music-on-hold pack ships no license file and is documented as CC-BY
  upstream — mind attribution before redistributing it.
- TURN authentication switched from a static username/password pair to
  REST-style ephemeral credentials: coturn runs with `use-auth-secret`
  and a systemd unit derives short-lived username/password pairs (48 h
  validity, renewed daily) into the runtime-rendered `config.js`.
  `turn.username`/`turn.password` are replaced by `turn.authSecret`.

### Fixed

- `tls.mode = "acme"` + `openFirewall` never opened TCP 80, so ACME's
  HTTP-01 challenge timed out on a default-firewalled host: no certificate,
  and nginx/wss/webphone dead on the first boot — exactly the
  `hosts/pbx-prod` scenario. The firewall now opens TCP 80 only in acme
  mode, guarded by a `checks.telephony-eval` assertion (open in acme,
  closed in every other mode).
- `tls.mode = "acme"` failed a full NixOS evaluation: the module defined
  `security.acme.certs.<domain>` without any HTTP-01 challenge provider,
  which trips security.acme's exactly-one-challenge assertion. Found by
  the new `checks.telephony-eval` on its first run; fixed by delegating
  to the nginx vhost's `enableACME`.
- Webphone calls never worked from a real browser, for four stacked
  reasons found by the new browser E2E suite:
  - the nginx `location /sip` prefix match also captured `/sip.min.js`
    and proxied the SIP.js bundle to FreeSWITCH (400, dead webphone);
    now an exact-match `= /sip` location with a regression assert in the
    webphone suite;
  - the plain-ws proxy hop silently dropped every browser REGISTER:
    browsers only speak `wss://` from https pages, so SIP.js sends
    `Via: SIP/2.0/WSS`, and FreeSWITCH discards requests whose Via
    transport does not match the connection transport; nginx now proxies
    TLS to the internal profile's `wss-binding`;
  - WebRTC INVITEs from LAN/lab browsers were rejected with
    488 INCOMPATIBLE_DESTINATION because FreeSWITCH screens ICE
    candidates against `wan.auto` (which denies all private ranges)
    when no `apply-candidate-acl` is set; the profile now sets
    `localnet.auto`;
  - `bridge(user/N)` died with "No origination URL specified": the
    directory `dial-string` template over-escaped its runtime dial
    variables (`$${dialed_user}` pre-processor form instead of
    `${dialed_user}`), so contact expansion never produced a URL.
- FreeSWITCH silently bound its SIP listeners to `127.0.0.1` whenever no
  default route existed yet when it started: FreeSWITCH resolves
  `$${local_ip_v4}` by UDP-connecting toward an external address and
  falls back to loopback when that fails, leaving the PBX unreachable
  from the network until a manual restart. The same race made the VM
  tests nondeterministically time out (on slower machines sofia bound
  the real interface while the tests probed `localhost`). The service
  now orders after `network-online.target`, and the tests derive each
  listener's actual address instead of assuming `localhost`.
- Dialplan voicemail fallbacks used `<anti-action>` (which runs when the
  condition does NOT match), so FreeSWITCH answered unrelated calls with
  voicemail before denial extensions could reject them; fallbacks are now
  plain actions after `bridge` gated by `continue_on_fail`/`hangup_after_bridge`.
- Denial extensions now hang up with explicit causes
  (`call_rejected`/`normal_temporary_failure`/`unallocated_number`) instead of
  the `respond` app.

## [0.1.0] - 2026-08-21

First public release.

### Added

- `services.telephony` NixOS module: extensions, ring groups, voicemail, call
  recording, RTP port range, TLS (self-signed or manual certificates), NAT
  address, firewall toggle — fully typed options with 8 configuration
  assertions.
- FreeSWITCH XML configuration generated from Nix options (no FusionPBX or
  FreePBX): sofia internal/external profiles, directory, dialplan (echo test
  `9196`, `*98` voicemail check, ring groups, toll-allow-gated E.164 routing),
  event socket bound to localhost with a configured password.
- Static SIP.js 0.21 WebRTC webphone (esbuild-bundled, no CDN) served by nginx
  behind `wss://<domain>/sip`, with the SIP.js MIT notice shipped next to the
  bundle.
- coturn STUN/TURN wiring, credentials delivered to the webphone via
  `config.js`.
- Optional ITSP gateway for international calls and inbound DIDs (null makes
  PSTN dialling answer 503).
- FreeSWITCH prompts and music-on-hold package.
- Example host (`hosts/pbx`) and ephemeral demo VM (`nix run .#vm`).
- NixOS VM test (`tests/pbx.nix`): sofia profiles, directory lookups, a real
  `originate` dialplan call, webphone and `config.js` over TLS, WSS proxy to
  sofia, coturn, recordings directory.
- flake-parts project layout: packages, VM app, checks (VM test, treefmt
  format, statix, deadnix) and a dev shell (treefmt wrapper, nil, jq).
- CI: GitHub Actions running `nix flake check` (with a KVM udev rule for the
  NixOS VM test); MIT `LICENSE`.

### Known limitations

- All secrets (extension, gateway, TURN, event-socket passwords) end up in the
  world-readable Nix store — wire a secret manager for exposed deployments.
- Emergency calling (911/112) is not wired.
- The webphone has not yet been validated with a real end-to-end browser call.
