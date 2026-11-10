# Handoff closeout session — three sweep incidents, gate-5 base attribution, the ladder's first real run

_Point-in-time snapshot, 2026-11-10 15:36 CET. Annotate, never rewrite — when stale, route corrections inline per the marker convention. This report covers ONLY the 2026-11-10 closeout session (following the morning's relock session, `docs/status/2026-11-10_09-23_webphone-relock-voicemail-range-ladder-and-child-inputs.md`); it does not re-derive that session's facts._

## Run sheet (what happened, in order)

| Time (CET)   | Event                                                                                                                                                                                                                                                                                                                                                       |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ~09:45       | Session start: ritual clean, 5 unpushed commits, todo reconciled to the handoff                                                                                                                                                                                                                                                                             |
| 09:52        | f8: hereditary `markers_check` red (7 findings) healed by append in both archived snapshots (daemon raced, amended → `2a362a8`)                                                                                                                                                                                                                             |
| 10:00        | f9: `markers-history` CI job added (`fetch-depth: 0`, actionlint-clean, local command reproduced green) → `c46c421`                                                                                                                                                                                                                                         |
| ~10:05–11:00 | f5: through-vhost Range assertion written → RED (placement: the suite's own delete drill empties the mailbox first) → moved before the drill → RED again (header-case-sensitive asserts) → case-insensitive + full-response dump + no-`re` fix → **GREEN** (daemon carried the edits across `748e3ce`/`4df7f7f`)                                            |
| ~10:20       | f2 source verification: all four delta claims confirmed at pin `2c2cc950` (proxy Range forwarding + `Accept-Ranges`/`Content-Range` passthrough, `shell.js` toast, Tailwind v4.3.4 artifact headers, `webphoneVersion = "2.12.0"`); the three parked audit leads disproven at source in this tree                                                           |
| ~10:45–13:30 | f1 base attribution: worktree at `19788cd`; browser E2E at the OLD pin — run 1 GREEN 398 s, run 2 RED 850 s under load ~27 (`data-dial buttons survived logout: 1`, after wss 1006 churn)                                                                                                                                                                   |
| 13:51        | **Sweep #1 lands (`268c091`, daemon, pushed by the daemon lane):** symmetric 66/66 formatter churn re-scrambles both archived snapshots' markers AND moves `flake.lock` — three child inputs reverted to pre-refresh pins, webphone forward-jumped to ungated `41eab05d`                                                                                    |
| ~13:55–14:58 | Sweep #1 response: lock restored to the `bd3c0e4` gate-proven state, both snapshots re-healed (one off-by-one marker caught by the gate and fixed), gate-0 build of the swept rev run for the record (GREEN, `webphone-2.12.0`, zero integration verdicts), full attribution in the CHANGELOG → squashed to hand-authored `8dd37ea`; f4 lessons → `28e1a74` |
| 14:58–15:04  | f7: **the fixed ladder's first real run** (`--browser-e2e --full-check --keep-going`): all 11 gates exit 0, verdict table printed, `LADDER_EXIT=0` (tree pinned at `28e1a74`, warm store — recorded honestly)                                                                                                                                               |
| 15:16        | **Sibling lane relocks webphone `2c2cc950` → `d537ed73`** (`ad841c4` lock + `7e1bcec` CHANGELOG draft, daemon-carried): landed mid-session, no gates run on it as of session end; my ladder verdicts explicitly exclude it                                                                                                                                  |
| 15:27        | f7 markers + audit-row shrink committed (daemon raced, amended → `21bf9c2`)                                                                                                                                                                                                                                                                                 |
| 15:31        | **Sweep #2 lands (`3ae07bf`):** f:1 cell dropped a FIFTH time, children reverted AGAIN, webphone re-pinned from `d537ed73` to yet another ungated tip `6936be2a`                                                                                                                                                                                            |
| ~15:32–15:35 | Sweep #2 response: lock restored to the `8dd37ea` gate-proven state, cell healed with a dated record, gates re-green (lock + cell rode the daemon's `91fa748`; my CHANGELOG attribution → `739f4a8`)                                                                                                                                                        |
| 15:36        | This report                                                                                                                                                                                                                                                                                                                                                 |

## a) FULLY DONE

1. **f8 — the hereditary `markers_check` red is healed.** Seven monotonicity findings across two archived snapshots (all caused by formatter sweeps renumbering ordered lists and dropping a corrected table cell) repaired by append per the `428f2f4`/`7445752`/`bb8f49d8` precedent: displaced verdicts restated verbatim in `→ corrected` continuation lines, arrows re-added, dated correction records added. Gate green over 109 files after every repair (three repair passes today — see §d for why it took three).
2. **f9 — the sweep-damage class is now CI-visible.** `markers-history` CI job: full-checkout (`fetch-depth: 0`) + the same live sweep command the wired check runs on store copies (where the history arms auto-skip because `.git` is absent). actionlint clean, YAML validated, the exact CI command reproduced locally green (109 files, 0 findings), and it joined `notify-failure`'s needs list. First live CI proof still pending push (§b).
3. **f5 — the 2.12.0 Range/seek capability is gated end-to-end in this repo.** `tests/operator.nix` now rides the full browser chain — nginx vhost → webphone proxy (session-injected Basic auth as ext 1000) → operator — and asserts `206`, `Content-Range: bytes 0-3/...`, `Accept-Ranges: bytes`, the RIFF body head, and `416` on an unsatisfiable range. Suite GREEN (`EXIT=0`, operator journal shows the upstream 206/416 pairs).
4. **f1 — the gate-5 red is base-attributed, with an honest boundary.** Two runs at the pre-relock base (`19788cd` worktree): GREEN 398 s, then RED 850 s under load ~27 with a DIFFERENT load-sensitive assertion (`data-dial buttons survived logout: 1`) after heavy wss-1006 reconnect churn. Conclusion written into the CHANGELOG: the red class lives in the suite-under-load, not the 2.12 delta; the original red's exact assertion did not reproduce (stochastic class — the runbook's attribution clause satisfied with its limit stated).
5. **f3 — the CHANGELOG gate-5 clause now tells the truth.** The morning's "no path to transport loss" inference replaced by the base-attribution verdict and its boundary; the parenthetical about "the server half is pinned" extended with the new through-vhost leg.
6. **f2 — the audit addendum landed, every claim source-verified first.** `docs/research/2026-10-25_webphone-deep-dive.html` gained `<section id="addendum-2026-11-10">` + a nav entry; `docs/research/README.md`'s index row updated. Verified at the pin before writing: the two-commit delta (`fc352e66` toast+Range, `2c2cc950` Tailwind), `proxy.go` forwarding/passthrough lines, `shell.js` toast machinery, `tailwindcss v4.3.4` headers, `webphoneVersion = "2.12.0"`. The three parked subagent leads disproven at source and recorded so the re-score cannot inherit them: `agent:false` is the deliberate value-pin (`tests/configjs_check.py`), `usermgmt.db` IS in `state.sqliteDatabases` (`modules/telephony/default.nix`), the operator keeps NO OIDC database (its only sqlite is the voicemail DB, read-only).
7. **f7 — the fixed ladder executed for real.** `scripts/relock-ladder.sh --browser-e2e --full-check --keep-going`: binary-proof, fast-fmt, fast-eval, all six `GATE4_SUITES`, browser-e2e, full-check — 11/11 exit 0, verdict table printed, `LADDER_EXIT=0`. Honest caveats recorded in the report: warm store (gates re-validated today's derivations rather than cold-building), and the tree it gated is pinned (`28e1a74`, lock at `2c2cc950`) — the 15:16 sibling relock landed after the last gate started.
8. **f4 — the session lessons are in durable docs.** `docs/lessons/operating.md`: the 2026-11-10 double-sweep lesson (formatter churn + lock moves in ONE heuristic commit; the two-check post-sweep ritual) plus the three smaller mechanics (no `--dry-run` on `nix flake update` 2.34.9; `<parent>/<child>` input paths work; the ~90 s daemon window). `AGENTS.md`: the sweep-forensics bullet extended with the escalated class.
9. **Two unattributed sweep incidents detected, repaired, and attributed** (13:51 `268c091` and 15:31 `3ae07bf` — full narrative in §b/d; the repair recipe is now documented and repeatable). The swept revs' gate-0 builds recorded (`41eab05d` GREEN; `6936be2a` not built — superseded by the restore).
10. **Four daemon-race recoveries without loss**: amend (`dfd3dbe`→`2a362a8`), leave-alone (my `operator.nix` edits inside `748e3ce`/`4df7f7f` once the sibling built on top), squash-of-three (`ddfbbe8`+`95b9242`+`0e0f59e` → `8dd37ea`), amend (`cbee203`→`21bf9c2`); plus the sweep repairs riding `91fa748` with the attribution in `739f4a8`.
11. **Final verification battery green at session end**: working tree clean; `markers_check` 0 findings (109 files); `rendering_audit` 0 findings; `doc_counts` derived match (`50` checks, `365` tests); `lock_guard` PASS; `python3 -m unittest discover -s tests -t .` = **365 tests OK** (149.9 s); `nix eval` of the operator suite drv green at the restored lock.
12. **CI state mapped (read-only triage)**: `bd3c0e4` (caller-id feature + everything before it) = **completed success** on origin; `268c091`/`4d6f408` in-flight at session end (both real `CI` push runs, event and job list checked per the workflow-filter rule).

## b) PARTIALLY DONE

1. **The healed state is not on origin.** origin/main = `4d6f408`, which still carries sweep #1's damage (reverted lock, dropped markers) and predates every repair. Six local commits (`8dd37ea`..`739f4a8` + the sibling's `ad841c4`/`7e1bcec` relock pair) are unpushed. The `markers-history` job — the systemic fix — cannot police origin until these push. Push is owner-gated (§g).
2. **The audit refresh is half-landed.** The addendum (verified deltas, disproven leads, gate-5 tail) is in; the full 27-capability re-score is not. The TODO row now points at the NEW pin (`d537ed73`, then re-swept — see §b.5) instead of the stale one.
3. **Sweep containment, not sweep prevention.** The executor is still unidentified (three sweeps today: 13:51, 15:16-adjacent relock is a separate lane, 15:31); both sweeps re-pinned the tracked input to moving upstream tips and reverted child inputs. Containment (lock-guard, markers-history, the two-check ritual, my restores) works; prevention does not exist yet. Root cause of the marker churn — the markdown formatter that renumbers lists — is also untreated: sweeps WILL re-damage the snapshots again.
4. **The browser suite's load sensitivity is recorded, not root-caused.** The failing `data-dial buttons survived logout` assert reproduced at the OLD pin, so it predates 2.12; whether it is a missing settle-wait in `tests/browser-e2e.py` or a real upstream logout bug is undug (routed as §f item).
5. **The sibling's relock (`d537ed73`) is stranded**: their CHANGELOG entry (`7e1bcec`) claims it, sweep #2 reverted the lock away from it, my restore pinned `2c2cc950` — the entry and the lock now disagree. Their lane owns the re-relock or the amend; nobody has acted as of session end (§g).
6. **The ladder's cold-store proof is open.** The first real run re-validated warm derivations. A `--rebuild` pass of at least gate 5 + one VM suite would upgrade the proof tier; not run today.
7. **The addendum's render check is parser-tier.** HTML parsed clean and `rendering_audit` passed; no browser-render spot check of the new section was done.

## c) NOT STARTED

1. Push + post-push CI verdict chase for the six local commits (owner-gated; the handoff's f27 stays open until then).
2. A gate run (the ladder) for the sibling's `d537ed73` — or their lane's own ritual completion.
3. Sweep-executor instrumentation (auditd / nix wrapper logging argv) — the standing owner lane.
4. The markdown-formatter root cause: find which tool renumbers the archived lists and stop it (treefmt glob? prettier config? the daemon's own normalization?).
5. f6 — ladder `--only`/`--skip` selector (re-run one red gate without rebuilding six).
6. A `--rebuild`/cold mode for the ladder.
7. f10 — a standing check that every `nix build .#…` attr printed in `scripts/` or AGENTS.md resolves.
8. f11 — ASR wiring (`webphone.asr.*` option surface, env wiring, eval assertions, configjs arm).
9. f12 — push transports (`push.ntfy`, `push.fcm`).
10. The audit re-score itself (§b.2's remaining half).
11. f13–f50 of the morning report — untouched this session (out of this session's scope; the morning report carries them).
12. BuildFlow run — the repo is BuildFlow-covered; this session again used the flake gates (carried from the morning's f28).

## d) TOTALLY FUCKED UP

1. **Two of my three operator-suite runs were red because of me, not the code.** Red #1: I inserted the Range block after the suite's delete-drill without reading the suite's full lifecycle — the mailbox is provably empty (`vm_boxcount 0:0:0:0`) by the time my late-placed legs ran, so `{"messages": []}` crashed my JSON extraction. A VM run spent on a planning failure. Red #2: I asserted exact-case response headers through a proxy chain whose wire casing I had never dumped. Both failures were preventable by the runbook's own disciplines (map the timeline first; dump first, assert second) — I applied them only after paying for them.
2. **My morning heal was swept within ~90 minutes.** The first repair (`2a362a8`) was committed fast, but the daemon's 13:51 sweep re-damaged everything anyway; the second sweep did it again. I cannot prevent sweeps (no hook reaches the daemon), but I ALSO did not push the heals — the only durable protection (`markers-history` on origin) sits in unpushed commits. The repair loop will repeat until push or executor-identification happens.
3. **My repair arithmetic failed once.** The second heal's `f:#11` restatement line carried 11 markers where 12 were needed — the gate caught it (as designed), but I eyeballed a count I should have computed from `MARKER_RE` before writing. The gate is the verifier, not my calculator.
4. **The lock was hostile for most of the session and I was slow to treat it that way.** Sweep #1's lock move (13:51) sat undetected until 13:55 because I was mid-f1; between 15:16 and 15:31 the sibling's relock and sweep #2's re-pin fought over `webphone` with me as a bystander. A session that watches `flake.lock`'s mtime (or re-hashes it before each verdict) would have caught both sooner. The two-check ritual is now documented — I ran it manually, late.
5. **My commit-message accuracy slipped once**: `c64f618` claimed the lock restore + cell heal, but the daemon's adjacent `91fa748` had already carried them — the commit actually held only the CHANGELOG bullet. Amended to `739f4a8` with the true attribution. (Also: two edit-tool rejections on stale reads — bash `sed` doesn't satisfy view-before-edit — pure friction, but each cost a round trip.)

Nothing was destroyed: no force-push, no pushed damage left unattributed, no data loss. The worst durable state (origin carrying sweep #1's reverted lock for ~40 minutes) is repaired locally and waiting on push.

## e) WHAT WE SHOULD IMPROVE

1. **Experiment design beats verdict-chasing.** One run per pin proves little; the f1 experiment would be stronger as n-runs-per-pin at recorded load (or a controlled-load harness) with the assertion signature compared per run. Today's design produced a usable boundary, not a tight proof — say so in the docs it feeds.
2. **Map a suite's lifecycle before inserting into it.** The delete-drill trap generalizes: any suite with destructive phases invalidates late-placed fixtures. A one-paragraph "lifecycle map first" rule in `docs/lessons/vm-testing.md` would have saved a VM run.
3. **Dump the wire, then pin the assert.** The header-casing failure is the dump-first lesson applied backwards. First probe prints the actual exchange; the assertion is written against evidence, not expectation.
4. **Script the post-sweep ritual.** `scripts/sweep_check.sh` (diff `flake.lock` against the last gate-proven commit + run markers/rendering + report the diff) would turn a 20-minute manual forensic into 20 seconds and make the two-check ritual executable under stress.
5. **Compute marker counts, don't eyeball them.** A 3-line python probe over `item_counts`/`MARKER_RE` (I eventually wrote one) should precede every repair line.
6. **Commit within the daemon window, every time.** The second half of the session averaged minutes from edit to commit; the morning heal proved why the first half's pace matters. Push (owner action) is the only durable containment — say that in every sweep report.
7. **Lane-awareness at session start and mid-session.** `git log origin/main..HEAD` + a lock-mtime peek at start (now also mid-session after any long gate) would have surfaced the sibling's relock before my ladder ran, not after.
8. **The ladder should print the tree it gated** (HEAD sha + lock hash) in its verdict table — today I had to reconstruct that from log timestamps after the sibling's relock landed mid-run.
9. **The ladder should refuse mixed-tree runs**: re-stat `flake.lock` at each gate start and warn/abort on change (the mixed-verdict hazard I navigated manually).
10. **Render-check HTML deliverables at the tier you claim.** "Parses + gate green" is weaker than "renders" — say which tier a doc claim rides, or add a render check.

## f) Up to 50 things we should get done next

Grounded in this session's observations plus the morning report's carried items. Bare rows — markers get added at closeout of whatever session picks them up.

1. Push the six local commits (owner call — note it releases the sibling's unpushed relock pair too; §g1), then chase CI for `8dd37ea`/`739f4a8` — the `markers-history` job's first live run is the real negative-test of the healed state.
2. Read the in-flight CI verdicts for `268c091`/`4d6f408` (event + job list per the workflow-filter rule) and record them.
3. Gate the sibling's `d537ed73` relock through the ladder — it has zero verdicts and its CHANGELOG entry already claims it; whoever moves the lock owes the gate table.
4. Resolve the sibling CHANGELOG/lock disagreement: `7e1bcec` claims `d537ed73`, the restored lock pins `2c2cc950` — re-relock through the ritual or amend the entry.
5. Root-cause the load-sensitive `data-dial buttons survived logout` assert (reproduced at the OLD pin — it predates 2.12): missing settle-wait in `tests/browser-e2e.py`, or a real upstream logout bug?
6. Harden `browser-e2e.py`'s logout-cleanup with the established settle pattern if (5) says suite-side; carry the evidence upstream if it says product-side.
7. Write `scripts/sweep_check.sh` — one command: lock diff vs last gate-proven commit, markers + rendering gates, exit nonzero on drift (the two-check ritual, executable).
8. Find and silence the markdown renumbering (formatter/root cause): identify which tool rewrites the archived lists (treefmt glob? prettier? the daemon's normalizer?) and exclude archived snapshots from it — this ends the entire repair loop.
9. Instrument the sweep executor (auditd rule or a nix wrapper logging argv+cwd+ppid) — three sweeps in one afternoon, all unattributed; the TODO row is stale the day it's written.
10. Add a lock-mtime watch to the session ritual (and re-check after any gate longer than ~10 min): `stat flake.lock` + `git diff --stat flake.lock` before trusting any verdict.
11. Pin the `webphone` input to a rev in `flake.nix` (owner decision — the runbook documents the tradeoff) OR accept tracked-main and make sweep_check mandatory pre-verdict; the status quo is the worst of both.
12. f6 — ladder `--only`/`--skip` gate selector so a single red gate rerun doesn't rebuild six greens.
13. Add `--rebuild` (cold mode) to the ladder for gate 5 + one suite; upgrade f7's warm-store caveat to a cold proof.
14. Ladder prints its tree (HEAD sha + `flake.lock` hash) in the verdict table.
15. Ladder re-stats `flake.lock` per gate and aborts on change (the mixed-verdict hazard, encoded).
16. f10 — standing check that every `nix build .#…` attr printed in `scripts/` or AGENTS.md resolves to a real flake attr.
17. f11 — ASR wiring (`webphone.asr.*` options, env-file wiring, eval assertions mirroring upstream validation, a configjs arm).
18. f12 — push transports (`push.ntfy`, `push.fcm`).
19. The audit re-score at the settled pin (after 3/4 resolve): score all 27 capabilities, supersede the 80/100, per the addendum's handoff note.
20. The ASR owner decision (the audit's one open capability gap) — provider choice, then f11 unblocks.
21. `retention_days` facade option (T13, carried; only if a policy actually applies).
22. Per-DID named identities (carried, owner-gated).
23. Deployment closeout row (owner hands-on steps; the repo side is proven — BLOCKED on the human half).
24. nixpkgs upstream lane: draft the `CPUSchedulingPolicy`/config-dir `mkDefault` ask (verify-before-filing first).
25. go-cqrs-lite#120: when upstream lands `marshalCeremonyResponse`, relock + rerun `tests/passkey.nix`.
26. GitHub residual-exposure: the support GC ask + stale-clone inventory (owner-only knowledge).
27. Verify the addendum renders in a real browser (or html5-validate) — upgrade the claim from parser-tier.
28. Confirm `d537ed73`'s `/config.js` key set against `tests/configjs_check.py` — the sibling's entry mentions an anonymous-deep-links door; any key drift is a red the current suite would catch only after the lock moves again.
29. Check whether `d537ed73`'s toast/waveform changes moved any gate-5 DOM selector (the runbook's markup-delta clause) before its eventual gate run.
30. Runbook: encode the "gate 5 under load" policy numerically (rerun when load > N? serialize?) so the next red is a procedure, not a judgment call.
31. Append the mailbox-lifecycle trap (delete drill empties the box; fixture legs must precede it) to `docs/lessons/vm-testing.md`.
32. Consider a `markers_check` structural fix: attribute continuations to the item that OWNED them pre-sweep (or exclude formatter-demoted lines), ending the ratchet where each heal raises peaks and the next sweep re-scrambles keys.
33. Re-verify AGENTS.md's `365`/`50` doc-count claims after the next test or check lands (doc-counts already gates it — just keep the habit).
34. When both morning + this report are fully marked, archive both with a check-rows uniformity pass (house convention).
35. Upstream webphone: the reports-train revs (`41eab05d`-era) that sweep #1 exposed — after `d537ed73` settles, evaluate the reports features as a deliberate relock candidate (gate-0 + ladder), not a sweep import.
36. Nudge the sibling lane: their relock entry cites "see the relock commit" — that commit (with the verdict table) doesn't exist yet.
37. Sweep #1/#2: record both in the sweep-executor TODO row's evidence column (count: five+ incidents; signature now includes lock moves).
38. The ladder's gate-4 suites could take the CI per-suite timeout pattern (bounded budget per suite) so a hung suite can't wedge the ladder.
39. Re-check `nix flake update --dry-run` availability if the fleet's nix moves past 2.34.9; keep the scratch-repo recipe until then.
40. Cross-ref `<parent>/<child>` input updates into the runbook's recursive-update lane note (currently lesson-only).
41. The two prunable foreign worktrees (`/tmp/wt-046623d`, `/tmp/wt-agent-old`) — other sessions' leftovers; owner sweep call, not mine.
42. `configjs_check.py`: consider asserting the FULL key set (not just `agent`) so upstream key additions surface as a named red, not a silent pass.
43. `tests/operator.nix`: the through-vhost leg logs the audio_url with its signed token into build logs — verify the token is short-lived enough that log exposure is harmless (it carries `e=` expiry; confirm the bound is tight).
44. Operator suite runtime budget: my three runs cost ~5 VM minutes on self-inflicted reds; a pre-flight `python3 -c` syntax check of the edited testScript block (imports included) would catch the `re` class cheaply.
45. Consider running the ladder's gates 2–3 as a pre-commit-style fast lane after ANY nix edit (they're ~2 min warm) — today they ran only inside the ladder.
46. Sweep-response playbook: add the "restore lock from last gate-proven commit" one-liner (with the commit-hash argument) next to the two-check ritual in AGENTS.md.
47. The deep-dive HTML: the nav's scrollspy picks up new sections only if nav links exist — the new addendum entry works; keep the pattern for future addenda.
48. Check whether the 15:31 sweep's `6936be2a` tip is upstream's next release candidate (affects the relock candidate list ordering).
49. AGENTS.md: the "sweep-source instrumentation" bullet now has three same-day incidents — consider promoting the two-check ritual from paragraph to process rule.
50. Keep the repair grammar honest under pressure: every `→ corrected` line restates REAL displaced verdicts; when the traveling set is ambiguous, probe `item_counts` at the peak commit first (I did — it works; make it the default).

## g) Questions I can NOT figure out myself (max 3)

1. **Push policy with a sibling's work in the pile.** Six commits sit unpushed; two of them (`ad841c4`, `7e1bcec`) are the sibling lane's relock lock-move + CHANGELOG draft — pushing releases THEIR relock onto origin CI without any gate verdict existing for `d537ed73`. Do I push everything as-is, push only my four (requires a lane-coordination rebase I'd rather not do while their session may be live), or hold until their relock is gated?
2. **Who/what ran today's three sweeps — and do you authorize the instrumentation?** Same signature each time (symmetric formatter churn + a lock move against a moving upstream tip), all daemon-carried, none attributable to a session I can see. If you know which lane runs `nix flake update` (a pma/crush session on another machine?), the mystery closes without tooling; otherwise shall I build the auditd/nix-wrapper instrumentation (the TODO row estimates 1h)?
3. **The webphone pin policy after today.** Three sweeps re-pinned the tracked input to moving upstream tips in one afternoon, and the sibling relocked mid-day; the gate-proven state (`2c2cc950`) is now the local lock. Do you want the input PINNED in `flake.nix` (rev-pinned, sweep-proof, but manual bumps), or does tracked-main stay — in which case, should `sweep_check.sh`-style lock verification become a MANDATORY pre-verdict step for every session and CI job that claims anything about the tree?
