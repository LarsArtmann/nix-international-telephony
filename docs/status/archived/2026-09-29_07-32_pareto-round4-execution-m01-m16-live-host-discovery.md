# Status Report: Pareto round-4 execution sprint (M01–M16 done, M19 mid-flight)

- **Date:** 2026-09-29 07:32 CEST
- **Session span:** ~05:15–07:32 CEST, one continuous run
- **Source plan:** `docs/planning/2026-09-29_04-52_first-call-to-daily-driver-round4-pareto-plan.md`
- **Starting point:** HEAD `b99ff74` (plan pushed, CI run 36514948861 failure
  verdict pending diagnosis), TODO_LIST 19 open + 12 owner-blocked
- **End state:** 9 of 27 medium tasks fully done and verified, M19
  investigation complete, live-host discovery (see §e), daemon-committed
  HEAD `1aad3e4`, all touched gates green

---

## a) FULLY DONE (verified green this session)

| # | Item                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Proof                                                                                                                                                                                           |
| - | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | **M01 CI verdict proven**: the failure of run 36514948861 was `##[error]The operation was canceled` mid-eval (no concurrency group, no step timeout — infra cancel #3 in a row; the aarch64 job on the same run passed); rerun completed **GREEN** at `b99ff74`                                                                                                                                                                                                                                                                                                                                    | `gh run view 36514948861` → `success`; log tail diagnosis; TODO row closed, CHANGELOG entry                                                                                                     |
| 2 | **M04 webphone stamping relock**: producer `f6239fa` verified reachable from origin/main (HEAD `045edfe`), relocked `3d8df3f` → `045edfe`, binary proof `webphone-2.7.0`, fast gates green, VM suites `telephony-webphone`/`-fax`/`-fax-feed` green, no markup/bundle delta → browser E2E correctly not triggered                                                                                                                                                                                                                                                                                  | commit `f53397a` (daemon commit reworded to house convention via scripted rebase); 2 TODO rows closed; CHANGELOG entry                                                                          |
| 3 | **M14 daemon leak vector**: source-proof (go-commit v0.9.0 shells out to `git commit`, no `--no-verify`, `skip_hooks` is dead code) + **live hole found and fixed**: the pre-commit hook was ABSENT here and in webphone (git-hooks.nix refuses to heal while `.pre-commit-config.yaml` exists; `pre-commit install` refuses when `core.hooksPath` is set; global `~/.gitconfig` points at a nonexistent `.githooks`). Hook reinstalled; scrub-canary (KEY-prefix fake) **BLOCKED** through the real shim; `scripts/heal-pre-commit-hook.sh` created and end-to-end tested from hook-missing state | canary run output `scrub-check: TREE HIT … exit 1`; heal script re-test `hook installed at .git/hooks/pre-commit`; AGENTS bullet + CHANGELOG Fixed entry + owner row for the gitconfig landmine |
| 4 | **M11 vhost split-brain guard + eval-time failregex check**: `web.nix` forces `services.webphone.nginx.enable = mkForce false`, legible assertion in `default.nix`; new `checks.telephony-failregex` runs REAL `fail2ban-regex` over filters extracted from a full module eval (single source of truth) against canned attack/benign lines with exact-count assertions; **negative arm proven** (broke the SIP filter → check FAILed with diagnostics)                                                                                                                                             | `nix build .#checks.x86_64-linux.telephony-failregex` green; broken-filter run printed `FAIL: sip.conf no longer matches … 0 matched, 3 missed`; both example hosts eval `nginx.enable = false` |
| 5 | **M12 webphone /healthz probe**: monitoring.nix arm (curl → same loopback addr nginx proxies to; upstream `GET /healthz` is the app's open readiness probe, verified in server.go); monitoring VM suite extended (healthy node enables webphone; stop webphone → unit FAILS with `webphone /healthz probe failed` → restart → recovers)                                                                                                                                                                                                                                                            | `checks.telephony-monitoring` build green with all three arms live                                                                                                                              |
| 6 | **M13 lock-doctor**: `scripts/lock-doctor.py` — locked revs vs upstream HEADs per input (aliased inputs deduped, tracking ref resolved from `original.ref`, pinned revs skipped, `ahead_by` direction), CI-verdict classifier (canceled → "NO VERDICT", never red), self-test included (it caught a fixture bug on first run — working as designed)                                                                                                                                                                                                                                                | real run: nixpkgs up-to-date on nixos-unstable, webphone current, home-manager correctly reported 96-behind (exposed and fixed the direction bug)                                               |
| 7 | **M15 lock-bump runbook section**: `docs/ops-runbook.md` gains the full section — pre-flight (lock-doctor + reachability check), 6-gate ladder table (relock → binary → fast → webphone suites → browser E2E on markup deltas → full), forward-pin-to-first-green-rev rule, revs-not-versions commit convention, upstream owner command-sheet cross-link                                                                                                                                                                                                                                           | section in place at the runbook tail                                                                                                                                                            |
| 8 | **M16 webphone build CI**: `.github/workflows/ci.yml` in the webphone repo (build `.#webphone`, go tests via devshell with `GOTOOLCHAIN=local`, fast flake checks incl. module eval), pinned action SHAs matching the stack's CI; all three jobs pre-verified locally; committed with rationale message and **pushed** (task-required verification); run `36525394545` completed **success** — the repo's first build-CI green                                                                                                                                                                     | `gh run view 36525394545 -R LarsArtmann/webphone` → success; TODO row closable                                                                                                                  |
| 9 | **M10 verify-live.sh parameterized upstream**: domain now REQUIRED (no host literal, exit 2 without), `PBX_CERT_ISSUER` single-glob contract, new `/healthz` and `/phone-api/` session-gate (401/403) arms; **live-verified against pbx.artmann.tech: 14 passed, 0 failed, exit 0**                                                                                                                                                                                                                                                                                                                | run transcript in session; the 401 expectation verified against the app's `session.Require` handler                                                                                             |

All touched gates along the way: `nix fmt` clean, `telephony-eval` green,
statix eval OK, cross-arch `--no-build` eval green, drift alarm PASS after
each TODO_LIST mutation, webphone VM suites green post-relock.

## b) PARTIALLY DONE

| # | Item                                                      | State                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| - | --------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | **M19 operator ACL hardening**                            | Investigation and design complete: narrow `telephony-fs` group for the FS-state ACLs (nginx keeps `telephony` for recordings/htpasswd only and loses core.db read), operator unit gains the group, `streamTokenSecret`/`streamTokenSecretFile` option pair + per-boot random render in `telephony-operator-auth`, `api.py` `stream_token()` currently HMACs with `self.esl()` (line 218) → new `--stream-token-secret-file` arg. NO code written yet. |
| 2 | **TODO row closures + CHANGELOG for M11/M12/M13/M15/M16** | Deliberately batched for the end of the run; rows still open, entries not yet written, drift alarm not yet re-run for them.                                                                                                                                                                                                                                                                                                                           |
| 3 | **M10 tail: deploy.md §5 pointer**                        | Script landed and live-verified, but §5 does not yet point at it.                                                                                                                                                                                                                                                                                                                                                                                     |
| 4 | **AGENTS.md knowledge additions**                         | M14 trap bullet added mid-session; M11/M12/M13/M15 conventions not yet recorded (fold into M27 slimming pass).                                                                                                                                                                                                                                                                                                                                        |

## c) NOT STARTED (from the plan)

- M18 `buildflow --build-mode full --max-time 60m` + triage → done — 3 full runs; lint backlog fixed; gate shape recorded
- M23 upstream filings (nix-ssh-config HM relock issue/PR, BuildFlow feedback — verify-before-filing first) → done — nix-ssh-config#5 + BuildFlow#25/26/27 filed; 4th item dropped (premise stale at source)
- M24 marker meta batch (AGENTS open-row convention, retro per-item + row-uniformity sweeps) → done — 90 retro verdicts, zero unmarked scoped items
- M25 code cleanup (extract `tests/webphone.nix` config.js python assert, contacts wire cross-link) → done — tests/configjs_check.py + 3-way cross-links; suite green
- M27 AGENTS slimming (16.2 KB → ~14 KB; note: grew slightly this session from the M14 bullet) → done — 15.2 KB (deviation from ~14 target recorded)
- M05 prep (finalize `[Unreleased]`) → done — section date-stamped, headings hook green
- Final full-gate battery for the session's whole diff (`nix flake check` realizing all VM suites, pre-commit `--all-files`, scrub `--history --strict`, 45 stdlib tests) → done — nix-flake-check green in-pipeline; pre-commit/scrub/unittest/drift all green
- All owner-gated lanes untouched by design: M02 (P1–P5), M03 (CI posture), M06–M09 (round-2 decisions + migration), M17 (E2E cadence), M20–M22, M26

## d) TOTALLY FUCKED UP (owned, all recovered)

1. **Issuer-glob regression in verify-live.sh**: my "improved" default
   (`*ISRG*`) rejected the live host's actual issuer
   (`O=Let's Encrypt, CN=YE1`) — the private-repo original matched both
   shapes and I dropped one. Caught by the live run (FAIL), not by review.
2. **`|` alternation from a variable**: assumed `case $x in $pat)` treats
   an expanded `|` as alternation — it is LITERAL. Two broken iterations
   (one bash syntax error that killed the whole script) before settling
   the single-glob contract. Should have tested the matching primitive in
   isolation first.
3. **heal-pre-commit-hook.sh v1**: binary-locating via `nix eval` + regex
   grep failed end-to-end (left the repo hookless mid-test); rewrote to
   the devshell one-liner. Should have run the manual recipe once before
   scripting around it.
4. **lock-doctor direction bug**: used `behind_by` (reads 0 for every
   ancestor) — every input falsely "up to date". Caught only because the
   real run showed differing revs; fixed to `ahead_by`.
5. **Invented edit anchor**: attempted the default.nix assertion edit
   against a gateways-assertion text that did not exist (edit failed
   harmlessly). Rule known, violated.
6. **Rebase blocked by dirty tree**: first reword attempt failed on
   unstaged changes — should check `git status` immediately before any
   history operation in a daemon-driven repo.
7. **Restore-sed scare**: the negative-arm test's restore sed appeared to
   fail (grep -c 0); the file was actually fine — mvdan/sh quoting
   confusion cost a diagnostic cycle.

## e) What we should improve / noticed

- **LIVE DISCOVERY — the deployed host is UP**: `verify-live.sh
  pbx.artmann.tech` answers 14/14 green (webphone 200, `/healthz` 200,
  receiver `{"ok": true}`, token gates closed, LE cert valid 77 days,
  TURN/SIP ports open). This contradicts the standing assumption that
  P1–P5 is still pending — either the owner deployed since the last
  session, or the old billing server is still serving. The M02 lane and
  the "first real call" framing need a reality check before more work
  keyed to "pre-deployment" happens. (Also: ssh banner still greets ~33s
  late — the reverse-DNS stall class, WARN not FAIL.)
- **The gates-vs-daemon gap is structural**: pre-commit is the only
  local gate and it is heal-fragile (M14). CI is the durable backstop —
  but only when a push happens; the daemon never pushes. A stale-origin
  stretch green-locally is invisible until someone pushes. (ahead-check
  exists; consider CI-posture decision M03 with this in mind.)
- **Webphone repo has NO local gates at all** (no pre-commit wiring):
  its new CI (M16) covers push time, but the daemon can commit ungated
  there. Candidate: port git-hooks.nix wiring upstream.
- **Upstream feedback candidates gathered this session**: git-hooks.nix
  non-convergent hook healing (refuses while config exists + hooksPath
  refusal leaves broken state); pma's dead `skip_hooks` config option.
  Both belong in the M23 filing batch with verify-first discipline.
- Match/glob logic must be validated against REAL data before wiring
  into checks (issuer case above); the same discipline that produced the
  failregex negative arm.

## f) Next — up to 48 things (route marks: [AI] = this session can do, [OWNER] = gated)

1. [AI] M19: `telephony-fs` group definition (mkIf operatorApiEnabled) → done — this session (2026-09-29 round-4 completion)
2. [AI] M19: ACL unit switches grants to `g:telephony-fs:rX` (+ default ACLs) → done — this session (2026-09-29 round-4 completion)
3. [AI] M19: operator unit `SupplementaryGroups` += `telephony-fs` → done — this session (2026-09-29 round-4 completion)
4. [AI] M19: operator suite asserts nginx NOT in `telephony-fs` → done — this session (2026-09-29 round-4 completion)
5. [AI] M19: `operator.streamTokenSecret` / `.streamTokenSecretFile` options (pair) → done — this session (2026-09-29 round-4 completion)
6. [AI] M19: exactly-one-of assertion in default.nix → done — this session (2026-09-29 round-4 completion)
7. [AI] M19: `telephony-operator-auth` renders per-boot random stream secret when unset → done — this session (2026-09-29 round-4 completion)
8. [AI] M19: `operatorApiArgs` += `--stream-token-secret-file` → done — this session (2026-09-29 round-4 completion)
9. [AI] M19: `api.py` dedicated stream secret (keep ESL fallback for bare invocations) → done — this session (2026-09-29 round-4 completion)
10. [AI] M19: operator suite arms (secret file mode, token stream still green) → done — this session (2026-09-29 round-4 completion)
11. [AI] M19: gates + TODO row + CHANGELOG → done — this session (2026-09-29 round-4 completion)
12. [AI] deploy.md §5 lead-in pointing at `scripts/verify-live.sh` (M10 tail) → done — this session (2026-09-29 round-4 completion)
13. [AI] Close TODO rows M11/M12/M13/M15/M16 + run drift alarm → done — this session (2026-09-29 round-4 completion)
14. [AI] CHANGELOG entries: failregex check, vhost guard, healthz arm, lock-doctor, runbook section, webphone CI → done — this session (2026-09-29 round-4 completion)
15. [AI] M18: kick `buildflow --build-mode full --max-time 60m` → done — this session (2026-09-29 round-4 completion)
16. [AI] M18: triage output against the AGENTS accepted-noise baseline → done — this session (2026-09-29 round-4 completion)
17. [AI] M18: fix or route real findings; update remainder note → done — this session (2026-09-29 round-4 completion)
18. [AI] M23: verify nix-ssh-config home-manager staleness is still true → done — this session (2026-09-29 round-4 completion)
19. [AI] M23: file the nix-ssh-config relock issue/PR (verify-before-filing + voice) → done — this session (2026-09-29 round-4 completion)
20. [AI] M23: verify + draft BuildFlow feedback items (max_time flag, FOD-hash advisory, mainProgram, todo-checker markers) → done — this session (2026-09-29 round-4 completion)
21. [AI] M23: file BuildFlow issues; close row → done — this session (2026-09-29 round-4 completion)
22. [AI] M23 candidates: git-hooks.nix healing issue; pma dead `skip_hooks` option → open — upstream candidates not yet filed (git-hooks.nix healing, pma dead skip_hooks); verify-first still required
23. [AI] M24: open-row marker convention → AGENTS Conventions → done — this session (2026-09-29 round-4 completion)
24. [AI] M24: retro per-item marker check over ALL archived snapshots → done — this session (2026-09-29 round-4 completion)
25. [AI] M24: annotate any unmarked items found (never rewrite) → done — this session (2026-09-29 round-4 completion)
26. [AI] M24: row-uniformity sweep; record expected open-row warnings → done — this session (2026-09-29 round-4 completion)
27. [AI] M25: extract the inline config.js python assertion to a file → done — this session (2026-09-29 round-4 completion)
28. [AI] M25: wire the extracted fixture into the webphone suite → done — this session (2026-09-29 round-4 completion)
29. [AI] M25: cross-link the contacts wire contract both directions (our suites ↔ upstream configjs_test.go) → done — this session (2026-09-29 round-4 completion)
30. [AI] M25: gates + rows → done — this session (2026-09-29 round-4 completion)
31. [AI] M27: inventory stale/duplicated AGENTS passages → done — this session (2026-09-29 round-4 completion)
32. [AI] M27: compress lesson-adjacent prose to docs/lessons pointers → done — this session (2026-09-29 round-4 completion)
33. [AI] M27: move one-off history to CHANGELOG/docs homes → done — this session (2026-09-29 round-4 completion)
34. [AI] M27: verify ~14 KB budget → done with deviation — 15.2 KB (target ~14); trap density judged the floor, history+dupes removed
35. [AI] M05 prep: finalize `[Unreleased]` (dates, heading hygiene) → done — this session (2026-09-29 round-4 completion)
36. [AI] Final: full `nix flake check` (all VM suites realize) → done — this session (2026-09-29 round-4 completion)
37. [AI] Final: pre-commit battery `--all-files` → done — this session (2026-09-29 round-4 completion)
38. [AI] Final: `scripts/scrub-check.sh --history --strict` → done — this session (2026-09-29 round-4 completion)
39. [AI] Final: `python3 -m unittest tests.test_telnyx_bridge tests.test_telnyx_reconcile` → done — this session (2026-09-29 round-4 completion)
40. [AI] Final: drift alarm + marker gates + git tree state → done — this session (2026-09-29 round-4 completion)
41. [OWNER] M02 reality check: host is live — deployed or old server? Close/reroute the P1–P5 lane accordingly → open — owner lane
42. [OWNER] Push posture: local main is ~8+ commits ahead of origin (relock, guards, scripts all daemon-committed) — push for a CI verdict? → open — owner lane
43. [OWNER] M03 CI posture decision (branch protection vs notification) → open — owner lane
44. [OWNER] M06 round-2 decisions (backup doctrine, timing, kexec appetite) → open — owner lane
45. [OWNER] Fix the global `~/.gitconfig core.hookspath=.githooks` landmine in home-manager (new BLOCKED row) → open — owner lane
46. [OWNER] M20 security hygiene (Telnyx key rotation + scrub prefix, placeholders) → open — owner lane
47. [OWNER] M21 DID lane (Warsaw KYC window, DE DID) → open — owner lane
48. [OWNER] M22 fspbx closure sign-off → open — owner lane

## g) Questions I cannot answer myself

1. **Is pbx.artmann.tech the finished P1–P5 deployment or the old billing → open — owner lane
   server?** Everything external answers green (14/14), but "first real
   calls + CDR rows" and "delete the old server" are still open rows.
   If you already deployed: I close the M02 lane and re-run the §5
   checklist host-side. If not: the old server is still serving and the
   deletion step becomes urgent before cutover.
2. **May I push this repo's main?** Local is well ahead of origin → open — owner lane
   (relock + guards + scripts, all committed by the daemon). Only a push
   gives origin a CI verdict for the whole train — but pushes have been
   explicitly gated so far, and the daemon never pushes.
3. **The `~/.gitconfig core.hookspath=.githooks` entry is host-global** → open — owner lane
   (points at a nonexistent dir — every repo without a local override
   silently runs NO hooks). Fixing it means touching your home-manager
   config (or deleting the entry): yours to decide; the repo-local heal
   script covers this repo meanwhile.

---

_Point-in-time snapshot — annotate, never rewrite._
