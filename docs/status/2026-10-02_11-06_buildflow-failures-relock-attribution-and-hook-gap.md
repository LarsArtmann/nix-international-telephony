# Buildflow failure triage, webphone relock attribution, and the hook gap — session status

Point-in-time snapshot: 2026-10-02 11:06 CEST. Written by the session that
took the 08:41 `buildflow --fix --build-mode full --budget 5m --max-time 5m`
failure (25/44 steps failed, exit 69) to green-except-sibling-WIP.
Scope: this session's run plus hazards noticed while running it. No
research beyond that.

Repos touched: `nix-international-telephony` (this repo),
read-only side-eyes at `~/projects/webphone` (upstream tip check, templ
diffs). Session commits: `ca146eb` (lint fixes, via daemon),
`81194dc` (CHANGELOG lock attribution, hand-authored),
`2823913` (scrub fix + lesson, hand-authored), `0976dd3`/`1879ec0`
(status-row annotations + report, via daemon).

## a) FULLY DONE

1. **ruff-check-fix loop killed (4 consecutive red runs → green).**
   Root causes: EXE001 on three shebang scripts that had lost their exec
   bit (`scripts/lock_guard.py`, `tests/telnyx_stub.py`,
   `tests/whatsapp_probe.py`), PLW1510 on the four `subprocess.run`
   git-walker calls in `scripts/markers_check.py` (now explicit
   `check=False` — each site already handles returncode manually), and
   RUF015 in `tests/test_operator_sms.py` (slice-of-comprehension →
   `next()`). Evidence: `ruff check` clean on all five files; the 122-test
   stdlib suite passes unchanged; the step is green in the full pipeline
   run. Committed `ca146eb` (daemon sweep of the working tree).

2. **Webphone lock moves attributed + gate ladder back-filled.** The
   input had moved three times unattributed (`f706575b5285` →
   `8b575c9898e5` → `d0ee9f5b0d34` → `ffaa03fd5ce5`, 2026-10-01 23:22
   through 2026-10-02 08:33 daemon sweeps) — lock-guard's exact failure
   class. Ran the runbook ladder late: binary proof
   (`nix build .#webphone` → webphone-2.8.0), `nix fmt` +
   `nix flake check --no-build` (clean), webphone + fax + fax-feed VM
   suites (exit 0), 122 stdlib tests, browser E2E (see a5), DOM-contract
   selector pre-check against the upstream templ sources (all 13 E2E ids
   present at the new rev; `theme-preload.js` intact; no unload guards
   added). Hand-authored CHANGELOG entry + commit `81194dc`.
   `python3 scripts/lock_guard.py` → PASS. Verified: upstream tip IS
   `ffaa03fd5ce5`, so future `nix flake update` runs cannot move the
   webphone input again until upstream advances.

3. **`nix.nixPath` eval warning eliminated.** The rename warning printed
   on every eval was a queued cleanup item slated to "ride the next lock
   move" — this session's relock was that move.
   `modules/telephony/ops.nix`: `nix.nixPath` → `nix.settings.nix-path`.
   Evidence: `nix flake check --no-build` is now warning-free (only the
   benign aarch64-omitted note remains). Status rows 10 and 13 in the two
   2026-10-01 snapshots annotated `→ done` with the riding-lock-move
   provenance (commits `0976dd3`, `1879ec0`).

4. **Pre-commit hook healed + battery all-green.** `.git/hooks/pre-commit`
   was ABSENT (the known git-hooks.nix non-convergence class) — restored
   via `scripts/heal-pre-commit-hook.sh`, then
   `nix develop -c pre-commit run --all-files`: changelog-headings,
   deadnix, gitleaks, nixfmt, scrub-check, statix all Passed. The
   absence is how the scrub hit in (d3) landed unnoticed.

5. **Browser E2E green at the new webphone rev, stall signature
   documented.** First run stalled its full 300 s marker window in the
   theme-flash check (wrongpass phase passed; the throttled hard reload
   never issued a single HTTP request; chromium spun ~23% CPU) while
   three VM suites ran concurrently. Idle re-run: clean pass,
   `THEME-CHECK-DONE` recorded, exit 0. Static evidence exonerates the
   webphone delta. Root-cause note appended to
   `docs/lessons/webrtc-browser.md` ("run the browser E2E alone"; the
   zero-requests+spinning signature = load flake first).

6. **scrub gate hit fixed.** `modules/telephony/options.nix` `answerDids`
   example `17287289311` (DID-shaped, pattern-flagged; landed 10-01
   through the hook gap) swapped to the NANP-reserved fictional range
   `15550001000`, matching the test suite's 555-01xx convention.
   Commit `2823913` carries the fix plus the lesson from a5.

7. **Buildflow's "9 tools unavailable" diagnosed.** `buildflow doctor`
   shows global-PATH misses (bandit, cargo-*, codespell, dprint, eslint,
   govulncheck, interrogate); the pipeline provisions the load-bearing
   ones via the pinned `nix develop` env — the same failed run executed
   dprint and vulnix through it. No gap. Status row 12 annotated
   `→ done` with the verdict.

8. **Full verification run at the correct budget.** Reran
   `buildflow --fix --build-mode full --max-time 60m` (the 5 m cap was
   the original nix-build killer): ruff-check-fix green, lock-guard
   green, nix-build completes, exactly one attribute red — the
   sibling-owned `telephony-cdr-cancel` (see d1). Store-level proof:
   all 34 x86_64-linux checks EXCEPT cdr-cancel build green
   (`nix build --no-link` exit 0).

## b) PARTIALLY DONE

1. **Full-pipeline green status.** What works: every BuildFlow step
   except nix-build passes; nix-build builds everything except
   `checks.x86_64-linux.telephony-cdr-cancel` (its only failed
   attribute; `nix-hash-fix` cascades from that verdict). What remains:
   the cdr-cancel attribute itself — owned by the sibling lane that is
   actively rewriting the suite (last move 11:12 on 10-01). Blocker:
   lane collision, not technical. → open (sibling-owned).

2. **nixpkgs lock-move attribution.** What works: status row 14 widened
   to name BOTH unattributed nixpkgs moves (`b4fd65b19` shim-forward,
   then `c59305bab206` in the 10-01 23:22 sweep). What remains: no
   CHANGELOG entries written — lock-guard fences only webphone, and the
   owner lane owns the nixpkgs story (the 2026-10-01 restore incident
   proves nixpkgs sweeps can break the aarch64 lane). → open (owner lane).

3. **Theme-check stall root cause.** What works: flake-vs-regression
   question answered (flake; re-run green; static DOM-contract evidence)
   and the mitigation documented. What remains: no attribution of the
   underlying browser-tooling behavior — chromium moved patch-level
   `154.0.8037.57` → `154.0.8037.92` with the nixpkgs sweep, untested as
   a suspect. Effort: M (two controlled VM runs with a pinned chromium).
   → open.

## c) NOT STARTED

1. **aarch64 FreeSWITCH glibc fix.** The 2026-09 monthly nixpkgs refresh
   sits on `chore/flake-update-2026-09` because FreeSWITCH 1.11.1 fails
   to compile against glibc 2.44 headers (`mod_enum.c` via the ldns
   assert path). Not started; waiting on an owner decision (nixpkgs fix
   vs overlay patch). Still wanted — it blocks every future monthly
   refresh. → open.

2. **Live-host deploy of this session's state.** The host is behind:
   webphone pre-`ffaa03fd`, `nix.settings.nix-path` rename, voice-agent
   options. Deploy lane (`docs/deploy.md`, `.#pbx-prod`) — deliberately
   not started here; CI must be green first, which cdr-cancel blocks.
   → open (deploy lane).

3. **Everything in section (f) below except the items already routed.**
   → open.

## d) TOTALLY FUCKED UP

1. **`telephony-cdr-cancel` blocks ALL CI on main.** Severity: blocks
   development (every push evaluates a red check; the 10-01 snapshot
   states no CI run can go green until it resolves). Root cause (known,
   documented by the sibling session): the suite's fs_cli premise is
   dead — the originate answer-path returns `+OK <uuid>` where the test
   expects failure; the suite is sibling WIP (new file 10-01 10:41,
   never green), and the pre-relock worktree run at base `1e7df77`
   reproduces the identical failure, so it is NOT caused by the relock
   or by this session's changes (drv hash `3bqwfnsk…` identical between
   the 08:43 and my rerun → deterministic). Mitigation: local green
   shape = the 34-check store proof (a8); CI stays red until the
   sibling restructures or removes the check.

2. **The auto-commit daemon swept four tracked-input lock moves in ~9 h
   with zero attribution.** Three webphone (`8b575c98`, `d0ee9f5b`,
   `ffaa03fd`) + one nixpkgs (`c59305bab`). Severity: the webphone half
   is caught (lock-guard red, now repaired); the nixpkgs half is
   UNFENCED and historically dangerous — the 10-01 "restore the
   last-CI-green flake.lock" entry documents an unvetted nixpkgs sweep
   breaking the aarch64 FreeSWITCH compile outright. Root cause:
   buildflow's `nix-flake-update` repair step + the daemon's
   commit-heuristic, with no gate on the nixpkgs node. Mitigation: none
   structural yet (see e1, e5).

3. **Pre-commit hooks were absent for ~a day and a scrub-pattern hit
   landed through the gap.** Severity: moderate (the hit was a synthetic
   example, but the gate class is the leak-prevention canary — a real
   secret would have sailed through the same hole). Root cause:
   git-hooks.nix cannot heal a lost hook (AGENTS.md documents the
   fragility); nothing detects absence proactively. Mitigation: hook
   healed (`scripts/heal-pre-commit-hook.sh`), hit fixed, battery green
   — but absence detection is still open (e2).

## e) WHAT WE SHOULD IMPROVE

1. **BuildFlow's `nix-flake-update` repair step should not sweep
   tracked inputs.** Every `--fix` full run re-updates ALL inputs;
   when upstream moves, the lock lands at an unvetted rev and
   lock-guard reds (or worse, nixpkgs breaks aarch64 silently). Fix:
   `--exclude nix-flake-update` by default in this repo's
   `.buildflow.yml` skip_steps, or gate the step on
   `scripts/lock-doctor.py` + the ritual.

2. **Hook-absence watchdog.** The crushrc guard checks skill fan-out at
   session start; nothing checks `.git/hooks/pre-commit`. One more
   generated guard line (warn on missing hook, pointer to the heal
   script) would have caught d3 a day earlier.

3. **Serialize the browser E2E against VM-realizing builds.** The
   morning run interleaved `nix flake check` (505 checks) with the
   nix-build VM tests; my first E2E attempt overlapped three VM suites.
   Both produced contention symptoms. Buildflow could mark the browser
   suite (and VM-realizing checks generally) as exclusive-lane steps.

4. **lock_guard's tracked-input set is too narrow.** webphone-only
   fencing let the nixpkgs node move unattributed twice. Extending the
   tracked set to nixpkgs (with the CHANGELOG-attribution contract)
   converts the row-14 class from doc-only to enforced.

5. **Session self-critique (what I forgot / could do better):**
   - I piped the 60-minute buildflow run through `tail -60`, so the
     step summary was lost and I had to reconstruct the verdict from
     the store. `tee` to a file would have kept it.
   - `${PIPESTATUS[0]}` is a bashism that silently expanded empty under
     this shell — I briefly trusted an empty "E2E-EXIT=" before
     re-verifying with a direct `nix build` exit code. The
     "never trust a piped exit code" lesson is IN the 10-04 snapshot
     and I still reached for the pipe pattern twice.
   - I initially read `git diff flake.lock` against the working tree
     and got nothing — the daemon had already committed the move
     minutes after BuildFlow ran. On this tree, lock forensics must go
     through `git show <rev>:flake.lock`, never the worktree.
   - I nearly started fixing `telephony-cdr-cancel` before reading the
     10-01 snapshot that routes it to the sibling lane. Reading the
     open snapshots BEFORE diagnosing a red check would have saved the
     detour — AGENTS.md says "detect lanes before editing"; the
     snapshots ARE the lane registry.

## f) Top things to get done next

Ranked by impact. Verdicts route per the marker convention; this
section is the HARVEST ground for TODO_LIST/ROADMAP.

| #  | Task                                                                                                                                                                              | Impact | Effort | Category      |
| -- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ | ------ | ------------- |
| 1  | Resolve `telephony-cdr-cancel`: sibling lane decides restructure (premise is dead: `+OK` answer-path) or remove the check; CI on main stays red until then                        | High   | M      | Bug           |
| 2  | Exclude `nix-flake-update` from BuildFlow's repair steps in `.buildflow.yml` (tracked inputs must move only through the runbook ritual)                                           | High   | S      | Cleanup       |
| 3  | Extend `scripts/lock_guard.py` to fence the nixpkgs node (CHANGELOG attribution contract), converting row-14's doc-only gap into an enforced gate                                 | High   | M      | Quality       |
| 4  | Write CHANGELOG entries for the two unattributed nixpkgs moves (`b4fd65b19`, `c59305bab206`) once the owner confirms they are vetted                                              | Medium | S      | Documentation |
| 5  | Fix aarch64 FreeSWITCH 1.11.1 vs glibc 2.44 headers (`mod_enum.c`/ldns assert path) so the 2026-09 monthly refresh branch can merge                                               | High   | L      | Bug           |
| 6  | Add lock_guard to the pre-commit hook battery (the daemon never bypasses hooks — a lock move without attribution would then be blocked at commit time, not discovered next CI)    | High   | S      | Quality       |
| 7  | Add a hook-absence guard (`.git/hooks/pre-commit` exists + executable) to the generated crushrc session-start checks, pointing at `scripts/heal-pre-commit-hook.sh`               | Medium | S      | Quality       |
| 8  | Deploy lane: rebuild the live host on `.#pbx-prod` once CI is green (picks up webphone ffaa03fd, the nix-path rename, voice-agent options)                                        | High   | M      | Deploy        |
| 9  | Post-deploy browser smoke probe against the live host to confirm ffaa03fd renders (the suites prove the VM; the host needs its own confirmation)                                  | Medium | S      | Deploy        |
| 10 | Escalate the x86 infra-kill streak to GitHub support (run URLs already ledgered; rerun protocol exhausted at 3)                                                                   | Medium | S      | Infra         |
| 11 | Branch protection / CI failure notification (standing TODO; two red streaks sat unnoticed ~26 h)                                                                                  | Medium | S      | Infra         |
| 12 | Serialize VM-realizing checks in BuildFlow (browser E2E + VM suites must not overlap; contention produced two separate stall/failure symptoms today)                              | Medium | M      | Quality       |
| 13 | Bisect the theme-check stall against chromium `154.0.8037.57` → `.92` (pinned-overlay controlled run) — or accept "run alone" as standing mitigation and close it                 | Low    | M      | Quality       |
| 14 | `nix-hash-fix` step: 87% historical failure rate per BuildFlow's own warning — investigate the failing pattern or skip the step in config                                         | Medium | S      | Cleanup       |
| 15 | cdr-cancel evidence ordering: move the MASTER-CSV dump BEFORE the `-ERR` assert so future failures leave CDR evidence (survives whichever way #1 resolves, if the check stays)    | Low    | S      | Quality       |
| 16 | Decide + document Paperless fax-archiving posture (upstream capability exists off-by-default here; `paperless.url`+`token` both-or-neither)                                       | Medium | S      | Decision      |
| 17 | Add the `/livez` + `/startupz` vhost-reachability asserts to a suite (T10 verdict is doc-only today)                                                                              | Low    | S      | Quality       |
| 18 | Adopt upstream's typed `csrf.trustedProxies`/`trustedOrigins` fronts instead of raw settings                                                                                      | Low    | M      | Feature       |
| 19 | Evaluate `serverTiming.enable` for the live host (new upstream diagnostic knob)                                                                                                   | Low    | S      | Feature       |
| 20 | Consume the enriched `/version` endpoint upstream added (operator window)                                                                                                         | Low    | S      | Feature       |
| 21 | CDR cancelled-leg live-host reproduction (registered-but-never-answering endpoint; in-VM path proven impossible — TODO_LIST row carries the base-attribution evidence)            | Medium | M      | Bug           |
| 22 | Document `--print-out-paths` as the standard suite invocation in AGENTS.md commands (piped-exit-code lesson, recurred today)                                                      | Low    | S      | Documentation |
| 23 | Add `tee <logfile>` discipline for long buildflow runs so step summaries survive output truncation                                                                                | Low    | S      | Documentation |
| 24 | Document the synthetic-DID convention (555-01xx range) next to the scrub-patterns template so future option examples are born gate-clean                                          | Low    | S      | Documentation |
| 25 | Update the regression-timings baseline (nix-flake-check +142% reflects the post-relock build volume, not a regression; stale baselines cry wolf)                                  | Low    | S      | Cleanup       |
| 26 | Follow through on BuildFlow#28 (findings-gate ignore mechanism) so the two documented port-collision pairs stop failing the gate in full mode                                     | Low    | S      | Cleanup       |
| 27 | Follow through on BuildFlow#26/#27 (FOD-hash advisory, mainProgram data carve-out) — the sounds.nix hash-inlining and meta advisories are the live instances                      | Low    | S      | Cleanup       |
| 28 | Extract `packages/sounds.nix` hashes to a dedicated `hash.nix` (nix-checker advisory; cleaner diffs, scriptable updates) — or record as accepted                                  | Low    | S      | Cleanup       |
| 29 | Vulnix build-closure noise (~68 advisories against toolchain drvs): repo-level suppression config or accept permanently as documented noise                                       | Low    | M      | Cleanup       |
| 30 | `buildflow doctor`: make the tool-availability check nix-develop-aware (or document that global-PATH misses for devShell-provisioned tools are expected)                          | Low    | S      | Cleanup       |
| 31 | Bump or deliberately document the `home-manager` input pin (123 commits behind per lock-doctor)                                                                                   | Low    | S      | Cleanup       |
| 32 | Increase the stall-diagnostics `tail` window on nginx access.log (tail-30 cut off `theme-preload.js` evidence during today's first stall)                                         | Low    | S      | Quality       |
| 33 | Once cdr-cancel resolves: push, then airtight `gh run view` verdict for the pending run (36977272474 lineage), and land T08                                                       | High   | S      | Infra         |
| 34 | After the two 2026-10-01 snapshots' open rows resolve, run the annotation pass + `check-rows` uniformity sweep, then archive both to `docs/status/archived/`                      | Low    | S      | Documentation |
| 35 | HARVEST this report: pull section (f) rows into TODO_LIST.md (actionable) and ROADMAP.md (brainstorm-scale), delete nothing from this snapshot — the arrows above are the routing | Medium | S      | Documentation |

## g) Questions I cannot answer myself

1. **Is automated lock sweeping (`nix flake update` via BuildFlow's
   repair step + the daemon) wanted at all for tracked inputs, or is the
   runbook ritual the only sanctioned path?** I tried answering from the
   tree: AGENTS.md documents the ritual as mandatory and the sweep as
   the hazard class, yet the tooling still sweeps. If the ritual is the
   only path, I will exclude the step and extend lock_guard (f2, f3, f6)
   without waiting.

2. **Is the sibling session still actively rewriting
   `telephony-cdr-cancel`, or is it abandoned?** The last file move was
   11:12 on 10-01 and the snapshot routes it "owner/sibling lane" — lane
   ownership is invisible to me from the tree. If abandoned, I take
   over: restructure around the `+OK` answer-path reality or remove the
   check; if active, I stay out entirely.

3. **For the theme-check stall: bisect chromium (one pinned-overlay VM
   run pair, ~1–2 h wall time) or accept "run the browser E2E alone" as
   the standing mitigation?** I can run the experiment, but it is only
   worth the wall time if browser-suite reliability matters more to you
   than the mitigation cost (serializing the suite, f12).
