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
- fail2ban shipped for SIP auth failures (`v0.2.0`); remaining idea:
  an nginx/443 scanner jail in front of the webphone
- Security hardening guide (firewall-to-provider, TURN exposure)
- SSH posture for real deployments: per-user key authorization (vs the
  demo's global `sshKeys` opening every account), per-host key selection
  (only the managing machine's key on prod), an operator key-rotation
  procedure, optional fail2ban/sshguard in front of an exposed 22,
  host-key persistence notes, one `ssh-audit` triage pass
- Deeper edge verification: TLS handshake on 5061 (not just the
  listener), loopback-only 8021 binding assert, wsprobe probes as suite
  assertions, NAT advertisement runtime test (two-NIC VM topology for
  `natAddress`), manual TLS mode runtime test, RTP port-range
  enforcement assert
- Hoster-level firewall posture (Hetzner Cloud Firewall) in front of the
  NixOS firewall

### 2. PBX feature depth

Grow from a dialtone-and-bridge PBX to one that replaces commercial offerings
for a small org. Direction: features stay declarative Nix options, never
interactive GUI state.

Raw ideas:

- DISA
- IVR nested sub-menus (menu → menu) when a real deployment asks
- Conference polish: MOH-when-alone profile option, pin-leg suite depth
- Gateway keepalive options (ping/pingMax/expiry) so REGED flaps are
  debuggable/avoidable in any NAT deployment
- Per-destination egress routing (country → gateway) once a second trunk
  exists; `register = false` peer-trunk dialplan leg
- Voicemail depth: transcription/summary (STT) on top of the mailer,
  HTML email template option, S3-compatible archive alternative
- Announcement option for the shipped `*97` no-record dial
- `force_local_ip_v4` option for deterministic sofia binding (escape the
  auto-detect race outright); `apply-nat-acl` option when `natSipAddress`
  is set (edge-proxy mode)
- Feature ideas worth stealing from the fspbx trial (keep as reference
  only — the verdict is NixOS-first): fax/SMS app structure, ESL-integrated
  profile sync, their iptables + fail2ban default posture
  (`docs/research/2026-09-16_fspbx-trial.md`)
- DB-backed directory (mod_pgsql + PostgreSQL) for large extension counts
- CDR to database; sounds at 16 kHz for better prompt quality
- Fax (T.38): nixpkgs' FreeSWITCH already ships `mod_spandsp`
  (`rxfax`/`txfax`/`t38gateway`) — receive-to-file plus mailer
  notification follows the voicemail/recordings patterns; needs a
  T.38-capable trunk (DIDWW market a fax product, see
  `docs/providers/`) and a dedicated fax DID routed to it

### 3. Web client maturity

Direction: the browser is a first-class phone, not a demo.

Raw ideas:

- Verify auto-reconnect live (kill nginx, watch backoff + re-register)
  — ideally folded into the browser E2E; the watchdog's auto path stays
  best-effort (reload recovery is the guaranteed backstop)
- Tree-shaken SIP.js bundle (import only needed modules)
- mod_verto as an alternative webphone transport (compiled into nixpkgs
  FreeSWITCH) — maybe drop the nginx proxy hop
- SIP.js version-bump path: evaluate the reconnect-hang against 0.22/0.23
  changelogs; FsAudioAgent
- Call-history export/clear button; UI languages beyond EN/DE (the
  strings table makes it cheap)
- Demo-VM smoke script for humans (register→call→recording in one
  command)
- Browser-suite ergonomics: wall-time reduction, failure dumps shipped
  as a CI artifact on red; depth candidates: wrong-password login path,
  multi-device (two browsers, one extension) call, call-history/DTMF
  asserts beyond the current media legs, voicemail deposit leg

### 4. Protocol & scale

Direction: correct behaviour at the network edge, then scale.

Raw ideas:

- IPv6 SIP profiles behind an `ipv6.enable` flag
- `freeswitch_exporter` + Grafana observability spike (metrics, not the
  ESL status page — P14 owns that); systemd network-restart linkage for
  freeswitch after address changes (operational nicety; network-online
  covers the boot case)
- Runtime validation for the shipped coturn turns:/DTLS listener
  (`turn.tls` is eval-verified only); QoS/DSCP marking options for RTP
- Kamailio edge proxy spike for large registration counts (time-boxed,
  defer until real load)
- Load-test spike (50 concurrent scripted REGISTERs, sofia reg limits);
  real-network WebRTC validation (webphone over LTE); external coturn
  reachability test; STIR/SHAKEN attestation grade check once the US
  number is live

### 5. Ecosystem & distribution

Direction: this stack should not stay a private flake.

Raw ideas:

- Upstream `services.telephony` to nixpkgs — the upstreamability
  checklist now lives in `docs/upstream.md`; a generated option-reference
  (`man`-style) dump would ride along
- Upstream fixes: the nix-ssh-config `KbdInteractiveAuthentication` issue
  is FIXED upstream (v0.1.3, pinned here); remaining nix-ssh-config
  upstreams: `prohibit-password` tri-state for `allowRootLogin`, a stance
  on agent/stream-local forwarding; the nixpkgs freeswitch
  `network-online.target` ordering PR is prepped in `docs/upstream.md`;
  also worth filing: qemu-vm's `diskInterface = "scsi"` emulates lsi53c895a,
  not virtio-scsi (documentation gap found by the metal-boot test)
- Repo plumbing: split CI into an eval/lint matrix vs the VM job for
  faster bisect; BuildFlow ergonomics (`watch`/`diff` in the dev loop);
  a drift-alarm-style check failing when `flake.lock` changes without a
  CHANGELOG line
- ~~Scheduled `nix flake update` PR cadence~~ done: monthly
  `.github/workflows/flake-update.yml` opens a reviewable refresh PR
- Machine-readable repo surface: `llms.txt` / generated index of flake
  options, VM suites (name, what it proves, how to run) and the runbook
  for AI sessions and integrators (steal-the-idea from Telnyx Builds;
  could be a flake check like `checks.docs-drift`)

### 6. Agent-calling integrations

Direction: the PBX is the telephony backend for a CV/agent pipeline
(`docs/providers/` requirement), not only for humans.

Raw ideas:

- Agent-call MVP spike: event-socket originate + human-in-the-loop
  bridge (warm-transfer/whisper patterns)
- Telnyx agent tooling evaluation: `@telnyx/agent-cli`, the MCP
  endpoint, no-key demo endpoints — against raw Call Control
- Outbound-agent guardrails: per-trunk cost caps (didlogic
  max-call-cost as the model spec), anti-spam compliance (STIR/SHAKEN,
  in-country CLI rules)

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
2. **Real ITSP (answered by adoption):** Telnyx is the primary trunk —
   paid tier, live US DID, Call Control app + outbound profile (verified
   against the live API 2026-09-14); first calls pending the deploy lane.
   DIDWW (failover + emergency calling) and Zadarma (budget DIDs) remain
   documented options in [`docs/providers/`](docs/providers/README.md).
   Both digest and IP-peer wiring are supported by `gateways`
   (`allowedCidrs` + `firewall.restrictExternalTo` for IP-peering).
3. **Browser E2E appetite (answered 2026-08-22):** added now — two chromium
   instances run a real 1000→1001 WebRTC call. Kept OUT of the default
   `checks` gate (closure cost); a manual `workflow_dispatch` CI job runs it
   on demand (default 2026-08-22). Promoting it to periodic or per-push
   gating remains an owner call.
4. **Primary deployment target (answered 2026-08-29):** public VPS — owner
   picked Hetzner Cloud (EU latency, IP-on-interface so no `natAddress`,
   traffic included) with ACME/Let's Encrypt. The ACME port-80 firewall gap
   this question gated was already fixed (edge.nix opens 80 in acme mode,
   regression-tested in `tests/eval.nix`); LAN/self-signed stays available as
   a mode, not the first target.
5. **Recording-consent posture (answered 2026-09-16):** record ALL calls
   by default, consent risk accepted by the owner — the first real
   traffic is ungated; revisit only if the deployment's jurisdictions
   (PL/DE/US legs) demand notification.
6. **`services.qemuGuest.enable` on prod (open):** panel screenshots /
   graceful shutdown convenience vs minimal unit graph; does not affect
   networking.
