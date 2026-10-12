# Comprehensive Status — nix-international-telephony (2026-10-12 08:45)

> Repo: `github.com/LarsArtmann/nix-international-telephony` · main ·
> HEAD `447d095` (821 commits, 3.85 MiB pack) · working tree clean ·
> all local gates green. Two agent lanes share the tree (this round-11
> lane + the sibling's dynamic-SIP-directory lane, which is LIVE and
> landing fixes while this report is written).
> Verdict markers scope to §b/§c/§f/§g; §a/§d/§e stay bare by
> convention.

## a) FULLY DONE

1. **Round-11 pareto plan executed end to end** (19 M-rows: 7 done,
   4 partial, 8 owner/gated-open — every row annotated, plan archived
   with check-rows complete; execution report:
   `docs/status/2026-10-12_07-15_round11-execution-per-item-arm-lens-lane-release-lane.md`).
2. **Per-item marker monotonicity arm** (`scripts/markers_check.py`):
   count-preserving verdict-stripping is now a finding; post-archive
   scope (16 of the first 17 hits triaged as benign live-time verdict
   dedup, 1 real damage residue found and repaired — webphone-ui
   row 36, restored by the house `→ corrected` append).
3. **Rendering audit** (`scripts/rendering_audit.py`): fence/strike/
   emphasis damage classes over all 78 archived snapshots — 0 damage;
   incident-triangle + split-brain assertions ship inside it
   (CHANGELOG ↔ lesson ↔ AGENTS must close for every archive-damage
   incident; they do).
4. **`docs/lessons/markdown-normalization.md`**: the formatter-over-
   archives incident class in full (three incidents, CommonMark
   mechanics, pickaxe→follow mechanism deviation, recovery-by-append
   grammar); AGENTS.md marker paragraph slimmed to rules + pointers;
   DOMAIN_LANGUAGE gained 5 terms.
5. **Docs-integrity bundle**: `tests/test_markers_check.py` (15 stdlib
   tests: ID-header regression, evasion class, exit-code parity,
   triangle), `scripts/archive_snapshot.py` (annotate → gate → move as
   the only path, refusal arm proven on a synthetic repo), three new
   flake checks (`markers-test`, `rendering-audit`, `archive-checklist`),
   SKILLS-repo routed-verdict note (SKILLS `2cf1446`).
6. **The lens lane**: `services.telephony.pbx-lens` gained the real
   CDR read path (ro-bind + telephony-fs ACLs + ordering, eval-
   asserted incl. a bare-lens negative arm), the backup oneshot
   preStarts its staging dir, and the new `checks.telephony-lens` VM
   suite is GREEN: a real sofia leg's Master.csv row reaches
   `/api/export.jsonl` at a 2s poll cadence and the staged snapshot
   passes sqlite integrity_check. FEATURES row flipped to
   FULLY_FUNCTIONAL.
7. **Two real bugs driven out by that suite**: (a) upstream pbx-lens
   rejected vanilla mod_cdr_csv output (strict CSV vs the `,"", ""`
   tail every FreeSWITCH writes) — fixed upstream with a regression
   arm, this repo relocked `fa3d338 -> d436dea` with CHANGELOG
   attribution; (b) the eval fixtures' latent readOnly double-import
   (tls-mode-host + file-secrets-host imported the module set alongside
   the wrapper) — telephony-eval caught it the first time an arm read
   `state.paths`; fixed by dropping the duplicate imports.
8. **pbx-lens sibling CI**: the cqrs-lint install line fixed
   (module-path casing at the pinned rev, `de49b4e`) and PROVEN green
   on the next origin run (Build/Test, Vulnerability, Duplication and
   cqrs-lint all green; only the sibling session's pre-existing Lint
   debt stays red — their lane is live on it).
9. **Relock auth-surface clause** (M10): the Lock-bump runbook's gate 5
   now has the seam-scan + `/config.js` + login-DOM + `/phone-api`
   checklist for the upstream unified-auth wave.
10. **CI failure notification wired** (M06 F20): the `notify-failure`
    job posts failed push-runs to `ALERT_WEBHOOK` (no-op while unset)
    — it already fired correctly on the red runs (job conclusion
    success = clean no-op without the secret).
11. **Doc-counts spike** (`scripts/doc_counts.py`): derives 44 checks /
    169 stdlib tests and diffs them against the FEATURES/AGENTS
    literals — caught both claims stale on its first run; docs now
    carry the derived truth.
12. **Hook canary re-proven** (M13 F38): a scrub-pattern canary commit
    was BLOCKED by the installed pre-commit hook; the repo's hook
    battery is alive.
13. **Gates, all green at write time**: markers 78 files/0, rendering
    78/0 + triangle, drift PASS, lock-guard PASS, changelog-headings
    PASS, doc-counts ok, scrub-check 23 patterns clean, actionlint
    clean, `nix fmt` clean, `nix flake check --no-build` green, 169
    stdlib tests green, telephony-eval + telephony-lens green.

## b) PARTIALLY DONE

1. Origin CI verdict for the final tree → open — the two completed
   runs (`38206928881`, `38207213164`) fail ONLY in the sibling
   session's `telephony-webphone-dynamic-directory` suite (auth-register
   expects 200, sofia answers 403); aarch64 is green and the
   notify-failure job works. The sibling lane is actively landing
   fixes (five daemon commits in the last hour; a newer run,
   `38211036564`, was in flight at write time).
   → done at 2026-10-12 — the sibling's fixes landed; run `38213939150`
   over `3b63222` completed GREEN (both main jobs, airtight read), so
   the round-11 tree is CI-proven.
2. M06 branch protection → open — the ready-to-apply packet sits in
   `docs/ci-posture.md` (context names verified against current runs);
   applying is an owner admin call because protection also blocks the
   daemon's pushes while red.
3. M04 v0.3.0 → open — everything for the cut is staged in CHANGELOG
   `[Unreleased]` (WhatsApp lane, agent, three attributed relocks,
   round-10 + round-11 gate work); the cut waits for a green origin
   verdict so the tag anchors a proven tree.
4. M14 pbx-lens lane → open — the install fix is proven; the Lint lane
   red is the sibling session's R-lane debt (bodyclose, cyclop,
   errcheck, gci, golines across `internal/web`, `internal/search`,
   `cmd/pbx-lens`), and that session is ACTIVE (fresh status report
   minutes ago) — fixing under it would collide.

## c) NOT STARTED

1. M01/M02 first-call close-out (Telnyx portal PATCH, outbound-loop
   close, IPv6+AAAA, old-server deletion, deploy.md §5, first real
   calls + CDR verify) → open — owner hands-on (portal + live host);
   everything repo-side is metal-boot-proven and verify-live.sh sits
   at 14 PASS / 0 FAIL / 1 WARN.
2. M05 WhatsApp live verification (Meta embedded signup, VOICE OTP,
   round trip incl. media) → open — owner (Meta business verification).
3. M11 Telnyx API-key rotation + scrub-pattern prefix update → open —
   owner (portal).
4. M12 Warsaw DID re-purchase + 5 KYC requirements in the ~48h window
   + DE national DID → open — owner (portal; deadline-bound once
   purchased).
5. M13 F37 the global `~/.gitconfig core.hooksPath` landmine at
   home-manager level → open — owner (machine-level; this repo's hook
   is healed + canary-proven).
6. M16 nine small owner decisions (browser E2E promotion, mainProgram
   policy, sops example host, GitHub residual exposure, scrub
   placeholders, lens vhost, fspbx sign-off, OQ6 qemuGuest, OQ8
   binfmt) → open — owner.
7. M18 CDR cancelled-leg reproduction on the live host → open — gated
   on M01/M02 (needs real traffic to journal).
8. M19 post-deploy runtime verifications (TURN-over-TLS with the real
   cert, real-ITSP validation pass) → open — gated on M02.

## d) TOTALLY FUCKED UP

1. **I shipped a broken workflow file.** The `notify-failure` job used
   `${{ secrets… }}` inside an `if:` — GitHub rejects the secrets
   context at workflow PARSE time, so two pushes went red with 0-second
   "workflow file issue" runs (38206813495, 38206843950) before
   actionlint caught it. Two avoidable red runs on main; the fix is in
   (`faddb58`), actionlint now gates it locally, and the incident is
   exactly the class the notify job exists to surface — but it should
   never have been shipped unlinted.
2. **I pushed before committing.** My first push sent the daemon's
   `053aabb` while my doc edits sat staged-uncommitted; the second
   commit+push then needed the pre-commit hook to re-format and re-run
   (nixfmt modified files, one retry). Sloppy sequencing, harmless
   outcome, wrong order.
3. **The per-item arm's first headline was wrong.** The first live
   sweep reported "17 findings" as if 17 verdicts were lost; triage
   showed 16 were benign live-time verdict-twin dedup and only one was
   real. The arm's scope (post-archive only) is the correct design and
   the self-test now pins it — but the initial framing overstated
   damage before triage, and only the triage made it true.
4. **`go build ./...` in pbx-lens overwrote a tracked file**
   (`cmd/pbx-lens/unused-dsn` — a build artifact checked into the
   repo); restored via `git restore` before it could be swept into a
   commit. The artifact being tracked at all is upstream's smell, not
   mine to fix in a passing lane.
5. **My pbx-lens parser fix landed via a daemon heuristic bundle**
   (`e1d9ff7`, mixed with the sibling's docs) instead of a
   hand-authored commit — the soft-reset re-author was NOT safe with a
   sibling lane mid-flight, so attribution went through a CHANGELOG
   entry instead. Honest, but the weaker remedy.

## e) WHAT WE SHOULD IMPROVE

1. **actionlint belongs in the pre-commit battery.** The secrets-in-if
   parse breakage would have died locally. One more git-hooks.nix
   entry (or a BuildFlow step upstream — fleet-wide value) closes it
   for every workflow file.
2. **`go build` artifacts should not be tracked** (pbx-lens
   `cmd/pbx-lens/unused-dsn`); one `.gitignore` + `git rm --cached`
   upstream ends the overwrite hazard for every future `go build ./...`.
3. **The marker-arm triage should be a printed classification**, not a
   human step: markers_check could split per-item findings into
   post-archive vs live-time itself (it already knows the archived
   index) so the headline number is true the moment it prints.
4. **Two lanes, one working tree, zero coordination**: the sibling and
   I interleave commits through the same daemon. It worked this time
   (disjoint files, both lanes' gates green locally), but the
   fs-directory suite went to origin red twice while I also pushed —
   a lane-claim convention (even a one-line file like `LANE.md`) would
   make pushes deliberate instead of incidental.
5. **`checks.markers-test` runs the whole synthetic-repo self-test per
   CI run** (~3s, fine), but `rendering-audit` + `archive-checklist`
   re-parse 78 snapshots each — still seconds; worth remembering if
   the archive ever reaches hundreds of files.
6. **The webphone relock runbook and the pbx-lens input deserve the
   same formal gate**: lock_guard tracks webphone only; today's
   pbx-lens relock was hand-attributed because the ritual says so, not
   because a gate would catch an unattributed move.

## f) NEXT (prioritized)

1. Watch origin run `38211036564` (and its successors — the sibling is
   landing fixes) to a GREEN verdict; airtight read via
   `gh run view <id> --json headSha,status,conclusion,event,jobs` →
   open — blocked on the sibling's dynamic-directory suite going green.
   → done at 2026-10-12 — GREEN verdict recorded: run `38213939150`
   over `3b63222` (both main jobs).
2. Cut `v0.3.0` the moment the tree is green: date `[Unreleased]`, tag,
   `gh release create v0.3.0`, metadata refresh → open — owner may
   prefer to hold the release for the first real call (round-10/11 §g
   question, still unanswered).
3. Owner: the 1% — first-call close-out (M01/M02 checklist in
   TODO_LIST High row; `scripts/verify-live.sh` tail prints the §5
   paste-pack) → open — owner.
4. Owner: set the `ALERT_WEBHOOK` repo secret (the notify lane is
   otherwise done) or apply Option A branch protection from
   `docs/ci-posture.md` → open — owner.
5. Owner: M05 WhatsApp live (embedded signup + VOICE OTP + round trip)
   → open — owner.
6. Owner: M11 Telnyx key rotation + scrub-pattern prefix in one action
   → open — owner.
7. Owner: M12 Warsaw DID re-purchase + KYC inside the ~48h window, then
   DE national DID → open — owner (deadline starts at purchase).
8. Owner: M13 F37 fix the global hooksPath at home-manager level, then
   re-run the canary → open — owner.
9. Owner: the nine M16 small decisions (E2E promotion cadence,
   mainProgram policy, sops example host, GitHub residual exposure,
   scrub placeholders, lens vhost, fspbx sign-off + execute, OQ6
   qemuGuest, OQ8 binfmt) → open — owner.
10. Agent, after the sibling's suite greens: re-run the full local
    battery on the then-HEAD and re-verify the three doc gates →
    open.
11. Agent: round-12 docs-health round — the 21 open October snapshots
    (18 status + 3 planning) are the annotate+archive batch; the
    2026-10-01→07 webphone/lock/buildflow clusters first → open.
12. Agent: extend `TRACKED_INPUTS` in `scripts/lock_guard.py` to the
    pbx-lens input (it rides a moving upstream exactly like webphone)
    → open.
13. Agent: markers_check could self-classify per-item findings
    (post-archive vs live-time) so the printed headline is already
    triaged → open.
14. Agent: add the `telephony-webphone-dynamic-directory` feature row
    to FEATURES once the sibling's suite greens (the check is
    enumerated; the feature row is their lane's to verdict) → open.
15. Agent: wire `doc_counts.py` as `checks.doc-counts` if the owner
    wants the counts gate enforced rather than swept → open (owner
    preference).
16. Agent: pbx-lens Lint debt (bodyclose/cyclop/errcheck/gci/golines)
    AFTER the sibling's session closes — coordinate, don't collide →
    open.
17. Agent: lens vhost decision support (if the owner picks "expose
    UI": nginx location + htpasswd wiring exists in the module — the
    suite proves loopback; a vhost arm would extend it) → open.
18. Agent: the remaining round-10 §f tails (archive back-catalog gate
    verification already accepted-by-default; counts-derivation now
    shipped as a spike) → open — fold into round-12.
19. Agent: provenance note in `docs/lessons/markdown-normalization.md`
    once the first real post-lesson normalization incident happens —
    the lesson predicts the recovery grammar; verify it holds → open.
20. Agent: keep `TODO_LIST.md` the living source — this report's §c/§f
    items are already mirrored there except §f.12/13/14 (lock_guard
    pbx-lens extension, per-item self-classification, dynamic-directory
    feature row) — harvest those three into TODO_LIST rows in the next
    docs pass → open.

## g) QUESTIONS I CANNOT FIGURE OUT MYSELF

1. **Release gate**: cut `v0.3.0` on the first green origin verdict
   (my recommendation — the tag anchors the proven tree BEFORE the
   owner's live-host churn), or keep the original "after the first
   real call" gate? The plan's critical path says M02 → M04; the
   rollback-anchor argument says earlier is safer.
   → open — owner (agent proceeds on the standing finish-everything
   directive; a tag is reversible)
2. **Branch protection while two agent lanes push straight to main**:
   protection blocks the daemon's pushes while red (that is its
   purpose), but the sibling's suite is red RIGHT NOW — apply Option A
   now and both lanes wedge on every push until their suite greens, or
   wait for green and apply on a calm tree? The interim from the
   packet: aarch64-only required context.
   → open — owner
3. **Is the dynamic-directory lane yours to prioritize over the first
   call?** The sibling session is deep in the webphone credential-
   brokering wave (upstream's unified-auth direction); M01/M02 (the
   actual phone calls) need no part of it. If the first call is still
   the 1%, the directory work could park behind it — that is a
   priority call only you can make.
   → open — owner
