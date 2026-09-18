# Security hardening guide

How to make this stack safe to expose to the internet. The direction:
no plaintext secret ever lands in the world-readable Nix store, inbound
trust is pinned to the provider, and the stack tells you when it is
sick. This guide owns the *posture*; procedures live in
[`docs/ops-runbook.md`](ops-runbook.md), deployment in
[`docs/deploy.md`](deploy.md), secret rendering in
[`docs/secrets.md`](secrets.md).

## Exposed surfaces (port inventory)

What an internet-facing host of this stack actually listens on, who
needs each port, and where it is enforced:

| Port                  | Service                    | Who needs it                    | Enforced by                                            |
| --------------------- | -------------------------- | ------------------------------- | ------------------------------------------------------ |
| 443/tcp               | nginx: webphone, operator  | everyone (browsers)             | TLS + basic auth/SIP creds; nginx scanner jail         |
| 80/tcp                | ACME HTTP-01 only          | Let's Encrypt (acme mode only)  | opened by the module in `tls.mode = "acme"` only       |
| 5060/tcp+udp          | sofia internal profile     | your own SIP devices            | digest auth (`auth-calls` on)                          |
| 5061/tcp              | sofia internal, SIP-TLS    | your own SIP devices            | TLS + digest auth                                      |
| 5080/tcp+udp          | sofia external profile     | your ITSP **only**              | `firewall.restrictExternalTo` + `gateway.allowedCidrs` |
| 3478/udp (+tcp)       | coturn STUN/TURN           | webphone browsers behind NAT    | REST auth (ephemeral credentials)                      |
| 5349/tcp              | coturn turns/DTLS          | same, TLS flavour               | same (eval-verified wiring, see gaps below)            |
| 49160-49260/udp       | coturn relay range         | same                            | allocation requires REST creds                         |
| 16384-16584/udp       | FreeSWITCH RTP media       | whoever has a call up           | only useful with signalling; window enforced/tested    |
| 22/tcp                | sshd (nix-ssh-config)      | the operator machine(s)         | keys-only, pinned kex/ciphers (`tests/ssh.nix`)        |
| 127.0.0.1:7443, 8021, 8071 | sofia wss, event socket, operator API | nobody external | loopback-only bindings (8021 assert-tested)            |

Rules of thumb:

- **5080 is the port scanners love.** If you run an ITSP gateway, set
  BOTH `gateways.<name>.allowedCidrs` (SIP-layer ACL, rejects before the
  dialplan) AND `firewall.restrictExternalTo` (drops at the firewall).
  Neither is on by default because the module cannot know your
  provider's networks — see `hosts/pbx-prod/default.nix` for the paired
  example.
- **Nothing else needs to be reachable.** The operator window, the
  recordings browser and the phone API all ride the 443 vhost with their
  own credentials; sofia's wss transport hides behind the nginx proxy on
  loopback.

## Layer 1 — hoster firewall (Hetzner Cloud Firewall)

A cloud-level packet filter in front of the NixOS firewall buys
rate-limiting and survives NixOS-side mistakes (an accidental
`openFirewall`-widening rebuild, a mis-merged `nft` rule). Mirror the
inventory above as inbound rules; recommended additions:

- **5080/tcp+udp: restrict to the ITSP source CIDRs.** Providers
  publish them (Telnyx's are in `docs/providers/telnyx.md`); this is the
  same pinning `restrictExternalTo` does one layer down.
- **22/tcp: restrict to the operator's static IP(s)** if you have a
  stable one — this is the strongest single SSH improvement available
  and costs nothing to operate.
- **Do NOT filter** the coturn relay range or the RTP window more
  narrowly than the module already does: TURN allocations and call media
  land on arbitrary ports inside them.
- Hetzner firewalls are inbound-only and stateful; replies flow freely.

Ordering caution: apply the hoster firewall only AFTER
`docs/deploy.md` §5 verifies green from outside, and keep a Hetzner
console session open while you do — the classic own-goal is filtering
port 22 (or 80, breaking ACME renewal) and locking yourself out of the
box you just installed.

## Layer 2 — the NixOS firewall (module-owned)

`services.telephony.openFirewall` (default on) opens exactly the
inventory above through NixOS's nftables firewall; port 80 opens only in
acme mode, and 5080 stays open-to-all until you set
`firewall.restrictExternalTo`. Do not fight the module by manually
adding `networking.firewall.allowedTCPPorts` entries — widen at the
hoster layer instead, where the change is visible as infrastructure.

## Layer 3 — SIP-layer trust

- **Digest auth is the real gate.** The internal profile runs
  `auth-calls` + `auth-subscriptions` with per-extension credentials; a
  scanner (banned or not) cannot register or place calls without them.
- **IP-peering trunks:** inbound ITSP INVITEs are unauthenticated by
  SIP nature — that is exactly what `allowedCidrs` + `restrictExternalTo`
  pin down. With both set, non-listed sources are dropped twice.
- **fail2ban cuts the noise, it is not the gate**
  (`fail2ban.enable`): the SIP jail bans sources of repeated auth
  failures (5/10min → 10min by default), the nginx scanner jail
  (`fail2ban.nginxScanner.enable`, on with the webphone) bans bot-path
  probes from 443. Lockout risk is real — the unban commands live in the
  [runbook](ops-runbook.md#sip-scanning-and-fail2ban).

## TURN exposure

coturn is an intentional, credentialed open relay for your webphone
users behind NAT:

- Credentials are REST-style and **short-lived** (48 h validity,
  re-rendered into `config.js` at half-life) — a leaked `config.js`
  grants relay access for hours, not forever. The signing secret never
  needs to leave the host: use `turn.authSecretFile`.
- The relay range (49160-49260) is ~50 concurrent allocations — if you
  never expect that many TURN users, narrowing it in `services.turn` is
  free attack-surface reduction.
- `turn.tls` (turns:/DTLS on 5349) exists but is eval-verified only;
  prefer plain turn:/stun: until a runtime test covers it.
- TURN cannot be turned off entirely for real deployments: browsers
  behind symmetric NAT simply cannot complete WebRTC calls without it
  (`webphone` ships the ICE diagnostics panel to prove when it is
  missing).

## SSH posture

The demo VM's `authorizedKeys = all tracked sshKeys` + root login is
**demo convenience**; production wants the opposite defaults:

- **Keys-only is the module default** (nix-ssh-config v0.1.3):
  password auth AND PAM keyboard-interactive are off; `tests/ssh.nix`
  pins the effective `sshd -T` (ML-KEM hybrid kex first, AEAD-only
  ciphers, forwarding off, 300 s/2 ClientAlive keepalives).
- **Per-user keys, not a global list.** Authorize each operator's key on
  exactly their account (`services.ssh-server.authorizedKeys` +
  `allowUsers`), and put only the managing machine's key on prod:
  `hosts/pbx-prod` pins `allowUsers = [ "root" ]` for the documented
  `nixos-rebuild --target-host` lane — a laptop-key compromise then does
  not automatically mean PBX access.
- **Host keys persist** on the root disk (`/etc/ssh/ssh_host_*` survive
  rebuilds with the disko layout). Reinstalls rotate them by design —
  expect the client-side `REMOTE HOST IDENTIFICATION HAS CHANGED`
  prompt and use `ssh-keygen -R <host>`; consider adding the host keys
  to your backup paths if you rebuild aggressively.
- **Key rotation procedure** (say, a lost laptop):
  1. Generate/install the replacement key on the managing machine.
  2. Update `authorizedKeys` in your (private-flake) host config, rebuild
     and deploy while the old session still works.
  3. Verify the NEW key logs in and the old one is refused
     (`ssh -o IdentitiesOnly=yes -i ~/.ssh/old_key ...` must fail).
  4. `ssh-keygen -R` is not needed — the host key did not change.
- **Exposed 22 optional hardening:** the hoster firewall source-pinning
  above is the first choice; if SSH must stay world-reachable, an
  `sshd` fail2ban jail (NixOS's `services.fail2ban.jails.sshd` with
  `ignoreIP` for your operator addresses) is a reasonable second.
- **One `ssh-audit` triage pass** per deployment:
  `nix run nixpkgs#ssh-audit -- <host>` — expect the pinned posture
  (mlkem768x25519-sha256 first, no CBC/3DES, MACs AEAD-only); treat any
  (ecdh-sha2-nistp*)-only or MAC%- CBC finding as a config regression
  against `tests/ssh.nix`'s golden snapshot, not as a reason to hand-tune
  `services.openssh.settings`.

## Secrets

The invariant: **no plaintext secret in the store, ever.** Every
credential has a plain/`*File` pair with exactly-one-of asserted at eval
time; runtime splicing happens in the freeswitch unit from
LoadCredential files. Rendering strategies (sops-nix recipe, manual
provisioning) are [`docs/secrets.md`](secrets.md)'s single home.

## What the repo proves (and what it does not)

| Property                                   | Proven by                                    |
| ------------------------------------------ | -------------------------------------------- |
| Store purity of `*File` secrets            | `checks.telephony-secrets` (VM)              |
| SIP fail2ban jail bans repeat offenders    | `checks.telephony-fail2ban` (VM)             |
| nginx scanner jail bans bot-path probes    | `checks.telephony-fail2ban` (VM)             |
| Event socket 8021 loopback-only            | `checks.telephony-tls-turn` (VM)             |
| 5061 completes a real TLS handshake        | `checks.telephony-tls-turn` (VM)             |
| Manual TLS mode serves the operator's pair | `checks.telephony-tls-turn` (VM)             |
| RTP media stays inside the configured port window | `checks.telephony` (VM)               |
| wss transport contract (Via/WSS vs Via/WS) | `checks.telephony-webphone` (VM)             |
| SSH keys-only + pinned crypto posture      | `checks.telephony-ssh` (VM)                  |
| ACME wiring (incl. HTTP-01 port 80 gating) | `checks.telephony-eval` (eval-only)          |
| coturn turns:/DTLS listener                | eval-only (runtime gap, noted above)         |
| NAT advertisement behind real NAT          | untested (ROADMAP; two-NIC suite is planned) |

## Going-live checklist

1. `*File` secrets rendered per `docs/secrets.md`; nothing
   `CHANGEME`-shaped survives (`checks.telephony-prod-boot` asserts the
   template shape).
2. Gateway live → set `allowedCidrs` + `restrictExternalTo` to the
   provider's published CIDRs (both, not one).
3. `fail2ban.enable = true` (SIP + scanner jails).
4. `monitoring.enable` + `alerts.urlFile` so a sick PBX pages you
   (backup failures ride the same webhook).
5. `docs/deploy.md` §5 verification green from an external network.
6. Hoster firewall applied (port table above; keep console access).
7. `ssh-audit` pass; rotation procedure tested once.

Honest gaps after all of the above: STIR/SHAKEN attestation is a
provider property (check per `docs/providers/`), emergency calling is a
documented non-goal (README disclaimer), and the fail2ban jails rate
noise rather than seal doors.
