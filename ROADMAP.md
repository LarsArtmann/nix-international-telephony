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
- Monitoring: exporter or fs_cli-driven health timer with alerts on profile
  down and gateway registration failures
- fail2ban / rate-limiting for SIP scanning
- Security hardening guide (firewall-to-provider, TURN exposure)

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
- Tree-shaken SIP.js bundle (import only needed modules)
- mod_verto as an alternative webphone transport (compiled into nixpkgs
  FreeSWITCH) — maybe drop the nginx proxy hop
- FsAudioAgent / SIP.js version-bump path

### 4. Protocol & scale

Direction: correct behaviour at the network edge, then scale.

Raw ideas:

- IPv6 SIP profiles behind an `ipv6.enable` flag
- Kamailio edge proxy spike for large registration counts (time-boxed,
  defer until real load)

### 5. Ecosystem & distribution

Direction: this stack should not stay a private flake.

Raw ideas:

- Upstream `services.telephony` to nixpkgs (the module/test are already
  structured like upstream `nixosTests`)

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

1. **Secrets tooling:** sops-nix or agenix — and should the module _require_
   it (hard assertion) or merely support file-based overrides for a soft
   migration from store secrets?
2. **Real ITSP:** which provider (digest username/password vs IP-peer) should
   the gateway options be validated against first? Is there a DID available to
   target in a demo config?
3. **Browser E2E appetite:** is adding chromium + fake media to the VM test
   (~1-2 GB closure, CI minutes) desired now, or is SIP-level verification the
   accepted gate until manual browser QA?
4. **Primary deployment target:** public VPS with ACME/Let's Encrypt, or
   lab/LAN with self-signed TLS first? This decides where TLS and hardening
   effort goes first.
