# Roadmap

> Long-term direction and raw ideas. Items here are NOT actionable tasks.
> When an idea is refined into bounded work, it moves to TODO_LIST.md.

## Themes

### 1. Production hardening & secrets

Make the stack safe to expose to the internet. Direction: no plaintext secret
ever lands in the world-readable Nix store; inbound trust is pinned to the
provider; the stack tells you when it is sick.

Raw ideas:

- Secret-manager integration story (sops-nix / agenix / FreeSWITCH
  DB-backed directory) replacing store-baked credentials — the module
  is manager-agnostic and the sops-nix recipe is shipped
  (`docs/secrets.md`, open question 1); the remainder is wiring it into
  an example host (owner-gated) and the DB-backed directory (theme 2)
- SSH posture live pass on the deployed host: one `ssh-audit` triage
  run and the Hetzner Cloud Firewall apply (the posture itself —
  per-user keys, per-host key selection, rotation procedure, host-key
  persistence — is documented in `docs/security.md`; the remaining work
  needs the real host)
- ~~NAT advertisement runtime test (two-NIC VM topology for
  `natAddress`)~~ done: `checks.telephony-nat` proves the full
  advertisement contract behind a port-forwarding router (2026-09-24)
- `nix.gc.automatic` on prod (small disk, growing closures); a
  trusted-users/substituter posture pass; an explicit FS
  `StateDirectoryMode` pin (documented 0750); a FreeSWITCH
  sound-compat drill before each nixpkgs bump (rides the monthly PR)

Shipped from this theme: fail2ban SIP + nginx/443 scanner jails, the
security hardening guide (`docs/security.md`), the deeper edge
verification (5061 TLS handshake, loopback-only 8021, wsprobe as suite
assertions, manual-TLS runtime test, RTP port-range enforcement), and
the NAT runtime suite.

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
- Operator-window depth: CDR freshness/vm-db-size/gateway-REG-age cards,
  recordings player, hangup-cause decode + colors, auto-refresh,
  `vm_delete` error-shape mapping, auth-cache TTL option, sms-store
  fixture depth, `parse_sms` bounded memory
- Simulator depth: IVR menu modeling, `--when` datetime picker,
  `--tz`/UTC-anchored mode, per-leg recording links, host-side unit
  tests for the pure logic
- Fax depth: mailer notification on received TIFF, T.38 posture note in
  deploy docs, TIFF/page-count validation helper
- DB-backed directory (mod_pgsql + PostgreSQL) for large extension counts
- CDR to database; sounds at 16 kHz for better prompt quality
- Fax (T.38): nixpkgs' FreeSWITCH already ships `mod_spandsp`
  (`rxfax`/`txfax`/`t38gateway`) — receive-to-file plus mailer
  notification follows the voicemail/recordings patterns; needs a
  T.38-capable trunk (DIDWW market a fax product, see
  `docs/providers/`) and a dedicated fax DID routed to it
- MMS: decided HTTP-API-only when a concrete need appears — no SIP
  standard exists, providers deliver it purely via HTTP APIs + webhooks;
  the shape (if ever) copies the SMS store pattern into an operator
  media tab (`docs/decisions/2026-09-17_mms-posture-http-api-only.md`)

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
  asserts beyond the current media legs, voicemail deposit leg,
  `/events` SSE session-gating + buffering asserts and a CSRF-403 leg
  in `tests/webphone.nix`; tee full `nix flake check` logs to a file
  with a per-suite summary
- Consume upstream `scripts/webphone-smoke.py` as a cheap post-build
  smoke for contexts where full VM suites are overkill
- Three-browser attended-transfer E2E (RFC 5589 heavy leg); a demo
  video of the UI (website-launch pattern) once visual QA lands

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
- Upstream nix: the eager global-registry fetch aborting offline
  indirect-ref resolution (nix 2.34, worked around by the opsTools pin);
  virtiofsd `--rlimit-nofile` headroom so path-flake hashing becomes
  VM-testable again
- Repo plumbing: split CI into an eval/lint matrix vs the VM job for
  faster bisect; BuildFlow ergonomics (`watch`/`diff` in the dev loop);
  a drift-alarm-style check failing when `flake.lock` changes without a
  CHANGELOG line; flake-update automation for the `webphone` input;
  a runtime `nix.nixPath` assert; ruff as the single Python formatter
  (treefmt); a pre-commit `*-DEBUG`-print ban under `packages/`;
  ahead-check wired into a timer or shell prompt; an advisory CI check
  when the webphone lock trails upstream main (stale-pin visibility);
  a `nix flake metadata` diff of tracked inputs surfaced in PR checks;
  browser E2E on webphone lock bumps (the eval-only flake-update PR
  cannot catch browser-only regressions); a tiny
  `scripts/doctor-host.sh` for the known host breakage classes (binfmt
  dir, store-path sandbox pins, buildflow binary staleness)
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
7. **Webphone lock governance (open, 2026-09-25):** lock moves have
   happened unattributed (the 13:52 daemon commit of 2026-09-24; the
   unrecorded 18:41 move) and one imported upstream breakage. Manual or
   automated? The answer decides whether relocks need a guard
   (CHANGELOG-line check / metadata diff in PRs) or stay trusted;
   tag-pinning instead of ride-main stays a considered exception only
   if incidents recur.
8. **aarch64 emulation on evo-x2 (open, 2026-09-25):** keep it (then
   the host config moves to module-managed `boot.binfmt.emulatedSystems`
   — self-healing tmpfiles, no hard store-path pins) or drop it
   (`extra-sandbox-paths` loses `/run/binfmt`; builds get simpler)?
   Either way, the current hand-rolled half-state breaks every sandboxed
   build after a reboot until root fixes it.
