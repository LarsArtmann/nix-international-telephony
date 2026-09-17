# Status Report — FS PBX Trial Live (session continuation)

Point-in-time snapshot: **2026-09-16 18:00 CEST**. Scope: this session's
continuation since the 16:43 report — the owner pivoted ("Let's just use
nemerald-voip/fspbx for now") and the session pivoted with it: provisioning a
local FS PBX trial appliance until login-verified. The earlier survey/UI
work (Go SIP ecosystem, layer map, LiveKit verdict, console concept) was
reported at `docs/status/2026-09-16_16-43_sip-ecosystem-research-console-scope.md`
and is only referenced here.

Skill-format overrides (user-mandated, same as the 16:43 report): `.md`
instead of HTML, self-review folded in, no manual commit (daemon owns them).

## a) FULLY DONE

1. **FS PBX trial VM live and verified**: Debian 13 trixie cloud image,
   8 vCPU/8 GB KVM VM at `/var/tmp/fspbx-trial/`, driven entirely via
   cloud-init NoCloud seed + serial console (harness bans ssh/curl; every
   change = new `write_files` script + `instance-id` bump + reboot cycle).
2. **Installer understood from source before running** (verify-external-
   claims discipline): wrapper (98 lines) + install.sh (819 lines) read;
   FreeSWITCH v1.11 compiled from source inside; non-interactive on trixie
   (baked SignalWire token); no official container image exists (checked).
3. **Three real install blockers found and fixed**, each verified by rerun:
   - composer dies without `HOME` (nohup/cloud-init env) → export fix
   - **host dnsblockd poisons `checkip.amazonaws.com`**; the HTML block
     page was fed into a `sed` → "unterminated `s' command" writing`APP_URL`→ installer patch`EXTERNAL_IP="127.0.0.1"`
   - nonstandard-port URL generation: `.env` APP_URL/SESSION_DOMAIN set to
     `https://127.0.0.1:18443` / `127.0.0.1`, Laravel config cache cleared,
     php-fpm/nginx/supervisor restarted
4. **GUI verified end-to-end (not just "port answers")**: `/login` 200
   (Vue SPA), CSRF flow solved (XSRF cookie is URL-encoded; header needs the
   decoded value; login field is `user_email`), `POST /login` → 200
   `{"two_factor":false}` + session cookie, authenticated `GET /dashboard`
   → 200 (22 KB, dashboard/extensions markers).
5. **Superadmin access delivered**: seeder creates `fspbx@fspbx.com` with a
   random never-printed password; reset to a known trial password via a
   Laravel-bootstrap PHP script injected by cloud-init.
6. **Trial documented**: `docs/research/2026-09-16_fspbx-trial.md` (staged)
   — access, VM stop/restart/destroy commands, installer anatomy, all four
   traps, honest caveats (isolated appliance; DB-backed config inverts this
   repo's model; `/var/tmp` dies on host reboot).
7. Host hygiene respected: ports picked free (18080 busy → 18443), VM
   isolated to 127.0.0.1 forwards, repo untouched except docs.

## b) PARTIALLY DONE

1. **Trial evaluation itself**: GUI reachable and login works, but no → superseded 21:04 — extensions created, E2E calls + CDR proven via vmclient.py + bearer API
   feature has been exercised (no extension created, no SIP registration,
   no call made, no CDR screen checked). The VM answers "can we log in",
   not "is it good".
2. **SIP plane untested and unreachable**: no hostfwd for 5060/RTP — a → done 21:04 — hostfwd 15060 + RTP window; registration + INVITE/200/BYE proven
   host softphone cannot currently register against the trial.
3. **Root-path UX quirk remains** (cosmetic): `/` 302s to portless → open — cosmetic quirk; dies with the VM on the kill path (verdict row)
   `https://127.0.0.1/login`; workaround is bookmarking `/login`. My nginx
   `fastcgi_param HTTP_HOST` patch was a **no-op** (the param never existed
   — I sed-mutated before grepping); a real fix would ADD the param.
4. **Reconciliation with earlier session output**: the console-concept → done — owner verdict collapsed the console direction
   milestones (16:43 report f1-f14) are now implicitly on hold behind the
   fspbx trial; no doc states this yet (this report does, TODO_LIST doesn't).

## c) NOT STARTED

- Softphone registration / test call against the trial. → done 21:04
- GUI feature-coverage walkthrough vs this repo's FEATURES.md. → partial 21:04 — model/API proven; GUI click-through = verdict-row loose end
- Any TODO_LIST/ROADMAP harvest from either status report (owner gate). → done — harvested by the 19:05 plan + TODO_LIST
- qcow2 snapshot as known-good rollback point (state mutations so far were
  all small and documented, but a clean snapshot would still be prudent). → done 21:04 — pre-sip-wiring snapshot

## d) TOTALLY FUCKED UP (owned, with root causes)

1. **Three ghost-hunt VM cycles on the wrong layer.** After install, host
   probes returned `ECONNREFUSED`; I read it as "hostfwd broken" and spent
   diag1/diag2/di3 instrumenting the GUEST firewall (iptables policy DROP,
   fail2ban, an nftables theory — `nft` wasn't even installed). Ground
   truth was visible in the FIRST traceback: `http_error_302` — the GET had
   _succeeded_ and urllib silently followed a redirect to host port 443
   where nothing listens. A no-redirect fetch (or a raw socket connect,
   done far too late) would have closed this in one step. Guest INPUT
   counters eventually proved zero packets ever arrived — I kept theorizing
   past the data.
2. **No-op mutation**: sed-patched a `fastcgi_param HTTP_HOST $host` that
   didn't exist; grep-before-sed would have caught it. Violates the
   verify-before-mutating rule this repo lives by.
3. **Process-control fumbles**: killed the pidfile PID (the pre-daemonize
   parent) while the real VM kept the disk lock; `kill -9` unsupported by
   the shell builtin burned another attempt. Cost: two wasted relaunch
   cycles before the external-kill path.
4. **Foreseeable port trap walked into blind**: I chose the
   `EXTERNAL_IP=127.0.0.1` patch knowing APP_URL gets baked from it, but
   never asked "what do redirects do on a nonstandard port that
   unprivileged QEMU cannot bind (<1024)?" — the whole port fight was
   predictable at patch time.

## e) WHAT WE SHOULD IMPROVE (self-review answers)

- **Forgot**: snapshotting the qcow2 before mutating guest state; noting
  the trial's idle resource cost (8 GB/8 vCPU held); pre-wiring SIP
  hostfwd for actual product evaluation; curl-ban awareness (hit it fresh
  instead of remembering the banned list).
- **Stupid-we-do-anyway**: trusting a summarized errno over the full
  traceback; theorizing past instrumented counters; mutating configs to
  "fix" things that were never confirmed broken.
- **Did I lie**: no. All claims in the trial doc carry their verification
  method; unverified items are labeled.
- **Ghost systems / split brains**: none built; one _risk_ — two UI
  directions now coexist in docs (console concept vs fspbx trial) until
  the owner's verdict collapses one.
- **Removed something useful**: no.
- **Tests**: N/A (no repo code changed); the trial's "test" was the
  end-to-end login proof — the right bar for infra work.
- **Less stupid going forward**: (1) no-redirect/raw-socket probe FIRST on
  any HTTP-path mystery; (2) read the entire traceback, not the last
  line; (3) grep before sed, always; (4) snapshot VM state before
  mutating; (5) enumerate privileged-port/unprivileged-runtime constraints
  BEFORE choosing patched values.

## f) Next things (trial-focused first, then carried-over; not padded)

_Trial evaluation (gated on g2/g3):_

1. Owner clicks through the GUI — verdict: prod candidate vs evaluation-only → open — verdict sign-off row (owner clicks or one more headless pass)
2. Wire SIP access: hostfwd 5060 (+RTP range or a test-only narrow range) → done 21:04
3. Create a test extension in the GUI; register Linphone/MicroSIP from host → done 21:04 — via their own models
4. Make a real call (extension → echo/9196, extension → extension) → done 21:04 — answered + BYE proven; RTP blocked by slirp (sandbox artifact, documented)
5. Check CDR/voicemail/ring-group/IVR screens against this repo's FEATURES.md → partial — CDR proven via API; screens → verdict row
6. STIR/SHAKEN premium module — evaluate for DE outbound caller-ID trust → Won't-implement — trial closed
7. Device provisioning (Yealink/Snom) — relevant if desk phones return → Won't-implement — trial closed
8. Their fail2ban nginx jails + iptables scanner-drops — mine for ideas → open — ROADMAP theme 2 (fspbx steal-ideas bullet: their fail2ban/iptables posture)
   worth porting to `pbx-prod` posture
9. Proper root-redirect fix: ADD `fastcgi_param HTTP_HOST $http_host` → Won't-implement — trial closed; quirk documented
10. `qemu-img snapshot` the current known-good state → done 21:04

_Trial lifecycle:_

11. Move VM dir out of `/var/tmp` if it survives the week (host reboot kills it) → open — verdict row (only if kept)
12. Idle-cost control: stop VM when unused (command is in the trial doc) → open — verdict row (stop command documented in the trial doc)
13. If verdict = kill: destroy VM, archive the trial doc's lessons → open — verdict row (kill path)
14. If verdict = adopt: Hetzner Debian box plan + DID/trunk migration plan → Won't-implement — not adopting
    (docs/providers decision feeds this)
15. If adopt: decide this repo's fate (webphone/console around fspbx? → answered — stays NixOS-first
    docs-only? mothballed?) — big owner call

_Reconciliation & carried-over (from the 16:43 report, still open):_

16. Collapse the console-vs-fspbx UI direction in docs after the verdict → done — verdict collapsed it
17. TODO_LIST/ROADMAP harvest from BOTH status reports (pending owner gate) → done — 19:05 plan
18. Check nixpkgs (nixos-unstable) freeswitch pin vs upstream v1.11.3 → done — 1.11.1 pinned vs v1.11.3 upstream (verified 2026-09-17)
19. UI/GUI comparison section appended to the research docs → done — trial doc
20. `sipexer` into the devShell → open — ROADMAP theme 5 (devShell nicety)
21. Verify repo top-level LICENSE (cited unverified in d4 of last report) → done — MIT LICENSE verified present
22. Trace origin of pre-existing `flake.nix` + `tests/backup.nix` mods → done — session2's work, identified 18:32
23. `gofaxip` spike (fax posture) → open — plan §P16 (fax lane; gofaxip alternative)
24. `freeswitch_exporter` + Grafana observability spike → open — ROADMAP theme 4 (exporter spike)
25. AGENTS.md headroom migration (at cap) → done 16:35
26. Backups + alerting sink (existing TODO row) → done 18:00
27. Real-disk-boot VM test (existing TODO row) → done 18:00 — checks.telephony-metal-boot

## g) Questions for the owner (cannot be figured out from the repo)

1. **After you click through: is fspbx a prod candidate or → answered — close properly; verdict NixOS-first (sign-off pending, TODO_LIST blocked row)
   evaluation-only?** (Decides items 13-15 — teardown vs migration
   planning vs repo pivot.)
2. **Want SIP wired into the trial now** (hostfwd 5060/RTP) so you can → done 21:04
   register a softphone and make a real call as part of the evaluation?
3. **If fspbx wins for prod:** does this repo pivot to surrounding it → answered — stays NixOS-first; fspbx kept as feature reference
   (webphone/console/docs against a Debian appliance), or stay
   NixOS-first with fspbx as a separate machine?

— END OF REPORT. Waiting for instructions.
