# Status: Round-7 arc close — verdict row born, cadence codified, verifier verified

- **Written**: 2026-09-30 00:42 CEST
- **Scope**: the fourth self-review invocation (00:41–00:42 CEST), reviewing
  the 23:58 debts-drained session. Predecessor:
  `docs/status/archived/2026-09-29_23-58_round7-debts-drained-count-truth-sibling-lane.md`.
- **TL;DR**: Three cheap items the 23:58 session left behind are drained:
  the pending-tail verdict TODO row now EXISTS (harvest rule: the row ships
  with the state that needs it), the check-rows-on-archive cadence is
  codified in AGENTS (closing that report's §f.6), and the link sweep ran
  file-relative over the living docs INCLUDING the sibling-edited
  deploy/ops-runbook — after my first sweep produced 4 false positives by
  resolving links from the CWD instead of the linking file (verification
  tool defect #4 this arc; it briefly pointed fingers at the sibling's
  files). Local main: 20 commits ahead; no new sibling commits since
  `f868e24`.

## a) FULLY DONE (verified this session)

1. **Lane glance first** (the codified rule): `git log` — no sibling
   activity since `f868e24`; tree clean at entry.
2. **Link sweep, file-relative**, over the six living docs + the
   sibling-edited `docs/deploy.md`/`docs/ops-runbook.md`: all internal
   links resolve. The first (CWD-relative) run was wrong — see d.1.
3. **TODO_LIST harvested**: new BLOCKED row — "Confirm a completed origin
   CI verdict for the unpushed main tail (20 commits: round-7 docs arc +
   sibling trunk-probe code) once pushed; cancel ≠ red". drift alarm PASS
   run immediately after the mutation.
4. **AGENTS codified**: "Every newly archived snapshot also gets a
   `check-rows` uniformity pass in the same session that archives it" —
   23:58 §f.6 closed as a rule, not a backlog item.
5. Committed with pathspecs (`b6c24ab`); battery green per commit.

## b) PARTIALLY DONE

1. **Origin CI verdict for the 20-commit tail** — row exists now; blocked
   only on the push decision. **→ open — TODO_LIST BLOCKED row (push
   gates it; §g.3)**
2. **markers_check plan-section preset decision** — third carry; a
   report-only mandate does not start new wiring. **→ open — next AI
   session**
3. **Full `nix flake check` at the final tree** — targeted checks + battery
   green all arc; the full VM battery rides the next origin verdict.
   **→ open — rides §b.1**

## c) NOT STARTED (owner lanes; unchanged by design)

CI posture, host identity, v0.3.0, M06 round-2 decisions (gates M07–M09),
security hygiene, DID lane, fspbx closure, hooksPath landmine, residual
exposure, mainProgram, sops example, nix-ssh-config merge.
**→ open — owner (TODO_LIST blocked rows)**

## d) TOTALLY FUCKED UP (owned, with costs)

1. **My link checker nearly impugned the sibling's lane.** The CWD-relative
   resolver flagged 4 "broken" links — ALL in the files the sibling
   session had just edited, ALL actually valid (file-relative targets).
   A verification tool that fails by construction turns into a false
   accusation machine the moment its output is believed. Verification
   defect #4 this arc (2 broken table checkers, 1 malformed nix
   expression, 1 wrong resolver). Cost: 10 minutes; the save was NOT
   trusting the first red.
2. **The 23:58 session queued a one-line codification as §f.6 while its
   own §e.2 said "drain cheap debts in-session"** — the anti-pattern
   reproduces itself in the very session that names it. Drained tonight
   (a.4).
3. **The verdict row was born two sessions late** — the pending-tail state
   was created at 23:12 (push held), explicitly reported at 23:58 (§b.1),
   and only became a TODO row at 00:42. Follow-through states get their
   row at creation, or the next session inherits an untracked obligation.
4. **Cosmetic but telling**: the 23:58 health score line ("Accuracy:
   10/10") preceded its own caveat — skimming readers take the number and
   skip the words. Scores carry their asterisks inline or not at all.

## e) WHAT WE SHOULD IMPROVE (systemic, from d)

1. **Verify the verifier**: any new check runs against known-good data
   BEFORE its failures are believed — especially when its output
   critiques someone else's lane. Four tool defects in one arc is a
   pattern: I write checkers faster than I test them.
2. **Cheap-fix threshold, stated**: ≤5 minutes AND my lane ⇒ executed in
   the session that identifies it; §f entries are for real work only.
   (This closes the loophole that let d.2 happen twice.)
3. **Obligation rows ship with their states** — unpushed tail ⇒ verdict
   row; new script ⇒ gate-wiring row-or-decision; new snapshot ⇒
   check-rows pass. Same session, always.
4. **Link sweep (file-relative) joins the standard closing battery** next
   to drift_alarm and markers_check.

## f) NEXT — ranked (route marks: [AI] = next session can do, [OWNER] = gated)

**Repo, AI-actionable now**

1. [AI] Wire `scripts/markers_check.py` as a flake check (TODO_LIST Low
   row) **→ open — TODO_LIST**
2. [AI] M05 host-identity reality check: `verify-live.sh` pass + decision
   packet (TODO_LIST High row) **→ open — TODO_LIST**
3. [AI] Webphone `SECURITY.md` + `DOMAIN_LANGUAGE.md` upstream (TODO_LIST
   Low row) **→ open — TODO_LIST**
4. [AI] Confirm the completed origin CI verdict after the tail is pushed
   (TODO_LIST BLOCKED row, born tonight) **→ open — TODO_LIST (§g.3
   gates the push)**
5. [AI] markers_check plan-section preset decision (third carry; ≤30 min)
   **→ open — next AI session**
6. [AI] drift_alarm cross-file arm idea (FEATURES↔README inventory drift)
   — or park on ROADMAP **→ open — idea routing**

**Skill / out-of-repo, AI**

7. [AI] Extend `annotate-rows.py` with the routed-arrow in-cell kind
   (upstream skill contribution) **→ open — skill repo**
8. [AI] Health report inline per the loaded format every docs round
   (process) **→ open — process**

**Owner-gated lanes (TODO_LIST blocked rows unless noted)**

9. [OWNER] CI posture on main — protection + required checks vs
   notification (Critical; 20-commit unverdicted tail compounds it)
   **→ open — owner**
10. [OWNER] Host-identity answer (feeds #2 and the P1–P5 reroute) **→
    open — owner**
11. [OWNER] Push discipline: standing push-when-green or one-time-only?
    (see g.3) **→ open — owner**
12. [OWNER] Cut v0.3.0 (Unreleased finalized + hook-green) **→ open —
    owner timing**
13. [OWNER] M06 round-2 decisions (backup doctrine, timing, kexec) —
    gates 16–18 **→ open — owner**
14. [OWNER→AI] M07 migration plan doc (after M06) **→ open — gated**
15. [OWNER→AI] M08 backup-staging upstream (after M06) **→ open — gated**
16. [OWNER→AI] M09 alert-relay + secrets perms-heal upstream (after M06)
    **→ open — gated**
17. [OWNER] P1–P5 deploy lane incl. first calls + CDR (after host
    identity) **→ open — owner hands-on**
18. [OWNER] Telnyx API key rotation + scrub-prefix coupling **→ open —
    owner**
19. [OWNER] Warsaw DID re-purchase + 5 KYC requirements in-window **→
    open — owner portal**
20. [OWNER] DE national DID order **→ open — owner portal**
21. [OWNER] fspbx verdict sign-off execution **→ open — owner**
22. [OWNER] hooksPath landmine fix (home-manager) **→ open — owner**
23. [OWNER] Browser E2E CI cadence decision **→ open — owner**
24. [OWNER] GitHub residual-exposure appetite + clone inventory **→ open
    — owner**
25. [OWNER] sops-nix example host go/no-go **→ open — owner**
26. [OWNER] flake-meta mainProgram policy (park on BuildFlow#27 or
    accept) **→ open — owner**
27. [OWNER] nix-ssh-config branch merge + relock here (issue #5) **→
    open — owner merge**
28. [OWNER] ROADMAP Q6–Q8 sweep (qemuGuest, lock governance, aarch64
    emulation) **→ open — owner**
29. [OWNER] scrub-patterns "OWNER TO ADD" placeholders: fill or drop **→
    open — owner**
30. [OWNER] BuildFlow binary refresh via system profile **→ open —
    owner**
31. [OWNER] `nix-hash-fix` → `skip_steps` call **→ open — owner**
32. [OWNER] /tmp-durability lesson → crush-config global lessons (commit
    there) **→ open — owner**
33. [OWNER] Demo/launch video + website wave (post-v0.3.0,
    post-first-call) **→ open — owner**

**ROADMAP homes (routed, not TODOs)**

34. Binary cache (cachix/attic) for VM closures **→ open — ROADMAP
    theme 5**
35. Vulnix replacement scanner **→ open — ROADMAP theme 5**
36. Lock-diff CI step **→ open — ROADMAP theme 5**
37. Machine-readable repo surface (llms.txt) **→ open — ROADMAP theme 5**
38. Webphone smoke-script adoption **→ open — ROADMAP theme 3**
39. aarch64 KVM suite (hardware-gated) **→ open — ROADMAP q8**

## g) QUESTIONS I CANNOT ANSWER MYSELF

1. **Is the live host the finished P1–P5 deployment or the old billing
   server?** Everything external answers green; the answer reroutes the
   deploy lane and gates the highest-impact TODO row. **→ open — owner**
2. **CI posture: branch protection + required checks, or failure
   notification only?** Main carries a 20-commit unverdicted tail (docs +
   sibling code); protection has never been cheaper or more warranted —
   and it changes the daemon's workflow, so it is your call.
   **→ open — owner**
3. **Push discipline: standing push-when-green-and-verdicted, or was the
   round-5 mandate one-time?** 20 commits ahead, everything local green;
   if standing, the next session pushes and watches the verdict.
   **→ open — owner**

---

_Point-in-time snapshot — born annotated; archives at write time (write →
`git add` → `git mv`)._
