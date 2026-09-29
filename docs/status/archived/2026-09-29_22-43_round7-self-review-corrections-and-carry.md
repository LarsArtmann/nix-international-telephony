# Status: Round-7 self-review — what was forgotten, what was wrong, what stays open

- **Written**: 2026-09-29 22:43 CEST
- **Scope**: evening continuation of the 09:58–10:45 docs-health round 7
  (commits `2944789..bf6bbaf` + this correction pass). Trigger: the owner's
  "what did you forget / what could be better / full status" instruction.
  Self-review only — no new lanes researched.
- **TL;DR**: The morning run's core work stands (6 snapshots annotated +
  archived, 65/0 marker gate, living docs fixed, drift alarm green). The
  self-review found **one shipped falsehood** (the archived round-7 report
  claimed "zero daemon races" + a wrong commit count while its own §d
  omitted the `git mv` failure entirely — and my fix commit `bf6bbaf`
  mislabeled that failure a "race" when `git mv` on an UNTRACKED file fails
  deterministically), **one skill-process deviation** (the health report was
  buried in the archived file instead of printed inline; the
  health-report-format reference was never loaded), and a handful of
  cheap-gate gaps (checks ran mid-tree, not at the final tree). All
  corrected or owned below; nothing needed history surgery.

## a) FULLY DONE (this evening continuation, each verified)

1. **The archived round-7 report corrected inline** (`→ corrected` append on
   §a.7): the commit count was 7 at write time (9 by session end), the
   daemon DID absorb the TODO_LIST intermediate state as `f025c38` (benign,
   no collision — but not "zero"), and the `git mv` failure was a
   write→mv sequencing error (`git mv` cannot move untracked files), not a
   race. markers_check on the file: 0 unmarked; check-rows: complete;
   per-table pipe consistency: clean.
2. **The health-report-format reference finally loaded** (skill AUDIT step 6
   says print INLINE, never to a file) — the health report is printed in
   the conversation this time, visible math included.
3. **Missed cheap gates run**: check-rows.py over the round-7 report (was
   skipped — only the 5 morning files got it), per-table pipe-consistency
   check (the morning's aggregate check was a false alarm comparing
   DIFFERENT tables' column counts).
4. **Honest accounting of the morning's "verify" claims**: what was verified
   at primary source (git/gh CI verdict, tests, gates, options, checks
   inventory) vs. what rests on internal consistency only (webphone
   `89502ee` push/CI state — carried from the 10-15 report, not re-fetched
   from the webphone repo).

## b) PARTIALLY DONE

1. **Final-tree gate closure**: the targeted nix checks (docs-drift, format,
   statix, deadnix) evaluated the mid-session tree (`ba4d812`-era source);
   the later tail is docs/status-only (not covered by those checks' inputs)
   but was never re-gated explicitly. `pre-commit run --all-files` at the
   final tree also not run (the per-commit battery ran on every change).
   **→ open — cheap; run before the next push (§f.4)**
2. **Webphone origin state at primary source**: TODO_LIST's webphone-polish
   row cites `89502ee` + "CI green" from the 10-15 report and CHANGELOG —
   internally consistent, not re-verified via `gh api` on the webphone repo.
   **→ open — §f.5**

## c) NOT STARTED (owner lanes; report-only session by instruction)

All owner-gated rows unchanged: CI posture, host identity, v0.3.0, M06
round-2 decisions, security hygiene, DID lane, fspbx closure, hooksPath
landmine, residual exposure, mainProgram, sops example, nix-ssh-config
merge. **→ open — owner (TODO_LIST blocked rows)**

## d) TOTALLY FUCKED UP (owned, with costs)

1. **Shipped a falsehood into an archived report during a truth-focused
   session.** §a.7 said "zero daemon races this session" + "(6 commits)"
   (real: one benign absorption `f025c38`; 7 commits at write time) while
   §d omitted the `git mv` failure entirely. And the fix commit `bf6bbaf`
   mislabeled that failure "the first git mv raced the untracked file" —
   `git mv` on an untracked file fails 100% deterministically; there was no
   race to lose. Two layers of wrong causal narrative around one simple
   sequencing bug (write → `git add` → THEN `git mv`). Cost: correction
   append + this report. History surgery NOT warranted (messages are
   cosmetic-wrong, trees are right).
2. **Skill-process deviation**: the docs-health AUDIT step says "Report
   using the health-report format … Print inline to the conversation; do
   not write to a file. Load ./references/health-report-format.md." I did
   neither — invented my own §h format inside the archived file and gave
   the conversation only two bare numbers. The skill's math-discipline rules
   (count-first, visible substitution) went unread on the very run where I
   was grading my own work.
3. **Re-typed anchors struck twice more** (4th/5th recurrence of the
   documented round-6 d.1 class): one trailing-space diff on the round-4
   plan's Vulnix row, one assumed line-start that was mid-line in round-6
   §g. Both caught by assert-then-write atomicity (zero partial states),
   but I then still used one full-line anchor (the §g.2 fix) where the
   proven answer was prefix matching.
4. **Drafted an open item as a done-strike** (round-6 §c.4) — caught in
   dry-run review, but only because I re-read the output; the spec was
   wrong on first write.
5. **Verification theater, twice**: (i) the aggregate pipe-count "check"
   compared counts across DIFFERENT tables and produced a false alarm I
   then chased; (ii) my first per-table script crashed on an unbound
   variable. Two broken tools to verify table shape after a session
   lecturing about gate discipline.
6. **"View ALL files" was 11 full reads + 63 gate-sampled.** Defensible
   (the round-5 classification precedent) — but I re-derived the
   classification from scratch instead of citing the standing one first;
   the archaeology already existed in the 09-25 report §d.1.

## e) WHAT WE SHOULD IMPROVE (systemic, from d)

1. **Fresh files: write → `git add` → `git mv`** (or plain `mv` + `git add
   -A <path>`). And never name a root cause before re-reading the error —
   "raced" was narrative, not diagnosis. Record both in AGENTS next round.
2. **Structural anchors, always** — prefix/row-id grammar beats full-line
   re-typing every time it has been tested; stop hand-typing anchors at
   recurrence #3. Better: extend the skill's `annotate-rows.py` with the
   house in-cell routed-arrow kind (P32 precedent) so table work stops
   needing bespoke scripts.
3. **Health report = inline + the format reference loaded**, scores a pure
   function of the findings table; a docs-health run that grades itself in
   a file nobody reads in-conversation is a trophy case.
4. **Finish gates at the FINAL tree**: "sequence long gates last" also
   means re-running the cheap battery (pre-commit --all-files + targeted
   checks) after the last commit, not at the last-but-three commit.
5. **Primary-source verification for cross-repo evidence**: when a TODO row
   cites another repo's state (`89502ee` CI green), one `gh api` call
   converts "carried claim" to "verified claim" — the gap between them is
   exactly what verify-external-claims exists for.
6. **markers_check scopes §b/§c/§f/§g only** — plan Step-2 tables pass the
   gate by scoping accident (documented per-file via the inheritance note).
   Decide: a plan-section preset, or an AGENTS line saying the M-table +
   note IS the convention. Silence is how the gap becomes a miss.

## f) NEXT — ranked (route marks: [AI] = next session can do, [OWNER] = gated)

**Repo, AI-actionable now**

1. [AI] Wire `scripts/markers_check.py` as a flake check (TODO_LIST Low row)
   **→ open — TODO_LIST**
2. [AI] M05 host-identity reality check: `verify-live.sh` pass + decision
   packet (TODO_LIST High row) **→ open — TODO_LIST**
3. [AI] Webphone `SECURITY.md` + `DOMAIN_LANGUAGE.md` upstream (TODO_LIST
   Low row) **→ open — TODO_LIST**
4. [AI] Final-tree cheap battery: `pre-commit run --all-files` + targeted
   nix checks re-run (this report §b.1) **→ open — §b.1 debt**
5. [AI] Verify webphone origin/main at primary source (`gh api
   repos/LarsArtmann/webphone/commits/…`) for the `89502ee` claim **→ open
   — §b.2 debt**
6. [AI] Recount flake checks; replace FEATURES "30+" with a derived or
   verified number **→ open — accuracy debt**
7. [AI] check-rows sweep over archived files added since the M24 sweep
   (round-7 + this report) **→ open — hygiene**
8. [AI] AGENTS: record write→add→mv for fresh files + the
   structural-anchors rule (5 recurrences) **→ open — lesson codification**
9. [AI] markers_check plan-section preset decision (§e.6) **→ open —
   decision + S effort**
10. [AI] After the next push: confirm a completed origin CI verdict for the
    docs tail (ahead-check lane; cancel ≠ red) **→ open — post-push**
11. [AI] drift_alarm cross-file arm idea (FEATURES↔README inventory drift)
    — or park it on ROADMAP **→ open — idea routing**

**Skill / out-of-repo, AI**

12. [AI] Extend `annotate-rows.py` with the routed-arrow in-cell kind
    (upstream skill contribution) **→ open — skill repo**
13. [AI] Next docs-health round: health report inline per the loaded format
    (process; costs nothing) **→ open — process**

**Owner-gated lanes (TODO_LIST blocked rows unless noted)**

14. [OWNER] CI posture on main — protection + required checks vs
    notification (Critical; green window open since `b8f211d`) **→ open —
    owner**
15. [OWNER] Host-identity answer (feeds #2 and the P1–P5 reroute) **→ open
    — owner**
16. [OWNER] Push-mandate standing rule — local main is now ~11 commits
    ahead (docs tail, pre-commit green per commit); see g.3 **→ open —
    owner**
17. [OWNER] Cut v0.3.0 (Unreleased finalized + hook-green) **→ open —
    owner timing**
18. [OWNER] M06 round-2 decisions (backup doctrine, timing, kexec) — gates
    20–22 **→ open — owner**
19. [OWNER→AI] M07 migration plan doc (after M06) **→ open — gated**
20. [OWNER→AI] M08 backup-staging upstream (after M06) **→ open — gated**
21. [OWNER→AI] M09 alert-relay + secrets perms-heal upstream (after M06)
    **→ open — gated**
22. [OWNER] P1–P5 deploy lane incl. first calls + CDR (after host identity)
    **→ open — owner hands-on**
23. [OWNER] Telnyx API key rotation + scrub-prefix coupling **→ open —
    owner**
24. [OWNER] Warsaw DID re-purchase + 5 KYC requirements in-window **→ open
    — owner portal**
25. [OWNER] DE national DID order **→ open — owner portal**
26. [OWNER] fspbx verdict sign-off execution **→ open — owner**
27. [OWNER] hooksPath landmine fix (home-manager) **→ open — owner**
28. [OWNER] Browser E2E CI cadence decision **→ open — owner**
29. [OWNER] GitHub residual-exposure appetite + clone inventory **→ open —
    owner**
30. [OWNER] sops-nix example host go/no-go **→ open — owner**
31. [OWNER] flake-meta mainProgram policy (park on BuildFlow#27 or accept)
    **→ open — owner**
32. [OWNER] nix-ssh-config branch merge + relock here (issue #5) **→ open —
    owner merge**
33. [OWNER] ROADMAP Q6–Q8 sweep (qemuGuest, lock governance, aarch64
    emulation) **→ open — owner**
34. [OWNER] scrub-patterns "OWNER TO ADD" placeholders: fill or drop **→
    open — owner**
35. [OWNER] BuildFlow binary refresh via system profile **→ open — owner**
36. [OWNER] `nix-hash-fix` → `skip_steps` call **→ open — owner**
37. [OWNER] /tmp-durability lesson → crush-config global lessons (commit
    there) **→ open — owner**
38. [OWNER] Demo/launch video + website wave (post-v0.3.0, post-first-call)
    **→ open — owner**

**ROADMAP homes (routed, not TODOs)**

39. Binary cache (cachix/attic) for VM closures **→ open — ROADMAP theme 5**
40. Vulnix replacement scanner **→ open — ROADMAP theme 5**
41. Lock-diff CI step **→ open — ROADMAP theme 5**
42. Machine-readable repo surface (llms.txt) **→ open — ROADMAP theme 5**
43. Webphone smoke-script adoption **→ open — ROADMAP theme 3**
44. aarch64 KVM suite (hardware-gated) **→ open — ROADMAP q8**

## g) QUESTIONS I CANNOT ANSWER MYSELF

1. **Is the live host the finished P1–P5 deployment or the old billing
   server?** Everything external answers green; the answer decides whether
   the deploy lane is "verify + close" or "do it all" — and it gates the
   highest-impact row in TODO_LIST. **→ open — owner**
2. **CI posture: branch protection + required checks, or failure
   notification only?** Main is green at `b8f211d` — protection has never
   been cheaper, but it also blocks the auto-commit daemon's pushes while
   red, which changes your workflow, not mine. **→ open — owner**
3. **Push discipline going forward: was "push when green and verdicted" a
   one-time round-5 mandate, or standing practice?** Local main sits ~11
   commits ahead again (all docs, all hook-green); the standing
   never-push-unasked rule is what keeps it there. **→ open — owner**

---

_Point-in-time snapshot — born annotated (every scoped item carries its
verdict inline); archives at write time per the round-7 precedent._
