# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- Dialplan voicemail fallbacks used `<anti-action>` (which runs when the
  condition does NOT match), so FreeSWITCH answered unrelated calls with
  voicemail before denial extensions could reject them; fallbacks are now
  plain actions after `bridge` gated by `continue_on_fail`/`hangup_after_bridge`.
- Denial extensions now hang up with explicit causes
  (`call_rejected`/`normal_temporary_failure`/`unallocated_number`) instead of
  the `respond` app.

### Changed

- TURN authentication switched from a static username/password pair to
  REST-style ephemeral credentials: coturn runs with `use-auth-secret`
  and a systemd unit derives short-lived username/password pairs (48 h
  validity, renewed daily) into the runtime-rendered `config.js`.
  `turn.username`/`turn.password` are replaced by `turn.authSecret`.

### Added

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
