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

## The daemon races multi-write artifacts: assemble in /tmp, mv atomically

The daemon does not just commit untracked files — it can commit them
HALF-WRITTEN. 2026-10-01 incident `1e552f4`: a session status report
was being assembled through several sequential in-tree writes; the
daemon landed a heuristic commit between two of them, so history
permanently contains a truncated table (annotate-never-rewrite means
the fix was a follow-up commit, not a squash). Same class as the
`git mv`-on-untracked trap: the window between "file exists" and
"file finished" is a commit lane.

Rules:

1. Multi-step artifacts (reports, plans, any file built by paste +
   append + edit) are assembled OUTSIDE the tree (e.g. `/tmp`) and
   moved in with ONE atomic `mv` — the daemon either sees nothing or
   the finished file.
2. Scrub review (personal data, DIDs, numbers) happens on the /tmp
   copy, BEFORE the mv — not after the commit. Safety checks that run
   after the daemon has already committed are theater; the 2026-10-01
   self-review owned exactly that ordering fuckup.
3. A hand-authored commit beats the daemon whenever attribution
   matters (lock moves per the relock ritual; findings-bearing
   reports). If the daemon won anyway, `git log -1 --format=%an` plus
   the heuristic-message shape tells you which one you got — do not
   rewrite history to fix it.
4. `git reset` / `git rebase` / `git restore` in a repo shared with
   the daemon AND parallel sessions races everyone else's in-flight
   edits: pbx-artmann 2026-10-06 — a parallel session's `git restore`
   (the reset family) silently ate ANOTHER session's on-disk work
   mid-flight, and the daemon then committed the loss. Before any
   history- or worktree-mutating git op: `git status`, identify every
   change you did NOT author, and leave it alone — and land your own
   edits in one write, so a half-state is never what a parallel reset
   catches.

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

## Provenance labeling: reconstructed facts wear the label inline

Durable docs (CHANGELOG, lessons, runbook) only carry facts that were
observed; everything REBUILT from reports or derivations is labeled
at the point of use, in the same sentence — "RECONSTRUCTED
2026-11-07 from <report-path>" for code (the nonce-deleter harness),
"(reconstruction)" or a count with its derivation for numbers. The
anti-pattern is the silent rebuild: a number that LOOKS measured but
was inferred shipped wrong conclusions into three 2026-10 era docs
before the round-11 sweep caught the class. A reconstruction that
later gets measured in-place replaces the label; nothing else edits
it.

## Attribution store sharing: two verdict runs, one store path

A relock's browser-E2E attribution sometimes needs the suite at BOTH
the base and the new pin (base-red + new-green proves the delta).
The naive shape realizes the whole VM closure twice — tens of
minutes and disk. The store-sharing lever: the two runs differ only
in the webphone drv, so running the BASE suite first and letting
`nix build` reuse every shared dependency keeps the second run's
cost at the delta; measure whether a shared VM store path (one
`nixosTest` invocation parameterized over the pin) is worth the
abstraction before building it (open 2026-10-05 item 44, routed to
TODO_LIST ops-singles).

## Pre-commit hook healing: the non-convergent updater, root-caused 2026-10-07

git-hooks.nix cannot heal a LOST hook file (it refuses while
`.pre-commit-config.yaml` exists), and `pre-commit install` refuses
whenever `core.hooksPath` is visible (the global `~/.gitconfig`
points it at a nonexistent `.githooks`). WORSE: the updater's update
branch fires whenever the config store path changes — i.e. after ANY
tracked-file edit — strips ALL hooks, unsets the local hooksPath, and
the install then refused on the GLOBAL value. Every such `nix
develop` entry (and every BuildFlow run building a devshell) left the
repo ungated until manually healed. The fix: `devShells.default`'s
shellHook wraps `config.pre-commit.installationScript` with
`GIT_CONFIG_GLOBAL=/dev/null` (saved/restored around it), so install
lands in the default `.git/hooks` and the updater's own final line
re-anchors local `core.hooksPath` there; a forced-fire entry installs
BOTH hooks green. `scripts/heal-pre-commit-hook.sh` remains the
remedy for hook-file loss outside an entry; a scrub canary proved the
restored hook blocks. Filed upstream as git-hooks.nix#754
(non-convergent hook healing).

The other structural finding of the same day: the auto-commit daemon
bypasses every hook — it commits via go-git (`NewGoGitWithRetry`),
which never EXECUTES git hooks; the 2026-09-29 "plain `git commit`,
no `--no-verify`" source check was vacuous (it verified the absence
of a flag, not the presence of hook execution). Only CLI/human
commits are hook-gated (canary-proven through real plumbing); the
daemon lane needs its guard inside pma/go-commit (owner lane,
fleet-wide — every go-commit repo is exposed).
