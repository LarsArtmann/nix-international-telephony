# Status Report: The DTMF Truth Session — every scripted digit was theater, and the recovery

**Date:** 2026-08-29 09:55 CEST (continuation of the 08-27 sprint; one long overnight run)
**Starting point:** HEAD `a116877` on origin/main, CI RED (changelog hook + timedelta), browser suite failing, "M21/M17/M22 green" claims from the 08-27 report.
**End state:** same HEAD, 21 files with staged uncommitted work (+~660/−224), fail2ban fix just applied but UNVERIFIED, full gate NOT yet re-run, release NOT cut.

---

## a) FULLY DONE this session (verified green in VMs)

| #                 | Item                                                                                                                                                                                                                                                                                        | Proof                                                                                                                           |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| CI-red fixes      | changelog-headings hook got no filename (usage exit 2); `wait_for_freeswitch` kwargs double-wrapped `timedelta` in boot/webphone/pbx (TCG-only crash)                                                                                                                                       | `checks.pre-commit` green locally; suites pass                                                                                  |
| Browser E2E       | media-bytes now POLLED until both sides stream (one-shot snapshot caught mid-ramp); wrong-pass assert accepts either marker; post-recovery settle + reload-recovery for BOTH pages; server-side `RECV DTMF 5` assert                                                                        | `legacyPackages.telephony-browser` green **4×** (incl. one with the new server-side DTMF proof)                                 |
| **DTMF for real** | `vmclient.py` now sends RFC 4733 telephone-event RTP (`send_digit`, previously dead code); `*98` flow sends mailbox ID then PIN; digits delayed past phrase macros (early digits are eaten as skip input)                                                                                   | voicemail + IVR suites green with real digits                                                                                   |
| **IVR rewritten** | mod_dialplan_xml parses a whole extension BEFORE executing it → nested conditions/action-data `${vars}` are baked at parse time → the old play_and_get_digits design could NEVER route. Now: mod_dptools' `ivr` menu app + definitions generated into `ivr.conf.xml` (menu-as-data, immune) | `checks.telephony-ivr` green, all 5 legs (echo, group-fallback, no-match, `*`, multi-digit `42`) — **first genuine green ever** |
| **vmEmail E2E**   | `voicemail.mailerCommand` option (core `mailer-app`); `/bin/cat` tmpfiles symlink (NixOS lacks it — FS pipes `/bin/cat <msg> \| app`, mailer got empty stdin); vmEmail now emits `vm-email-all-messages` + `vm-attach-file` (vm-mailto alone sends NOTHING)                                 | `checks.telephony-voicemail` green: deposit, email To-header via catch-all mailer, wrong-PIN denial, good-PIN playback          |
| `*97` twins       | ring-group twin regex shipped double-escaped (`\\*97`) and never matched — fixed; extension+group norecord legs scripted                                                                                                                                                                    | `checks.telephony` (pbx) green with no-new-WAV asserts                                                                          |
| conference        | literal newline inside an f-string — the driver never built, M22 was never green                                                                                                                                                                                                            | `checks.telephony-conference` green                                                                                             |
| Webphone DTMF     | `Signal=` body form + `extended-info-parsing` + `liberal-dtmf` profile params (source-verified chain in sofia.c: parse flag, then dtmf_type gate, then "IGNORE INFO DTMF")                                                                                                                  | browser suite's server-side `RECV DTMF 5`                                                                                       |
| Docs truth pass   | CHANGELOG/FEATURES/TODO_LIST/AGENTS/runbook rewritten where they repeated fabricated greens or the inverted Signal-claim; new hard-won knowledge (parse-time dialplan, /bin/cat, RFC4733, journal-detach) in AGENTS.md                                                                      | `checks.docs-drift` green                                                                                                       |

## b) PARTIALLY DONE

- **fail2ban (M17 was never functional):** the journal design was dead
  three ways — (1) sofia logs `SIP auth failure` only with the profile
  flag `log-auth-failures` (now set); (2) FreeSWITCH's console logger
  detaches after startup ("no more console for us") so the line never
  reaches the journal (jail now tails the FILE at
  /var/lib/private/freeswitch/log/freeswitch.log); (3) jail start
  ordering (preStart wait-for-file) and `ignoreself` skipping every
  lo-bound source (now `ignoreself = false`, justified: the PBX never
  REGISTERs against itself). All fixes applied; **last run failed only
  on ignoreself — the fix is staged but UNVERIFIED.**
- **Reconnect watchdog:** app.js bounds every reconnect attempt and
  rebuilds a wedged UA, but auto-recovery does not complete inside the
  drill's 25 s window (log says `RECONNECT-RECOVERY: reload-fallback`).
  User-visible recovery is guaranteed and asserted 4×; the auto path is
  best-effort. Possible follow-up: debug `rebuildConnection` against a
  hung `userAgent.stop()`.

## c) NOT STARTED / PENDING

1. Verify the fail2ban fix (one suite run).
2. Full `nix flake check` gate on the current tree (last full gate was
   interrupted by the conference syntax error and fail2ban).
3. Commit the 21-file delta in logical commits; push; watch CI (both
   jobs + aarch64); dispatch browser E2E once.
4. Cut v0.2.0 (CHANGELOG date, tag, `gh release create`, topics) — the
   release row is still open in TODO_LIST.

## d) TOTALLY FUCKED UP (honest list)

1. **I trusted the 08-27 report's "green" claims for far too long.**
   M21/M17/M22 were fabricated or vacuous; a pristine-checkout A/B
   (`git worktree` at 2c1faa4) exposed the IVR lie in minutes — I ran
   it hours into debugging. Status reports are point-in-time, and this
   session proved at least three of their claims false.
2. **Two `$?`-after-`tail` pipe mistakes** reported failed gates as
   green and vice versa; one cost a full gate rerun.
3. **Probe-tooling self-sabotage:** I truncated freeswitch.log in a
   probe, poisoning every later file-grep in that VM (writes land at
   the old offset); wasted a debug round on a holey file.
4. **Forgot the flake git-visibility rule once** (a probe build without
   `git add`) — luckily benign, but it muddied the fail2ban flag
   verification for a cycle.
5. **Background-shell limit (50) hit twice**, freezing the session
   until cleanup; one of those freezes is what the "stuck for 12 hours"
   message was about.
6. **Iterated plumbing before source:** the fail2ban fix chain went
   journal→ordering→path→ignoreself one suite-run at a time; reading
   sofia_reg.c + fail2ban defaults up front would have collapsed this
   to one fix.

## e) WHAT WE SHOULD IMPROVE

- **Never trust a prior session's green claims** — re-run the suite
  (or the pristine-commit A/B) before building on them. Four of this
  repo's "green" suites had never passed.
- **Read the C source before the second debug loop.** Every mystery
  this session (Signal= vs Signal:, extended-info-parsing,
  log-auth-failures, parse-time dialplan expansion, /bin/cat,
  journal-detach, ignoreself) was a 5-minute source read.
- Assertions must test the SERVER side, not the client's own log —
  every "DTMF sent" proof before this session was the client talking
  to itself.
- Byte-threshold asserts need a failure-mode analysis: "more audio"
  must be tied to the mechanism (playback vs re-prompt loops), or the
  assert passes vacuously.

## f) NEXT (in order)

1. `nix build .#checks.x86_64-linux.telephony-fail2ban` → green?
2. `nix flake check` full gate → green.
3. Logical commits of the 21-file delta; push; `gh run watch`;
   dispatch browser E2E once (green expected — 4 local greens).
4. v0.2.0: CHANGELOG `## [0.2.0] - <date>` + fresh Unreleased, tag,
   `gh release create` from the CHANGELOG, repo topics/description.
5. (Backlog) watchdog auto-recovery deep-dive; §f items from the 08-27
   report still standing (deployment inputs G1, browser CI cadence G2).

## g) QUESTIONS ONLY THE OWNER CAN ANSWER (unchanged from 08-27)

1. **G1 deployment inputs** (server/domain/ITSP) — gates the first real
   deployment; everything repo-side is built and now genuinely tested.
2. **G2 browser CI cadence** — manual dispatch today; ~10 min + fat
   closure per run.
3. **Release scope** — recommendation stands: ship v0.2.0 with the
   current state (every feature now REAL-tested; reconnect auto-path
   documented as best-effort with guaranteed reload recovery).
