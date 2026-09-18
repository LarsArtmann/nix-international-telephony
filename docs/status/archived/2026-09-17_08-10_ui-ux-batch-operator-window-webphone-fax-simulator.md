# UI/UX batch execution: operator window, webphone features, fax, simulator — build-out session

**When:** 2026-09-17 07:00–08:10 CEST
**Scope:** execute the TODO_LIST P-lanes (P7–P23, owner-gated rows excluded) in one
session: source-verified design, module + webphone + operator-package
implementation, test updates, and VM-suite verification.
**Status:** implementation substantially landed and mostly verified; 1 suite red
(conference pin), 2 suites untested (operator, browser E2E), docs not yet
harvested. Details below, brutally honest per the report contract.

---

## TL;DR

Every TODO lane got real code. Two genuine product bugs were found and fixed by
reading upstream FreeSWITCH source instead of guessing (CDR CSV template
mismatch; conference pin prompt unresolvable without a sound_prefix). Ten
checks are green. The conference pin test burned three 5-minute VM runs on
assertion-format guesses — the exact anti-pattern the repo's lessons warn
about — and is still red. The new operator suite and the extended browser E2E
have never been run. No docs (TODO_LIST/FEATURES/CHANGELOG) have been touched.

## What this session did NOT do (kept out on purpose)

Owner-gated rows only: P1–P5 (deploy/user steps), P9 (trunk hardening, gated on
first call), P18 (release, G3), P19.1 (key rotation), P24/P25 (owner cadence),
sops-nix example, upstream BuildFlow feedback. No SSH anywhere; no deploys.

---

## a) FULLY DONE (implemented AND verified)

| Item                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Evidence                                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P8 research: transfer semantics** — read sofia v1.10.12 source: blind REFER re-routes the REFERing party's PARTNER leg through the default dialplan (`sofia_handle_sip_i_refer` → `switch_ivr_session_transfer(b_session, exten)`); attended (Replaces) does `switch_ivr_uuid_bridge`; `MFLAG_REFER` is default-on; FS consumes all REFERs server-side so the webphone only sends REFER + waits for the NOTIFY sipfrag                                                                                                                               | `~/tmp-research/sofia_1.10.12.c:8938-9660`; sip.js 0.21.2 `Session.refer(URI\|Session)` + `Notification` API confirmed from the pinned npm tarball                                          |
| **P12/P13/P21 research: CDR shape** — found that our generated `default-template="example"` matches NO registered template; mod_cdr_csv silently falls back to an 18-field unquoted template                                                                                                                                                                                                                                                                                                                                                           | `mod_cdr_csv.c` source (template hash has only "default"); **fixed** in `modules/freeswitch.nix` to `value="default"` (13 quoted fields)                                                    |
| **Dialplan dry-run simulator** (`packages/telephony-operator/dialplan_sim.py`): parse-time condition semantics (document-order flat walk, break attr, wday/hour ranges), transfer-chain following, DID-vs-internal context auto-pick, bridge/voicemail/fax/ivr/echo/hangup outcomes, CLI + library API                                                                                                                                                                                                                                                 | Verified against 8 materialized dialplan scenarios (DID→group in/out of hours, echo, fax ext, fax DID, PSTN allowed/denied, *98) — all correct                                              |
| **Read-model API** (`packages/telephony-operator/api.py`, stdlib-only): `/api/health` (fs_cli sofia/gateways/units/cert), `/api/cdr` (parses BOTH 13- and 18-field shapes), `/api/sms`, `/api/simulate`, `/phone-api/voicemail/{summary,messages,audio,DELETE}` with per-extension SIP-credential auth (fs_cli `user_data`, compare_digest, 5-min cache) + HMAC stream tokens, `/phone-api/history` (accountcode-scoped)                                                                                                                               | Booted locally against fake Master.csv/dialplan: all endpoints asserted incl. 401 paths; `vm_delete` used for deletes so mod_voicemail invalidates MWI itself                               |
| **Operator dashboard** (`packages/telephony-operator/webroot/`): CDR table w/ filters + recordings link-out, health cards, SMS tab, simulator UI; zero dependencies, same-origin                                                                                                                                                                                                                                                                                                                                                                       | Served paths wired via nginx (`/operator/`, `/operator-api/` → `:8071/api/`, `/phone-api/`) in `modules/telephony/web.nix`                                                                  |
| **Operator package derivation** — builds; `bin/telephony-operator-api` + `bin/telephony-dialplan-simulate` + webroot; meta kept (BuildFlow)                                                                                                                                                                                                                                                                                                                                                                                                            | `nix build` of `packages/telephony-operator`                                                                                                                                                |
| **Module interface** (`options.nix`): `fax.enable/.extension`, `gateways.<n>.faxDid`, `operator.{enable,apiUser,apiPasswordFile,smsMessageStore}`, `webphone.phoneApi.enable`, `webphone.contacts`; assertions for collisions, auth-file requirement, faxDid uniqueness                                                                                                                                                                                                                                                                                | `nix flake check`-style eval passes for both hosts                                                                                                                                          |
| **Generator** (`freeswitch.nix`): fax extension (rxfax + TIFF under recordings fax dir), spandsp module load, public faxDID routing, **CDR template fix**, **conference sound_prefix fix** (see d/b below)                                                                                                                                                                                                                                                                                                                                             | Generator eval + host toplevels build                                                                                                                                                       |
| **Wiring**: `pbx.nix` — `telephony-operator-auth` oneshot (ESL password + shared htpasswd) and `telephony-operator.service` (DynamicUser, `BindReadOnlyPaths=/var/lib/private/freeswitch` — the only non-root path into sofia's private state, IPAllow localhost, fs_cli/systemd/openssl PATH); `web.nix` — config.js carries `phoneApi` flag + contacts; nginx locations with auth posture split (operator = nginx basic auth; phone-api = in-service ext auth)                                                                                       | Demo host toplevel builds; unit file args verified in store output; prod template evals                                                                                                     |
| **Hosts**: demo (`hosts/pbx`) enables phoneApi + operator + contacts (store-rendered demo password); prod template enables both with CHANGEME secrets + fax                                                                                                                                                                                                                                                                                                                                                                                            | Both toplevels evaluate/build                                                                                                                                                               |
| **Webphone frontend** (all six features, both i18n languages): P8 transfer button + inline row + blind/attended REFER + NOTIFY sipfrag verdict handling; P10 Notification permission at login-gesture, incoming notification, distinct WebAudio ringtone, tab-title flash, reconnect "N call(s) preserved"; P11 voicemail panel (badge, list, token-audio play, delete); P12 shared+personal contacts w/ click-to-dial, redial + save buttons, server CDR history merged; P17 ICE panel (selected pair, RTT, loss/jitter, codec, plain-language hints) | `node --check` (real nodejs) + `nix build .#webphone` (0.2.0); CSP compatible (all same-origin); served-markup asserts updated in `tests/webphone.nix` — **telephony-webphone suite green** |
| **Tests**: `tests/operator.nix` written (deposit → summary → list → token audio RIFF → delete → MWI 0; wrong/cross-mailbox 401s; nginx auth gating; health/cdr/sms/simulate; simulator 400 on bad input); `tests/webphone.nix` asserts all new markup/logic; `tests/common.nix` gains `assert_fs_hour`/`assert_file_log`/`sip_call` helpers (P23.3) and time-routing suite now uses them — **telephony-time-routing green**                                                                                                                            | Suite runs below                                                                                                                                                                            |
| **P23.3 test-depth**: conference PIN leg via `vmclient join --pin` (RFC 4733 digits) — wrong pin rejection proven; `docs/lessons/freeswitch.md` records the sound_prefix lesson                                                                                                                                                                                                                                                                                                                                                                        | see d) for the red remainder                                                                                                                                                                |
| **Verification (green)**: telephony-eval, statix, deadnix, docs-drift, format (nixfmt+prettier), webphone pkg, telephony-dialplan, telephony-webphone, telephony-time-routing, telephony-voicemail                                                                                                                                                                                                                                                                                                                                                     | `NIXEXIT:0` per suite (honest exit codes after the pipeline-masking slip)                                                                                                                   |
| **Demo VM smoke of fixes**: conference wrong-pin no longer dies with "Cannot ask the user for a pin" after the sound_prefix fix                                                                                                                                                                                                                                                                                                                                                                                                                        | `/tmp/conf2.log`                                                                                                                                                                            |

## b) PARTIALLY DONE

1. **telephony-conference pin suite — RED.** The repo bug is fixed (wrong-pin
   leg now runs the prompt/reject path and ends cleanly), but the right-pin
   assertion timed out in two shapes (`list count` output format never
   verified; then `grep '@'` on `board list` while up). Three 5-min VM burns;
   the third failure (conf3, `board list` grep '@') was interrupted before
   diagnosis. Next step is ONE debug run dumping the literal `conference board
   list` output — not another blind retry.
   → done — root causes fixed at module level 2026-09-17 (14:06 session: flattened compat sounds + `#`-binding strip); suite green
2. **P16 fax**: options + dialplan + module load + storage dir + prod wiring
   done; the planned VM test (spandsp loaded, fax ext answers rxfax, TIFF dir
   wired) is NOT written; live Telnyx T.38 test remains owner-gated.
   → done — `tests/fax.nix` written + green 2026-09-17 (14:06 session); the live Telnyx T.38 test stays owner-gated (deploy lane)
3. **P15 SMS lane**: mechanism shipped (`operator.smsMessageStore` JSONL →
   `/api/sms` → operator tab; no private-flake coupling); the decision MEMO
   (Telnyx-API-only vs mod_sms chatplan, why) is not written yet.
   → done — `docs/decisions/2026-09-17_sms-lane-telnyx-api-only.md`
4. **P23 hygiene**: helpers landed (P23.3); AGENTS headroom migration (P23.1),
   BuildFlow ergonomics probes (P23.2), docs archive verdict-sweep (P23.4),
   browser E2E re-run (P23.5 — my new browser legs make this mandatory anyway)
   not started.
   → done — P23.1/P23.2/P23.4 closed by the 07:21 docs-health round; P23.5 closed by the 14:06 browser E2E green run
5. **Browser E2E** (`tests/browser-e2e.py`, `tests/browser.nix`): transfer/
   notification/title-flash/ICE legs written but the suite has never been run —
   the P8/P10/P17 browser paths are therefore UNVERIFIED end-to-end.
   → done — first full run green 2026-09-17 (14:06 a.5); re-proven on the final webphone lock (2026-09-18)

## c) NOT STARTED

- **P7 fspbx trial closure** (g1–g3 verdict memo, destroy-or-persist) — and
  P22 (diff-drafter spike) depends on its verdict.
  → done — trial closed with a verdict 2026-09-16 (retire VM, stay NixOS-first); P22 verdict memo landed; execution awaits the owner sign-off (TODO_LIST blocked row)
- **P20** MMS posture decision doc.
  → done — `docs/decisions/2026-09-17_mms-posture-http-api-only.md`
- **P15.1 decision memo** (see b.3).
  → done — `docs/decisions/2026-09-17_sms-lane-telnyx-api-only.md`
- **Docs harvest**: TODO_LIST row deletions, FEATURES rows (operator window,
  fax, phoneApi, contacts/history/ICE/transfer), CHANGELOG entries, ops-runbook
  operator-window section, README mention, AGENTS.md new gotchas (CDR
  template, sound_prefix, BindReadOnlyPaths trick).
  → done — the 19:40 session harvested everything (its a.8)
- **Full gate**: `nix flake check` (BuildFlow full mode) — nothing above the
  per-suite level has run.
  → done — all suites green 2026-09-17 evening (19:40 a.7) and on the final webphone lock (2026-09-18); the canonical buildflow full-mode run → open — TODO_LIST hygiene row
- **Private-flake absorb**: `nix flake update telephony` + store-path check in
  pbx-artmann.
  → done — 19:40 a.9 (fs-cert + webphone-root store paths verified moved); deploy itself stays owner-run

## d) TOTALLY FUCKED UP (self-review, no excuses)

1. **The conference pin assertion loop.** I guessed at unverified output
   formats (`list count` → `'^1$'` → `'@'`) and paid a 5-minute VM run per
   guess — three times — when the repo's own vm-testing lesson says: dump the
   actual command output FIRST. The correct move was a single debug run with
   `fs_cli 'conference board list'` output printed at failure. This is the
   session's biggest waste.
2. **Edit-tool freshness fights.** Running `sed -i` mid-session bumped mtimes
   and one edit reported success but was NOT in the file (caught by a later
   grep, per the "independently verify tool output" lesson — but the root
   cause was my own tool hygiene). Several lost round trips.
3. **Pipeline exit masking, again.** Reported `DIALPLAN-EXIT:0` from a grep's
   exit code, not nix-build's — exactly the AGENTS.md pipefail trap. Caught it
   and re-verified with honest exits, but I should not have re-committed the
   sin the memory file documents.
4. **Sequencing.** The brand-new operator suite (newest, most likely to fail
   code) has not run once, while I polished already-green suites. Run order
   should have been: eval → operator → conference → browser E2E → rest.
5. **Executor visibility.** I let long VM suites run to completion between
   user-visible progress notes instead of streaming per-suite verdicts.

## e) WHAT WE SHOULD IMPROVE (process, durable)

1. VM-test debugging protocol: on marker/assert failure, FIRST dump the raw
   command output into the failure block (`machine.execute` + print), THEN
   re-run. One debug run replaces N guess runs.
2. Never assert on command output formats not read from source or observed in
   the same run (this bit twice: `list count`, `board list`).
3. Keep one edit path per file per session (no interleaved sed -i + edit);
   re-View after any external mutation.
4. Run new/never-executed suites before re-verifying green ones.
5. Parallelize independent VM checks (nix builds are independent; the host has
   headroom) instead of serial background shells.
6. Write FEATURES/CHANGELOG rows in the same commit as the feature, not as a
   deferred phase.
7. Consider a `machine.nested("dump: conference board list")` helper in
   common.nix so every suite failure self-documents.

## f) NEXT 50 (ordered; 1–15 are the critical path to "everything works")

1. Diagnose conference right-pin leg: ONE debug run dumping `conference board
   list` + joinRight.log; then fix the assertion (suspect: digits racing the
   prompt, or admission fine and the list format differs — dump decides).
   → done — root causes were module-level (sounds prefix + `#` binding), fixed 2026-09-17; suite green
2. Run `telephony-operator` suite; fix what it finds (it has never executed).
   → done — green 2026-09-17 (19:40 a.1) after four module-level root-cause fixes
3. Run the browser E2E (`legacyPackages.telephony-browser`); expect iteration
   on the transfer leg (REFER timing, title-flash selector, ICE panel wait).
   → done — green 2026-09-17 (14:06 a.5) and again on the final webphone lock
4. Fix whatever 1–3 surface until all three are green.
   → done — all three green 2026-09-17
5. Write the P15 SMS decision memo (`docs/decisions/`), citing the webhook
   store + `operator.smsMessageStore` hook; close the TODO row as decided.
   → done — `docs/decisions/2026-09-17_sms-lane-telnyx-api-only.md`
6. Write the P16 fax VM test (spandsp loaded; 6000 answers with rxfax; clean
   hangup without fax tones; TIFF dir exists) + run it.
   → done — `tests/fax.nix` green (14:06 a.4)
7. Write the P20 MMS posture decision doc; close the row Won't-implement-now.
   → done — `docs/decisions/2026-09-17_mms-posture-http-api-only.md`
8. Fax live-test runbook note (Telnyx T.38) marked owner-gated in deploy docs.
   → done — ops-runbook inbound-fax section (19:40 a.8); the live test rides the deploy lane
9. P7 fspbx closure (needs the trial VM pointer — see question 2): snapshot,
   hostfwd, softphone/browser call, CDR-in-GUI, fax/SMS click-through, verdict
   memo, destroy-or-persist.
   → done — verdict delivered 2026-09-16; VM disposal awaits owner sign-off (TODO_LIST blocked row)
10. P22 Nix diff-drafter concept spike + build-or-drop verdict memo (fed by 9).
   → done — don't-build-now (`docs/decisions/2026-09-17_nix-diff-drafter-verdict.md`)
11. P23.1 AGENTS.md headroom migration → `docs/session-craft.md`.
   → done — closed per the round-2 plan log (AGENTS halved to docs/lessons/)
12. P23.2 BuildFlow ergonomics probes (`--failed-only`, `watch`, env var
    rediscovery) + record findings.
   → done — probed per the round-2 plan log (BUILDFLOW_MAX_TIME not honored, flag-only)
13. P23.4 docs archive verdict-sweep → `git mv` annotated reports to
    `docs/status/archived/` / `docs/planning/archived/`.
   → done — 07:21 round archived 23 snapshots
14. Full gate: `buildflow --build-mode full --max-time 60m` (or explicit `nix
    flake check`); fix fallout; purge stale BuildFlow result-cache rows only if
    findings replay.
   → done — explicit `nix flake check` sweep green 2026-09-17 evening + 2026-09-18 final lock; the canonical buildflow full-mode run → open — TODO_LIST hygiene row
15. Harvest docs: TODO_LIST deletions (P8/P10/P11/P12/P13/P14/P15/P16/P17/P20/
    P21/P23 rows), FEATURES rows (operator window incl. all four API surfaces,
    fax, CDR default-template fix, conference sound_prefix fix), CHANGELOG
    entry, ops-runbook "operator window" section, README feature line,
    AGENTS.md gotchas (CDR template shape, conference sound_prefix,
    BindReadOnlyPaths for cross-DynamicUser reads, REFER executes server-side).
   → done — 19:40 a.8
16. `nix fmt` + statix/deadnix/docs-drift re-check after doc harvest.
   → done — gates green through the 19:40 + 09-18 sweeps
17. pbx-artmann: `nix flake update telephony`; build toplevel; CONFIRM the
    fs-cert/webphone/operator store paths MOVED before any deploy handoff.
   → done — 19:40 a.9
18. Host-level polish: demo VM banner + forwarded ports mention `/operator/`.
   → done — banner now lists the operator window with demo creds (2026-09-18 docs-health round)
19. Consider `phone-api` MWI push: refresh badge on SIP MESSAGE indicator or
    periodic poll (today: login, call-end, manual refresh).
   → routed — the UI moved to the webphone repo (extracted 2026-09-17/18); idea lives there now
20. Operator page: paginate CDR beyond 500 (server limit is hard-clamped).
   → open — TODO_LIST Medium row (operator tail)
21. Operator health: add CDR-file freshness (mtime) + voicemail DB size cards.
   → open — ROADMAP theme 2 (operator-window depth)
22. `vm_delete` failure surfacing: map `-ERR` variants to distinct API codes.
   → open — ROADMAP theme 2 (operator-window depth)
23. Add rate limiting/lockout to phone-api auth (5 fails → 403 window) —
    digest-style brute-force resistance without fail2ban coupling.
   → open — TODO_LIST Medium row (operator tail: auth lockout)
24. History endpoint: merge SMS store rows into the per-extension view when
    the store's from/to matches (plan P15.4 remainder).
   → deferred — per the SMS decision doc (merged timeline waits until someone actually texts the number; ROADMAP theme 2)
25. Simulator: model `_ivr_` menu entries from ivr.conf.xml (menu follow-through
    via `--ivr-input` currently needs the entry map passed manually).
   → open — ROADMAP theme 2 (simulator depth)
26. Simulator: expose per-leg `record_session`/recording link in outcomes.
   → open — ROADMAP theme 2 (simulator depth)
27. Operator UI: CSV export button for the filtered CDR view.
   → open — TODO_LIST Medium row (operator tail)
28. Operator UI: wsproxy live-refresh? No — keep polling; but make the interval
    configurable via query param.
   → open — ROADMAP theme 2 (operator-window depth)
29. Audio streaming: Range request support (seek long voicemails).
   → open — TODO_LIST Medium row (operator tail)
30. Webphone: MWI badge should count per-folder (INBOX only today by SQL).
   → routed — webphone repo (UI extracted 2026-09-17/18)
31. Webphone: played messages marked read via `vm_read` API endpoint (read/unread
    flip without the phone).
   → open — TODO_LIST Medium row (operator tail: `vm_read` flip; UI half lives in the webphone repo)
32. Webphone: i18n for operator-ish hint strings already dual; audit remaining
    English-only strings in the event log (deliberate — keep).
   → **Won't implement — the event log stays English by design (operator-facing diagnostics).**
33. `tests/operator.nix`: add a 403-vs-401 distinction once (23) lands.
   → open — rides TODO_LIST Medium row (operator tail: lockout)
34. `tests/webphone.nix`: assert config.js carries contacts JSON (currently only
    phoneApi flag asserted).
   → open — small test-depth assert (grep-verified still absent 2026-09-18)
35. Docs: `docs/DOMAIN_LANGUAGE.md` — add operator window / phone-api / read-model
    vocabulary.
   → done — operator window / phone API / stream token rows added 2026-09-18 (docs-health round)
36. ops-runbook: add "operator API is down" triage (unit, BindReadOnlyPaths,
    credentials oneshot).
   → done — operator window & phone API section shipped (19:40 a.8)
37. Edge case: operator API when FreeSWITCH restarts mid-request (fs_cli
    failure → 502 already; verify health marks degraded not crashed).
   → open — ROADMAP theme 2 (resilience edge)
38. Edge case: CDR file rotation (Master.csv only grows; check mod_cdr_csv
    rotate-on-hup=false means unbounded — size the file in health view).
   → open — ROADMAP theme 2 (operator-window depth)
39. Backup coverage: restic paths already include /var/lib/private/freeswitch —
    confirm fax TIFFs (under recordings) and operator creds dir are covered.
   → open — TODO_LIST Low row (backup suite)
40. Security review pass on the new surface: nginx auth realm consistency,
    token TTL (1h) vs mailbox enumeration, `uuid` validation, CORS (none set —
    same-origin only, CSP enforces).
   → open — TODO_LIST Medium row (operator security hardening)
41. CI: the browser E2E stays manual-dispatch (P25 owner-gated) — but ensure
    `nix flake check` doesn't pull it (it's in legacyPackages; verified by
    design; re-confirm after flake.nix edit).
   → done — still true post-extraction (legacyPackages, outside `checks`)
42. flake-meta-checker: confirm the operator package passes (mainProgram set —
    done; watch for the data-package finding pattern).
   → done — mainProgram set; the data-package policy question → open — TODO_LIST blocked row (mainProgram)
43. statix non-fixes: verify the dotted-attrs hints don't flag the new
    assertions block (run statix locally — done once, re-run post-harvest).
   → done — statix green through every later gate sweep
44. Consider `services.telephony.operator.port` option (8071 hardcoded in
    shared.nix today) if a collision ever matters.
   → **Won't implement — YAGNI; no collision ever materialized. Revisit on demand.**
45. Consider exposing `operatorTlsCert` for ACME mode via an acme group read
    instead of "unavailable" (tiny; decide later).
   → **Won't implement — YAGNI until an ACME deployment actually asks.**
46. Webphone package version + CHANGELOG link for 0.2.0.
   → overtaken — the UI moved to the webphone repo (extracted 2026-09-17/18); versioning lives there
47. Triple-check `vmclient.py` join pin change didn't regress the plain
    (pinless) join path — conference suite green covers it; keep it green.
   → done — conference suite green incl. plain + pin legs (14:06)
48. Time-permitting: RFC 5589 attended transfer E2E (three browsers) — heavy;
    defer behind owner input; blind is covered.
   → deferred — attended covered by the single-browser leg; three-browser E2E → open — ROADMAP theme 3
49. After first real call (owner): wire the private flake's webhook JSONL to
    `operator.smsMessageStore` (one-line host config).
   → open — deploy lane (one-line host config in the private flake)
50. Update pbx-artmann AGENTS.md gotcha: operator window exists upstream; the
    private flake should enable it at next rebuild (with ITS secrets layout).
   → open — out-of-repo (private flake)

## g) Questions (cannot answer myself)

1. **Concurrent session**: while I worked, another session added `gwAuthAcl`
   (gateway auth ACL: option + generator param + assertion, commits
   "genericize the public template" era). I left it untouched and my work
   doesn't collide. Is that your parallel work to keep (I'll include its
   verification in the full gate), or should it be reverted/finished by me?
   → done — kept; full gates stayed green through every later sweep
2. **fspbx trial (P7)**: where does the trial live (disk image path, launch
   command, or the 18:00 report's machine)? I can close it out end-to-end only
   with that pointer; without it I'll write the verdict memo as blocked-on-artifact.
   → done — trial closed with verdict 2026-09-16 (see `docs/research/2026-09-16_fspbx-trial.md`); execution owner-blocked
3. **Release posture**: P18 was gated on the first real call, but this session
   adds a package + options + a CDR format fix. Cut `v0.2.x`/`v0.3.0` after the
   full gate goes green, or hold tags until the deployment era (first real
   call) per the original plan?
   → open — TODO_LIST blocked row (v0.3.0)

---

_Point-in-time snapshot; executed work lands in TODO_LIST/FEATURES/CHANGELOG at
harvest time (items 15–17 above). Sources of truth for this report: the git
history of this session (daemon-committed), /tmp/_check-_.log suite logs, and
the research files under ~/tmp-research/ (upstream sources cited inline)._
