# Round-4 execution complete: M17–M27 lane closed, full gate proven

Session: 2026-09-29 ~07:45–09:20 CEST. Continuation of the round-4
Pareto plan (`docs/planning/2026-09-29_04-52_first-call-to-daily-driver-round4-pareto-plan.md`)
after the M01–M16 session (report archived as
`docs/status/archived/2026-09-29_07-32_pareto-round4-execution-m01-m16-live-host-discovery.md`,
all its AI items now resolved inline).

## a) FULLY DONE (each verified this session)

1. **Quick batch**: 6 TODO rows closed (failregex, healthz, runbook,
   vhost guard, lock-doctor, webphone CI), 7 CHANGELOG entries,
   deploy.md §5 lead-in pointing at `scripts/verify-live.sh <domain>`,
   drift alarm green.
2. **M19 operator ACL hardening — landed and suite-proven**: new
   `telephony-fs` group (operator-API-only) owns the FS-state read
   ACLs + the rendered stream secret; nginx keeps `telephony`
   (htpasswd/recordings) and cannot read the FS tree; new
   `operator.streamTokenSecret` / `.streamTokenSecretFile` options
   (at-most-one assertion, negative arm proven: eval throws) with
   per-boot random default; `api.py` gains
   `--stream-token-secret-file` (ESL password stays only as the bare
   binary fallback). Operator VM suite extended (nginx group
   non-membership, ACL group on the tree, secret 0640
   root:telephony-fs, runuser-read-denied) — **GREEN**, including the
   token-authed audio flow on the dedicated secret.
3. **M25**: `tests/configjs_check.py` extracted (self-documenting wire
   contract fixture; positive + 3 negative arms proven locally; webphone
   VM suite green in-VM); contacts seam cross-linked three ways (fixture
   docstring, browser-e2e round-trip docstring, upstream
   `configjs_test.go` comment — upstream `go vet` + `TestConfigJS` green).
4. **M23 upstream filings (own repos, verify-first)**:
   nix-ssh-config#5 (the flake-lock update branch already relocks
   home-manager to HEAD but sits unmerged — 96 commits behind on
   master); BuildFlow#25 (max-time/budget flag-only, source-cited
   `local:"true"`), #26 (FOD-hash advisory noise), #27 (mainProgram
   data carve-out). A 4th item (todo-checker marker text) was NOT
   filed: scanner.go:73-78 already embeds the marker text at HEAD —
   premise stale, dropped.
5. **M24 marker meta batch**: open-row marker convention recorded in
   AGENTS Conventions (§b/§c/§f/§g scoping, routed-verdict-beats-
   uniformity, `→ corrected` appends); block-aware per-item retro sweep
   over ALL 60 archived snapshots — **90 evidence-cited verdicts added
   across 15 files** (incl. the 2026-09-18 extraction report's 50-row §f
   table), re-check reports **zero unmarked scoped items**; row
   uniformity swept: the 3 PARTIAL rows are correct mixed verdicts, the
   128 open-routed rows the accepted style — both recorded.
6. **M27 AGENTS slimming**: 16.7 KB → 15.2 KB — relock ritual now points
   at its ops-runbook home, the false "upstream has NO build CI" claim
   fixed (M16 landed CI), history compressed, every trap kept inline.
   Deviation from the ~14 KB target recorded (trap density is the
   floor).
7. **M05 prep**: `[Unreleased]` date-stamped and heading-hooked
   (changelog-headings hook green); tag/release itself stays
   owner-gated.
8. **M18 canonical full gate — run 3× and triaged**: run 1 died at
   ruff (11 findings); runs 2–3 executed the whole pipeline with
   `nix-flake-check` **green at the final tree** (all VM suites). The
   findings gate exits with exactly the 4 documented port-collision
   errors (the two accepted pairs) — recorded in AGENTS as "that IS the
   green shape". **24-finding Python lint backlog fixed** (details in
   d/CHANGELOG); vulnix baseline updated (no longer crashes; ~68
   build-closure toolchain advisories).
9. **Final battery, all green**: `nix flake check` (in-pipeline),
   pre-commit `--all-files` (6/6 hooks), `scrub-check --history
   --strict` (23 patterns clean), `python3 -m unittest …` (45/45),
   drift alarm, marker gates, mypy/ruff/bandit-medium+/vulture all
   zero.
10. **Docs hygiene**: the 07:32 report fully annotated (all 40 AI items
    resolved, f22 routed open, 8 owner items + 3 questions routed) and
    `git mv`'d to `docs/status/archived/`.

## b) PARTIALLY DONE

| Item | State | Gap |
| ---- | ----- | --- |
| M23 candidate filings (f22 of the prior report) | verified as candidates | git-hooks.nix non-convergent healing + pma dead `skip_hooks` NOT yet filed — verify-first still owed → open — next session's filing batch |

## c) NOT STARTED (owner lanes; untouched by design)

M02 reality check, M03 CI posture, M05 tag/release, M06 round-2
decisions, M20 security hygiene, M21 DID lane, M22 fspbx closure,
hooksPath landmine fix → open — owner.

## d) TOTALLY FUCKED UP (owned)

1. **First buildflow launch used a nonexistent `--parallel` flag**
   (inherited from a stale session note) — died in 1s; relaunched
   without it.
2. **Waited ~10 min on a "sibling buildflow" that wasn't one** — the
   pma-wrapped run targets a DIFFERENT repo; only its CPU was shared.
   Should have checked the process cwd first.
3. **Two annotation-script guard failures** (wrong line number for the
   assert_fs_hour row; nosec-block on an already-marked line) — both
   caught by the scripts' own assertions, both fixed by looking at the
   real lines. Guards paid for themselves twice.
4. **Whitelist round-trips**: extended vulture whitelist first for
   do_DELETE only to learn mypy flags do_GET/do_POST too (typeshed
   omits the dispatch methods on the base) — three passes instead of
   one; should have run mypy on the whitelist immediately after the
   first extension.

## e) WHAT WE SHOULD IMPROVE

1. Full-mode buildflow cadence: this 24-finding backlog accrued because
   no full run happened for 10 days while five Python files landed —
   the fast-mode default hides ruff/mypy/bandit/vulture drift.
2. The marker-convention retro sweep should be a standing tool in
   scripts/ (the block-aware checker lived in a heredoc); next
   docs-health round should land it.
3. BuildFlow findings-gate exits nonzero on the accepted-noise pairs —
   an nix-checker ignore mechanism is the structural fix (upstream has
   no config surface at all; BuildFlow#25–27 are the start of that
   conversation).

## f) Next — ranked (route marks: [AI] = next session can do, [OWNER] = gated)

1. [OWNER] Answer the three standing §g questions (host identity, push, hooksPath) → open — carried from the prior report
2. [OWNER] M03 CI posture (branch protection / notification) → open — Critical row
3. [OWNER] M05 cut v0.3.0 (Unreleased is finalized and hook-green) → open — owner timing
4. [OWNER] M06 round-2 decision batch (backup doctrine, migration timing, kexec) → open — gates M07–M09
5. [AI] File the two remaining upstream candidates (git-hooks.nix healing, pma `skip_hooks`) with verify-first
6. [AI] Land the block-aware marker checker as scripts/ (from this session's heredoc) + wire a docs gate
7. [AI] Push webphone local main (1 unpushed daemon commit: the configjs cross-link comment) — owner-approved push lane exists for CI'd changes
8. [AI] nix-ssh-config: merge the update_flake_lock_action branch once CI is green there (issue #5 tracks)
9. [OWNER] M20/M21/M22 lanes (Telnyx key rotation, DID KYC window, fspbx closure) → open — owner

## g) QUESTIONS I CANNOT ANSWER MYSELF (carried, unanswered)

1. **Is pbx.artmann.tech the finished P1–P5 deployment or the old
   billing server?** → open — owner (everything external answers green;
   the P1–P5 row stays blocked on this)
2. **May this repo's main be pushed?** Local is ~25+ commits ahead
   (everything green locally; only origin CI can verdict the train). →
   open — owner
3. **The host-global `core.hookspath` landmine** (home-manager): fix or
   drop? → open — owner

---

_Point-in-time snapshot — annotate, never rewrite._
