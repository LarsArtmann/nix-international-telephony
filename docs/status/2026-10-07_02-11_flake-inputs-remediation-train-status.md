# Flake-inputs remediation train — execution status (2026-10-07 02:11)

**Scope of this snapshot:** the M01→M08 execution session against
`docs/planning/2026-10-07_00-38_SUPERB-flake-inputs-remediation-pareto-plan.md`.
Point-in-time report of what this one session did, broke, and left
open. Git state at write time: `main` **ahead 4** (all unpushed),
working tree clean, `stash@{0}` holds the M02 ritual files, machine
load ~38 (sibling-session build storm all night, 16 crush instances).

## a) Fully done (verified this session)

- **M01 — CI eval step budget: ALREADY LANDED, verified.** Heuristic
  commit `c01f3a1` (2026-10-06 23:10, prior session) contains the
  exact 20→60 `timeout-minutes` raise + why-comment citing runs
  37482412349/37528539317 + CHANGELOG + runbook entries. Verified
  live: both in-progress origin runs passed the 20-minute step-kill
  point that killed their predecessors (37540403627 alive at 20m17s;
  prior failures died at 20m36s/20m37s).
- **M03 — preventive lock-move tripwire: LANDED (`e72d54e`).**
  `scripts/lock_move_hook.py` (commit-msg stage, 6 self-test arms:
  unmarked blocks, marker passes, spelling variant, unrelated, untracked
  input, unreadable message), wired in `flake.nix`
  (`always_run` + default `pass_filenames` — the plan's
  `files`/`pass_filenames=false` shape is unworkable at commit-msg and
  the deviation is documented in the commit), heal script extended to
  install BOTH stages (a heal dropping commit-msg would silently
  disarm the tripwire), hooks were LOST again (samples-only
  `.git/hooks`) and healed before wiring, arms proven LIVE: a staged
  fake webphone-rev move + heuristic message blocked via
  `pre-commit run` AND via a real `git commit` (exit 1, nothing
  committed); marker message passed; fake lock restored to `d84df26`.
  AGENTS.md paragraph added. Attribution: the wiring was daemon-swept
  as `bb8f11d` pre-hook-install; soft-reset + hand-re-authored.
- **M04 — changelog-headings hermetic check: LANDED (`4c89feb`).**
  `tests/changelog_headings.py` gained `--self-test` (4 arms: clean,
  decayed, per-version scoping, pre-version preamble);
  `checks.changelog-headings` mirrors the lock-guard shape
  (self-test then live sweep). Negative arm proven on the DERIVATION:
  an exact duplicate `### <type>` heading planted inside [Unreleased]
  made `nix build` of the check FAIL with the pointing message;
  CHANGELOG restored afterwards. Attribution: daemon-swept as
  `bc4fbbe`; soft-reset + hand-re-authored.
- **M05 — statix/deadnix onto treefmt: LANDED (`0ba2f0b`).**
  Equivalence proven BEFORE deleting anything: statix with
  `statix.toml` = 0 findings, without = 352 `repeated_keys` warnings —
  `disabled` is the only load-bearing field (`ignore`/`nix_version`
  changed nothing); `programs.statix.disabled-lints` reproduces the
  exact surface. deadnix autofix proven live: a planted unused let
  binding was removed by `nix fmt` under the new programs.
  `checks.statix`/`checks.deadnix` deleted, both pre-commit hooks
  dropped (nixfmt kept), `statix.toml` retired. Check set: 35 checks,
  `format` green. Also solved the stale-battery bite: the old
  `.pre-commit-config.yaml` store symlink (old hooks + deleted
  statix.toml) blocked the first commit attempt; devshell re-entry
  regenerated it.
- **M07 — Paperless seam verdict: NO-GO, LANDED (`c524985`).** Upstream
  seam read at the pinned rev: `settings.paperless.{url,token}`,
  both-or-neither with boot-failing closed, fire-and-forget archiving
  (slow/dead Paperless never delays or fails a fax). Zero Paperless
  references anywhere in this stack (hosts, prod template, docs — the
  only hit is the runbook's description of upstream exit codes).
  FEATURES.md "Planned" row records the verdict, the TODAY escape
  hatch (freeform settings + `WEBPHONE_PAPERLESS__TOKEN` via
  `services.webphone.environmentFiles`), and the GO trigger.
- **M08 (render arm) — VERIFIED, no fixes needed.** Headless chromium:
  screenshot rendered (417 KB pixels); `--dump-dom` + console capture
  shows ZERO page errors (the single console line is chromium's own
  dbus/UPower noise); DOM stack-balance identical source vs rendered
  (0/0, 15 ids, 50 classes both) — no dead CSS, no layout-destroying
  script path. Remaining M08 work is only the final TODO truth pass,
  which is gated on M06's CI verdict.
- **M02 gates: ALL GREEN except the browser E2E retry.** Selector
  pre-check 30/30 selectors present at `f0772e1` (including
  `article.wp-row`, whose first "miss" was my needle bug — CSS
  selector vs bare class name); binary `webphone-2.8.0` builds at
  BOTH `f0772e1` and `d84df26`; fast gates green (nix fmt,
  telephony-eval, markers-check 72/0, drift alarm, lock-guard PASS
  after the CHANGELOG entry); VM suites green: telephony-webphone
  (incl. configjs contract), webphone-empty-secret, messaging,
  fax-feed; browser E2E run #1 RED under the load-44 storm and
  EXONERATED per the runbook protocol (below).
- **Fifth lock sweep absorbed.** `98323e2` (daemon, 01:04) moved the
  lock `f0772e1 → d84df26` mid-ritual. Verified docs-only (28 markdown
  files, ZERO code files vs `f0772e1` — same binary, same module
  surface, same DOM; binary rebuild at the new narHash confirms the
  same version literal). Adopted rather than pinned back; the
  CHANGELOG entry in the stash names `3928dbd1 -> d84df26` and all
  five sweep incidents. The sibling-session formatter reflow of
  TODO_LIST/plan (prettier) and my hook script (ruff-format) verified
  content-equivalent before accepting.

## b) Partially done

- **M02 — relock ritual, one gate and one commit short.** Done:
  everything in a) plus the TODO lock-sweep row deletion (staged in
  the stash). Missing: (1) the browser E2E GREEN retry — run #1
  failed at the `CONTACTS-ROUNDTRIP-OK` marker, exoneration evidence
  on record: ALL server-side contacts requests returned 200
  (`GET /partials/contacts`, `POST /contacts/save`,
  `POST /contacts/delete`), the restart drill took 30.18 s under load
  (webphone's graceful-shutdown deadline expired → classified
  exit-1 → island reconnect storm), and the whole phase chain drifted
  past the 180 s marker deadline — the runbook's FOUC class
  (red-under-load is not attribution); (2) `stash pop` + the
  hand-authored M02 commit (marker `relock:`) + drift gate. The
  ritual files sit in `stash@{0}` because the daemon swept
  `CHANGELOG.md` once already (`3c3faa2`, pushed — attribution of the
  intermediate entry eaten; the stash copy is the completed
  `d84df26`-naming version).
- **M06 — not started (hard-blocked on M02's commit).**

## c) Not started

- **M06 verification capstone:** full-mode buildflow to the documented
  green shape (exactly the 4 port-collision findings), push of the
  4-commit train (currently `ahead 4`), airtight `gh run view`
  verdict, deep-dive report addendum (M01–M08 resolutions), TODO row
  22 close-out with the run id.
- **Origin verdict check for the runs that were in flight at session
  start** (37542131268 on the plan head): never read their final
  state; the expectation stands (they should be RED on lock-guard,
  NOT on the eval step).
- **Post-train AGENTS.md truth-ups:** the Commands/Conventions lines
  still describe statix+deadnix as checks and battery members.

## d) Totally fucked up (this session's own errors)

- **Pipe-eaten exit code produced a false green:** `nix build ... |
  tail; echo $?` reported `BROWSER_EXIT=0` for a FAILED browser suite
  — the exact documented trap, violated anyway. Consequence: for a
  few minutes the CHANGELOG entry claimed "browser E2E green" before
  any green existed. Caught within minutes from the run log; the
  false claim lives only in the STASH (uncommitted) and was corrected
  there. No unverified verdict landed in git.
- **The load-gated E2E retry watcher was LOST:** an interrupted
  `job_output` call killed background shell 03E; discovered gone at
  this report. ~50 minutes of load-gating produced no retry. The
  retry must be re-armed with a detached runner (nohup + log file),
  not a background shell.
- **Daemon race losses:** three sweeps hit mid-work (`3c3faa2` ate
  CHANGELOG + the hook script; `98323e2` carried the fifth lock move;
  `bb8f11d`/`bc4fbbe` ate the M03/M04 edits). Two recovered by
  soft-reset + re-author while unpushed; `3c3faa2` was already pushed
  — its attribution loss is permanent (documented, accepted).
- **Hooks were silently absent at session start** (samples-only
  `.git/hooks/`): every daemon commit until 01:20 ran ungated.
  Discovered only while wiring M03 — should have been the FIRST check
  of a session that planned to rely on gates.
- **First negative-arm plant was malformed:** a bare `### Changed`
  next to a suffixed heading is NOT a full-line duplicate, so the
  check correctly passed and my arm read as a false negative
  ("NEG=0, want nonzero"). Replanted an exact duplicate → real FAIL.
  Lesson: construct negative arms against the code's actual
  comparison key, not a lookalike.

## e) What to improve

- Exit-code discipline is non-negotiable: `PIPESTATUS[0]` or
  redirect-to-file-then-`$?`; never `| tail; echo $?`.
- Long waits must run DETACHED (nohup/setsid + log file), because
  interrupted tool calls kill background shells silently.
- After editing `pre-commit.settings.hooks`, regenerate the battery
  (`nix develop -c true`) BEFORE the next commit — the stale store
  symlink runs the OLD hook set against the NEW tree shape.
- Check hook presence at session START whenever gates matter to the
  plan (`ls .git/hooks | grep -v sample`), not incidentally.
- Write verdicts into durable docs only after they exist; the ritual
  held only because the stash delayed the commit.
- Negative arms must target the exact matching key (full heading
  line; selector vs class-name needle).

## f) Next (execution order)

1. Re-arm the browser E2E retry as a DETACHED load-gated runner
   (threshold ~15–20, log to /tmp, survives tool-call interrupts).
2. On GREEN: `stash pop`, hand-author the M02 commit (`relock:`
   message naming `3928dbd1 -> d84df26`, the five sweeps, every gate
   verdict), run drift + lock-guard + markers, verify the commit
   passes the new commit-msg tripwire.
3. If RED again at sane load: adjudicate per the runbook (rerun once;
   a second red at matched phase = real regression → forward-pin or
   fix lane).
4. M06: `buildflow --build-mode full --max-time 60m` → expect exactly
   the 4 documented port-collision findings, nothing else.
5. Push the train (`ahead 4` + M02 + M06 commits).
6. Airtight origin verdict: `gh run view <id> --json
   headSha,status,conclusion,event,jobs`; cancel ≠ red; read step
   timestamps on any anomaly.
7. Deep-dive report addendum (append-only): M01–M08 resolutions with
   commit ids, the fifth-sweep incident, the E2E flake exonvention.
8. Close TODO row 22 (CI-gate green) with the run id as evidence.
9. Final TODO truth pass (M08) + drift/markers/lock-guard sweep.
10. AGENTS.md truth-ups: battery list (statix/deadnix hooks gone,
    commit-msg stage added — already noted), statix.toml retirement,
    treefmt programs as the lint surface.
11. Read the origin verdicts of the in-flight session-start runs
    (37542131268 era) for the record.
12. Consider an operator note in docs/ops-runbook.md: after battery
    edits, regenerate `.pre-commit-config.yaml` before committing.
13. Upstream observation worth reporting (owner lane): the E2E
    restart drill surfaces a 30 s graceful-shutdown deadline that
    exits 1 under CPU starvation — benign for systemd (retry loop)
    but noisy in classified-boot terms.
14. Post-train: v0.3.0 release readiness summary for the owner
    (CHANGELOG [Unreleased] is release-shaped already).

## g) Questions for the owner (cannot be resolved from here)

1. The machine has hosted a 16-instance sibling-session build storm
   all night (load 38–106). Should the E2E retry keep waiting for a
   quiet window (could be hours), or launch immediately and accept
   runbook-adjudicated flake handling if it reds under load?
2. The FIFTH lock sweep came from an unidentified LOCAL
   `nix flake update` execution (the documented mystery class). Hunt
   the source with system-level auditing, or is the new commit-msg
   tripwire sufficient containment?
3. Once the train is green at origin: cut v0.3.0 immediately, or hold
   it behind the first-real-deployment close-out lane as originally
   gated?
