# Status: Docs-health round 6 — all 2026-0* snapshots annotated + archived, CI red root-caused as infra, living-doc drift fixed

- **Written**: 2026-09-29 04:35 CEST
- **Scope**: this session only (~03:40–04:35 CEST). Trigger: the owner's
  standing docs-health instruction (view ALL `**/2026-0*` files, execute the
  docs-health skill properly, six living docs superb, archive fully-done +
  inline-strikethrough files) followed by a self-review + status request.
  **A sibling session was active in this tree the whole time** (the bridge/MMS
  Content-Type lane: commits `53f3b7c`/`6e949fc`); it was detected late (see
  d.4), its lane was then left strictly alone.
- **TL;DR**: All 3 loose snapshots carry inline verdict markers on every
  actionable item (103 items: 35/27/41, zero unmarked) and are archived — both
  snapshot dirs hold zero loose files. The CI "red" was root-caused as two
  GitHub runner-shutdown cancellations mid-green (NOT code failures); the full
  LOCAL `nix flake check` is green end to end. Living-doc drift found and
  fixed: a stale IN_PROGRESS relock row (the relock had landed at `3c87f80`),
  test-count drift 42→45, a phantom "webphone >= 2.8" version claim in the
  in-flight CHANGELOG (no v2.8 exists), missing AGENTS lock-governance
  knowledge. TODO_LIST net +8 rows, ROADMAP +2 ideas. Health report (audit
  time): Accuracy 6.75 / Fitness 9.25 — every finding fixed during the session.

## a) FULLY DONE (verified this session)

1. **Snapshot inventory + classification**: every non-archived `2026-0*` file
   identified; 3 loose status reports viewed in full and annotated; the
   `docs/research/` (2 md + 1 html) and `docs/decisions/` (3) files verified
   as SKIP-class permanent reference/decision docs (verdict banners present),
   consistent with the round-5 classification.
2. **103 inline verdict markers** across the 3 snapshots (09-25: 35, 09-26:
   27, 09-29: 41 — block-aware per-item checker reports zero unmarked in
   §b/§c/§f/§g of each). Form: `~~item~~ done — <evidence>` for resolved
   items (owner instruction: strikethrough), `**→ open — <live home>**`
   routed arrows for still-open ones (house style, 2026-08-24 precedent).
3. **3 files archived via `git mv`** (`docs/status/archived/`); both snapshot
   dirs now hold ZERO loose files; the dual-form marker gate (grep) passes
   over all 60 archived files.
4. **CI red root-caused**: runs 36262573684 (34250f8) and 36501187472
   (3c87f80) both end with `##[error]The runner has received a shutdown
   signal` — cancellations while green, never code failures. Last completed
   verdict: green at `f2aa2be`. The reading rule (canceled ≠ red) is now in
   AGENTS.md.
5. **Webphone lock truth established**: relock landed at `3c87f80`
   (`932c181` → `3d8df3f`, docs-only upstream delta), `nix build .#webphone`
   → webphone-2.7.0. The stale IN_PROGRESS TODO row ("Remaining: relock")
   was deleted; CHANGELOG gained the lock-refresh entry.
6. **CHANGELOG phantom version corrected in flight**: "webphone >= 2.8"
   never existed (upstream tags stop at v2.6.0, version literal 2.7.0) and
   the producer-side stamping code sits at webphone main HEAD (`f6239fa`
   era, `internal/gateway/webhook.go` CreatePart), AFTER our locked rev.
   Disclosed deviation from append-only, justified as pre-release factual
   repair.
7. **Test-count drift fixed**: AGENTS.md and FEATURES.md said 42; the real
   suite is 45 (35 bridge + 10 reconcile) — verified by running it twice
   (`Ran 45 tests, OK`).
8. **AGENTS.md knowledge codified**: the relock ritual (build → fast gates →
   VM suites → browser E2E on markup deltas → HAND-AUTHORED commit naming
   revs), the `nix flake update --dry-run` unsupported-flag gotcha, the
   concurrency pre-flight line, the tags-vs-version-literal rule, the CI
   cancel-reading rule (commits `7777c7a`/`73752fc`).
9. **devShell extended**: `gh` + `vulture` (as `python3Packages.vulture`)
   pinned beside the BuildFlow lint binaries; FEATURES devShell row expanded
   from 3 words to the real inventory.
10. **The 09-29 advisory's verification debts closed at code level**, using
    the local sibling checkouts (`/home/lars/projects/{pbx-artmann,webphone}`):
    the downstream `backup.nix` tail confirms every assertion (retention-8,
    26h freshness, 85% disk, 1 GiB MMS guard, journal-only relay); option
    names `backupStaging`/`secretsDir` are free; the webphone NixOS module
    read surfaced a REAL finding — upstream ships an optional nginx vhost
    generator that would collide with our `web.nix` vhost if its default
    ever flips → new split-brain-guard TODO row.
11. **HARVEST executed with routing discipline**: TODO_LIST +8 net-new rows
    (CI-verdict confirm, webphone build CI, vhost guard, lock-doctor, daemon
    leak-vector check, nix-ssh-config home-manager relock, extract inline
    assert, contacts cross-link), +1 owner row (CI posture), 2 rows extended
    (browser-E2E lock-trigger, runbook command-sheet alignment), 2 done rows
    deleted (relock, vulture pin); ROADMAP +2 raw ideas (binary cache, vulnix
    replacement). Deduped against every existing row; the 09-29 §f
    already-tracked items (20–25) were verified present, not duplicated.
12. **Every gate green**: full local `nix flake check` ALL PASSED (exit 0 —
    first local run since the binfmt return; `/run/binfmt` is back);
    pre-commit battery 6/6 (changelog-headings, deadnix, gitleaks, nixfmt,
    scrub-check, statix); `nix fmt`; drift alarm self-test + real gate PASS
    (after fixing 5 ghost citations — see d.2); scrub-check 23 patterns
    clean; 45 stdlib tests OK; internal-link sweep over the six living docs
    OK; markdown table-shape checks OK.
13. **Health report printed inline** with visible math (Accuracy 6.75 /
    Fitness 9.25 at audit time; every finding fixed on sight).

## b) PARTIALLY DONE

1. ~~**Origin CI verdict ≥ `3c87f80`**: the local full check is green, but~~ done — GREEN at `b8f211d` — run 36538651011 completed success 2026-09-29 (origin/main verified via gh; CHANGELOG Added 2026-09-29)
   ~~origin's two post-relock runs were runner-canceled and the daemon had not~~
   ~~yet pushed this session's tail when the report was written. Remaining:~~
   ~~one completed verdict on origin. Blocker: daemon push + runner luck.~~
   ~~Effort: S.~~
2. ~~**check-rows.py uniformity**: run over the 09-26 table; its~~ done — recorded in AGENTS.md Conventions (M24/f24.01, 2026-09-29)
   ~~"CLEAN row in a struck table" warnings on open rows are a DELIBERATE~~
   ~~deviation (unstruck + arrow, per the 2026-08-24 house precedent), but~~
   ~~that convention decision is recorded only here — not yet in AGENTS.md.~~
   ~~Effort: S to record.~~
3. ~~**Per-item marker completeness**: proven for the 3 newly annotated files;~~ done — M24 retro sweep — 90 verdicts across 15 files + the standing `scripts/markers_check.py` gate (a5ce7f1): zero unmarked
   ~~not retro-verified over the other 57 archived files (file-level grep gate~~
   ~~does pass for all). Effort: S.~~
4. ~~**Browser E2E at `3d8df3f`**: not run this session. The delta from the~~ done — superseded — the relock moved past it (`f53397a`: `3d8df3f` → `045edfe`, docs-only delta, browser E2E not triggered per the ritual; CHANGELOG 2026-09-29)
   ~~browser-proven `0230ead` is docs-only upstream, so the risk is low, but~~
   ~~the ritual technically wants a run per relock. Effort: M.~~
5. ~~**AGENTS.md size**: 14.5 → 16.2 KB. Additions are durable knowledge, but~~ done — M27 slimming landed — 16.7 → 15.2 KB (09-20 report §a.6)
   ~~the trend deserves a future slimming pass. Effort: M.~~

## c) NOT STARTED (deliberately out of this session's scope)

1. ~~Implementation of the TODO rows (failregex eval check, healthz probe,~~ done — round-4 execution closed them — failregex, healthz, runbook, vhost guard, lock-doctor, webphone CI (09-20 §a.1) + the M19 ACL hardening (§a.2)
   ~~lock-doctor, daemon check, vhost guard, webphone build CI …) — this was a~~
   ~~docs session; rows are the deliverable.~~
2. ~~`buildflow --build-mode full --max-time 60m` (runnable again now that~~ done — M18 — buildflow full run 3× + triaged; green shape recorded (09-20 §a.8)
   ~~binfmt is back; owner row stands).~~
3. ~~Upstream webphone: pushing the local stamping commits (whether `f6239fa`~~ done — push done (`89502ee`, CI green) + relock landed (`f53397a` → `045edfe`)
   ~~is on origin main was NOT verified) and the relock that would pick them~~
   ~~up.~~
4. The round-2 migration moves (all await the owner go; plan doc not
   written). **→ open — owner go (M06 gates)**
5. ~~Local markdown-lint / lychee pass (the pre-commit battery and BuildFlow~~ done — pre-commit battery 6/6 green (09-20 §a.9); markdown-lint/lychee stay pre-commit/BuildFlow-owned
   ~~own them; nix-side battery ran clean).~~

## d) TOTALLY FUCKED UP (owned, with costs)

1. **Repeated the documented anchor-failure class twice.** The AGENTS multiedit
   failed on a line-wrap difference ("are pinned in" vs "are pinned\n in"),
   and the TODO_LIST Low-section edit failed on padding — both from anchors
   re-typed from memory instead of copied bytes. The exact lesson (round-5
   d.4, 09-26 d.2) was in files I had JUST annotated. Cost: 3 repair round
   trips. Mitigation that held: python-scripted replaces with uniqueness
   assertions for everything after.
2. **Wrote 5 ghost citations into TODO_LIST, then misread the gate.** The
   09-29 report's own harvest note says "route evidence to repo paths"; I
   still backtick-cited `.github/workflows/ci.yml` (dot-stripped by the
   alarm), `branches/main/protection`, upstream's
   `package/nixos-module.nix`, the not-yet-existing `scripts/lock-doctor.sh`,
   and `.git/hooks/pre-commit`. Then I ran `drift_alarm.py` BARE (a usage
   error, exit 2) and initially read a stale self-test PASS as the gate
   passing. Real gate: 5 FAILs. Root cause: gate-after-all-edits instead of
   gate-after-every-table-edit (round-5 d.5, now twice) + unknown CLI args.
3. **The vulture package guess.** Added `vulture` as a top-level nixpkgs
   attr; the devShell build failed with "undefined variable 'vulture'".
   Fixed to `python3Packages.vulture`. Should have eval-checked the attr
   before editing the flake.
4. **Late sibling-lane detection.** The parallel bridge session was
   discovered only when its commit `53f3b7c` (files I never touched)
   appeared in git log. My early `ps` scan included 'crush' in the pattern
   but `head -8` truncated the output before the crush rows. The concurrency
   pre-flight rule I codified in AGENTS.md was born ~40 minutes after I
   needed it. Mitigation that held: strict lane separation afterward, zero
   collisions, CHANGELOG appends coexisted.
5. **A wasted full background `nix flake check`.** Started before the TODO
   citation fixes were final, so its copied source guaranteed a docs-drift
   failure; re-ran clean afterward. Long gates must start after the tree is
   believed-final.
6. **Health-report grouping inconsistency.** Merged the AGENTS+FEATURES
   count-drift as one root cause in prose, then counted them as two Medium
   rows in the table anyway. The arithmetic stayed self-consistent (3 Medium
   counted explicitly), but narrative and table told two different stories —
   the math-discipline rule says grouping happens in ONE place.

## e) WHAT WE SHOULD IMPROVE (systemic, from d)

1. **Copy anchors, never re-type** — any multiedit anchor longer than one
   line gets re-viewed immediately before the edit (d.1; third recurrence).
2. **Run drift_alarm after EVERY TODO_LIST table mutation**, and know its
   CLI (`TODO_LIST.md FEATURES.md <root>`; bare = usage error) (d.2).
3. **Eval-check package attrs before flake edits**
   (`nix eval nixpkgs#<attr>.version`) (d.3).
4. **Sequence long gates last**: kick `nix flake check` only when the tree
   is believed-final, else the run is a scheduled stale-failure (d.5).
5. **Record the open-row marker convention** (unstruck + `**→ open**`
   arrow inside struck tables beats check-rows uniformity, 2026-08-24
   precedent) in AGENTS.md Conventions — today it lives in archaeology (b.2).
6. **Mid-flight `git log` glance before every annotate/archive batch** —
   daemon commits shift mtimes and content under you (one edit failed on a
   mod-time guard; the fix re-read first).

## f) NEXT (ranked; routing marked so HARVEST does not duplicate)

Already routed to TODO_LIST unless marked otherwise. `[NEW]` = net-new from
this session, harvest target; `[OWNER]`/`[DOWNSTREAM]` = not routable by me.

| #  | Task                                                                                             | Impact   | Effort | Category / route         |
| -- | ------------------------------------------------------------------------------------------------ | -------- | ------ | ------------------------ |
| 1  | Confirm a completed origin CI verdict ≥ `3c87f80` after the daemon push **→ done — GREEN at `b8f211d` (run 36538651011, 2026-09-29)** | Critical | S      | TODO_LIST                |
| 2  | CI posture on main: branch protection + required checks, or failure notification **→ open — TODO_LIST [OWNER] row (CI posture)** | Critical | S      | TODO_LIST [OWNER]        |
| 3  | Webphone repo build CI workflow (zero build CI today) **→ done — webphone CI landed 2026-09-29, first run green (M16)** | High     | M      | TODO_LIST                |
| 4  | Relock webphone to pick up the MMS stamping producer (main HEAD `f6239fa` era) **→ done — relock landed at `f53397a` (`3d8df3f` → `045edfe`)** | High     | S      | [NEW]                    |
| 5  | Verify the webphone local stamping commits are on origin main (reachability of the producer rev) **→ done — CHANGELOG relock entry: producer rev "verified reachable from origin/main first"** | High     | S      | [NEW]                    |
| 6  | Vhost split-brain guard: force `services.webphone.nginx.enable = false` **→ done — vhost split-brain guard landed (CHANGELOG Added 2026-09-29)** | Medium   | S      | TODO_LIST                |
| 7  | `lock-doctor` script (revs vs upstream HEADs + verdict-per-rev; cancel ≠ red) **→ done — `scripts/lock-doctor.py` (cancel-≠-red verdicts, `--self-test`)** | Medium   | S      | TODO_LIST                |
| 8  | Daemon leak-vector check (can auto-commits bypass scrub/gitleaks?) **→ done — hooksPath landmine found; canary-proven blocked; `heal-pre-commit-hook.sh` landed (CHANGELOG Fixed 2026-09-29)** | Medium   | S      | TODO_LIST                |
| 9  | Lock-bump runbook section + upstream command-sheet alignment **→ done — ops-runbook "Lock-bump runbook" section (CHANGELOG Added 2026-09-29)** | Medium   | S      | TODO_LIST                |
| 10 | Eval-time failregex check over both shipped filters **→ done — `checks.telephony-failregex` (negative arm proven)** | Medium   | S      | TODO_LIST                |
| 11 | Webphone `/healthz` probe in the health unit **→ done — `/healthz` probe + monitoring recover arm** | Medium   | S      | TODO_LIST                |
| 12 | Operator FS-state ACL hardening + dedicated stream-token secret **→ done — M19 operator ACL: `telephony-fs` group + `streamTokenSecret{,File}` (09-20 §a.2)** | Medium   | M      | TODO_LIST                |
| 13 | Round-2 migration plan doc (belongs-table, scrub checklist, verification matrix) **→ open — owner go (round-4 M07; gated on M06)** | High     | M      | [OWNER go]               |
| 14 | Backup-staging mechanics upstream as a module option **→ open — owner go (round-4 M08)** | High     | M      | [OWNER go]               |
| 15 | Alert-relay collision: module-own `telephony-alert@` **→ open — owner go (round-4 M09)** | Medium   | M      | [OWNER go]               |
| 16 | Restic PUSH vs staging+PULL doctrine decision **→ open — owner decision (M06)** | Critical | S      | [OWNER decision]         |
| 17 | Secrets perms-heal unit upstream (`secretsDir` option) **→ open — owner go (round-4 M09)** | Medium   | S      | [OWNER go]               |
| 18 | `verify-live.sh` parameterized into this repo (deploy.md §5 companion) **→ done — `scripts/verify-live.sh` landed + live-proven 14/0 (CHANGELOG Added 2026-09-29)** | Medium   | S      | [OWNER go]               |
| 19 | Kexec-installer framework: public here / private / fleet tooling **→ open — owner decision** | High     | —      | [OWNER decision]         |
| 20 | `pack-initramfs.nix` + RAM-envelope gate shared with metal-boot **→ open — conditional on 19** | Medium   | M      | [OWNER, cond. on 19]     |
| 21 | Cut v0.3.0 release from the accumulated Unreleased entries **→ open — TODO_LIST v0.3.0 row (owner timing)** | High     | S      | TODO_LIST [OWNER timing] |
| 22 | `buildflow --build-mode full --max-time 60m` (runnable since binfmt return) **→ done — M18: 3× full runs triaged (09-20 §a.8)** | Medium   | M      | [NEW, unblocks rows]     |
| 23 | BuildFlow binary refresh via system profile **→ open — owner** | Low      | S      | [OWNER]                  |
| 24 | `nix-hash-fix` → `skip_steps` call **→ open — owner** | Low      | S      | [OWNER]                  |
| 25 | ROADMAP q7 answer (webphone lock governance: manual vs automated) **→ open — owner decision (ROADMAP q7)** | High     | —      | [OWNER decision]         |
| 26 | ROADMAP q8 answer (aarch64 emulation keep/drop) **→ open — owner decision (ROADMAP q8)** | Medium   | —      | [OWNER decision]         |
| 27 | /tmp-durability lesson → crush-config global lessons (commit there) **→ open — owner (crush-config repo lane)** | Low      | S      | [OWNER]                  |
| 28 | Binary cache (cachix/attic) for VM closures **→ open — ROADMAP theme 5** | Medium   | L      | ROADMAP                  |
| 29 | Vulnix replacement scanner (NVD 2.0 feed retired) **→ open — ROADMAP theme 5** | Medium   | M      | ROADMAP                  |
| 30 | Lock-diff CI step (old→new revs per input) **→ open — ROADMAP theme 5** | Medium   | S      | ROADMAP                  |
| 31 | nix-ssh-config home-manager relock issue/PR **→ done — issue nix-ssh-config#5 filed 2026-09-29 (M23); merge+relock = round-5 M21 owner lane** | Low      | S      | TODO_LIST                |
| 32 | Extract the inline config.js python assertion from tests/webphone.nix **→ done — `tests/configjs_check.py` (09-20 §a.3)** | Low      | S      | TODO_LIST                |
| 33 | Contacts wire contract cross-link (both directions) **→ done — three-way contacts cross-link (09-20 §a.3)** | Low      | S      | TODO_LIST                |
| 34 | Browser E2E promotion (periodic / lock-rev trigger) **→ open — TODO_LIST blocked row (owner cadence)** | High     | M      | TODO_LIST [OWNER]        |
| 35 | First real deployment lane P1–P5 (user hands-on steps) **→ open — TODO_LIST High blocked row (+ host-identity question)** | Critical | 2h     | TODO_LIST BLOCKED        |
| 36 | Warsaw DID re-purchase + KYC window **→ open — TODO_LIST blocked row** | High     | S      | TODO_LIST BLOCKED        |
| 37 | Rotate the Telnyx API key (+ scrub-pattern prefix update) **→ open — TODO_LIST blocked row** | Medium   | S      | TODO_LIST BLOCKED        |
| 38 | sops-nix example host wiring **→ open — TODO_LIST blocked row** | Low      | S      | TODO_LIST BLOCKED        |
| 39 | fspbx verdict sign-off execution (kill/keep the trial VM) **→ open — TODO_LIST blocked row** | Medium   | S      | TODO_LIST BLOCKED        |
| 40 | GitHub residual-exposure appetite (support GC + clone inventory) **→ open — TODO_LIST blocked row** | Low      | S      | TODO_LIST BLOCKED        |
| 41 | flake-meta-checker mainProgram policy **→ open — TODO_LIST blocked row** | Low      | S      | TODO_LIST BLOCKED        |
| 42 | Upstream BuildFlow feedback filing (verify-before-filing first) **→ done — BuildFlow#25–27 + #28 filed 2026-09-29 (AGENTS record)** | Low      | M      | TODO_LIST BLOCKED        |
| 43 | scrub-patterns "OWNER TO ADD" placeholders: fill or drop **→ open — TODO_LIST blocked row** | Low      | S      | TODO_LIST BLOCKED        |
| 44 | aarch64 KVM suite (if hardware materializes) **→ open — ROADMAP q8** | Low      | L      | ROADMAP q8               |
| 45 | Webphone smoke-script adoption as cheap post-build smoke **→ open — ROADMAP theme 3** | Low      | M      | ROADMAP                  |
| 46 | Machine-readable repo surface (`llms.txt`-style index) **→ open — ROADMAP theme 5** | Medium   | M      | ROADMAP                  |
| 47 | Record the open-row marker convention in AGENTS.md Conventions **→ done — AGENTS.md Conventions (M24)** | Low      | S      | [NEW]                    |
| 48 | Retro per-item marker check over the other 57 archived files **→ done — M24 retro sweep (90 verdicts / 15 files) + `markers_check.py` standing gate** | Low      | S      | [NEW]                    |
| 49 | check-rows.py retro over all archived tables (round-5 d.3 debt) **→ done — M24 row-uniformity sweep; accepted style recorded in AGENTS** | Low      | S      | [NEW, still open]        |
| 50 | AGENTS.md slimming pass (16.2 KB and growing) **→ done — M27 (15.2 KB)** | Low      | M      | [NEW]                    |

## g) QUESTIONS (cannot self-answer)

1. **CI posture on main.** The branch is unprotected (protection API → 404),
   the 2026-09-24/25 red streak sat unnoticed ~26h, and both post-relock
   runner-cancels also went unnoticed. Branch protection with required
   checks (which also blocks the daemon's pushes while red), a failure
   notification only, or leave as-is? I can configure any; blocking your own
   auto-commit daemon changes your workflow, so it is your call. (Tried to
   infer from repo settings; posture preference is not machine-readable.)
   **→ open — owner (CI posture = TODO_LIST Critical row; green window open)**
2. **Backup doctrine fork.** The module ships restic PUSH backups
   (VM-proven, zero production users — a ghost system); production runs
   staging + PULL (a compromised PBX holds zero target credentials, by
   doctrine). Round 2 forces a choice: dogfood restic in production, or
   retire the restic option and upstream staging+pull as the one supported
   story? Both maintained + neither reconciled is the worst current state.
   **→ open — owner decision (M06 gate)**
3. **Round-2 timing + kexec appetite.** Execute the migration moves now, or
   park them until the pending deploy + verification backlog clears (a
   second staged train would stack on the undeployed one)? And should the
   kexec self-install framework ever go public in this repo, stay private,
   or move to fleet tooling? Publishing the install path is an owner-only
   maintenance commitment.
   **→ open — owner decision (M06 gate)**

---

_Snapshot per the status-report convention: annotate, never rewrite. Section
(f) rows marked TODO_LIST/ROADMAP are already routed; `[NEW]` rows are this
report's harvest set for the next docs-health round._
