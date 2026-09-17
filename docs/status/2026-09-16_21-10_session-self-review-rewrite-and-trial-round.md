# Status #5: session self-review — license round, Pareto plan, history rewrite, fspbx closure

Point-in-time: **2026-09-16 21:10 CEST**. Scope: this session's full arc
(license question → UI/UX needs → SMS/fax scorecard → Pareto plan P0–P25 →
owner G2 answers → P19.2 rewrite → P7 trial closure). Format: `.md` + a–g
per standing owner override. State right now: trial VM running (pid
718005, snapshot `pre-sip-wiring` intact), git clean at `80885b1`, CI
green on both rewrite-era commits, final closure commit's run in flight.

## a) FULLY DONE

1. **License verdict** (verified from source): fspbx = Apache-2.0 (file
   text); bundled FusionPBX GUI = MPL 1.1 per file headers; readme
   pricing = support membership, not code license. Documented in trial
   doc; the "GitHub shows no license" scare explained.
2. **UI/UX needs analysis + SMS/MMS/fax/history scorecard** (chat
   round): phone surface ~70% daily-driver (transfer/notifications/
   voicemail/contacts missing), operator surface ~15% (no window);
   SMS exists via Telnyx webhooks, fax has a verified T.38 path
   (Telnyx), MMS is API-only.
3. **Pareto plan P0–P25** (`docs/planning/2026-09-16_19-05_first-call-
   to-daily-driver-pareto-plan.md`): tiers 1%/4%/20%/rest, 26 medium +
   124 micro tasks, mermaid graph; TODO_LIST harvested (14 rows);
   committed + pushed.
4. **P6 owner decision pack executed**: all five G2 answers recorded
   (record-all-calls consent, close-fspbx-properly, deploy-not-now,
   rewrite-now, DIDs-deferred) and propagated to TODO/plan.
5. **P19.2 history rewrite** complete and verified end to end:
   23 spellings replaced (blobs + 1 message), scrub gate green in
   history mode, lease force-push, origin re-verified 0 pickaxe hits,
   tags unchanged, CHANGELOG Security entry, CI green after.
6. **P7 fspbx trial closure** complete with evidence (9 cycles):
   extensions via their own models, E2E REGISTER/digest/INVITE/200/BYE
   via this repo's vmclient.py, CDR rows via their v1 bearer API, ESL
   profile-sync verified, fax/SMS presence confirmed, verdict memo +
   recommendation (retire VM, stay NixOS-first, keep as feature
   reference).

## b) PARTIALLY DONE

1. **CI on the final closure commit** — in flight as of writing → done — CI run 35138458020 green (verified 2026-09-17)
   (previous two rewrite-era runs green).
2. **P7.5 literally**: 9196 echo had no dialplan entry (480) —
   extension-to-extension answer used as substitute; CDR was verified
   via API, never confirmed to RENDER in the Vue GUI (owner clicks).
3. **P7.6 "click-through"**: fax/SMS verified present (tree + routes),
   but no page was ever actually loaded — headless SPA limits; honestly
   labeled untested.
4. **GUI cookie-session 302**: root cause never found (PAT workaround
   adopted). Open loose end, deliberately time-boxed away.
5. Trial-doc housekeeping: ecosystem survey still lacks the license → done — license cross-ref added to the survey's verification table (2026-09-16 docs-health round)
   cross-reference (one-home rule satisfied, cross-ref pending).

## c) NOT STARTED

Everything owner-gated or queued in the plan: P1–P5 deploy lane
(deferred by owner), P8 webphone transfer, P9 trunk hardening, P10–P17
UX/operator lanes, P18 release 0.3.0, P19.1 key rotation, P20 MMS
posture doc, P21 dry-run, P22 diff-drafter, P23 hygiene pack, P24 DIDs,
P25 browser-CI cadence.

## d) TOTALLY FUCKED UP

1. **Assumed the FreeSWITCH config path twice** (source-install default,
   then a find-race to the `.orig` backup) — two cycles burned on a path
   the systemd unit printed on cycle one. Read ExecStart FIRST.
2. **The License section header eaten** by my own doc edit
   (insert-without-anchor) — caught + restored within one step.
3. **urllib chased the portless 302 a THIRD time** before the
   NoRedirect handler came out — the trap now has a name in AGENTS.md;
   it should also have a helper in my toolbox from step one.
4. **"Voicemail fallback" written as fact in the trial doc** — it is an
   inference (33s durations suggest it) but WHO answered 1002 was never
   verified. An overclaim, small but real.
5. **P0.3 (CI glance) skipped until this report** — verified green only
   now, retroactively. A 30-second check deferred past its own deadline.

## e) WHAT WE SHOULD IMPROVE

1. **Live credential hygiene in trials**: the Sanctum PAT + extension
   passwords sit in plaintext console logs under /var/tmp and the PAT is
   still valid — revoke/destroy on verdict (trial scope, but the habit
   should be automatic).
2. **Time-box NAT/sandbox gymnastics to 2 attempts** (this round: 5) —
   the slirp SDP wall is now a documented dead end, not a challenge.
3. **Pickaxe lesson for the scrub gate**: removals count as "touched" —
   the gate's FAIL output could label add-vs-remove to save the next
   person the ghost hunt (script improvement, P23 candidate).
4. **Daemon risk during history surgery was accepted silently** — next
   time, state it in the report BEFORE operating (mitigation was
   origin-as-backup, which worked, but say so up front).
5. **AGENTS.md encoding still pending** for this round's lessons
   (slirp wall, pickaxe removals, ExecStart-first, CLI-bootstrap-PAT
   pattern) — P23.1 covers it; do not let it slip.

## f) Next (up to 50; plan IDs refer to §2 of the 19:05 plan)

1. Owner verdict on the P7 recommendation (retire VM / NixOS-first / → open — TODO_LIST blocked row (verdict sign-off); sub-items 2-3 fold into it
   fspbx-as-reference) — blocks P7.8 disposal + P22 framing
2. If kill: `pkill -9 -f disk.qcow2` + `trash /var/tmp/fspbx-trial` +
   revoke PAT first (it is live in console logs)
3. If keep: relocate `/var/tmp/fspbx-trial` to persistent storage +
   post-wiring snapshot
4. P1 deploy lane when owner ready (runbook snippet → rescue-boot →
   reinstall → verify → first calls)
5. P2–P5 verification/inbound-SMS/first-calls/hygiene after P1
6. P8 webphone transfer (REFER + attended) — top UX gap
7. P10 incoming-call notifications + reconnect polish
8. P11 voicemail in-browser + MWI
9. P12 contacts + CDR-backed history
10. P13 operator CDR viewer
11. P14 operator live health view
12. P15 SMS lane decision (Telnyx-API-only vs mod_sms)
13. P16 fax enablement (mod_spandsp + Telnyx T.38, verified-capable)
14. P17 ICE/turn diagnostics panel
15. P9 trunk hardening after first calls (Telnyx CIDRs + fail2ban)
16. P18 release 0.3.0 after first real call
17. P19.1 Telnyx key rotation (owner)
18. P20 MMS posture decision doc
19. P21 dialplan dry-run simulator
20. P22 Nix diff-drafter spike (after fspbx verdict formalized)
21. P23.1 AGENTS.md: encode this round's lessons (see e.5) → done — AGENTS.md pickaxe line; remaining trial-craft lessons documented in their homes
22. P23.2 BuildFlow ergonomics probes
23. P23.3 test-depth pack (assert_fs_hour, dedupe, conference pin)
24. P23.4 docs archive continuation → done — this docs-health round archived the 08-21/22 set, 09-02/03, the 13-52 HTML and the superseded 09-15 plan
25. P23.5 browser E2E re-run
26. P24 Warsaw/DE DIDs when first calls green (owner, KYC windows)
27. P25 browser-CI cadence (owner call)
28. Verify CDR rendering in the trial GUI (owner clicks, or one more
    headless pass) — closes b.2
29. Verify who answers 1002 (ESL `show channels`/voicemail check) —
    closes the d.4 overclaim in the trial doc
30. GitHub residual-exposure handling: ask support to GC old commits /
    audit stale PR refs (Dependabot) — see g.3
31. Ecosystem-survey cross-ref to the trial-doc License section (b.5) → done — cross-ref added 2026-09-16
32. scrub-check.sh improvement: label add vs remove in HISTORY HITs (e.3)
33. Daemon push-loop observability (why it died 18:00→19:05) — a note → open — TODO_LIST row (daemon push observability)
    in AGENTS.md or a health check
34. Consider qemu-img snapshot post-wiring if VM survives this round

## g) Questions I cannot answer myself

1. **Verdict sign-off**: accept the recommendation (retire the VM, stay → open — TODO_LIST blocked row (verdict sign-off)
   NixOS-first, keep fspbx as feature reference)? The VM + snapshot are
   preserved until you say.
2. **Clone inventory**: do any other machines (evo-x2, the private → open — TODO_LIST blocked row (residual-exposure row covers the clone inventory)
   pbx-artmann box, laptops) hold clones of this repo from BEFORE the
   rewrite? They still contain the old history — I cannot see them.
3. **Residual-exposure appetite**: is chasing GitHub's cached old → open — TODO_LIST blocked row (residual exposure)
   commits (support request, stale PR refs) worth it, or is the
   documented CHANGELOG warning + natural GC sufficient? Your risk call.

— Reported. Waiting for instructions.
