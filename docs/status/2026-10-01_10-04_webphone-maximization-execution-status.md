# Webphone-maximization execution status — 2026-10-01 10:04

**Scope:** Full Execution Mode of the 13-task SUPERB Pareto plan
(`docs/planning/2026-10-01_06-19_SUPERB-webphone-maximization-pareto-plan.md`),
tasks T01–T11 (T12/T13 owner-gated, defaults: skip). Plus one unplanned
blocker fix that the train depended on.

**Format note:** `.md` per explicit user instruction (the status-report
skill's canonical format is HTML; override honored, not propagated).

---

## a) FULLY DONE

1. **T01 — Backup truth-up (Critical, the 1%→51% task).** Webphone,
   recordings and CDR now ride restic: `state.paths` carries the
   webphone online-snapshot dir, `services.webphone.backup.enable`
   defaults on, the restic unit `Wants`+`After`s `webphone-backup`
   (fresh consistent snapshot every run), `state.sqliteDatabases`
   names the live `webphone.db`, pbx-prod consumes `state.paths`.
   Evidence: commit `e8ac9cc` + docs-truth `56919af`;
   `telephony-backup` VM suite GREEN twice — with blob + recording +
   CDR canaries round-tripping byte-exact and the restored db being a
   genuine SQLite file — at TWO locks (the swept 41c8ade and the
   restored green pair). Drift/markers/lock-guard gates PASS.
2. **Unplanned: CI-red root cause fixed locally (commit `81ac99a`).**
   Every origin CI run since `428ee5d` failed: the 2026-10-01 daemon
   sweeps (`8cf9e48`, `b2acca6`, `db59670`) carried an unvetted
   nixpkgs bump (`b4fd65b`, glibc 2.44 + gcc 16) into main, and
   FreeSWITCH 1.11.1's `mod_enum` does not compile against it
   (`conflicting types for __assert_single_arg`; verified in CI logs
   36795217002/36789955809 and reproduced locally). Restored the lock
   byte-identical to the last-green pair (nixpkgs `7a0f122f`, webphone
   `0e1d1743` = 3afcf57's lock, green on both arches) and proved the
   backup suite green at exactly that lock. NOT yet pushed — origin is
   still red until T08's push.
3. **T03 — daemon-race lesson** (commit `e9480a1`): assemble
   multi-write artifacts in /tmp, single atomic `mv`, scrub BEFORE the
   artifact lands; cites the `1e552f4` half-written-report incident.
   Applied in practice for this report (assembled in /tmp).
4. **T02 — /metrics fence** (commit `5ec2dd2`): nginx exact-match
   location, allow 127.0.0.1/::1, deny all. `telephony-webphone` suite
   GREEN with both directions asserted: egress-IP client → 403,
   loopback → full Prometheus text (build_info + uptime). One triage
   round (the driver's mypy type-check rejected `re.search(...).group`
   on Optional — fixed with an assert-guarded match).
5. **T04 + T05 — identities derivation + gateway auto-wire** (combined
   commit `7853c5b`; both features share tests/eval.nix, and the daemon
   had already entangled the staging — one fully-attributed combined
   commit beat two misleading ones). `settings.identities` derives
   extension → gateway DID (ring-group members included; eval-armed
   both derive-and-absent). Messaging now auto-wires webphone's webhook
   gateway (mode/URL/secret-file from `messaging.gatewaySecretFile`;
   inline `webhook_secret` fails at EVAL; pbx-prod CHANGEME seam
   pruned). `telephony-eval` GREEN with the new happy + rejection
   arms; `telephony-messaging` suite GREEN incl. rendered-runtime-config
   proof.
6. **T06 — memoryMax** (512M on `services.webphone` in pbx-prod):
   eval-verified — the option lands and the unit's MemoryMax reads
   512M; `telephony-eval` GREEN. Committed inside daemon batch
   `ec277f5` (attribution imperfect — see d/3).

Session evidence pattern: every suite verdict additionally confirmed
via `nix build --no-link --print-out-paths` (output path returned =
derivation succeeded; piping through `tail` masks exit codes).

## b) PARTIALLY DONE

1. **T07 — relock ritual.** Not executed, but fully researched: the
   target has MOVED — upstream main is now `f706575` (28 commits past
   the restored pin `0e1d1743`), adding beyond the audit's list: the
   contacts-manager feature AND its revert (net zero), a Settings
   command palette, and (post-audit) a Paperless-ngx fax archive seam
   - the go-health dashboard — the latter two are NEW capabilities the
     audit never scored. Markup delta vs the pin is heavy
     (layout/messages/settings templ + shell.js), so the browser E2E is
     MANDATORY per the runbook. Effort left: M (the full ladder:
     relock → binary build → fast gates → webphone suites → browser E2E
     → CHANGELOG rev entry → hand-authored commit).
2. **T08 — full-mode buildflow + origin CI verdict.** Blocked on T07
   landing (and on the lock-strategy decision below). The push itself
   is what turns origin's CI red streak green again. Effort: M.

## c) NOT STARTED

- **T09 — evidence hardening** (browser-render the audit report, full
  Unreleased delta note, demo-VM /metrics probe post-fence, report
  addendum with upstream module-check citations + the new-capabilities
  note). Low impact, M effort. Still wanted: the audit's claims
  deserve probe evidence now that the fence exists.
- **T10 — open-probe sweep verdict** (`/healthz` `/livez` `/startupz`
  through the vhost catch-all). Low, S effort.
- **T11 — /health dashboard spike** (`settings.dashboard.enable`).
  Low, S effort; default verdict: keep off.
- **T12/T13 — owner-gated extras** (metrics consumer card; retention/
  timezone facade options). No gate answers given → defaults apply:
  skipped. Re-open on owner request.

## d) TOTALLY FUCKED UP

1. **Origin main's CI is RED** (every run since `428ee5d`, ~10 runs).
   Root cause: daemon-absorbed nixpkgs bump vs FreeSWITCH mod_enum
   (details in a/2). Severity: blocks every PR-lane validation and
   erodes "CI means something". Mitigation in place locally
   (restoration commit `81ac99a`); the fix reaches origin only at
   T08's push. The red window has been open ~17 hours.
2. **The daemon swept the lock THREE times this morning** — and the
   third (`db59670`) silently UNDID a documented, CHANGELOG-carrying
   restore (`5969278`-era entry). `checks.lock-guard` only checks
   CHANGELOG attribution after the fact; nothing PREVENTS a sweep.
   This is the third incident class in a week (2026-09-24/25, now
   2026-10-01). The lock is the most daemon-dangerous file in the repo.
3. **Commit attribution keeps getting eaten.** T06's line landed inside
   daemon batch `ec277f5` — entangled with a SIBLING SESSION's work
   (see d/4), so a clean surgical re-commit would touch their lane.
   Accepted cost; the plan's "commit each task separately" held for
   T01/T02/T03/T04+T05 but broke for T06.
4. **Two sessions are concurrently fixing the same CI break with
   OPPOSITE strategies.** This session: back-pin to last-green (active
   in `flake.lock`). Sibling session: a gcc-16/glibc-2.44 assert shim
   (`modules/telephony/freeswitch-assert-shim/assert.h` + an
   overrideAttrs in `pbx.nix`, committed inside `ec277f5`) that
   enables the NEW toolchain. Interaction hazard: the shim changes the
   freeswitch derivation hash → EVERY suite now rebuilds FreeSWITCH
   from source (30+ min per fresh arch) even on the old toolchain
   where the shim is unnecessary. The two strategies coexist in-tree
   without an owner decision. Not touched (not my lane to revert).

## e) WHAT WE SHOULD IMPROVE

1. **A preventive lock guard.** `lock-guard` is post-hoc. Add a
   pre-commit hook (or make the daemon skip `flake.lock`): a lock
   change without a `ritual:` marker in the message gets rejected.
   Impact: kills the recurring unattributed-sweep class entirely.
2. **Session-lane declaration for this shared tree.** Two agents
   worked the same breakage in one tree with no visibility of each
   other beyond git artifacts. A tiny `LANES.md` scratch (branch-name,
   scope, TTL) or a convention of pushing a WIP commit per lane would
   make concurrency visible. Impact: prevents duplicate/contradictory
   work (today: back-pin vs shim).
3. **Suite verdicts should never trust a piped exit code.** This
   session caught itself echoing `tail`'s exit status twice; the
   `--print-out-paths` pattern should be the documented standard in
   AGENTS.md's commands section.
4. **The eval `nix.nixPath` rename warning** (ops.nix vs current
   nixpkgs) is noise on every eval — a two-line fix riding the next
   lock move. → done 2026-10-02 (`nix.settings.nix-path` rename landed
   with the ffaa03fd5ce5 relock; eval warning gone, `nix flake check
   --no-build` clean)

## f) Top things to get done next

| #  | Task                                                                                                                                                                                                                                | Impact   | Effort       | Category      |
| -- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------ | ------------- |
| 1  | **OWNER DECISION: lock strategy** — forward (sibling's assert shim + nixpkgs bump, patch maintained locally until upstream fixes gcc-16/glibc-2.44) vs back-pin (current, proven green, 2-day-old nixpkgs). Blocks T07/T08 shaping. | Critical | S (decision) | Decision      |
| 2  | T07 relock ritual `0e1d1743 → first-green ≥ f706575` (full ladder, browser E2E mandatory, CHANGELOG rev, hand-authored commit)                                                                                                      | High     | M            | Feature       |
| 3  | T08: `buildflow --build-mode full --max-time 60m` to the documented green shape + push + airtight `gh run view` CI verdict                                                                                                          | High     | M            | Quality       |
| 4  | TODO_LIST truth-up: delete the done rows (metrics fence, identities, gateway auto-wire, memoryMax) + prune the relock row's stale rev pair                                                                                          | High     | S            | Documentation |
| 5  | AGENTS.md: record the daemon-lock-sweep class + the `--print-out-paths` verdict standard + the sibling-lane hazard                                                                                                                  | Medium   | S            | Documentation |
| 6  | Preventive lock guard (pre-commit hook refusing unattributed flake.lock moves)                                                                                                                                                      | Medium   | S            | Quality       |
| 7  | T09 evidence hardening (report render, CHANGELOG delta note, demo-VM /metrics probe, addendum incl. Paperless + dashboard as NEW upstream capabilities)                                                                             | Low      | M            | Documentation |
| 8  | T10 open-probe sweep verdict (/healthz /livez /startupz through-vhost)                                                                                                                                                              | Low      | S            | Security      |
| 9  | T11 /health dashboard spike verdict (default: keep off)                                                                                                                                                                             | Low      | S            | Feature       |
| 10 | ops.nix `nix.nixPath` → `nix.settings.nix-path` rename fix (rides the next lock move)                                                                                                                                               | Low      | S            | Cleanup       |
| 11 | Evaluate upstream Paperless-ngx fax archive seam (paperless.url/token) for this stack post-relock                                                                                                                                   | Low      | M            | Feature       |
| 12 | Re-verify `docs/providers/` pricing drift (quarterly-ish; last pass predates today)                                                                                                                                                 | Low      | M            | Documentation |

## g) Top question

**Which lock strategy should own main — and who owns that call given
two sessions are mid-flight on opposite ones?** I back-pinned to the
proven-green pair (done, local); the sibling session built an assert
shim to move the toolchain forward (committed, unproven through a full
battery, and it forces a ~30-min FreeSWITCH rebuild on EVERY suite
even on the old toolchain). I cannot decide this myself: it trades
"maintain a local FreeSWITCH patch until upstream fixes gcc-16/
glibc-2.44" against "sit on a two-day-old nixpkgs and keep pristine
cache substitution". The answer decides whether T07 relocks onto the
shim-forward lock or keeps my back-pin as the base.

---

_Snapshot per `docs/status/` convention: annotate, never rewrite.
Execution of the remaining plan (T07+) resumes on instruction or on
the g/1 decision._
