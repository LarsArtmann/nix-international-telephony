# AGENTS.md

Enduring context for AI sessions working in this repo.

## What this is

A NixOS telephony stack flake: FreeSWITCH PBX (via upstream
`services.freeswitch`) with a generated XML config, a static SIP.js WebRTC
webphone behind nginx (`wss://<host>/sip` -> loopback `ws` transport on
5066), coturn for NAT, and an ITSP gateway option. **No FusionPBX/FreePBX** —
they are not Nix-packageable sanely; we generate FreeSWITCH XML from Nix
instead.

## Commands

```console
nix flake check            # eval + build + lint + NixOS VM test (the CI gate)
nix fmt                    # treefmt: nixfmt (nix) + prettier (webphone assets)
nix build .#webphone       # static webphone derivation
nix build .#freeswitch-sounds
nix run .#vm               # ephemeral demo VM (root autologin)
```

No Makefile, no justfile — everything through flake.nix.

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
  packages/webphone/default.nix).
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

## Conventions

- Options: every `mkOption` has `type` + `description`; secrets-related
  options must be set explicitly (assertions enforce).
- Generated XML lives in `modules/freeswitch.nix` (pure function, no module
  system); `modules/telephony.nix` owns options and service wiring.
- Tests assert real behaviour (`fs_cli` queries, an `originate loopback/9196`
  call through the dialplan, nginx/coturn ports), not just unit states.
