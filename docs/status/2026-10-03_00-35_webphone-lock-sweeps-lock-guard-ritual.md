# Status Report — 2026-10-03 00:35: webphone lock sweeps vs. lock-guard ritual

Session scope: user request "fix nix build". Everything below is what this
session did and noticed — no unrelated backlog research. The headline: `nix
build` itself was never broken; the actual red is `checks.lock-guard`, and its
root cause recurred for the THIRD time in three days (daemon lock sweeps past
the last documented webphone rev). The full lock-bump gate ladder was run at
the current lock tip and is green; only the CHANGELOG attribution entry and
the hand-authored commit remain, held per "WAIT FOR INSTRUCTIONS".

## a) FULLY DONE

1. **Failure triage, isolated to one check.** `nix build` (default attr),
   `nix build .#webphone`, `nix build .#freeswitch-sounds` all exit 0;
   `nix flake check --no-build` eval-green (all x86_64 checks evaluate,
   "all checks passed"). Building every cheap non-VM check individually
   isolated the single failure: `checks.x86_64-linux.lock-guard` with its
   exact message: tracked input 'webphone' sits at rev f27525b693e5, but
   CHANGELOG.md never mentions it.
2. **Root-cause archaeology (git history of flake.lock).** After the
   hand-authored relock d8bd34c (webphone f706575b) and the 2026-10-02
   morning attribution restore (documented tip ffaa03fd5ce5), the
   auto-commit daemon swept the webphone input THREE more times, all with
   heuristic messages: ffaa03fd5ce5 to 35688a171988 (a0c78ca, 11:18),
   to 66f16ad1f5a4 (f61e9f0, 13:51), to f27525b693e5 (4eab1bf, 13:56).
   This is lock-guard's exact incident class, third recurrence
   (2026-09-24, 2026-10-02 morning, 2026-10-02 midday).
3. **Upstream rev verification.** All four revs resolve in the webphone
   checkout and `git merge-base --is-ancestor <rev> origin/main` passes for
   each (after `git fetch origin`) — real upstream main commits, not lock
   corruption.
4. **Upstream delta inspection (ffaa03fd5ce5..f27525b693e5).** 40 commits,
   112 files, +10963/-1684. Substantive: a00dadc (message organization,
   snippet replies, trust feedback seams), 65b7f0d (boot failures classified
   through the error-chain, not top text), 66f16ad (T23 close-out, two
   harness-found product fixes); remainder daemon chores, docs, and 14 new
   ui-shots PNGs. Markup delta is REAL: 7 templ files changed (messages
   +277, settings +88, fax +78 lines) and shell.js +453 — so the browser
   E2E gate was mandatory, not optional.
5. **DOM-contract pre-verification (before the E2E, per AGENTS.md).** All
   six ids asserted by tests/browser-e2e.py (log, login-error, login-view,
   phone-view, calls, incoming-call) exist in internal/web/views/phone.templ
   at f27525b693e5; .call-state-text and .transfer-row exist in the calls.js
   island sources. Verified via `git grep <rev> -- internal/web`.
6. **Gate ladder at lock tip f27525b693e5 — ALL GREEN:**
   - Binary proof: `nix build .#webphone` exit 0, store path
     /nix/store/l640x9val4i6lvnjz7af9xfm0avr5asy-webphone-2.8.0
     (version literal unchanged; revs are the citation, not versions).
   - Fast gates: eval check green; format, statix, deadnix, docs-drift,
     markers-check, pre-commit, browser-e2e-pycompile, telephony-eval,
     telephony-failregex, initrd-audit checks all built green.
   - Stdlib suite: `python3 -m unittest tests.test_telnyx_bridge
     tests.test_telnyx_reconcile tests.test_operator_sms
     tests.test_voice_agent` — 122 tests, OK.
   - VM suites: telephony-webphone, telephony-fax, telephony-fax-feed all
     exit 0 (first run real, re-verified exit 0 cached).
   - Browser E2E: legacyPackages.telephony-browser exit 0, run ALONE after
     the three VM suites finished (heeding the 2026-10-02 stall lesson —
     no stall this time).

## b) PARTIALLY DONE

1. **Lock-bump ritual for the current tip.** All gates green (evidence in
   a6), but the two finishing moves are NOT done: the CHANGELOG.md
   [Unreleased] attribution entry (old-to-new revs + why + gates run) is
   unwritten, and the hand-authored relock commit is unmade. open remainder:
   author entry, rebuild lock-guard check green, commit naming
   ffaa03fd5ce5 to 35688a171988 to 66f16ad1f5a4 to f27525b693e5.
   Blocker: user interrupt ("WAIT FOR INSTRUCTIONS"). Effort: S (~10 min).
   → done 2026-10-03: entry in CHANGELOG, lock-guard green locally and
   as a check build, ritual commit 2f24aad (re-authored over a daemon
   heuristic commit that landed 7 s earlier).
2. **"fix nix build" as literally asked.** The default `nix build` target
   was green before this session started. The red the user presumably hit
   (directly or via CI) is the lock-guard gate, which stays red until
   b1 completes. open remainder: same as b1.
   → done 2026-10-03: resolved by b1; lock-guard check build exit 0.

## c) NOT STARTED

1. **Full `nix flake check`** (realizing all ~25 VM-test checks, 20-60 min
   wall) at the new tip — only the webphone-relevant subset ran.
   Priority: high (it is the CI gate).
   → running 2026-10-03 (this session, post-report); verdict pending.
2. **Sweep-source hunt / prevention.** Something in this environment
   repeatedly moves the lock unattended (three sweeps inside ~2.5 h). The
   source was not identified, and no preventive mechanism exists beyond
   lock-guard's after-the-fact trip. Priority: critical (class-killer).
   → done 2026-10-03 (forensics, prevention partial): the auto-commit
   daemon (projects-management-automation) only stages/commits, never
   runs nix; the sweeps were WEBPHONE-SCOPED `nix flake update webphone`
   executions (all three lock diffs moved only the webphone node —
   runbook gate-1's own command, pointing at interrupted relock
   attempts from sibling sessions, not a scheduler; no timer matched).
   Prevention: the GitHub flake-update bot now excludes webphone
   (60b16fb); the local actor remains unidentified, lock-guard stays
   the gate. Recorded in AGENTS.md + the runbook.
3. **Identity check of the OTHER inputs** that moved in the same three
   daemon commits (non-webphone rev pairs changed alongside; which inputs
   exactly was not verified this session). Priority: medium.
   → done 2026-10-03: premise corrected — the sweeps' flake.lock diffs
   contain ONLY webphone rev/lastModified/narHash changes; no other
   input moved (verified per-commit against a0c78ca/f61e9f0/4eab1bf).
4. **HARVEST of this report's section f** into TODO_LIST/ROADMAP via
   docs-health — not run (user said wait). Priority: medium.

## d) TOTALLY FUCKED UP

1. **The recurring unattributed-lock-sweep class — third recurrence.**
   What is broken: the webphone flake input keeps moving under heuristic
   daemon commits with no hand-authored record; `nix flake check` (CI gate)
   is red until a full evidence ladder is re-run by hand. Severity: blocks
   CI; no deployed-host or data impact. Root cause: unattended
   `nix flake update`-style sweeps in this shared tree, auto-committed by
   the daemon faster than rituals land (the 2026-10-01 d8bd34c lesson
   "minimize the relock-to-commit window" is being violated BY THE
   ENVIRONMENT, not by the ritual). Mitigation: lock-guard catches it
   (working as designed — this session is the proof); prevention absent.
   At snapshot time the gate is STILL RED (ritual finishing moves held).

## e) WHAT WE SHOULD IMPROVE

1. **Prevent, don't just attribute.** A pre-commit-side rule (or daemon
   carve-out) that refuses to land flake.lock webphone-rev changes riding
   a heuristic "chore: auto-commit" message would kill the class at the
   source; lock-guard only bills us after the fact. Impact: this class has
   now cost three repair sessions.
2. **Re-verify lock identity immediately before authoring the CHANGELOG
   entry.** The E2E ran ~10 min unattended at the end; the lock could have
   swept again during it (not re-checked before this report — check before
   writing the entry). The ritual's own lesson, applied one step later
   than ideal.
3. **Shell quirk cost a verification round-trip:** `${PIPESTATUS[0]}` echo
   printed empty in this shell's for-loops (mvdan/sh), so suite exits were
   re-proven with unpiped `$?` reruns. Use unpiped commands + `$?` from
   the start.
4. **lock-guard ergonomics:** its FAIL line could parse CHANGELOG.md for
   the last attributed rev and print old-to-new directly, saving the
   git-archaeology step this session needed. Small script gain.

## f) Next tasks (from this session's observations, ranked)

1. Re-check flake.lock webphone rev right now; author the CHANGELOG
   [Unreleased] attribution entry for ffaa03fd5ce5 to 35688a171988 to
   66f16ad1f5a4 to f27525b693e5 (why: message organization / snippet
   replies / trust feedback seams, boot-failure error-chain
   classification, T23 close-out; gates: binary, fast, 122 stdlib,
   3 VM suites, browser E2E). Impact: Critical. Effort: S. Category: Bug.
2. Rebuild `checks.lock-guard` green, then the hand-authored relock commit
   (runbook convention: old-to-new revs + why + which gates ran).
   Impact: Critical. Effort: S. Category: Bug.
3. Full `nix flake check` at the new tip before pushing (all VM checks).
   Impact: High. Effort: L. Category: Quality.
4. Airtight CI verdict after push: `gh run view <id> --json ...` per
   AGENTS.md (a canceled run is infra, not code). Impact: High.
   Effort: S. Category: Process.
5. Identify the sweep source in this tree (sibling agent session, cron,
   interactive terminal, lock-doctor pre-flight?) — cannot be determined
   from inside this session. Impact: Critical. Effort: M. Category: Bug.
6. Preventive gate: reject heuristic-commit flake.lock webphone moves
   (pre-commit hook or daemon carve-out) so the ritual is the only path.
   Impact: High. Effort: M. Category: Quality.
7. lock-guard FAIL line should name the last attributed CHANGELOG rev
   (parse + print old-to-new). Impact: Medium. Effort: S.
   Category: Quality.
8. Verify which non-webphone inputs moved in the three sweep commits
   (jq-diff flake.lock a0c78ca^..4eab1bf); decide if any now "ride a
   moving upstream" enough to join TRACKED_INPUTS (policy: webphone-only
   today). Impact: Medium. Effort: S. Category: Quality.
9. Consider a project script encoding the lock-bump ladder
   (relock, build, fast gates, suites, E2E, changelog skeleton) to
   compress the ritual window toward zero. Impact: High. Effort: M.
   Category: Quality.
10. docs/lessons/operating.md: record the third recurrence, the sweep
    timestamps, and that the run-E2E-alone heuristic held again.
    Impact: Medium. Effort: S. Category: Documentation.
11. Confirm the 14 new upstream ui-shots PNGs are repo-docs only (not
    served assets our closure inherits). Impact: Low. Effort: S.
    Category: Quality.
12. docs-health HARVEST of this section f into TODO_LIST/ROADMAP once
    instructions allow. Impact: Medium. Effort: S. Category: Process.

## g) Questions I cannot answer myself

1. **Bless forward or roll back?** f27525b693e5 passed every gate this
   session ran. Default plan: bless forward (CHANGELOG entry + commit).
   If you prefer pinning back to the last documented rev ffaa03fd5ce5
   (restore-lock pattern like dc69b79), say so — the ladder evidence
   would then cover a rollback instead.
2. **What keeps sweeping the lock?** Three webphone moves inside ~2.5 h
   (11:18, 13:51, 13:56) were not started by me; their trigger (sibling
   agent session, cron, your own terminal) is invisible from inside this
   session. Knowing the source decides whether the fix is configuration
   or habit.
3. **Commit now or after your review?** The ritual is evidence-complete;
   say the word and b1+b2 land as one hand-authored commit, or hold until
   you have read the E2E/VM logs yourself.
