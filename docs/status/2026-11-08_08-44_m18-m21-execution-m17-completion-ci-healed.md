# Status & Self-Review — M18–M21 Execution + M17 Completion (2026-11-08 08:44)

**Scope.** ONE session: the continuation of the 2026-11-07 SUPERB
ci-truth train (`docs/planning/2026-11-07_09-15_SUPERB-ci-trust-and-truth-pareto-plan.md`)
— M18 (passkey ceremony lane), M19 (ops singles, partial), M21 (CI
topology), the M17 leftovers (providers re-verification, wall-clock
smoke, deep-dive renders), and the M01/M04 CI verdict closure. Ran
ALONGSIDE an active sibling session the whole time (their "nix-native
consolidation train": a secret-predicate refactor of pbx.nix/default.nix,
their own Pareto plan file, docs bookkeeping — commits interleaved with
mine and their refactor HEAD currently reds the eval gate).

**The one-sentence state: five of the train's remaining lanes are
delivered and proven (M01/M04 airtight greens ×5, M17 complete, M21
complete, M18 ~80%, M19 ~50%), but the session ENDS on a red tree that
is NOT mine** — `checks.telephony-eval` fails on a clean checkout of
the sibling's refactor head (`ringGroupDidToplevel` eval), attribution
proven by a stash-based clean-tree run — and the passkey ceremony suite
is one experiment from green with the root cause fully diagnosed.

## a) FULLY DONE

1. **M01/M04 — the airtight CI greens EXIST now.** Root-caused the twin
   1h deaths FIRST: the GitHub annotation said "The hosted runner lost
   communication with the server" — our default-concurrent `nix flake
   check` ran ~10 NixOS VM tests at once on a 7 GB runner and starved
   it to death. Fix: ci.yml pre-builds the VM suites ONE at a time via
   the repo's own `apps.check-vm` driver (eval-discovered list), each
   with a per-suite `CHECK_VM_TIMEOUT` budget (default 45 min, added to
   check-vm; timeout wrapper proven both ways locally: success rc=0,
   `CHECK_VM_TIMEOUT=1` kills mid-suite with the FAILED line, rc=1).
   Pushed as `7ec6556`. Then FIVE consecutive runs over successive
   heads completed GREEN (47–58 min each: `42436537760` over `8342f2b8`,
   `42436496246` over `47a9f0f0`, plus `42439341506`, `42438505651`,
   `42437708582` — all push-event, all jobs success, aarch64 + stdlib
   lanes green throughout). One red in the series (`42434684049`,
   pre-fix) failed EXACTLY as my textagent diagnosis predicted — the
   503 probe draft corrupting tail-position asserts — and the pushed
   fix addressed precisely that.
2. **M17 providers re-verification — ALL files stamped 2026-11-07.**
   Three research subagents did the live fetches (one hit a rate limit
   and was retried); I applied and committed every stamp:
   telnyx.md (re-verified block with messaging-enablement +$0.10/mo
   per number, WhatsApp platform fee + Meta passthrough rates),
   didlogic.md (PSTN $0.005→$0.007/min, "$8/mo FREE tier" framing,
   trunk features/SDK/signup held), commpeak.md (coverage claims
   raised: 100+ countries DDx, A-Z 150+ destinations; still no public
   DID pricing), didww.md (93 countries / 8763 areas, emergency
   counter 40→39, pricing NOW PUBLIC: Local from $1.20/mo + $0.010/min),
   twilio.md (per-country pricing publicly UNVERIFIABLE — URLs 404,
   CDN 403, JS shells; HK OFCA CLI restriction confirmed stricter),
   bandwidth.md (still fully gated), zadarma.md (all 5-country prices
   held; DE setup 28→8 zł, DE now documents in-country-address KYC,
   line counts now per-country DE 10 / CH-HK 2 / PL 1), others.md
   (Flowroute/Voxtelesys/Easybell held; Skyetel + sipgate dismissals
   CHANGED — both grew international DID products), README.md index
   (the pass stamped). Drift/markers/rendering gates green.
3. **M17 deep-dive HTML renders (steps 93–94).** Both reports
   headless-rendered via chromium at full and viewport sizes and
   INSPECTED by me: 2026-10-01 webphone deep-dive and 2026-10-07
   flake-inputs deep-dive render perfectly — CSS alive (Bauhaus
   shapes, scorecard tiles, sidebar), zero dead classes. Screenshots
   in /tmp/render/ (evidence, not committed).
4. **M17 demo-VM Berlin wall-clock smoke (step 95) — DELIVERED as a
   permanent on-demand suite.** `legacyPackages.telephony-demo-wallclock`
   (tests/demo-wallclock.nix): boots the REAL example host
   (hosts/pbx + ssh module), asserts the host zone (timedatectl),
   FreeSWITCH's runtime zone (`fs_cli strftime %Z`), the webphone
   facade (the rendered WEBPHONE_CONFIG JSON carries
   `"timezone": "Europe/Berlin"` — NOT /config.js, which does not
   surface the timezone; the first smoke run proved exactly that by
   failing on the PBX_CONFIG payload), the rendered dialplan window
   (8-20 in the store conf dir from the unit's ExecStart), and the
   after-hours leg END TO END: RTC pinned outside the window
   (`-rtc base=2026-11-11T21:30:00` UTC = 22:30 Berlin; the guest
   reads the RTC as UTC, first run pinned 22:30 and the clock came up
   23:30 — one assert, one lesson), caller dials the ring group and
   the ECHO TEST answers (after-hours transfer, ANSWERED + log line).
   **GREEN: SMOKE6-RC=0.** The demo host gained the timeWindow its
   comment always advertised (startHour 8, endHour 20, after-hours →
   9196).
5. **M21 CI topology batch — COMPLETE** (commit `e82ca47`): the
   `--system` sentinel (the aarch64 eval answer must name the real
   boot-tcg check drv — a stale/missing system eval fails loud), per-
   arch eval timings into `$GITHUB_STEP_SUMMARY`, the aarch64 webphone
   binary build proof as a NAMED step, `canary.yml` (a DELIBERATE red
   weekly, Mon 04:17 UTC, through the same failure→notification wiring
   as notify-failure, unmissably named), and the E2E runner user unit
   documented in the runbook (solo-rule enforcement via ExecCondition
   refusing to start when sibling nix builds run). The cross-arch eval
   job split itself was already the per-system sequential shape from
   2026-10-06 — recorded as satisfied.
6. **M17/M13 bookkeeping.** TODO rows closed with evidence: webphone
   listener-bind-order (`5dfc0ef`-era row), pbx-lens upstream CI heal,
   lens runbook subsection (landed via `724e9ce`), Browser E2E depth
   pins (both asserts proven), plus the three TODO closures commit
   `47a9f0f` and `8342f2b`.
7. **webphone FEATURES.md Browser E2E row refreshed** (sibling repo,
   commit `b19cf624`): the 2026-10-01/02 markup-train obligation marked
   PAID (solo green over stack head, webphone `36f0c6f4`, ended-card
   contract + duration/Close content pins), solo rule reaffirmed.
8. **Daemon-lane discipline held**: four soft-reset + re-author cycles
   (the CI-fix lane, the TODO closures, the provider pass, the M18/M21
   wave) — every unpushed daemon shard re-authored as a hand-authored
   lane commit; hooks green each time.

## b) PARTIALLY DONE

1. **M18 passkey ceremony suite — ~90% there, ONE experiment from
   green.** `tests/passkey.nix` + `tests/passkey-e2e.py`: full WebAuthn
   round trip (CLI-minted one-time token → /enroll create ceremony →
   /login get ceremony → /api/session 200) through a CDP
   virtual-authenticator, deliberately outside checks. Debugging got
   THREE real root causes, each proven at source/journal level:
   (a) `env: '{': Permission denied` — `systemctl show -p ExecStart
   --value` prints a property OBJECT (`{ path=… ; argv[]=… }`), so
   naive first-field cuts hand env a literal `{` to exec; fixed with
   the `path=` extraction (runbook recipe fixed too). (b) the
   projection race — the CLI registers the user as an EVENT, verify
   reads the token from the event store (immediate) but begin reads
   the users_view PROJECTION; begin raced the projector by ~30ms and
   answered `usermgmt.user_not_found`; added a users_view wait. (c)
   passkey mode enables upstream's inline-secret scrutiny — baseNode's
   inline `turn.authSecret` failed the eval; the suite now sources it
   via `authSecretFile` (empty string is that option's "unset" — null
   is not legal for the plain str type). **BUT run 6 STILL answered
   user_not_found at begin WITH the projection wait green** — which
   reframes (b): the wait polled the CLI's own projection flush; the
   SERVER's projector never consumed the CLI's events within the suite
   window (separate engines on one sqlite event store). The next (and
   designed) experiment: `systemctl restart webphone.service` after
   the mint — the boot replay re-projects ALL events, which is also
   the honest operator workaround. NOT yet run.
2. **M19 ops-singles — half landed.** DONE: the mailbox-quota option
   (`services.telephony.voicemail.maxMessages`, null = vanilla 100;
   renders the vanilla-template override with only max-messages
   swapped — conference.conf precedent, builder-grepped; eval arm
   `quotaCheck` added with null/set arms), the pipefail/pipes-mask-rc
   lesson in vm-testing.md (from MY OWN `| tail -3` probe bug this
   session — arm 2 "passed" because `$?` was tail's), the
   `scripts/pbx-status.sh` triage helper (shellcheck-clean), the
   post-deploy browser smoke recipe (deploy.md §5.2: verify-live →
   pbx-status → real-browser pass → theme toggle), the buildflow
   doctor run (works; missing-tool advisories are PATH-dependent —
   the devshell pins provide them). NOT STARTED: MWI provisioning
   check, voicemail greeting surface/runbook recipe, status-answer
   helper is DONE (see pbx-status.sh — same item), attribution
   store-sharing note verified ALREADY in operating.md (§e item closed
   as pre-existing).
3. **M18 theme-only E2E variant — code complete, suite NOT yet run.**
   `tests/theme-e2e.nix` + a THEME_ONLY=1 gate in browser-e2e.py's
   `__main__`; wired as `legacyPackages.telephony-theme`. Eval green;
   first runtime run deliberately not launched yet (browser suites
   run SOLO and the passkey lane owns the solo window this session).
4. **The M17/M19/M20 TODO row bookkeeping lags the deliveries** — the
   sibling consolidated the swept rows into two batch rows (70 "CI
   topology batch", 71 "Passkey/test depth batch"); row 70 is now
   FULLY delivered by my M21 lane but the row is still open, and row
   71's remaining sub-items (enroll wrapper unit = verified ALREADY
   upstream, MWI, greeting, quotas-landed) need the row rewritten
   rather than struck.

## c) NOT STARTED

1. **M20 messaging depth batch** (WhatsApp media in-VM arm, `.chan-mms`
   badge CSS, portal 40008 wording pin) — untouched, est. 45 min.
2. **M19 MWI provisioning check + voicemail greeting recipe** — the
   remaining voicemail-family singles.
3. **The passkey ceremony upstream issue** — the begin-vs-projection
   race (and/or the separate-engines design) is now WELL-evidenced for
   a verify-before-filing upstream report to webphone (journal lines,
   users_view probes, the verify-200/begin-503 pair). Not filed.
4. **M21 canary.yml first live firing** — the workflow is pushed but
   only Monday 04:17 UTC (or a manual dispatch) proves the plumbing.
5. **Row 70/71 TODO bookkeeping + CHANGELOG verdict entries** for this
   session's deliveries.
6. **The theme-only and passkey suites' first GREEN runs** (code
   complete, runtime proof pending).
7. **`checks.doc-counts` archived-counts pin** (report-1 item 46,
   still unevaluated).

## d) TOTALLY FUCKED UP

1. **I popped a stash entry I did not create.** Attributing the eval
   failure, I ran `git stash push <4 files>` then `git stash pop` —
   but the pop hit a conflict on tests/passkey.nix, revealing the
   stash I popped was a PRE-EXISTING entry (from the sibling's lane,
   base commit `41ec5c5`). The pop smeared THEIR stale passkey.nix
   (with `mkForce null`) over MY working copy and left conflict
   markers (`UU`) in the tree. Resolved to my version and committed
   (`d66fc3b`) — but I violated my own rule from the status-report
   era: before ANY git operation that modifies the working tree,
   check `git stash list` / what exists. The tree ended the session
   CLEAN of markers (verified zero conflict markers), and the foreign
   stash entry survives (still in the stash list minus the popped
   one).
2. **My own probe bug (twice)**: the check-vm timeout proof "passed"
   both arms because each probe ended in `| tail -3` — `$?` was
   tail's. Caught on the second arm's suspicious rc=0, re-run with
   explicit rc capture, and codified as the pipes-mask-rc lesson in
   vm-testing.md. A third instance bit later: `demo_call(..., 4, ...)`
   passed an INT into a string-concat (TypeError inside the VM run).
3. **Two edit attempts landed nothing while reporting success** — the
   passkey.nix projection-wait block: two `edit` calls returned
   success, grep showed the block absent. Root cause: my "reads"
   between edits were bash `sed`/`grep`, which do NOT refresh the
   edit tool's read-state; the tool kept failing on the stale-read
   guard while I misread the errors as successes. The actual block
   loss earlier (the wait block vanishing post-edit) was the SIBLING's
   stale-buffer save — the same lost-update class as report-1's §d2.
   Discipline re-learned: View tool before every edit, verify edits
   by grep with a NEW marker string.
4. **I launched passkey suite runs 3–6 with known-stale expectations**
   — run 4 knew the projection wait was clobbered (I saw mod time
   newer than my read and did NOT verify the content before
   launching); the run wasted ~10 minutes answering a question I
   could have answered with `grep -c USER-PROJECTED` in one second.
   The harness-discipline rule (instrument before theorize; check the
   bytes before re-running) applied to suite LAUNCHES, not just edits.
5. **The session inherited a red tree at handoff without a safe-push
   decision**: my `d66fc3b` (quota arm + passkey turn fix) is
   committed but UNPUSHED because `telephony-eval` is red on the
   SIBLING's head (their refactor, clean-tree proven) — pushing now
   would stack my verdict on a red I cannot fix in their lane. Held
   per "don't fix unrelated bugs", but the HOLD decision itself is
   undocumented in the repo — it lives only in this report.

## e) WHAT WE SHOULD IMPROVE

1. **Stash hygiene is a lane boundary, not a convenience**: `git
   stash pop` on a shared tree must be preceded by `git stash list`
   and a content check (`git stash show -p`), or avoided entirely in
   favor of `git worktree`/scratch branches for attribution runs. The
   clean-tree attribution experiment SHOULD have used a worktree.
2. **Verify-before-launch extends to suite runs**: before any
   background VM build, grep the testScript content for the marker
   you expect the run to prove. Every wasted run 4-type launch is
   10+ minutes of TCG/KVM time.
3. **Cross-session eval attribution should be the FIRST response to
   any sudden mass-eval red**: the stash-based clean-tree run settled
   "mine vs theirs" in one build — it should be reflexive (and a
   worktree makes it side-effect-free).
4. **Upstream cross-engine projection semantics need a documented
   operator recipe**: mint-then-restart (or mint-then-wait-for-
   projection) belongs in the runbook's Passkey surfaces section once
   run 7 proves which form works — operators will hit this on real
   hosts.
5. **The sibling-session protocol needs a shared lane ledger** — we
   both ran trains in the same tree for two days; the only collision
   mechanisms were stale-buffer saves and now a stash entry. A
   WHO-IS-WHERE note file (or distinct worktrees per lane) would
   remove the class.
6. **`legacyPackages` suites are invisible to CI** — both new suites
   (demo-wallclock, passkey) eval-checked locally but never gated
   remotely; if either breaks eval, CI stays green. The runbook's
   relock ladder gates them; consider a weekly scheduled dispatch
   (owner decision — CI-minutes cost).

## f) Up to 50 things we should get done next

Ranked: impact/effort, execution-order. Agent-executable unless marked.

1. Passkey suite run 7: add the post-mint `webphone.service` restart
   (+ healthz wait) before the browser phase; expect begin to find the
   user after boot replay. This closes M18's E2E.
2. If run 7 greens: commit + push the passkey lane (held behind the
   eval red — see 4).
3. If run 7 stays red: capture the journal again; if begin STILL
   user_not_found after a full boot replay, file the upstream issue
   (webphone: enroll begin cannot see CLI-registered users across
   engine restarts) with the full evidence chain.
4. Coordinate the eval-red handoff: the sibling's refactor lane owns
   the `ringGroupDidToplevel` fix; when their fix lands and
   telephony-eval greens, push `d66fc3b` and watch CI.
5. Run the theme-only suite solo (`legacyPackages.telephony-theme`) —
   code complete, needs its one green.
6. M20a: WhatsApp media in-VM arm (tests/messaging.nix) — the media
   download path asserted in-VM.
7. M20b: `.chan-mms` badge CSS in operator.css (visual + suite).
8. M20c: portal 40008 wording pin (replace the catch-all self-
   description assert in the stdlib suite).
9. M20 suite + gates + one hand-authored commit.
10. M19b: MWI provisioning check — probe the real fsapi command in a
    driverInteractive session (voicemail count/msgcount shape), then
    assert it in dialplan.nix after the voicemail fallback.
11. M19c: voicemail greeting recipe — runbook subsection: *97 records
    greetings per box, where the files land (storage dir), which
    state.paths entry backs them; verify the path exists in a VM probe.
12. Rewrite TODO row 70 (CI topology) as DELIVERED → delete the row
    (done work is deleted, never struck).
13. Rewrite TODO row 71: remove the delivered sub-items (theme-only
    E2E, passkey ceremony E2E, secrets.md note, CHANGEME prep verified
    existing, enroll wrapper verified upstream, store-sharing note
    verified pre-existing, quota option landed) — leave MWI + greeting
    - whatever remains as bounded rows.
14. CHANGELOG: Fixed/Added entries for the CI serialization fix (with
    the runner-starvation root cause), the demo-wallclock smoke, the
    M21 batch, the provider stamps, the quota option.
15. CHANGELOG: the airtight-green verdicts (five runs, heads named)
    close the M01/M04 CI verdict claims.
16. AGENTS.md: the ExecStart property-object lesson (`systemctl show
    -p ExecStart --value` prints `{ path=… ; argv[]=… }` — cut field
    1 and you exec `{`) — one line in the process/hard-won section.
17. AGENTS.md: the pipes-mask-rc rule is in vm-testing.md — add the
    AGENTS one-liner pointing at it (one home, pointer only).
18. AGENTS.md: the RTC-as-UTC lesson (guest reads RTC base as UTC;
    Berlin = UTC+1) — one line in the vm-testing pointer cluster.
19. runbook: the passkey enrollment recipe gains the restart/projection
    note (whatever run 7 proves) beside the path= extraction fix.
20. runbook: the E2E runner user unit section gains the theme-only and
    passkey lane names (already listed — verify the names match the
    final flake attrs).
21. File the webphone upstream issue for the begin/projection (or
    cross-engine) enrollment race — verify-before-filing: reproduce
    minimally, cite journal + users_view evidence (blocked on run
    7's classification).
22. Re-run `checks.doc-counts` after the sibling's test-count drift
    (their 54-file sweep touched tests/) — run doc_counts, bump the
    AGENTS/FEATURES claims if moved.
23. Scrub-check the session's new files (`scripts/pbx-status.sh`,
    tests/passkey-e2e.py) against the scrub patterns — gitleaks
    passed at commit time, but the daemon swept intermediates.
24. Evaluate: does `checks.doc-counts` need the archived-counts pin
    (69/10)? (carried from report-1; still unevaluated).
25. Canary first firing: `gh workflow run canary.yml` (workflow_
    dispatch) to prove the plumbing before Monday's schedule.
26. After the sibling's eval fix: full `nix flake check` locally once
    (the serialization lesson applies locally too — consider
    `nix run .#check-vm` for the VM phase).
27. Attribution store-sharing note: already in operating.md — close
    any TODO fragment pointing at it (grep for stale pointers).
28. The deep-dive render screenshots (in /tmp/render/) — if the
    owner wants durable evidence, copy into docs/research/ renders/
    (owner-visual lane; the inspection verdict is recorded here).
29. M19: post-deploy smoke recipe cites `scripts/pbx-status.sh` —
    smoke-test the script against a running VM once (it degrades to
    dashes offline by design; verify the degradation path).
30. The `env: '{'` bug class generalizes: grep the repo's docs for
    other `systemctl show -p ExecStart` extraction recipes and fix
    them all the same way (deploy.md? monitoring?).
31. Consider upstreaming the `path=` extraction fix to the webphone
    runbook (their AGENTS/docs carry the CLI recipe too).
32. Voice-agent lane (sibling's): re-run doc_counts and bump claims
    if their test additions moved the count (report-1 item 41,
    still open).
33. README.md stale-singular-gateway grep (report-1 item 49, still
    open): `grep -rn "gateway\." README.md` and fix leftovers.
34. scripts/ ruff sweep (standing Low row, report-1 item 35).
35. buildflow doctor note: record the PATH-dependence finding in the
    AGENTS BuildFlow paragraph (one clause; the finding is in this
    report's context).
36. Probe `/startupz` during the webphone shutdown drain (report-1
    item 38) — cheap VM probe via driverInteractive.
37. Suite-side port-poll helper dedup (report-1 item 39): wait-for-8080
    into tests/common.nix.
38. Bridge 503 retry-semantics doc in the ops-runbook messaging
    section (report-1 item 40).
39. lock-doctor `--target-rev` runbook wiring (report-1 item 37).
40. Runbook BuildFlow invariants row (`--max-time` cap note; report-1
    item 36).
41. Render-inventory: the webphone-audit refresh trigger (report-1
    item 42's owner gate) — the audit doc says refresh on next
    webphone release tag; `36f0c6f4` may qualify (owner call).
42. The M21 `--system` sentinel could ALSO assert x86 (currently only
    aarch64 is sentinel'd) — symmetric guard, one line.
43. ci.yml: the notify-failure job could carry a run-url to the
    canary's notification for diffability (minor).
44. tests/passkey.nix: the driverInteractive probes created several
    /tmp/probe-*.py files — if any is worth keeping as a harness,
    salvage per the keep-diagnostic-harnesses-in-repo rule (else
    they die in /tmp as the lesson warns).
45. Demo-wallclock: the FS-log timestamp format assert (a Berlin
    rendered-timestamp grep in freeswitch.log) would pin the FS-side
    RENDERING, not just the zone query — one more assert if wanted.
46. The quota option: VM-level proof (set maxMessages=2 in a suite,
    fill the box, hear the full prompt) — the eval arm proves the
    render, not the runtime behavior (time-boxed: one suite).
47. M18's enroll-wrapper unit: verified upstream (5 island tests) —
    record the verification in the row rewrite (13), no new test.
48. Owner-lane reminders batch (unchanged): Sanctum PAT revocation,
    Telnyx key rotation, Warsaw DID/KYC, flake-update bot Actions
    toggle, ALERT_WEBHOOK secret for the canary to actually post.
49. The foreign stash entry (`stash@{0}` WIP on 41ec5c5, popped copy
    resolved): confirm with the owner/sibling whether their passkey.nix
    line (`mkForce null`) was an abandoned approach — if yes, drop the
    entry; if theirs is alive, reconcile.
50. When M18–M21 fully close: archive the 2026-11-07 SUPERB plan per
    the markers convention (annotate → `git mv` to planning/archived).

## g) Questions I cannot answer myself

1. **The sibling's eval-red (`ringGroupDidToplevel` on their nix-native
   refactor head): is their lane actively fixing it right now, and do
   you want me to fix it myself if their session went quiet?** My
   clean-tree attribution proves the red is theirs (my quota arm is
   additive), but two sessions owning one red is how yesterday's
   clobber wars started. A one-line "theirs" or "yours" decision
   unblocks my pushes (currently held at `d66fc3b`).
2. **Passkey begin-after-restart (run 7's design): if the boot replay
   ALSO answers user_not_found, do you want the upstream issue filed
   with the full evidence chain (journal + users_view probes + the
   verify-200/begin-503 pair), or is the CLI-mint flow considered
   owner-only enough that a runbook workaround suffices?** Filing
   upstream follows the verify-before-filing gates; I have the
   evidence, I don't have the appetite decision.
3. **The demo-wallclock + passkey suites are on-demand lanes (matching
   the browser E2E precedent) — do you want a weekly scheduled CI
   dispatch that runs BOTH (plus the theme lane) as a "browser/VM
   extras" workflow, accepting the ~40–60 min of runner minutes per
   week, or do they stay manual-only until the owner promote gate
   (report-1 question 3, still unanswered, now covers three lanes)?**

---

**Verdict summary.** The train's 1% promise landed: the CI gate is
healed with a root-caused fix (runner starvation) and FIVE airtight
greens, M17 is fully closed with live-provider evidence, M21 is done,
and the two new on-demand lanes (demo-wallclock GREEN, passkey one
experiment away) follow the house pattern. The costs were again
concurrency (the sibling's stale-buffer save, a foreign stash entry,
their eval-red at handoff) — each now has a named countermeasure in
§e. Wait for instructions.

**Addendum (08:52, post-commit gate sweep).** `markers_check.py`
currently reports SEVEN findings — NOT from this report (it passes
clean): the file-level and per-item MONOTONICITY arms fire on three
ARCHIVED snapshots
(`2026-10-07_16-00_mailbox-status-verdict-evidence-tier-self-review.md`,
`2026-10-07_16-24_proof-loop-closed-sibling-dispatch-lane-discovered.md`,
`2026-10-28_10-10_webphone-relock-ritual-session.md`) whose committed
HEAD marker counts sit below their historical peaks — marker loss
landed in COMMITTED history during this session's window, riding the
sibling's 54-file sweep lane, and the worktree is clean (nothing to
restore by me without touching their lane). The remedy per the
convention is restore-by-append in THEIR lane (count recovery clears
the finding). My report's own arms pass; the tree handoff carries:
their eval red (telephony-eval, clean-tree proven), their seven
monotonicity findings, and my held unpushed commit `d66fc3b` plus this
report.
