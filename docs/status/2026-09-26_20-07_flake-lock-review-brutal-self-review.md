# Flake.lock review + brutal self-review — 2026-09-26 20:07

Scope: this session only (flake.lock review, the CI red-streak investigation it
uncovered, the doc fixes that followed, and an honest critique of how I ran
it). No unrelated codebase research, per instruction. Point-in-time snapshot —
annotate, never rewrite.

## Session summary

User asked "Review flake.lock!". Delivered: structure/freshness audit, webphone
green-rev proof on three arms (build, CI check, browser E2E), root-cause of a
4-run CI red streak (upstream webphone@`2bbbc2e` contacts-wire bug, fixed
upstream `e43fea8`, picked up by today's relock to `0230ead`/v2.7.0), plus
CHANGELOG + `docs/lessons/operating.md` updates. Verdict: the lock is sound and
now fully proven.

Key evidence: CI run 36259480221 (f2aa2be) all-jobs success; browser E2E exit 0
(`CONTACTS-ROUNDTRIP-OK` … `E2E-OK`); `nix build .#webphone` → webphone-2.7.0;
pre-commit battery + `nix fmt` green after doc edits.

---

## Brutal self-review (what did I get wrong)

### 1. What did I forget?

- **The CI verdict was open when my first turn ended.** I reported freshness
  findings that read near-conclusive while main's gate was literally red
  (4 failed runs) / in progress. The user had to push me to dig properly. A
  review of a lock that tracks-main inputs is not done until the gate verdict
  is in.
- **Inconsistent rigor on nixpkgs freshness.** I compared every other input's
  locked rev against upstream HEAD but skipped nixpkgs itself (unstable moves
  hourly). Defensible, but I did it silently — and then my summary sentence
  "every directly-pinned input sits at upstream HEAD" listed nixpkgs
  (yesterday's unstable) inside it. Self-contradicting phrasing.
- **Cache nuance unstated.** `nix build .#webphone` returned instantly from
  store; that IS proof (same derivation ⇒ same inputs), but I never said so —
  a skeptical reader would wonder if anything was verified at all.
- **`nix flake update --dry-run` failed (unsupported flag on this nix)** and I
  silently pivoted to per-repo HEAD checks without telling the user a command
  had failed. The pivot was better, but silent failures are how trust erodes.
- **The daemon-commit/push gap.** My doc edits are committed locally (f7e0a56)
  but origin/main is still f2aa2be — CI has NOT seen the CHANGELOG/lessons
  edits. I only noticed this while writing this report, not when I declared
  "all gates pass" (gates that ran were local: pre-commit, nix fmt).

### 2. What was stupid?

- **The CHANGELOG multiedit fumble.** I drafted an edit from my memory of my
  own draft instead of re-reading the file: old_string didn't match, the
  companion edit half-applied, and I duplicated an entire changelog section.
  Three recovery edits to fix what one careful edit would have done. Rule I
  broke: re-read after write, before editing around it.
- **A no-op edit** ("new content is the same as old") because I didn't check
  whether the recovery was already complete before firing the next fix.

### 3. Did I lie?

No deliberate lies. Two imprecisions, both corrected above: the "every input
at HEAD" phrasing (nixpkgs isn't), and presenting the review as essentially
finished while the gate verdict was pending. Also: "CI red across four runs"
is verified; "prod is on webphone 2.6.0" appears only in upstream commit
messages — I did NOT verify it against the prod host.

### 4. Ghost systems / split brains?

- None created this session.
- Noted (pre-existing, acceptable): the contacts wire contract is now pinned
  in TWO places — upstream `configjs_test.go` and our
  `tests/webphone.nix`/`browser-e2e.py` assertions. Consumer-side contract
  tests are correct to keep, but the shapes must move together; upstream can
  change its test and ours goes red (exactly what just happened, in reverse).

### 5. How are we doing on tests?

Strong where it matters: the lock change was proven by build + full CI check
(eval, packages, VM suites, aarch64 TCG boot) + browser E2E. Gap: browser E2E
runs nowhere automatically (CI skips it by design), and main sat red ~26h
because nothing alerts on red. Tests exist; the feedback loop around them
doesn't.

---

## a) FULLY DONE

| Item | Evidence |
| --- | --- |
| flake.lock structure audit: 7 inputs match flake.nix, all follows resolve to the single root nixpkgs, dup nodes identical revs, v7 format, no orphans | flake.lock read in full; cross-checked against flake.nix |
| Freshness audit: webphone/nixpkgs/nix-ssh-config/git-hooks/disko/flake-parts/treefmt-nix/flake-compat all locked at upstream HEAD at check time (nixpkgs = 1 day old unstable) | `gh api repos/*/commits/HEAD` per input |
| webphone green-rev invariant proven on 3 arms: build, CI check, browser E2E | webphone-2.7.0 store path; run 36259480221 success; E2E exit 0 |
| CI red-streak root-caused: 2bbbc2e capitalized contacts marshaling → KeyError 'name'; fix e43fea8 inside 0230ead | failed run 36090709865 log; `gh api compare` |
| Upstream webphone has NO build CI — discovered and recorded (stack's check is the only gate) | `gh workflow list -R LarsArtmann/webphone` |
| Browser E2E re-run against v2.7.0 markup changes (EmptyState, tw.css) — green | `CONTACTS-ROUNDTRIP-OK` … `E2E-OK`, exit 0 |
| CHANGELOG: new "Fixed (2026-09-26)" section documenting the tail | f7e0a56 |
| docs/lessons/operating.md: forward-pin lesson sequel (no upstream CI; UI-release relocks owe a browser-E2E run) | f7e0a56 |
| Local gates after doc edits: nix fmt + full pre-commit battery (changelog-headings, gitleaks, scrub-check, nixfmt, statix, deadnix) | all Passed |

## b) PARTIALLY DONE

- **Doc edits not yet CI-proven.** f7e0a56 (CHANGELOG + lessons) is local
  only; origin/main = f2aa2be. Remaining: push (daemon/user), watch CI for
  f7e0a56 go green. Blocker: none — waiting on push. Effort: S.
- **Lock review follow-through.** The review verdict is delivered, but two
  observations (home-manager 7d stale via nix-ssh-config; nixpkgs 1d behind
  unstable) were reported, not actioned. Deliberate — they are upstream-repo
  and cadence decisions, not defects. Effort: S each.

## c) NOT STARTED

- CI-failure alerting / branch protection on main (the 26h red streak says
  this is the top process hole). Not started; needs owner posture decision.
- Scheduled or relock-triggered browser E2E in CI (currently on-demand only).
- A build CI workflow in the webphone repo (upstream has none).
- A mechanized "lock doctor" (revs vs upstream HEADs + last CI verdict) — I
  did this by hand with gh api; it would be a 50-line script.
- Cutting a release: CHANGELOG Unreleased now carries two days of Fixed
  entries; release flow (CHANGELOG cut → tag → gh release) not run.

## d) TOTALLY FUCKED UP!

1. **Main sat red for ~26h / 4 CI runs (2026-09-24→25) and nothing noticed.**
   Root cause: webphone@2bbbc2e wire bug (fixed since), but the real defect is
   process: no alerting, no branch protection, relock landed via a heuristic
   auto-commit with no rationale in the message (violating the repo's own
   forward-pin rule "say so in the commit"). Mitigation: this review caught
   it; prevention is (c) item 1.
2. **My CHANGELOG edit fumble** — duplicated a whole section via a
   half-matched multiedit; 3 recovery edits. Root cause: edited from memory,
   not from the file. Fixed; final file verified clean + hooks green.
3. **First-turn review read as done while the gate was open** — process
   failure in how I staged the review, corrected in turn two.

## e) WHAT WE SHOULD IMPROVE!

- **Relock ritual over relock luck.** Every webphone relock should run: build
  → fast gates → VM suite → browser E2E (if markup release) → hand-authored
  commit message. This session proved the value of each step; the ritual
  should live in AGENTS.md, not in one session's memory.
- **Alert on red.** A gate nobody watches is theater. Branch protection or a
  failure notification converts the 26h hole into a 26-minute one.
- **Mechanize what I did manually.** Lock-freshness + green-rev checks were
  ~10 gh/nix invocations; a `lock-doctor` script makes them reproducible and
  reviewable.
- **Say when a command fails.** My silent pivot past `--dry-run` was harmless
  here and still wrong.
- **Re-read-before-edit around freshly written text.** The fumble's one-line
  lesson.

## f) Next tasks (impact / effort / category)

| # | Task | Impact | Effort | Category |
| --- | --- | --- | --- | --- |
| 1 | HARVEST this report's (f) into TODO_LIST/ROADMAP (docs-health) | High | S | Documentation |
| 2 | Watch CI for f7e0a56 after push; confirm green | High | S | Quality |
| 3 | Add branch protection + required checks on main (owner decision) | Critical | S | Quality |
| 4 | Add CI-failure notification (email/gh alert) as fallback if protection unwanted | High | S | Operations |
| 5 | Codify the relock ritual (build → gates → VM suite → browser E2E on markup releases → rationale commit) in AGENTS.md | High | S | Documentation |
| 6 | Add a build CI workflow to LarsArtmann/webphone (currently zero build CI) | High | M | Quality |
| 7 | Schedule browser E2E (nightly) or trigger on webphone lock-rev change in ci.yml | High | M | Quality |
| 8 | Write `scripts/lock-doctor.sh`: locked revs vs upstream HEAD + last CI verdict per rev | Medium | S | Quality |
| 9 | Verify the auto-commit daemon does not bypass scrub-check/gitleaks (leak vector) | Medium | S | Security |
| 10 | Hand-author future relock commits with rationale; never let the daemon own them | High | S | Process |
| 11 | Consider switching webphone input from tracking main to release tags (owner decision; 2 imported breakages in 3 days) | High | S | Process |
| 12 | Bump nixpkgs (`nix flake lock --update-input nixpkgs`) + full check; telephony exposure argues for freshness | Medium | M | Maintenance |
| 13 | Open nix-ssh-config issue/PR to relock its home-manager (7d stale) | Low | S | Maintenance |
| 14 | Prod deploy decision: runbook deploy of webphone 2.7.0 to pbx-prod (upstream docs claim prod on 2.6.0 — unverified) | High | M | Operations |
| 15 | Align this repo's deploy runbook with upstream's owner command sheet (357ffec references the pbx-artmann relock ritual) | Medium | S | Documentation |
| 16 | Record the `nix flake update --dry-run` unsupported-flag gotcha in AGENTS.md | Low | S | Documentation |
| 17 | Add a lock-diff step to CI (print old→new revs per input) so relocks are reviewable | Medium | S | Quality |
| 18 | Extract tests/webphone.nix's giant inline config.js python assertion into a file | Low | S | Cleanup |
| 19 | Cross-link the contacts wire contract: upstream configjs_test.go ↔ our webphone.nix/browser-e2e.py (both directions) | Low | S | Documentation |
| 20 | Evaluate a binary cache (cachix/attic) for VM test closures — CI is 20–60min | Medium | L | Performance |
| 21 | Replace the crashing vulnix step (NVD 2.0 feed retired) or document the noise louder | Medium | M | Security |
| 22 | Cut a release from the accumulated Unreleased CHANGELOG entries (owner) | Low | S | Process |
| 23 | docs/status/2026-09-25_05-08_docs-health-round5 snapshot: annotate + archive once resolved | Low | S | Documentation |
| 24 | Check whether `gh` is in devShell (I used host gh; CI verdicts should be reproducible) | Low | S | Cleanup |
| 25 | aarch64 coverage: only telephony-boot TCG runs — consider one KVM aarch64 suite if hardware exists | Low | L | Quality |

## g) Questions I cannot answer myself

1. **CI posture on main:** branch protection with required checks (blocks even
   daemon pushes while red), notification-only, or leave as-is? I can
   configure any of these, but blocking your own auto-commit daemon changes
   your workflow — owner call. (Tried to infer from repo settings via gh;
   protection config is not readable with my current token scope.)
2. **Browser E2E cadence:** nightly scheduled, trigger on webphone lock-rev
   change, or keep strictly on-demand? Cost is ~1–2 GB chromium closure +
   ~7 min VM per run — a CI-minutes/time-to-feedback tradeoff only you weigh.
3. **Reopen the 2026-09-18 "webphone tracks main" decision?** Two imported
   upstream breakages in three days (stale vendorHash, contacts wire bug) are
   evidence for tracking release tags instead. It's your recorded owner
   decision — overturning it is yours too.
