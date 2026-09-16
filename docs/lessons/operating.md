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
