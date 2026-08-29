# AGENTS.md

Enduring context for AI sessions working in this repo.

## What this is

A NixOS telephony stack flake: FreeSWITCH PBX (via upstream
`services.freeswitch`) with a generated XML config, a static SIP.js WebRTC
webphone behind nginx (`wss://<host>/sip` -> TLS to sofia's `wss` transport
on loopback 7443), coturn for NAT, and an ITSP gateway option. **No
FusionPBX/FreePBX** —
they are not Nix-packageable sanely; we generate FreeSWITCH XML from Nix
instead. The example host also enables a hardened keys-only sshd from the
`nix-ssh-config` flake input (`services.ssh-server`, tracked `sshKeys`).

Public repository: https://github.com/LarsArtmann/nix-international-telephony
(the local directory name predates it and keeps the historical `internatial`
typo — do not "fix" the directory, the GitHub name is the correct one).

Two example hosts: `hosts/pbx` is the throwaway demo VM (QEMU-shaped,
store-plaintext demo secrets by design); `hosts/pbx-prod`
(`nixosConfigurations.pbx-prod`) is the production template (`*File` secrets
only, ACME TLS, CDR, CHANGEME markers; its toplevel eval is forced by `nix
flake check`, it never boots in CI). The zero-to-first-call deployment
runbook is `docs/deploy.md` — real deployments point at `.#pbx-prod`, never
`.#pbx`. sops-nix stays a docs-only recipe (owner decision: no flake input).

Operator procedures for a deployed host (fs_cli cheat-sheet, cert rotation,
gateway REG-state debugging) live in `docs/ops-runbook.md`. SIP-trunk/DID/
CPaaS provider evaluations (question framework, per-provider files with
verification-status tables, trunk decision) live in `docs/providers/` —
re-verify claims there before purchasing; prices and KYC rules drift.

## Commands

```console
nix flake check            # eval + build + lint + NixOS VM test (the CI gate)
nix fmt                    # treefmt: nixfmt (nix) + prettier (webphone assets)
nix build .#webphone       # static webphone derivation
nix build .#freeswitch-sounds
nix run .#vm               # ephemeral demo VM (root autologin)
```

No Makefile, no justfile — everything through flake.nix.

Pre-commit hooks (nixfmt, statix, deadnix, gitleaks) are wired through
git-hooks.nix: entering `nix develop` installs them into
`.git/hooks/pre-commit` and (re)generates `.pre-commit-config.yaml` as a
symlink into the store — that file is gitignored, never commit it.
`nix develop -c pre-commit run --all-files` runs them without a shell.

CI: GitHub Actions (`.github/workflows/ci.yml`) runs the same
`nix flake check` on `ubuntu-latest` (a udev rule opens `/dev/kvm` for the
NixOS VM test). Releases: update CHANGELOG.md, tag `vX.Y.Z`, then
`gh release create vX.Y.Z`.

## Stack conventions (mirrors SystemNix)

- **flake-parts** (`mkFlake { inherit inputs; }`): `flake = { nixosModules,
  nixosConfigurations }` at the top; `packages`/`checks`/`devShells`/`treefmt`
  in `perSystem`. Use `self'` inside perSystem, `self` only outside.
- **treefmt-nix** flakeModule provides `formatter` + `checks.format`.
- **statix + deadnix** as checks; `statix.toml` disables `repeated_keys`
  because `services` is deliberately split across mkIf blocks.
- After adding files, `git add` them: with a git repo, the flake source is the
  git tree — untracked files are invisible to `nix build/check` (this bit us:
  a stale cached source copy made statix.toml appear missing).

## Hard-won knowledge

- **Nix string escaping for FreeSWITCH XML**: in indented strings write
  `''$''${var}` for a literal `$${var}` (FS pre-processor variable) and
  `''${var}` for a literal `${var}` (channel variable). `nix eval` prints
  dollars escaped as `\$` — do not "fix" working code because output looks
  doubled. Same trap in Python `testScript` blocks: any shell-level `''`
  (e.g. `ssh-keygen -N ''`) TERMINATES the indented Nix string — use `""`
  or `'''` there, or you get a baffling "syntax error, unexpected '>'"
  pointing at unrelated later lines.
- **SIP.js/JsSIP npm tarballs ship no `dist/` browser bundle.** We fetch the
  sip.js tarball (0.21.2, zero runtime deps) and esbuild-bundle
  `lib/index.js --format=iife --global-name=SIP` (see
  packages/webphone/default.nix). esbuild's `--legal-comments=external`
  emits nothing (sip.js `lib/*.js` carry no license comment) — ship the
  tarball's `package/LICENSE.md` as `sip.min.js.LEGAL.txt` instead.
- **FreeSWITCH sounds URLs need the rate component**:
  `freeswitch-sounds-en-us-callie-8000-1.0.52.tar.gz` (the name without
  `-8000-` 404s). Music pack: `freeswitch-sounds-music-8000-1.0.52.tar.gz`.
- The upstream `services.freeswitch` module copies `${package}/share/
  freeswitch/conf/vanilla` and overlays `configDir`; our overrides must not
  rely on `X-PRE-PROCESS` includes of template subdirectories we replaced.
- `freeswitch` builds/substitutes from cache.nixos.org; VM tests are cheap.
- Module list loaded by our config is deliberately minimal and must match the
  modules compiled into nixpkgs' freeswitch (no mod_av, no mod_signalwire,
  no mod_verto in ours). The nixpkgs build ships `mod_spandsp` (the
  `rxfax`/`txfax`/`t38gateway` fax apps) but NOT the legacy `mod_fax` —
  any fax work starts from mod_spandsp (fax posture: docs/providers/).
- `event_socket.conf.xml` is overridden to 127.0.0.1 with a configured
  password; `fs_cli -p <password> -x "<cmd>"` in tests/ops.
- **SSH integration**: `nix-ssh-config` is consumed as a flake input
  (`nixpkgs.follows`, single nixpkgs in the closure); its module is wired
  into `nixosConfigurations.pbx` in flake.nix (where `inputs` are in
  scope), NOT in hosts/pbx. The demo host relaxes to
  `services.ssh-server.allowRootLogin = true` (documented demo
  convenience). **`PasswordAuthentication no` is NOT keys-only on NixOS**:
  the default `KbdInteractiveAuthentication yes` + `UsePAM` let PAM accept
  Unix account passwords over keyboard-interactive (matters on the demo VM
  where root has an initialPassword) — we set
  `extraSettings.KbdInteractiveAuthentication = false` in the flake
  wiring and assert `kbdinteractiveauthentication no` in tests/ssh.nix
  (upstream module defaults stay untouched). `sshd -T` prints canonical
  mixed-case directives (`PermitRootLogin`, `Macs`) — compare
  case-insensitively in tests. tests/ssh.nix receives the module as a
  function argument so the test file itself stays input-free.
- Vanilla `acl.conf.xml` `domains` list (default deny) is unused by us: our
  internal profile has no `apply-inbound-acl`, auth is digest (`auth-calls`).
  When `gateway.allowedCidrs` is set we emit our own `acl.conf.xml`
  (list `trusted-itsp`) and point the external profile's `apply-inbound-acl`
  at it.
- **Dialplan `anti-action` runs when the CONDITION fails, not when `bridge`
  fails.** Shipping anti-action voicemail fallbacks inside extension/ring-group
  entries made FreeSWITCH answer (200 OK + voicemail) every call whose number
  did not match that entry — E.164 denial paths and unknown numbers never
  reached their reject extensions. Found via VM-test siptrace + `console
  loglevel debug` EXECUTE lines. Correct pattern for bridge-failure fallback:
  plain `<action>`s listed after `bridge` with `continue_on_fail=true` and
  `hangup_after_bridge=true` (they only run when the bridge fails). Denial
  extensions use `hangup` with a mapped cause; observed SIP mappings:
  `call_rejected`→603, `normal_temporary_failure`→503,
  `unallocated_number`→404.
- **SIP auth challenge specifics for scripted clients** (tests/sip.py):
  REGISTER is challenged with 401 + `WWW-Authenticate`, INVITE with 407 +
  `Proxy-Authenticate`; answer with `Authorization` vs `Proxy-Authorization`
  accordingly. In the test VM sofia binds 5060/5061/5080 on 127.0.0.1.
- **VM-test journal gotcha:** sofia-channel dialplan `EXECUTE` lines for
  `sofia/internal/...` channels do NOT reach the VM journal (loopback
  channels' do). Grep `Processing <cid>-><dest>` INFO lines instead, or
  use `sofia global siptrace on` + `console loglevel debug` for evidence.
  Post-startup evidence in general (voicemail app lines, DTMF) is only in
  `/var/lib/freeswitch/log/freeswitch.log` — green suites grep the FILE.
- **FreeSWITCH never follows a BACKWARDS system-clock jump.** Its
  internal clock is monotonic-plus-offset; a `date -s` into the past is
  ignored indefinitely (probed live: 60s of `fs_cli -x 'strepoch'` /
  `eval ${strftime(...)}` polling kept the pre-jump wall time), so
  date-time dialplan conditions keep evaluating with the stale time and
  time-window tests route the wrong leg — this made
  `telephony-time-routing` fail deterministically on three independent
  runs after its original "green". Restarting the unit re-reads the wall
  clock, BUT CI runners saw the guest clock itself revert to host time
  between `date -s` and the restart. Final design in
  `tests/time-routing.nix`: one node per leg with a fixed QEMU RTC base
  (`virtualisation.qemu.options = [ "-rtc base=<iso-time>" ]`) plus a
  loud `date +%H` precondition assert — the guest boots at the wanted
  time and nothing can drag it back.
- **Sharing files between freeswitch and nginx (recordings pattern):** the
  nixpkgs freeswitch unit is `DynamicUser` with `StateDirectory=freeswitch`,
  so `/var/lib/freeswitch` is private to it. A shared dir needs: a
  pre-freeswitch oneshot `install -d -g telephony -m 2770` (setgid),
  `SupplementaryGroups=telephony` **and** `ReadWritePaths` on the freeswitch
  unit (DynamicUser namespacing makes everything but its StateDirectory
  read-only), and for nginx put the user in the group via
  `users.users.nginx.extraGroups` — nginx _workers_ call `initgroups()`,
  so systemd `SupplementaryGroups` on the unit is not enough. nginx
  auth_basic supports `{PLAIN}` htpasswd entries, so a runtime oneshot can
  render credentials with plain `printf` (no htpasswd tool in the closure).
- **freeswitch needs AF_NETLINK under `RestrictAddressFamilies`:** sofia's
  NAT/interface detection calls `getifaddrs`, which opens an AF_NETLINK
  socket; without it the first inbound INVITE creates a channel that never
  reaches the dialplan (silent stall — the VM test's echo INVITE catches
  it). `DynamicUser` already implies `ProtectSystem=strict`/`PrivateTmp`,
  so only NoNewPrivileges/ProtectHome/RAF add value there.
- **`ReadWritePaths` targets must exist before the unit starts** — create
  parent state dirs with a `systemd.tmpfiles.rules` entry (`d /var/lib/…
  0755 root root -`) so hardened oneshots can bind-mount them writable.
- **sofia binds `$${local_ip_v4}`, which silently falls back to `127.0.0.1`
  when no default route exists yet** (`switch_find_local_ip` UDP-connects
  toward `82.45.148.209` and keeps its loopback pre-fill on failure). A
  slow-network boot therefore yields a PBX bound to loopback only
  (unreachable-until-restart in production); our unit orders after
  `network-online.target`, and VM tests derive listener addresses from
  `ss -ltn 'sport = :<port>'` instead of assuming `localhost` (this race
  masqueraded as a "sofia profile-start wedge" for two sessions — the DIAG
  `ss` dump eventually showed 5060/5061/5080 bound on eth0). When a test
  dials the external profile while an ACL lists `127.0.0.1`, the scripted
  client must `--bind 127.0.0.1` explicitly (the source address follows
  the destination address otherwise).
- **sofia profiles up ≠ event socket ready**: mod_event_socket binds 8021
  late in startup; `fs_cli` right after the 5060 listener check raced it
  (`Error Connecting`). The shared `wait_for_freeswitch` helper now waits
  for a 8021 listener too.
- **WebRTC/browser stack — four stacked reasons browser calls failed**
  (all fixed, each verified by the browser E2E):
  1. nginx `location /sip` is a PREFIX match — it captured `/sip.min.js`
     and proxied the bundle to sofia (400). Exact-match `= /sip`; the
     webphone suite asserts a 200 bundle fetch as the regression guard.
  2. **FreeSWITCH drops SIP requests whose Via transport token mismatches
     the connection transport, silently** (no 4xx, no log at default
     level; only `siptrace` shows the recv). Browsers only speak `wss://`
     from https pages (Via/WSS), so the proxy hop MUST be TLS to sofia's
     `wss-binding` (7443) — a plain `ws-binding` eats every browser
     REGISTER. (A later A/B — browser suite green with the `ws-binding`
     removed — DISPROVED the early claim that a plain ws listener is
     needed for outbound legs: after the dial-string fix in item 4, sofia
     bridges to WS-registered contacts over wss alone; 5066 is gone.)
  3. Without `apply-candidate-acl`, sofia screens ICE candidates against
     `wan.auto`, which DENIES all private ranges — every LAN/lab browser
     (no srflx candidates) gets 488 INCOMPATIBLE_DESTINATION. Profile
     sets `apply-candidate-acl localnet.auto`.
  4. The directory `dial-string` template's `dialed_user`/`dialed_domain`
     are RUNTIME dial variables (single `${}`), not `$${}` pre-processor
     vars — over-escaping them breaks every `bridge(user/N)` with
     "No origination URL specified". TCP regs happened to work via a
     fallback; WS regs (with fs_path contacts) did not.
  - `tests/wsprobe.py` (stdlib RFC 6455 client, shipped into the browser
    test VM) probes the whole path by hand: handshake + REGISTER with
    Via/WSS vs Via/WS controls — the decisive tool for transport issues.
- **Eval-only regression checks (`tests/eval.nix` → `checks.telephony-eval`)**
  force `system.build.toplevel.drvPath` for all three `tls.mode` variants
  (needs boot fixtures: `fileSystems`/`grub`/`stateVersion` in
  `tests/tls-mode-host.nix`, else NixOS's own assertions fail) and grep the
  generated directory XML for the dial-string's single-dollar runtime
  vars. First run caught a real bug: `tls.mode = "acme"` had a hand-rolled
  `security.acme.certs` entry with NO challenge provider — security.acme's
  assertion kills the full eval. Correct wiring: delegate to the nginx
  vhost's `enableACME` (challenge location, group, reloads included).
- **Selenium/browser-test traps:** `.text` returns "" for elements inside
  hidden parents (read `textContent` via `execute_script` for the
  webphone's `#log`, which sits in the hidden-until-login phone view) and
  returns RENDERED text, so CSS `text-transform: uppercase` breaks
  case-sensitive substring waits. A bare `python3` on the VM PATH shadows
  a `python3.withPackages` interpreter — run E2E scripts through a
  `writeShellScriptBin` wrapper naming the exact interpreter
  (`writeShellScript` alone is a file and buildEnv-rejected in
  `systemPackages`). `environment.systemPackages` entries producing the
  same binary name collide nondeterministically. Keep E2E-script wait
  timeouts BELOW the testScript's marker timeouts so the script's own
  failure dumps land in the log before the driver aborts.
- **aarch64 CI on GitHub arm runners:** `ubuntu-24.04-arm` is free for
  public repos but exposes NO /dev/kvm (Azure arm VMs, no nested virt),
  so the job advertises `system-features = nixos-test benchmark
  big-parallel` and builds a KVM-feature-less test. The test driver's
  connect() retries the serial shell only 10×30s (FIXED, not configurable
  from testScript) — full VM suites never finish booting under TCG in
  that window; only the minimal `telephony-boot-tcg` suite fits.
- **The interactive test driver is the VM-state debugging superpower:**
  `nix build .#checks.x86_64-linux.<suite>.driverInteractive --no-link
  --print-out-paths`, write a probe script (plain `machine.succeed(...)`
  calls), then `<path>/bin/nixos-test-driver --test-script /tmp/probe.py
  --no-interactive`. Faster than a full suite rerun for "what does the
  VM actually look like" questions.
- **VM tests that set the clock MUST stop NTP first:**
  `systemctl stop systemd-timesyncd && timedatectl set-ntp false` before
  `date -s` — otherwise timesyncd snaps the clock back mid-test and
  time-window assertions flake mysteriously (cost a full suite run once).
- **`wait_for_freeswitch` (tests/common.nix) takes plain SECONDS** and
  builds the `datetime.timedelta`s itself; call sites passing
  `timedelta(...)` into it double-wrap and die at runtime with
  `TypeError: unsupported type for timedelta seconds component`. The
  test driver's own `wait_until_succeeds(timeout=...)` DOES take
  timedeltas. A suite can green in CI while its kwargs-path is broken
  if the kwargs are only used by a variant (TCG) that CI-x86 never ran.
- **DTMF from scripted clients must be RFC 4733 telephone-event RTP**
  (`RtpStream.send_digit` in tests/vmclient.py). sofia's ONLY
  dtmf-relay INFO parser looks for `Signal=` (equals) behind the
  off-by-default `extended-info-parsing` profile flag — "Signal: <d>"
  (colon) INFOs are 200-OK'd and silently dropped, so every
  Signal-colon digit in this repo's history was theater (the voicemail
  PIN legs passed vacuously on re-prompt phrase audio; the IVR suite
  never actually passed). Digits sent WHILE a phrase macro or prompt
  plays are eaten as its cancel input — send them after the collector
  starts (voicemail *98 asks for the MAILBOX ID first, then the PIN).
- **mod_dialplan_xml parses a whole extension BEFORE executing it**:
  nested conditions and action-data `${vars}` are evaluated at PARSE
  time, so routing on a variable set by play_and_get_digits in the same
  extension can never work. Runtime menus use mod_dptools' `ivr` app
  (registered name "ivr", NOT "menu") with menu definitions generated
  into ivr.conf.xml — digits there are config data, immune to the trap.
- **mod_voicemail emails** go through the core `mailer-app` param in
  switch.conf.xml (verified in switch_core.c), invoked as
  `/bin/cat <msg> | <app> -f <from> <args> <to>` with the full RFC 5322
  message on stdin — and `/bin/cat` DOES NOT EXIST on stock NixOS, so
  the module symlinks it via tmpfiles when `voicemail.mailerCommand` is
  set (without it the mailer silently receives an empty message).
  vm-mailto alone sends NOTHING — `vm-email-all-messages` is required
  (the generator emits both plus `vm-attach-file`; insert_db defaults
  to 1 so the local copy for *98 stays). A VM catch-all writes under
  /var/lib/freeswitch (StateDirectory, host-readable via
  /var/lib/private); NOT /tmp (PrivateTmp).

## Conventions

- **One home per fact**: README sells, FEATURES inventories status,
  TODO_LIST holds open work, CHANGELOG logs history, DOMAIN_LANGUAGE
  defines vocabulary, this file keeps session-durable knowledge. When a
  fact moves, delete it from its old home in the same commit — never
  maintain two copies. Done work is deleted from TODO_LIST, never struck
  through; `checks.docs-drift` (tests/drift_alarm.py) enforces this by
  failing when a TODO row duplicates a FULLY_FUNCTIONAL FEATURES row.
  Status reports and plans under `docs/` are point-in-time
  snapshots: annotate, never rewrite — once every item in one carries an
  inline resolution marker, `git mv` it to `docs/status/archived/` or
  `docs/planning/archived/`.
- Cite stable names (option names, package/file names), not `file:line`
  — line numbers rot on every edit.
- Options: every `mkOption` has `type` + `description`; secret options come
  in plain/`*File` pairs with exactly-one-of assertions.
- Generated XML lives in `modules/freeswitch.nix` (pure function, no module
  system); `modules/telephony/` owns options and service wiring
  (`options.nix` interface, `pbx.nix` FreeSWITCH + secrets splice,
  `web.nix` nginx + config.js, `edge.nix` coturn + firewall, `shared.nix`
  derived values as a plain function — sibling bindings inside its returned
  attrset are NOT in scope for each other; define cross-referencing values
  in the `let`).
- Domain vocabulary lives in `docs/DOMAIN_LANGUAGE.md`; feature status in
  `FEATURES.md`; next work in `TODO_LIST.md`.
- Tests assert real behaviour (`fs_cli` queries, an `originate loopback/9196`
  call through the dialplan, nginx/coturn ports), not just unit states.
  KVM-less TCG variants need `pkgs.testers.runNixOSTest` + `requiredFeatures`
  (legacy `nixosTest` rejects the argument); template scripts with
  `pkgs.replaceVars` (`substituteAll` is gone). The browser E2E lives in
  `legacyPackages.telephony-browser`, deliberately outside `checks`.
