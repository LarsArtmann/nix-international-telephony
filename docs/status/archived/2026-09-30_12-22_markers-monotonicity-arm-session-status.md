# Status report: `markers_check` monotonicity arm session

**Snapshot:** 2026-09-30 12:22 CEST · **Scope:** this session's lane only (the
monotonicity-arm TODO row and the incidents it surfaced) — per instruction, no
unrelated research. Format note: written as `.md` per the explicit user
instruction (the status-report skill's canonical default is styled HTML —
one-off override, not propagated into the skill).

---

## Brutal self-review — the three questions, answered first

**What did you forget?**

1. **The sweep beyond the caught instance.** The arm caught ONE corrupted
   strike tail (`04562e7877f7` turning a line-start `~~~` into a fence) and I
   repaired that one row — but did NOT sweep the other 71 archived files for
   residual fence corruption or for the same-commit `*` → `_` emphasis
   rewrites, which prove the formatter rewrites archive prose wholesale. A
   count-preserving corruption class (e.g. a verdict reworded so the arrow
   survives but the verdict text changes 1:1 against a prose arrow) sails
   through the net by design, and I documented recovery semantics without
   documenting the evasion class.
2. **Verify numbers before publishing them.** The CHANGELOG bullet says the
   repair recovered "135 -> 137" — I published 137 as an inference before
   measuring it (it is now measured: history `[1, 136, 135, 137]`, worktree
   newest = 137, so the claim happens to be true, but publishing unmeasured
   numbers is how a report learns to lie).
3. **My own research output.** I had already captured real
   `git log --follow --name-status` output showing `M<TAB>path` — and then
   wrote the parser assuming a leading tab anyway. The bug I shipped was
   visible in evidence I possessed.

**What could you have done better?**

- Write the parser FROM the captured output, not from memory (the rename
  self-test arm caught it, which is the system working — but it cost a cycle).
- The TODO_LIST edit was inverted (I duplicated the row I meant to delete);
  caught by a one-line grep count, but it is exactly the "match structurally,
  never re-type anchors" trap AGENTS.md already records.
- The `--allow-empty` flat arm was impossible by construction (git history
  simplification never lists commits that don't touch the path) — the
  synthetic-repo design should have been thought through against git
  semantics before typing it.

**What could you still improve?**

- Per-ITEM (row-level) marker monotonicity as a second arm (closes the
  equal-count evasion class).
- A formatter-scope policy for archives (root-cause fix, §d/§e below).
- `_repo_toplevel(Path.cwd())` mislabels "paths are in a repo but cwd isn't"
  as "not a git repository" — resolve the toplevel from the first checked
  path instead.
- Record the deliberate deviation from the TODO row's candidate mechanism
  (row said "pickaxe-based count diff"; shipped `--follow` + per-revision
  count — strictly stronger, but the reasoning lives nowhere).
- The monotonicity semantics now live in three places (script docstring,
  AGENTS.md convention, CHANGELOG). CHANGELOG is history (fine); docstring
  and AGENTS.md overlap — one should point at the other as normative.

**Did you lie to you?** No claim was false at publish time, but one number
(137) was inferred, not measured — measured after, and it held. The "72 files
/ 0 findings" claims are tool output, not memory.

---

## a) FULLY DONE

| # | Work                                                                                                                                                                                                                                                                                                            | Evidence                                                                                                                                         |
| - | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1 | Monotonicity arm in `scripts/markers_check.py`: `git log --follow --name-status` parser, per-revision marker counts across renames, unrepaired-decrease findings (decrease must recover to the historical peak or it flags), worktree-based newest point, `--no-monotonicity` escape                            | live sweep green; 352 revisions / 72 files in 2.3 s                                                                                              |
| 2 | `--self-test` extended: pure-function arms (increase/flat/single/repaired-dip/real-dip) + synthetic git repo (seed → append → count-flat reformat → masked-column drop → in-cell recovery → `git mv` → post-rename loss → worktree repair)                                                                      | `self-test: ok`                                                                                                                                  |
| 3 | `checks.markers-check` sandbox story: `pkgs.git` in `nativeBuildInputs`, synthetic-repo arms prove the mechanism in-sandbox; live arm auto-skips there with a notice                                                                                                                                            | derivation builds green (`nix build .#checks.x86_64-linux.markers-check`)                                                                        |
| 4 | Incident #1 retro-verified: the arm sees `5ba5d2b` as 82 → 77 and the restore as → 82 — silent by design (repaired), exactly the semantics the TODO row asked for                                                                                                                                               | count history printed this session                                                                                                               |
| 5 | **Incident #2 caught live, unrepaired:** auto-commit `04562e7877f7` (2026-09-29) had normalized item 29's strike tail of the round-2 advisory report into a fenced code block (prettier treats line-start `~~~` as a CommonMark fence), destroying the strikethrough; count 136 → 135 for a day, never restored | arm's first live sweep flagged it; repaired in place, fence-immune (`~~ ~2.2x …`) + `→ corrected` append; measured recovery 135 → 137 ≥ peak 136 |
| 6 | Docs: CHANGELOG Added bullet; TODO_LIST row deleted (done work); FEATURES checks-row + scripts-row extended; AGENTS.md commands line + the `~~~`-fence formatter trap recorded in the marker convention                                                                                                         | drift alarm PASS against edited living docs                                                                                                      |
| 7 | Fast gates: `nix fmt` clean; statix/deadnix/format/docs-drift/markers-check derivations all green                                                                                                                                                                                                               | build outputs green this session                                                                                                                 |

## b) PARTIALLY DONE

| # | Work                                                                                                                                                                                                                                                                        | State                            |
| - | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- |
| 1 | "Archived snapshots never silently degrade" — the stated GOAL of the TODO row. The count net is live and CI-proven; the rendering-level truth is NOT audited (same commit also rewrote `*` → `_` emphasis across the archive; count-preserving damage classes exist)        | protection ≈ count-level only **→ open — routed to the TODO_LIST Low residual-rendering-sweep row (2026-10-12)**    |
| 2 | Verification depth: every cheap/eval gate green; the full `nix flake check` (VM suites, 20–60 min) not run. Flake change is `nativeBuildInputs`-only (low risk, derivation eval/build proves it); the standing full-gate TODO row owns this debt for the merged tree anyway | cheap-gate green, full gate open **→ done — CI-level full gates green repeatedly (36696533753 on `542443a`; 36714029522 over a lock move; the 2026-10-06 eval split ended the timeout kills)** |
| 3 | This report's §f list is HARVEST fuel — not yet routed into TODO_LIST/ROADMAP (awaiting instructions; entombment risk if it stays only here)                                                                                                                                | pending owner go **→ done — routed by the 2026-10-12 docs-health round: TODO_LIST Low rows + ROADMAP docs-gate cluster; the WhatsApp B-rows shipped 2026-09-30 (CHANGELOG)**                 |

## c) NOT STARTED (observed in this lane this session; not researched beyond it)

| # | Work                                                                                                                                                                                                                                                                 | Why it matters                                                                               |
| - | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| 1 | Residual-corruption sweep over all 72 archived files (line-start `~~~`, stray fences, emphasis-rewrite damage rendering strikes/asides as code or plain text)                                                                                                        | the arm proves counts, not rendering; two incidents happened, the audit happened zero times **→ open — TODO_LIST Low row**  |
| 2 | Formatter-scope policy: exclude `docs/status/archived/**` + `docs/planning/archived/**` from prettier (or a pre-commit canary proving formatters never rewrite archives)                                                                                             | root cause of BOTH incidents; will strike again otherwise **→ done in force — the flake surface cannot touch archives (treefmt prettier is webroot-only since the 2026-09-17 split-brain fix; nixfmt/statix/deadnix are nix-only); BuildFlow's dprint is the one unverified surface, guarded by the arm and folded into the lessons TODO row**                                    |
| 3 | Per-item marker monotonicity arm (row-level counts across history)                                                                                                                                                                                                   | closes the equal-count evasion class **→ open — TODO_LIST Low row (the shipped arm stays file-level)**                                                         |
| 4 | `docs/lessons/` entry for the formatter-over-archives incident class (long-form: CommonMark fence semantics, daemon normalization passes, recovery grammar)                                                                                                          | AGENTS.md bullet is the compressed form; the lesson file is the house home for the long form **→ open — TODO_LIST Low row** |
| 5 | Vocabulary into `docs/DOMAIN_LANGUAGE.md`: monotonicity arm, verdict-marker count, recovery-by-append, fence-immune                                                                                                                                                  | session-coined terms with no domain home **→ open — TODO_LIST Low row**                                                     |
| 6 | Markers arms into the stdlib test suite (`tests/test_markers_check.py`) so BuildFlow's pytest-test lane covers them (today only the flake check + manual runs exercise the script)                                                                                   | pytest-test runs only `tests/test_*` **→ open — TODO_LIST Low row**                                                         |
| 7 | The 12 WhatsApp TODO rows from the round-9 harvest (deploy/runbook bundle, OpenAPI cross-check, smoke probe, reconciler WABA lane, operator tab rendering, 16 MiB cap, bridge VM suite, fixture, eval warning, status-event shape, WABA owner lane, live round-trip) | standing tracked work, untouched here **→ done — shipped 2026-09-30 (see §f B-table verdicts); owner lanes stay in TODO_LIST**                                                        |
| 8 | Full `nix flake check` over the merged tree (standing TODO row)                                                                                                                                                                                                      | merged tree has not been through the full gate **→ done — CI-level (see §b.2)**                                               |

## d) TOTALLY FUCKED UP

1. **The systemic one: a markdown normalization pass rewrites ARCHIVED
   point-in-time snapshots.** Two incidents, two different commits
   (`5ba5d2b` dropped a verdict column; `04562e7877f7` destroyed a strike
   tail AND rewrote emphasis repo-wide in the same pass). The pipeline
   treats frozen history as living docs. The new arm guards marker COUNTS;
   the root cause — formatter scope over archives — is unfixed and will
   produce a third incident of whatever class the count net cannot see.
   This is the thing to fix next.
2. Session-level self-inflicted wounds (all self-caught, all minor, listed
   for honesty): the inverted TODO_LIST edit; the parser written from
   memory instead of from captured evidence; the impossible
   `--allow-empty` test arm; one unmeasured number published in the
   CHANGELOG (since measured, held).
3. Nothing else is on fire: live sweep 72 files / 0 findings, every
   cheap gate green, no open findings from either arm.

## e) WHAT WE SHOULD IMPROVE

1. **Fix the formatter-scope root cause, not just the detection net** —
   detection is shipped; prevention isn't.
2. **Trust measured evidence over memory** — both code bugs came from
   writing what I "knew" instead of what I had captured; the report
   culture must stay measured-numbers-only.
3. **Publish measured numbers only** — verify, then write (the 137 rule).
4. **Document the count metric's evasion classes** in the script docstring
   so nobody mistakes the arm for rendering-level truth.
5. **One normative home for the monotonicity semantics** (docstring vs
   AGENTS.md cross-pointing) to prevent drift.
6. **Toplevel resolution from paths, not cwd** — error messages must not
   lie about WHY the arm skipped.
7. **Record mechanism deviations** (pickaxe → follow+count) at the moment
   of decision, in the artifact that replaces the TODO row (CHANGELOG).

## f) Things to get done next (prioritized; ~35 honest items — padding to 50 would manufacture fake work, so the remaining slots are deliberately unused)

**A. Direct follow-ups from this session**

| #  | Item                                                                                                              | Suggested home              |
| -- | ----------------------------------------------------------------------------------------------------------------- | --------------------------- |
| 1  | Decide + wire formatter scope for archives (exclude from prettier or canary-guard) **→ done in force — see §c.2 (2026-10-12)**                                | TODO_LIST (S)               |
| 2  | Residual-corruption sweep of all 72 archived files (one-off audit script + fix pass) **→ open — TODO_LIST Low row**                              | TODO_LIST (S)               |
| 3  | Per-item marker monotonicity arm **→ open — TODO_LIST Low row**                                                                                  | TODO_LIST (M)               |
| 4  | Document count-metric evasion classes in the script docstring **→ open — TODO_LIST Low row**                                                     | TODO_LIST (S)               |
| 5  | Toplevel resolution from checked paths, not cwd **→ done — `_repo_toplevel(start)` resolves from the checked path; self-test arms prove both (scripts/markers_check.py)**                                                                   | TODO_LIST (S)               |
| 6  | `docs/lessons/` formatter-over-archives lesson **→ open — TODO_LIST Low row**                                                                    | TODO_LIST (S)               |
| 7  | Monotonicity vocabulary into DOMAIN_LANGUAGE **→ open — TODO_LIST Low row**                                                                      | TODO_LIST (S)               |
| 8  | Markers arms into `tests/test_markers_check.py` (BuildFlow pytest lane) **→ open — TODO_LIST Low row**                                           | TODO_LIST (S)               |
| 9  | Mechanism-deviation note (pickaxe → follow+count) — fold into lesson #6 **→ open — folded into the lesson TODO row**                                           | TODO_LIST (S)               |
| 10 | `--audit-history` verbose flag (per-file count timelines for retro-verification) **→ routed — ROADMAP docs-gate cluster (2026-10-12)**                                  | ROADMAP                     |
| 11 | Summarize/cap decrease lists in findings for noisy histories **→ routed — ROADMAP docs-gate cluster**                                                      | ROADMAP                     |
| 12 | Slim the AGENTS.md marker-convention paragraph once the lesson file exists (M27 pattern) **→ open — rides the lesson TODO row**                          | TODO_LIST (S)               |
| 13 | Full `nix flake check` over merged tree (standing row; also covers this session's flake edit under VM conditions) **→ done — CI-level (see §b.2)** | TODO_LIST (already tracked) |

**B. Already-tracked WhatsApp/telephony rows (restated so §f is one list; no new research)**

| #  | Item                                                                                                                      | Home          |
| -- | ------------------------------------------------------------------------------------------------------------------------- | ------------- |
| 14 | WhatsApp docs + example wiring bundle (deploy §WhatsApp, ops-runbook debugging, commented prod block, `preview_url` note) **→ done — CHANGELOG 2026-09-30** | TODO_LIST     |
| 15 | WhatsApp schema cross-check vs Telnyx OpenAPI spec3.json + date-stamp **→ done — spec3 fetched 2026-09-30; bridge conformant; one probe payload corrected**                                                     | TODO_LIST     |
| 16 | WhatsApp smoke probe script (vantage-probe pattern, `whatsapp+` thread-tag assert) **→ done — tests/whatsapp_probe.py (verdict table + exit codes)**                                        | TODO_LIST     |
| 17 | Reconciler WABA phone-registration lane **→ done — optional whatsapp_did desired-state, read-only VERIFY step (CHANGELOG 2026-09-30)**                                                                                   | TODO_LIST     |
| 18 | Operator SMS tab: render WhatsApp channel distinctly **→ done — envelope flattening + channel badge (CHANGELOG 2026-09-30)**                                                                      | TODO_LIST     |
| 19 | Per-channel 16 MiB inbound media cap **→ done — 16 MiB WhatsApp / 5 MiB MMS split (CHANGELOG 2026-09-30)**                                                                                      | TODO_LIST     |
| 20 | Bridge WhatsApp VM suite **→ done — five stub-Telnyx arms via TELNYX_API_BASE in tests/messaging.nix**                                                                                                  | TODO_LIST     |
| 21 | WhatsApp test fixture **→ done — oversize fixture monkeypatched tight (CHANGELOG 2026-09-30)**                                                                                                     | TODO_LIST     |
| 22 | Eval warning cleanup (round-9 harvest) **→ done — whatsapp-without-messaging warns at eval; eval-check case pinned**                                                                                    | TODO_LIST     |
| 23 | Outbound status-event `to`-shape tolerance **→ done — both envelopes read; Meta read maps to delivered (CHANGELOG 2026-09-30)**                                                                                | TODO_LIST     |
| 24 | WABA + number registration owner lane (embedded signup, VoIP-OTP warning) **→ open — owner (TODO_LIST WhatsApp live row)**                                                 | TODO_LIST     |
| 25 | Live round-trip WhatsApp verification both directions incl. media **→ open — owner (same row; probe shipped: tests/whatsapp_probe.py)**                                                         | TODO_LIST     |
| 26 | Webphone-side WhatsApp thread affordances **→ routed — ROADMAP (round-9 harvest)**                                                                                 | ROADMAP       |
| 27 | aarch64-vs-x86 CI kill-streak protocol (cap 3 reruns) — revisit after next full gate **→ superseded — reclassified 2026-10-06: the stretch was the 60-min timeout class, fixed by the per-system eval split; AGENTS.md carries the protocol**                                      | TODO_LIST (S) |

**C. Hygiene / brainstorm (ROADMAP-grade)**

| #  | Item                                                                                                                                                                          | Home          |
| -- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| 28 | Marker-rendering round-trip test: render archived files (markdown → HTML) and assert strike/routed-verdict elements survive — turns rendering truth into a gate, not an audit **→ routed — ROADMAP docs-gate cluster** | ROADMAP       |
| 29 | Batch `git show` via `cat-file --batch` if the arm ever grows past seconds (2.3 s today — do NOT do now) **→ routed — ROADMAP docs-gate cluster**                                                                      | ROADMAP       |
| 30 | Split-brain audit of docstring-vs-AGENTS semantics after item A.4/A.12 land **→ open — TODO_LIST Low row (after the lesson lands)**                                                                                                   | TODO_LIST (S) |
| 31 | Consider `errors="strict"` read mode with a clear failure for non-UTF-8 archived blobs (today: `errors="replace"` silently degrades) **→ routed — ROADMAP docs-gate cluster**                                          | ROADMAP       |
| 32 | Unify "incident" storytelling: CHANGELOG bullets reference lessons; lessons reference commits — check the triangle closes for incidents #1/#2 **→ open — TODO_LIST Low row**                                  | TODO_LIST (S) |
| 33 | `markers_check` exit-code documentation parity (docstring says 0/1/2; help text should too) **→ open — TODO_LIST Low row (folded with the docstring row)**                                                                                   | TODO_LIST (S) |
| 34 | Archive-time checklist automation: the annotate→archive→check-rows pass is convention-driven; consider one script that does all three gates **→ routed — ROADMAP docs-gate cluster**                                   | ROADMAP       |
| 35 | Re-verify `docs/providers/` WhatsApp pricing/KYC before any purchase (standing rule, untouched here) **→ done by recording — the standing rule lives in AGENTS.md (provider evaluations)**                                                                          | standing rule |

## g) Questions I can NOT figure out myself

1. **Formatter scope policy:** should `nix fmt`/prettier NEVER rewrite
   `docs/status/archived/**` and `docs/planning/archived/**` (frozen
   history), even when non-conformant? I can wire either behavior; whether
   an archive may ever be reformatted is an owner call about who owns
   archive formatting — you (owner) or the pipeline? **→ resolved in force — every wired formatter excludes archives: treefmt prettier is webroot-only (flake.nix), nixfmt/statix/deadnix are nix-only; the monotonicity arm is the standing net (2026-10-12)**
2. **Arm scope:** should the monotonicity arm also cover LIVE snapshots
   (`docs/status/*.md`, `docs/planning/*.md` pre-archive)? While a report
   is being drafted its counts legally go down; I would need your
   annotation workflow's answer for where "drafting" ends? **→ open — shipped scope is archived-only (the script's contract); no live-snapshot damage observed; owner call if that changes**
3. **Next long gate:** run the full `nix flake check` over the merged tree
   now (20–60 min, clears the standing full-gate debt and exercises this
   session's flake edit under VM conditions), or push the WhatsApp lane
   rows first and batch the full gate after? **→ superseded — CI runs the full gate per push since the 2026-10-06 eval split; the standing debt cleared at run 36696533753 (2026-09-30) and repeatedly since**

---

_Point-in-time snapshot per the status-report convention. §a/§d/§e bare by
convention; §f items carry suggested (not final) homes for HARVEST._
