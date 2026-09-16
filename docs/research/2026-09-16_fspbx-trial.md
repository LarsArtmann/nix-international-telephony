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
  + session cookie; authenticated `GET /dashboard` → 200 (22 KB, dashboard
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

## Hard-won traps (each cost one install cycle)

1. **composer dies without HOME** — running the installer from cloud-init
   `nohup` strips the environment; `export HOME=/root COMPOSER_HOME=...`
   fixed it ("The HOME or COMPOSER_HOME environment variable must be set").
2. **Host dnsblockd poisons `checkip.amazonaws.com`** — the installer stores
   the HTML block page in `EXTERNAL_IP` and feeds it to `sed -i "s|...|...|"`
   → "unterminated `s' command" while writing `APP_URL` to `.env`. Fixed by
   patching the installer to `EXTERNAL_IP="127.0.0.1"` before running.
3. **Serving on a nonstandard host port fights the app**: APP_URL and the
   root `/` redirect drop the port (`https://127.0.0.1/login` from
   `https://127.0.0.1:18443/`) — nginx never passes `HTTP_HOST` with a
   port. Host-side `127.0.0.1:443` forward is impossible (QEMU runs
   unprivileged; CAP_NET_BIND_SERVICE). Workaround: use `/login` directly;
   the Vue SPA routes client-side from there, all API calls stay on the
   origin port. `.env` was set to `APP_URL=https://127.0.0.1:18443`,
   `SESSION_DOMAIN=127.0.0.1`, config cache cleared.
4. **urllib follows redirects silently** — `ECONNREFUSED` on a healthy
   hostfwd was actually the *followed* redirect to host port 443, not the
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
