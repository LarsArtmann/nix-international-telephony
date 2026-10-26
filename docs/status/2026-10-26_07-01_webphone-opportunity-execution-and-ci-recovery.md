# Status: webphone opportunity execution & CI recovery session

- **Date**: 2026-10-26, 07:01 CET (session ran 2026-10-25 ~18:45 → ~22:15; written next morning)
- **Scope**: this session only — the execution leg of the 2026-10-25 webphone
  deep-dive audit (opportunities #2/#4/#5/#6) plus the CI-red triage trains it
  opened (dialplan, messaging, browser E2E). Based on what was done and
  noticed in-session; no fresh research.
- **Prior snapshots**: audit report `docs/research/2026-10-25_webphone-deep-dive.html`
  (80/100, annotated same-evening), status `2026-10-25_19-37_webphone-deep-dive-audit-session.md`.

## §a FULLY DONE

1. **Opportunity #2 — wall-clock ownership (15 pts)**: both example hosts set
   `time.timeZone = "Europe/Berlin"`; the facade derives
   `services.webphone.settings.timezone` from it (`mkDefault`, `"UTC"` fallback
   when a deployment leaves the host zone unset — upstream fails boot on a
   typo, verified in config.go). The `ringGroups.timeWindow` option
   description now names the zone semantics (FreeSWITCH evaluates `hour=`
   in host-local time; the default 9–17 window was silently UTC before).
   Derived values proven by eval on both hosts; gates green.
2. **Opportunity #6 — state.paths derivation (10 pts)**:
   `services.telephony.state.paths`/`sqliteDatabases` no longer hardcode
   `/var/lib/webphone-backup`, `webphone.db`, `usermgmt.db` — they derive from
   `services.webphone.backup.destDir`/`dataDir`. Behavior-identical at the
   defaults, proven by eval including the passkey branch (demo host).
3. **Opportunity #4 — OIDC SSO deployment recipe (12 pts)**:
   "OIDC SSO surfaces" section in `docs/ops-runbook.md` beside "Passkey
   surfaces" (IdP client registration, verbatim issuer, default redirect URI,
   runtime client-secret staging, shared users map, fail-closed
   `allowedGroups` second gate, passkey/SSO coexistence) + a commented
   `webphone.users`/`oauth2` CHANGEME block in `hosts/pbx-prod`.
4. **Opportunity #5 — the owed browser E2E + csrf suite (12 pts)**: the
   relock's ssoerror-delta browser E2E ran GREEN end-to-end (`E2E-OK`,
   reconnect watchdog, DTMF, 267s clean) on the second attempt — the first
   attempt exposed a real defect (see §d2) which was root-caused and fixed
   first. The csrf-pinning webphone VM suite green.
5. **telephony-dialplan "INVITE 407" — root-caused AND fixed AND A/B-proven**:
   mod_sofia's nonce store (`sip_authentication` in the profile SQLite DB)
   loses a fresh nonce row between challenge and verify under build-load
   vCPU stalls (CI runners build the closure while the VM runs); a correct
   digest then answers `407 stale=true` (verified against FreeSWITCH source:
   the nonce SELECT + `last_nc` anti-replay + stale re-challenge insert).
   The one-round test client gave up with the exact CI signature.
   Deterministic reproduction: a one-shot in-VM deleter removing a single
   nonce row at the challenge boundary — old client `rc=2 INVITE 407`
   (control), fixed client `rc=0 INVITE 503`. Fix: `tests/sip.py` `call()`
   now answers 401/407 re-challenges like a real UA (bounded, 3 rounds).
   Full dialplan check green with the fix; NAT suite green with the change.
   Verdict: exposure, not regression — earlier CI reds cancelled the suite
   before it ever ran after 2026-10-16; the webphone pin was never implicated.
6. **telephony-messaging exonerated**: it never failed — every "red" was the
   forward-auth (10-24) / lock-guard fatals cancelling the suite before it
   ran. Locally green now. Zero known-red checks remain, by evidence.
7. **Report addendum annotated** (non-rewriting): dialplan resolved,
   messaging exonerated, no-known-red statement.
8. **Gates**: `checks.format`, `telephony-eval`, prod toplevel eval,
   `markers_check`, `drift_alarm`, `py_compile` (sip.py, browser-e2e.py) —
   all green, repeatedly, on the final tree.
9. **AGENTS.md audit memory updated** (this morning): timezone + state.paths
   + owed-E2E + OIDC recipe struck from the open-gaps list with the closure
   record.
10. Everything committed by the daemon: a10ca7e, 94a7040, b5127e7, 881e2e0,
    6e03a76, 1a86a51 (CHANGELOG attribution entries written for every change:
    wall-clock, state.paths, OIDC recipe, browser-E2E hardening, dialplan
    deflake).

## §b PARTIALLY DONE

1. **"CI green" is local-evidence-only**: every known-red cause is fixed, but
   NO CI run has proven the set — run 40219400440 was timeout-killed at
   2h05m (120-min budget, zero failed steps), and the six green-candidate
   commits have been **unpushed since yesterday evening** (§d1). The verdict
   is owed to a future run.
2. **Python lint battery not run** on this session's python edits
   (tests/sip.py, tests/browser-e2e.py): ruff/ruff-format/bandit/vulture live
   in buildflow's fast pipeline, which was not run (only py_compile +
   treefmt's non-python scope). Style drift risk: unverified.
3. **Suites never executed post-changes** (cancelled in every CI run, no
   local run this session): `telephony-time-routing` (the one that interacts
   with clocks — the timezone change makes this the highest-value unproven
   seam), `telephony` (the big one), `telephony-boot`, `telephony-prod-boot`,
   `telephony-lens`, `telephony-operator`, `telephony-forward-auth`
   (green-proven yesterday in the prior session, not re-run today),
   ssh/nat-extras/etc.
4. **The dialplan A/B harness is ephemeral**: the one-shot nonce-deleter
   driver script lives in `/tmp/diag7-dialplan.py` — it dies with /tmp. The
   regression value (deterministic race injection) is real but not captured
   in the repo.

## §c NOT STARTED

1. **Push seam** (report opportunity #1, 15 pts — the highest): ntfy/FCM
   facade + `/hooks/ring` + the dialplan ring hook upstream explicitly waits
   on. Blocked on owner scope decision (§g).
2. **ASR transcription facade** (#3, 12 pts): blocked on owner provider
   decision — whisper.cpp loopback vs Google STT v2 EU vs defer (§g).
3. **webphone.retentionDays facade** (#7): owner-gated policy knob (2026-10-01
   T13 precedent).
4. **/metrics consumer card** (#8): owner-gated T12 revival.
5. **serverTiming passthrough** (#9): owner-YAGNI'd, deferred.
6. **TODO_LIST HARVEST** of the 19:37 + this report: owner-gated per the
   12:44 §g/10 precedent — not self-started.
7. **Annotation of the 19:37 status report** (its §f items 12–13 — dialplan,
   messaging — are now resolved): docs-health ANNOTATE lane, not done.
8. **CI budget fix**: the x86_64 flake-check job's 120-min cap is no longer
   sufficient (2h05 kill with zero failed steps). Needs a split or a raise —
   identified, not designed.

## §d TOTALLY FUCKED UP

1. **The daemon push lane died mid-session and I normalized it.** b5127e7
   (19:15) through 1a86a51 (~21:55) — ALL of this session's fixes — have
   been unpushed the whole time; nothing has reached origin since 18:53
   yesterday; the addendum edit sat dirty ~10h overnight. I noticed "ahead 2,
   45 minutes" at 20:15 and logged it as "push lane slow, not my lane" —
   that was already anomalous (the daemon's cadence is minutes) and I should
   have escalated immediately instead of writing a final summary claiming
   "everything rides the push lane". Twelve hours of CI darkness on a
   session whose point was to turn CI green. The work is safe locally; the
   delivery is stalled. (I cannot push — harness rule; §g1 asks for the
   owner action.)
2. **Three format-gate races with the daemon → two doomed CI runs I then
   cancelled.** Twice the daemon committed between my edit and my nixfmt
   pass (a10ca7e, 94a7040), deterministically reddening `checks.format` and
   wasting runner time (40223393443, 40224260579 — cancelled). My
   edit→eval→format ordering invited it; gates must be FIRST after any
   nix-touching edit, before the daemon's commit window.
3. **A false-negative verdict on my own fix.** The first fixed-client proof
   run (0B8) failed with `rc=2 INVITE 407` — because I selected the test
   driver via `ls -dt` on store paths, which carry epoch mtimes: I re-ran
   the OLD driver and briefly believed the sip.py fix didn't work. The
   correct exclusion-based driver lookup then proved the fix (rc=0). A
   tooling sloppiness that could have sent me chasing a nonexistent bug.
4. **First dialplan theory was wrong.** I diagnosed a "VM wall-clock jump"
   from kernel-monotonic vs wall timestamps; reading the raw journal showed
   it was buffered-console drain, not a jump. The AGENTS.md lesson "diagnose
   from the error text, never from a narrative" applies to me, in-session.
   Cost: one analysis cycle on a dead end (the real cause — the nonce-store
   race — surfaced only via direct in-VM measurement).
5. **~90 minutes of waiting on a verdict that never came.** Three watcher
   cycles on run 40219400440 (which then died at the budget cap) while the
   02:52 run's logs already contained everything needed to start the
   dialplan reproduction. Local repro was the evidence machine all along.

## §e WHAT WE SHOULD IMPROVE (self-review, distilled)

1. **Escalate infra anomalies on a clock, not a vibe**: "daemon hasn't pushed
   in 45min" was already a red flag; define it as one (e.g. >2 cadence
   intervals → report to owner in the next message, with the exact ahead
   set).
2. **Gate-before-commit-window discipline**: after any nix/python edit, run
   format+eval gates IMMEDIATELY (daemon commits within minutes); never
   batch gates after other verifications. Two of my three races were this.
3. **View tool before every edit** — three edits bounced this session
   (hosts/pbx, pbx-prod, options.nix) because I'd read them via bash sed.
4. **Prefer local reproduction over remote-verdict waiting** whenever the
   failing artifact is reproducible; CI logs are for triage, not verdicts.
5. **Keep diagnostic harnesses in-repo**: the one-shot nonce-deleter and the
   custom-driver pattern (`--test-script`, driver-drv discovery) are
   reusable; /tmp is where tooling goes to die.
6. **Diag scripts deserve the same care as product code** — two false starts
   on the deleter (mangled guard `${$n:-0}`, wrong `-ge 3` threshold) each
   cost a full VM boot cycle.
7. **Memory updated on closure, not next morning**: the AGENTS.md gap list
   went stale the moment timezone/state.paths landed; it took a
   user-prompted review to strike them.
8. No ghost systems created this session (everything wired and exercised);
   no useful things removed; split brains: two small ones — the duplicated
   wall-clock comment across both hosts (template-duplication, accepted) and
   the now-closed AGENTS.md staleness (fixed this morning).

## §f NEXT (brainstorm fuel — most items are TODO_LIST/ROADMAP grade; harvest is owner-gated)

1. Owner: push b5127e7..1a86a51 + the straggler edits (addendum annotation,
   AGENTS.md bullet, this report) or restart the daemon lane — unblocks
   everything CI.
2. Read the CI verdict on the pushed head: expect format/lock-guard/
   forward-auth/dialplan all green; if the job times out again → item 3.
3. Fix the CI budget: split the x86_64 VM checks into two jobs (or raise
   timeout-minutes); the 2h05 zero-failure kill is the new failure class.
4. Run `telephony-time-routing` locally post-timezone-change (the untested
   clock-adjacent seam).
5. Run the big `telephony` suite + `telephony-boot` + `telephony-prod-boot`
   locally (unproven since the relock — CI kept cancelling them).
6. Run `telephony-forward-auth` once more on the final tree (green-proofed
   yesterday pre-dialplan-fix).
7. Run buildflow fast (or `nix develop -c pre-commit run --all-files`) to
   clear the python lint battery on sip.py/browser-e2e.py edits.
8. Capture the nonce-deleter harness in-repo (tests/ or scripts/) as the
   deterministic dialplan-race regression + document the custom-driver
   recipe in docs/lessons/vm-testing.md (incl. the epoch-mtime `ls -dt`
   trap and driver-drv discovery).
9. docs/lessons/freeswitch.md: add the nonce-store mechanics (sqlite
   sip_authentication, last_nc anti-replay, stale=true on miss, races under
   load; one-round UAs die; nonce-ttl profile knob as mitigation).
10. Annotate the 19:37 status report (§f 12–13 resolved) via docs-health
    ANNOTATE.
11. TODO_LIST HARVEST from the 19:37 + this report (owner-gated).
12. Push seam (#1, 15 pts): facade-only drafting (options + dialplan hook
    shape) is technically unblocked while the provider decision pends.
13. ASR facade (#3): blocked on §g provider answer.
14. webphone.retentionDays facade (#7) — owner-gated.
15. /metrics consumer card (#8) — owner-gated T12 revival.
16. serverTiming (#9) — deferred by owner.
17. Cancelled-run ledger: record 40223393443/40224260579 (doomed-format,
    cancelled by session) + 40219400440 (budget kill, zero failed steps) in
    the CI-verdict protocol notes so future reads don't misclassify.
18. Check the stale `chore/flake-update-2026-09` branch + the pending
    flake-update bot PR (toggle note in AGENTS.md).
19. Consider serializing CI VM checks (the check-vm app pattern) if the
    dialplan-class load flakes recur — cost: wall time; trade-off note.
20. Verify the demo VM renders Berlin wall clock post-change
    (`nix run .#vm` smoke, webphone timestamps + ring-group window).
21. OIDC recipe follow-up: an oauth2 VM leg (the 02:52 clobber fix has no
    VM-level oauth2 assertion — passkey is pinned, SSO is not).
22. docs/deploy.md: mention `time.timeZone` in the operator CHANGEME walk
    (wall-clock ownership landed; deploy doc silent).
23. Unit-test sip.py's re-auth loop (digest over the NEW nonce, bound
    exhaustion) in the stdlib tests lane — the loop is currently only
    VM-proven.
24. CHANGELOG: today's entries are all [Unreleased] — release tag decision
    (owner) once CI proves green.
25. Re-verify webphone upstream freshness (`gh api .../commits/HEAD`) before
    any next ritual; upstream moved +22 at audit time.
26. Report README index: verdict unchanged (80/100); the addendum annotation
    needs no index change — verify only.
27. Consider a workflow_dispatch trigger for the browser E2E CI job if it
    lacks one ("on demand" today = manual/local only).
28. Cancel doomed runs FASTER: the second doomed run sat 8 minutes queued —
    cancel at queue-detection, not after first-log-scan.
29. pbx-lens suite local run (cancelled in every CI run since its +120
    relock; module contract asserted unchanged — prove it once).
30. scrub-check `--history --strict` after this session's daemon commits
    (no secrets touched, but the gate is cheap and the daemon bypasses
    hooks).

## §g QUESTIONS (cannot be figured out myself)

1. **The push lane**: the auto-commit daemon has neither committed (addendum
   dirty ~10h) nor pushed (nothing since 18:53 yesterday) — it looks dead,
   and ALL of this session's fixes are stranded local. I don't push (harness
   rule) and won't restart system services unasked: do you want to push
   `b5127e7..1a86a51` + the three straggler edits yourself, or should the
   daemon be restarted first (and is its stall known/intentional — e.g.
   paused for the night)?
2. **ASR provider** (blocks opportunity #3, 12 pts): whisper.cpp loopback
   (self-hosted, no cloud egress) vs Google STT v2 EU (managed, per-use
   cost) vs defer — which lane, if any?
3. **Push-seam scope** (blocks opportunity #1, 15 pts — the audit's highest):
   ntfy-only, ntfy+FCM, or facade-only-first (wire the stack's dialplan hook
   + options now, pick the transport later)?

---
*Written 2026-10-26 07:01 CET. `.md` at explicit user path demand (HTML is
this repo's status-report default; override flagged per skill). Point-in-time
snapshot: annotate, never rewrite.*
