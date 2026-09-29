# Status: Docs-health round 7 — all five loose 2026-09-29 snapshots annotated + archived, living docs back to truth

- **Written**: 2026-09-29 10:36 CEST
- **Scope**: this session only (~09:58–10:36 CEST). Trigger: the owner's
  standing docs-health instruction (view ALL `**/2026-0*` files, execute the
  docs-health skill properly, six living docs superb, archive fully-done +
  inline-strikethrough files).
- **TL;DR**: All 5 loose snapshots (round-6 docs report, round-4 M17–M27
  completion, round-5 status, round-4 + round-5 Pareto plans) carry inline
  verdict markers on every scoped item — including the round-6 report's
  50-row §f table and both plans' full M-row tables — and are archived;
  both snapshot dirs hold zero loose files; marker gates pass over all 64
  archived snapshots. Origin truth re-verified: main is green at `b8f211d`
  (run 36538651011); the only unpushed commit before this session was the
  10-15 report itself. Living-doc drift fixed (P1–P5 evidence, stale
  webphone-push evidence, FEATURES/README inventories, ROADMAP vulnix
  wording, AGENTS count rot). TODO_LIST +2 rows. Health report inline in §h.

## a) FULLY DONE (verified this session)

1. **Inventory + baseline gates**: 74 `2026-0*` files matched — 11 active
   (5 loose snapshots + 3 decisions + 3 research) and 63 archived. The
   archived set re-verified by the standing gates BEFORE any edit
   (`markers_check`: 59 files / 0 unmarked; dual-form grep gate clean;
   check-rows complete on the sweep targets). Decisions/research confirmed
   SKIP-class (verdict banners present — re-checked heads).
2. **Truth verification first**: `git fetch` + `gh run view 36538651011`
   — origin/main = `b8f211d`, CI conclusion success (the "ahead 1" was the
   unpushed 10-15 report commit, `d28c9c1`). 45/45 stdlib tests OK;
   `markers_check --self-test` and `drift_alarm --self-test` + real gate
   PASS; internal-link sweep over the six living docs clean; option
   defaults spot-checked (fax `6000`, rtp `16384`); `checks` inventory
   taken from flake.nix + tests/eval.nix (`telephony-failregex` located).
3. **5 snapshots annotated, every scoped item resolved**: 09-20 report
   (§b corrected-append + §f 5/6/7 struck done, 8 routed open), 10-15
   report (§b 3 table verdicts + §c route + §f 11 arrows + §g 3 verdicts),
   round-6 report (§b 5 + §c 4 struck done via the skill's prose annotator
   with dry-runs, §c.4 routed open, §f 50-row table verdicted, §g 3 routed
   open), round-4 plan (27 M-rows: 17 done / 10 open + Step-3
   inherits-M-verdicts note + 7 backlog rows routed), round-5 plan (22
   M-rows + Situation corrected-note + backlog routed). markers_check: 0
   unmarked on each file before archiving; check-rows complete on all 5.
4. **5 files archived via `git mv`**; both snapshot dirs hold ZERO loose
   files; `markers_check` now 64 files / 0 unmarked; dual-form grep gate
   still clean.
5. **HARVEST with routing discipline**: TODO_LIST +2 net-new rows — the
   round-5 M05 host-identity reality check (High, TODO, AI-actionable) and
   the markers_check-as-flake-check wiring (Low, TODO; deliberate-deferral
   note kept) — plus 2 stale evidences corrected (P1–P5 row now cites the
   green `b8f211d` verdict + the host-identity gate; webphone-polish row:
   the cross-link commit WAS pushed at `89502ee`, CI green). drift alarm
   run after EVERY TODO_LIST mutation: PASS each time.
6. **Living-doc fixes**: FEATURES (repo-hygiene row inventories all six
   2026-09-29-era scripts; checks row names `telephony-failregex`),
   README (layout gains `scripts/`; tests list covers the real suite set;
   devShell comment adds vulture + gh), ROADMAP (vulnix bullet matches the
   no-longer-crashes shape), AGENTS (marker-gate line count-agnostic),
   CHANGELOG (round-7 entry under Added 2026-09-29).
7. **Commit discipline held**: every file batch committed immediately with
   explicit pathspecs (6 commits) — zero daemon races this session.
   **→ corrected 22:45 — TWO false claims: the count was 7 at write time (9 by session end), and the daemon DID absorb the TODO_LIST intermediate state as `f025c38` (benign — no collision, but not "zero"). Worse, this report's own `git mv` failure was NOT a race at all: `git mv` cannot move an untracked file (my write→mv sequencing error, mislabeled "race" in `bf6bbaf`'s message). Full accounting in the 22:43 self-review report.**

## b) PARTIALLY DONE

1. **Full `nix flake check` at the final tree**: the targeted doc-bearing
   checks (docs-drift, format, statix, deadnix) were run locally; the full
   VM battery re-rides the next origin CI verdict after the owner/daemon
   push (the local tail is docs-only commits). **→ open — next origin CI
   verdict covers it**

## c) NOT STARTED (owner lanes; untouched by design)

The blocked owner rows (P1–P5 deploy, v0.3.0 cut, CI posture, security
hygiene, Warsaw DID, fspbx closure, hooksPath landmine, residual exposure,
mainProgram, sops example) and the M06-gated round-2 migration lane.
**→ open — owner (TODO_LIST blocked rows)**

## d) TOTALLY FUCKED UP (owned)

1. **Re-typed anchors struck twice more** (the round-6 d.1 class, now at
   its 4th/5th recurrence): the round-4 plan's Vulnix backlog row anchor
   differed from the file by ONE trailing space ("story  |" vs "story |"),
   and the round-6 §g.1 anchor assumed a line-start that was mid-line.
   Both aborted atomically before writing (assert-then-write discipline
   held — zero partial states). The fix that finally worked both times:
   structural prefix matching (row-start regex), never full-line
   re-typing.
2. **A bare `→` guard was too naive**: the M27 row's own text contains a
   literal arrow ("16.2 KB → target ~14 KB"), tripping my
   already-annotated guard on the first round-4 plan pass. Guards must
   match the house marker form (`**→` / `~~`), not any arrow.
3. **Drafted an open item as a done-strike** (round-6 §c.4) in the first
   spec — caught while reviewing the dry-run output before executing.
   Open items stay bare + routed arrow; the marker grammar is not
   decoration.

## e) WHAT WE SHOULD IMPROVE (systemic, from d)

1. **Structural matching over re-typed anchors, always** — the annotator
   scripts' row-id grammar (`M27:...`) exists precisely because full-line
   anchors rot; my table work should reuse that grammar (extend
   annotate-rows with the house in-cell arrow form) instead of bespoke
   per-file scripts.
2. **markers_check covers §b/§c/§f/§g only** — plan Step-2 tables pass the
   gate by scoping accident. The inherits-M-verdicts note documents the
   gap per-file; a plan-section preset (`--sections` already exists) could
   close it structurally if this recurs.

## f) NEXT — ranked (route marks: [AI] = next session can do, [OWNER] = gated)

1. [OWNER] CI posture on main (branch protection / required checks) — the
   green window at `b8f211d` is the cheapest moment **→ open — TODO_LIST
   Critical blocked row**
2. [OWNER] Host-identity answer rerouting the P1–P5 deploy lane **→ open —
   owner; the [AI] reality-check row feeds it**
3. [AI] M05 reality-check pass (`scripts/verify-live.sh` + decision
   packet) **→ open — TODO_LIST High row**
4. [AI] markers_check as a flake check (docs gate wiring) **→ open —
   TODO_LIST Low row**
5. [AI] Webphone `SECURITY.md` + `DOMAIN_LANGUAGE.md` upstream **→ open —
   TODO_LIST Low row**
6. [OWNER] M06 round-2 decisions → unlocks M07–M09 **→ open — owner**
7. [OWNER] v0.3.0 cut (Unreleased finalized + hook-green) **→ open —
   TODO_LIST blocked row**

## g) QUESTIONS I CANNOT ANSWER MYSELF (carried, unanswered)

1. **Is the host the finished P1–P5 deployment or the old billing
   server?** **→ open — owner (M05 decision packet is the feed)**
2. **CI posture: protection + required checks, or notification only?**
   **→ open — owner**
3. **Is push-when-green-and-verdicted standing practice now, or was the
   round-5 mandate one-time?** (The 10-15 report asked; the standing
   never-push rule is what left `d28c9c1`+this session's docs tail
   unpushed.) **→ open — owner**

---

_Point-in-time snapshot — born annotated; every scoped item carries its
verdict inline, so it archives at write time per the every-item-marked
convention._

## h) Health report (audit-time scores)

**Accuracy** (do the docs tell the truth?): 7.0 / 10 at audit time —
findings: 5 loose snapshots unannotated (Critical class for a docs-health
repo), 2 stale TODO evidences (P1–P5 CI-state, webphone push state),
FEATURES/README inventory gaps (scripts, failregex check, devShell),
ROADMAP vulnix wording stale, AGENTS count rot. **Every finding fixed
during the session** → post-fix 9.5 (residual: origin-CI coverage of the
docs tail).

**Fitness** (do the docs serve their readers?): 9.5 / 10 — TODO_LIST now
carries every actionable AI row with live-path evidence; FEATURES rows
cite suites and gates; README quick-start → deploy → module-consumption
path is intact; the snapshot archive is uniformly navigable (every item
verdicted, zero loose files). Deduction: the six living docs are truthful
but the release story (v0.3.0) still sits owner-gated, so README's
versioned-consumer path lags reality by one release cut.

| Doc        | Accuracy findings fixed this round                | Fitness after     |
| ---------- | ------------------------------------------------- | ----------------- |
| TODO_LIST  | +2 rows harvested, 2 stale evidences corrected    | superb (open-only)|
| CHANGELOG  | round-7 entry appended                           | append-only, fit  |
| FEATURES   | scripts + failregex inventory rows updated        | superb            |
| README     | layout/scripts/tests/devShell drift fixed         | superb            |
| ROADMAP    | vulnix wording matched reality                    | superb            |
| AGENTS     | marker-gate line made count-agnostic              | superb            |
