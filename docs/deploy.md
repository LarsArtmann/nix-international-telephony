# Deploying for real

From zero server to a verified first call. The demo (`nix run .#vm`,
`hosts/pbx`) is deliberately throwaway: tmpfs root, root autologin,
plaintext demo secrets, QEMU port forwards. A real deployment uses the
production host template **`hosts/pbx-prod`** (`nixosConfigurations.pbx-prod`)
— file-based secrets only, ACME TLS, CDR, real disk/boot fixtures — plus
this runbook. Day-2 operations (fs_cli, cert rotation, gateway debugging)
live in [`ops-runbook.md`](ops-runbook.md).

Every `CHANGEME` marker in `hosts/pbx-prod/default.nix` corresponds to a
step below.

## 1. Prerequisites

| Need            | Notes                                                                                                                                    |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Server          | Any NixOS-capable x86_64 or aarch64 box; 1 vCPU / 2 GB is plenty for a small office. A VPS with a public IPv4 keeps the TLS story simple. |
| DNS             | `A` (and `AAAA`) record for your domain (e.g. `pbx.example.com`) pointing at the server. ACME needs ports 80 and 443 reachable from the internet. |
| Operator SSH key | `hosts/pbx-prod` authorizes the keys tracked in the [nix-ssh-config](https://github.com/LarsArtmann/nix-ssh-config) input (`sshKeys`). Swap in your own `authorizedKeys` if that is not you. |
| ITSP account    | Optional until you want PSTN calls: SIP username/password, proxy, one DID (your inbound number), and the provider's source IP ranges for the ACL. |
| Secrets         | 4 mandatory + 2 optional short random strings, generated in step 3.                                                                     |

Ports: the module opens everything the stack needs itself (see the
canonical listening-port table in
[`ops-runbook.md`](ops-runbook.md#health-checks)); the two things to double-check
in a hoster/VPS firewall are **TCP 22** (SSH — not a telephony port, but you
firewall yourself out without it) and, in `tls.mode = "acme"`, **TCP 80**
(ACME's HTTP-01 challenge — no 80, no certificate, dead webphone).

## 2. Configure the host

Edit `hosts/pbx-prod/default.nix` (or copy the directory and adjust the
flake wiring):

1. **Domain + email** — `services.telephony.domain`, the parent
   `networking.domain` and `tls.acmeEmail` (all `CHANGEME`).
   LAN-only deployment: drop the whole `tls` block instead —
   the default `self-signed` mode needs no DNS or open ports, at the cost of
   a browser warning.
2. **Disk + bootloader** — declared, not hand-rolled: `hosts/pbx-prod/disk.nix`
   (disko) describes the Hetzner cx22 shape (ext4 on `/dev/sda`, GPT + BIOS
   boot); UEFI hosts want an ESP + `boot.loader.systemd-boot` instead.
3. **Gateway** — uncomment `gateways.itsp` and fill it with your provider's
   values; set `allowedCidrs` plus `firewall.restrictExternalTo` to the
   provider's source networks so port 5080 is not world-open. Without a
   gateway, PSTN dialling answers 503 and nothing is wrong.
4. **Network** — DHCP is on by default; pin a static address if DNS and the
   ITSP ACLs will point at this host long-term.
5. **Behind NAT?** — set `services.telephony.natAddress` to the public IP.

## 3. Secrets

The template uses `*File` options exclusively: no credential lands in the
world-readable Nix store, and exactly-one-of plain/file is asserted at eval
time. The files it expects (all single-line):

| File (`secretsDir = /run/secrets`) | Option reading it                     |
| ---------------------------------- | ------------------------------------- |
| `telephony_event_socket`           | `eventSocketPasswordFile` (fs_cli)    |
| `telephony_ext_1000` / `_1001`     | `extensions.<n>.passwordFile`         |
| `telephony_turn`                   | `turn.authSecretFile` (coturn)        |
| `telephony_gw_itsp`                | `gateways.itsp.passwordFile`          |
| `telephony_recordings`             | `recording.serve.basicAuthPasswordFile` (only if enabled) |

Generate values, e.g. `nix shell nixpkgs#openssl -c openssl rand -hex 24`.

**Option A — sops-nix (recommended).** Follow the complete recipe in
[`secrets.md`](secrets.md): add `sops-nix` as an input, declare the
`telephony_*` secrets (remember `owner = "turnserver"` for
`telephony_turn`), and the default `secretsDir = "/run/secrets"` matches
where they render at activation.

**Option B — manual runtime files.** Change `secretsDir` in the template to
a persistent directory (`/run` is tmpfs and empties on reboot), then on the
target host before the first switch:

```console
install -d -m 700 /var/lib/telephony-secrets
install -m 600 /dev/null /var/lib/telephony-secrets/telephony_event_socket
printf '%s' "$(openssl rand -hex 24)" > /var/lib/telephony-secrets/telephony_event_socket
# …repeat for every file in the table above…
```

Without these files the telephony units fail fast at start (systemd
`LoadCredential`), which is the intended loud failure — no secret, no PBX.

## 4. Install

All three paths build the same `.#pbx-prod` flake output; pick one:

**Fresh server, from your workstation (nixos-anywhere):** create the VM
(e.g. `infra/hcloud.tf` — Terraform), then run

```console
nix run github:numtide/nixos-anywhere -- --flake .#pbx-prod --target-host root@<server-ip>
```

The disk layout is part of the flake (`hosts/pbx-prod/disk.nix`, executed
via disko), so the target only needs SSH. After the install the server's
host key changes — `ssh-keygen -R <server-ip>` before the next login.

**Fresh server, from a NixOS installer:** partition/mount per your
`fileSystems`, then `nixos-install --flake .#pbx-prod`. On first boot the
hardened sshd only accepts the configured keys — make sure you can
authenticate before you leave the console.

**Existing NixOS host:** deploy remotely and roll back the same way:

```console
nixos-rebuild test --flake .#pbx-prod --target-host root@<host>   # no boot entry
nixos-rebuild switch --flake .#pbx-prod --target-host root@<host> # activate + generations
```

## 5. Verify

Run the health-check block from
[`ops-runbook.md`](ops-runbook.md#health-checks) — in short, everything in
this list must pass:

```console
systemctl is-active freeswitch nginx coturn
fs_cli "sofia status"                        # internal + external RUNNING
fs_cli "sofia status gateway itsp"           # state REGED (with a gateway)
fs_cli "originate loopback/9196 &park()" && fs_cli "hupall"
curl -fsS https://<domain>/ >/dev/null       # real cert, no warning
```

(The `fs_cli` calls assume the runbook's shell alias; on this template the
password lives in a file — `fs_cli -p "$(cat /run/secrets/telephony_event_socket)" -x …`.)

Then the human checks:

- Webphone: log in as 1000, dial **9196** — echo within a second proves
  signaling, ICE/TURN and RTP end to end.
- Inbound: call your DID from a mobile phone; the ring group should ring.
- Recordings (if enabled): `https://<domain>/recordings/` answers 401
  without, and lists WAVs with, the basic-auth credentials.

If the webphone is dead but softphones work, it is almost always the wss
hop — see the hint under "Health checks" in the runbook.

## 6. Day-2

- Updates: `nixos-rebuild switch --flake .#pbx-prod --target-host root@<host>`;
  `test` before `switch` when nervous, `--rollback` when sorry. Old
  generations stay bootable.
- Certificates rotate themselves (ACME renewal re-provisions FreeSWITCH via
  `telephony-fs-cert.path`); manual modes are covered in the runbook.
- Everything is declarative: the fix for a broken unit is an option change
  and a rebuild, never editing files under the store.

## 7. Known gaps (honest list)

- **No emergency calling (911/112).** Keep a mobile phone around.
- No fail2ban/rate limiting yet — digest auth is the actual gate against
  SIP scanners (rotate secrets, keep `allowedCidrs` set) — see `ROADMAP.md`.
  Rotate `turn.authSecret` to evict all TURN users at once.
- Backups are a documented recipe, not a wired option: the target
  inventory (recordings, voicemail, CDRs) and a restic example live in
  [`ops-runbook.md`](ops-runbook.md#backups).
- Recording consent is a legal question, not a technical one
  (`recording.enable` defaults to true).
