# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### Known limitations

- All secrets (extension, gateway, TURN, event-socket passwords) end up in the
  world-readable Nix store — wire a secret manager for exposed deployments.
- Emergency calling (911/112) is not wired.
- The webphone has not yet been validated with a real end-to-end browser call.
