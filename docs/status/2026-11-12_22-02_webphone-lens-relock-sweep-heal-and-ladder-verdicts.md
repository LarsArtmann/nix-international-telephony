# The webphone + pbx-lens relock: sweep healed, ladder green, daemon raced the commit

> Claims verified as of 2026-11-12 22:02 CET, from THIS session's run only
> (18:26–19:35 relock ritual, plus a 22:00 verification pass). Verified
> with: `scripts/relock-ladder.sh --browser-e2e --full-check` verdict
> table (logs in `/tmp/relock-ladder-20261112-183047`), gate-0
> prove-before-lock build at the exact rev, the `telephony-lens` VM build,
> `nix flake check --no-eval-cache` (all checks passed), standalone
> `scripts/lock_guard.py` PASS, and `gh run view/list` for origin CI
> state. NOT verified: the origin CI verdict at the CURRENT head
> `2b2e578` (run in progress at report time — a local green is tier
> suite-green, not the airtight origin verdict); deployed-host pin state
> (invisible from this repo); upstream webphone tags past `v2.14.0`.

## a) FULLY DONE

- **webphone relock to main HEAD**: `c211d42fe952` → `2847fe1d2c1c`.
  Gate-0 prove-before-lock built the exact rev green BEFORE the lock
  moved (store path `webphone-2.14.0`, `NIX_EXIT=0`) — zero daemon
  window on an unproven rev.
- **Full gate ladder green**: binary-proof, fast-fmt, fast-eval, all six
  webphone VM suites (webphone, dynamic-directory, empty-secret,
  textagent, fax, fax-feed) GREEN; `telephony-lens` GREEN; gate-6
  `nix flake check --no-eval-cache` GREEN ("all checks passed").
- **Browser E2E (gate 5)**: RED once under the documented theme-FOUC
  flake signature (stalled past `THEME-THROTTLE-ARMED` at host load
  122 — the multi-project build storm), GREEN on retry
  (`THEME-CHECK-DONE`, script finished 364.7 s). Exonerated per the
  runbook's flake-signature clause; the data point landed in
  `docs/ops-runbook.md` (stall is storm-shaped, not load-magnitude-
  gated — retry green even through a transient load-1017 spike).
- **pbx-lens confirmed at upstream HEAD**: `5d777f3e68f8` (lock-doctor
  "up to date"); the relock update proved a no-op (only the webphone rev
  line moved in `flake.lock`); VM-proven by `telephony-lens` this
  session, not just by the aarch64 CI boot job.
- **The `641ccbe` sweep healed**: CI on `641ccbe` was red on
  `checks.lock-guard` ONLY (both tracked inputs' current revs
  unattributed). The CHANGELOG entry now names webphone
  `2834810ea06d` → `c211d42fe952` (daemon sweep) → `2847fe1d2c1c`
  (deliberate) and pbx-lens `27fd19a72355` → `5d777f3e68f8` (same
  sweep pass). Standalone `lock_guard.py` PASS ("tracked inputs
  attributed: webphone, pbx-lens").
- **Auth-surface clause executed**: seam scan (the auth delta is a
  re-homing carve — `session.create`/`session.switch` wire shapes and
  the one-credential-field contract unchanged), `/config.js` keys
  `phoneApi`/`crm`/`agent` present at the new
  `internal/server/platform/configjs.go`, ended-card selectors
  `wp-ended-card`/`close-ended-btn` present in
  `island/app/calls.js`, login DOM selectors intact. No contract moved;
  one line recorded in the relock commit.
- **Hand-authored attribution commit `1fca8f9`** landed with the full
  pre-commit battery green (changelog-headings, gitleaks, scrub-check,
  lock-move-guard). The lock move itself was swept by the daemon race
  (heuristic `88a6157`, byte-intact — flake.lock + the pre-drafted
  CHANGELOG entry); `1fca8f9` completes the attribution with the real
  verdicts, per the house heal pattern.

## b) PARTIALLY DONE

- Origin-CI airtight tier for the relock train: the train is PUSHED
  (`origin/main == HEAD == 2b2e578`), but the current head's CI run was
  in progress at report time. Two intermediate heads (`3a5ddd8`,
  `174daf3`) went red on `checks.format`/`checks.treefmt` — the
  sibling lane's nixfmt bytes (their own fix commit `2b2e578`
  "style(nixfmt): the caddy-failregex block's canonical bytes"
  addresses exactly that), NOT a relock surface. → open until the
  `2b2e578` run lands green.
- The post-sweep ritual (2026-11-10 lesson: re-heal snapshots by append
  + diff the lock against the last gate-proven commit) for the
  `641ccbe`/`88a6157` sweeps: attribution healed and markers-check green
  inside the full check, but the ritual was not run as a NAMED
  two-check pass. → routed (covered by gates, not by ritual)
- This report's §f harvest into `TODO_LIST.md`/`ROADMAP.md`: not done
  (the session was told to report and wait). → open

## c) NOT STARTED

- Nothing in the relock task scope itself is unstarted — every gate in
  the runbook's ladder ran to a verdict. The deferred items live in §f.
  → open (by instruction: report, then wait)

## d) TOTALLY FUCKED UP

- **The `| tail` exit-code slip**: gate 0's first run was piped
  (`nix build … | tail -5; echo "EXIT=$?"`) — `$?` captured tail's exit,
  not nix's. This is the EXACT documented anti-pattern (the 2026-10-07
  battery discipline). Self-caught one step later and re-proven with
  redirect-then-`$?`; no verdict rode on the broken probe. But the slip
  happened on the gate whose entire purpose is verdict integrity.
- **Browser E2E launched INTO a visible storm**: load was already ~90+
  (sibling lanes visible at session start) when the ladder started; the
  runbook documents the theme check's load sensitivity. Cost: one red
  gate, ~7 min timeout, plus exoneration overhead. The calm-window
  retry should have been the FIRST move, not the remediation.
- **The daemon race was not anticipated**: third documented recurrence
  of a mid-ritual lock move landing in a heuristic commit
  (`aceaf598`, `641ccbe`, now `88a6157`). The relock sat unauthored for
  ~70 min while the ladder ran. Heal worked; anticipation would have
  been cheaper (see §e).
- **Skipped the base-attribution arm** of the gate-5 clause (prove the
  suite at the pre-relock base). Reasoned exemption: the retry went
  GREEN at the new pin, which trivially exonerates the relock — the
  base proof exists for a PERSISTENT red. Documented deviation, not
  silent; still a deviation from the letter of the runbook.
- House-level, observed this session: CI ordering burns ~55 min before
  `checks.lock-guard` reports its red (cheap gates run last); and the
  daemon lane remains structurally unguarded for lock moves (owner
  lane, pma/go-commit).

## e) WHAT WE SHOULD IMPROVE

- Order cheap verdict-first gates (lock-guard, format/treefmt) before
  the VM battery in CI — two origin reds this evening took 50–55 min to
  report failures a 30-second gate could have named.
- Harden the browser E2E theme leg against storms: either an in-suite
  single retry, or a host-load probe that defers the rAF-sampling leg
  (the flake now has two dated recurrences: 2026-10-05 at ~91, today at
  122; both exonerated, both expensive).
- Close the relock→commit window structurally: either the owner-lane
  daemon guard (lock-move marker inside pma/go-commit) or a ritual
  change — commit lock + pre-drafted entry immediately after gate-2
  binary proof, complete verdicts in the SAME-ENTRY follow-up commit.
- Always run `lock-doctor.py --target-rev <candidate>` as pre-flight
  (this session surveyed HEAD manually — same result, more steps).
- Honor the report-harvest loop: §f of every status report belongs in
  `TODO_LIST.md`/`ROADMAP.md`, not entombed here (this report included).
- Keep the positive discipline from this session: gate-first after
  edits, `--no-eval-cache` on every post-move suite, verdicts written
  only after they exist, hand-authored commits for every lock move.

## f) NEXT (core first, then brainstorm tier)

1. Watch the `2b2e578` CI run to its verdict; if red on a non-format
   surface, run the full attribution protocol before touching anything.
   → open
2. Harvest this report's §f into `TODO_LIST.md` (core items) and
   `ROADMAP.md` (brainstorm tier). → open
3. Sibling lane ownership: the lens native-login + web.edge external
   mode work (`3a5ddd8`, `576bc08`, `879c367`…) — their gates and
   attribution, not this session's. → routed (sibling session)
4. lock-doctor full pass: `home-manager` child (nix-ssh-config) 319
   commits behind — the runbook's recursive-update lane (`nix flake
   update nix-ssh-config/home-manager`), overdue per the monthly rule.
   → open
5. Same lane: `flake-parts_2`/`flake-parts_4` (6/3 behind, dedupe-able
   onto root pins) and `treefmt-nix_2` (127 behind) child refresh.
   → open
6. Confirm `go-nix-helpers` (pbx-lens child, 1 behind) stays
   upstream-pinned per the runbook rule — re-read that rule at the next
   lock-doctor pass. → open
7. Check upstream webphone tags: if a tag past `v2.14.0` exists, decide
   tag-pin vs ride-main for the next relock (the tag-pin discipline the
   v2.14.0 release dance set). → open
8. Browser E2E theme-leg hardening (§e item 2) — in-suite retry or
   load-defer. → open
9. CI gate ordering: cheap verdict-first (§e item 1) in
   `.github/workflows/ci.yml`. → open
10. Daemon lock-move guard: file/forward the owner-lane item (pma
    go-commit hook) if not already tracked. → open
11. Relock-ritual window: propose the gate-2 checkpoint-commit variant
    in the runbook's commit-convention section. → open
12. Deployed-host pin audit: any prod host on a pre-v2.14.0 webphone
    pin needs the `docs/deploy.md` §6 Day-2 hop check before pulling
    this relock (the cross-release-hop warning). → open (needs owner
    knowledge, see §g)
13. Live-vhost ringhook consumption verdict (the push-seam observation
    debt AGENTS.md carries). → open
14. Upstream webphone: watch whether the DE locale / views restructure
    triggers a webphone deep-dive audit refresh trigger (the audit's
    refresh conditions). → open
15. The unattributed-sweep instrumentation incident class: this session
    saw TWO more sweeps land unattributed (`641ccbe` pre-session,
    `88a6157` mid-ritual) — the per-process audit instrumentation
    (auditd/nix wrapper) remains the only durable fix. → open
16. Brainstorm tier: pre-commit the CHANGELOG draft entry as a repo
    convention artifact (a template block) so daemon sweeps carry
    attribution payload by default.
17. Brainstorm tier: `nix flake update` wrapper in the devShell that
    refuses tracked-input moves without a marker file present.
18. Brainstorm tier: teach lock-doctor to emit the CHANGELOG entry
    skeleton for a candidate rev pair automatically.
19. Brainstorm tier: gate-5 clause could name the exact retry protocol
    (defer window, max retries) instead of prose "after load subsides".
20. Brainstorm tier: a `checks.browser-e2e-flake-baseline` documenting
    the two recurrence data points so a third recurrence triggers a
    hardening decision instead of another exoneration.

## g) QUESTIONS (cannot be answered from this repo)

1. **Deployed hosts**: does any production host still pin a
   pre-v2.14.0 webphone rev? If yes, it needs the Day-2 hop recipe
   before pulling this relock — deployment state is invisible from
   this tree.
2. **Daemon policy**: is the heal pattern (heuristic commit carries the
   lock move, hand-authored follow-up completes attribution) the
   accepted permanent shape, or should the pma/go-commit guard work
   move up the owner queue? Three recurrences now.
3. **Prioritization**: harden the browser theme leg now (in-suite
   retry/load-defer — suite runtime cost) versus keeping the documented
   flake-signature clause as the only defense (zero cost, occasional
   expensive exoneration)? Both defensible; it is your call.
