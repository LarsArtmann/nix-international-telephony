# Status Report — 2026-10-25 19:37 CET

**Session scope:** "Use ~/projects/webphone SUPERBLY to the MAX" — a full
library-deep-dive utilization audit of the webphone flake input, executed via
the library-deep-dive skill (phases 0-8), plus the gate repairs the audit's
verification surfaced. This report covers ONLY this session's run
(~14:30-19:37 CET). Point-in-time snapshot; annotate, never rewrite.

**Format note:** `.md` at the operator's explicit path demand — an override of
this report type's HTML-canonical default (same as the 12:44 report today).

---

## a) FULLY DONE

1. **The deep-dive is published: `docs/research/2026-10-25_webphone-deep-dive.html`.**
   Verdict: **80/100 (high band), 21/27 applicable capabilities fully
   leveraged, 0 anti-patterns, 5 missed, 5 N/A-with-reasons**. Supersedes the
   2026-10-01 audit (78/100); the 2026-10-07 flake-inputs study (88/100,
   nix-consumption scope) cited and left standing. Score arithmetic shown in
   the report (32-row matrix, round(100×21.5/27)=80); self-consistency gate
   passed (denominators, sort orders, tag balance); browser-verified via
   headless-chromium DOM dump + screenshot (this model cannot view images —
   DOM-level verification is the run trace; the 440KB PNG is at
   /tmp/webphone-report-shot.png).
2. **Phase 0 discipline held.** Prior overlapping reports read before
   auditing (2026-10-01 webphone deep-dive + its same-day execution status +
   addendum; 2026-10-07 flake-inputs deep-dive; today's 12:44 webphone flake
   audit). No duplication; supersession stated in the report.
3. **The audit's headline findings (all evidence-cited in the report):**
   the push seam is upstream-complete and waits on THIS repo's dialplan hook
   (zero references here — top missed opportunity); the ASR transcription
   seam is dark (owner provider decision); timezone unset anywhere → the
   webphone renders UTC; state.paths hardcodes what
   `services.webphone.backup.destDir`/`dataDir` own; retention_days and
   serverTiming unsurfaced; three verification tails open (csrf VM suite,
   browser E2E for the ssoerror.js bundle delta, full flake check).
4. **RED GATE FIXED: `checks.lock-guard`.** The 07:11 daemon lock sweep
   (webphone `6274c85→50c4ac2` +36 commits, pbx-lens +120, nixpkgs bump) had
   no CHANGELOG attribution — lock-guard was red at HEAD and failing every CI
   run since. Wrote the attribution entry (old→new revs, content summary,
   verification state at the pin). `python3 scripts/lock_guard.py` → PASS.
5. **RED SUITE ROOT-CAUSED AND FIXED: `telephony-forward-auth`.** The audit's
   gate run failed it at the break-glass leg ("expected 200, got 302"). Root
   cause (git-archaeology, not guessing): the 2026-10-16 login-brick fix
   (`ee9b5f6`) deliberately removed the satisfy-any loopback trio from the
   forward-auth access phase, but `tests/forward-auth.nix` (last touched
   10-15) still asserted the deleted bypass — CI logs show it failing since
   at least 10-24, masked earlier by lock-guard/messaging failures cancelling
   the suite. Updated the test to pin the NEW contract (loopback follows the
   gate: 302 to sign-in; break-glass rides a more-specific location or gate
   policy). **Proof: the check builds green in-VM locally** (out-path
   returned by `nix build .#checks.x86_64-linux.telephony-forward-auth`);
   today's typed-csrf change is exonerated (failure predates it).
6. **Report discoverability + memory (deep-dive done bar):**
   `docs/research/README.md` index created (first index for the 5 reports;
   refresh triggers per row); AGENTS.md carries the durable outcome (verdict
   line + gap list + refresh triggers) in the webphone section.
7. **Cheap gates green on the session's changes:** markers_check (78 files,
   0 findings), drift_alarm (PASS), checks.format/treefmt incl. nixfmt over
   the test edit (PASS), lock-guard (PASS).

## b) PARTIALLY DONE

1. **BuildFlow as the session gate.** First fast run surfaced the
   forward-auth red (valuable) but also realized VM checks; my re-run (job
   046) was backgrounded without a budget cap and got entangled with a
   SIBLING session's `buildflow --build-mode=full --budget 15m` lanes running
   on the same tree (17:48/19:06/19:27 processes) — I killed my job rather
   than duplicate theirs. Every individual gate it would have covered was
   verified directly (see a/7 + a/5). The sibling full run owns the tree now.
2. **Commit attribution.** The daemon committed+pushed mid-verification with
   heuristic messages: dbd5c6e (CHANGELOG), 0bd8722+bab4dff (report),
   0951eff (report addendum + index + forward-auth fix). Per the owner's
   12:44 ruling on 974a03a, history stays — the CHANGELOG entry and the
   report/addendum carry the why. AGENTS.md was still uncommitted at report
   time (daemon will take it). No hand-authored commit happened this session.
3. **CI green-loop.** Run 40207676418 (bab4dff, 17:03) failed on
   forward-auth — expected: it ran the tree BEFORE the test fix. Run
   40219400440 (0951eff, carries the fix) was in progress at 19:37. Even if
   forward-auth passes there, the streak has other named causes (see c/2).

## c) NOT STARTED

1. **Every audit opportunity** (report §03, ranked): push-seam wiring, ASR
   facade + provider, timezone defaults, state.paths derivation, OIDC
   runbook recipe + pbx-prod demo, retention facade, serverTiming passthrough,
   /metrics consumer card, csrf eval-time arm. Deliberately not started —
   the deliverable was the audit; execution is a new train.
2. **Pre-existing CI reds outside this session's lane:** telephony-dialplan
   "INVITE 407" (02:52 run) and telephony-messaging (10-24 run) — named in
   the report addendum for the next session; not triaged here.
3. **TODO_LIST harvest of this report's §f** (docs-health HARVEST) — pending
   owner instruction, matching the 12:44 session's g/10 precedent.

## d) TOTALLY FUCKED UP

1. **I hit the `rg -rn` hook trap TWICE in one session** (blocked both
   times; the hook explicitly calls it a third-strike class on this host).
   First a stray flag, then I literally typed `rg -rn "" /dev/null` as a
   "probe". Lesson burned in: `rg -n pattern` — recursion is the default,
   `-r` is replace-display.
2. **A 4-hour unattended background gate.** I backgrounded `buildflow`
   (15:45) and did not check it until 19:37 — no budget cap, on a
   daemon+sibling-shared tree. It produced nothing this session needed that
   the targeted gates hadn't already proven. Lesson: a backgrounded gate
   needs a deadline and an owner-check cadence, or it is theater with a PID.
3. **Two whitespace/self-inflicted edit failures** (giant old_string
   mismatch on the report template — recovered by script-splicing the copied
   file; edit-before-read rejections on CHANGELOG/AGENTS — recovered by
   reading first). No damage, but both were avoidable with read-first
   discipline on big blocks.
4. **CI verdict misread once:** I treated a "success" run (10-23 15:13) as
   ci.yml green when it was a Dependabot run — the workflow filter
   (`--workflow ci.yml`) corrected it and moved the "last real green" back
   to 10-16. The forward-auth regression window narrowed accordingly; the
   root cause was unaffected, but the first window I stated was wrong.

## e) WHAT WE SHOULD IMPROVE

1. **Beat the daemon when attribution matters.** The lock-guard fix and the
   report both went out under heuristic messages because I finished
   verification before committing. The 12:44 session already named this
   (same-window bookkeeping); this session re-proves it: commit the
   attribution-carrying artifact FIRST, verify after, amend never (pushed).
2. **Background gates need caps.** Any `run_in_background` gate should carry
   `--max-time`/budget flags up front (buildflow supports them) and a
   scheduled check; otherwise kill it the moment a targeted gate supersedes
   it — I did, four hours late.
3. **Read CI verdicts through the workflow filter from now on** —
   `gh run list --workflow ci.yml` — Dependabot/gitleaks successes pollute
   the plain list and misdate regressions.
4. **Skill-sequencing worked** (library-deep-dive → buildflow before format
   territory → status-report before this file): keep the loop. The
   forward-auth root-cause via CI log archaeology + `git -S` is the pattern
   to keep for any future "since when is this suite red" question.

## f) Things we should get done next (session-derived, ranked)

| # | Task | Impact | Effort | Category |
|---|------|--------|--------|----------|
| 1 | Push seam: `webphone.push.*` facade + inbound-DID dialplan action POSTing `/hooks/ring` (upstream is waiting on this repo) | 5 | M | Feature |
| 2 | Timezone: `time.timeZone` on hosts + derive `settings.timezone` (one line each) | 3 | S | UX |
| 3 | ASR facade (fail-closed, default off) + owner provider decision — whisper.cpp loopback vs Google STT v2 EU | 4 | M | Feature |
| 4 | Read CI verdict of run 40219400440 (carries the forward-auth fix); if dialplan/messaging still red, triage them as their own trains | 4 | S | Quality |
| 5 | state.paths: derive from `services.webphone.backup.destDir`/`dataDir` instead of literals (default.nix:77,82,86) | 2 | S | Correctness |
| 6 | OIDC/OIDC-runbook: deployment recipe beside "Passkey surfaces" + commented pbx-prod demo block (12:44 §f/5, still open) | 3 | S | Documentation |
| 7 | Browser E2E for the current pin (ssoerror.js bundle delta fires the runbook trigger) + telephony-webphone VM suite for the typed csrf shape | 3 | M | Quality |
| 8 | Add eval-time csrf arm to tests/eval.nix pinning typed fronts → rendered keys (12:44 §f/4, still open) | 2 | S | Quality |
| 9 | `webphone.retentionDays` facade beside recording.retentionDays | 2 | S | Feature |
| 10 | serverTiming facade passthrough (deferred by owner YAGNI 12:44 §c/3 — re-open only on need) | 1 | S | Feature |
| 11 | /metrics consumer card in the operator window (owner-gated T12 revival; fence stays) | 2 | M | Feature |
| 12 | Triage telephony-dialplan "INVITE 407" red (02:52 CI; gateway 407 anti-spoof class?) | 4 | M | Quality |
| 13 | Triage telephony-messaging red (10-24 CI log) | 3 | M | Quality |
| 14 | HARVEST this report's §f into TODO_LIST.md per docs-health (pending owner instruction) | 3 | S | Documentation |
| 15 | Full `nix flake check` green run once dialplan/messaging are triaged (CI has not been green since 10-16) | 4 | M | Quality |
| 16 | webphone relock ritual to a ≥50c4ac2 rev once upstream settles (22-commit drift; browser E2E rides it) | 2 | M | Maintenance |
| 17 | Consider `time.timeZone` implications for ringGroups.timeWindow semantics (evaluated in UTC today) | 2 | S | Correctness |
| 18 | Upstream (webphone repo): its FEATURES "Browser E2E" row owes a stack E2E run too (2026-10-01/02 markup trains) — coordinate with item 7 | 2 | M | Quality |

Session-scoped honesty over padding: eighteen concrete items, not fifty —
everything else observed belongs to the two pre-existing red suites (items
12-13) or is already ranked inside the published report's §03.

## g) Questions I can NOT figure out myself

1. **ASR provider call (blocks audit opportunity #3):** self-hosted
   whisper.cpp on loopback (sovereignty-aligned, needs a server deployed by
   the stack), Google Cloud STT v2 EU region (zero infra, cloud egress for
   caller audio), or defer the seam entirely?
2. **Push seam scope (blocks opportunity #1):** wire it against self-hosted
   ntfy only (de-Googled lane — but the stack then ships/needs an ntfy
   server: in-scope as a module, or operator-brings-URL?), include FCM
   (needs a Google service-account file), or facade-only now and dialplan
   hook when the Android shell train (webphone-android) goes live?
3. **History hygiene for today's daemon shards** (dbd5c6e/0bd8722/bab4dff/
   0951eff carry this session's report, CHANGELOG attribution and test fix
   under heuristic messages, already pushed; CI 40219400440 is running on
   them): leave history (my lean — the CHANGELOG/report carry the why, same
   ruling as 974a03a this morning) or rebase-re-author the four shards into
   one attributed commit (rewrite on a remote mid-CI-run)?

---

_Report written by Crush (glm-5.3) at operator demand; .md format is an
explicit operator override of this report type's HTML-canonical default._
