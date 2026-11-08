# Status: docs-health round 11 — full corpus archive, living-docs truth pass, harvest (2026-11-07, 09:07 CET)

Mission: "View ALL `**/2026-0*` files. Execute the docs-health SKILL. Archive FULLY done and
UPDATED (inline strikethrough) .md files." Scope grew honestly: the `2026-0*` glob surfaced
the six un-archived research/decision stragglers, and the archive directive pulled in the
whole 2026-10 live-snapshot corpus — 29 snapshots (27 status + 2 planning), ~1,000 numbered
items, annotated + archived in one round with six subagent lanes plus this session's own.

End state: **`docs/status/` and `docs/planning/` hold ZERO loose snapshots** — everything
from 2026-08-21 to 2026-10-28 now lives under `archived/` with per-file manifests in both
archive READMEs. All living docs verified against the tree and corrected. Gates green:
`markers_check` 107 files / 0 findings, `rendering_audit` 107 / 0, `drift_alarm` PASS,
`treefmt` clean, completeness grep clean over all 29 moves.

---

## a) FULLY DONE

1. __2026-0_ files (the literal ask), all six viewed and dispositioned_*: `docs/research/2026-09-16_fspbx-trial.md` (ANNOTATE — the "VM preserved until sign-off" header struck: host check 2026-11-07 shows `/var/tmp/fspbx-trial` gone; index row added to the research README, which had silently omitted this file), `docs/decisions/2026-09-17_mms-posture-http-api-only.md` (ANNOTATE — "no MMS code today" overtaken 2026-09-26/29 by the bridge lane, struck with commit evidence), `docs/decisions/2026-09-17_sms-lane-telnyx-api-only.md` (ANNOTATE — writer moved in-repo to `services.telephony.messaging`, struck), plus three verified SKIPs: the SIP ecosystem survey (self-verifying table, dated, rot warnings), the nix-diff-drafter verdict (`telephony-dialplan-simulate` binary + `/operator-api/simulate` route confirmed present), and the nix-ssh-config HTML (index carries its verdict).
2. **ROADMAP MMS row rewrite**: the row described a future ("if ever") that already shipped — replaced with the shipped-bridge facts + the remaining operator-media-tab raw idea.
3. **29/29 snapshots annotated + archived** (27 status → `docs/status/archived/`, 2 planning → `docs/planning/archived/`), every file gated with `check-rows --strict` + `bare-rows` BEFORE `git mv`, completeness grep clean over every move. My own lane: 10-26_07-01, 10-28_10-10, 10-12_05-38 (24 table rows + 8 late-caught prose items), and both SUPERB Pareto plans (62 + 46 action lines).
4. **Six subagent lanes completed** after rate-limit carnage (see §d1): joakim (10-01 batch ×3), noemie (10-12 ×3), connie (10-25/28 ×3), akiko (10-01→03 ×4), luka (10-07 ×5), madeline (10-05→07 ×6, plus a follow-up pass on two dash-prose files). Zero left-bare items anywhere; zero fabricated hashes (agents cite `git cat-file` / `gh` verification in their reports).
5. **Harvest: TODO_LIST rebuilt** — the stale `mainProgram` row deleted (AGENTS.md records the accepted remainder), the fspbx row updated (VM retired), and ~35 routed rows added across High (CI red ×3, `5f331e6` CHANGELOG overclaim, runbook ritual hardening batch, full-check re-proof), Medium (pbx-lens upstream CI, providers re-verify, AGENTS trim, pma go-commit gating, sweep-executor hunt, lock-input refresh, relock ladder, gate-4 archaeology), Low (three batch rows: process codification, ops/test depth, pre-commit hardening; plus singles: lock-doctor retry, configjs value-pin, nonce harness + lessons, deploy.md timeZone, E2E depth, csrf eval arm, pbx-lens runbook subsection, TRACKED_INPUTS dedup, doc-counts check, crush-config lessons, `(repo: webphone)` bind-order issue + FEATURES row refresh). Drift-gate-clean after three ghost-citation fix cycles.
6. **Living-docs fixes**: FEATURES gained the dynamic-directory row (`directory.mode = "xml_curl"`, the bridge contract, the static-fallback rule) and the CDR row now names `telephony-cdr-visibility` with the loopback-blindness finding; README's module example modernized to the preferred plural `gateways.main` shape (all example fields verified against `gatewayType`); CHANGELOG gained the missed-record backfill entry (typed-CSRF wiring + the `c043434` battery verdict).
7. **Archive manifests recorded**: 20 status rows + 2 planning rows in the two archived READMEs, each with classification + deciding reason — no invisible bulk-archive history.
8. **AGENTS.md and DOMAIN_LANGUAGE verified with NO edits needed** — the durable knowledge held (vulture whitelist EXISTS as AGENTS claims — disproving one agent route; doc_counts derives 338 tests/46 checks; the ritual + daemon forensics paragraphs all served as valid citation targets all session).
9. **One rendering gate catch repaired**: a mid-item strike split with a swallowed backtick closer in the archived 02-11 file — rejoined whole per the prose-repair grammar, gates re-run green.

## b) PARTIALLY DONE

1. **CI main-gate triage**: classified at job level (the `nix flake check` job fails while aarch64 VM + stdlib python suites pass — a real red, latest failing head `0b4ce0c`), but the failed STEP log was never read and the heal never started. The TODO row carries the facts and the airtight-verdict protocol pointer.
2. **Daemon push lane**: origin/main..HEAD sat at 0–5 commits through the session (the daemon absorbed and pushed continuously, including mid-sweep heuristic commits that bundled sibling lanes' files); the final tree state rides the daemon's schedule, not a verified push.
3. **TODO_LIST granularity**: several new rows are deliberate grab-bags (process-codification, ops/test-depth, pre-commit hardening) — bounded but multi-item; per-lane splitting is deferred.
4. **Two dash-prose files needed tool workarounds**: `repair` mechanically cannot parse dash-prefixed or paragraph-shared items (`reNumItem` requires `N.` prefixes), so madeline fell back to byte-exact hand-shape strikes validated through the gates. The shape gap is real upstream annotate.go surface, unfiled.

## c) NOT STARTED

1. Healing the CI red itself (row exists; the log read + fix is the next session's highest-value opening move).
2. Everything the harvest minted — the ~35 TODO rows ARE the backlog now; none were executed this session (by design: this session is the docs-health round).
3. The docs-gates battery (`nix run github:Artmann-Technologies/docs-gates`) was never run — the repo's native gates (markers/rendering/drift) were used instead; adoption is an open question (§g3).
4. AGENTS.md trim (~560 lines today), lessons batches, runbook invariants — routed, untouched.
5. Release lane: the CHANGELOG `[Unreleased]` pile (including today's backfills) awaits the owner's cut decision.

## d) TOTALLY FUCKED UP!

1. **Rate-limit mismanagement cost the session hours.** I dispatched SIX concurrent subagents at once; four died instantly on `retry error: too many requests`. Resumes then re-burst (resuming noemie while three ran killed luka again). The working concurrency was ~3; I learned it by burning agents, not by starting there. Serial-with-stagger should have been the plan from dispatch one.
2. **Nearly minted a false TODO row from an unverified agent route.** madeline reported "no vulture whitelist file"; AGENTS.md says `tests/vulture_whitelist.py` holds load-bearing references. I caught the contradiction only in the final verification batch — `ls` proved the file EXISTS and the route was false. Had I batch-consolidated routes when each report landed (the tempting move), the lie would be in TODO_LIST. Route → row needs a grep gate, always.
3. **Edit-anchor failures repeated a documented lesson.** I tried re-typing the giant TODO_LIST table separator lines as anchors (failed twice) before switching to structural prefixes — the AGENTS.md edit-mechanics lesson says exactly this ("match structurally, never re-type full-line anchors"). Then my own `sed` deletion triggered the modified-since-read dance. Cost: ~4 wasted cycles.
4. **A one-cycle scope miss on the drafter verdict**: the first `simulate` grep covered only modules/tests/scripts + flake.nix and found nothing — nearly mislabeling an accurate decision doc as stale. The wider grep (`packages/`) found `dialplan_sim.py` + the wrapper. Diagnose from evidence, widen the scope before concluding.
5. **Shipped a malformed manifest row for one edit cycle** (missing closing backtick in the luka section of the status archive README) — self-caught immediately, but it shipped. The rendering gate did NOT flag it (it audits snapshot files, not the README); only my own re-read did.

## e) WHAT WE SHOULD IMPROVE!

1. **Fan-out discipline**: rate-limit-aware dispatch (start ≤3 concurrent subagents, stagger resumes on failure reports, never re-burst into a draining fleet).
2. **Route-to-row gating**: every agent-reported route gets a tree/CHANGELOG grep BEFORE becoming a TODO row (the vulture near-miss class).
3. **Pre-flight TODO evidence cells through `drift_alarm`** before finalizing rows — the ghost-citation grammar (`path:NN`, cross-repo paths, to-be-created paths) cost three fix cycles that a pre-flight would have collapsed to one.
4. **Batch rows should carry route counts and per-item subjects** (the later manifest rows do; the earliest TODO batch rows are looser).
5. **File upstream annotate.go gaps**: dash-prose items, paragraph-shared numbered items, and non-token table first cells all required fallbacks this sweep — three concrete shapes, one upstream note.
6. **Archive manifests belong in the same commit as the moves** — mine landed across several edits because agent reports arrived asynchronously; a sweep that collects manifests before moving avoids the gap.

## f) Up to 50 things next (impact-sorted; ~35 already live as TODO_LIST rows — row references in parens)

1. Read the CI main-gate failure log airtight and heal the red (TODO row: CI main gate RED ×3) — the opening move.
2. Fix the `5f331e6` CHANGELOG overclaim (TODO row; 5-minute append-only correction).
3. Refresh the lagging non-webphone inputs — `flake-parts_2` + `home-manager` (TODO row; the flake-update bot toggle is the owner half).
4. Runbook ritual hardening batch, twelve sub-items a–l (TODO row).
5. AGENTS.md trim to the round-10 proposal (~560 → target; TODO row).
6. `(repo: pbx-lens)` heal the upstream CI (TODO row; gh-verified failing).
7. `(repo: pma)` go-commit hook gating + `exclude_pathspecs` lever + fleet sweep (TODO row).
8. Sweep executor hunt — instrument the mystery `nix flake update` lane (TODO row).
9. Gate-4 anomaly archaeology: rerun `telephony-webphone` at the `5f331e6` base with `--no-eval-cache` (TODO row).
10. Full `nix flake check` green re-proof on a current head (TODO row).
11. `scripts/relock-ladder.sh` automation (TODO row).
12. Value-pin `agent is False` in `tests/configjs_check.py` (TODO row).
13. lock-doctor retry/backoff + target-rev verdict (TODO row + route).
14. Nonce-deleter harness in-repo + vm-testing lessons + freeswitch.md nonce mechanics (TODO rows ×2).
15. deploy.md `time.timeZone` in the CHANGEME walk (TODO row).
16. `(repo: webphone)` file the listener-bind-order issue upstream, verify-at-source first (TODO row).
17. Domain vocabulary additions: base-attribution, enrollment token, usermgmt.db, prove-before-lock (TODO row).
18. Providers pricing re-verification pass (TODO row).
19. vm-testing lessons batch: busy-spin/`_parse_one`/py_compile/tail-truncation + empty-output/nix-log + OOM local-vs-CI + eval-cache serialization (TODO row).
20. Codify the ~20 round-11 process rules into AGENTS.md/lessons (TODO row, the big batch).
21. Pre-commit/lock-gate hardening batch: self-heal regression script, canary script, lock-move-guard arm swap, commit-msg check counterpart, heal-script canary, mypy ladder (TODO row).
22. Docs batch: runbook BuildFlow invariants, hook-strip/go-git long-form, README BuildFlow pointer, CHANGELOG backfills (`c19bdea`, `c59305ba`), CDR TODO row compression (TODO row).
23. `(repo: crush-config)` lessons.md entries (TODO row).
24. Ops/test depth batch: livez/startupz asserts, verify-live livez gates, operator `/version`, dashboard/paperless eval arms on verdict flip, post-deploy browser smoke, missed-call ring shape, cdr-visibility row-shape assert, synthetic-DID doc (TODO row).
25. Passkey/test depth batch: theme-only E2E, passkey ceremony E2E, enroll wrapper unit, secrets.md note, pbx-prod passkey CHANGEME enablement, attribution store sharing, pipefail guidance, status-answer helper, mailbox quotas, MWI check, greeting surface, buildflow doctor (TODO row).
26. Pre-commit hardening singles: configjs value-pin sibling, csrf eval arm, pbx-lens runbook subsection, TRACKED_INPUTS dedup, doc-counts check, scripts/ ruff sweep (TODO rows).
27. CI topology batch: `--system` sentinel, cross-arch eval split, weekly red-gate canary, per-arch timings, aarch64 build proof, E2E runner unit (TODO row).
28. File the annotate.go shape gaps upstream (dash-prose, paragraph items, non-token first cells) — new this session, no row yet.
29. Add per-route counts to future archive manifests at move time (process note, §e6).
30. Decide the docs-gates battery adoption (§g3) — new, no row.
31. Split the TODO grab-bag rows per lane when first touched (process note).
32. Next docs-health round is cheap now: zero loose snapshots — the corpus debt is gone; only the freshest reports accumulate from here.
33. `(repo: webphone)` refresh the upstream "Browser E2E" FEATURES row (TODO row).
34. Demo-VM Berlin wall-clock smoke (TODO row, Low).
35. Browser-render both deep-dive HTMLs for dead CSS (TODO row, Low).
36. Messaging depth batch: WhatsApp media arm, `.chan-mms` CSS, portal 40008 pin (TODO row).
37. Stale `chore/flake-update-2026-09` branch deletion + the flake-update bot toggle — owner admin lane, rows exist.
38. `a0c78ca` history surgery — owner lane, standing.
39. Lens vhost exposure decision — owner row exists.
40. ALERT_WEBHOOK secret fire-drill — owner row exists.
41. T12 `/metrics` consumer card + T13 `retentionDays` — owner-gated rows exist.
42. Push seam + ASR facade — owner-gated, ROADMAP raw ideas + AGENTS open-gaps list.
43. Nixpkgs lock fencing policy decision (ROADMAP raw idea, new).
44. Voicemail depth family (ROADMAP theme 2, extended this session).
45. Upstream bulk-commit split proposal (ROADMAP, new).
46. Webphone staleness alarm (ROADMAP, new).
47. Serialize CI VM checks on recurring load flakes (ROADMAP, new).
48. Round-12 folding + post-incident provenance note (ROADMAP, new).
49. M12 summarize-button pin if `agent=true` ever wires (ROADMAP, new).
50. Refresh `docs/research/README.md` verdicts when the next webphone release tag lands (standing trigger, already recorded there).

## g) Questions I can NOT figure out myself (3)

1. **Opening priority for the next session**: heal the CI main-gate red first (read the failed step log, fix, re-proof green — the Critical row), or the lagging-input refresh + `5f331e6` overclaim correction (the fast honesty/two-row sweep) first? Both are queued; the order is yours.
2. **The annotate.go upstream note**: three tool-shape gaps forced hand-shape fallbacks this sweep (dash-prose items, paragraph-shared items, non-token first cells). File them upstream as one docs-health issue per verify-before-filing, or leave the shapes as accepted hand-work?
3. **docs-gates adoption**: the fleet battery (`docs-gates run .`) could replace or wrap this repo's three native doc gates (markers/rendering/drift). Adopt it as the standing gate, keep the native trio, or wrap both behind one script?

---

_Written 2026-11-07 09:07 CET. Point-in-time snapshot per house convention: annotate, never
rewrite. The full per-file manifests live in `docs/status/archived/README.md` and
`docs/planning/archived/README.md`; the inline health report (Accuracy 4.75 as-found /
Fitness 8.5 as-found) was printed to the session, not filed._
