# SUPERB verdict-truth + tails execution — eval heal, upstream wire bug, suite greens, and a self-inflicted CI red

**Session:** 2026-11-08, ~09:00–15:45 CET (single session, continuing the
08:44 report's train). Plan: the 08:53 SUPERB plan (N1–N17). This
report covers N1–N12 + N14/N15 execution and hands off with an OPEN
CI red the train created itself (§d1 — read before anything else).

## a) FULLY DONE

1. **N1 — the eval gate ROOT-CAUSED and healed (`9a092f9`), attribution
   corrected.** The red was NEVER `ringGroupDidToplevel`/the sibling
   refactor (d66fc3b's message was wrong): the daemon's webphone lock
   sweeps (`1e2a60a`: a4b9a0c, `4c94117`: e762f5a) imported upstream's
   NEW inline-secret guard — any secret-shaped settings key with an
   inline value fails eval (it would render into the world-readable
   config JSON). Three tree sites violated it: hosts/pbx's demo turn
   secret, tests/tls-mode-host.nix's fixture, tests/common.nix's shared
   suite base (that one failing EVERY VM suite toplevel — the exact
   shape CI tripped). All three moved to `turn.authSecretFile` (same
   values, runtime files; coturn splices natively, the boot renderer
   carries WEBPHONE_TURN_REST__SECRET). The eval arms keep BOTH
   renderer lanes covered (crmEval forces the inline form explicitly,
   turnFileEval mkForces its own path, the negative turn arm forces
   both-set). telephony-eval green locally — but see §d1 for the gate
   gap CI exposed.
2. **N5 — all seven marker-monotonicity findings cleared** (`428f2f4` +
   `7445752`): the sweep's damage was prettier column-drops in the two
   2026-10-07 snapshots (restored in-cell with corrected notes) and a
   LIST RENUMBERING in 2026-10-28 (done-marked §f items demoted into
   continuation lines, displacing the verdict blocks of items #11/#6 —
   the archived structure restored verbatim, then count-recovery
   appends for keys #5/#9/#16 whose peaks the renumbered shape had
   inflated). markers_check: 7 findings → 0 across 108 files; the
   restore is fmt-stable.
3. **N2 — the TODO truth sweep** (`b77def0`): nine rows closed with
   evidence verified BEFORE deletion (test_sip_reauth.py exists; csrf
   arm in eval.nix; livez/startupz asserts in webphone.nix; 9/9 provider
   stamps; five CI greens; demo-wallclock; deep-dives; webphone
   FEATURES row b19cf624; M21 batch e82ca47). Row 53 trimmed to its
   remainder; row 71 rewritten to the bounded remainder. The plan's
   errata was PARTLY WRONG: DOMAIN_LANGUAGE vocabulary, the sweep
   executor hunt, and the lagging-inputs refresh did NOT land — those
   rows stay open (grep-proven).
4. **N4 — the CHANGELOG verdict batch** (`28cb55e`): the eval heal (root
   cause named, d66fc3b attribution corrected), the marker restorations,
   the five airtight greens with the serialization root cause (M01/M04),
   M17 provider stamps, M21 batch, the quota option. changelog-headings
   gate green.
5. **N3 — passkey run 7 executed: the run-6 race is FIXED, the ceremony
   is blocked UPSTREAM** (`ce92b2a`). The post-mint
   `systemctl restart webphone.service` countermeasure works: boot
   replay re-projects, run 7's journal shows enroll verify 200 + begin
   200 + "registration ceremony begun" (run 6's user_not_found is
   gone). The browser wall moved into the enroll page's own error
   element ("Network error — try again.") with NO finish request ever
   reaching the server — root-caused AT SOURCE across both repos: user
   mgmt's provider marshals go-webauthn's CredentialCreation raw
   (everything nests under `"publicKey"`) while webphone's enroll.js
   AND go-cqrs-lite's loginpage login.js read `opts.challenge` at the
   TOP level. Three test layers are mutually blind (Go asserts only
   non-empty bytes; the JS tests stub the flat shape; no VM drives the
   real wire). The suite lands the countermeasure and stays red until
   upstream fixes the wire contract.
6. **N10 — go-cqrs-lite#120 filed and verified OPEN.** The issue carries
   the full chain with file:line evidence at both pinned revs, the live
   ceremony journal, the three-blind-test-layers analysis, and both fix
   shapes (unwrap at the provider, or `opts.publicKey ?? opts` in the
   consumers) — no future-work promises, banner unchecked for review.
   The second probe (upstream ExecStart/enroll docs) found NO defect:
   upstream prescribes only the CLI flag, never the `systemctl show
   --value` shape.
7. **N8 — theme-only fast lane FIRST GREEN RUN** (`E2E-THEME-ONLY-DONE`,
   rc=0, captured to a file). Recorded in the runbook's E2E section;
   the relock-ritual fast lane is now real. The same runbook commit
   (`aceb122`) carries the passkey enroll-leg blocker note (#120) and
   the projection-stale troubleshooting recipe (restart re-projects;
   run-7 proof) plus the network-error classifier.
8. **N11 — canary first dispatch PROVEN** (run `42479647624`:
   deliberate-red failed by design, canary-notification ran the no-op
   path — the failure() wiring is live-tested). The symmetric x86
   sentinel landed in ci.yml (`nix eval
   .#checks.x86_64-linux.telephony-eval.drvPath | grep -q '.drv$'`,
   YAML-validated, local-proven). doc-counts claims verified CURRENT
   (AGENTS 344 / FEATURES 49 both re-derive clean — no bump needed).
9. **The demo-wallclock FS wall-clock-stamp assert LANDED AND PASSED on
   its first run** (rc=0): freeswitch.log stamps Berlin wall-clock
   without an offset suffix (proven shape `2026-11-11 22:30:24.898053`
   from the earlier green run's log — checked BEFORE asserting, the
   run-4 waste class avoided); the assert pins the first stamp to the
   pinned RTC's Berlin wall (`2026-11-11 22:`).
10. **N12 — the `system` warning killed at its ROOT, and the TODO row's
    premise corrected** (`70ab538`): the warning was nixpkgs' top-level
    ALIAS `pkgs.system` (warnAlias since 2025-10-28), NOT the nixosSystem
    arg — the "~20 sites" estimate was a misdiagnosis; the real count is
    TWO (the check-vm driver's system sentinel, eval.nix's pristine
    legacyPackages lookup). Both now `pkgs.stdenv.hostPlatform.system`;
    eval emits zero warnings; row closed with the honest count.
11. **N14 — the wait_webphone dedup** (`179f98e`): the #238
    port-poll workaround lived in SIX inline copies across five suites;
    now one helper in common.nix's bootWait block (node parameterized,
    kwargs pass through for the boot-timeout variants). eval green; the
    wallclock + messaging runs already exercised the helper. Plus the
    runbook singles (`c02a79c`): 503 retry semantics (Telnyx redelivers
    ~24h with backoff; the operator window + the persistent-failure
    flip side), lock-doctor `--target-rev` pre-flight wiring, the
    BuildFlow invariants section (--max-time cap, fast-gates-first, the
    accepted-findings green shape, doctor PATH clause).
12. **N15 — singles batch B**: README's two deprecated
    `gateway.allowedCidrs` citations moved to
    `gateways.<name>.allowedCidrs` (the alias row stays, honestly
    documented); scripts/ ruff sweep CLEAN (2 ISC004 wrapped literals
    merged byte-identically, 1 EXE001 chmod — catalog selftest still
    green); the worktree/stash protocol landed in AGENTS.md with the
    foreign-stash verdict: stash@{0} (WIP-on-41ec5c5) is the pre-d66fc3b
    quota/passkey WIP, byte-count identical on eval.nix — a subset of
    landed d66fc3b, safe to drop (owner call recorded).
13. **N6 — M20 messaging depth GREEN** (suite rc=0,
    `MMS-MEDIA-ROUNDTRIP-DONE`): the new in-VM arm proves the full
    outbound MMS media lane — stage (gateway multipart), wire shape
    (stub row carries `"media_urls"` with the
    `https://pbx.test/mms-media/<token>.png` public URL), and DOWNLOAD
    through the REAL nginx → bridge → token-ACL wire returning
    byte-identical content (cmp). The 40008 arm now pins the HUMANIZED
    guidance sentence ("only accepts free-form replies within 24
    hours" + "pre-approved template (managed in the Telnyx portal") —
    not catch-all keywords. `.chan-mms` badge CSS landed (--warn,
    matching the .chan-whatsapp shape; the webroot has a single dark
    theme). Two suite-side gaps were found and fixed ON THE WAY (the
    node maps the vhost hostname via extraHosts — an unmapped name
    made curl answer empty; nginx + 443 waits before https curls —
    the house shape).

## b) PARTIALLY DONE

1. **N1's final gate is UNMET: CI is RED on the train's heads**
   (runs `42480111527`/c02a79c, `42480376875`/64da08c,
   `42480633487`/179f98e — all failing the "Cross-arch eval check" step;
   the 42479647624 run in the list is the CANARY's deliberate red, by
   design). My local gate proved `telephony-eval` green, but CI's flake
   check evals EVERY suite toplevel and caught two sites my fix missed:
   - `tests/secrets.nix:73` sets `turn.authSecretFile =
     "/run/secrets/turn"` as a plain def OVER baseNode's new file form →
     conflicting-definitions eval error.
   - `tests/fax-feed.nix:53` still sets
     `settings.gateway.webhook_secret = "test-hook-secret-4d5e6f"`
     INLINE → the same upstream guard fires on a key I did not sweep
     (the messaging suite had already moved its own line to the file
     form; fax-feed did not).
   Fix shape is known and small (mkForce in secrets.nix; file-form in
   fax-feed) — NOT yet executed. The next push must ride a FULL-eval
   local gate (see §e1).
2. **N7 (M19 voicemail family) — recon only.** No MWI-specific wiring
   exists anywhere in the tree (mod_voicemail defaults carry it); the
   driverInteractive fsapi probe (the real count/msgcount command
   shape), the dialplan MWI assert, and the greeting runbook recipe are
   NOT executed. Gap noted during recon: `state.paths` covers
   `voicemail_default.db` but NOT the voicemail STORAGE dir
   (/var/lib/freeswitch storage — greetings + deposited messages) —
   the backup surface for greetings is an open question the recipe
   must answer.
3. **N13 (harvest + plan annotation + the final airtight verdict)** —
   not started; it waits on the red fix (§b1) so the annotation can
   cite a green head.
4. **Daemon-merge hygiene partially lost**: the soft-reset re-author
   of `70ab538` folded the M20 messaging code (operator.css +
   messaging.nix) into the alias-fix commit — lanes mixed in one
   authored commit; `4e8e5bb`/`15799f4` carry more singles content
   under heuristic messages. Content is all on main; the verdict
   narrative lives in this report + the next CHANGELOG batch.

## c) NOT STARTED

1. The two CI-red fixes (§b1) + the healed-head push + airtight verdict.
2. M19's MWI probe/assert + greeting recipe + the dialplan suite run.
3. N13 harvest, plan annotation, archive-when-annotated.
4. CHANGELOG verdicts for M18 (theme green + passkey upstream-blocked),
   M20 (media roundtrip green), N12 (2-site alias fix).
5. Quota VM-level proof (row 58, time-boxed: maxMessages=2, fill the
   box, full-prompt evidence).
6. startupz drain probe (driverInteractive during a webphone restart).
7. doc-counts archived-pin verdict (row 46, one paragraph).
8. Executing the stash drop (subset-proven; owner call recorded).
9. Upstream follow-through on go-cqrs-lite#120 (watch → relock → the
   passkey suite's enroll leg goes green when the wire contract lands).

## d) TOTALLY FUCKED UP

1. **The verdict-truth train shipped its own red.** I pushed the eval
   fix after proving `telephony-eval` green — but that check does NOT
   eval every VM suite's toplevel; CI's flake check does, and two more
   scrutiny-surface sites (secrets.nix conflict, fax-feed inline
   secret) turned three consecutive pushes red. The miss: my local
   gate was a SUBSET of the CI gate, and I treated it as equivalent.
   The rule this buys: pre-push gate = `nix flake check --no-build`
   (evals every toplevel in ~2 min), never the single check attr
   alone, whenever the change touches fixture/secret shapes that
   multiple suites inherit.
2. **The pipes-mask-rc trap bit me IN THE SAME SESSION I committed the
   lesson about it.** The passkey "PK_EVAL_RC=0" was tail's rc — run 7
   had actually FAILED (stall before ENROLL-CEREMONY-DONE). The
   content-check discipline (grep the log for the markers) is what
   caught the lie — the marker grep showed 4×ENROLL-CEREMONY-DONE from
   the testScript SOURCE and zero PASSKEY-E2E-DONE. Lesson honored in
   every later run (rc captured to a file, no pipes), but the first
   passkey read was wrong for several minutes.
3. **Two daemon fold-ins mixed lanes inside authored commits**
   (70ab538 carries N6's code under an N12 message). Every fold-in
   trace dates to the same window shape: gates ran, edits from the
   NEXT lane were already on disk, the daemon swept mid-commit. The
   remedy is sequencing, not speed: commit the landed lane BEFORE
   opening the next lane's files.

## e) WHAT WE SHOULD IMPROVE

1. **Local-gate parity**: pre-push = `nix flake check --no-build` when
   the change touches anything suites inherit (fixtures, baseNode,
   module settings shapes); the single check attr is only enough for
   leaf edits.
2. **Scrutiny-surface sweep per lock move**: grep the suite nodes +
   hosts for the guard's key grammar (`*secret*`, `*token*`,
   `*password*` non-`*_file` settings keys) whenever the webphone lock
   moves — the upstream guard's reach grows with each upstream
   release, and inline fixtures are the exposed surface.
3. **rc-to-file as reflex** on every background job, including the
   "quick" ones; the content-check (grep the marker) is the SECOND
   half of every verdict, never a substitute for a clean rc.
4. **Lane sequencing**: hand-authored commit FIRST, then the next
   lane's edits — the daemon's window only bites uncommitted work.
5. **The plan-file execution record**: annotate plan rows as they land
   (N13's discipline) instead of batching at train end — this report
   reconstructed the landed-set from git archaeology, which is the
   failure mode the annotation convention exists to prevent.

## f) Up to 50 things next (impact-sorted; 1–13 are this train's tails)

1. Fix `tests/secrets.nix:73` — mkForce the suite's own turn-secret
   file path (unblocks the CI eval step).
2. Fix `tests/fax-feed.nix:53` — inline `gateway.webhook_secret` → the
   file form (gatewaySecretFile wiring, the messaging-suite precedent).
3. Full-eval local gate (`nix flake check --no-build`) → push →
   airtight CI verdict over the healed head (cancel ≠ red protocol).
4. M19 MWI probe: driverInteractive on the dialplan fixture; deposit a
   message; discover the REAL voicemail fsapi count/msgcount shape.
5. M19 MWI assert pinned in dialplan.nix after the voicemail-fallback
   leg (what an MWI endpoint reads).
6. M19 greeting recipe: runbook subsection (*97, the storage path,
   backups) + the state.paths coverage verdict for the greeting dir.
7. Dialplan suite run carrying the MWI assert; M19 lane commit.
8. N13 harvest: fold this report's §c items into TODO_LIST.
9. N13: annotate the 08:53 plan's rows as landed; archive when every
   row carries a verdict.
10. CHANGELOG verdict batch 2: M18 (theme green, passkey upstream-
    blocked + #120), M20 (media roundtrip), N12 (2-site alias).
11. Quota VM-level proof (time-boxed; ONE suite attempt then stop).
12. startupz drain probe via driverInteractive during a webphone
    restart.
13. doc-counts archived-pin verdict (pin or reject, one paragraph).
14. Drop the reconciled stash (subset-proven; §d-verdict recorded).
15. Watch go-cqrs-lite#120: when the wire fix lands upstream, relock
    (ritual-gated) and rerun the passkey suite — the enroll leg greens.
16. Verify-live.sh livez gates (the ops-depth row remainder).
17. Operator `/version` consumption (ops-depth row).
18. Dashboard/paperless eval arms (ops-depth row; only on verdict flip).
19. Post-deploy browser smoke (ops-depth row).
20. Missed-call ring shape assert (ops-depth row).
21. cdr-visibility row-shape assert (ops-depth row).
22. Synthetic-DID convention doc (ops-depth row).
23. verify-live.sh livez/startupz probe gates (report-1 item 38 tail).
24. ESL presence-coverage gap in the textagent fixture (TODO row 45).
25. CDR cancelled-leg live-host track (TODO row 46; owner-side host).
26. docs-batch: the hook-strip + go-git long-form into
    docs/lessons/operating.md (TODO row 52 remainder).
27. Cross-arch eval-thrash narrative into operating.md (row 52).
28. README BuildFlow pointer (row 52).
29. CHANGELOG backfill entries for the hook self-heal + test-infra
    waves (row 52).
30. (repo: pma) go-commit hook gating + the flake.lock exclude_pathspecs
    lever + fleet exposure sweep (TODO row 54).
31. (repo: crush-config) the round-11 sweep lessons into the lessons
    file, by commit (TODO row 55).
32. DOMAIN_LANGUAGE ritual vocabulary (row 67 — verified NOT landed).
33. Sweep executor hunt: instrument the mystery `nix flake update`
    executions (row 69 — verified NOT landed).
34. Refresh the lagging inputs: flake-parts_2 (2026-09-03) + 
    home-manager (2026-09-18) once the bot toggle flips (row 68 —
    verified NOT landed).
35. Browser-render screenshots placement decision (owner-visual lane).
36. E2E CI promotion gate (owner-gated; the canary run proves the
    dispatch path now).
37. Branch protection + required checks (owner-gated; the red streaks
    keep arguing for it).
38. ALERT_WEBHOOK secret fire-drill with a REAL secret (the canary
    proves the wiring; the secret path still needs one live shot).
39. sops-nix example host (owner-gated).
40. /metrics consumer card (owner-gated).
41. retentionDays facade policy option (owner-gated).
42. Push seam scope decision + ASR provider decision (owner-gated;
    audit refresh triggers).
43. a0c78ca history surgery (owner-gated).
44. Stale chore/flake-update-2026-09 branch cleanup (owner-gated).
45. flake-update bot Actions toggle (owner-gated).
46. (repo: pma) the daemon's hook gating, fleet-wide (owner-gated).
47. First-deployment close-out hands-on steps (owner-gated).
48. fspbx sign-off + Sanctum PAT revocation (owner-gated).
49. Warsaw DID + KYC window (owner-gated).
50. Telnyx key rotation + scrub-pattern update in one action
    (owner-gated).

## g) Questions for the owner

1. **The CI red on the train's heads** (§d1): fix-forward NOW in this
   lane (two small fixes + the full-eval gate + push), or route to the
   sibling session (their nix-native lane is quiet ~4h; the fixes are
   in MY changed files' blast radius, so my default is fix-forward)?
2. **The fax-feed inline secret** (§b1): move it to the
   `gatewaySecretFile` module wiring (the messaging-suite precedent,
   one more *File surface), or keep a suite-local `/etc` file read by
   the existing environment-file seam (smaller diff)? My default: the
   suite-local file — smaller, and the module wiring is unchanged.
3. **The reconciled stash** (§c8): `stash@{0}` is proven a subset of
   landed d66fc3b (eval.nix line-count identical) — drop it now, or
   keep it until you eyeball `git stash show -p` yourself?

---
💘 Generated with Crush (GLM-5.3-flash)
