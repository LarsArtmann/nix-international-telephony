# AGENTS.md

Enduring context for AI sessions working in this repo.

## What this is

A NixOS telephony stack flake: FreeSWITCH PBX (via upstream
`services.freeswitch`) with a generated XML config, a static SIP.js WebRTC
webphone behind nginx (`wss://<host>/sip` -> loopback `ws` transport on
5066), coturn for NAT, and an ITSP gateway option. **No FusionPBX/FreePBX** —
they are not Nix-packageable sanely; we generate FreeSWITCH XML from Nix
instead.

Public repository: https://github.com/LarsArtmann/nix-international-telephony
(the local directory name predates it and keeps the historical `internatial`
typo — do not "fix" the directory, the GitHub name is the correct one).

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
  doubled.
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
  no mod_verto in ours).
- `event_socket.conf.xml` is overridden to 127.0.0.1 with a configured
  password; `fs_cli -p <password> -x "<cmd>"` in tests/ops.
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

## Conventions

- **One home per fact**: README sells, FEATURES inventories status,
  TODO_LIST holds open work, CHANGELOG logs history, DOMAIN_LANGUAGE
  defines vocabulary, this file keeps session-durable knowledge. When a
  fact moves, delete it from its old home in the same commit — never
  maintain two copies. Done work is deleted from TODO_LIST, never struck
  through. Status reports and plans under `docs/` are point-in-time
  snapshots: annotate, never rewrite.
- Cite stable names (option names, package/file names), not `file:line`
  — line numbers rot on every edit.
- Options: every `mkOption` has `type` + `description`; secrets-related
  options must be set explicitly (assertions enforce).
- Generated XML lives in `modules/freeswitch.nix` (pure function, no module
  system); `modules/telephony.nix` owns options and service wiring.
- Domain vocabulary lives in `docs/DOMAIN_LANGUAGE.md`; feature status in
  `FEATURES.md`; next work in `TODO_LIST.md`.
- Tests assert real behaviour (`fs_cli` queries, an `originate loopback/9196`
  call through the dialplan, nginx/coturn ports), not just unit states.
