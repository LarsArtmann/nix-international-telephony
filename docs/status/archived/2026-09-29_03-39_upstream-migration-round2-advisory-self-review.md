# Upstream-migration round 2: advisory session + self-review

**Date:** 2026-09-29 03:39 CEST
**Session type:** Advisory (repo-boundary analysis). **No code changed in any
of the three repos this session.** This report is a point-in-time snapshot of
what was analyzed, recommended, got wrong, and should happen next.
Written as `.md` per explicit owner instruction (the status-report skill's
HTML default was overridden).

## Session summary

Owner question: _what from the private deployment repo (downstream of this
module) and from the webphone repo makes sense to move into this repo?_

What was actually read, end to end or in verified part:

- Downstream repo: `AGENTS.md` (full), `TODO_LIST.md` (full), the executed
  2026-09-26 upstream-migration plan doc (belongs-table, invariants, macro
  tasks), `hosts/pbx/backup.nix` (first ~60 of 181 lines), `hosts/pbx/secrets.nix`
  (full), top-level tree.
- Webphone repo: top-level tree, `scripts/webphone-smoke.py` and
  `scripts/webphone-backup-drill.py` headers.
- This repo: `modules/telephony/` tree, `modules/telephony/resilience.nix`
  (full), `TODO_LIST.md` (full), top-level tree, scrub-patterns file (to keep
  this public report clean).

The delivered recommendation (chat only — no repo record until this report):

1. **Backup staging mechanics** (`hosts/pbx/backup.nix` staging half) upstream
   as a module option; rsync pull kit stays downstream.
2. **Secrets perms-heal unit** (`hosts/pbx/secrets.nix`) upstream as an
   optional `secretsDir` + heal unit.
3. **`tests/installer/verify-live.sh`** parameterized by domain, upstream as
   companion to `docs/deploy.md` §5.
4. Kexec-installer framework core flagged as an **owner call** (generic
   NixOS-install tooling, arguably fleet tooling, not telephony).
5. **Nothing from webphone** — correctly scoped since the v2 extraction.

---

## a) FULLY DONE

- Three-repo boundary analysis delivered, ranked by impact, with an explicit
  non-move list (`desired.json`, disk layout, pull kit, docs gates,
  deploy-freshness, lock-drift-probe) and per-item rationale.
- Verified at code level: the module already ships a restic backup option +
  `telephony-alert@` template (`modules/telephony/resilience.nix`) that the
  sole production deployment does not use (split-brain/ghost finding); the
  downstream staging script consumes `services.telephony.state.*` and does
  `sqlite3 .backup` + `MANIFEST.missing` (head of `backup.nix`); the secrets
  heal unit encodes module knowledge (coturn/turnserver group + per-file
  modes for module secret files).
- Webphone smoke/backup-drill scripts confirmed app-level (belong in webphone).
- Cross-checked recommendations against BOTH repos' TODO lists: none of the
  three moves duplicates an existing row (net-new recommendations).
- Scrub discipline held: no DIDs, IPs, trunk credential, API-key prefix,
  domain, or account resource names in the delivered answer or this report.

## b) PARTIALLY DONE

- ~~**Evidence base for recommendation 1:** only the first ~60 of 181 lines of~~ done — tail read 2026-09-29; all assertions confirmed in code (retention-8, 26h freshness, 85% disk, 1 GiB MMS guard, journal-only relay)
  ~~the downstream `backup.nix` were read. The retention, freshness/disk-full~~
  ~~check, and alert-relay mechanics were asserted from the downstream AGENTS~~
  ~~structure-table row — a secondary source — not from code.~~
- ~~**Option-surface check:** whether `services.telephony.backupStaging` /~~ done — names verified free in modules/telephony/options.nix (2026-09-29)
  ~~`secretsDir`-shaped option names are actually free in~~
  ~~`modules/telephony/options.nix` was never verified. The 2026-09-26 plan~~
  ~~doc explicitly did that ("name verified free") for `messaging.*`; this~~
  ~~session skipped the equivalent step.~~
- ~~**Webphone verdict:** built from the tree, script headers, and AGENTS~~ done — package/nixos-module.nix read 2026-09-29; finding: upstream ships an OPTIONAL nginx vhost generator, guard row added to TODO_LIST
  ~~context. `package/nixos-module.nix`, `nix/vm-tests.nix`, and~~
  ~~`nix/module-check.nix` were NOT read.~~
- ~~**Alert-collision claim:** the module side (`resilience.nix` template) is~~ done — collision confirmed in code (downstream telephony-alert@ unit vs resilience.nix template)
  ~~code-verified; the deployment side (the journal-only relay living in the~~
  ~~unread tail of `backup.nix`) was cited from a downstream TODO §8 row.~~

## c) NOT STARTED

- All three recommended moves: no code, no plan doc, no option drafts.
  **→ open — await owner go (f.1 is the plan row)**
- The restic-option disposition decision (see d.4 / g.1).
  **→ open — owner fork (g.1)**
- ~~HARVEST of section (f) into `TODO_LIST.md`/`ROADMAP.md` — deliberately~~ done — docs-health pass 2026-09-29
  ~~parked per "wait for instructions". NOTE for harvest time: the docs-drift~~
  ~~alarm fails any TODO row whose evidence cites a `docs/status/` snapshot;~~
  ~~route evidence to repo paths.~~
- Round-2 migration plan doc (belongs-table + scrub checklist + verification
  matrix, mirroring the 2026-09-26 one).
  **→ open — f.1 above**

## d) TOTALLY FUCKED UP

Nothing broke — no code changed. But three process failures, ranked:

1. **Silent override of a recorded owner-endorsed decision.** The executed
   2026-09-26 belongs-table row says: "Backup staging SERVICE — stays here;
   pull doctrine is an owner decision, not module API." The delivered answer
   recommended moving it anyway (staging/pull split is a genuine refinement —
   staging mechanics are generic, only the pull direction is doctrine) but
   NEVER named that this reverses a recorded decision. That violates the
   standing rule: state which decision you are revisiting and why, in the
   answer itself. The owner read a recommendation presented as
   conflict-free when it is actually a decision reversal proposal.
2. **Confidence ahead of evidence.** Retention counts, the freshness/disk
   check, MANIFEST completion logic, and the alert-relay collision were
   presented as facts of the file having read none of those code paths.
   Conclusions are probably right (two independent secondary sources agree),
   but the session asserted them at the same confidence level as the
   code-verified parts — an honesty-of-evidence failure, not a correctness
   one.
3. **A whole-repo verdict on thin evidence.** "Nothing from webphone" closes
   the door on an entire repo, but was built on file names and doc context
   without opening the webphone NixOS module, its VM tests, or its module
   check. If that module hardcodes nginx/TURN assumptions overlapping our
   `web.nix`, a genuine split brain is hiding exactly there — unexamined.

## e) WHAT WE SHOULD IMPROVE

- **Verify at code before verdicts, or label the source.** Advisory answers
  should distinguish "read in code" from "asserted from a TODO/doc row".
  One prefix character of honesty (`~`, "per docs") would have fixed d.2.
- **Decision ledger discipline.** When any recommendation touches a recorded
  belongs-table/ADR/plan row, name the reversal explicitly. The 2026-09-26
  plan is the decision record for repo boundaries; treat it like an ADR.
- **Surface the undecidable forks as questions.** The restic-vs-pull
  doctrine fork, migration timing, and installer appetite are owner calls;
  the answer buried the first entirely and deferred the others to prose.
- **Reuse the scrub checklist.** Any round-2 plan doc must carry the
  never-publish invariants list verbatim from the 2026-09-26 plan (DIDs,
  domain, `artmann-pbx-*` resource names, trunk username, secrets-dir
  paths) — this repo is public and the auto-commit daemon commits within
  minutes.
- **Advisory inventory step.** Before recommending moves, sweep BOTH TODO
  lists for already-tracked related rows so recommendations state their
  relationship to tracked work (this session did check for duplicates, but
  only for the moves themselves — not for the sibling-side rows that
  intersect them, e.g. the alert-collision row).

## f) Next things (30; grouped, harvestable)

**Round-2 moves (net-new from this session — await owner go):**

1. Write the round-2 migration plan doc: belongs-table, scrub checklist,
   invariants, verification matrix (mirror the 2026-09-26 plan).
   **→ open — await owner go (this row IS the round-2 plan ask)**
2. Upstream backup-staging mechanics as a module option: `sqlite3 .backup`
   over `services.telephony.state.sqliteDatabases`, copy of `state.paths`,
   MANIFEST, retention, freshness+disk-full check.
   **→ open — await owner go**
3. Module-own the alert relay and dissolve the `telephony-alert@` collision
   (coordinate: already tracked downstream TODO §8).
   **→ open — await owner go; the collision is code-verified now (b.4)**
4. **Decide the restic `services.telephony.backups` disposition: dogfood or
   retire.** Today it is a ghost system — shipped and VM-tested
   (`tests/backup.nix`) with zero production users, while production runs a
   private system the module does not know.
   **→ open — owner fork (g.1)**
5. Upstream the secrets perms-heal unit as an optional `secretsDir` option +
   heal unit (module owns the coturn-group and per-file-mode knowledge).
   **→ open — await owner go**
6. Parameterize `verify-live.sh` (strip host literals) into this repo as the
   companion to `docs/deploy.md` §5.
   **→ open — await owner go**
7. ~~Extend it with the messaging arm: `/recent` without token must 401/403~~ **NOT-DO — stays downstream — tracked in the downstream TODO.**
   ~~(tracked downstream).~~
8. Owner decision: kexec-installer framework core — upstream here, fleet
   tooling, or stays private.
   **→ open — owner call (g.3)**
9. If 8 = upstream: extract `pack-initramfs.nix` + the RAM-envelope gate as
   machinery shared with `checks.telephony-metal-boot` and
   `packages/initrd-audit`.
   **→ open — conditional on 8**

**Verification debts this session created (do before executing any move):**

10. ~~Read the unread tail (~120 lines) of the downstream `backup.nix`~~ done — tail read 2026-09-29 — retention-8, 26h freshness, 85% disk headroom, 1 GiB MMS guard and the journal-only relay all confirmed in code
    ~~(retention, freshness check, alert relay) — recommendation 1's scope~~
    ~~depends on it.~~
11. ~~Read `modules/telephony/options.nix`; verify option-name freedom for the~~ done — backupStaging and secretsDir absent from modules/telephony/options.nix — both names free (checked 2026-09-29)
    ~~proposed surfaces.~~
12. ~~Read webphone `package/nixos-module.nix` hunting nginx/TURN assumption~~ done — package/nixos-module.nix read 2026-09-29 — upstream ships an OPTIONAL nginx vhost generator (nginx.* options); no active collision, but a guard row (force nginx.enable = false) went to TODO_LIST
    ~~overlap with `web.nix` (split-brain sweep behind the "nothing" verdict).~~
13. ~~Read webphone `nix/vm-tests.nix` + `nix/module-check.nix` to close the~~ done — nix/vm-tests.nix (KVM backup-drill suites) and nix/module-check.nix (eval/build gate) read 2026-09-29 — no further nginx/TURN hardcoding beyond the nginx.* option family
    ~~evidence gap.~~

**Already-tracked rows observed this session (do NOT duplicate at harvest —
listed because the session surfaced them as adjacent):**

14. ~~Verify this repo's CI verdict on main HEAD `3c87f80` (tracked downstream~~ done — answered 2026-09-29 — both runs (36262573684, 36501187472) were canceled by runner-shutdown signals while green; re-verify row in TODO_LIST
    ~~TODO §8, but it is about THIS repo — candidate to re-home here).~~
15. ~~Messaging VM test (receiver + inbound bridge against a stub webphone) —~~ **NOT-DO — stays downstream — tracked there.**
    ~~tracked downstream.~~
16. ~~`docs/ops-runbook.md` messaging-bridge section — tracked downstream.~~ **NOT-DO — stays downstream — tracked there.**
17. ~~`docs/deploy.md` §3: add the three messaging secret files — tracked~~ **NOT-DO — stays downstream — tracked there.**
    ~~downstream.~~
18. ~~Derived default for `operator.smsMessageStore` when messaging is enabled~~ **NOT-DO — stays downstream — tracked there.**
    ~~— tracked downstream.~~
19. ~~Webphone upstream: gateway webhook secret read from a file (kills the~~ **NOT-DO — webphone repo — tracked there.**
    ~~two-file sync dance) — tracked downstream.~~
20. Add the webphone app (`/healthz`) to the `telephony-health` probe set —
    this repo TODO.
    **→ open — TODO_LIST row**
21. Eval-time fail2ban-regex check over both shipped filters — this repo TODO.
    **→ open — TODO_LIST row**
22. Webphone lock-bump runbook section in `docs/ops-runbook.md` — this repo
    TODO.
    **→ open — TODO_LIST row (extended with the upstream command-sheet alignment)**
23. ~~Relock this repo's webphone input (the lowercase shared-contacts assert~~ done at `3c87f80`
    ~~is RED at the old lock BY DESIGN) — this repo TODO, IN_PROGRESS.~~
24. Operator hardening: narrow the FS-state ACL group + dedicated
    stream-token secret — this repo TODO.
    **→ open — TODO_LIST row**
25. Cut v0.3.0 — this repo TODO (blocked on owner timing).
    **→ open — TODO_LIST row (blocked on owner timing)**

**Downstream-side observations (stay downstream; for context only):**

26. ~~Deploy the staged migration train (user, ssh) — downstream TODO §1.~~ **NOT-DO — stays downstream (deploy lane).**
27. ~~Republish the kexec-installer release (STALE vs tree) — downstream §6.~~ **NOT-DO — stays downstream.**
28. ~~`telnyx/desired.json` schema unit pinned to the engine's~~ **NOT-DO — stays downstream.**
    ~~REQUIRED_DESIRED_KEYS contract — downstream TODO §8.~~
29. ~~Downstream `AGENTS.md` slimming toward the ~377-line budget (currently~~ **NOT-DO — stays downstream.**
    ~~ ~2.2x over) — downstream TODO.~~ → corrected 2026-09-30 — the
    markers_check monotonicity arm caught the 2026-09-29 auto-commit
    normalizing the strike tail's leading tildes into a fenced code
    block; strike restored in a fence-immune shape (space after the
    opening pair).

**Process:**

30. ~~HARVEST this section into `TODO_LIST.md`/`ROADMAP.md` with repo-path~~ done (docs-health pass 2026-09-29)
    ~~evidence only (never this snapshot — docs-drift alarm rule), skipping~~
    ~~already-tracked rows 14–25 re-homed as needed.~~

## g) Questions the owner must answer (cannot be figured out)

1. **Backup doctrine fork.** The module ships restic PUSH backups; production
   runs staging + PULL (a compromised PBX holds zero target credentials, by
   explicit doctrine). Round 2 forces a choice: dogfood the module's restic
   path in production, or retire the restic option and upstream
   staging+pull as the one supported story? Both are defensible; they are
   mutually exclusive philosophies, and the current state (both maintained,
   neither reconciled) is the worst option.
   **→ open — owner fork (dogfood restic vs staging+pull)**
2. **Round-2 timing.** Execute the moves now, or park until the pending
   deploy + verification backlog clears (staged train, CI verdict on
   `3c87f80`, live proofs)? Moving now stacks a second staged train on top
   of an undeployed one and re-runs the whole relock ritual mid-backlog.
   **→ open — owner timing call**
3. **Installer appetite.** Make the kexec self-install framework public in
   this repo (parameterized by consumer config), keep it private, or extract
   to shared fleet tooling? Publishing the install path and taking on its
   maintenance publicly are owner-only calls.
   **→ open — owner call (publish / private / fleet tooling)**

---

_Snapshot per the status-report convention: annotate, never rewrite. This
report's own §f is the input for a docs-health HARVEST once the owner gives
the go._
