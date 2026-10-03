# CDR suite rescue, lock attribution, and daemon races — session status

Session 2026-10-03 ~00:42–02:09 CEST, resuming the paused handoff with
execution authority ("fix nix build" → lock-guard attribution → full ritual).
This snapshot reports THIS session only; the 00:35 report covers the gate
ladder evidence at tip `f27525b6`.

## a) FULLY DONE

1. **Lock-guard attribution restored.** CHANGELOG [Unreleased] entry naming
   the full chain `ffaa03fd5ce5 → 35688a171988 → 66f16ad1f5a4 →
   f27525b693e5` (sweeps 2026-10-02 11:18/13:51/13:56) plus the gates run.
   Evidence: commit `2f24aad`; `python3 scripts/lock_guard.py` PASS;
   `nix build .#checks.x86_64-linux.lock-guard --no-link` exit 0.
2. **Scrub gate unblocked.** The 2026-10-02 hook-gap report QUOTED the
   pattern-flagged DID literal it described scrubbing, so every commit was
   blocked at pre-commit. Replaced the quote with a description per the
   `2823913` precedent. Evidence: commit `61eea9b`, scrub-check Passed on
   every commit since. The literal remains in PUSHED history (`a0c78ca`,
   landed through the hook gap) — owner decision, see §g.
3. **Sweep forensics closed (as close as facts allow).** The committer
   daemon is `projects-management-automation` (config read: auto_stage,
   on-change, `/home/lars/projects`, auto_push false) — it only stages and
   commits, never runs nix. All three sweep lock-diffs moved ONLY the
   webphone node: webphone-scoped `nix flake update webphone` executions
   (runbook gate-1's own command — interrupted relock attempts from
   sibling sessions, no scheduler; crush-daily and PMA ruled out by
   config/timing). Recorded in AGENTS.md and the runbook. Evidence:
   commits `c6877c3`, `379f359`.
4. **flake-update workflow fixed and its two failures root-caused.**
   Sep 1 run: update step SUCCEEDED, `gh pr create` blocked — the repo
   setting "Allow GitHub Actions to create and approve pull requests" is
   off (owner toggle; branch `chore/flake-update-2026-09` was pushed and
   lingers on origin). Oct 1 run: runner shutdown mid-eval (infra-kill
   class). Fix: the bot now refreshes every top-level input EXCEPT
   webphone (ritual-gated; semantics PROVEN in a scratch clone: full
   update moves webphone, the all-but-webphone set leaves the lock
   untouched) and a PR-open failure keeps the pushed branch while naming
   the settings toggle and the compare URL. Evidence: commit `60b16fb`.
5. **The never-green `telephony-cdr-cancel` saga closed.** Independently
   re-derived AND found pre-documented (2026-10-01 17:28 collision
   report: suite never green, relock exonerated, "fs_cli premise is
   dead"). This session added the mechanism: (a) unregistered ring-group
   members fail `bridge(user/…)` INSTANTLY (`USER_NOT_REGISTERED`) and
   `continue_on_fail` hands the caller to answer+voicemail — the
   originate lands `+OK` in ~0.2s, never `-ERR` after 5s; (b) LOOPBACK
   channels never reach mod_cdr_csv at all (interactive-driver probe:
   loopback originate wrote zero Master.csv rows; the same call through
   a real sofia self-INVITE wrote rows immediately) — the old harness
   was CDR-blind from birth. Restructured as `telephony-cdr-visibility`
   on the sofia-leg harness: GREEN, deterministic (2× runs + suite run).
   Evidence: commit `78025ec` (squash of the restructure incl. two
   daemon heuristic commits), TODO row 45 updated, lesson recorded in
   docs/lessons/freeswitch.md (`379f359`).
6. **Knowledge + snapshot hygiene.** The 00:35 report's open items
   annotated (ritual done, forensics done, other-inputs premise
   corrected — the sweeps moved only webphone); markers gate green (72
   files, 0 findings). The docs-drift alarm caught a dead path citation
   from the rename (TODO row citing the old file) — fixed in `4cf107b`,
   drift check exit 0.
7. **Eight hand-authored commits landed** (`61eea9b`, `2f24aad`,
   `60b16fb`, `c6877c3`, `33331a5`, `78025ec`, `379f359`, `4cf107b`),
   each with full rationale; tree clean at report time; lock tip
   unchanged at `f27525b6` across the whole session.

## b) PARTIALLY DONE

1. **Full `nix flake check` — round 3 RUNNING at report time.** Round 1
   failed at telephony-cdr-cancel (see a5; the failure was the
   discovery). Round 2 failed at docs-drift (dead path citation, fixed
   same session). Round 3 in progress (telephony-monitoring VM check
   building when this report was written). open remainder: green exit
   code, then §c1. Blocker: VM wall time (~20–60 min). Effort: S (wait).
2. **Push + CI verdict.** Branch is 10 commits ahead of origin/main and
   push-ready; blocked on b1 (pushing before a green local check would
   hand CI a known state). Note: a sibling-dispatched CI run is testing
   the PRE-fix origin/main (`4eab1bf`) and will legitimately go red on
   lock-guard — its headSha distinguishes it; my push supersedes.
   open remainder: push, `gh run view` airtight verdict. Effort: S.

## c) NOT STARTED

1. **docs-health HARVEST of this report's §f** (and the 00:35 report's
   still-unharvested §f) into TODO_LIST/ROADMAP. Not started: prior
   user instruction said wait; this report's §f is the input. Priority:
   medium.
2. **Live-host mid-ring ORIGINATOR_CANCEL repro** (TODO row 45 next
   step: journal the cancelled call, `uuid_dump` CDR vars, then decide
   the honest fix). Not started: needs the live deployment, not this
   tree. Priority: high (row is High).

## d) TOTALLY FUCKED UP

1. **The daemon raced EVERY hand-off (4 heuristic commits this
   session).** It committed the CHANGELOG edit 7 s before the ritual
   commit; it took the restructured test files mid-rename; it took the
   AGENTS/runbook edits. Two soft-reset re-authors and one 3-commit
   squash were needed. Severity: the exact unattributed-landing class
   the runbook exists to prevent nearly recurred three times.
   Mitigation: the race remedy is now documented (AGENTS.md + runbook);
   root fix is owner-side (see §g/§f).
2. **The PIPESTATUS/tail trap struck AGAIN.** Round 1 of the full check
   printed `FLAKE-CHECK-EXIT=0` (tail's exit) while cdr-cancel was
   deterministically red inside. Caught only by distrusting the shape;
   the incoming handoff had explicitly warned about this shell quirk.
   Severity: a green lie on the CI gate. Mitigation: redirect-to-file +
   unpiped `$?` used ever since; process fix in §e.
3. **Premature "done" annotation.** I marked the 00:35 report's §c1
   "done: green" while the check was still running, then had to correct
   it to "running/pending" before committing. Claim-before-evidence in a
   durable doc — the exact pattern AGENTS.md warns about
   (reconstructed/anticipated facts).
4. **Wasted forensic cycles on a solved problem.** I re-derived the
   never-green verdict with two killed bisect builds (scratch clones at
   old nixpkgs and at d8bd34c) AFTER the repo's own 2026-10-01 17:28
   report had already proven it — I read the historical reports too
   late. Along the way I chased two wrong theories (webphone delta;
   nixpkgs FreeSWITCH semantics — the fs store path is IDENTICAL across
   both nixpkgs revs, which killed the theory the moment I checked it).
5. **A never-green check sat in the CI gate for two days** because the
   17:28 report's "restructure or remove (owner/sibling lane)"
   recommendation never became a TODO row — the finding was entombed in
   a timestamped report instead of harvested. This session only found it
   by collision. (The HARVEST loop exists precisely to prevent this.)

## e) WHAT WE SHOULD IMPROVE

1. **Read the repo's own recent status/planning reports BEFORE external
   forensics.** 30 minutes of bisect/probe work this session was
   pre-answered in `docs/status/2026-10-01_17-28_*.md`. Impact: hours.
   Fix: forensic sessions start with a docs/status mtime scan of the
   last 72 h.
2. **Never trust piped exits for gate verdicts** (recurrence #2 across
   two sessions). Fix: always `cmd > log 2>&1; echo $?` unpiped; or a
   `scripts/gate.sh` wrapper that does this once.
3. **Scrub-narration anti-pattern:** a report describing a scrub fix
   must not quote the scrubbed literal — the pattern matcher hits the
   quotation and blocks the tree (this is exactly how the Oct-2 gap
   report re-leaked). Describe, never quote. Candidate for the
   scrub-check script to lint (warn on `example \`<digits>\`` inside
   scrub-narration lines).
4. **Owner-lane recommendations from collision reports must land as TODO
   rows the same session** (the d5 failure). HARVEST discipline.
5. **The daemon race needs an owner-side lever** — a PMA exclude-path
   for this repo during rituals, or a pause command. Four races in one
   session is systemic, not bad luck (60 s debounce vs multi-minute
   verify loops).

## f) Next tasks (ranked; brainstorm-grade beyond the top rows)

| #  | Task                                                                                                                                                                                                            | Impact   | Effort | Category       |
| -- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------ | -------------- |
| 1  | Confirm full check round 3 green (running, shell 06A); if red, triage from /tmp/full-check2.log                                                                                                                 | Critical | S      | Bug            |
| 2  | Push the 10-commit stack; airtight CI verdict via `gh run view` (canceled ≠ red protocol; expect the sibling dispatch run on `4eab1bf` to be red on lock-guard — its headSha predates the fix)                  | Critical | S      | Quality        |
| 3  | OWNER: enable "Allow GitHub Actions to create and approve pull requests" (Settings → Actions → General) so the monthly refresh PR can open (next fire Nov 1; manual workflow_dispatch to verify after flipping) | High     | S      | Infrastructure |
| 4  | OWNER: decide history surgery for the DID literal in pushed history (`a0c78ca`, public on GitHub) — `scripts/scrub-check.sh --history --strict` first; if rewriting, re-run after (pickaxe counts removals)     | High     | M      | Security       |
| 5  | OWNER: decide the missed-call product shape — instant voicemail failover (current semantics for all-unregistered ring groups) vs dialplan change to keep ~25 s ring; affects live callers                       | High     | M      | Product        |
| 6  | Delete stale origin branch `chore/flake-update-2026-09` (superseded Sep artifact)                                                                                                                               | Low      | S      | Cleanup        |
| 7  | docs-health HARVEST: this report §f + the 00:35 report §f into TODO_LIST/ROADMAP                                                                                                                                | Medium   | M      | Documentation  |
| 8  | Live-host CDR repro per TODO row 45 (journal + `uuid_dump` on a real cancelled call) then the honest fix decision                                                                                               | High     | M      | Bug            |
| 9  | Consider a lock_guard WARNING arm for nixpkgs moves (685ee2e smuggled a full update under a webphone-shaped attribution)                                                                                        | Medium   | S      | Quality        |
| 10 | Add `scripts/lock-doctor.py` to AGENTS.md Commands (it exists; only the runbook mentions it)                                                                                                                    | Low      | S      | Documentation  |
| 11 | Add a small CHANGELOG note attributing the nixpkgs bump `b4fd65b1 → c59305ba` that rode 685ee2e unattributed                                                                                                    | Medium   | S      | Documentation  |
| 12 | Watch for the NEXT webphone sweep (upstream main is already at `f8d2edbdc78f`): when it lands, the relock ritual applies; consider a proactive forward-pin at a quiet time instead                              | Medium   | M      | Maintenance    |
| 13 | Record the interactive-driver probe technique (build `driverInteractive`, pipe a self-contained script into the REPL stdin) in docs/lessons/vm-testing.md — it cracked the CDR case in minutes                  | Medium   | S      | Documentation  |
| 14 | FEATURES row "Call detail records" can now NAME the proving check (`telephony-cdr-visibility`) instead of "VM test asserts a row"                                                                               | Low      | S      | Documentation  |
| 15 | Serialize VM suites vs browser E2E automatically (a tiny runner script honoring the run-alone lesson) instead of by memory                                                                                      | Medium   | S      | Quality        |
| 16 | Ask owner about a PMA pause/exclude lever for this repo during relock rituals (§e5)                                                                                                                             | Medium   | S      | Process        |
| 17 | Re-verify the flake-update workflow end-to-end (workflow_dispatch) once the PR-creation toggle is flipped; expect an "inputs already up to date" no-op unless non-webphone inputs moved                         | Medium   | S      | Quality        |
| 18 | Instrument/audit the local `nix flake update webphone` actor (the sweep source is narrowed to local runs but no session owns it; sibling session logs under .crush/shell-output only cover this project's cwd)  | Medium   | M      | Investigation  |
| 19 | Re-run `vantage_probe` / `whatsapp_probe` from several machines per their docstrings (drift check on provider behavior)                                                                                         | Low      | M      | Maintenance    |
| 20 | Consider asserting the exact two-row shape (caller + failover leg) in cdr-visibility once it has a few green runs behind it (currently asserts ≥1 row mentioning "2000")                                        | Low      | S      | Quality        |
| 21 | The 2026-10-02 11-06 report's §f (12 items) is still unharvested — fold into the same HARVEST pass as f7                                                                                                        | Medium   | S      | Documentation  |
| 22 | If history surgery happens (f4): re-run markers-check git-history monotonicity arm after the rewrite (verdict counts must not drop)                                                                             | Low      | S      | Quality        |

## g) Questions I cannot answer myself

1. **History surgery or accept-and-rotate?** The pattern-flagged DID
   literal sits in PUSHED, public main history (`a0c78ca`, landed through
   the pre-commit hook gap on 2026-10-02; pushed same day). I cannot
   rewrite remote main, and scrub-check's own guidance defers to the
   owner. If it is a live number: rewrite (I can prepare the
   filter-repo plan + post-surgery gate list) or rotate the number and
   accept the history?
2. **Flip the Actions PR-creation toggle?** The monthly flake refresh can
   never open its PR until "Allow GitHub Actions to create and approve
   pull requests" is enabled (Settings → Actions → General). I have no
   repo-settings access. Enable it, or should the workflow instead push
   a branch only and you open the PR by hand monthly?
3. **Is instant voicemail failover the accepted missed-call shape?**
   Since the current stack semantics, a call to an all-unregistered ring
   group reaches voicemail after ~0.2 s instead of ringing ~25 s. I can
   change the dialplan (e.g., drop `continue_on_fail` for
   USER_NOT_REGISTERED, or force a ring window) — but whether callers
   SHOULD hear ringing first is a product call only you can make.

— Session paused here per instruction; full check round 3 still running
in background (shell 06A); nothing pushed.
