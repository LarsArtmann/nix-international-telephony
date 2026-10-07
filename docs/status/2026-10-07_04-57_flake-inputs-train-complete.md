# Flake-Inputs Remediation Train — COMPLETE (M01–M08 all landed)

Session: 2026-10-07 ~02:15→04:57 CEST. Continuation of
`2026-10-07_02-11_flake-inputs-remediation-train-status.md` (read that
for the ritual-detail backlog; this report closes it out).

Train head: `b578c2e` (pushed). The plan:
`docs/planning/2026-10-07_00-38_SUPERB-flake-inputs-remediation-pareto-plan.md`.

## a) What I actually got done (no fucking around)

- **Environment triage on resume**: hooks were MISSING (only `.sample`
  files — the battery had vanished, tripwire disarmed) → healed both
  stages via `scripts/heal-pre-commit-hook.sh` BEFORE the ritual wait.
  Daemon had already pushed the whole train (`e72d54e`…`c524985`) and
  swept the 02:11 status report (`0deda04`).
- **Stash forensics**: the handoff's "expect clean pop" held — the
  stash's own delta vs base `98323e2` was exactly `CHANGELOG.md` +
  `TODO_LIST.md` (row-21 deletion); no commit since the base touched
  either. Pre-verified lock-guard + drift-alarm against stash copies
  BEFORE popping.
- **M02 browser E2E retry — honest green**: armed a detached
  (nohup+setsid) load-gated runner. A machine REBOOT at 02:51 (3rd
  boot that night) killed the first attempt and wiped /tmp (log,
  script, message drafts). Re-armed durable (`~/.cache/e2e/`), load
  11.2 → build ran 02:59→03:03 (cached steps), **EXIT=0,
  CONTACTS-ROUNDTRIP-OK present as the suite's own
  `waiting for success` assertion, flanked by server-side
  /partials/contacts + /contacts/save + /contacts/delete 200s**. Log:
  `~/.cache/e2e/browser-retry.log`.
- **M02 landed**: stash pop (clean), lock-guard PASS, drift PASS,
  hand-authored `relock:` commit **`86f3d3d`** — full battery green
  (changelog-headings, gitleaks, scrub-check, lock-move-guard).
- **M06 capstone**: BuildFlow `--build-mode full --max-time 60m` ended
  at the findings gate with **EXACTLY the four documented nix-checker
  port-collision errors** (443 pair at `hosts/pbx/default.nix:121` +
  `modules/telephony/security.nix:51`; NAT tcp+udp sourcePort pair at
  `tests/nat.nix:85`) — the documented green shape. Pushed `86f3d3d`
  ahead of buildflow (parallelized; doc-only delta on a green tree).
- **Origin CI GREEN**: run **`37555437689`** on `86f3d3d` — push
  event, x86_64 "nix flake check (eval, packages, VM test)" +
  aarch64 telephony-boot both success (53m13s) — **the first fully
  green run since the lock went red**. Before-evidence: `37552875317`
  on `9b9a1c0` failed on lock-guard (the honest pre-M02 gate).
- **M06 landed**: research HTML append-only addendum (section 06 +
  TOC link; splice via anchored script, `assert`-guarded),
  browser-rendered after edit: **0 page errors, all tags balanced**
  (store-path chromium). Daemon swept the HTML mid-ritual (`7542594`)
  → unpushed → soft-reset + re-authored per protocol → **`79a7b15`**
  (addendum + TODO row-22 deletion, full verdict in the message).
- **M08 landed**: TODO truth pass — deleted the stale kill-ledger row
  ("land a green CI verdict": its remaining clause died with the
  `c19bdea` root-cause; the eval-split mitigation it proposed is
  landed and green); CHANGELOG [Unreleased] gained the train's
  gate-hardening record (M03–M05 had none); AGENTS.md gained the
  statix-warning accepted-remainder note. **All four doc gates PASS**
  (markers, drift, lock-guard, changelog-headings) → **`b578c2e`**.
- Earlier-session AGENTS.md truth-ups (battery members, treefmt
  programs) landed via daemon sweep `9b9a1c0` (content verified).

## b) Partially done (be honest)

- **CI at the final head**: runs `37560299655` (`79a7b15`) and
  `37560417056` (`b578c2e`) were still in flight at report time
  (~51 min, aarch64 green, x86_64 grinding — identical shape to the
  green M02 run). Doc-only deltas ahead of a green SHA; expected
  green. The train's CI-green obligation is discharged by
  `37555437689`; these two would make the HEAD airtight too.
  → done 05:05: run `37560417056` on `b578c2e` completed SUCCESS
  (57m22s) — the train head is CI-green at origin.

## c) Not started

- Q3: v0.3.0 release cut (owner timing; TODO row stands).
- Optional docs-health pass: annotate the 02:11 snapshot + the plan
  file (per markers convention) toward archival.
- vulture whitelist restoration + ruff cosmetics (declared
  out-of-train scope, see d/e).

## d) What I totally fucked up (nothing hidden)

- **Put session-critical artifacts in /tmp on a machine that had
  already rebooted twice that night.** The 02:51 reboot ate the
  runner, its log, and both message drafts. ~30 min lost plus a
  confused diagnosis (impossible loadavg math) before `who -b`
  settled it. Fix: durable paths from minute one.
- **Stash scare**: my first stash diff (vs working tree) made the
  stash look like it contained 9 files; the correct canonical check
  (delta vs `stash@{0}^1`) came second. Cost: one diagnostic round,
  zero damage.
- Minor waste: a jq syntax error, a grep-exit-1 misread as failure,
  chromium-not-on-PATH (127) before finding the store path.

## e) What I'd do differently / improve

1. Durable session paths (`~/.cache/...`) from the start on
   reboot-prone hosts.
2. Stash forensics: diff against the stash BASE first, always.
3. Daemon race windows: pre-write commit messages; commit the moment
   a file is verified (the addendum sweep window existed only because
   render-check + TODO edit preceded the commit — inherent, but
   minimizable).
4. `buildflow doctor` follow-up for the "9 tools unavailable (health
   check failed)" line I noted but never drilled.
5. E2E runner as a systemd user unit (self-rearms after reboot; this
   session I supervised manually).
6. vulture-clean (a DECIDED state) regressed pre-train: 3 findings
   (`_fallback_line`, `EndToEndCallSpec`, `EntrypointSpec`) — 3-line
   whitelist fix or deletion, plus `chmod +x` for the EXE001 class.

## f) Next things (a realistic 50-lane backlog, unpadded)

Owner/deploys: 1 first-real-deployment close-out (webhook PATCH,
AAAA, §5 checklist, first calls+CDR, trunk hardening, security
pass); 2 cut v0.3.0; 3 fspbx trial verdict + execute; 4 Warsaw DID
re-purchase + 5 KYC items, then DE national DID; 5 rotate Telnyx API
key + scrub KEY pattern; 6 fill/delete 3 scrub-patterns OWNER
placeholders; 7 GitHub residual exposure (support GC + Dependabot
audit); 8 global `core.hookspath=.githooks` landmine fix;
9 sops-nix example host; 10 WhatsApp live verification (portal
signup, VOICE OTP, real round trip); 11 CDR cancelled-while-ringing
live-host reproduction; 12 Master.csv cancelled-A-leg live check.

CI/gates: 13 branch protection + failure notification on main;
14 promote browser E2E CI off manual dispatch (lock-rev trigger);
15 watch for the first REAL daemon lock move vs the tripwire (sweep
#6 = the live proof); 16 verify the flake-update bot's next PR skips
webphone cleanly; 17 delete stale `chore/flake-update-2026-09` origin
branch; 18 x86_64 job at ~53 min green — split VM suites if it
drifts toward the 60-min step budget; 19 aarch64 TCG duration watch;
20 flake-meta-checker mainProgram policy; 21 buildflow doctor for
the 9-unavailable-tools warning; 22 upstream git-hooks.nix#754
(non-convergent healing — bit us again at session start).

Repo hygiene: 23 annotate 02:11 snapshot → archive; 24 annotate plan
snapshot per markers convention; 25 vulture whitelist/EXE001 fixes;
26 `buildflow -s ruff-format --fix` for the 11-file py drift;
27 commit the E2E retry evidence excerpt somewhere durable-in-repo;
28 sweep #6 source hunt (auditd/shell history) if owner reopens Q2;
29 research-HTML visual check in a real browser (DOM-level only so
far); 30 formal deep-dive scorecard update if owner wants the
post-train scores re-derived.

## g) Questions (I could not figure these out myself)

1. **v0.3.0 timing**: cut now (train + gate hardening ride the
   release) or after the deployment close-out lane?
2. **Row-37 deletion**: I closed the kill-ledger row as
   resolved-dead-premise (GitHub-support lane dead per the `c19bdea`
   root-cause). Confirm, or file the support ticket anyway?
3. **Snapshots**: run the annotate/archive pass over the 02:11 report
   - plan file now, or leave them point-in-time?
