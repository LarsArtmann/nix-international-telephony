# AGENTS.md

Enduring context for AI sessions working in this repo.

## What this is

A NixOS telephony stack flake: FreeSWITCH PBX (via upstream
`services.freeswitch`) with a generated XML config, the webphone v2
service (a single Go binary from the `github:LarsArtmann/webphone` input,
wired through that repo's own `services.webphone` NixOS module) behind an
nginx TLS vhost (`wss://<host>/sip` -> TLS to sofia's `wss` transport on
loopback 7443), coturn for NAT, and an ITSP gateway option. **No
FusionPBX/FreePBX** —
they are not Nix-packageable sanely; we generate FreeSWITCH XML from Nix
instead. The example host also enables a hardened keys-only sshd from the
`nix-ssh-config` flake input (`services.ssh-server`, tracked `sshKeys`).

The webphone UI lives in its own repo since 2026-09-17 (v2 Go service
since 2026-09-18): `github:LarsArtmann/webphone` is a flake input whose
package defaults `services.telephony.webphone.package` AND whose
`nixosModules.default` (the `services.webphone` unit the stack's nginx
vhost proxies to) is imported by the `nixosModules.telephony` wrapper —
consumers importing the raw `modules/telephony` set must import BOTH the
package and the webphone module themselves; every VM suite imports the
wrapper via `tests/common.nix`. The UI's DOM/bundle contract — what
`tests/webphone.nix` and `tests/browser-e2e.py` assert — is documented in
that repo's AGENTS.md; changing markup or bundle flags requires
re-running those suites here.

Public repository: https://github.com/LarsArtmann/nix-international-telephony
(the local directory name predates it and keeps the historical `internatial`
typo — do not "fix" the directory, the GitHub name is the correct one).

Two example hosts: `hosts/pbx` is the throwaway demo VM (QEMU-shaped,
store-plaintext demo secrets by design); `hosts/pbx-prod`
(`nixosConfigurations.pbx-prod`) is the production template (`*File` secrets
only, ACME TLS, CDR, CHANGEME markers; its toplevel eval is forced by `nix
flake check`, and `checks.telephony-prod-boot` boot-proves the template
shape with stubbed secrets — real hardware awaits the first deployment). The zero-to-first-call deployment
runbook is `docs/deploy.md` — real deployments point at `.#pbx-prod`, never
`.#pbx`. sops-nix stays a docs-only recipe (owner decision: no flake input).

Operator procedures for a deployed host (fs_cli cheat-sheet, cert rotation,
gateway REG-state debugging) live in `docs/ops-runbook.md`. SIP-trunk/DID/
CPaaS provider evaluations (question framework, per-provider files with
verification-status tables, trunk decision) live in `docs/providers/` —
re-verify claims there before purchasing; prices and KYC rules drift.
The security hardening guide (exposed-surface inventory, layered
firewalls, SSH posture, going-live checklist) is `docs/security.md`.

## Commands

```console
nix flake check            # eval + build + lint + NixOS VM test (the CI gate)
nix fmt                    # treefmt: nixfmt (nix) + prettier (operator webroot)
nix build .#webphone       # webphone v2 Go binary (from the webphone input)
nix build .#freeswitch-sounds
nix run .#vm               # ephemeral demo VM (root autologin)
nix run .#initrd-audit -- --platform cloud <initrd-or-toplevel>  # driver gate
```

No Makefile, no justfile — everything through flake.nix.

BuildFlow's local default is `build_mode: fast` (.buildflow.yml); a full
pipeline must be explicit: `buildflow --build-mode full --max-time 60m`
(1h is the flag maximum; there is no config key, and the
`BUILDFLOW_MAX_TIME` env var is NOT honored — flag only, probed
2026-09-16). Without the cap the default 5-minute hard-kill lands
mid-`nix-build`, which realizes all VM-test checks — roughly 20-60 min
after any source change re-runs the suites. Fast gates before slow
gates: `nix fmt` + the cheap checks (treefmt/statix/deadnix/
`telephony-eval`) always precede a VM-realizing run.

Pre-commit hooks (nixfmt, statix, deadnix, gitleaks, changelog-headings,
scrub-check) are wired through git-hooks.nix: entering `nix develop`
installs them into `.git/hooks/pre-commit` and (re)generates
`.pre-commit-config.yaml` as a symlink into the store — that file is
gitignored, never commit it. `nix develop -c pre-commit run --all-files`
runs them without a shell.

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

Long-form lessons live in `docs/lessons/` — **freeswitch.md** (XML
escaping, dialplan anti-action, DTMF, mod_voicemail, sofia bind race),
**vm-testing.md** (clock jumps, initrd gaps, TCG, interactive driver,
eval-check patterns), **webrtc-browser.md** (SIP.js bundling, the
four-reason browser postmortem, Selenium traps), **operating.md**
(systemd hardening, SSH, ACME CAA, history surgery). Read the relevant
one before touching that area. The sharpest traps, inline:

- Nix-to-FreeSWITCH XML escaping: `''$''${var}` for a literal `$${var}`,
  `''${var}` for a literal `${var}`; `nix eval` prints `\$` — do not
  "fix" doubled dollars. Shell-level `''` inside Python testScript
  blocks TERMINATES the Nix indented string (use `""`/`'''`).
- Dialplan `anti-action` fires on CONDITION failure, never on bridge
  failure — bridge fallbacks are plain `<action>`s listed after `bridge`
  with `continue_on_fail=true` (SIP cause mappings in the lessons file).
- sofia binds `$${local_ip_v4}` and silently falls back to 127.0.0.1
  without a default route — our unit orders after network-online.target;
  VM tests derive listener IPs from `ss -ltn`, never assume localhost.
- The metal boot path IS CI-proven now (`checks.telephony-metal-boot`):
  kexec into the real pbx-prod kernel+initrd against a GPT
  `disk-main-root` behind a `virtio-scsi-pci` HBA (framework
  `diskInterface = "scsi"` is lsi53c895a — wrong bus). Mechanism
  lessons (virtiofsd fd cap, driver-shell death after kexec) in the
  lessons file; `checks.initrd-audit` remains the cheap eval-time gate.
- `PasswordAuthentication no` is NOT keys-only on NixOS (PAM answers
  keyboard-interactive); the nix-ssh-config module defaults close that
  door, tests/ssh.nix asserts it. `sshd -T` prints mixed-case directive
  names — compare case-insensitively.
- WebRTC via nginx→sofia needs exact-match `location = /sip`, TLS to
  sofia's wss-binding (a Via/transport mismatch is dropped SILENTLY),
  `apply-candidate-acl localnet.auto`, and runtime `${}` (not `$${}`) in
  the directory dial-string — four-reason postmortem in the lessons file.
- ACME failure ladder: `dig CAA <registered-domain>` FIRST (RFC 8659 —
  lego's error names the ZONE, not the host), then crt.sh (zero CT
  entries = issuance never succeeded anywhere), then the unit journal.
- Auto-commit daemon: it commits untracked files within minutes — scrub
  personal data BEFORE it does. `scripts/scrub-check.sh --history
  --strict` (patterns from gitignored `secrets/scrub-patterns.txt`,
  template: `secrets/scrub-patterns.example`) is the gate; run it before
  any history surgery and after every squash. Its `--history` pickaxe
  hits count REMOVALS too — a cleanup commit can look like a
  reintroduction; check the diff direction before treating a hit as a
  leak.
- nix registry pinning needs BOTH halves (ops.nix): `nix.registry.nixpkgs
  .to = pkgs.path` alone is not enough — nix eagerly fetches the global
  flake registry for any indirect ref and a failed fetch ABORTS lookup
  even when the local entry matches exactly; `nix.settings.flake-registry
  = ""` disables it. And never let a VM test hash a path flake
  (`nix flake metadata nixpkgs` walks the whole tree → virtiofsd fd
  exhaustion); assert via `nix registry list` + `test -f <path>/flake.nix`.
  Long-form: docs/lessons/operating.md, docs/lessons/vm-testing.md.
- BuildFlow noise is DECIDED (2026-09-16), not ambient: bandit is clean
  (inline `# nosec` at the ISSUE line — bandit attributes findings to
  the innermost call line, which ruff-format rewraps), vulture is clean
  (tests/vulture_whitelist.py holds load-bearing attribute references),
  todo-check clean, lychee reads `lychee.toml` (`docs/status/**`
  excluded — point-in-time snapshots), pytest-test skipped (VM suites
  own testing; no pytest exists here). The lint binaries buildflow
  orchestrates (ruff, bandit, mypy, dprint, prettier, vulnix) are pinned
  in `devShells.default` (2026-09-17): without them buildflow falls back
  to `nix run nixpkgs#X`, i.e. the moving registry revision instead of
  the flake's pinned nixpkgs — the same formatter version-skew class as
  the oxfmt/prettier war excluded in `.buildflow.yml`. Accepted
  remainder: nix-checker
  FOD-hash advisories (hashes are mandatory for fetchurl FODs) and
  nix-checker port-collision advisories (bare port numbers compared
  across unrelated mechanisms: QEMU guest forward vs fail2ban jail
  `port`, and the NAT suite's deliberate tcp+udp forward pair),
  flake-meta-checker mainProgram (data packages have no executable —
  blocked on upstream carve-out), bandit's own banner noise in its
  output, a cosmetic bandit "nosec encountered" warning, and the vulnix
  step crashing on NVD's retired 2.0 feed
  (`nvdcve-2.0-modified.json.gz` 404s since NVD ended the JSON feeds;
  vulnix 1.12.5 upstream is archived — observed 2026-09-23, repo-content
  independent, it crashes before scanning anything). Until BuildFlow
  gains a replacement scanner, treat a vulnix step failure here as
  noise, not a regression.
- The webphone input TRACKS UPSTREAM MAIN (no rev in flake.nix; only
  flake.lock pins revisions — owner decision 2026-09-18). That is safe
  since the 2026-09-18 v2 switchover: the stack imports upstream's
  `services.webphone` module (unit, user, hardening and JSON config
  rendering stay in sync with the binary), and `web.nix` owns only the
  nginx integration. Switchover invariants: the app serves
  `/config.js` itself and derives TURN REST credentials PER RESPONSE
  from `settings.turn_rest.secret` (inline) or
  `WEBPHONE_TURN_REST__SECRET` (file-sourced via
  `services.webphone.environmentFiles` + the
  `telephony-webphone-env` boot renderer) — the old nginx config.js
  shadow and its daily timer are GONE (2026-09-23), so never
  resurrect a restart-to-rotate pattern; the app's
  `/phone-api` proxy (session-injected Basic auth) replaced the old
  nginx `/phone-api/` location; `= /sip` still proxies WSS straight to
  sofia. The 2026-09-18 pin era existed because the static-site layout
  (`share/webphone` webRoot copy) vanished upstream — the deploy failure
  was `cp: cannot stat …/share/webphone/.`; do not resurrect that
  pattern.

## Conventions

- **One home per fact**: README sells, FEATURES inventories status,
  TODO_LIST holds open work, CHANGELOG logs history, DOMAIN_LANGUAGE
  defines vocabulary, this file keeps session-durable knowledge with
  long-form lessons in docs/lessons/. When a fact moves, delete it from
  its old home in the same commit — never maintain two copies. Done work
  is deleted from TODO_LIST, never struck through; `checks.docs-drift`
  (tests/drift_alarm.py) enforces this by failing when a TODO row
  duplicates a FULLY_FUNCTIONAL FEATURES row, cites ANY docs/status/ or
  docs/planning/ snapshot (archived or not) as evidence, or cites a
  repo-relative path missing from the tree (`--self-test` runs the
  negative tests for every arm). Status reports and plans under `docs/` are
  point-in-time snapshots: annotate, never rewrite — once every item in
  one carries an inline resolution marker (`~~…~~ done at` /
  `Won't implement` strikes or `→ done/open/…` routed arrows in markdown;
  `<del>` tags in the HTML-era snapshots), `git mv` it to
  `docs/status/archived/` or `docs/planning/archived/`.
- Cite stable names (option names, package/file names), not `file:line`
  — line numbers rot on every edit.
- Options: every `mkOption` has `type` + `description`; secret options come
  in plain/`*File` pairs with exactly-one-of assertions.
- Generated XML lives in `modules/freeswitch.nix` (pure function, no module
  system); `modules/telephony/` owns options and service wiring
  (`options.nix` interface, `pbx.nix` FreeSWITCH + secrets splice,
  `web.nix` nginx + webphone service wiring + config.js, `edge.nix` coturn
  - firewall, `shared.nix`
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
