# Status: passkey lane shipped, CI infra-blocked release

- **Snapshot:** 2026-10-05 12:20 CEST
- **Scope:** this continuation session only — the three owner decisions executed after the 07:20 report (push ✓, passkey lane ✓, release ✗ blocked), the CI infra fight, and the daemon-push discovery. Carried-forward open items from the 07:20 report are marked as such. No new repo-wide research.
- **Tree state at snapshot:** `main` == `origin/main` at `6591dd7`; local full `nix flake check` GREEN on this exact content; lock-guard PASS; markers clean (72 files, 0 findings).

## a) FULLY DONE

- The three owner decisions from the question round were executed in safe order:
  1. **Push** — the relock lineage (`0048d35` relock, `e860627` runbook lesson, `5f9ba76` status report) is on origin.
  2. **Passkey lane — SHIPPED** as `7678967`: `services.telephony.webphone.passkey.*` wires the upstream passkey train (locked at `3928dbd`) into the stack — `rpId`/`rpOrigins` derived from the vhost domain, `users` email→extension mapping, password files DEFAULTING from the extensions' existing `passwordFile` options (per-extension override for inline-password setups), fail-closed eval assertions mirroring upstream boot validation, `usermgmt.db` added to the restic sqlite backups when the mode is on, demo host enabled with a store-plaintext file, operator enable+enroll recipe in the runbook ("Passkey surfaces"), FEATURES row, AGENTS.md stack description, two new docs/lessons/vm-testing.md traps.
  3. **Release — staged but NOT cut** (blocked; see c/d).
- Passkey lane verification: pbx + pbx-prod eval green, telephony-webphone VM suite green after three fix rounds (rendered config shape, conditional login DOM, `userauth` healthz leg, unknown-email 401 anti-enumeration, full CLI token lifecycle: runuser + the unit's `WEBPHONE_CONFIG` → mint → verify 200 → burned 503), fax + fax-feed suites green (off-shape regression), local full `nix flake check` green on the lane tree.
- CI fight fought by the book: 5 runs observed, every red diagnosed with the airtight verdict command — ALL five were `cancelled` with ZERO failed steps and aarch64 green (the documented runner-kill class, not code).
- New durable fact discovered and recorded (AGENTS.md `6591dd7`): **the auto-commit daemon also PUSHES** — eight heuristic lane shards landed on origin/main while a soft-reset recovery was in flight. Recovery was by rebase (`7678967` rebased on the shards), never force-push; the "unpushed, so soft-reset and re-author" remedy is now documented as a race, not a guarantee.
- Daemon-race recoveries: the lane's six local heuristic shards + one mid-lane CHANGELOG split were folded via `git reset --soft 5f9ba76` + one chained re-author; the CHANGELOG passkey attribution survived (verified by tree-diff against the remote shard head: identical except the 18-line entry).
- Upstream CI for the locked webphone rev `3928dbd`: success (checked earlier in this continuation).

## b) PARTIALLY DONE

- **Release v0.4.0** → ~90% staged: house style confirmed (annotated tag, `## [0.4.0] - 2026-10-05` heading, `release: vX.Y.Z — <wave>` commit), the atomic sequence is written, but the user's gate was "cut after CI green" and CI x86 is 5-for-5 infra-cancelled today. Blocked on external infra, not on work.
- **CI verdict watch** → protocol exhausted (3 reruns on the relock head per the documented cap; two fresh runs on the lane heads also cancelled). Escalation is the documented next step — owner lane.
- **§f harvest from the 07:20 report** → NOT routed to TODO_LIST/ROADMAP yet (waiting for instructions, per directive); this report adds more candidates.
- **Browser E2E passkey coverage** → deliberately NOT in scope: the WebAuthn ceremony stays upstream's island-tests (provider-seam stubs); our browser suite keeps the extension login (lifeline property). A ceremony E2E via CDP virtual authenticator remains an option — unstarted.
- The 119 stdlib python tests remain unrun this session (unrelated surface — messaging/voice agent; noted for completeness, not a gap in the shipped work).

## c) NOT STARTED

- Release cut (v0.4.0 tag + CHANGELOG versioning + `gh release create`) — sequence staged, blocked on CI.
- The CI x86 infra escalation itself (owner/support lane per the ledger).
- TODO_LIST/ROADMAP routing of §f from both reports (docs-health HARVEST).
- All carried §f items from the 07:20 report not since resolved (PMA exclusion, lock-guard scope question, nixpkgs sweep mystery, scheduled browser E2E lane, theme-check hardening, a0c78ca history surgery, bot toggle, stale branch, upstream BuildFlow/pma/git-hooks issues, …).

## d) TOTALLY FUCKED UP

Nothing shipped is broken — pushed HEAD is locally fully proven. Honest self-review of this continuation:

- **Four VM-suite runs before green; three were avoidable.** (1) The NixOS test driver TYPE-CHECKS the script — bare `re.search(...).group(1)` fails; the suite's own /metrics block already had the match-then-assert house pattern and I didn't re-read the file end-to-end before writing. (2) I asserted unknown-email 401 via anonymous curl BEFORE tracing the route groups — the CSRF middleware answers 403 pre-handler; one `server.go` read would have predicted it. (3) `systemctl show -p ExecStart --value` returns a `{ path=…; }` struct on current systemd, not a path — a full run burned on a "{"-prefixed assertion message. All three are now lessons-file'd, but each was a 25-minute VM cycle I could have bought back with ten minutes of reading.
- **The daemon pushed the lane in shards to origin before my re-author landed.** Result: origin history carries eight heuristic shards + my rebased attribution commit instead of one hand-authored lane commit. Content is identical (tree-diff proven: only the CHANGELOG entry differed) and lock-guard is green, but the commit convention outcome I was protecting was destroyed by my own assumption: I trusted the AGENTS.md claim "the daemon only stages and commits" instead of VERIFYING origin state during the delicate window. The stale claim was mine to doubt — the forensics note even says "only stages and commits" from a day when nobody had watched it push.
- **One wasted eval cycle on my own logging:** the chained pbx/prod eval with `tail -1` per step interleaved stdout/stderr so I misattributed which host threw `attribute 'name' missing`; the `listToAttrs` name/value bug itself was trivial. Marker-prefixed evals from the start would have saved the round trip.
- **The demo-host edit initially placed `environment.etc` inside `services.telephony`** — caught by reading back the edit before eval, but it should not have been written that way (I had just read the file and knew the block boundary).
- Carried from earlier today: the pipeline-masking bug and the guessed check name (both fixed and lessoned in the 07:20 report; they remain the day's signature mistakes).

## e) WHAT WE SHOULD IMPROVE

- **Read the whole target file before extending it** (the suite had the exact guard pattern I then wrote unguarded — the information was on screen an hour earlier).
- **Trace route groups + middleware BEFORE writing wire-level assertions** (`open` vs `protected` + the CSRF gate decided my 401-vs-403 outcome).
- **`/proc/PID/exe` and `/proc/PID/environ` are the ONLY unit-introspection surfaces the suites should use** — `systemctl show --value` shapes drift across systemd versions (both patterns now codified in docs/lessons/vm-testing.md; keep it that way).
- **Never trust a stale "the daemon only does X" claim during a delicate window — verify `git fetch` + origin state first.** The daemon-push fact is now in AGENTS.md; the practical rule is: re-author IMMEDIATELY after any soft-reset, expect remote shards, recover by rebase.
- **The relock ritual lacks a FEATURES/README lock-citation check** — FEATURES.md still cited `f706575` after two relocks; only the lane's doc pass caught it. Add "grep docs for the old short rev" to the ladder's commit step.
- **Release sequence should be a script, not prose** — the atomic sequence exists as chat history; it belongs in the runbook (owner decides: `scripts/release-vX.Y.Z` or a runbook block).
- **CI-resilience option worth costing out:** the x86 job (eval + packages + full VM battery) is a single long unit that keeps getting killed; splitting eval-only from VM-realization would let green partial verdicts count (BuildFlow-style fast-gates-first, now for CI).
- Keep the 3-strike discipline even when tempting to rerun a fourth time — today's 5 kills across 3 heads say the infra lane, not luck, is the fix.

## f) NEXT — up to 50 things († = carried open from the 07:20 report; others are this continuation's output)

**Tier 1 — do next session**
1. Cut v0.4.0 on the first green CI run — sequence staged (CHANGELOG versioning incl. the passkey `### Added` entry, annotated tag, push, `gh release create`) → open (blocked on infra)
2. Escalate the x86 CI infra-kill class (5 today; 2026-09-30 ledger precedent) to the owner/support lane → open (owner)
3. Decide the fallback release gate: is local-full-check-green + aarch64-green acceptable when x86 CI is infra-dead for days? → open (owner policy)
4. Route §f of BOTH today's reports into TODO_LIST/ROADMAP (docs-health HARVEST) → open
5. Add "grep docs for the old short rev" to the relock ladder's commit step (FEATURES/README staleness class — FEATURES cited a two-relock-old rev until today) → open (trivial)
6. Re-run `gh run list` when infra recovers and confirm a green verdict on `6591dd7` or newer → open
7. File the PMA daemon-push behavior upstream (own repo issue): pushes deserve at least a configurable local-only mode → open
8. † PMA: exclude flake.lock + CHANGELOG.md from heuristic commits (TWO shard-storms in one day now) → open (owner)
9. † Browser E2E: scheduled CI lane OR standing weekly ritual row (it rots silently outside checks) → open (owner policy)
10. † Solve the unidentified local `nix flake update` sweeps (nixpkgs moved unattributed 10-02→03; still unsolved) → open (owner knowledge)
11. † lock-guard scope decision: webphone-only vs nixpkgs/home-manager attribution → open (owner)

**Tier 2 — hardening (this month)**
12. † Theme FOUC check robustness: load precondition + wider settle budget + one retry → open
13. † `scripts/relock-attribution` helper (base/new lock snapshot + restore in one command) → open
14. † `scripts/relock-commit` atomic helper (lock update + CHANGELOG + commit chained) → open
15. Passkey: browser-ceremony E2E via CDP virtual authenticator (enroll + login ceremony end-to-end in `telephony-browser`) → open
16. Passkey: extend the sops-nix recipe in docs/secrets.md with the webphone-readable owner/group note for `telephony_ext_<n>` (the runbook references it; the secrets doc should show it) → open
17. Passkey: consider a `telephony-webphone-enroll` wrapper unit/script (resolves WEBPHONE_CONFIG + /proc/exe itself; drops the two-line shell dance) → open
18. † Rendered-passkey-shape assertion could move into `checks.telephony-eval` (eval-time, free) instead of VM-only → open (low)
19. † AGENTS pointer line to the runbook flake-signature section (07:20 report item, still open) → open (trivial)
20. † Runbook gate-4 row: full check names (`telephony-fax`, `telephony-fax-feed`) → open (trivial)
21. † Deprecated `nix flake lock --update-input` → `nix flake update webphone` in runbook/AGENTS/lessons → open (trivial)
22. † Stall-DIAG: capture `__wpTheme` counters + chromedriver-theme.log in the browser E2E diagnostics → open
23. † Explain the two divergent flake-parts nodes in flake.lock (`flake-parts_2` behind) → open
24. † nixpkgs 1745 behind: plan a pinned bump lane → open
25. † home-manager input 152 behind → open
26. Re-verify `scripts/heal-pre-commit-hook.sh` after next pull (standing ritual) → open
27. † Daemon-race frequency watch: 3 incidents today (1 diagnosis-time, 1 commit-split, 1 push-storm) — if PMA gets no exclusion, consider a local `pre-push` hook that refuses heuristic-message commits touching flake.lock → open
28. † DOMAIN_LANGUAGE: "base-attribution", "enrollment token", "usermgmt.db" as ritual vocabulary → open
29. CI split proposal: eval-only job + VM-realization job (green partials count; kills stop nuking everything) → open (owner cost call)

**Tier 3 — carried documented-backlog re-confirmations (unchanged, not re-researched)**
30. † Owner toggle "Allow GitHub Actions to create and approve pull requests" (flake-update bot) → open (owner)
31. † Delete stale `chore/flake-update-2026-09` branch → open (owner)
32. † a0c78ca DID literal history surgery → open (owner)
33. † CDR mid-ring ORIGINATOR_CANCEL live-host reproduction → open
34. † BuildFlow#25/#26/#27/#28 upstream items → open
35. † pma#341 (dead skip_hooks) → open
36. † git-hooks.nix#754 (hook healing) → open
37. † nix-ssh-config#5 (unmerged lock-update branch) → open
38. † vulnix ~68-advisory build-closure noise class → open (low)
39. † scrub-check canary after next hook heal → open
40. † lock-doctor after the bot's next PR (webphone exclusion still holds) → open
41. † Sibling webphone checkout: owner commits/discards the dirty docs file → open (owner)

**Tier 4 — product/roadmap**
42. † Passkey for pbx-prod: the wrapper is ready (`passkey.enable` + users + sops files); enablement on the prod template is an owner product decision with CHANGEME-marker shape → open (owner)
43. † Release cadence after v0.4.0 (v0.5.0 candidates: passkey prod enablement, browser ceremony E2E) → open
44. † CDR visibility live-host verification → open
45. † Fast theme-check-only browser suite for relock rituals → open
46. † lock-doctor: also print upstream CI verdict for the TARGET rev → open
47. † Runbook: relocks may chase a newer tip than surveyed (main moves mid-ritual) → open
48. † Move gate-2 before gate-1 in the ladder docs (binary proof possible pre-relock via input rev) → open (low)
49. Annotate the 07:20 status snapshot's §b rows that this continuation resolved (push ✓, questions ✓, CI verdict ✓-blocked) per the marker convention → open (post-report)
50. Post-release: `git push --tags` hygiene check + `gh release view v0.4.0` verification → open (follows item 1)

## g) Questions I cannot figure out myself

1. **Release authority under dead CI:** v0.4.0's gate was "after CI green". x86 CI is 5-for-5 infra-cancelled today with aarch64 green and local full-check green. Should I (a) auto-cut the release on the first green CI whenever it lands, (b) accept local-full-check-green as a sufficient gate and cut now, or (c) hard-wait for your explicit go? Only you can set the risk posture.
2. **The daemon pushing to main:** heuristic auto-commits now reach origin without review (eight shards today). Is main-push by the daemon acceptable as-is, should it be config-limited to local-only commits, or should relock-sensitive paths (flake.lock, CHANGELOG.md) be excluded from heuristic commits entirely? This is a projects-management-automation owner decision.
3. **The x86 CI killer:** five cancellations today, ten in the 2026-09-30 ledger, always mid-eval, aarch64 always green, zero failed steps. Is this the known GitHub runner-shutdown infra lane you'll escalate — or do you want the workflow restructured (split eval-only from VM realization) to shrink the blast radius? I cannot see runner-level telemetry or your support history.
