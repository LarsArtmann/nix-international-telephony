# FS PBX Trial VM (nemerald-voip/fspbx)

Point-in-time: **2026-09-16**. Owner decision: "Let's just use
nemerald-voip/fspbx for now" — this stands up a **local throwaway trial** of
FS PBX to evaluate the GUI. It shares **nothing** with this repo's NixOS
stack: the VM runs its own FreeSWITCH, Postgres, nginx, and PHP inside.

## Access (while the VM runs)

- URL: **https://127.0.0.1:18443/login** (self-signed cert; bookmark
  `/login` — see quirks)
- Login: `fspbx@fspbx.com` / `FspbxTrial!2026` (superadmin; the installer
  generates a random password, we reset it via Laravel bootstrap)
- Verified end-to-end 2026-09-16: `POST /login` → 200 `{"two_factor":false}`
  - session cookie; authenticated `GET /dashboard` → 200 (22 KB, dashboard
    content); guest redirect behavior correct.

## VM management (host)

```console
# status
ps -p "$(cat /var/tmp/fspbx-trial/qemu.pid)"
# stop (nothing is persistent across a reboot of the HOST: /var/tmp!)
pkill -9 -f "disk.qcow2"
# restart later (disk state persists in /var/tmp/fspbx-trial/disk.qcow2)
cd /var/tmp/fspbx-trial && nix shell nixpkgs#qemu -c qemu-system-x86_64 \
  -enable-kvm -cpu host -m 8192 -smp 8 \
  -drive file=disk.qcow2,if=virtio,format=qcow2 \
  -drive file=seed.iso,if=virtio,media=cdrom,readonly=on \
  -netdev user,id=n0,hostfwd=tcp:127.0.0.1:18443-:443 \
  -device virtio-net-pci,netdev=n0 \
  -display none -daemonize -serial file:console.log -pidfile qemu.pid
# destroy everything
pkill -9 -f "disk.qcow2" && trash /var/tmp/fspbx-trial
```

Shape: Debian 13 trixie genericcloud qcow2 + cloud-init NoCloud seed
(`user-data`/`meta-data` in the same dir), 8 vCPU/8 GB, 40 GB overlay over
the stock cloud image (`base.qcow2`). Serial console → `console.log` is the
only management channel (no ssh from the agent harness; cloud-init
`write_files`/`runcmd` script every change, bumping `instance-id` to re-run).

## What the installer does (verified from source, not marketing)

`install/install-fspbx.sh` (98 lines) clones the repo + unpacks the
`nemerald-voip/fusionpbx` release into `public/`, then `install/install.sh`
(819 lines) builds a full appliance: PHP 8.x + composer, nginx, **FreeSWITCH
v1.11 compiled from source** (trixie path embeds a base64 SignalWire token),
sounds, Postgres 17/18, Redis, Laravel Reverb + Horizon + CDR service under
supervisor, fail2ban (nginx-404/badbots/dos + sshd jails), FusionPBX-style
iptables ruleset, `fspbx:initial-seed` (admin.localhost domain + random-pass
superadmin). Takes ~10-30 min; fully non-interactive apart from the traps
below.

## SIP wiring round (2026-09-16 evening, cycles 009–017)

Extensions 1001/1002 were created **through fspbx's own model/service
classes** (Laravel CLI bootstrap from cloud-init, same pattern as
reset-pw.php): `Extensions::create` + `Voicemails::create` with domain
`admin.localhost`; SIP passwords set by us (`Trial1001!`/`Trial1002!`).
A Sanctum personal access token was minted the same way for the
`/api/v1/*` bearer API.

Proven end to end from the host (this repo's `tests/vmclient.py` +
`tests/sip.py` as the client, via `hostfwd` tcp/udp 127.0.0.1:15060→5060):

- REGISTER with HTTP-Digest auth → accepted
- INVITE 1001→1002 → **200 with SDP** (answered; voicemail fallback), BYE
- **CDR rows** for every test call via `GET /api/v1/domains/{uuid}/cdrs`
  (direction/destination/duration/hangup_cause) — the appliance's CDR
  pipeline captured all 6 calls including the 9196 dialplan miss
- Internal profile state readable via ESL (`Ext-RTP-IP`, `AGGRESSIVENAT`)
  after `SipProfileService::save()` — their service does xml_locate regen
  + `sofia profile rescan/restart` over ESL from the DB (config truth IS
  the DB; the `sip_profiles/*.xml.noload` files are inert by design)

**Not achieved: bidirectional RTP in the sandbox.** Five mechanisms tried
(DB `ext-rtp-ip`/`ext-sip-ip`, generated-file sed, service ESL sync,
`apply-nat-acl=rfc1918.auto`, `local-network-acl=loopback.auto`); sofia
kept advertising `c=IN IP4 10.0.2.15` (the guest IP, unroutable from the
host under slirp). Verdict: **slirp artifact, not an fspbx defect** — on a
public-IP deployment rtp-ip is reachable natively and this problem class
does not exist. RTP ports allocated from 16384 land inside the 40-port
hostfwd window, so only the advertised address was wrong.

Relaunch command differs from the management section: add
`hostfwd=tcp:127.0.0.1:15060-:5060,hostfwd=udp:127.0.0.1:15060-:5060` plus
`hostfwd=udp:127.0.0.1:16384..16423-:same` (one entry per port; QEMU
hostfwd has no ranges). Known-good disk snapshot: `pre-sip-wiring`
(`qemu-img snapshot -l disk.qcow2`). Guest RTP range is FS-default
16384-32768 (switch.conf.xml is a stub; narrowing was not needed since
allocation starts at 16384). GUI/API state: extensions + voicemail boxes +
NAT profile settings live in Postgres; `meta-data` instance-id 017.

Fax/SMS apps: **present** in the fork (`app/fax`, `app/fax_queue`,
`app/sms`; API routes FaxesController/FaxInbox/FaxSent) — **untested**:
needs a T.38-capable trunk, out of trial scope.

## License (verified 2026-09-16, from source files via GitHub API)

- **fspbx itself: Apache-2.0** — canonical 201-line `LICENSE` at the repo
  root. Verified from the file text, not just GitHub's auto-detection.
- The GUI it deploys is **not** fspbx code: the installer unpacks a
  `nemerald-voip/fusionpbx` release into `public/` (fork of
  `fusionpbx/fusionpbx`, "Modified FusionPBX", v1.2.6 at trial time). That
  code is **MPL 1.1 via file headers** ("The Original Code is FusionPBX",
  Mark J Crane, 2008-2023) — verified on the fork's `login.php` and
  upstream's `index.php`. Neither fusionpbx repo has a standalone LICENSE
  file, so GitHub shows "no license"; the grant lives per file.
- Sampling caveat: classic FusionPBX files carry MPL 1.1 headers; new
  fspbx-integration files in the fork (e.g. the Laravel `index.php` front
  controller) carry no header at all. Same org publishes both repos
  (fspbx commits: "nemerald" <info@nemerald.com>; upstream: markjcrane).
- The readme pricing tables ($500/$1000 per month, 1-year commitment) are
  a paid **support membership**, not a software license — the installer
  ran end-to-end with no license key, payment, or gating step.
- Practical: internal/trial use has zero obligations. MPL 1.1 is weak
  file-level copyleft — redistributing modified MPL files requires keeping
  them MPL 1.1; combining with other licenses (the Apache-2.0 + MPL 1.1
  mix fspbx itself ships) is permitted.

## Hard-won traps (each cost one install cycle)

1. **composer dies without HOME** — running the installer from cloud-init
   `nohup` strips the environment; `export HOME=/root COMPOSER_HOME=...`
   fixed it ("The HOME or COMPOSER_HOME environment variable must be set").
2. **Host dnsblockd poisons `checkip.amazonaws.com`** — the installer stores
   the HTML block page in `EXTERNAL_IP` and feeds it to `sed -i "s|...|...|"`
   → "unterminated `s' command" while writing`APP_URL`to`.env`. Fixed by
   patching the installer to`EXTERNAL_IP="127.0.0.1"` before running.
3. **Serving on a nonstandard host port fights the app**: APP_URL and the
   root `/` redirect drop the port (`https://127.0.0.1/login` from
   `https://127.0.0.1:18443/`) — nginx never passes `HTTP_HOST` with a
   port. Host-side `127.0.0.1:443` forward is impossible (QEMU runs
   unprivileged; CAP_NET_BIND_SERVICE). Workaround: use `/login` directly;
   the Vue SPA routes client-side from there, all API calls stay on the
   origin port. `.env` was set to `APP_URL=https://127.0.0.1:18443`,
   `SESSION_DOMAIN=127.0.0.1`, config cache cleared.
4. **urllib follows redirects silently** — `ECONNREFUSED` on a healthy
   hostfwd was actually the _followed_ redirect to host port 443, not the
   forward. Diagnose with a no-redirect opener. (Also: Laravel's
   `XSRF-TOKEN` cookie is URL-encoded; the `X-XSRF-TOKEN` header needs the
   decoded value; login field is `user_email`.)

## Honest caveats

- This is an **isolated appliance trial**: separate FreeSWITCH (bound
  10.0.2.15:5060/5066/5080/7443, ESL 127.0.0.1:8021 inside the VM), separate
  everything. It does NOT integrate with `nixosConfigurations.pbx*`, the
  webphone, coturn, or the ITSP gateway config of this repo.
- Config truth inside the VM is the Postgres DB — the exact inversion of
  this repo's declarative model that the earlier survey warned about.
- Nothing here is backed up; `/var/tmp` dies with the host reboot. Treat as
  disposable.
- Firewall inside the VM: iptables INPUT policy DROP with explicit ACCEPTs
  (22/80/443/7443/5060-5091/RTP ranges) + fail2ban — sane defaults out of
  the box, worth noting as a good idea for our own prod posture.
