# Ops Runbook

Operating procedures for a host running the `services.telephony` module.
Option names are stable identifiers — check `README.md` for their meaning
and defaults. All commands assume a root shell on the PBX host.

## Service inventory

| Unit                                      | What it does                                                                    |
| ----------------------------------------- | ------------------------------------------------------------------------------- |
| `freeswitch.service`                      | The PBX (sofia SIP profiles, dialplan, voicemail, recordings)                   |
| `nginx.service`                           | Webphone + `config.js` + `/recordings/` over HTTPS, `wss` proxy at `/sip`       |
| `coturn.service`                          | STUN/TURN relay for WebRTC media                                                |
| `telephony-tls.service`                   | `tls.mode = "self-signed"` only: renders the throwaway cert at boot             |
| `telephony-fs-cert.service` + `.path`     | `tls.mode = "acme"` only: provisions the cert to FreeSWITCH, re-runs on renewal |
| `telephony-web-config.service` + `.timer` | Renders `config.js` with fresh TURN credentials (daily, 48 h validity)          |
| `telephony-recordings-dir.service`        | Creates the shared recordings dir (`root:telephony 2770`) before FreeSWITCH     |
| `telephony-recordings-auth.service`       | Renders the `/recordings/` basic-auth htpasswd from the password file           |
| `telephony-recording-retention.timer`     | Daily prune of recordings past `recording.retentionDays`                        |
| `sshd.service`                            | Hardened keys-only SSH (nix-ssh-config input); demo VM: `ssh -p 2222 root@localhost` |

Everything is declarative: the recovery action for any broken oneshot is
usually "fix the option, `nixos-rebuild switch`", not manual surgery.

## fs_cli cheat-sheet

The event socket listens on `127.0.0.1:8021` only; the password is your
`services.telephony.eventSocketPassword`. Shell alias for the rest of this
page:

```console
fs_cli() { fs_cli -p "<eventSocketPassword>" -x "$1"; }
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
curl -fsS https://<domain>/config.js >/dev/null # web config served
curl -fsS https://<domain>/ >/dev/null          # webphone served
fs_cli "originate loopback/9196 &park()"        # dialplan executes
fs_cli "hupall"
```

The webphone itself is the end-to-end check: register extension 1000 and
dial `9196` (echo test) — you should hear yourself within a second.

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
