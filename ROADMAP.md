# Roadmap

> Long-term direction and raw ideas. Items here are NOT actionable tasks.
> When an idea is refined into bounded work, it moves to TODO_LIST.md.

## Themes

### 1. Production hardening & secrets

Make the stack safe to expose to the internet. Direction: no plaintext secret
ever lands in the world-readable Nix store; inbound trust is pinned to the
provider; the stack tells you when it is sick.

Raw ideas:

- Secret-manager integration story (sops-nix / agenix / FreeSWITCH DB-backed
  directory) replacing store-baked credentials
- fail2ban / rate-limiting for SIP scanning
- Security hardening guide (firewall-to-provider, TURN exposure)
- SSH posture for real deployments: per-user key authorization (vs the
  demo's global `sshKeys` opening every account), optional fail2ban/
  sshguard in front of an exposed 22, host-key persistence notes
- Deeper edge verification: TLS handshake on 5061 (not just the
  listener), loopback-only 8021 binding assert, wsprobe probes as suite
  assertions

### 2. PBX feature depth

Grow from a dialtone-and-bridge PBX to one that replaces commercial offerings
for a small org. Direction: features stay declarative Nix options, never
interactive GUI state.

Raw ideas:

- IVR, DISA, conference rooms (vanilla FreeSWITCH modules already exist
  upstream)
- Time-based routing (business hours) per ring group
- Voicemail-to-email (`vm-mailto`)
- Per-extension outbound caller-id override; `*97` per-call recording toggle
  with announcement option
- DB-backed directory (mod_pgsql + PostgreSQL) for large extension counts
- CDR to database; sounds at 16 kHz for better prompt quality

### 3. Web client maturity

Direction: the browser is a first-class phone, not a demo.

Raw ideas:

- i18n (de/en) for the webphone UI
- Surface transport/registration errors in the UI (status pill only says
  "offline" today); verify auto-reconnect live (kill nginx, watch
  backoff + re-register) — ideally folded into the browser E2E
- Tree-shaken SIP.js bundle (import only needed modules)
- mod_verto as an alternative webphone transport (compiled into nixpkgs
  FreeSWITCH) — maybe drop the nginx proxy hop
- FsAudioAgent / SIP.js version-bump path

### 4. Protocol & scale

Direction: correct behaviour at the network edge, then scale.

Raw ideas:

- IPv6 SIP profiles behind an `ipv6.enable` flag
- coturn TLS/DTLS listeners (`turns:`) for restrictive NATs; QoS/DSCP
  marking options for RTP
- Kamailio edge proxy spike for large registration counts (time-boxed,
  defer until real load)

### 5. Ecosystem & distribution

Direction: this stack should not stay a private flake.

Raw ideas:

- Upstream `services.telephony` to nixpkgs (the module/test are already
  structured like upstream `nixosTests`)
- Upstream fixes discovered here: `network-online.target` ordering for the
  nixpkgs freeswitch unit; nix-ssh-config's `KbdInteractiveAuthentication`
  default undermining its advertised "keys only" on NixOS
- Scheduled `nix flake update` PR cadence (Dependabot-style) for input
  freshness

## Non-goals

Things we are deliberately NOT pursuing and why:

- **FusionPBX / FreePBX packaging:** PHP applications with interactive
  installers; not sanely Nix-packageable. The generated-XML approach replaces
  them.
- **Emergency calling (911/112):** needs a provider package and verified
  address handling. The README disclaimer stays until that exists; do not rely
  on this PBX for emergency calls.
- **GUI admin panel:** declarative Nix options are the interface; GUI state
  contradicts the hermetic-config principle.
- **Kamailio scale-out (for now):** YAGNI at v0.1 load levels; revisit when
  registration counts demand it.

## Open questions

Unresolved decisions that gate TODO_LIST work; answers belong in TODO_LIST
items once made.

1. **Secrets tooling (answered 2026-08-22):** the module is manager-agnostic —
   `*File` options render at service start from runtime files; sops-nix is
   the documented recipe direction (soft migration, no hard dependency).
   Remainder closed by default 2026-08-22: standalone recipe doc landed
   (`docs/secrets.md`); wiring sops-nix into the example host stays out
   until the owner asks for it.
2. **Real ITSP:** which provider (digest username/password vs IP-peer) should
   the gateway options be validated against first? Is there a DID available to
   target in a demo config?
3. **Browser E2E appetite (answered 2026-08-22):** added now — two chromium
   instances run a real 1000→1001 WebRTC call. Kept OUT of the default
   `checks` gate (closure cost); a manual `workflow_dispatch` CI job runs it
   on demand (default 2026-08-22). Promoting it to periodic or per-push
   gating remains an owner call.
4. **Primary deployment target (made concretely gating 2026-08-27):** public
   VPS with ACME/Let's Encrypt, or lab/LAN with self-signed TLS first? This
   decides whether the ACME port-80 firewall gap (TODO_LIST top row) is the
   immediate next task or can ride behind the first real deployment — and
   which TLS path gets validated first.
