# Status Report: Operator tooling baseline + pinned nixpkgs registry (ops-tools session)

- **When:** 2026-09-17, session ~14:05–19:45 CEST (background VM batches spanned the full window; last check batch finished ~19:19 CEST)
- **Trigger:** user SSH'd into the live host `pbx.artmann.tech` and hit: `htop`/`btop` missing, `nix run nixpkg#btop` failing on disabled `nix-command` → `flakes`, then a `nixpkg` vs `nixpkgs` typo. "Why don't we even have the basics!?!?"
- **Scope:** this report covers THIS session's work only (ops tooling baseline). A concurrent agent session was active on the operator window / fax / conference work (`tests/operator.nix`, `operator.js`, `app.js`, status report `2026-09-17_14-06_*`); its state is noted where it intersects, not audited.
- **Format note:** canonical status-report format is a styled HTML dashboard; the user explicitly requested `.md` — honored (one-off override, not propagated back into the skill).

## The fix in one paragraph

New module `modules/telephony/ops.nix` behind `services.telephony.opsTools.enable` (default **true**), imported by the `services.telephony` module so **both example hosts and every external consumer** get it: btop, htop, dig, tcpdump, jq, lsof, sqlite, tmux, vim, openssl on the host shell; `nix.settings.experimental-features = [nix-command flakes]`; `nix.registry.nixpkgs` pinned to `pkgs.path` (the exact nixpkgs source the running system was built from); `nix.settings.flake-registry = ""` (disables the global registry — the load-bearing half, see lessons); `nix.nixPath = [ "nixpkgs=flake:nixpkgs" ]`. Asserted in `tests/pbx.nix`; opted out in `tests/boot.nix` to keep the TCG guest minimal. Docs: ops-runbook "On-host tooling", README options tour, FEATURES, CHANGELOG, DOMAIN_LANGUAGE, lessons (operating + vm-testing), AGENTS.md hard-won bullet.

## a) FULLY DONE

| Item | Evidence |
| --- | --- |
| `modules/telephony/ops.nix` — operator tooling + nix CLI baseline | In `HEAD` (daemon commit 14:14 + later); eval-proven via both toplevels (`pbx`, `pbx-prod` force-evaluated clean) |
| Option `services.telephony.opsTools.enable` (default true) in `options.nix` | Eval of both toplevels passes; unknown-option would have failed eval |
| Module wired into `modules/telephony/default.nix` imports + header layout comment completed (monitoring/security lines were stale-missing pre-session — fixed on sight) | `git show HEAD` verified |
| `tests/pbx.nix` operator-tooling assertions: 10 tool version probes, `experimental-features` in `/etc/nix/nix.conf`, `nix registry list` → exactly one `system flake:nixpkgs path:/nix/store/…` line, no `global` entries, pinned source present in guest (`test -f <path>/flake.nix`) | `checks.telephony` multi-node suite **PASSED** (3rd run) |
| `tests/boot.nix` opts out (`opsTools.enable = false`) with rationale | `checks.telephony-boot` PASSED |
| Root-cause proof: nix 2.34 eagerly loads the global flake registry for ANY indirect ref and a failed fetch is FATAL even when the local entry matches exactly (reproduced via `NIX_CONF_DIR` + `registry.json` sandbox; user-registry shadowing identified as the confound) | Documented in `docs/lessons/operating.md` (three traps) + AGENTS.md bullet |
| Second root-cause proof: any command that LOCKS a path input (`nix flake metadata nixpkgs`) hashes the whole nixpkgs tree → virtiofsd fd-passthrough exhaustion in shared-store VMs (64k fds) | Documented in `docs/lessons/vm-testing.md` |
| Docs: ops-runbook "On-host tooling" section (tool table, `nix run nixpkgs#ngrep` example, `nixpkg` spelling trap), README options-tour bullet, FEATURES row, CHANGELOG `[Unreleased] → Added` entry, DOMAIN_LANGUAGE row | treefmt/docs-drift green after edits |
| Fast gates: buildflow fast (statix/deadnix/…), treefmt, docs-drift, telephony-eval | All green with `set -o pipefail` discipline |

## b) PARTIALLY DONE

| Item | Done | Missing |
| --- | --- | --- |
| `nix run/shell nixpkgs#<tool>` on a real deployed host | Proven piecewise in the VM (flakes active, registry pinned offline, source aboard) and locally in a bare-host sandbox | Never executed end-to-end on real hardware — VM framework cannot hash path flakes (virtiofsd fd cap), and `pbx.artmann.tech` still runs the OLD system until the user rebuilds |
| Full `nix flake check` green | 19 of 20 checks realize green (incl. metal-boot, prod-boot, secrets, voicemail) | `telephony-operator` is RED — the **concurrent session's committed WIP** (their JSON-quoting bug in `tests/operator.nix`: quotes stripped in a `python3 -c` one-liner → garbage `audio_url` → failing curl). Not my file; left untouched per "never revert/fix what you didn't author" |
| Registry/CLI coverage of legacy paths | `nix.nixPath` replaced with `nixpkgs=flake:nixpkgs` (standard flakes-host idiom), eval-verified | Runtime legacy behaviors (`nix-shell -p`, `nixos-option`) unexercised |
| FEATURES row accuracy | Rewritten twice until it matched the shipped assertion exactly | — |

## c) NOT STARTED (deliberate, observed but untouched)

- `docs-health` HARVEST of section (f) into `TODO_LIST.md`/`ROADMAP.md` (this report is the input; user said report-then-wait).
- Release: CHANGELOG `[Unreleased]` is piling up (research snapshots, disk layout, ops tooling, …) — no tag cut this session.
- Demo-VM banner (`hosts/pbx`) doesn't mention the new tools (btop etc. work there now).
- `docs/deploy.md` has no post-install verification section pointing at the runbook tooling.
- virtiofsd `--rlimit-nofile` bump (would re-enable path-flake hashing inside VM tests) — upstream/framework territory, not probed.
- Whether nix's eager-global-registry behavior deserves an upstream issue (verify-before-filing flow not started).
- `scripts/ahead-check.sh`: appeared staged at session start, later committed by the daemon; purpose unknown to this session — needs review or deletion (possible debris).
- Pre-existing lychee errors observed during `buildflow format` (not mine, untouched): `docs/research/2026-09-16_fspbx-trial.md` (127.0.0.1 TLS link) and `packages/telephony-operator/webroot/index.html` (root-relative `/favicon.svg`, `/operator/operator.css`).

## d) TOTALLY FUCKED UP

Nothing destroyed and nothing shipped broken — but four honest failures, two of which are repeats of documented lessons:

1. **I repeated the pipeline-masking mistake class twice** — `nix build … | tail && echo GREEN` printed a green banner while the format check was RED (the repo's AGENTS.md documents exactly this trap; `set -o pipefail` is the mandated fix). I then did it again on an experiment `echo exit=$?` after a pipe. Known lesson, repeated anyway. The only mitigation: both lies were caught within one step because adjacent gates disagreed.
2. **Shipped an incomplete registry design first**: v1 of `ops.nix` pinned `nix.registry.nixpkgs` but did NOT disable the global registry — offline resolution still aborted. Found only because I wrote the VM test (the test earned its keep); a source-level read of nix's resolution order up front would have caught it pre-flight. Cost: one full VM cycle (~10 min).
3. **Designed a test assertion invalid for its environment**: `nix flake metadata nixpkgs` hashes the whole nixpkgs tree and blew up virtiofsd's fd pool in the shared-store VM. A cheaper probe with the same proof power (`nix registry list`) existed and should have been chosen first. Cost: another VM cycle.
4. **Whole-tree `buildflow format` in a repo with a concurrent active session**: swept the other session's WIP files (`operator.js`, docs) through my formatter run and blurred session boundaries in daemon history. Mechanically safe (formatter-verified, no logic change) but sloppy hygiene under concurrency.

Not-fucked-up-but-worth-admitting: `FEATURES.md` churn (wrote the row referencing an assertion I later replaced); a `multiedit` that briefly duplicated `monitoring.nix`/`security.nix` imports (caught in one step); one statix `inherit` nit in fresh code (caught by the gate, as designed).

## e) WHAT WE SHOULD IMPROVE

1. **Gate commands get `set -o pipefail` unconditionally** — no banner unless the pipeline's own exit code says so. This bit me twice in one session; make it muscle memory, not a lesson to re-learn.
2. **Design test probes for the runtime environment first** (shared-store VM = no path-flake hashing, no network). Cheapest probe that still proves the chain should be the default; heavyweight end-to-end probes are for real-host smoke tests.
3. **Read the tool's resolution semantics BEFORE building on them** (nix registry lookup order: user → system → global, global eager-fetched). Two of three VM iterations traced back to assuming instead of reading.
4. **Concurrency protocol**: before whole-tree formatters/quality runs, `git status` + check for a fresh `docs/status/*` from another session; scope formatter runs to my files when the tree is shared.
5. **Verify user-facing fixes on the target surface** — VM-green ≠ host-green; the report should have led with "live host not yet fixed" instead of burying the rebuild step at the end.
6. **Doc rows should reference assertions after they settle**, not before (avoids rewrite churn like the FEATURES row).
7. Daemon-interleaved history is unavoidable here, but per-task explicit commits (when authorized) would keep session boundaries readable — this session relied entirely on heuristic daemon commits for my own work.

## f) Up to 50 things we should get done next

Sorted by impact; owner tags: [user], [me], [other-session], [upstream]. This section is the HARVEST input for TODO_LIST/ROADMAP.

1. [user] Rebuild `pbx.artmann.tech` from this change (bump the private deployment flake's input → `nixos-rebuild switch --flake .#pbx-prod --target-host`) — the live host still lacks the basics until then.
2. [user] Post-rebuild smoke on the host: `btop --version`, `dig CAA artmann.tech +short`, `openssl version`, `nix run nixpkgs#jq -- --version`.
3. [other-session] Fix the committed `tests/operator.nix` quoting bug (JSON quotes stripped in the `python3 -c` one-liner → `audio_url` garbage → curl exit 23).
4. [me/CI] Re-run full `nix flake check` end-to-end once the operator suite is green — CI is presumably RED on `main` right now from that committed WIP.
5. [me] HARVEST this report's (f) into `TODO_LIST.md` / `ROADMAP.md` (docs-health HARVEST mode).
6. [user/other-session] Confirm whether the concurrent agent session is still active before anyone else touches `tests/operator.nix`, `operator.js`, `app.js`, `api.py`.
7. [upstream/nix] Verify-then-file the nix behavior finding: eager global-registry fetch aborts indirect-ref resolution offline even when the local registry matches (nix 2.34.8) — follow verify-before-filing + github-voice.
8. [me] Investigate raising virtiofsd `--rlimit-nofile` in the test framework (or upstream nixpkgs) so path-flake hashing becomes VM-testable again; then upgrade the `tests/pbx.nix` piecewise asserts back to one real `nix flake metadata nixpkgs` call if feasible.
9. [me] Add a runbook troubleshooting entry for the two nix failure modes (offline registry abort; `nixpkg` typo) — runbook section exists, the failure-ladder framing doesn't.
10. [me] Update the demo-VM banner (`hosts/pbx`) to mention btop/htop/dig availability.
11. [me] `docs/deploy.md`: add a post-install verification section (first-call runbook already exists; anchor it to the new on-host tooling).
12. [me] Review `scripts/ahead-check.sh` (unexplained staged-then-committed file; delete or document).
13. [me] Cut the pending release: CHANGELOG `[Unreleased]` → version, tag, `gh release create` (project release flow).
14. [me] Point `docs/deploy.md` §secrets at the on-host `openssl` availability (the `nix shell nixpkgs#openssl` workaround is obsolete on new hosts).
15. [me] Consider `nix.gc.automatic = true` on `pbx-prod` (small disk, growing closures; owner decision).
16. [user] Tool-set taste call: keep both `htop` + `btop` (and `vim` + `tmux`), or trim the baseline.
17. [user] Confirm no host workflow needs indirect flake refs other than `nixpkgs` — `flake-registry = ""` stops `nix run <other-flake-id>` from resolving.
18. [me] README architecture section: one line on the pinned-registry posture (README sells; currently only the options tour mentions it).
19. [me] Add `opsTools` to `FEATURES.md` "Host integration (example hosts)" cross-reference if docs-drift ever flags it (it doesn't today — skip unless flagged).
20. [me] Legacy `<nixpkgs>` runtime spot-check: `nix-shell -p hello` style probe on a rebuilt host (nixPath change is eval-verified only).
21. [other-session] Pre-existing lychee errors: fspbx research doc (localhost TLS link) + webroot root-relative links — fix or exclude in `lychee.toml`.
22. [me] Consider exporting the "three traps" as a reusable check in the deploy docs (operator onboarding).
23. [me] Annotate + archive this report once its items are resolved (docs-health ANNOTATE → `docs/status/archived/`).
24. [me] Aggressive-update protocol: project AGENTS.md now carries the registry/fd-cap bullet — re-check wording after any nixpkgs nix version bump (behavior may change upstream).
25. [me] `nix.settings.flake-registry = ""` interaction with `nix registry pin` workflows — document or explicitly declare unsupported.
26. [me] Evaluate `pkgs.dig` vs `pkgs.dnsutils` alias stability (used `pkgs.dig`; both resolve to `bind.dnsutils` today).
27. [me] Assert `nix.nixPath` effective value in a VM test (currently set, unasserted).
28. [me] opsTools: consider an `opsTools.extraPackages` passthrough (optAdditive escape hatch) — likely YAGNI, note and defer.
29. [me] Check `metal-boot`/`prod-boot` closure growth from the default-on tools (measured fine this session; re-check on slow CI runners).
30. [me] The boot-tcg suite disables opsTools — verify the disable path keeps the guest truly minimal (closure diff, one-off).
31. [me] Sweep for other places assuming `nixpkgs#` ad-hoc installs work and reference the runbook instead (docs/secrets.md `nix shell nixpkgs#age-keygen` is admin-side, fine; grep for target-host variants).
32. [me] Consider adding `ngrep` (or `tcpdump` examples) coverage claim accuracy: runbook table says `tcpdump` ships — true; the ngrep example pulls ad-hoc — verify `nix run nixpkgs#ngrep` on a real host post-rebuild.
33. [me] Update `docs/lessons/operating.md` if nix changes the eager-registry behavior (tie to #24).
34. [me] Run `buildflow doctor` — 9 tools were "unavailable (health check failed)" in the fast run; identify which and whether any mattered.
35. [me] The `nix run nixpkg#…` typo class: nothing to fix in-repo (can't patch user typos), but the runbook documents it — done; consider a shell alias suggestion for serial offenders.
36. [user] Decide whether the private deployment flake should ALSO pin its registry independently (defense in depth) or rely on the module.
37. [me] Explore `nix.settings.trusted-users` / substituter posture for the host while in the settings area (not changed this session; confirm defaults are intended).
38. [me] Add the virtiofsd fd-cap finding to the browser-E2E docs if `legacyPackages.telephony-browser` ever runs nix commands inside the guest (it doesn't today — note only).
39. [me] Repo has two example hosts with divergent systemPackages (restic on prod only) — document that opsTools is module-level while host-specific tools stay host-level (one-home-per-fact cross-check).
40. [me] Sweep `docs/planning/2026-09-17_08-05_first-call-to-daily-driver-round2-pareto-plan.md` for items this session accidentally advanced (e.g. demo-VM ssh smoke row) and annotate them.
41. [me] `statix.toml`/`deadnix` coverage of `modules/telephony/ops.nix` confirmed by gates — no action; keep new files inside the gates (habit note).
42. [me] Check whether `nix.registry` pin survives `nixos-rebuild --upgrade`-style flows on the host (registry points at `pkgs.path` = the BUILD's nixpkgs; next rebuild re-pins — confirm no stale-registry trap after rebuilds).
43. [me] Domain-language: "operator tooling baseline" row added; keep future host-shell concepts in `DOMAIN_LANGUAGE.md` rather than ad-hoc prose.
44. [me] `CHANGELOG.md` entry wording ties the fix to `opsTools.enable` default-on — ensure the eventual release notes carry the "rebuild required to take effect" callout.
45. [me] Consider a `telephony-ops-tools` dedicated fast check if the multi-node suite ever becomes too slow to iterate on (currently fine — pbx suite ran in ~2 min).
46. [me] Upstream-adjacent: the virtiofsd fd message (`guest_fd_limit`) names the knob — a one-line PR or issue to nixpkgs' VM framework could help everyone (verify-before-filing first).
47. [me] Confirm `nix flake metadata nixpkgs` works on the REAL host post-rebuild (it should; hashing is seconds on local disk) and record the actual timing in the runbook.
48. [me] Session-hygiene retro item: my three-iteration test loop is the normal red→green cost — but pre-flight sandbox experiments (like the `NIX_CONF_DIR` repro) BEFORE the first VM run would have compressed it; adopt "sandbox first, VM second".
49. [me] Keep `scripts/scrub-check.sh --history --strict` in the loop before any future squash that absorbs daemon commits mixing sessions (this session's 32-file daemon commit mixes two sessions' work).
50. [user] Priority call between this lane (ops tooling polish) and the other session's lane (operator window) — both touched `pbx.nix`-adjacent wiring; avoid merge-by-daemon.

## g) Questions I can NOT figure out myself

1. **When should `pbx.artmann.tech` be rebuilt** — do you want this live now (bump the private flake, rebuild), or batched with the operator-window work from the other session? I cannot rebuild your prod host from here, and the fix is inert until you do.
2. **Is the concurrent agent session still active on `telephony-operator`?** Its committed WIP leaves `checks.telephony-operator` RED (JSON-quoting bug) and therefore `nix flake check` / CI red on `main`. May I fix its test, or is that file yours to finish?
3. **Does anything on the host need indirect flake refs other than `nixpkgs`** (e.g. `nix run nixos-unstable#…`, `home-manager`, custom flake ids)? `opsTools` disables the global registry on purpose; those refs stop resolving. If you need them, the right shape is extra pinned `nix.registry` entries, not re-enabling the global one.
