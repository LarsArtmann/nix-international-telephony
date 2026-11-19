# Webphone relock to main `b0f53e53b` — ritual report (2026-11-19 20:49)

Session scope ONLY: the owner directive "Make sure we use the LATEST
version of /home/lars/projects/webphone SUPERBLY!" executed as the full
lock-bump ritual from `docs/ops-runbook.md`. Nothing else was researched
or touched. Verdict up front: the relock is COMPLETE and green
(commit `1403650`, local, unpushed); one honest coverage gap was found
during this self-review (the passkey ceremony E2E did not run — §b/§e).

## Ritual ledger (what actually ran, in order)

| Step | What | Verdict |
| ---- | ---- | ------- |
| Session-start ritual | `git status` + stash + lane scan | clean tree, no stash, no nix lanes |
| Runbook read | `docs/ops-runbook.md` "Lock-bump runbook" + gate-5 auth clause | read before acting |
| Delta survey | `cfba725..b0f53e53` = 52 commits, lock-doctor `--target-rev` | surveyed, no upstream CI verdict (expected) |
| Gate-0 prove-before-lock | `nix build github:LarsArtmann/webphone/b0f53e53…#webphone` | GREEN, exit 0 (store path `webphone-2.14.0`) |
| Auth-surface seam scan | `internal/web`/`internal/server` diff, configjs.go, ring.go, selector grep old↔new | no contract moved (details §a) |
| CHANGELOG draft | entry written BEFORE the ladder ran | same-window bookkeeping held |
| Gate 1 relock | `nix flake update webphone` | exact surveyed rev, nothing else moved |
| Gates 2–6 ladder | `scripts/relock-ladder.sh --browser-e2e --full-check` | ALL GREEN (11 rows), logs `/tmp/relock-ladder-20261119-201759` |
| Daemon race heal | heuristic `3657f87` swept my 2 files mid-ritual | verified unpushed + byte-intact → `git reset --soft` → re-authored `1403650` |
| Hooks | changelog-headings, gitleaks, scrub-check, lock-move-guard | all Passed |
| Tip re-check | fetch origin/main after the ritual | still `b0f53e53` (no mid-ritual drift) |

## a) FULLY DONE

- Webphone input relocked `cfba72529` → `b0f53e53b` (52 commits, upstream
  main tip, still the tip at ritual end). Lock diff grepped for
  unsurveyed revs: none.
- Gate 0 built the exact candidate rev green BEFORE the lock moved —
  the zero-daemon-window proof for the broken-sweep class.
- Auth-surface clause executed with real evidence: `configjs.go` +
  `configjs_test.go` untouched; `internal/server/hooks/ring.go`
  untouched (ring wire contract intact); every pinned DOM selector
  byte-count identical old↔new across `.templ`/`.go`/`.js` — login
  (`#login-form`, `#ext`, `#pass`, `#reg-status`, `#toasts`), tabs,
  panels/rows, compose, ended-card (`wp-ended-card`/`close-ended-btn`
  in `island/app/calls.js`), enroll + `lp-` passkey sets; the only
  `internal/server/auth` delta is additive (AccentColor brand ruling +
  a CSP `report-uri`/`report-to` tail on the login page);
  `session_api.go` unmoved.
- Full ladder green: binary-proof, fast-fmt, fast-eval, the six
  gate-4 VM suites (webphone, dynamic-directory, empty-secret,
  textagent, fax, fax-feed — all `--no-eval-cache`, the post-move
  rule), browser E2E (required: `internal/web` non-test files moved),
  full `nix flake check --no-eval-cache`.
- CHANGELOG attribution drafted pre-verification and landed in the
  same commit as the lock move; commit hand-authored with old→new revs,
  delta shape, auth-surface line, and the ladder verdict table — the
  `5f331e6` overclaim class avoided by construction.
- Daemon race handled exactly per protocol (verify unpushed +
  byte-intact, soft-reset, re-author) — no history damage, no lost
  work, hooks green on the authored commit.
- Upstream nix surface triaged: `nix/packages.nix` gained `meta`
  blocks on aux packages only; no module, package, `go.mod`, or vendor
  move in the range.

## b) PARTIALLY DONE

- **Passkey ceremony E2E (`telephony-passkey`) did NOT run.** The
  gate-5 auth clause triggered (files under `internal/server/auth`
  moved) and I completed steps 1–5 of the clause EXCEPT actually
  rerunning the passkey suite: `telephony-passkey` lives in
  `legacyPackages` (runs SOLO, browser rule), so neither the ladder's
  gate 4 nor gate 6 (`nix flake check` sees only `checks`) executed it.
  Mitigations that bound the risk: its pinned selectors and
  `session_api.go` were verified unmoved, the login CSP tail touches
  only the login page (not the enroll surface), and the delta is
  additive. But the suite's green at this pin is INFERRED, not proven.
  → first item in §f.
- Local checkout `/home/lars/projects/webphone` left at `3c775147`
  (behind origin/main) with another session's uncommitted
  `CHANGELOG.md`/`TODO_LIST.md`/`nix/checks.nix`. Correctly untouched
  (not my lane; the flake reads the GitHub remote), but "use the LATEST
  version of /home/lars/projects/webphone" is only true at the FLAKE
  level, not for that working copy.

## c) NOT STARTED (noticed this session, deliberately out of scope)

- pbx-lens relock (lock-doctor: 3 commits behind, `0ecf1c1ee` →
  `8ac47dd55`).
- go-nix-helpers sibling input (118 commits behind default branch).
- Pushing `1403650` (never push without the owner saying so; the
  daemon's push pass will likely carry it).
- webphone deep-dive audit refresh — no trigger fired (version literal
  still 2.14.0, no new tag; trigger is next release tag or an
  ASR/oauth2/CRM decision landing).

## d) TOTALLY FUCKED UP

Nothing. Zero red gates, zero lost work, zero history damage. The one
near-miss class — the daemon sweeping the relock mid-ritual — was the
documented race and the protocol absorbed it. The §b passkey gap is the
session's only honest deficiency, and it was self-caught in this review.

## e) WHAT WE SHOULD IMPROVE

- **The ladder under-covers the auth clause it exists to enforce.**
  `GATE4_SUITES` and the runbook gate-4 row do not mention
  `telephony-passkey`; the gate-5 clause tells you to rerun it, but no
  gate ever will unless a human remembers. The ladder should carry a
  `--passkey-e2e` flag (mirroring `--browser-e2e`) and the runbook gate
  table should name it as the gate-5 sibling.
- **My selector grep almost produced a false alarm** — grepping
  `.templ` only read zeros for five selectors; comparing old↔new across
  `.templ`+`.go`+`.js` was what proved the contract. That comparison
  rule should be written into the gate-5 clause step 3 (it currently
  just says "grep the upstream .templ sources").
- Gate 0 + warm store made gates 2–6 nearly free (~2 min). Worth
  remembering that a warm store is a STORE-STATE delta: a CI rerun of
  the same checks pays full price — no action, but do not cite this
  session's wall-clock as the ritual's cost.

## f) NEXT (session-scoped, honestly bounded — not padded to 50)

1. Run `nix build -L .#telephony-passkey` at the new pin — close the
   §b gap with a real verdict (chromium closure, runs solo).
2. Add a `--passkey-e2e` flag to `scripts/relock-ladder.sh` + a
   gate-4/gate-5 row naming `telephony-passkey` in the runbook.
3. Encode the selector old↔new comparison rule (all three file types)
   into the gate-5 clause step 3.
4. pbx-lens relock ritual (+3 commits) with its own gate-0/ladder.
5. go-nix-helpers sibling-input refresh (118 behind).
6. Push `1403650` (owner or daemon lane — see §g Q1).
7. On the next webphone release tag: refresh
   `docs/research/2026-11-14_webphone-deep-dive.html` (78/100-era
   rules; check whether the stale-agent fix and audio unlock change any
   capability rows).
8. Triage upstream's new `scripts/check-catalog-contract.py` (164
   lines, CI wiring commit `2a46a9c6`): does OUR catalog exporter need
   the same frontmatter-contract validation to stay hub-clean?
9. Check whether upstream `internal/server/platform/metrics.go` (+16)
   grew metric keys this stack's `webphone.metrics.islandBeacon` /
   scrape arm should consume.
10. Verify the login-page CSP `report-uri`/`report-to` tail does not
    affect the theme FOUC slice on the NEXT markup delta (add to the
    gate-5 mental list; the full browser E2E this session was green).
11. Owner decision replay (from the standing audit, unchanged this
    session): ASR "local or none", Kith machine token, G1 whispercpp
    flip.

## g) QUESTIONS FOR THE OWNER (cannot be answered from this tree)

1. **Push authority:** should I push `1403650` to origin now, or leave
   the push to the daemon's next pass? (I never push unprompted; but
   until it lands, Forgejo-mirror consumers — including the catalog
   hub — cannot see the new pin.)
2. **The webphone repo's uncommitted lane** (`M CHANGELOG.md`,
   `TODO_LIST.md`, `nix/checks.nix` at `3c775147`): an active sibling
   session's WIP or abandoned? This decides whether that checkout may
   be fast-forwarded to `b0f53e53` or must be left alone.
3. **Passkey suite as standing ritual cost:** adding
   `telephony-passkey` to every relock ladder means a chromium-closure
   build per ritual — pay it on every auth-adjacent relock (my
   recommendation), or only when the clause's seam scan hits?
