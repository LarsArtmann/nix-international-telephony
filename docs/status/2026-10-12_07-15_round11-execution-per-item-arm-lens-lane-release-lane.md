# Round-11 execution — status (2026-10-12 ~07:15)

> Executes `docs/planning/2026-10-12_05-47_SUPERB-first-call-to-daily-driver-round11-pareto-plan.md`
> end to end. §b/§c/§f/§g carry per-item verdicts; §a/§d/§e stay bare by
> convention. All gates green at write time: markers 77/0, rendering
> audit 77/0 + triangle, drift PASS, lock-guard PASS, changelog
> headings PASS, doc-counts 44/169 ok, actionlint clean; the
> `telephony-lens` VM suite green locally; origin run `38206928881`
> (final tree) in flight.

## a) ACHIEVEMENTS (this session, verified)

1. **M09 — per-item monotonicity arm shipped** (`scripts/markers_check.py`):
   verdict markers counted per scoped item; count-preserving verdict
   moves (strip from one surviving item, compensate elsewhere) now a
   finding. First live sweep: 17 hits → 16 triaged as benign live-time
   verdict-twin dedup (scope corrected to POST-archive revisions), 1
   REAL damage residue found and repaired by the house `→ corrected`
   append (webphone-ui row 36, `04562e78`-class partial repair).
   Self-test arms: post-archive strip, live-churn exemption, recovery.
2. **M08 — archive-integrity debt paid**: `scripts/rendering_audit.py`
   (fence/strike/emphasis classes; del class retired with rationale)
   over all 77 archived snapshots → 0 rendering damage; the incident
   triangle + split-brain assertions shipped as a standing check;
   `docs/lessons/markers-normalization` written (`docs/lessons/markdown-normalization.md`)
   with all three incidents, the CommonMark mechanics, the
   pickaxe→follow mechanism deviation and the recovery-by-append
   grammar; AGENTS.md marker paragraph slimmed to rules + pointers;
   DOMAIN_LANGUAGE gained the five terms.
3. **M07 — docs-integrity bundle**: `tests/test_markers_check.py`
   (15 stdlib tests incl. the ID-header regression + evasion class),
   `scripts/archive_snapshot.py` (annotate → gate → move as the only
   path, refusal arm proven), three new flake checks
   (`markers-test`, `rendering-audit`, `archive-checklist`), and the
   SKILLS-repo routed-verdict note (SKILLS `2cf1446`).
4. **M10 — relock gate-5 auth-surface clause** in
   `docs/ops-runbook.md`: seam scan, `/config.js` contract, pinned
   login DOM selectors, `/phone-api` gate; same-commit rule.
5. **M15 — the lens lane, the session's biggest find**: the module
   gained the operator-style FS-state read path (ro bind +
   `telephony-fs` group + ACL ordering; eval-asserted with a bare-lens
   negative arm), the backup oneshot preStarts its staging dir, and
   `checks.telephony-lens` proved the whole chain in a VM. Driving it
   surfaced THREE real bugs: (a) pbx-lens's strict CSV rejected vanilla
   mod_cdr_csv output (`,"", ""` tail) — fixed upstream
   (`LazyQuotes`) + regression arm + this repo relocked
   `fa3d338 -> d436dea` with attribution; (b) the missing `backups/`
   mkdir; (c) the eval fixtures' latent readOnly double-import
   (tls-mode-host + file-secrets-host imported the module set alongside
   the wrapper) — telephony-eval went red the first time an arm read
   `state.paths`, fixed by dropping the duplicate imports.
6. **M14 — pbx-lens cqrs-lint install fixed and proven**: the pinned
   rev publishes lowercase (`github.com/larsartmann/...`); install line
   corrected, verified locally, pushed (`de49b4e`); the install step
   ran GREEN on the next CI run (the lane now fails only on pre-existing
   `Lint` findings from the sibling R-lane).
7. **M17 — doc-counts spike + October inventory**:
   `scripts/doc_counts.py` derives checks/tests counts and diffs them
   against FEATURES/AGENTS — it caught BOTH claims stale on first run
   (39→44 checks, 154→169 tests; docs updated). The 22 open October
   snapshots (18 status + 4 planning incl. this plan) are inventoried
   in §f.
8. **M06 F20 + packet refresh**: the `notify-failure` job landed
   (push-run failures post to `ALERT_WEBHOOK`, no-op while unset); the
   first version used `secrets` in `if:` — GitHub rejects the context
   at parse time (two 0s red runs), actionlint now clean, no-op moved
   into the script. `docs/ci-posture.md` refreshed.
9. **F38 hook canary**: a scrub-pattern canary commit was BLOCKED by
   the installed pre-commit hook (scrub-check fired, nothing landed).
10. **Doc truth pass**: FEATURES 44 checks (re-derived), 169 stdlib
    tests (re-derived), pbx-lens row → FULLY_FUNCTIONAL (VM-proven),
    8 completed TODO rows deleted into CHANGELOG.

## b) PARTIALLY DONE

1. M14 pbx-lens CI → the install fix is proven green, the lane stays
   red on the sibling session's R-lane lint debt (bodyclose/cyclop/
   errcheck/gci/golines in `internal/web`, `internal/search`,
   `cmd/pbx-lens`) → open — their lane is mid-flight; dispatching a
   lint-fix commit under it risks colliding with their edits (§g 2).
2. M06 CI posture → the notification lane is wired agent-side; the
   repo secret `ALERT_WEBHOOK` and branch protection (Option A) are
   owner-only → open — owner: set the secret or apply the packet's
   Option A (docs/ci-posture.md, names verified against current runs).
3. M03 origin verdict → the post-attribution run over `369ecee`
   completed GREEN (`38201268241`, 54m15s); the final-tree run
   `38206928881` was queued at write time → open — verdict recorded
   here when it completes (the two 0s reds before it were the invalid
   workflow parse, fixed and actionlint-gated).
4. M04 v0.3.0 → planned to cut on the `38206928881` green verdict →
   open — §g 1 asks whether the release should wait for the first real
   call instead.

## c) NOT STARTED (owner lanes, unchanged from the plan)

1. M01/M02 first-call close-out → owner (portal + live host).
2. M05 WABA live, M11 key rotation, M12 DIDs+KYC → owner (portals).
3. M13 F37 global hooksPath at home-manager level → owner (this
   repo's hook healed + canary-proven; the machine-level landmine
   remains).
4. M16 small decisions (E2E promotion, mainProgram, sops example,
   residual exposure, scrub placeholders, lens vhost, fspbx sign-off,
   OQ6, OQ8) → owner.
5. M18 CDR cancelled-leg live repro, M19 post-deploy runtime checks →
   gated on M01/M02.

## d) PROCESS NOTES

- Two agent lanes shared the tree (the fs-directory bridge landed
  mid-session, `95df7de`, plus its own check). The interplay worked:
  no file-level collisions, but my pbx-lens parser fix was swept into
  a heuristic daemon bundle (`e1d9ff7` upstream) — attribution
  restored via a CHANGELOG entry there, which is the cheap remedy when
  a soft-reset would tangle a sibling's unpushed work.
- flake single-file interpolation (`${./script.py}`) strips the source
  tree from `__file__` discovery — the marker-gate scripts now take
  `GATE_SCRIPTS_DIR`/`GATE_REPO_ROOT`/`--repo-root` instead of
  guessing roots in the sandbox.
- `systemctl is-active` on a finished oneshot exits 3 ("inactive") —
  suite asserts read the state string, not the exit code.

## e) VERIFICATION LEDGER

- Local: markers_check (77/0 incl. both monotonicity arms),
  rendering_audit (77/0 + triangle), drift_alarm PASS, lock_guard PASS,
  changelog_headings PASS, doc_counts ok (44/169), actionlint OK,
  `nix fmt` clean, unittest 169 OK (76s), archive-checklist +
  markers-test + rendering-audit checks green in-sandbox,
  telephony-eval green (lens arms incl. negative arm),
  telephony-lens GREEN (full VM chain).
- Upstream pbx-lens: `go test ./...` green with the regression arm;
  CI run `38205681080`: cqrs-lint install step GREEN, Lint red
  (pre-existing sibling debt only).

## f) NEXT

1. Watch origin run `38206928881` to a completed verdict and record it
   here → open — airtight read per protocol
   (`gh run view <id> --json headSha,status,conclusion,event,jobs`);
   runner-cancel protocol capped at 3 reruns.
   → done at 2026-10-12 — GREEN: `38213939150` over `3b63222` (the
   round-11 tree, sibling suite fixed) and `38231608546` over `8711531`
   (the release commit), both airtight-read.
2. Cut `v0.3.0` on the green verdict: date `[Unreleased]`, finalize,
   tag, `gh release create`, metadata refresh → open — owner timing
   question in §g 1.
   → done at 2026-10-12 — shipped as **v0.4.0** (v0.3.0 already existed
   since 2026-09-30): release commit `8711531` CI-proven before
   tagging, annotated tag + GitHub release published, repo description
   + topics refreshed (M16.3).
3. Owner rows (§c) — first-call close-out remains the 1%.
4. pbx-lens lint debt dispatch (§g 2).
5. October snapshot inventory (18 status + 3 planning + this plan):
   the 2026-10-01→07 webphone/lock/buildflow clusters are the next
   ANNOTATE+ARCHIVE batch (round-12 scoping; several already carry
   partial annotations from their own sessions); research + decision
   docs keep standing classifications → open — routed to the next
   docs-health round.
6. `doc_counts.py` standing-gate decision (§g 3) → open.
7. `telephony-webphone-dynamic-directory` (the sibling's new check)
   needs a FEATURES feature row from its own lane → open — only the
   check is enumerated in the checks row so far.

## g) QUESTIONS FOR THE OWNER

1. **v0.3.0 timing**: cut on the final-tree green verdict today (the
   rollback anchor ships with the lens lane + gate battery), or hold
   to the original "after the first real call" gate?
2. **pbx-lens lint debt**: dispatch as a sibling task (fix
   bodyclose/cyclop/errcheck/gci/golines across the R-lane files), or
   does the active pbx-lens session own it? The install fix is
   independent and already proven.
3. **doc_counts**: wire `scripts/doc_counts.py` as
   `checks.doc-counts` (docs must move with every check/test
   addition), or keep it a manual spike?
4. **notify-failure secret**: paste the alerts webhook URL as the
   `ALERT_WEBHOOK` repo secret, or skip straight to Option A branch
   protection now that the x86 infra-kill streak has cooled?
