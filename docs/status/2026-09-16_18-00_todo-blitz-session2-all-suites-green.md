# Status Report — 2026-09-16 18:00: TODO-List Execution Blitz (Session 2: resume → all suites green)

_Point-in-time snapshot. Session resumed from the 16:35 report; this session's
scope: finish the in-flight TODO rows (backup test rerun, PR #1, pbx-prod
backup wiring, real-disk-boot VM test, docs sweep, full gate)._

## a) FULLY DONE (this session, each verified)

1. **Backup VM test green** (`checks.telephony-backup`): the first rerun
   failed only because `nix build` evaluated the tree BEFORE the daemon
   committed the `%N` assertion fix (build 17:08, fix commit 17:12 —
   race). Second run green: restic round-trip (canary → snapshot →
   `restic ls latest`), OnFailure wiring on 3 units, and a REAL
   `telephony-health` failure landing in the HTTP sink.
2. **PR #1 (Dependabot nix-installer-action 22→23): resolved without me.**
   The owner merged it at 14:42 UTC (squash `35b2742`); the GitGuardian
   question is moot.
3. **Git divergence repaired**: the daemon had 16 unpushed local commits
   while origin moved (dep-bump merge) → its pushes failed non-FF, which
   is why main CI kept testing STALE code (the "still red" mystery: the
   nixfmt fix was local-only). `git pull --rebase origin main` replayed
   all 16; tree identical, no conflicts.
4. **pbx-prod ships backups + alerting** (`hosts/pbx-prod/default.nix`):
   `backups.enable = true` with `repositoryFile`/`passwordFile` under
   `secretsDir` + CHANGEME comments, paths = real
   `/var/lib/private/freeswitch` + the secrets dir, prune 7d/4w/6m;
   `alerts.urlFile`; `restic` CLI on PATH for restores. Verified:
   toplevel evals (restic.initialize=true), and
   `checks.telephony-prod-boot` GREEN with new assertions
   (timer enabled, OnFailure → `telephony-alert@restic-backups-telephony.service`)
   and the secrets stub extended to the three new files.
   `docs/deploy.md` §3 table documents all three.
5. **Real-disk-boot VM test: `checks.telephony-metal-boot` GREEN (37s)** —
   the big one. Boots the REAL pbx-prod kernel+initrd (bootspec cmdline,
   `root=fstab`) against a GPT `disk-main-root` behind a
   `virtio-scsi-pci` HBA (Hetzner's bus). Console-asserted: initrd binds
   the Virtio SCSI HBA, mounts the by-partlabel root — the exact
   2026-09-14 first-boot hang point — and stage-2 systemd boots to the
   `pbx login:` prompt (nginx/sshd started). Six iterations to green;
   every trap is now a lesson (below).
6. **Docs sweep**: CHANGELOG [Unreleased] entries added (initrd-audit,
   backups+alerting, scrub gate, metal-boot, BuildFlow noise triage,
   AGENTS split); FEATURES rows added/updated (backups, alerting,
   initrd-audit, metal-boot, pre-commit hooks, prod template); TODO_LIST
   pruned to 2 actionable rows (hcloud.tf, scrub-patterns.txt fill) +
   blocked section; `checks.docs-drift` GREEN. AGENTS bullet +
   `docs/lessons/vm-testing.md` rewritten: the "VM tests cannot catch
   initrd gaps" claim is obsolete.

## b) PARTIALLY DONE

- **Main CI on origin**: still red — see d)4. The fix is committed
  locally; delivery is the blocker. → done — the daemon's push loop recovered 2026-09-16 19:08; origin == main, CI green on the new head (The final `nix flake check` gate
  finished GREEN at ~18:05 — every check substitutes from today's
  verified builds.)

## c) NOT STARTED

- `infra/hcloud.tf` reconcile (owner-gated: import needs server IDs/token
  or a retire decision).
- Filling `secrets/scrub-patterns.txt` (owner values; gate is
  warning-only until then).
- sops-nix example host, browser-E2E CI promotion, recording-consent,
  Warsaw DID, Telnyx key rotation (all owner-blocked rows, untouched).

## d) TOTALLY FUCKED UP / WENT WRONG (and what it cost)

1. **CHANGELOG multiedit failure mode**: my first "Added" insertion used
   `### Fixed` as anchor — ambiguous (exists in released versions too),
   and an earlier attempt even briefly created a duplicate heading.
   Fixed by anchoring on unique prose. Cost: one round trip.
2. **Paste error in metal-boot.nix**: a garbage
   `if False else None` line landed in an edit (caught on view, removed
   before it could confuse the daemon's commits).
3. **Closure-scope bug**: `closureTar` defined inside the node function
   but referenced from `testScript` (outer scope) → eval error. Fixed by
   hoisting + passing `pkgs` from flake.nix. Cost: one build round trip.
4. **The daemon has stopped pushing** (not my bug, but this session's
   biggest operational finding): 23 commits sit on local main; origin CI
   last ran at 14:42 UTC on pre-fix code, so **origin/main is red on
   stale code while every suite is locally green**. Its push presumably
   kept failing non-FF even after my rebase made it a fast-forward — no
   push as of 17:55.
5. **Metal-boot iteration taxes** (each a real lesson, now in
   docs/lessons/vm-testing.md): `wait_for_path` doesn't exist in this
   driver (type-check gate); `/mnt` absent on test VMs; file-by-file
   closure copy exhausts virtiofsd's 65536-fd budget ("Too many open
   files in system" is the DAEMON's limit surfacing); `execute("kexec -e")`
   kills the driver shell mid-command (parser death), fixed with a
   `systemd-run` transient unit; and the driver epilogue's unconditional
   `machine.execute("sync")` crashes against the post-kexec getty —
   fixed with `machine.crash()` (monitor-based teardown).

## e) WHAT WE SHOULD IMPROVE

1. **Git push observability**: the daemon commits silently but its push
   failures are invisible — main CI went stale for 3+ hours while local
   was green. Either the daemon should alert on push failure, or sessions
   must check `ahead-count` early (this session lost ~1.5h of CI signal).
2. **Build-vs-commit racing**: `nix build` on a flake reads the worktree,
   but CI builds origin — a fix sitting uncommitted makes local green /
   remote red (backup test rerun hit exactly this). After fixing a test,
   verify the fix is COMMITTED before rerunning (or accept the ambiguity
   consciously).
3. **Full-closure transfers in VM tests** should always be tarball
   streams, never per-file walks — the virtiofsd fd cap is systemic (any
   future test copying big trees will hit it).
4. **Small-file edits via multiedit** on prose files with repeated
   structure (CHANGELOG headings) are fragile — anchor on unique text.

## f) NEXT (ranked, ≤50 — realistically 11)

1. Push local main (23 commits) — or restart the daemon's push loop; then → done — recovered by itself; verified 19:08
   confirm origin CI green on the new head.
2. hcloud.tf: owner picks import (needs server IDs + token) vs retire. → done — retired 18:15
3. Fill `secrets/scrub-patterns.txt` from the example (owner values). → done — armed 18:15
4. Consider promoting `telephony-metal-boot` learnings upstream → open — ROADMAP theme 5 (diskInterface ≠ virtio-scsi doc gap; verify-before-filing first)
   (verify-before-filing first): qemu-vm's `diskInterface = "scsi"` ≠
   virtio-scsi is a documentation gap worth an nixpkgs issue/PR.
5. First real deployment runbook execution (rescue-boot + reinstall + → open — deploy lane §P1 (TODO_LIST)
   first calls) — still the Critical blocked row.
6. Rotate the Telnyx API key; Warsaw DID re-purchase + KYC window. → open — TODO_LIST blocked rows (key rotation, Warsaw/DE DIDs)
7. Recording-consent posture decision (PL/DE/US). → answered 2026-09-16 — record ALL calls, consent accepted
8. sops-nix example host wiring (owner-gated). → open — TODO_LIST blocked row (sops wiring)
9. Browser-E2E CI promotion (periodic/per-push) decision. → open — TODO_LIST blocked row (browser-CI cadence)
10. Upstream BuildFlow feedback (max_time config key, FOD-hash advisory, → open — TODO_LIST blocked row (upstream BuildFlow feedback)
    mainProgram for data packages) — verify-before-filing first.
11. Optional hardening: restic backup of `/etc`/host keys beyond the → open — TODO_LIST row (backup-suite restore round-trip)
    secrets dir; test a real `restic restore` path in the backup suite.

## g) QUESTIONS FOR THE OWNER (cannot be figured out from here)

1. **May I push local main to origin?** The daemon's push loop is stalled → moot — the daemon's push loop recovered (plan log 19:08)
   (23 commits, fast-forward, all local suites green) — rule says no push
   without explicit ask, so origin CI stays red until you either push
   yourself or authorize me.
2. **Is the auto-commit daemon supposed to push?** It pushed earlier → open — TODO_LIST row (daemon push observability)
   today (16:42 CEST run) but nothing since; if its push is broken
   (credentials? non-FF retry loop?), it needs a restart/fix outside this
   repo.
3. **Backup target confirmation**: I pre-wired pbx-prod for a Hetzner → open — owner; Storage Box pre-wired, documented in deploy.md §3
   Storage Box sftp restic repo (`telephony_backup_repo` secret file) —
   keep that shape, or point it at a different target (rest-server, S3)?
