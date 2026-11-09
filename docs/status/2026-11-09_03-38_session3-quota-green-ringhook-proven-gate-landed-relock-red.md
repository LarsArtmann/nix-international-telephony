# Status — session 3 of the verdict-truth train (2026-11-08 evening → 2026-11-09 03:38 CET)

Session scope: the handoff's open red (the voicemail quota arm), the
ringhook lane the sibling session left half-wired, the §f tails, and
the owner questions. Two airtight CI greens landed over my heads; the
tip went red AFTER my pushes — through a sibling's webphone v2.10.0
relock, not through this session's commits.

## a) FULLY DONE

1. **The voicemail quota saga is CLOSED, source-true, and CI-green.**
   The root cause of the seven-run red was never calibration margin:
   it was the UNIT. mod_voicemail 1.11.1 compares `sum(message_len)`
   against `vm-disk-quota`, and `message_len` is a DURATION —
   `measure_file_len` divides the file position by the samplerate,
   `create_file` divides `samples_out` by the rate, and the generated
   email bodies read "%u second Voicemail" (mod_voicemail.c:1176,
   :1238, :1883; nixpkgs f9a75f41 ships vanilla 1.11.1, zero patches —
   verified via the derivation). The option now says SECONDS honestly
   (options.nix example 3600), the eval quotaCheck asserts the
   directory param at 3600, and the suite arm is deterministic from
   the source invariants: the cap sits BELOW min-record-len (2 < 3),
   so any STORED message exceeds it by construction. Live proof: after
   the over-quota deposit the index DB froze at `(count=1, sum=13)` —
   the refusal fired, no second wav — with the param read back through
   sofia's own `user_data` lookup returning `'2'`. The 102400-byte
   interim that cost CI run 42508659445 is documented in CHANGELOG.
2. **The ringhook lane went from inert to VM-proven end to end.** The
   sibling session shipped the shim + dialplan emission + module, but
   three runtime faults made it dead code: (i) `mod_curl` was never in
   the rendered `modules.conf.xml` load list — every call to an
   extension died with a 502 ("unknown application"), the exact gap
   the fax/xml_curl conditional loads prevent for their modules;
   (ii) the derived POST target lacked the shim's `/ring` path —
   mod_curl POSTed to `/` and 404'd; (iii) the secret derivation nested
   `mkIf` INSIDE `mkDefault`, leaking a raw `_type = "if"` attrset into
   the option type check (eval-red). Plus two test-side faults: the
   ringhook eval fixture's gateway lacked `didDestination` (now
   unconditionally accessed), and the eval check's dialplan accessors
   missed `.text` — every dialplan assertion grepped a store PATH
   string and returned false. After the fixes, tests/dialplan.nix
   proves the whole wire on a booted stack: `forwarded ring for 1000`
   and `forwarded end for 1000` in the shim journal, POST `/ring` 202,
   verdict 503 from webphone (fire-and-forget contract — the call
   never noticed).
3. **`checks.driver-typecheck` landed** (the 20:56 report's e1/§f48):
   builds every VM suite's test driver — each driver build runs the
   test script's Python type check — without booting anything. Closes
   the `--no-build` eval gate's structural blind spot (the
   "wait_webphone used when not defined" splice class of CI
   42500794001, and an inverted check condition that sat green in CI
   for a week). Checks count 49 → 50, FEATURES/README updated.
4. **Two airtight CI GREENs over my heads**: `42533371040` (10509d7:
   quota fix + ringhook completion + driver gate) **SUCCESS** — that
   run's `nix flake check` includes the healed telephony-voicemail arm
   AND the new dialplan ringhook arm AND the prod-boot re-proof;
   `42535372698` (d6e768a: + textagent ESL arm + plan archive)
   **SUCCESS**.
5. **The 08:53 plan is annotated and archived** (d6e768a): all fifteen
   agent-executable rows carry evidence-cited verdict arrows (ten done,
   three partial, two routed open; N16/N17 carry-forward arrows added
   to satisfy the archived-snapshot rule). markers_check 0 across 109
   files, rendering_audit 0.
6. **The textagent's ESL leg is proven** (7335aa7): the fixture now
   drives a real handshake (`/etc/esl-auth-probe.py`: greeting → auth
   with the shared password → `+OK accepted` required). The 2026-10-26
   green run never proved this — presence/missed-call drafts degrading
   to schedule-only was an unconfirmed fear. Suite green on the first
   full run; TODO row closed.
7. **TODO truth sweep**: rows closed with evidence — 44 (ESL gap,
   proven), 48 (prod-boot re-proof, landed in CI 42533371040), 49
   (buildflow step-name resolved via `buildflow list steps`: the Python
   lane is `ruff-check`/`ruff-format`/`mypy-check`/`pytest-test`/
   `bandit-check`, recorded in AGENTS.md), 59 (DOMAIN_LANGUAGE
   relock vocabulary — all four terms already present; the row was
   stale). Row 62 (go-cqrs-lite#120) gained the healing fact: the
   webphone-side enroll-STORE split that forced the 2026-11-08
   forward-pin is GONE at upstream HEAD 5c623e78 (CLI mint and serve
   `EnrollSvc()` both ride the metaengine enroll-token stream — probed
   via the GitHub contents API tonight).
8. **Docs moved forward**: ops-runbook gained the ringhook operator
   recipe (enable, secret derivation/rotation, health/journal verify)
   and the diskQuota-seconds operator note; docs/lessons/operating.md
   gained the cross-arch eval-thrash narrative (the 22-cancelled-run
   reclassification rule + the --no-build blind-spot note); README
   gained the BuildFlow pointer + driver-typecheck mention; FEATURES
   gained the diskQuota and ringhook rows (both 🟢, CI-proven); the
   AGENTS audit paragraph's stale "zero references here" push-seam
   claim is corrected (the producer side landed).
9. **§g answered from inside the repo** (details in g): quota KEPT;
   the webphone enroll-split issue NOT filed (healed upstream before
   filing); push policy moot (origin already carried the interim shards
   — the daemon had pushed through 89eca55/fccc1f4 before this session
   started).

## b) PARTIALLY DONE

1. **The CI verdict over the CURRENT tip is RED — and it is not this
   session's code.** After my two green heads, a sibling/daemon lane
   pushed `072138d` ("relock webphone e762f5af -> 3da66985 (v2.10.0)")
   and `8c5dff7` (its CHANGELOG attribution) at ~23:47Z. CI run
   `42536820517` over that head and `42538177192` over my docs-only
   `cf6283b` (which sits on top of it) both FAIL on the SAME
   signature the 2026-11-08 forward-pin diagnosed: **"fresh enrollment
   token must verify 200, got 503"** (`userauth.enroll.invalid`) — the
   passkey enroll leg. v2.10.0's enroll wave still needs what
   go-cqrs-lite#120 owes (or a matching go-cqrs-lite bump); the relock
   landed without the ritual's gate-4 stop. My heads are green; the
   tip is not mine.
2. **§f singles batch**: the ESL row and step-name row closed, but the
   batch's remaining tails (port-poll dedup, 503 retry-semantics doc,
   lock-doctor `--target-rev` runbook wiring, BuildFlow invariants
   row, scripts/ ruff tail, README singular-gateway grep, deep-dive
   screenshots placement, worktree/stash protocol note) are untouched.
3. **The ringhook consumption verdict**: the dialplan suite proves the
   shim contract (202 fire-and-forget); webphone answered 503 there
   because that fixture runs without the gateway webhook secret. A
   configured-secret proof (200 end to end) is a possible follow-up
   arm, not yet built.

## c) NOT STARTED

1. **Triage of the v2.10.0 relock red** (see b1): either forward-pin
   back to e762f5af tonight per the ritual's stop rule, or prove the
   pairing rev (does 3da66985 need a go-cqrs-lite bump that carries
   the #120 marshal fix?). NOT touched this session — it landed after
   my last substantive push.
2. The deep-dive HTML refresh itself (the standing trigger fired — the
   push-seam producer landed — but only the AGENTS note records it).
3. §f carries 16–50 below.
4. The serial-console printk-ratelimit lesson is recorded inline in
   tests/voicemail.nix and CHANGELOG but not yet long-formed into
   docs/lessons/vm-testing.md.

## d) TOTALLY FUCKED UP (honest failures)

1. **Three more VM runs burned on the quota arm after the root cause
   was known.** The unit fix (bytes → seconds) was right on the first
   try, but I then guessed the calibration TWICE from a recording-
   length model I never measured (5 s — the recording is ~13 s minus
   greeting, but I assumed 9; then the journal assert hid the truth).
   The winning move — cap BELOW min-record-len, making the arm
   calibration-free — was available on run one if I had read the
   invariant instead of modeling the recording.
2. **I asserted a log line the platform structurally cannot deliver.**
   The "Voicemail disk quota is exceeded" NOTICE fired (proven: the
   DB froze) yet never reached the VM journal — FreeSWITCH's console
   flood over the serial console hits kernel printk ratelimiting, the
   same suppression class that ate the dialplan Processing lines
   earlier in the same log. One full run wasted; the DB-state contract
   was the assertable truth all along.
3. **The daemon raced me three times and I fumbled one of them**: docs
   shards swept mid-edit (fine — re-authored), the textagent arm swept
   (re-authored), and my own soft-reset for the re-author DISCARDED the
   just-made archive commit — I caught the `D docs/planning/...` in
   the same command's output and re-committed it immediately, but the
   dance should have been one atomic sequence the first time.
4. **The inverted quota condition (`!nullHas && setHas`) was my own
   session-2 code** and sat green in CI for a week because `--no-build`
   never runs check scripts. I found it only by BUILDING the eval check
   locally. The lesson is now structural (driver-typecheck + the
   lessons note), but the defect class was mine.
5. **The first ESL probe used a Python `while` inside a `;` chain** —
   a SyntaxError at driver runtime. The escaping discipline solved the
   wrong problem; the writeText probe-file pattern (the proven
   esl-mwi-listen shape) was the right tool and I reached for it only
   after the failure.

## e) WHAT WE SHOULD IMPROVE

1. **Assert STORED STATE, never log lines, on serial-console VMs** —
   printk ratelimiting silently drops arbitrary console bursts; the
   DB/wav/filesystem state is the honest oracle. Generalize the
   voicemail.nix comment into a vm-testing lesson.
2. **Derive test constants from source invariants** (min-record-len,
   samplerates, DB row shapes) instead of measuring or modeling
   runtime quantities. The 2<3 cap needs no calibration and can never
   drift.
3. **An application↔module eval assertion**: the generator can emit
   `<action application="curl">` but modules.conf.xml didn't load
   mod_curl — a cheap render-time cross-check (every application the
   generated dialplan references must appear in the rendered load
   list) would have caught the ringhook 502 class at eval seconds
   instead of a VM run.
4. **Batch the docs commits BEFORE pushing the substantive head**, so
   the airtight verdict's head IS the tip. Tonight the tip moved
   post-verdict (sibling relock + my docs), which is how a green
   verdict stopped describing main.
5. **The daemon is now the primary attribution hazard** (three sweeps
   tonight; it also PUSHES). The re-author dance works but burns
   attention every time; the structural fix stays inside pma/go-commit
   (owner lane, fleet-wide).
6. **Multi-line Python belongs in writeText files, never in `;`
   chains** — extend the existing escaping lesson with the compound-
   statement trap.

## f) Up to 50 things to do next

1. Triage the v2.10.0 relock red: forward-pin to e762f5af per the
   ritual, or prove the pairing (go-cqrs-lite bump carrying #120).
2. Re-probe go-cqrs-lite#120 for the marshal fix (the enroll leg's
   true blocker).
3. The application↔module eval assertion (e3).
4. Serial-console ratelimit long-form into docs/lessons/vm-testing.md.
5. Deep-dive HTML refresh (push seam landed; ASR still open).
6. A configured-secret ringhook arm proving a 200 forward verdict.
7. Sweep-executor hunt (the mystery `nix flake update` runs).
8. verify-live.sh livez/startupz gates.
9. 503 retry-semantics doc in the runbook messaging section.
10. lock-doctor `--target-rev` wiring into the runbook pre-flight.
11. port-poll helper dedup into tests/common.nix.
12. BuildFlow invariants row (README pointer landed; the row's tail).
13. scripts/ ruff sweep tail.
14. README singular-gateway grep.
15. deep-dive screenshots placement.
16. worktree/stash protocol note (recovery point 2895944 until reflog
    GC).
17. Attributed relocks for the parked nixpkgs f4a03c00 + pbx-lens
    ca1dd821 revs.
18. CDR cancelled-while-ringing live-host track.
19. Lagging non-webphone inputs refresh (flake-parts_2, home-manager).
20. pma/go-commit hook gating (tonight's triple-race is the exhibit).
21. crush-config lessons-file round-11 entries (by commit).
22. Operator `/version` consumption.
23. Post-deploy browser smoke.
24. Missed-call ring shape assert.
25. cdr-visibility row-shape assert.
26. Synthetic-DID convention doc.
27. verify-live.sh re-run against pbx.artmann.tech after next deploy.
28. Branch protection + required checks (owner admin call, packet
    ready).
29. ALERT_WEBHOOK secret fire-drill (owner).
30. WhatsApp live round-trip (owner, WABA).
31. Lens UI vhost decision (owner).
32. fspbx trial sign-off (owner; PAT revoke).
33. Warsaw DID + DE DID (owner, KYC window).
34. Telnyx API key rotation (owner).
35. Scrub placeholder fill-or-delete (owner).
36. GitHub GC / stale-clone inventory after the history rewrite
    (owner).
37. Global hooksPath landmine fix (home-manager, owner).
38. Browser E2E CI promotion (owner call).
39. sops-nix example host (owner).
40. nixpkgs upstream lane from the mkForce audit (owner-gated draft).
41. `/metrics` consumer card (owner-gated).
42. `webphone.retentionDays` facade (owner-gated).
43. ROADMAP raw ideas carry-forward (staleness alarm, bulk-commit
    split, nixpkgs lock fencing, voicemail depth remainder).
44. aarch64 TCG boot suite stays outside driver-typecheck by design —
    revisit if the splice class ever bites arm runners.
45. Re-verify docs/providers before any purchase (standing).
46. Domain-language: add "ringhook" + "enroll token stream" entries if
    the vocabulary grows again.
47. Consider recording the quota unit story as a FreeSWITCH upstream
    docs issue (the vm-disk-quota name vs seconds semantics is
    genuinely misleading — verify-before-filing first).
48. Dialplan suite: assert the shim's end-fact arrives AFTER the call
    fully tears down (ordering nit, optional).
49. Archive this session's plan when the next planning cycle lands
    one.
50. Keep CI-verdict hygiene: after any multi-push sequence, run the
    final `gh run view` over the TIP sha before declaring green.

## g) Owner questions (not answerable from inside the repo)

1. **The v2.10.0 relock red on the tip**: forward-pin back to
   e762f5af tonight to restore green CI (the ritual's own remedy, one
   commit), or leave the red up while you decide whether v2.10.0's
   enroll wave pairs with a go-cqrs-lite bump that fixes #120? The
   relock itself is correctly attributed in CHANGELOG (8c5dff7) — only
   its gate-4 outcome is red.
2. **go-cqrs-lite#120 watch**: keep it passive, or should the next
   session re-probe upstream and, if the marshal fix landed, run the
   full passkey-enroll relock lane (webphone 3da66985 + the bumped
   go-cqrs-lite + tests/passkey.nix) immediately?
3. **Ringhook consumption proof**: is the 202-verified shim contract
   (what the dialplan suite proves) enough for the audit's push-seam
   closure, or do you want a configured-secret arm proving webphone
   answers 200 to a forwarded fact before the deep-dive refresh
   declares the seam closed?
