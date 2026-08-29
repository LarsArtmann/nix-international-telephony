# Ops Runbook

Operating procedures for a host running the `services.telephony` module.
Option names are stable identifiers — check `README.md` for their meaning
and defaults. All commands assume a root shell on the PBX host.

## Service inventory

| Unit                                      | What it does                                                                         |
| ----------------------------------------- | ------------------------------------------------------------------------------------ |
| `freeswitch.service`                      | The PBX (sofia SIP profiles, dialplan, voicemail, recordings)                        |
| `nginx.service`                           | Webphone + `config.js` + `/recordings/` over HTTPS, `wss` proxy at `/sip`            |
| `coturn.service`                          | STUN/TURN relay for WebRTC media                                                     |
| `telephony-tls.service`                   | `tls.mode = "self-signed"` only: renders the throwaway cert at boot                  |
| `telephony-fs-cert.service` + `.path`     | `tls.mode = "acme"` only: provisions the cert to FreeSWITCH, re-runs on renewal      |
| `telephony-web-config.service` + `.timer` | Renders `config.js` with fresh TURN credentials (daily, 48 h validity)               |
| `telephony-recordings-dir.service`        | Creates the shared recordings dir (`root:telephony 2770`) before FreeSWITCH          |
| `telephony-recordings-auth.service`       | Renders the `/recordings/` basic-auth htpasswd from the password file                |
| `telephony-recording-retention.timer`     | Daily prune of recordings past `recording.retentionDays`                             |
| `sshd.service`                            | Hardened keys-only SSH (nix-ssh-config input); demo VM: `ssh -p 2222 root@localhost` |

Everything is declarative: the recovery action for any broken oneshot is
usually "fix the option, `nixos-rebuild switch`", not manual surgery.

## fs_cli cheat-sheet

The event socket listens on `127.0.0.1:8021` only; the password is your
`services.telephony.eventSocketPassword`. On the production template (and
any `eventSocketPasswordFile` deployment) the password lives in a runtime
file — read it with `$(cat …)` so it never lands in your shell history.
Shell alias for the rest of this page:

```console
# eventSocketPasswordFile deployments (hosts/pbx-prod default):
fs_cli() { fs_cli -p "$(cat /run/secrets/telephony_event_socket)" -x "$1"; }
# plain eventSocketPassword deployments: inline it instead
# fs_cli() { fs_cli -p "<eventSocketPassword>" -x "$1"; }
```

Status and inventory:

```console
fs_cli "sofia status"                          # profiles + gateways overview
fs_cli "sofia status profile internal"         # bindings, TLS, context
fs_cli "sofia status profile internal reg"     # registered SIP devices
fs_cli "sofia status gateway <name>"           # ITSP trunk REG state
fs_cli "show channels"                         # active calls (0 total = idle)
fs_cli "show detailed_calls"                   # calls with codecs/addresses
fs_cli "status"                                # FS version, uptime, CPU
```

Live calls and users:

```console
fs_cli "show channels"
fs_cli "uuid_dump <uuid>"                      # one call, every variable
fs_cli "user_data 1000@<domain> param password"  # directory lookup
fs_cli "hupall"                                # hang up every call
fs_cli "originate loopback/9196 &park()"       # dialplan smoke test (echo)
```

Logging and tracing (all reset by a FreeSWITCH restart):

```console
fs_cli "console loglevel debug"                # verbose dialplan EXECUTE logs
fs_cli "console loglevel info"                 # back to normal
fs_cli "sofia global siptrace on"              # full SIP messages on console
fs_cli "sofia global siptrace off"
journalctl -u freeswitch -f                    # console output lands here
```

Profile and gateway maintenance:

```console
fs_cli "sofia profile internal restart"        # re-reads TLS material on 5061
fs_cli "sofia profile external rescan"         # re-reads gateway config
fs_cli "sofia profile internal flush_inbound_reg"  # drop stale registrations
fs_cli "reloadxml"                             # re-read the (immutable) XML
```

Note: the generated config lives in the Nix store and is read-only at
runtime — never edit it on disk; change the Nix options and rebuild.

## Health checks

One-liners for a monitoring script or a post-deploy gate (all must succeed):

```console
systemctl is-active freeswitch nginx coturn
fs_cli "sofia status profile internal" | grep -q "5060"
ss -ltn | grep -q ':5061'                       # SIP TLS listener
ss -ltn | grep -q ':7443'                       # sofia wss (nginx /sip proxies here)
curl -fsS https://<domain>/config.js >/dev/null # web config served
curl -fsS https://<domain>/ >/dev/null          # webphone served
fs_cli "originate loopback/9196 &park()"        # dialplan executes
fs_cli "hupall"
```

Listening ports — the canonical table (loopback-only listeners marked `lo`;
"module" = opened by `services.telephony.openFirewall`, so also allow it in
any hoster/VPS firewall):

| Port | Process | Purpose |
| ---- | ------- | ------------------------------------------------------------------- |
| 22 | sshd | operator SSH (hardened keys-only; not a telephony port — opened by the sshd module) |
| 80 | nginx | ACME HTTP-01 challenge + redirect to https (module, acme mode only) |
| 443 | nginx | webphone, `config.js`, `/recordings/`, `wss://<domain>/sip` proxy (module) |
| 5060 | sofia | internal SIP UDP/TCP (softphones) (module) |
| 5061 | sofia | internal SIP TLS (module) |
| 5080 | sofia | external profile: ITSP trunk (module; restrict with `allowedCidrs`!) |
| 7443 | sofia (`lo`) | internal wss — nginx terminates browser wss and re-origins TLS here |
| 8021 | freeswitch (`lo`) | event socket (fs_cli) |
| 3478 | coturn | STUN/TURN (module, with `turn.enable`) |
| 49160–49260 | coturn | TURN relay range (module, with `turn.enable`) |
| 16384–16584 | sofia | RTP media, `rtp.startPort`–`rtp.endPort` (~2 ports per leg; module) |

A dead webphone with working softphones is almost always the wss hop:
check `ss -ltn | grep 7443` and `journalctl -u nginx -u freeswitch | grep -i sip`.
FreeSWITCH silently drops SIP whose Via transport mismatches the connection
transport — the browser path only works end to end over wss.

The webphone itself is the end-to-end check: register extension 1000 and
dial `9196` (echo test) — you should hear yourself within a second.

## Monitoring

`services.telephony.monitoring.enable` runs a `telephony-health.service`
oneshot on a timer (`monitoring.intervalSec`, default 60 s). A failed
unit IS the alert — the journal line names the sick component:

- event socket unresponsive — FreeSWITCH is dead or wedged
- `profile internal/external is not RUNNING` — sofia lost a profile
- `gateway <name> is not REGED` — the ITSP registration is down
  (only gateways with `register = true`; disable the check while
  bringing a trunk up with `monitoring.requireGatewayReg = false`)

Point your notifier at the unit: `OnFailure=` of `telephony-health.service`,
a systemd unit monitor, or a journal shipper. Manual run:

```console
systemctl start telephony-health.service    # exit 0 = healthy
journalctl -u telephony-health -n 5         # what failed, if it did
```

The check talks to the event socket over loopback only (the unit's
network access is firewall-scoped to localhost); the password comes
from `eventSocketPassword`/`eventSocketPasswordFile` like every other
consumer.

## SIP scanning and fail2ban

`services.telephony.fail2ban.enable` wires a jail that watches
FreeSWITCH's log file (`/var/lib/private/freeswitch/log/freeswitch.log` (the host-visible path of the DynamicUser state dir)) for
the source-verified auth-failure line
(`SIP auth failure (REGISTER|INVITE) ... from ip X` — emitted only
because the generated profile sets `log-auth-failures=true`) and bans
repeat sources (defaults: 5 failures / 10 min → 10 min ban; tune
`fail2ban.maxretry/findtime/bantime`). Inspect it live:

```console
fail2ban-client status freeswitch-sip    # jail state + banned list
fail2ban-client set freeswitch-sip unbanip <ip>
```

Honest posture — what fail2ban does NOT do here:

- **Digest auth is the real gate.** A banned-or-not scanner cannot place
  calls or register without valid credentials; the jail only cuts the
  noise (log volume, CPU per challenge) and slows credential stuffing.
- The filter counts only *failures*; the normal first-REGISTER
  `SIP auth challenge` line is deliberately not matched, so healthy
  phones never accumulate strikes.
- The jail tails the log FILE, not the journal — after startup
  FreeSWITCH's console logger detaches and post-startup lines (like
  the auth failures) never reach the journal. If you rotate or move
  the log, keep the jail's `logpath` in sync.
- Lockout risk is real: an operator mis-typing a password 5× gets
  banned; unban with the command above.

## Probing the wss path with wsprobe.py

When the webphone is dead but ports answer, the decisive tool is
[`tests/wsprobe.py`](../tests/wsprobe.py) in the repository: a stdlib-only
client that performs the full WebSocket handshake and sends hand-rolled
REGISTER frames by hand, printing everything that comes back. It isolates
the exact layer that fails without a browser in the loop.

Copy it to the host, adapt the constants, run with the bare python3:

```console
# on the PBX host, as root
sed 's/pbx\.test/<your-domain>/g' tests/wsprobe.py > /tmp/wsprobe.py
python3 /tmp/wsprobe.py            # probes both targets below
python3 /tmp/wsprobe.py direct     # only sofia's wss listener, 127.0.0.1:7443
python3 /tmp/wsprobe.py proxied    # only the nginx https/wss hop, 127.0.0.1:443
```

Reading the output, per target:

| Line                        | Healthy                        | Meaning when it is not                                       |
| --------------------------- | ------------------------------ | ------------------------------------------------------------ |
| `handshake: 'HTTP/1.1 101'` | Upgrade accepted               | 4xx/5xx: nginx location or upstream wrong; `<os error>`: TLS/port dead |
| `after-register-WSS: …401`  | REGISTER reached sofia (digest challenge follows) | Nothing/timeout: Via-transport drop or the proxy ate the frame |
| `after-register-WS: …`      | Mirror control: may be dropped silently | If WS answers like WSS does, transport enforcement is OFF somewhere |
| `after-ping: …PONG`         | ws read loop alive             | No PONG: the connection's read loop is dead, not just SIP |

The decisive pattern: `after-register-WSS` shows a `401` challenge (good —
the REGISTER reached sofia; the browser only needs to answer it with
credentials) while `after-register-WS` stays silent (FreeSWITCH enforcing
the Via/connection transport match, as it must). The reverse — WSS silent —
is the smoking gun for the classic proxy misconfiguration (a plain-ws hop
in front of a wss transport).

## Webphone failure playbook

The browser E2E suite (`legacyPackages.telephony-browser`) built this
decision tree from real failures; work it top to bottom:

1. **Page does not load / blank** — `curl -kI https://<domain>/`:
   404/502 → nginx vhost/root wrong; certificate error →
   `tls.mode` wiring (self-signed: `telephony-tls.service` ran?).
2. **`/sip.min.js` 404s or answers something odd** — the bundle must be
   served by nginx, never proxied: the `= /sip` location must be an
   EXACT match (`location /sip` captures `/sip.min.js` and forwards the
   bundle to sofia, which answers 400 — this ate a whole session once).
3. **Login spins, never registers** — run wsprobe (above). If WSS is
   dropped silently, fix the proxy hop (TLS upstream to 7443); if the
   handshake fails, fix nginx; if 401 never arrives at sofia
   (`journalctl -u freeswitch | grep REGISTER` + `sofia global siptrace
   on`), the credentials/splice path is broken: check
   `grep '@TELEPHONY_' /var/lib/freeswitch/conf/directory/default.xml`
   (must be EMPTY — placeholders already substituted).
4. **Registers, call fails instantly** — `fs_cli "show channels"` while
   dialing: no channel → INVITE rejected before the dialplan (candidate
   ACL: `apply-candidate-acl localnet.auto` must be on the internal
   profile); channel appears then dies → dialplan (see gateway table
   above for 603/503/404 meanings).
5. **Call connects, no audio** — one-way media: TURN allocation failing
   (`curl -fsS https://<domain>/config.js` must carry a TURN entry with a
   FUTURE-looking expiry username) or the RTP port range firewalled.
6. **Browser-side evidence** — open the page with devtools: console
   errors (CSP violations point at the vhost header), the Network tab's
   `wss://<domain>/sip` frame list (steady REGISTER re-sends without 401
   = frames eaten upstream), and `window.PBX_CONFIG` in the console
   (must carry the domain and TURN servers — else `/config.js` failed to
   load). The E2E suite's automated dumps replicate exactly these views
   (console, webphone event log, chromedriver log, raw WS probe) — when
   filing an issue, attach what `nix build -L
   .#legacyPackages.x86_64-linux.telephony-browser` printed; it usually
   contains the answer already.

## TLS certificate rotation

`tls.mode` decides the flow:

**`self-signed` (default, labs):** `telephony-tls.service` renders
`/var/lib/telephony/tls/{cert,key}.pem` at boot. To rotate:

```console
rm /var/lib/telephony/tls/cert.pem /var/lib/telephony/tls/key.pem
systemctl restart telephony-tls.service nginx.service
```

Browsers will re-warn on the new cert — expected.

**`manual`:** you own renewal (e.g. `security.acme` or an external process
writing `tls.certificate`/`tls.key`). Point those options at the renewed
files and `nixos-rebuild switch`; nginx reloads, and FreeSWITCH's 5061
picks the files up on the next `sofia profile internal restart`.

**`acme`:** fully automatic. `security.acme` renews
`/var/lib/acme/<domain>/`; the `telephony-fs-cert.path` unit watches the
cert file and triggers `telephony-fs-cert.service`, which re-renders
`/var/lib/freeswitch/tls-certs/{agent,cafile}.pem` and restarts the
internal profile so SIP TLS serves the new material. Verify a rotation
landed:

```console
systemctl status telephony-fs-cert.service
openssl x509 -noout -dates -in /var/lib/freeswitch/tls-certs/agent.pem
journalctl -u telephony-fs-cert.service --since today
```

If the path unit ever misses a renewal, `systemctl start
telephony-fs-cert.service` re-provisions on demand.

## Gateway (ITSP trunk) debugging

The generated gateways are named after their `services.telephony.gateways`
keys. Live state per gateway:

```console
fs_cli "sofia status gateway <name>"
```

The `State:` line cycles through FreeSWITCH's REG state machine:

| State       | Meaning                                                       | Action                                   |
| ----------- | ------------------------------------------------------------- | ---------------------------------------- |
| `REGED`     | Registered with the provider — trunk is up                    | None                                     |
| `TRYING`    | REGISTER sent, waiting for the answer                         | Wait; check siptrace if it persists      |
| `FAILED`    | REGISTER rejected (usually auth: wrong username/password)     | Check credentials, then `rescan` (below) |
| `FAIL_WAIT` | Backing off after failures                                    | Same as FAILED                           |
| `NOREG`     | Gateway configured without registration (peer-to-peer trunks) | Expected for `register: false` providers |
| `NOAVAIL`   | Proxy not resolving/reachable                                 | Check DNS/routing to the proxy address   |

After changing gateway options and rebuilding:

```console
fs_cli "sofia profile external rescan"          # picks up new gateways
```

For live signalling evidence:

```console
fs_cli "sofia global siptrace on"
journalctl -u freeswitch -f                     # watch REGISTER/INVITE flows
fs_cli "sofia global siptrace off"
```

Outbound calls traverse gateways in ascending `priority` with serial
failover; with **no** gateway configured, E.164 numbers answer `503`
(deliberate). Inbound calls from the provider arrive on the `external`
profile (port 5080) — restrict who may hit it with
`gateways.<name>.allowedCidrs` (SIP ACL) and
`firewall.restrictExternalTo` (firewall); unknown DIDs answer `404`.

Common failure modes:

- **Outbound 603 immediately**: the calling extension lacks
  `allowInternational` (toll_allow) — by design.
- **Outbound 503**: no gateway reachable — check `State:` above.
- **Inbound calls never arrive**: provider's source IPs not in
  `allowedCidrs`, or firewall drops 5080 — check
  `journalctl -u freeswitch | grep -i invite`.
- **One-way/no audio**: RTP ports (`rtp.startPort`–`rtp.endPort`) not
  forwarded on NAT, or a wrong `natRtpAddress` advertisement.

## Recordings

- Files: `/var/lib/telephony/recordings/*.wav`, written by FreeSWITCH,
  served by nginx at `https://<domain>/recordings/` behind basic auth
  (user `recording.serve.basicAuthUser`, password from
  `recording.serve.basicAuthPasswordFile`).
- Rotate the password: change the file's contents (or path), rebuild —
  `telephony-recordings-auth.service` re-renders the htpasswd before
  nginx starts.
- Retention: `telephony-recording-retention.timer` runs daily (Persistent)
  and deletes files older than `recording.retentionDays`; run it on
  demand with `systemctl start telephony-recording-retention.service`.
- The directory is setgid (`root:telephony`, mode 2770): files stay
  group-readable by nginx through the `telephony` group — never chmod it
  wider.

## TURN credentials

`config.js` carries REST-derived TURN credentials (valid 48 h, re-rendered
daily by `telephony-web-config.timer`). Rotating `turn.authSecret` revokes
every served credential at once; clients pick up fresh ones on their next
page load. Verify the currently served pair:

```console
curl -fsS https://<domain>/config.js
```

## Emergency actions

- **Stop all telephony**: `systemctl stop freeswitch nginx coturn`.
- **Cut PSTN outbound only**: set the gateways' `password` wrong on
  purpose is hacky — better: remove/comment the `gateways` attrset and
  rebuild (E.164 then answers 503), or stop the provider-side trunk.
- **Drop a runaway call**: `fs_cli "show channels"` then
  `fs_cli "uuid_kill <uuid>"`, or `fs_cli "hupall"` for everything.
- **Full reset of runtime state** (voicemail, CDRs, stale registrations):
  stop FreeSWITCH and clear its private state directory
  `/var/lib/freeswitch/` (voicemail boxes and CDRs live there) —
  recordings are NOT under that path and survive.

## Backups

What is worth backing up on a deployed host (everything else — system,
services, dialplan — is declarative in the flake and rebuilds itself):

| Data                             | Host path (as seen by root)                                | Notes                                              |
| -------------------------------- | ---------------------------------------------------------- | -------------------------------------------------- |
| Call recordings                  | `/var/lib/telephony/recordings/*.wav`                      | personal data; retention timer may prune it       |
| Voicemail boxes (audio + prefs)  | `/var/lib/private/freeswitch/storage/voicemail/`           | DynamicUser StateDirectory namespace — see note    |
| Voicemail index DB               | `/var/lib/private/freeswitch/db/voicemail_default.db`      | message list/envelopes; restore WITH the wavs      |
| CDRs                             | `/var/lib/private/freeswitch/cdr-csv/Master.csv`           | append-only billing/history log                    |

Note: `freeswitch` runs as a `DynamicUser`, so its state lives under
`/var/lib/private/freeswitch/` on the host filesystem (inside the unit's
namespace it is `/var/lib/freeswitch`; `/var/lib/freeswitch` on the host
is a symlink that `find`/`tar` do not follow — back up the `private`
path or use `tar -h`).

Example nightly restic backup (operator-owned config, deliberately not a
module option — pick your own repository/retention):

```nix
services.restic.backups.telephony = {
  paths = [
    "/var/lib/telephony/recordings"
    "/var/lib/private/freeswitch/storage/voicemail"
    "/var/lib/private/freeswitch/db/voicemail_default.db"
    "/var/lib/private/freeswitch/cdr-csv"
  ];
  repository = "sftp:backup@storage:/srv/backups/pbx";
  # passwordFile / environmentFile per restic.nix docs; prune as desired
  timerConfig = { OnCalendar = "daily"; Persistent = true; };
};
```

`services.restic.backups` comes from the `restic` NixOS module (enabled
implicitly by defining a backup); an rsync timer over SSH works equally
well for small setups.

### Restore drill

1. Restore the directories to a staging area on the PBX host
   (`restic restore latest --target /tmp/restore`).
2. Stop consumers: `systemctl stop freeswitch`.
3. Move the data back WITH ownership intact — the files must stay
   writable by the DynamicUser (copy as root, keep 0600-ish modes):
   `cp -a /tmp/restore/var/lib/private/freeswitch/storage/voicemail/. /var/lib/private/freeswitch/storage/voicemail/`
   (repeat for `db/voicemail_default.db`, `cdr-csv/`, and
   `/var/lib/telephony/recordings` — that one is group `telephony`,
   mode 2770 dir).
4. `systemctl start freeswitch`, then verify: dial `*98`, play a
   restored message; `tail /var/lib/private/freeswitch/cdr-csv/Master.csv`.
5. If the voicemail DB and wavs disagree (restored one without the
   other), messages may not list: restore both from the SAME snapshot.
