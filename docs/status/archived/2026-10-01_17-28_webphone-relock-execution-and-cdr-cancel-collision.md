# Webphone relock execution & the cdr-cancel collision — session status

**Snapshot:** 2026-10-01 17:28 CEST · session resumed ~10:05 from the
13-task SUPERB Pareto plan
(`docs/planning/2026-10-01_06-19_SUPERB-webphone-maximization-pareto-plan.md`),
picked up at T07.

**Session scope:** T07 relock ritual, T08 full-gate verification, docs
truth-up, T09 evidence hardening, T10 probe sweep, T11 dashboard spike.
Base inherited: sibling lane's shim-forward (`nixpkgs b4fd65b` + assert
shim + fs_cli PATH fixes, all already pushed; the prior session's
back-pin `81ac99a` superseded de facto).

**Commits this session (mine, all path-scoped and hand-authored):**
`d8bd34c` (relock), `19610ea` (TODO/FEATURES truth-up), `def576a`
(deep-dive addendum + dead-CSS fix), `e0eafa1` (T10/T11 verdicts),
`e665424` (CDR base-attribution evidence). Daemon's `5ed5888`
(voice-agent.py ruff sweep) rode along uninvited. **Push state:
`ahead 6`, held** (see §d).

---

## a) FULLY DONE

| Work                                                                                                                                                                                                           | Proof                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ~~**T07 — webphone relock `0e1d1743` → `f706575`** (67 commits, binary 2.8.0), full runbook ladder~~ done at d8bd34c (CHANGELOG 2026-10-01 v2.8.0 UX-train entry — full ladder incl. browser E2E)              | ~~Binary builds (checkPhase green); `nix fmt` 0-changed; `nix flake check --no-build` all-pass; `telephony-webphone` + `-fax` + `-fax-feed` VM suites green; browser E2E green on the changed markup; **beyond-ladder**: `telephony-messaging` also green; lock-guard/markers/drift PASS; hand-authored commit `d8bd34c` after daemon-sweep surgery~~                                                                                                                                                                                                                               |
| ~~Delta due diligence BEFORE gates~~ done at d8bd34c (pre-gate checks; the DOM-contract pre-check lesson is codified in the AGENTS.md relock paragraph)                                                        | ~~lock-doctor pre-flight (corrected the stale "28 commits behind" → 67); `f706575` verified ancestor of origin/main; module-refactor surface check (`settings` stays freeform-JSON — `gateway`/`identities` eval-safe; `memoryMax`/`backup`/`environmentFiles` intact); **contacts-revert impact pre-checked** (`6989b99` kept the scratchpad: `wp-compose-new`/`wp-row`/`wp-danger`/`data-dial` selectors verified in `contacts.templ` before the E2E ran)~~                                                                                                                       |
| ~~CI verdict triage on the inherited base~~ done — triage recorded; AGENTS.md 2026-10-06 reclassification (60-min job timeout, fixed by the per-system eval split in ci.yml) superseded the infra-kill reading | ~~Run `36841263555` = documented infra-kill (87 checks ✅ then 20-min stall → `cancelled`; the `nix flake check` step `skipped`; aarch64 green) — cancel ≠ red, per AGENTS.md protocol~~                                                                                                                                                                                                                                                                                                                                                                                            |
| ~~Docs truth-up (T02/T04/T05/T06/T07)~~ done at 19610ea                                                                                                                                                        | ~~5 TODO rows deleted; FEATURES webphone-service row + pbx-prod memoryMax updated; drift/markers green (`19610ea`)~~                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ~~**T09 — report hardening**~~ done at def576a                                                                                                                                                                 | ~~Dead-CSS sweep found `.warn`/`.highlight` referenced since publication but never defined → appended definitions (0 undefined now; rendered-DOM + screenshot render verified); 7 addendum items: execution verdict, version currency, upstream capability deltas (Paperless + dashboard NEW, contacts RETRACTED), upstream module-check citations (`nix/module-check-backup.nix`/`-csrf.nix` verified), missed-train supplement (Receipt.Resolution, fail-closed config, /version, SSE lifecycle, samber/do root), capability-enumeration + weighting reconstruction (`def576a`)~~ |
| ~~**T10 — health-probe sweep verdict: document-and-leave**~~ done at e0eafa1 (scripts/verify-live.sh:87 healthz probe verified in tree)                                                                        | ~~Decisive evidence: `scripts/verify-live.sh:87` probes `https://<host>/healthz` off-host (fencing breaks live verification); probes leak booleans only; `/metrics` stays uniquely fenced; suite-log probe evidence (healthz vhost-200, metrics external-403/loopback-200, green at `f706575`) quoted (`e0eafa1`)~~                                                                                                                                                                                                                                                                 |
| ~~**T11 — dashboard spike verdict: default-off**~~ done at e0eafa1 (seam since wired: services.telephony.webphone.dashboard.enable, default-off loopback-fenced — modules/telephony/options.nix + web.nix)     | ~~Upstream `internal/app` tests run live at `f706575`: default = styled 404 (fail-closed), enabled = mount + CSP nonces + SSE + `/health/livez` alias, all PASS; verdict vs operator window recorded (would duplicate status surface unauthenticated; revisit only behind the operator realm) (`e0eafa1`)~~                                                                                                                                                                                                                                                                         |
| ~~cdr-cancel failure attribution~~ done at e665424 (suite since restructured as telephony-cdr-visibility, 78025ec — CHANGELOG 2026-10-03)                                                                      | ~~Worktree run at base `1e7df77` (pre-relock) reproduces the identical `+OK <uuid>` failure → **relock exonerated**; suite proven sibling-WIP (new file 10:41, never green); evidence annotated into TODO row 45 (`e665424`)~~                                                                                                                                                                                                                                                                                                                                                      |

## b) PARTIALLY DONE

~~- **T08 — full-mode verification + push + airtight CI verdict.**~~ done at 86f3d3d (capstone full-mode run; origin run 37555437689 GREEN — CHANGELOG 2026-10-07)
`buildflow --build-mode full --max-time 60m` RAN: every step green
except ONE check (`telephony-cdr-cancel` — not mine, see §d), so the
documented "green shape" (findings gate with exactly the 4 port-collision
findings) was never demonstrated — the run died at the step failure
before the findings gate. The **push is held** and the origin CI verdict
is unobtainable while the base carries a code-red check: the next
completed x86 run fails on `telephony-cdr-cancel` regardless of what I
push. Everything my session touched is locally proven green.

## c) NOT STARTED

~~- **T12 — /metrics consumer card** (owner-gated; default skip applied —~~ → routed to TODO_LIST (/metrics consumer card)
no gate answer given).
~~- **T13 — facade `retentionDays`/`timezone` options** (owner-gated;~~ → routed to TODO_LIST (webphone retentionDays facade)
default skip applied).
~~- The push itself (deliberately held, not forgotten — see §d/§g).~~ done at 86f3d3d (pushed; capstone run 37555437689 GREEN)

## d) TOTALLY FUCKED UP (and near-misses, and forgot)

~~- **Near-miss, caught late: I wrote fabricated arithmetic into the report~~ done at def576a (rewritten as an honestly-labeled reconstruction; AGENTS.md now carries the rule: never write reconstructed counts into durable docs)
addendum.** The capability-enumeration item initially claimed
"7 named + 9 bundled = 17" — numbers I invented because the original
scoring worksheet was never published. I caught it on reflection AFTER
it was in the file and rewrote it as an honestly-labeled row-level
reconstruction. The file never shipped a commit with the fabricated
version, but it existed on disk. Root cause: writing reconstruction
where only verification belongs.
~~- **Lost the daemon race on the lock move — twice.** The runbook's exact~~ done at d8bd34c (surgery recovered the sweep; window lesson + commit-msg lock-move-guard since — AGENTS.md, CHANGELOG 2026-10-07)
known hazard (daemon heuristic message on a lock move = unattributed
breakage class) hit anyway: my relock→gates→commit window was ~90
minutes, the daemon swept `flake.lock` (`923c003`) and `CHANGELOG.md`
(`11c7557`) as heuristic commits mid-ritual. Soft-reset surgery
recovered it into `d8bd34c`, but the window was careless — the ritual
should commit the lock + entry scaffold minutes after gate 2-3, not
after every suite.
~~- **Wasted a verification roundtrip on a shell-context artifact:** read~~ done — codified in AGENTS.md: git show <rev>:<path> is the first-choice tree inspection
`f706575` from the fresh base worktree (contradiction!) and only
resolved it via `git show 1e7df77:flake.lock`. First-choice tool for
tree inspection should always be `git show <rev>:<path>`.
~~- **Forgot: no AGENTS.md durable-knowledge update this session.** The~~ done — the lessons landed in AGENTS.md (relock ritual at 67-commit scale, suite-asserts-as-probe-evidence, reconstruction-vs-verification)
global memory rules require it at discovery time; the session's durable
lessons (relock ritual proven at 67-commit scale; suite-log-as-probe-
evidence substitution; the reconstruction-vs-verification trap) were
only recorded in docs/status + commit messages until this report
session added the bullet.
~~- **Wasted render:** produced a 443 KB screenshot for a "visual check"~~ done at def576a (rendered-DOM structural checks are the recorded evidence; AGENTS.md: probe evidence comes from the suites own asserted curls)
before confirming the model could view images at all (it cannot) —
fell back to rendered-DOM structural checks (the stronger evidence
anyway).
~~- **Mechanism dithering on T09b:** spent real time choosing between~~ done — codified in AGENTS.md: probe evidence comes from the suites own asserted curls (greppable in nix log), never ad-hoc VM sessions
`nix run .#vm` driving, scratch test files, and upstream suites before
landing on "the suite's own asserts ARE the probe evidence". The
decision should have been immediate — the suites are the house's probe
mechanism by design.
~~- **Stranded-state risk I created:** 6 unpushed commits with no~~ done at 86f3d3d (pushed, capstone run 37555437689 GREEN; the daemon-also-pushes race is documented in AGENTS.md)
escalation path beyond waiting on a sibling lane that may be done for
the day. If the sibling is finished, main sits unpushed indefinitely
(the daemon never pushes). This is a policy gap, not an accident — see
§g Q1.

## e) WHAT WE SHOULD IMPROVE

~~- **Reconstruction discipline:** never write derived counts into durable~~ done — codified in AGENTS.md: never write reconstructed counts into durable docs — label reconstructions as reconstructions
docs without a verifiable source; label reconstructions as
reconstructions in the same breath.
~~- **Lock-move commit windows:** commit scaffold early, minimize~~ done — AGENTS.md carries minimize the relock→commit window; the commit-msg lock-move-guard landed (CHANGELOG 2026-10-07)
relock→commit latency; the surgery pattern works but is risk debt.
~~- **Red-base push policy (missing):** the house has a cancel-≠-red~~ → routed to TODO_LIST (red-base push policy)
protocol but no rule for "my commits are green, the base is
code-red from another lane" — hold vs push-and-attribute should be a
written decision, not an agent's judgment call.
~~- **Cross-repo citations rot:** the addendum cites webphone-internal~~ → routed to TODO_LIST (rev-stamp cross-repo citations)
paths (`nix/module-check-*.nix`, `internal/app` tests) without rev
stamps; they should carry the rev they were verified at.
~~- **AGENTS.md at discovery time**, not at session end.~~ → routed to TODO_LIST (durable-knowledge discovery rule)
~~- **Cap image-based verification attempts** when the harness can't view~~ → routed to TODO_LIST (structural-first verification rule)
them; go structural first.
~~- The inline dead-CSS sweep was a one-off shell heredoc; it should be a~~ → routed to TODO_LIST (deep-dive HTML dead-CSS)
`scripts/` tool if HTML reports multiply (one report = not yet worth
it — note for the future).

## f) Things to get done next (impact-ordered; brainstorm, not commitments)

| #      | Task                                                                                                                                                                                                                                                                                                                                                                                                                                    | Impact     |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- |
| ~~1~~  | ~~Land T08: once `telephony-cdr-cancel` resolves, push + airtight `gh run view` verdict~~ done at `86f3d3d`                                                                                                                                                                                                                                                                                                                             | ~~High~~   |
| ~~2~~  | ~~Resolve `telephony-cdr-cancel` itself (owner/sibling lane): fs_cli premise is dead (+OK answer-path); either restructure or remove the check~~ done — restructured as telephony-cdr-visibility, green (78025ec; CHANGELOG 2026-10-03; tests/cdr-visibility.nix)                                                                                                                                                                       | ~~High~~   |
| 3      | Test the 127.0.0.2 INVITE-wall theory noticed in `tests/sip.py`: sofia may dial the REGISTER source instead of the advertised Contact (received/rport rewriting) — force-contact experiment **→ routed to TODO_LIST (CDR cancelled-leg repro)**                                                                                                                                                                                         | High       |
| 4      | Live-host CDR investigation per TODO row 45 (journal the cancelled call, `uuid_dump` CDR vars) **→ routed to TODO_LIST (CDR cancelled-leg repro)**                                                                                                                                                                                                                                                                                      | High       |
| 5      | Owner question backlog: T12 metrics consumer card **→ routed to TODO_LIST (/metrics consumer card)**                                                                                                                                                                                                                                                                                                                                    | Medium     |
| 6      | Owner question backlog: T13 facade retention/timezone knobs **→ routed to TODO_LIST (webphone retentionDays facade)**                                                                                                                                                                                                                                                                                                                   | Low        |
| ~~7~~  | ~~Escalate the x86 infra-kill streak to GitHub support (run URLs already ledgered; rerun protocol exhausted)~~ done — reclassified 2026-10-06 — not infra: the 60-min job timeout, fixed by the per-system eval split + 120-min budget (AGENTS.md; ci.yml)                                                                                                                                                                              | ~~Medium~~ |
| 8      | Branch protection / CI failure notification (standing TODO; two red streaks sat unnoticed ~26h) **→ routed to TODO_LIST (branch protection application)**                                                                                                                                                                                                                                                                               | Medium     |
| 9      | `home-manager` input 123 commits behind (lock-doctor) — bump deliberately or document the pin **→ routed to TODO_LIST (home-manager input pin)**                                                                                                                                                                                                                                                                                        | Low        |
| ~~10~~ | ~~Decide + document Paperless fax-archiving posture for this stack (new upstream capability, off here; `paperless.url`+`token`)~~ done — evaluated in the 2026-10-25 deep-dive (paperless.* recorded off — docs/research/2026-10-25_webphone-deep-dive.html)                                                                                                                                                                            | ~~Medium~~ |
| 11     | Add 2-line suite asserts pinning `/livez` + `/startupz` vhost-reachability (T10 verdict is doc-only today) **→ routed to TODO_LIST (livez/startupz suite asserts)**                                                                                                                                                                                                                                                                     | Low        |
| ~~12~~ | ~~Diagnose buildflow's "9 tools unavailable (health check failed)" from the full run → done 2026-10-02 (`buildflow doctor`: global-PATH misses for cargo-*/eslint/codespell/interrogate; the pipeline provisions ruff/dprint/bandit/vulnix via the pinned `nix develop` env, which the same run proved by executing them — no gap)~~ done — 2026-10-02 doctor triage; devShells.default pins the load-bearing lint binaries (AGENTS.md) | ~~Low~~    |
| ~~13~~ | ~~Fix the `nix.nixPath` rename eval warning in `modules/telephony/ops.nix` (printed by every eval) → done 2026-10-02 (`nix.settings.nix-path`, rode the ffaa03fd5ce5 relock)~~ done at `ca146eb`                                                                                                                                                                                                                                        | ~~Low~~    |
| 14     | CHANGELOG gap (sibling lane): the shim-forward nixpkgs move (`b4fd65b`) has no CHANGELOG entry; lock-guard only fences webphone → open, widened 2026-10-02: the follow-up nixpkgs move to `c59305bab` (10-01 23:22 daemon sweep) is also unattributed — same class, still owner lane **→ routed to TODO_LIST (c59305ba attribution note)**                                                                                              | Medium     |
| ~~15~~ | ~~Consider consuming upstream's typed `csrf.trustedProxies`/`trustedOrigins` fronts instead of raw settings (now that they exist)~~ done — typed fronts consumed — modules/telephony/web.nix trustedProxies/trustedOrigins, rendered shape suite-pinned (tests/webphone.nix)                                                                                                                                                            | ~~Low~~    |
| 16     | Evaluate `serverTiming.enable` for the live host (new upstream diagnostic knob) **→ routed to TODO_LIST (serverTiming evaluation)**                                                                                                                                                                                                                                                                                                     | Low        |
| 17     | Operator window: consume the enriched `/version` endpoint (upstream added enrichment) **→ routed to TODO_LIST (operator /version consumption)**                                                                                                                                                                                                                                                                                         | Low        |
| 18     | `verify-live.sh`: add `/livez`/`/startupz` gates next to `/healthz` **→ routed to TODO_LIST (verify-live livez gates)**                                                                                                                                                                                                                                                                                                                 | Low        |
| 19     | Gate browser E2E CI on webphone lock-rev change (standing TODO row 34; this relock would have triggered it) **→ routed to TODO_LIST (browser E2E promotion)**                                                                                                                                                                                                                                                                           | Medium     |
| ~~20~~ | ~~If the dashboard is ever wanted: wire `settings.dashboard.enable` behind the operator basic-auth realm (verdict + seam recorded)~~ done — seam wired — services.telephony.webphone.dashboard.enable default-off, loopback-fenced mount (modules/telephony/options.nix + web.nix); verdict e0eafa1                                                                                                                                     | ~~Low~~    |
| 21     | Eval-check rendering `settings` with `dashboard.enable`/`paperless` on (upstream smoke coverage ≠ our config path) **→ routed to TODO_LIST (dashboard/paperless eval arms)**                                                                                                                                                                                                                                                            | Low        |
| ~~22~~ | ~~Re-run markers/lock-guard/drift after the sibling's next landing (daemon interleaving can shift files under gates)~~ done — CI runs the flake-check gate incl. lock-guard/markers/drift on every push (ci.yml); green capstone run 37555437689                                                                                                                                                                                        | ~~Low~~    |
| ~~23~~ | ~~Check upstream tag state vs the 2.8.0 CHANGELOG section (tags-trail-versions convention; footer citations depend on it)~~ done — upstream tags exist through v2.9.0 incl. v2.8.0 (~/projects/webphone git tag)                                                                                                                                                                                                                        | ~~Low~~    |
| ~~24~~ | ~~`tests/configjs_check.py`: confirm the contacts revert didn't drop wire keys it pins (round-trip green in E2E, but the check's key set deserves a glance)~~ done — superseded — the configjs fixture follows the current agent-key contract (CHANGELOG 2026-10-28); contacts now module-option-derived                                                                                                                                | ~~Low~~    |
| ~~25~~ | ~~TODO row 21's evidence cell still cites webphone rev `0e1d174` as "in flake.lock" — stale pointer after `f706575`~~ done at `19610ea`                                                                                                                                                                                                                                                                                                 | ~~Low~~    |
| ~~26~~ | ~~If `telephony-cdr-cancel` stays: move the MASTER-CSV dump BEFORE the `-ERR` assert so failures leave evidence~~ **NOT-DO — the check did not stay — restructured as telephony-cdr-visibility (78025ec) whose evidence prints precede the asserts.**                                                                                                                                                                                   | ~~Low~~    |
| ~~27~~ | ~~Consider a standing "probe evidence" convention: suites quote their probe lines into the log with greppable prefixes (partially exists: ORIGINATE/MASTER-CSV)~~ done — codified in AGENTS.md — probe evidence comes from the suites own asserted curls (greppable in nix log)                                                                                                                                                         | ~~Low~~    |
| ~~28~~ | ~~HARVEST §f into TODO_LIST/ROADMAP per docs-health (pending owner instruction; this snapshot alone must not be the tomb)~~ done (docs-health pass 2026-11-07)                                                                                                                                                                                                                                                                          | ~~Medium~~ |

## g) Questions I can NOT figure out myself

~~1. **Push policy under a sibling-red base:** my 6 commits are locally~~ done at 86f3d3d (pushed behind the capstone; origin run 37555437689 GREEN)
proven green; origin main already carries the sibling's code-red
`telephony-cdr-cancel` check, so no CI run can go green until it is
fixed regardless of my push. Hold (current state) or push-and-attribute?
~~2. **Lane ownership + sibling status:** is the sibling session still~~ done at 78025ec (saga closed — restructured as telephony-cdr-visibility, CHANGELOG 2026-10-03)
active on `telephony-cdr-cancel` (last move 11:12, suite rewritten
10:41), or should this lane take the fix/remove decision? I cannot see
their session state.
~~3. **Ratify the de-facto lock strategy:** the prior session's open fork~~ done — shim-forward is standing: FreeSWITCH builds under GCC 16 via the assert shim (CHANGELOG 2026-10-06); forward relocks since
(shim-forward vs back-pin) was settled by the sibling's commits, not
by an owner answer — confirm shim-forward (`nixpkgs b4fd65b` + assert
shim) is the standing strategy so the CHANGELOG's restore-era entry
can be understood as history, and so future relocks build on it.

---

_Point-in-time snapshot. Annotate, never rewrite. §b/§c/§f/§g items are
the open-work surface for markers; §a/§d/§e stay bare per house
convention._
