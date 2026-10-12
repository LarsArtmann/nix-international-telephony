# Status Report — docs-health round 10: 2026-0* snapshot sweep, the unattributed-relock catch, and the living-doc truth pass (2026-10-12 05:38)

> Scope: THIS session only — the "view ALL \*\*/2026-0\* files, execute
> docs-health PROPERLY, make the six living docs superb, archive what is
> done" request, plus the two pbx-lens readiness checks that opened the
> session. Written as `.md` per the owner's explicit instruction
> (standing exception to the skill's HTML default; what the marker and
> drift tooling expects). No unrelated research.
> Session state at write: all gates green (markers 77/0, drift PASS,
> lock-guard PASS); `CHANGELOG.md` + `scripts/markers_check.py` edits
> are the only uncommitted files (the daemon absorbs them); origin CI
> has two in-flight runs that will fail lock-guard by birth (started
> before the attribution entry lands on origin) — the NEXT completed run
> is the one that matters.

## a) FULLY DONE

1. **docs-health executed end to end on the stated scope**: skill + its
   annotation/harvest references loaded FIRST; recon (git status, lane
   check — one active pbx-lens lane found and avoided, it landed later
   that day); all 9 OPEN `2026-0*` files viewed (2 status snapshots, 1
   plan, 2 research, 3 decisions + 1 HTML audit skimmed to its verdict
   section). The 75 archived snapshots were verified MECHANICALLY
   (completeness greps `~~|→|<del>`, markers 77/0, check-rows) — the
   round-9 precedent, restated in §d so nobody mistakes the gate sweep
   for literal reads.
2. **The critical catch: an unattributed webphone lock move had origin
   CI red on `lock-guard`.** The daemon moved the input
   `dffdb5f06 → db741fd0bed6` at ~03:28; two origin runs had already
   failed on the gate. Full Lock-bump runbook executed retroactively:
   upstream delta mapped via compare API (37 commits — the "unified
   auth on cqrs-htmx + server-side SIP credential brokering" wave plus a
   `.templ`/island markup pass), rev confirmed on upstream origin/main,
   binary build green (`webphone-2.8.0`), `nix fmt` clean,
   `nix flake check --no-build` green, VM suites `telephony-webphone` +
   `telephony-fax` + `telephony-fax-feed` green, and — because the delta
   touched markup — the browser E2E green. Hand-authored attribution
   entry landed in CHANGELOG; `lock_guard.py` PASS.
3. **All three open snapshots annotated inline and archived**: the
   markers-arm session report (49 verdicts), the round-9 harvest report
   (28), the round-10 lockdown plan (18 M-rows; Step-3 inherits bare per
   convention). §a/§d/§e stayed bare per house style. `git mv` to the
   archived dirs; per-dir README manifests written (bulk-archive rule);
   annotate.go `check-rows` COMPLETE on all three.
4. **Research/decision docs classified, not touched**: the 2 research
   files and 3 decision ADRs are dated, self-resolving records (verdict
   banners, decided posture, rot-discipline tables) — SKIP per the
   skill's classification table; archiving them would destroy their
   reference value.
5. **Living-doc truth pass, all claims re-derived against the tree**:
   FEATURES.md — checks 35 → **39** (`nix eval`, 2026-10-12), the **AI
   voice agent row was missing entirely and is now written** (FULLY_
   FUNCTIONAL: agent.nix surface + telephony-agent VM proof + 65 stdlib
   tests, measured split 56+9), webphone lock line `3928dbd/10-05` →
   `db741fd0/10-12`. README.md — voice agent, pbx-lens and passkey
   capability rows added (the sales page was three features behind) plus
   agent/lens architecture nodes. AGENTS.md — 129 → **154** stdlib tests
   (ran the suite: OK, 74.6 s), voice-agent intro paragraph, complete
   13-module `modules/telephony/` map (was 6). ROADMAP.md — OQ7 (lock
   governance) answered by shipping (guard + commit-msg hook), theme-6
   marked shipped-in-part, docs-gate raw-idea cluster harvested.
   TODO_LIST.md — 9 new rows (7 from the markers-report harvest, the
   per-item arm, the next-relock auth-surface diff).
6. **Root-cause gate fix, not an archive patch**: markers_check flagged
   round-10's `| ID |` table header as an unmarked item. HEADER_ROW_RE
   simply lacked `ID`; provenance settled — rounds 5/6 used `| # |`
   headers (why they never tripped it), round 10 introduced `| ID |`.
   Fixed the regex + added a self-test arm. The gate now reads 77 files
   (75 snapshots + 2 manifests) / 0 findings.
7. **CHANGELOG honesty**: the relock attribution + a round-10 entry
   (sweep, gate fix, living-doc refreshes) recorded append-only.
8. **Gates at the final tree, all green**: markers_check 77/0 +
   self-test ok, drift_alarm PASS + self-test, lock_guard PASS +
   self-test, check-rows complete, `nix build` of the markers-check /
   lock-guard / docs-drift check derivations clean, 154 stdlib tests OK.

## b) PARTIALLY DONE

1. **"View ALL \*\*/2026-0\* files" is true for OPEN files only.** All 9
   non-archived files were read; the 75 archived ones were verified by
   the standing gates, not read — the same honest gap round 9 self-
   reported (§d.6 there). The skill forbids reading closed history for
   coverage; the instruction and the skill are in tension and I resolved
   it the same way, stated plainly.
2. **The relock proof is local, not origin**: gates 2–5 ran on this
   machine (KVM present); the full `nix flake check` under CI conditions
   is the next completed origin run's job. Until then the green claim
   about HEAD is conditional — the standing shape for every relock.
3. **The annotator rounds burned retries**: 3 of 28 verdict edits on the
   round-9 report missed (misremembered tails + a line-break I
   reconstructed instead of copying); all landed on the retry after
   re-reading the exact lines.
4. **pbx-lens readiness (the session's opening question) was answered in
   chat, not acted on**: the retention lane landed, CI went red on the
   sibling's `cqrs-lint` INSTALL step (upstream go-cqrs-lite module-path
   casing change at the pinned rev — a one-line workflow fix there), and
   this repo ALREADY integrated pbx-lens (input `fa3d338`, `lens.nix`)
   between my two checks. The sibling fixes belong to sibling lanes;
   nothing was filed.

## c) NOT STARTED

1. Watching the next origin CI run to a completed verdict (the two
   in-flight ones predate the attribution; their lock-guard reds are
   correct behavior, not news).
2. The SKILLS-repo hand-authored attribution note for the annotate-prose
   `r` kind — verified STILL absent today (git log in the skills repo);
   routed open in the archived round-9 report, no owner.
3. Any verdict on the 2026-10-01..07 status reports (17 October
   snapshots) — outside the `2026-0*` scope the user set; they carry
   their own routed markers from their writing sessions and are the
   natural corpus for a round 11.

## d) TOTALLY FUCKED UP

1. **I forgot my own harvest item mid-pass.** The per-item
   monotonicity-arm row (markers-report §f.A.3) was missing from my
   TODO_LIST routing until I was already annotating that report's §f
   table and the verdict had nothing true to point at. Caught in-pass,
   row added, drift re-run — but the miss class (routing from memory
   instead of walking the source list) is exactly what HARVEST's
   "route each surviving item" step exists to prevent.
2. **Three verdict edits failed on reconstructed anchors** — I re-typed
   tails ("CHANGELOG the accepted cost of ride-main?",
   "(Meta business verification can take days).") instead of copying
   from the View output; one spanned a line break. The AGENTS.md
   edit-mechanics bullet records this exact trap and I still paid the
   round trip. Copy, never recall.
3. **I archived before gating.** The markers finding on round-10's
   header appeared AFTER the `git mv` — the annotate→check→move order
   would have caught it pre-archive. The check exists only as part of
   the post-move battery today (ROADMAP C.34's checklist script is the
   unbuilt fix; it graduated from idea to demonstrated need this
   session).
4. **Ran `drift_alarm.py` with no args first** (exit 2, usage text) —
   didn't read the invocation before running it; the same measured-
   evidence-over-memory lapse in miniature.
5. **Round-9's §e.1 prescription ("run gates after EACH living-doc
   edit") was again not installed as a habit** — the drift gate caught
   my ghost path (`tests/test_markers_check.py` cited as an existing
   path) at gate time, not authoring time. Two rounds, same lesson.

## e) WHAT WE SHOULD IMPROVE

1. **Archive-time gating must be mechanical**: run the per-item gate
   over a snapshot BEFORE `git mv` (a `--path` mode on markers_check or
   the C.34 checklist script). Today the ordering is convention, and
   convention slipped on its first outing.
2. **Route harvests by walking the source list, never by recall** — the
   A.3 miss is only catchable if §f tables are enumerated row-by-row
   into TODO rows or explicit "dropped, because" decisions.
3. **Copy anchors from the current View** — after this session the
   failure mode has cost round trips in three consecutive doc rounds;
   the rule needs to be mechanical: no old_string that wasn't pasted
   from a View in the same turn.
4. **Hand-maintained counts rot on schedule**: AGENTS.md carries the
   stdlib test count in two places and FEATURES the checks count — all
   three were stale this round (129→154, 35→39). A derivation gate
   (like checks.docs-drift) would kill the class; the checks count at
   least is eval-able.
5. **The relock ritual needs an auth-wave clause**: upstream's unified-
   auth plan means future deltas can move the `/config.js` and login
   contracts this repo pins; "diff the auth surface" should sit next to
   gate 5's markup check in the runbook (row routed to TODO_LIST today).
6. **Verdict-watching needs an owner**: two origin runs failing by birth
   plus the next decisive run — someone must read them airtight; today
   that someone is "whoever opens the repo next".

## f) Things to get done next (prioritized; 24 honest items — the remaining slots deliberately unused)

**A. Direct follow-ups from this session**

| #  | Item                                                                                                                                       | Home                |
| -- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------- |
| 1  | Read the next completed origin CI run airtight (the two in-flight lock-guard reds are expected; the post-attribution run is the verdict)    | agent, minutes      |
| 2  | Commit-watch: confirm the daemon absorbs `CHANGELOG.md` + `scripts/markers_check.py` and the tree ends clean                                 | agent, minutes      |
| 3  | Residual rendering sweep over all 75 archived snapshots (TODO row)                                                                          | TODO_LIST (Low)     |
| 4  | `docs/lessons/` formatter-over-archives entry + AGENTS marker-paragraph slim (TODO row)                                                     | TODO_LIST (Low)     |
| 5  | Markers arms into a pytest module — MORE valuable now: HEADER_ROW_RE changed with only `--self-test` coverage (TODO row)                     | TODO_LIST (Low)     |
| 6  | Docstring evasion classes + exit-code parity in markers_check (TODO row)                                                                    | TODO_LIST (Low)     |
| 7  | Per-item marker monotonicity arm (TODO row)                                                                                                 | TODO_LIST (Low)     |
| 8  | Incident triangle + docstring-vs-AGENTS split-brain audit after the lesson lands (TODO row)                                                 | TODO_LIST (Low)     |
| 9  | DOMAIN_LANGUAGE vocabulary: verdict-marker count, recovery-by-append, fence-immune, monotonicity arm (TODO row)                              | TODO_LIST (Low)     |
| 10 | Build the archive-time checklist gate (annotate → gate → move as one script; ROADMAP C.34, demonstrated need this session)                   | TODO_LIST candidate |
| 11 | SKILLS-repo hand-authored attribution note for the `r` kind (open since round 9; verified absent today)                                      | skills-repo lane    |
| 12 | Next webphone relock: diff the auth/config contract first (TODO row, new)                                                                    | TODO_LIST (Medium)  |
| 13 | Derive the stdlib-test/checks counts in docs instead of hand-maintaining them (ROADMAP-grade)                                                | ROADMAP candidate   |

**B. Already-tracked rows restated so §f is one list (no new research)**

| #  | Item                                                                                              | Home          |
| -- | ------------------------------------------------------------------------------------------------- | ------------- |
| 14 | CI posture: branch protection + failure notification (two more unnoticed reds this week sharpen it) | owner BLOCKED |
| 15 | Cut v0.3.0 — the section now holds the WhatsApp lane, agent, relocks and round 10                   | owner BLOCKED |
| 16 | First-call close-out lane (High deployment row)                                                     | owner BLOCKED |
| 17 | WhatsApp live verification (WABA) + OQ9/OQ10 product calls                                          | owner BLOCKED |
| 18 | Key rotation, Warsaw DID + KYC, fspbx sign-off, global hooksPath landmine, small-decisions batch     | owner BLOCKED |
| 19 | CDR cancelled-leg: live-host reproduction (the one non-owner Medium row)                            | TODO_LIST     |

**C. Sibling-repo observations (noticed this session, unowned here)**

| #  | Item                                                                                                                              | Home           |
| -- | --------------------------------------------------------------------------------------------------------------------------------- | --------------- |
| 20 | pbx-lens CI red: cqrs-lint install step fails on the go-cqrs-lite module-path casing change at the pinned rev — one-line workflow fix | pbx-lens lane   |
| 21 | pbx-lens: 7 commit + retention work landed and pushed; the sibling now needs a re-ping only if integration pinning should advance    | pbx-lens lane   |
| 22 | `services.pbx-lens` in this repo: FEATURES row 63 still says "no VM suite of its own yet; UI loopback-only until a vhost lands"      | TODO/ROADMAP    |
| 23 | 17 October status reports (2026-10-01..07) are the corpus for a docs-health round 11                                                 | next round      |
| 24 | The relock runbook's gate-5 row could name the auth-surface diff explicitly once the TODO row proves the shape                        | ops-runbook     |

## g) Three questions I can NOT figure out myself

1. **Verdict protocol for the in-flight runs**: the two origin runs that
   started before the attribution entry will fail lock-guard by birth.
   Do you want the post-attribution run watched to completion and its
   verdict recorded now (agent lane, ~30-60 min of wall clock), or is
   the next push's verdict good enough and the reds just noted?
2. **Sibling dispatch**: the pbx-lens `cqrs-lint` casing fix and the
   SKILLS-repo attribution note are one-liners in repos I can reach —
   should I dispatch them as sibling-lane tasks, or do you take them?
3. **"View ALL" semantics for the archive back-catalog**: gate-
   verification (this round and round 9) vs literal reads of all 75
   archived snapshots — which is your accepted meaning for future
   rounds? Literal reads would burn real context for (per the gates)
   zero findings; but it is your instruction and I keep resolving the
   tension the same way without your explicit answer.

— End of report. Waiting for instructions.
