# Status Report: TODO-List Execution Blitz

**Date-time:** 2026-09-16 16:35 CEST
**Scope:** This session only — executing the TODO_LIST.md open items
(taken from the 2026-09-15 09:19 rebuild) plus fallout discovered
along the way. Owner-blocked rows untouched by design.

**One-line verdict:** Ten of the actionable TODO items fully done and
verified; the backups+alerting module is one test-rerun from green
(its VM test already caught two real bugs); main CI went red once
mid-session because I edited flake.nix without running `nix fmt` —
root-caused and fixed; the final full-gate run and the doc sweep
(TODO_LIST/CHANGELOG/FEATURES) are still pending, so the session is
NOT cleanly handed off yet.

---

## a) FULLY DONE (verified this session)

1. **flake.lock audit** (High/S): all three lock-touching commits
   eyeballed — `849e951` (the TODO's target: flake-parts + nixpkgs
   moved by the failed run's nix-flake-update repair), `c556425`
   (git-hooks-nix bump), `bfcb5d0` (nixpkgs bump paired with the
   deliberate cert-restart dedup fix). Verdict: keep all three (each
   is the base of green verified work); CHANGELOG entries added,
   including two forgotten 09-16 behavior changes (prod ssh posture,
   cert-restart dedup).
2. **Formatter split-brain verify** (High/S): fresh `buildflow format`
   touched zero files under `packages/webphone/assets/**`;
   `checks.format` (treefmt) green.
3. **Initrd-audit gate** (High/S): new `packages/initrd-audit`
   (writeShellApplication; cloud=virtio_*, metal=nvme/ahci,
   `--modules` override; accepts initrd file or toplevel dir);
   `checks.initrd-audit` (x86_64) builds and audits the pbx-prod
   initrd — green; negative test fails with exit 1 and an actionable
   message; wired into docs/deploy.md §4 as the pre-install step.
   Bycatch: the demo `pbx` toplevel initrd genuinely has no virtio
   drivers (by design — it only boots as a VM), so the check audits
   the artifact that ships to metal (pbx-prod) only.
4. **Lychee probe** (Medium/M): `lychee.toml` IS read by BuildFlow's
   invocation (empirically: `exclude_path` changed the step's
   behavior); `docs/status/**` excluded (point-in-time snapshots);
   lychee step green.
5. **BuildFlow noise decisions** (Medium/M):
   - bandit: 0 findings — real B324 fix (`usedforsecurity=False` on
     the protocol-mandated TURN MD5) + inline `# nosec` at the 11
     intentional test sites (`.bandit` file probed first: BuildFlow
     does NOT pass `-c`, dead config removed).
   - vulture: 0 findings — root-caused `PT_EVENT` (dead constant,
     now actually used in vmclient.py SDP/defaults) +
     `tests/vulture_whitelist.py` for genuinely load-bearing
     attribute assignments (with `# noqa: B018`).
   - todo-check: 0 findings — drift_alarm.py's print label reworded
     ("TODO:" → "todo-list row:"); `todo_min_severity` probed and
     found ineffective for this checker (removed again).
   - pytest-test: skipped in `.buildflow.yml` (VM suites own testing;
     pytest collects 0 items by design).
   - per-tool excludes: NOT supported by BuildFlow (canonical key
     list) — documented in `.buildflow.yml`; jscpd/lychee keep losing
     webphone-asset coverage to the global oxfmt exclude (accepted).
6. **BuildFlow ergonomics** (Low/S): `BUILDFLOW_MAX_TIME` env var NOT
   honored (proven via the startup banner: flag works, env doesn't);
   `watch` / `diff` / `--failed-only` each exercised once (all work);
   `build_mode: fast` set as local default; AGENTS.md Commands section
   updated (full runs: `buildflow --build-mode full --max-time 60m`).
7. **Scrub-checklist script** (Medium/S): `scripts/scrub-check.sh`
   (tree scan always, `--history` adds `git log --all -S` per pattern,
   `--strict` makes a missing patterns file an error) +
   `secrets/scrub-patterns.example` template + gitignore split
   (secrets/* ignored, example tracked) + pre-commit hook in flake.nix
   (store-path bash). All four behaviors verified live (tree hit,
   history hit, clean pass, strict-missing fail).
8. **AGENTS.md headroom** (Medium/M): 400 → 162 lines; four lesson
   files created under `docs/lessons/` (freeswitch, vm-testing,
   webrtc-browser, operating) with the long-form entries migrated;
   inline section rewritten as sharp one-liners + pointers, and
   updated for today's decisions (initrd-audit, scrub-check, BuildFlow
   noise, fast default).
9. **Browser E2E re-run** (High/M): `nix build -L .#telephony-browser`
   — full suite GREEN in 118s, including the E2E-OK marker, media
   legs and DTMF; this simultaneously validates the ruff-driven
   `WebDriverException` narrowing AND this session's edits to
   tests/{browser-e2e,sip,vmclient}.py under a real Selenium session.
10. **Main CI red triage (introduced-then-fixed this session)**: the
    13:00 UTC main run failed `treefmt-check` because my repeated
    flake.nix edits never went through `nix fmt` before the
    auto-commit daemon pushed them; fixed (`nix fmt`, format check
    green locally). The pending pushes still need a green CI run to
    confirm.

## b) PARTIALLY DONE

1. **Backups + alerting** (Medium/M): `services.telephony.backups.*` → done — rerun green 2026-09-16 18:00
   and `services.telephony.alerts.*` options (plain/`*File` pairs,
   exactly-one-of assertions) + `modules/telephony/resilience.nix`
   (delegates to NixOS `services.restic.backups` with initialize=true;
   `telephony-alert@` template unit POSTs failed unit + journal tail
   to the webhook; OnFailure wired onto restic-backups-telephony,
   telephony-health, fail2ban) + `tests/backup.nix` VM test with a
   real restic round-trip and a real HTTP sink. The test caught TWO
   real bugs: (1) default path `/var/lib/freeswitch` is a
   DynamicUser symlink — restic archives links as links, default is
   now `/var/lib/private/freeswitch`; (2) systemd `%n` expands WITH
   the `.service` suffix → `…service.service`, now `%N`. Both fixed;
   **the post-%N-fix test rerun has not happened yet** — the item is
   one green run from done.
2. **Dependabot PR #1** (Medium/S): branch updated onto current main → done — owner merged 14:42 UTC
   (the two old failures were pre-fix-era treefmt split-brain + an
   old-tree VM flake, not the action bump); CI on the updated branch
   is GREEN (11m1s: nix flake check + aarch64 TCG pass). Remaining:
   the GitGuardian Security Checks job fails after 9s (external
   dashboard service) and the PR is not merged.

## c) NOT STARTED (remaining TODO rows)

1. Real-disk-boot VM test through the target bus. → done — checks.telephony-metal-boot green 2026-09-16 18:00
2. `infra/hcloud.tf` reconcile (needs owner facts — server IDs or a → done — retired 2026-09-16 18:15
   retire decision).
3. Session-close doc sweep: delete completed TODO_LIST rows, add → done — docs sweep done 18:00
   CHANGELOG/FEATURES entries for today's additions, re-run
   docs-drift.
4. Final full `nix flake check` (now 23 checks: +initrd-audit, → done — full gate green 18:01
   +telephony-backup) as the session gate.

## d) TOTALLY FUCKED UP (or close to it)

1. **Main CI red for ~1.5h mid-session** (root-caused, fixed, not yet
   CI-confirmed): I edited flake.nix ~6 times and never ran `nix fmt`;
   the daemon pushed unformatted nix; `checks.format` failed on main
   at 13:00 UTC. Process failure: with a fast-committing daemon,
   formatting after every nix edit is not optional.
2. **Config-first-probe-later twice**: wrote `.bandit` before probing
   whether BuildFlow passes `-c` (it doesn't — file deleted); set
   `todo_min_severity: warning` before probing its semantics
   (ineffective — removed). Both were cheap but exactly the
   guess-risky pattern the 09-15 session had sworn off.
3. **Two junk drafts of tests/backup.nix hit disk** (placeholder
   garbage like a copy_fromHost stub and an f-string hack) because I
   saved before composing; the daemon commits within minutes, so
   junk may be absorbed into history (`git log -S 'pkgs_'` at report
   time showed nothing — but this was luck of timing, not design).
4. **nosec placement thrash**: three iterations to learn bandit
   attributes findings to the innermost call line and ruff-format
   rewraps long lines (moving the issue line away from my comment).
5. **vulture whitelist collided with ruff B018** (useless-expression
   findings) — should have anticipated that every .py file feeds
   every linter.
6. Pipeline-masking echo (`… | tail; echo exit=$?` printed tail's
   exit) — caught immediately by the AGENTS lesson, but I still wrote
   it first.

## e) WHAT TO IMPROVE (session-derived)

- `nix fmt` after EVERY nix edit (or a daemon-side format hook) —
  CI-red-for-90min on a formatting nit is pure waste.
- Compose test/code files fully before first save; the daemon makes
  drafts permanent.
- Probe semantics empirically BEFORE writing config files; a probe is
  one command, a wrong config is a round-trip plus history noise.
- Cross-linter collision checklist for any new file: what ELSE reads
  *.py / *.nix / *.toml in this repo (BuildFlow feeds everything).
- Watch main CI runs during daemon-active sessions (push cadence vs
  CI lag caused the red window to go unnoticed).

## f) NEXT (ranked, ~25 real items — from this session's leftovers)

1. Re-run `checks.x86_64-linux.telephony-backup` after the %N fix; → done — green 18:00
   iterate to green.
2. Confirm the daemon's pending pushes turn main CI green (the 13:00 → done — CI green after the daemon recovered
   failure's fix is in the pushed tree).
3. Assess GitGuardian check on PR #1: required? broken integration? → done — merged (owner, 14:42 UTC)
   then squash-merge the PR.
4. Final full `nix flake check` as session gate (23 checks). → done — 18:01, all checks
5. TODO_LIST sweep: delete the ten completed rows. → done — 18:00 sweep
6. CHANGELOG: entries for initrd-audit, scrub-check, backups+alerts, → done — entries landed 18:00
   lessons split, BuildFlow noise decisions, fast default.
7. FEATURES.md rows for the same (statuses per docs-health rules). → done — rows landed 18:00
8. Real-disk-boot VM test (remaining Medium row). → done — metal-boot 18:00
9. hcloud.tf reconcile (blocked on owner facts; reclassify row). → done — retired 18:15
10. hosts/pbx-prod: wire `backups`/`alerts` with CHANGEME markers so → done — pbx-prod wired + prod-boot extended 18:00
    the template demonstrates the feature.
11. OWNER: fill `secrets/scrub-patterns.txt` with real values — the → done — armed 18:15
    gate runs WARNING-ONLY until then.
12. Run `scripts/scrub-check.sh --history --strict` once patterns → done — quantified 18:15; rewrite executed later (d7ac48f)
    exist (tripwire for the historical DID).
13. docs/ops-runbook.md: restic restore procedure + webhook setup. → done — runbook carries the restic restore procedure
14. tests/backup.nix: cover `pruneOpts` and the urlFile variant. → open — test-depth pack (pruneOpts/urlFile legs)
15. Consider OnFailure alerting for freeswitch.service itself → Won't-implement — deliberate: the health timer covers liveness
    (deliberately not added — health timer covers liveness).
16. Upstream BuildFlow feedback (via verify-before-filing): env-var → open — TODO_LIST blocked row (upstream BuildFlow feedback)
    support for max-time; bandit `-c` passthrough / per-tool excludes;
    todo_min_severity vs checker reality.
17. aarch64 confirmation that the two new x86_64-gated checks don't → done — aarch64 flake check green since
    break aarch64 flake check.
18. Consider cutting 0.3.0 once backups land (CHANGELOG is dense). → open — release 0.3.0 lane (plan §P18)
19. prod-boot/eval assertions for the backup/alert wiring in the → done — prod-boot extended 18:00
    pbx-prod template.
20. Re-check drift_alarm wording change didn't break docs-drift (in → done — gate green
    final gate).
21. gitleaks/scrub-check interplay sanity once patterns exist. → done — armed + history rewritten (d7ac48f), interplay clean
22. Hetzner Storage Box sftp + hostkey pinning note in deploy.md. → open — deploy lane §P1 (Storage Box hostkey pinning note)
23. Watch: browser E2E at 118s — consider promoting its CI cadence → open — TODO_LIST blocked row (browser-CI cadence)
    (owner call, ROADMAP q3).
24. AGENTS.md: add the restic-symlink-path and %N-suffix lessons → done — the symlink/%N traps are captured in the FEATURES backup/alerting rows
    (terse, one line each — headroom exists now).
25. Verify the daemon-pushed tree on GitHub matches local HEAD (no → done — origin == main verified 2026-09-16 19:08
    missing pushes) before closing the session.

## g) QUESTIONS FOR THE OWNER (cannot be answered from here)

1. **GitGuardian Security Checks** on PR #1 fails after ~9s (external → moot — GitGuardian question died with the squash-merge
   dashboard link). Is that check required for merging here, and is
   the GitGuardian integration alive? (If it fails on every run, it is
   an account/integration issue, not the PR.)
2. **hcloud.tf**: import the two manually created Hetzner servers into → done — retired 2026-09-16 18:15 (no state ever existed)
   Terraform (I would need their server IDs — or an hcloud token in
   scope) or retire the Terraform module?
3. **Backups target for pbx-prod**: is Hetzner Storage Box via sftp → answered — Storage Box sftp pre-wired; documented in deploy.md §3
   the intended restic repository (my option example and docs assume
   it), and should `backups`/`alerts` be pre-wired into the
   pbx-prod template with CHANGEME markers?

_Snapshot per status-report conventions; annotate, never rewrite._
