# Status — session 2 of the verdict-truth train (2026-11-08, ends ~20:56 CET)

## a) FULLY DONE

1. **The CI red is healed and the train has an AIRTIGHT GREEN verdict.** CI run
   `42501322421` (over the forward-pin head `ad55ec2`) is **SUCCESS** on all
   main jobs. The red decomposed into THREE layers, each fixed at its root:
   - the two eval conflicts (secrets.nix `mkForce` + fax-feed file-form
     secret) — landed in the previous session's tail, carried by daemon
     commit `080e5cb`;
   - the **helpers-split splice bug**: someone (sibling sweep era) split
     `common.nix`'s `bootWait` into `bootWait` + `helpers`, moving
     `wait_webphone`/`assert_file_log` out from under four suites' splices —
     their driver builds fail the type check with "wait_webphone used when
     not defined" (invisible to `--no-build` eval gates; this killed CI
     `42496030807`'s fax-feed/messaging). Fixed by splicing
     `${common.helpers}` into fax-feed, messaging, textagent, tls-turn
     (`23849ea`); all four drivers verified building.
   - the **daemon's lock sweep onto a broken webphone rev**: `6029134`
     moved webphone `e762f5af -> 58f4b506`, nixpkgs `f9a75f41 -> f4a03c00`,
     pbx-lens `9c98f9c -> ca1dd821` in one heuristic commit. Gate 2 (binary
     build) passed but gate 4 failed at runtime: upstream's CLI mint
     (`cmd/webphone/main.go:93`) writes the ENGINE-backed enroll store while
     the server reads the dispatch-backed `EnrollSvc()`
     (`internal/app/app.go:288`) — CLI-minted enrollment tokens are
     invisible to the serve path at that rev (upstream mid-wave on the
     EnrollGate split; the delta itself says "the engine store is the test
     seam"). **Forward-pinned all three inputs back to the proven set**
     (`ad55ec2`, `relock:` marker, lock_guard PASS; the moved-lock tree did
     eval green, and the telephony-webphone suite went straight back green
     on the pinned rev — the runtime proof of the diagnosis).
2. **M19/MWI landed end to end.** driverInteractive probes (4 iterations)
   settled the truth: mod_voicemail exposes **NO fsapi count command**
   (`msgcount` is not a command; the `voicemail` api is
   rss/load/unload/reload only) — the message-waiting truth surface is the
   **MESSAGE_WAITING ESL event** (`MWI-Messages-Waiting: yes`,
   `Update-Reason: NEW`, fired by `update_mwi`, consumed by mod_sofia for
   NOTIFY). tests/dialplan.nix now subscribes an in-VM ESL listener
   (`esl-mwi-listen.py`), deposits a real µ-law-noise message through a
   dedicated 6 s ring group 3001 (vmclient's 20 s SIP socket timeout cannot
   sit through group 2000's 25 s ring — first-run evidence), and asserts
   the yes/NEW event. Suite GREEN (`DIALPLAN_RC=0`; MWI grep 0.02 s).
3. **Voicemail storage dir joined `state.paths`**
   (`/var/lib/private/freeswitch/storage`) — the WAV payloads were
   uncovered while `voicemail_default.db` was already backed up.
4. **Runbook additions**: the `*98` mailbox recipe (storage paths, index
   DB, MWI observation) and the startupz drain-window measurement
   (driverInteractive probe: 300/300 samples 200 through a deliberate
   restart — the 503 drain window at test scale is faster than 10 Hz
   sampling; one attempt, honest verdict recorded beside the 502 section).
5. **Sweep re-damage restored**: the sibling's 17:19 prettier sweep
   (`6029134`) re-ran the known damage class on the archived snapshots
   (2026-10-28 list demotion/renumbering; 2026-10-07 16:24 corrected-cell
   drop). Both restored verbatim to the archived shape per the 428f2f4
   precedent with count-recovery appends (`bb8f49d`); markers_check and
   rendering_audit back to **0 findings across 108 files**.
6. **CHANGELOG verdict batches landed**: the eval-red heal bullet (three
   layers + wrong-attribution correction), the Added batch (MWI, storage
   dir, M20 media roundtrip, M18 run-7 green + #120 upstream-blocked, N8
   theme green, N12 alias, N11 canary/wallclock/wait_webphone), and the
   `c19bdea`/`c59305ba` backfills verified present.
7. **TODO_LIST truth sweep**: M20 row + passkey/voicemail remainder row
   closed with grep-verified evidence; CDR wall-of-text row compressed;
   Docs-batch and ruff rows trimmed to their landed-remainder halves; NEW
   bounded row for the go-cqrs-lite#120 relock-and-rerun (verified OPEN
   upstream via `gh issue view`).
8. **Tails executed**: reconciled stash dropped (subset-proven vs pushed
   `d66fc3b`, recoverable at `2895944`); doc-counts archived-pin verdict =
   REJECT (archived snapshots keep historical counts; doc_counts stays a
   live-tree gate); daemon-entangled commits re-authored hand-written
   twice (`eafb839` M19 lane, `ce4e217` sibling TODO polish).
9. **Sibling lanes respected**: their mkForce-audit status report
   (`58b101d`) and TODO polish passed through untouched; the 17:19 sweep
   damage was repaired, not reverted.

## b) PARTIALLY DONE

1. **The voicemail quota option's model correction — code landed, runtime
   proof still RED.** The original `voicemail.maxMessages` option
   (`d66fc3b`) rode a FICTIONAL parameter: the first suite build caught the
   vanilla template carrying no `max-messages` line (the sed-swap was a
   silent no-op, the grep-verify failed the builder — three runs burned on
   GC/eval-cache ghosts before the real error surfaced), the runtime probe
   then recorded a third message WITH the quota set, and the mod_voicemail.c
   source (source-verified via the web) has **zero matches** for
   max-messages — the real mechanism is the per-user `vm-disk-quota`
   directory param (BYTES; `voicemail_leave_main` compares the stored-bytes
   sum before recording; over-quota plays `voicemail_disk_quota_exceeded`
   and skips the recording). The option was replaced same-day, before any
   release: `voicemail.diskQuota` (bytes) renders the directory param on
   every extension (options.nix, freeswitch.nix userXml, pbx.nix call site,
   eval.nix quotaCheck arm, voicemail.nix suite arm, CHANGELOG rewritten).
   **The suite arm is still RED**: `over-quota deposit stored a message
   anyway: 2` — the vm-disk-quota param rendered but the refusal did not
   happen on the last run. Open hypotheses: quota margin too high (msg 1's
   recorded length may land under 100 KB), the param's parse position in
   the rendered directory XML, or mod_voicemail reading the quota only at
   profile (re)load. The local tree carries this red UNPUSHED (daemon
   shards `89eca55`/`ac8d35a` carry the model fix; origin has NOT received
   it — deliberately held back until the arm is green).
2. **CI verdicts for the newest heads**: `pin-head` green is the airtight
   verdict for the healed stack; the splice-fix-only head (`42500794001`)
   failed (it raced the broken intermediate era) and is superseded — its
   red is NOT a live problem but the run list looks red until the next
   green head lands with the quota fix.
3. **The 08:53 plan's annotation + archive** (N13's final clause): Step 2
   M-table rows still lack verdict arrows; archive-after-annotation not
   executed (held for the quota verdict so N7/N15's rows carry final
   truth).

## c) NOT STARTED

1. Plan annotation + archive (see b3).
2. README BuildFlow pointer + the hook-strip/go-git long-form +
   cross-arch eval-thrash narrative into `docs/lessons/operating.md`
   (the trimmed Docs-batch remainder).
3. buildflow step-name resolution tail (trimmed row remainder).
4. Upstream follow-through on go-cqrs-lite#120 (watch → relock → passkey
   enroll leg green) — the row is in TODO_LIST, the watch is passive.
5. The 50-item §f backlog below (16-50 carried forward unchanged).

## d) TOTALLY FUCKED UP (honest failures)

1. **Seven voicemail suite runs to reach the source-true mechanism — and
   the arm is STILL red.** The chain of mis-steps: (i) the original option
   was authored against a fictional param and nothing ever BUILT it
   (eval-only gates); (ii) when the builder finally failed, I chased GC'd
   drv / eval-cache ghosts for three runs because a "successful" standalone
   drv build misled me (it built a DIFFERENT driverConfiguration than the
   suite's — I never verified WHICH drv the suite actually needed); (iii) I
   asserted `VM-SERVER-HANGUP yes` in the deposit flow without reading
   vmclient's deposit() (the marker is check/menu-only) — one wasted run;
   (iv) after switching to the real mechanism, the quota margin (100 KB
   under one ~120 KB message) still doesn't refuse — the runtime behavior
   has now contradicted TWO of my models. The source citation was right;
   the runtime still disagrees, and I do not yet know why.
2. **Daemon entanglement all session**: three soft-reset + re-author
   dances, my eval fix/M19 lane/CHANGELOG/TODO batches each swept into
   heuristic commits within minutes. The protocol worked (content always
   verified intact, attribution recovered in CHANGELOG), but the trail is
   noisy and one `89eca55` shard carries a MIXED bag (model fix + docs).
3. **The MWI probe burned three VM runs on escaping** (JSON `\n` escaping
   through the write tool into heredocs: one f-string interpolation eaten
   by sed, one double-backslash, one real-newline). The disciplined shape
   (quoted placeholder + doubled backslashes verified by grep BEFORE the
   run) only emerged on iteration 4.
4. **I nearly pushed a red lane twice**: the first push carried the daemon's
   lock sweep toward CI (saved only by the lock-guard + ritual discipline),
   and the local-gate parity rule (full `nix flake check --no-build`) did
   NOT catch the splice bug because `--no-build` never runs driver pyflakes
   — the gate misses this entire failure class.

## e) WHAT WE SHOULD IMPROVE

1. **A cheap driver-build gate**: a `checks.driver-typecheck`-style attr
   (or a loop over `checks.*.driverInteractive` builds) that catches the
   "name used when not defined" class locally — the `--no-build` eval gate
   is structurally blind to it.
2. **Relock discipline held, but the sweep still landed on origin**: the
   daemon's go-git lane remains ungated for flake.lock (pma#341 class).
   The forward-pin + CHANGELOG attribution worked, but a lock-move guard
   INSIDE the daemon is still the only structural fix.
3. **Verify WHICH drv a suite needs before believing a standalone build**
   (the eval-cache/GC chase class): diff the failing drv path against the
   one you built — 20 seconds vs three wasted VM runs.
4. **Read the client helper's code before asserting its markers**
   (vmclient's deposit/check flows print different markers — the M19 probe
   got this right, the quota arm got it wrong).
5. **Source-check FreeSWITCH params BEFORE authoring options around
   them**: mod_voicemail's "max-messages" looks documented but does not
   exist in the source; a 2-minute sourcegraph/raw-github grep would have
   saved the whole quota saga.
6. **Quota margins need DB-read calibration**: derive the threshold from
   the VM's actual `sum(message_len)` (the suite can read the index DB
   like the read_epoch assert does) instead of assuming ~120 KB per
   message.

## f) Up to 50 things to do next

1. Debug the disk-quota refusal (count=2 stored despite vm-disk-quota) —
   dump the rendered directory entry inside the VM, check the param's
   parse position, and re-check `voicemail_leave_main`'s quota read path.
2. Calibrate the quota margin from the VM's actual `sum(message_len)`.
3. Push the model-fix head only after the quota arm is green; then a
   CHANGELOG line for the green run.
4. Airtight CI verdict over the model-fix head (the current green is over
   `ad55ec2`, which lacks the quota work).
5. Annotate the 08:53 plan's Step 2 rows (N1-N17 verdict arrows) and
   archive it per the marker convention.
6. Close the trimmed TODO rows' landed halves with the new commit ids.
7. Driver-typecheck gate (see e1) so the splice class can never land
   again.
8. README BuildFlow pointer.
9. The hook-strip + go-git long-form into `docs/lessons/operating.md`.
10. The cross-arch eval-thrash narrative into the lessons file.
11. buildflow step-name resolution tail.
12. Upstream issue to webphone: the CLI/serve enroll-store split at
    58f4b506 (source-proven; verify-before-filing first, then file with
    the two call sites as evidence).
13. Upstream follow-through on go-cqrs-lite#120 (watch → relock → passkey
    rerun).
14. Re-run the relock ritual for webphone when the EnrollGate wave lands
    upstream (gate 0 prove-before-lock on the candidate rev).
15. Same for nixpkgs f4a03c00 + pbx-lens ca1dd821 (the swept revs are
    parked in the daemon's history; they deserve a proper attributed
    relock + suite ladder when convenient).
16. ESL presence-coverage row (TODO_LIST Medium #1): add the ESL-wait to
    the textagent fixture.
17. CDR cancelled-while-ringing live-host track (compressed row).
18. Domain-language ritual vocabulary row (relock terms).
19. Lagging non-webphone inputs refresh (flake-parts_2, home-manager).
20. Sweep-executor hunt (the mystery `nix flake update` executions).
21. pma/go-commit hook gating (the structural daemon fix).
22. crush-config lessons-file round-11 entries (by commit).
23. verify-live.sh livez/startupz gates.
24. Operator `/version` consumption.
25. Post-deploy browser smoke.
26. Missed-call ring shape assert.
27. cdr-visibility row-shape assert.
28. Synthetic-DID convention doc.
29. verify-live.sh pbx.artmann.tech re-run after the next deploy (the
    decision packet's tail).
30. Branch protection + required checks (owner admin call, packet ready).
31. ALERT_WEBHOOK secret fire-drill (owner).
32. WhatsApp live round-trip (owner, WABA).
33. Lens UI vhost decision (owner).
34. fspbx trial sign-off (owner; PAT revoke).
35. Warsaw DID + DE DID (owner, KYC window).
36. Telnyx API key rotation (owner).
37. Scrub placeholder fill-or-delete (owner).
38. GitHub GC / stale-clone inventory after the history rewrite (owner).
39. Global hooksPath landmine fix (home-manager, owner).
40. Browser E2E CI promotion (owner call).
41. sops-nix example host (owner).
42. nixpkgs upstream lane from the mkForce audit (owner-gated draft).
43. `/metrics` consumer card (owner-gated).
44. `webphone.retentionDays` facade (owner-gated).
45. telephony-prod-boot re-proof wording once the model-fix head is green
    (the row's evidence updates to the new run id).
46. Refresh the webphone adoption deep-dive when the push seam or ASR
    facade lands (standing trigger).
47. ROADMAP raw-ideas carry-forward (staleness alarm, bulk-commit split,
    nixpkgs lock fencing, voicemail depth remainder).
48. Consider a `checks.driver-typecheck`-style meta-check naming ALL
    suites (closes e1 structurally).
49. Re-verify docs/providers before any purchase (standing rule; next
    due when a provider decision nears).
50. The stash-drop follow-up: `git stash drop` printout SHA `2895944`
    noted here as the recovery point until reflog GC (owner FYI).

## g) Owner questions (not answerable from inside the repo)

1. **The voicemail quota option**: keep `voicemail.diskQuota` (bytes, the
   real mechanism) and debug the runtime refusal — or drop the option
   entirely until mod_voicemail's enforcement is proven on 1.11.1? The
   source says the mechanism exists; the runtime currently disagrees, and
   I can debug it, but if you do not need per-mailbox quotas the honest
   move may be removal.
2. **The swept revs** (webphone 58f4b506 with the broken CLI enroll split,
   nixpkgs f4a03c00, pbx-lens ca1dd821): should I file the webphone issue
   upstream NOW (verify-before-filing passes — both call sites are
   source-verified) or wait until you have eyeballed the forward-pin
   rationale?
3. **The unpushed local red**: the model-fix tree sits unpushed with the
   quota arm red (six daemon shards). Push it now with the red suite
   (honest red on CI, verdict next session), or hold the lane until the
   arm is green locally as I have been doing?
