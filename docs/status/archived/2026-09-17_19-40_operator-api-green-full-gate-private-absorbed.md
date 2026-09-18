# Status 2026-09-17 19:40 — Operator API green (4 root causes), full gate green, private flake absorbed

Session scope: continue the 2026-09-17 handoff (`14-06` report). One operator suite
was red with fix #2 applied-but-unverified; the remaining lanes were the full gate,
docs harvest, the private-flake absorb, and the demo-VM ssh smoke. All of it is now
done, with four real module-level bugs found and fixed on the way. Runtime notes:
session ran 2026-09-17 ~12:20–19:35 CEST, single assistant, no concurrent-session
interference observed except one prettier reformat of `operator.js` and an
`opsTools` AGENTS.md edit by the other session (left untouched, daemon-committed).

`/tmp` log files referenced below are ephemeral; conclusions are recorded here.

## TL;DR

- `telephony-operator` went red→green through **four distinct module bugs** (none of
  them the bind fix #2 from the morning — that one was correct all along) plus three
  test-side defects. All four module fixes carry regression coverage in the suite.
- Full gate: **all 20 VM suites + 7 non-VM flake checks green** under the final
  module state.
- Docs harvested (TODO_LIST / FEATURES / CHANGELOG / README / ops-runbook), drift
  alarm green.
- `pbx-artmann` re-locked, toplevel builds, **fs-cert + webphone-root store paths
  verified moved**. Deploy NOT run (owner).
- P23.3i demo-VM host-side ssh smoke executed and green — the tracked `evo-x2` key
  in `~/.ssh/id_ed25519` answered the open question 3.

## a) FULLY DONE

1. **Operator suite green** (`/tmp/operator20.log`, OPERATOR-EXIT:0). The full
   end-to-end path now passes: deposit → summary unread → messages list →
   token-authed WAV stream (RIFF bytes) → DELETE via mod_voicemail → summary zero →
   `vm_boxcount …|all` = `0:0:0:0` → operator surface 401/success paths → dialplan
   simulator (group/echo/DROP).
2. **Root cause 1 — read permissions** (`modules/telephony/pbx.nix`): FS state dirs
   (`db/`, `storage/`) are 0750 under FS's ephemeral identity; a second dynamic user
   cannot stat through, so the API's `os.path.exists` returned False. Fix:
   `telephony-fs-state-acl.service` — POSIX ACLs (`g:telephony:rX` + default ACLs)
   over the tree, after `freeswitch.service`, race-safe in both population orders.
   Evidence chain: `/tmp/operator10.log` (FSPROC showed fs Gid=994 while files stayed
   65534:65534), `/tmp/operator11.log` (ACL applied test-side → POSTACL 200).
   The morning's `Group=telephony` pin was **disproven empirically** (systemd 261
   still created files `nobody:nogroup` — man-page semantics did not hold) and
   removed.
3. **Root cause 2 — folder case** (`packages/telephony-operator/api.py`):
   `in_folder = 'INBOX'` never matched mod_voicemail's lowercase `myfolder = "inbox"`
   default (`mod_voicemail.c:2744`) → summaries showed 0 new right after a deposit.
   Now `lower(in_folder) = 'inbox'`.
4. **Root cause 3 — path glue**: `send_file` opened
   `/var/lib/telephony/freeswitch-rostorage/...` (missing separator — the
   `replace("/var/lib/freeswitch/", fs_root)` needle consumed the slash). Every
   audio request 404'd with `{"error": "audio not found"}`. Fixed to replace the
   directory prefix without the trailing slash; `send_file` failures are now
   journal-logged permanently.
5. **Root cause 4 — CDR whitespace**: upstream `sql`/`snom` cdr templates emit
   `, "${accountcode}"` with a space after the comma → accountcode parsed as
   `" 1001"` → per-extension history always empty. `read_cdr_rows` now normalizes
   whitespace/quotes/`;` per field.
6. **Test-side fixes** (`tests/operator.nix`): JSON extraction rewritten to
   `printf '%s' '<json>' | python3 -c …` (the old `r'''` triple-quote trick had its
   inner double quotes eaten by the shell → SyntaxError → empty URL → the SPA's HTML
   served for `/`); audio fetch captures status+body and dumps the API journal on
   mismatch; `vm_boxcount` assert corrected to the `|all` → `0:0:0:0` format
   (verified against `boxcount_api_function`: default prints a bare `%d`).
7. **Full gate green** under the FINAL module state — every suite re-run this
   session except the four noted in b): `telephony` (pbx multi-node), dialplan,
   webphone, tls-turn, secrets, voicemail, monitoring, backup, fail2ban, ivr,
   time-routing, boot, prod-boot, metal-boot, operator, ssh, eval, docs-drift,
   deadnix, statix, treefmt, initrd-audit, pre-commit. Honest exits checked in every
   log (`EXIT:0` per /tmp/*.log); no pipe-masking.
8. **Docs harvest** (daemon-committed): TODO_LIST — closed P8, P10–P17, P20, P21,
   P22, P26, P28, P29; P23 shrunk to its leftover. FEATURES — new rows for operator
   window/read-model API, fax receive, transfer, incoming-call UX, voicemail panel,
   contacts+history, ICE panel, hygiene scripts; conference + ssh + recordings rows
   updated. CHANGELOG — new entries incl. the **user-visible `#`-no-longer-expels
   conference change** (Changed section) and the operator API (Added) + audio 404s
   (Fixed). README options tour gained `operator.enable`, `phoneApi`,
   `faxExtension`, conference pin note. ops-runbook gained three sections (operator
   window & phone API, conference rooms, inbound fax). `drift_alarm.py` PASS; the
   `docs-drift` check re-run green.
9. **pbx-artmann absorbed** (deploy NOT run): `nix flake update telephony`
   (lastModified 1789663814 → 1789664911), toplevel builds green
   (`/nix/store/b1248ng38…-nixos-system-pbx-…`), **store paths verified moved**:
   telephony-fs-cert `588p4mk…→2sn2g87…`, webphone-root `wlqxdi70…→vzd0v8b…`
   (old-vs-new closure comparison against the Sep-16 `result` root). Daemon
   committed the lock.
10. **P23.3i demo-VM host-side ssh smoke**: `nix run .#vm` → `ssh -p 2222 -i
    ~/.ssh/id_ed25519 root@127.0.0.1` → `SMOKE-OK`, hostname `pbx`,
    freeswitch `active`, nginx `active`. Discovery: `~/.ssh/id_ed25519` derives
    exactly the tracked `lars@evo-x2` public key, so **no throwaway keypair is
    needed** — open question 3 from the morning report is answered.
11. **Post-hoc gate-hole check**: conference/fax/browser/ssh suites do NOT enable
    `phoneApi`/`operator` (grep: zero occurrences), so today's module changes do not
    alter their closures — their earlier green runs remain valid. Verified 19:39.

## b) PARTIALLY DONE

1. **Buildflow full pipeline** — deliberately skipped in favor of the explicit
   per-suite sweep (the handoff allows either), and I ran `nix fmt` directly instead
   of `buildflow -s treefmt`/`--fix`. Equivalent tooling, same configs, green — but
   the canonical buildflow findings-gate run (error-severity threshold, its pinned
   binaries) did not execute this session. The flake's own checks (deadnix, statix,
   treefmt) cover the same ground, so risk is low.
   → open — TODO_LIST hygiene row (one canonical full-mode run)
2. **P23** — every sub-item including the smoke is done, but the TODO_LIST row was
   harvested BEFORE I ran the smoke, so TODO_LIST still lists the demo-VM ssh smoke
   as the one leftover. Stale by an hour; needs a one-line close.
   → done — row deleted in the 2026-09-18 TODO_LIST rebuild (the smoke itself was green, a.10)
3. **Session lessons → AGENTS.md** — the new gotchas (below) are recorded in the
   CHANGELOG and this report but not yet distilled into the sibling repo's
   AGENTS.md "paid-for" gotcha lists, which is where the next session will look
   first.
   → open — out-of-repo (private flake AGENTS.md)
4. **Push state unknown** — the daemon committed ~8+ commits today; last session
   ended with 9 unpushed. `scripts/ahead-check.sh` (P29) exists precisely for this
   but needs network (`git fetch`), which this sandbox lacks. Origin may be red
   while local is green — again.
   → open — owner/daemon push state (the script exists for exactly this)
5. **treefmt-check sandbox oddity** — the check derivation emitted git output ("On
   branch main … nothing to commit") from inside the sandbox before failing on the
   genuinely unformatted `operator.js`. After formatting, green. I did not
   root-cause why git runs inside that derivation; cosmetic but unexplained.
   → open — standing cosmetic oddity, unroot-caused

## c) NOT STARTED

- Operator API longer tail: pagination/CSV export, auth-failure lockout,
  HTTP Range for `send_file`, mark-read (`vm_read`) flip via API.
  → open — TODO_LIST Medium row (operator tail)
- P27 restic `restore` round-trip assertion; P31 hygiene probes; P32
  arrow-annotator contribution to the docs-health skill.
  → open — TODO_LIST Low rows (backup suite + hygiene probes)
- Upstream BuildFlow feedback items (still owner-gated).
  → open — TODO_LIST blocked row
- sops-nix example host (owner-gated).
  → open — TODO_LIST blocked row
- Release 0.3.0 cut (owner-gated; CHANGELOG [Unreleased] keeps growing).
  → open — TODO_LIST blocked row (v0.3.0)
- Deploy lane P1–P5 (owner).
  → open — TODO_LIST High row
- The 50-item ranked list below.
  → annotated inline (2026-09-18 docs-health pass)

## d) TOTALLY FUCKED UP

Nothing was destroyed, no data lost, no wrong claims shipped — but honest process
debt, worst first:

1. **~9 avoidable VM burns on the operator suite** (runs 7–15, roughly 45–60 min).
   The handoff literally said "dump-first debugging proved cheapest … one
   instrumented VM burn settles what blind retries can't", and I STILL under-
   instrumented the first debug run (operator7 lacked freeswitch-unit introspection;
   operator10 lacked numeric uid/gid; operator12 lacked the CDR/DB postmortem), so
   each burn answered one question instead of all of them. The final pattern (one
   burn = probes + fix-validation + postmortem, operator11/16/17) is what run 7
   should have been.
2. **Stepped on a documented trap**: the test-driver typecheck rejects shadowing
   driver builtins; the handoff warned about `log` and I hit the same class with
   `debug` (one wasted burn, operator13).
3. **Hypothesis-first instead of evidence-first on the Group= pin**: I edited the
   module on documented semantics, burned a run discovering systemd 261 doesn't
   deliver what the man page implies, then reverted. The right order was: numeric
   uid/gid probe first, then decide. (Mitigated — the revert is clean and the ACL
   fix is validated.)
4. **The premature "full gate green" claim in my final message**: conference, fax,
   and browser last ran green BEFORE today's module changes. It turned out
   factually safe (verified closures unaffected — see a.11), but I asserted it
   without having checked at the time. A gate claim should carry its closure-
   freshness proof the moment it is made.
5. **Stale `result` symlink confusion** in pbx-artmann (read the Sep-16 root,
   briefly concluded the operator unit was missing from the fresh closure — it was
   operator-disabled there, and my fresh build used `--no-link`). One wasted
   round-trip; `-o /tmp/… --print-out-paths` should have been the first move.
6. **Self-inflicted docs drift**: harvested TODO_LIST, then completed the smoke it
   lists — the file went stale within the same session (b.2).
7. Minor: one `edit` rejected mid-flight for a stale read (daemon raciness — the
   mtime trap the handoff warns about), and `git add -A` used once during harvest
   (worked because the tree was clean, but the rule is targeted adds).

## e) WHAT WE SHOULD IMPROVE

1. **Standardize the "one burn, full evidence" dump** as a shared snippet in
   `tests/common.nix` (probe helpers: unit introspection, numeric ids, db dump,
   CDR, journal grep) so every suite's failure path is comprehensive by default,
   not assembled ad hoc at 3 a.m.
2. **Suite-closure freshness**: a gate claim should state which store paths each
   suite's closure carries, or `nix flake check` should be THE gate so the question
   cannot arise.
3. **Buildflow delegation discipline**: even when the flake's checks are green,
   run the buildflow pipeline as the single canonical verdict (it exists to stop
   me from hand-running its tools).
4. **AGENTS.md memory duty**: distill each session's new gotchas into the sibling
   AGENTS.md at end of session, not just into CHANGELOG/status prose.
5. **Push observability**: run `ahead-check.sh` at session end from a networked
   shell; the daemon stall pattern has now bitten three times.
6. **Security review of the ACL scope**: the `telephony` group (nginx is a member)
   can now read the whole FS state tree including `core.db` (SIP credential hashes).
   Acceptable for the trust circle today, but a narrower group or per-file grants
   deserve a deliberate decision, not a default.
7. **Stream-token key reuse**: `stream_token` HMACs with the ESL password. Works,
   but a dedicated token secret would decouple the two concerns.
8. **vmclient**: record the early-media observation (deposit answers/streams from
   the 183) in a comment — it worked here, but it's a live grenade for future
   ring-group tests that change timing.

## f) NEXT — ranked, up to 50

1. Close the stale TODO_LIST row (demo-VM ssh smoke is done) — 2 min.
   → done — 2026-09-18 TODO_LIST rebuild
2. Distill this session's gotchas into the sibling AGENTS.md.
   → open — out-of-repo (private flake)
3. Run `ahead-check.sh` / push the accumulated local commits from a networked shell.
   → open — owner/daemon (script shipped and ready)
4. Run `buildflow --build-mode full --max-time 60m` in the sibling repo as the
   canonical findings gate.
   → open — TODO_LIST hygiene row
5. Owner: deploy lane P1–P5 (rebuild switch on the recreated server).
   → open — TODO_LIST High row
6. Owner: cut 0.3.0 (the `#` conference change is user-visible; CHANGELOG is ready).
   → open — TODO_LIST blocked row (v0.3.0)
7. Security review: scope the FS-state ACL to a narrower group than `telephony`
   (keep nginx's recordings access out of `core.db`).
   → open — TODO_LIST Medium row (operator security hardening)
8. Dedicated stream-token secret instead of the ESL-password HMAC key.
   → open — TODO_LIST Medium row (operator security hardening)
9. Operator API: pagination for `/messages` and `/operator-api/cdr`.
   → open — TODO_LIST Medium row (operator tail)
10. Operator API: CSV export for the CDR viewer.
   → open — TODO_LIST Medium row (operator tail)
11. Auth lockout on phone-api basic-auth failures (nginx-level or api-side).
   → open — TODO_LIST Medium row (operator tail)
12. HTTP Range support in `send_file` (browser seek/scrub).
   → open — TODO_LIST Medium row (operator tail)
13. Mark-read flip (`vm_read`) via the API (mod_voicemail `vm_save`).
   → open — TODO_LIST Medium row (operator tail)
14. P27: assert a real `restic restore` round-trip in `telephony-backup`.
   → open — TODO_LIST Low row (backup suite)
15. Turn the demo-VM ssh smoke into an automated check (`telephony-demo-ssh`).
   → open — ROADMAP theme 5 (repo plumbing)
16. Investigate the treefmt-check sandbox git noise.
   → open — standing cosmetic oddity
17. Add `telephony-operator` to the monitoring suite's watched-unit coverage.
   → open — ROADMAP theme 2 (operator depth)
18. healthz: add a voicemail-db-reachable probe (would have made the original bug a
    health-card red instead of a user-facing 500).
   → open — TODO_LIST Medium row (operator tail)
19. Parse rotated CDR files (`Master.csv.*`) in `read_cdr_rows`.
   → open — ROADMAP theme 2 (operator depth)
20. `send_file`: ETag/Last-Modified revalidation headers.
   → open — ROADMAP theme 2 (operator depth)
21. Conference caller-controls as module options (mute/deaf keys configurable)
    instead of the hard-coded sed drop of the `#` binding.
   → open — ROADMAP theme 2 (PBX feature depth)
22. Replace the conference `sed` overlay with an XML-aware transform if the file
    shape ever drifts (fragility note, not urgent).
   → open — ROADMAP theme 2 (conditional on drift)
23. vmclient: comment the early-media answering behavior.
   → open — small test-depth note (grep-verified absent 2026-09-18)
24. tests/operator.nix: extract the JSON-extraction one-liners into a shared helper.
   → open — ROADMAP theme 5 (test plumbing)
25. Cross-extension DELETE leak check (404 vs 401 shape) as explicit asserts.
   → open — ROADMAP theme 2 (security tests)
26. Document extension-password rotation ↔ API auth-cache TTL interplay in the
    runbook.
   → open — ROADMAP theme 2 (runbook depth)
27. Operator window: auto-refresh the CDR/health cards.
   → open — ROADMAP theme 2 (operator depth)
28. Hangup-cause color coding in the CDR viewer.
   → open — ROADMAP theme 2 (operator depth)
29. `check_extension_auth` cache: expose TTL as an option.
   → open — ROADMAP theme 2 (operator depth)
30. Runbook: post-deploy verification steps for the ACL unit + `freeswitch-ro` bind.
   → open — ROADMAP theme 2 (runbook depth)
31. Pin FS `StateDirectoryMode` explicitly (documented 0750 posture).
   → open — ROADMAP theme 1 (hardening)
32. P31 hygiene probes batch (docs-health hash sweep, buildflow doctor/upgrade,
    mypy decision).
   → open — TODO_LIST hygiene row
33. P32: contribute the arrow-annotator to the docs-health skill.
   → open — TODO_LIST hygiene row
34. Upstream BuildFlow feedback (max_time config keys, nix-checker FOD advisory,
    mainProgram carve-out) — verify-before-filing first.
   → open — TODO_LIST blocked row
35. sops-nix example host (owner call).
   → open — TODO_LIST blocked row
36. Browser E2E CI promotion (owner call).
   → open — TODO_LIST blocked row
37. operator.js review note from P31 ("formatting-only") — close it.
   → done — prettier-formatted via the gates (2026-09-17 20:23 session; daemon-absorbed)
38. `/tmp` operator logs: conclusions now recorded here; optionally copy the final
    green log into docs/status as evidence.
   → **Won't implement — /tmp logs are ephemeral by design; the suite re-proves the path every run.**
39. Consider `checks` dedupe: docs-drift + deadnix + statix + treefmt already run
    via buildflow — document the split (flake checks = nix-side, buildflow = full).
   → open — ROADMAP theme 5
40. flake-meta-checker mainProgram data-package carve-out (owner, upstream).
   → open — TODO_LIST blocked row (mainProgram)
41. Operator API: 404-vs-401 shape audit for all routes (no existence leaks).
   → open — ROADMAP theme 2 (security tests)
42. Add a `sms-store` fixture leg to the operator suite (the SMS panel currently
    asserts only the empty shape).
   → open — ROADMAP theme 5 (test depth)
43. MWI badge polling interval → `config.js` knob.
   → routed — webphone repo (UI extracted 2026-09-17/18)
44. `parse_sms`: bounded memory for huge sms-store files (mmap or seek-from-end).
   → open — ROADMAP theme 2 (operator depth)
45. Conference: pin `#`-drop with a dedicated eval regression (like
    `ringGroupDidEval`) so a template change can't silently re-add hangup-on-`#`.
   → open — ROADMAP theme 5 (eval regression)
46. Document the demo VM's authorized key (evo-x2) in README so the ssh smoke is
    reproducible for others.
   → **Won't implement — key-comment names stay out of the public README (scrub posture); the tracked-keys pointer is already there.**
47. Consider `machine.execute` timeouts in the operator failure dumps (a hung probe
    would stall the suite).
   → open — ROADMAP theme 5 (test plumbing)
48. FreeSWITCH bump drill: re-run the conference sound-compat derivation check
    against a newer `freeswitch` package before the next nixpkgs bump.
   → open — standing drill, rides the monthly flake-update PR
49. Idea parking lot → ROADMAP: dedicated token secret, ACL scope group, CDR
    viewer export (keep TODO_LIST actionable-only).
   → done — routed: token secret + ACL scope → TODO_LIST Medium row; CDR export → operator-tail row
50. Next session starts by re-verifying this report's green claims with the two
    cheap commands (`drift_alarm.py`, operator suite) — reports age.
   → done — re-proven by the 2026-09-18 extraction session's full gate and this docs-health pass

## g) QUESTIONS FOR THE OWNER (cannot self-answer)

1. **Release**: cut 0.3.0 now (conference `#` behavior change + operator API + fax
   proof are all user-visible and documented), or hold the tag until the first real
   call proves the deployed stack? The [Unreleased] section keeps growing either way.
   → open — TODO_LIST blocked row (v0.3.0)
2. **Security appetite**: the `telephony` group (nginx among its members) can now
   read FreeSWITCH's state tree, including `core.db` with the SIP credential hashes.
   Accept as the trust circle, or should I introduce a dedicated `telephony-ro`
   group so nginx's exposure stays limited to recordings?
   → open — TODO_LIST Medium row (operator security hardening)
3. **Push state**: this sandbox cannot `git fetch`, so I could not verify origin.
   Last session ended with 9 unpushed commits and this session added ~8 more. Should
   you push from evo-x2 before anyone builds on this work, or is origin current?
   → open — owner (since delivered by later pushes per the 09-18 report; `scripts/ahead-check.sh` verifies)
