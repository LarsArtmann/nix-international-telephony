# Status Report: The Pareto Plan Execution Session (26-medium sprint)

**Date:** 2026-08-27 15:24 CEST
**Session span:** ~11:00–15:24 CEST (one continuous run)
**Starting point:** HEAD `9bf2c62` (plan pushed), CI green, browser-e2e never dispatched.
**End state:** HEAD `9527068`, 7 new commits, 8 new VM suites, 2 uncommitted files
(`tests/browser-e2e.py` drill-hardening + the TODO row for the SIP.js bug — see §d).

---

## a) FULLY DONE (verified green this session)

| #     | Item                                                                                                             | Proof                                                                                               |
| ----- | ---------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| M1    | ACME TCP-80 fix + eval assert                                                                                    | `checks.telephony-eval` asserts 80 open in acme / closed elsewhere; negative-proven live            |
| M2    | deploy.md truth pass, runbook owns the canonical port table                                                      | commit `69a00a5`                                                                                    |
| M3    | Push + CI green (both jobs) + browser-e2e dispatched **green on its first-ever run**                             | run `33061454926`, dispatch `33062207832`                                                           |
| M5    | Eval-check extensions: candidate-acl, wss-binding, placeholder counts                                            | negative-proven live                                                                                |
| M6    | CI `--all-systems --no-build` step                                                                               | verified on run `33061454926`                                                                       |
| M7    | pbx-prod boot-smoke suite (`telephony-prod-boot`)                                                                | units up, sofia non-loopback, nginx TLS, spliced secrets REGISTER, no CHANGEME leak                 |
| M8    | Negative eval tests: both-set secret pairs fire assertions AND block toplevel                                    | 4 pairs, `fires` + `blocks` both asserted                                                           |
| M10   | **Voicemail deposit/retrieval/denial** — the session's hardest nut                                               | `tests/vmclient.py` (SIP+PCMU noise+DTMF); wrong-PIN proven via voicemail DB `read_epoch` staying 0 |
| M12   | Ops docs pack: wsprobe walkthrough, browser failure playbook, agenix variant (source-verified)                   | commit `08decd2`                                                                                    |
| M13   | Drift-alarm check (`checks.docs-drift`)                                                                          | fires on injected dupes of both shapes                                                              |
| M14   | Repo hygiene: sip_server dedupe, timedelta migration, favicon, CHANGELOG heading lint                            | dialplan suite green after                                                                          |
| M15   | Annotation tooling upstream (SKILLS repo commit `bcbf485`): section scoping, M/B row IDs, post-write shape check | regression-tested on report copies                                                                  |
| M16   | Health monitoring (`monitoring.enable`) + VM test (dead gateway, stopped profile, healthy)                       | commit `6ddc6b8`                                                                                    |
| M17   | fail2ban SIP jail + VM test (bad REGISTERs → ban, others untouched)                                              | failregex source-verified from sofia_reg.c                                                          |
| M18   | Backups docs (target inventory incl. `/var/lib/private` trap, restic example, restore drill)                     | runbook §Backups                                                                                    |
| M19   | Webphone error surfacing (disconnect reasons, post-login rejection pill)                                         | proven by the browser suite's wrong-pass leg                                                        |
| M20   | Webphone i18n EN/DE with persisted toggle                                                                        | node --check + suite green                                                                          |
| M21   | Declarative IVR (`ivrs.*`) + VM suite (echo key, extension key, fallback hangup)                                 | suite green                                                                                         |
| M22   | Conference rooms (`conferences.*`) + VM suite (two legs, mixed audio both ways)                                  | suite green                                                                                         |
| M23   | Time-based routing (`timeWindow`) + VM suite (clock set into/out of window)                                      | suite green                                                                                         |
| M25   | coturn TLS listener option (`turn.tls.*`, eval-verified; runtime test deferred)                                  | commit `9527068`                                                                                    |
| M26.1 | nix-ssh-config kbd-interactive issue **FILED** (source-verified first)                                           | LarsArtmann/nix-ssh-config#1                                                                        |
| M26.4 | Monthly flake-update workflow (opens reviewable PR)                                                              | `.github/workflows/flake-update.yml`                                                                |
| —     | DTMF-format bug FIXED in the webphone (`Signal=` → `Signal:`, sofia silently ignored the equals form)            | found via M11 work                                                                                  |
| —     | **Full `nix flake check` gate GREEN** mid-session (all checks incl. every new suite)                             | job output GATE=0                                                                                   |

## b) PARTIALLY DONE

- **M11 (browser depth)** — wrong-password leg ✓ (pill rejection proven),
  reconnect DETECTION ✓ (backoff pill), DTMF + media-bytes legs written but
  the final hardened run failed (see §d). The drill found a real SIP.js bug.
- **M9 (RTP byte-flow)** — `getStats` probe implemented (`window.__pcs`
  handle in app.js + `MEDIA-BYTES` assert), never seen green in a log yet.
- **M24** — `vmEmail`/`callerIdNumber`/`*97` twins all land in the generated
  XML (eval-verified); behaviour tests queued in TODO_LIST.
- **M4 (0.2.0 release)** — deliberately deferred to last so it ships
  everything; CHANGELOG is release-ready.

## c) NOT STARTED

- The 0.2.0 tag + `gh release` + repo metadata polish itself.
- Final push of today's 7 commits (nothing since `502dbd1` is on origin).
- `*97`/vmEmail behaviour tests, IPv6 profiles, DSCP marking (ROADMAP).

## d) TOTALLY FUCKED UP (honest list)

1. **The last browser-suite run (EXIT=1) is unresolved.** The drill-hardening
   (reload-recovery) run failed and I did NOT get its log before stopping —
   the log fetch hit cache 502 noise and I never re-read it. State:
   `tests/browser-e2e.py` hardened version is staged but UNVERIFIED.
2. **Real product bug found, unfixed:** SIP.js 0.21 `userAgent.reconnect()`
   never settles after a transport loss — pill sticks at try-N forever;
   reload recovers. Filed as a TODO row, workaround asserted in the suite.
3. **Two mid-edit commits got swept into wrong-labeled commits** (M8/M7
   inside the drift-alarm commit; M14/M19/M20 inside the monitoring commit).
   Content is correct; history granularity is not.
4. **Wasted a long stretch on a ghost chase:** four suites "failed" with a
   familiar drv hash → I suspected stale flake sources, dirty-tree caches,
   daemon races; the standalone render was fine all along. The failures were
   real test bugs (missing vmclient ship, F811 sip_server redefinitions).
   Lesson: reproduce against the rendered artifact FIRST, theorize second.
5. **`git restore` bit me twice** — restoring from HEAD/index while edits
   were uncommitted (recovered from the index once; re-typed once).

## e) WHAT WE SHOULD IMPROVE

- **Verify the artifact, not the mechanism:** render the generated
  dialplan/config standalone (nix-instantiate trick) BEFORE debugging
  flake/git/daemon plumbing. It would have saved ~40 minutes today.
- **Commit after every green suite**, not in waves — prevents both the
  mislabeled commits and the daemon-race window.
- **Interactive driver is the debugging superpower** — worth a paragraph in
  AGENTS.md (how to `--test-script` a probe file against a suite's VM).
- **The suite-lint (F811/type-check) errors cost 3 iterations** because new
  test files duplicated `sip_server`. The common.nix dedupe happened late;
  new suites should be written against the shared helpers from the start.
- **Journald hides sofia-channel EXECUTE lines** (known) — but the
  freeswitch.log FILE has them; dump `/var/lib/freeswitch/log/freeswitch.log`
  FIRST in future dialplan debugging.
- **VM-clock tests must stop timesyncd** before `date -s` — took one full
  suite run to notice the NTP snap-back.

## f) NEXT — up to 50 things, in priority order

1. Re-run the browser suite; read the hardened-drill log; fix what it shows.
2. Land the SIP.js reconnect-hang fix (upgrade SIP.js or own retry loop in
   app.js: timeout around `reconnect()`).
3. Commit the pending browser-e2e.py + TODO row once green.
4. Full `nix flake check` gate re-run (post turn.tls + browser changes).
5. Push all commits; watch both CI jobs + dispatch browser-e2e once.
6. Cut v0.2.0 (CHANGELOG date, tag, `gh release create`, topics/description).
7. `*97` no-record behaviour test (dial `*97<ext>`, assert no WAV).
8. vmEmail end-to-end test (msmtp catch-all in the VM).
9. IVR `*`/`#`/multi-digit key coverage.
10. DTMF end-to-end assert server-side (sofia log sees digit 5, not just the
    webphone's own `#log` entry).
11. Conference pin leg (wrong pin denied, right pin joins).
12. `turn.tls` runtime test with a self-signed cert fixture.
13. Tighten conference list assert (pin exact member-count format).
14. i18n de-leg in the browser suite (toggle to DE, assert a German label).
15. Promote browser E2E CI cadence (owner gate G2).
16. TLS-handshake assert on 5061 (ROADMAP edge-verification idea).
17. wsprobe as suite assertions (ROADMAP idea).
18. 8021 loopback-only assert.
19. aarch64 run of the new suites (`--all-systems` covers eval; consider a
    boot-tcg variant of monitoring/fail2ban).
20. nixpkgs freeswitch network-online PR (docs/upstream.md checklist).
21. nix-ssh-config #1 follow-up PR (kbd-interactive fix + test).
22. First real deployment (G1: server, DNS, ITSP, secrets — owner inputs).
23. Evaluation of the reconnect-hang against SIP.js 0.22/0.23 changelogs.
24. Monitoring: OnFailure= hook example (alert router wiring) in the runbook.
25. fail2ban: nginx/443 scanner jail option (SIP-only today).
26. Backups: a wired `backups.enable` option if the docs recipe proves out.
27. QoS/DSCP options once verified against sofia param names.
28. IPv6 profiles behind `ipv6.enable` (big; needs a dual-stack VM test).
29. Per-extension `vmEmail` HTML template option.
30. IVR nested sub-menus (menu → menu) if a real deployment asks.
31. Conference MOH-when-alone profile option.
32. Webphone call-history export/clear button (UI nicety, i18n'd).
33. Webphone multi-language expansion (the table makes it cheap).
34. Consider `services.telephony.monitoring` alert on CDR growth stall.
35. Eval-check for `turn.tls` port in the firewall set (mirror the 80 assert).
36. Load-test spike: 50 concurrent scripted REGISTERs (sofia reg limits).
37. TLS 5061 manual-mode runtime test with a provisioned cert.
38. Gateway `register=false` (peer-to-peer trunk) dialplan leg test.
39. Docs: option reference dump (`man services.telephony`) for upstream.
40. Second dial-tone: local 3-digit feature codes documented (which exist).
41. `nix flake update` dry-run to warm the monthly workflow's first PR.
42. Split the two mislabeled commits' content into a follow-up
    CHANGELOG note if anyone asks (no history rewrite).
43. Add the interactive-driver debugging recipe to AGENTS.md.
44. Add "stop timesyncd before date -s" to AGENTS.md VM-test gotchas.
45. Consider caching `tests/vmclient.py` assertions on the session log for
    the read-state wait (currently a 30s wait_until at worst).
46. Ship the browser suite's failure dumps as a CI artifact on red.
47. Sops-nix/agenix: a wired example host once the owner picks (G3).
48. Reduce browser suite wall-time (the wrong-pass leg adds ~2 min).
    49.ROADMAP Q2 ITSP provider decision (feeds G1).
49. Quarterly re-run of the docs-health audit (calendar it).

## g) QUESTIONS ONLY THE OWNER CAN ANSWER

1. **G1 deployment inputs:** which server/VPS (provider + arch), which
   domain, and which ITSP? These gate the first real deployment — everything
   repo-side is now built, boot-proven, and release-ready.
2. **G2 browser CI cadence:** the suite is green and self-diagnosing but
   costs ~10 min + a 1–2 GB closure per run — per-push, daily, or keep
   manual dispatch?
3. **Release scope for v0.2.0:** ship today's state (incl. the known
   SIP.js-reconnect bug, documented + workshotted) or hold the tag until
   the reconnect fix lands? My recommendation: ship now, fix in 0.2.1 —
   but the bug is user-visible (stale pill after a network blip), so it is
   your call.
