# Operating lessons: systemd, SSH, ACME, deploy hygiene (long-form)

Moved verbatim from AGENTS.md 2026-09-16 to keep that file under its
line cap. AGENTS.md carries one-line pointers; the full stories live
here. Annotate, never rewrite — append new lessons at the bottom.

## Sharing files between freeswitch and nginx (recordings pattern)

The nixpkgs freeswitch unit is `DynamicUser` with
`StateDirectory=freeswitch`, so `/var/lib/freeswitch` is private to it.
A shared dir needs: a pre-freeswitch oneshot `install -d -g telephony
-m 2770` (setgid), `SupplementaryGroups=telephony` **and**
`ReadWritePaths` on the freeswitch unit (DynamicUser namespacing makes
everything but its StateDirectory read-only), and for nginx put the
user in the group via `users.users.nginx.extraGroups` — nginx
_workers_ call `initgroups()`, so systemd `SupplementaryGroups` on the
unit is not enough. nginx auth_basic supports `{PLAIN}` htpasswd
entries, so a runtime oneshot can render credentials with plain
`printf` (no htpasswd tool in the closure).

## freeswitch needs AF_NETLINK under RestrictAddressFamilies

Sofia's NAT/interface detection calls `getifaddrs`, which opens an
AF_NETLINK socket; without it the first inbound INVITE creates a
channel that never reaches the dialplan (silent stall — the VM test's
echo INVITE catches it). `DynamicUser` already implies
`ProtectSystem=strict`/`PrivateTmp`, so only
NoNewPrivileges/ProtectHome/RAF add value there.

## ReadWritePaths targets must exist before the unit starts

Create parent state dirs with a `systemd.tmpfiles.rules` entry
(`d /var/lib/… 0755 root root -`) so hardened oneshots can bind-mount
them writable.

## SSH integration (nix-ssh-config)

`nix-ssh-config` is consumed as a flake input (`nixpkgs.follows`,
single nixpkgs in the closure); its module is wired into
`nixosConfigurations.pbx` and `pbx-prod` in flake.nix (where `inputs`
are in scope), NOT in hosts/*. Both hosts set `allowRootLogin = true`:
with keys-only enforced by the module defaults (passwordAuthentication
AND keyboard-interactive off since upstream v0.1.2) that is the
prohibit-password posture; the prod runbook needs it
(`nixos-rebuild --target-host root@<host>` — without it the documented
update path is refused post-install: no other login user exists). Prod
additionally pins `allowUsers = [ "root" ]`.

**`PasswordAuthentication no` is NOT keys-only on NixOS**: the default
`KbdInteractiveAuthentication yes` + `UsePAM` let PAM accept Unix
account passwords over keyboard-interactive (matters on the demo VM
where root has an initialPassword) — the upstream module closes this
door by default (kbdInteractiveAuthentication follows
passwordAuthentication); we set nothing by hand and assert
`kbdinteractiveauthentication no` in tests/ssh.nix. `sshd -T` prints
canonical mixed-case directives (`PermitRootLogin`, `Macs`) — compare
case-insensitively in tests. tests/ssh.nix receives the module as a
function argument so the test file itself stays input-free.

## ACME issuance failure: check CAA FIRST; then know the minica

## placeholder and the no-retry trap

2026-09-16 deploy: pbx.artmann.tech served `CN=minica root ca` for
hours while DNS, port 80, challenge path, nginx wiring, and LE rate
limits all verified good. Root cause: the domains repo's CAA set for
artmann.tech allowed only pki.goog + amazon.com — under RFC 8659
Let's Encrypt refuses every subdomain whose zone doesn't list it; lego
fails with `urn:ietf:params:acme:error:caa` (the error names the ZONE,
not the hostname). Two amplifiers: the minica cert is nixpkgs ACME's
self-signed placeholder (served until the first SUCCESSFUL order), and
nixpkgs' `acme-order-renew-<cert>` unit ships `RestartSec=15min` with
NO `Restart=` (dead config) — one failed order is never retried until
the daily timer's up-to-a-day jitter. modules/telephony now adds
`Restart=on-failure` + `StartLimitIntervalSec=0` for
`acme-order-renew-<domain>` in acme mode (pinned by tests/eval.nix
`acmeRestart`). Diagnosis ladder: `dig CAA <registered-domain> +short`
→ `crt.sh?q=<domain>` (zero CT entries ever = issuance never succeeded
anywhere) → unit journal.

## Auto-commit daemon + history surgery

Scrub/redact ALL candidate-sensitive content — including UNTRACKED
files (status reports: DIDs in any formatting, personal mobile numbers,
SIP usernames) — BEFORE any write-tree/commit-tree squash. The daemon
commits untracked files within minutes and the squash absorbs them;
`git log --all -S '<string>'` after EVERY squash is the mandatory
tripwire (it caught an unredacted DID once). Widen scans beyond the
strings a handoff summary lists: grep the tree for spaced variants too
(`+48 9xx …` does not match `-S '489xx…'`).

Since 2026-09-16 the tripwire is productized: `scripts/scrub-check.sh`
greps the real values (gitignored `secrets/scrub-patterns.txt`, every
spelling listed) over the tree and, with `--history`, over
`git log --all -S`. It runs as a pre-commit hook (tree scan) and must
be run with `--history --strict` before any squash/release.

Tags anchor history too: after any history surgery, force-move the
release tags in the SAME session (`git tag -f <tag> <new-hash>` +
`git push --force-with-lease origin <tag>`, pinned to the exact expected
remote objects), then prove it from a scratch clone
(`git fetch --prune --tags` must exit 0). The 2026-09-03 scrub
force-pushed branches but left `v0.1.0`/`v0.2.0` on the pre-scrub
history for ~2 weeks — anchoring the redacted-away commits and breaking
every `git fetch --tags` until repaired 2026-09-17.

## Ad-hoc `nix run nixpkgs#<tool>` on a deployed host: three traps

`modules/telephony/ops.nix` ships the fix; this records why each part
exists (all proven against nix 2.34 in the pbx VM test net, 2026-09-17).

1. **Experimental features off**: a fresh NixOS host has neither
   `nix-command` nor `flakes`, so every `nix run/shell nixpkgs#…` dies
   immediately. `nix.settings.experimental-features` fixes it.
2. **The global registry fetch is a fatal offline dependency**: for ANY
   indirect ref (`nixpkgs#btop`), nix eagerly loads the global registry
   from channels.nixos.org — and a failed download ABORTS the whole
   lookup even when `/etc/nix/registry.json` holds an exact `nixpkgs`
   match (reproduced with a local `NIX_CONF_DIR` + registry.json: the
   pinned entry resolves only once `flake-registry` is disabled). Hence
   the pair: pin `nix.registry.nixpkgs.to` to `pkgs.path` AND set
   `nix.settings.flake-registry = ""`. Side effect, deliberate: other
   indirect ids no longer float against upstream — the pin is the
   sanctioned path.
3. **Spelling**: it is `nixpkgs` (with the s); `nixpkg` fails with
   "cannot find flake 'flake:nixpkg' in the flake registries".

Debugging note: registry lookup order is user → system → global. A
developer machine's own `~/.config/nix/registry.json` SHADOWS the
system entry under test — replicate a bare host with an empty
`XDG_CONFIG_HOME` plus `NIX_CONF_DIR`, or the experiment lies.

## Tracked-main inputs: a lock update can import upstream breakage

The `webphone` input tracks upstream main (owner decision 2026-09-18);
only `flake.lock` pins revisions. On 2026-09-24 a 13:52 lock update
imported an upstream rev with a stale `vendorHash` (the go-modules
proxy served no zips for four bumped deps) and every consumer build
died. Lesson: after ANY relock, build the affected package BEFORE
trusting the gate ladder, and when upstream main is broken,
forward-pin to the first GREEN rev (verified: upstream fixed the
vendorHash one auto-commit later; compare on GitHub shows the
minimal diff) and say so in the commit message. Corollary: a
handoff's "locked rev" claim is not ground truth — `git log --
flake.lock` costs five seconds and would have exposed a mid-session
relock before a 25-minute pipeline burned on it.

Sequel (2026-09-26, a second breakage class): `2bbbc2e` was
vendorHash-clean but wire-broken — `SharedContact` had no JSON tags,
`/config.js` emitted capitalized `Name`/`Number`, and
`checks.telephony-webphone` died on `KeyError: 'name'`; CI stayed red
for four runs until upstream `e43fea8` (lowercase marshaling + wire
test) arrived via the `0230ead` relock. Two additions to the rule:
upstream webphone has NO build CI (only Dependabot/Dependency Graph
workflows — verified via `gh workflow list`), so "first green rev"
can only be proven by THIS repo's suites, never read off upstream
checks; and a relock that lands a UI release (2.7.0 changed markup:
EmptyState, `tw.css`) owes a browser-E2E re-run, which CI never does
(the suite is on-demand by design).

## /tmp is ephemeral by policy: durable clones or git bundles, immediately

The 2026-09-24 host reboot destroyed an unpushed upstream fix living
in a `/tmp` clone — verified intact at 18:05, gone at 03:00.
"Verified" without mitigation is theater: any unpushed work moves to
`~/projects` or becomes a `git bundle` within minutes of creation,
not at session end. The same reboot took background-shell logs and
watch plumbing with it: monitoring state that must survive a session
belongs in durable sources (`gh run view`), never `/tmp` paths or
shell IDs.
