# Status Report — M32–M34 landed; CI freeze narrowed to a sofia profile wedge

**Date:** 2026-08-22 03:51 CEST
**Session scope:** Executed the remaining Pareto plan mediums M32 (test split),
M33 (ops runbook + diagram), M34 (aarch64 validation), plus the M20 CI
investigation that consumed most of the session. This report covers only this
session's work.

## TL;DR

- M32 and M33 are **done and pushed**. M34 is ~80% done (all aarch64 builds
  prove out; VM boot and the FEATURES row remain).
- M20 (CI green) went **backwards and then forwards**: three red CI runs, but
  the boot diagnostics I landed captured the first hard evidence — on CI and
  locally. The freeze is now a **narrowed, locally reproducible (~40% on the
  multi-node suite) sofia profile-start wedge**, not a scheduler/starvation
  problem, not a boot-contention problem.
- One landed prose claim (CHANGELOG/module comment: SCHED_FIFO causes the
  freeze) is **disproven by my own later evidence** and needs rewording.

## a) FULLY DONE

| Item                                  | Evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **M32 — test suite split**            | `tests/common.nix` (shared `baseNode` fixtures + `bootWait` helper); `tests/dialplan.nix`, `tests/webphone.nix`, `tests/tls-turn.nix` single-node suites; `tests/pbx.nix` slimmed to the multi-node scenarios (recordings serving, gateway, escape hatch); all four wired as flake checks (`telephony`, `telephony-dialplan`, `telephony-webphone`, `telephony-tls-turn`). Single-node suites green locally: **84.8 s / 39.2 s / 28.1 s**. Commits `76a49d4`, `d96484b`.                       |
| **M33 — ops runbook + diagram**       | `docs/ops-runbook.md` (service inventory, fs_cli cheat-sheet, health-check block, cert rotation for all three `tls.mode`s, gateway REG-state table with actions, recordings + TURN credential rotation, emergency actions); Mermaid architecture diagram + updated layout table + links in README; AGENTS.md points at the runbook. Claims verified against module code and the vanilla FS config (caught and fixed a wrong voicemail-path claim before commit). Commits `76a49d4`, `195bf3a`. |
| **M34.1 — aarch64 builds**            | `webphone` cross-built as a genuine aarch64 derivation (`nix derivation show` → `"system":"aarch64-linux"`); `freeswitch-sounds` built; nixpkgs `freeswitch-1.11.1` cross-built within 45 min (store path `9s4h95hd…`). Full aarch64 NixOS system **evaluation** with our module succeeds (only generic minimal-host assertions fire; none from `services.telephony`).                                                                                                                         |
| **Boot-failure diagnostics in tests** | `wait_for_freeswitch()` in `tests/common.nix`: bounded timeouts + on failure dumps unit state, `ps`, `/proc` (wchan/syscall/kernel-stack/thread count), `ss`, journal tail, dmesg — wired into all four suites. **First CI run already produced decisive evidence** (see M20 section).                                                                                                                                                                                                         |
| **Doc sync**                          | TODO_LIST: M32/M33 rows deleted as done, M20 → IN_PROGRESS, aarch64 row narrowed to "VM boot". FEATURES: per-component-suites + ops-runbook rows added. CHANGELOG: entries for suites, runbook, scheduling override, diagnostics. Verified after daemon commits that the rows survived.                                                                                                                                                                                                        |

## b) PARTIALLY DONE

| Item                         | State                                                                                                                                                                                                                                        | What remains                                                                        |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **M20 — CI green**           | Three consecutive red runs (`32529436940` lazy-boot only; `32531293026` suites commit; `32537142983` incl. SCHED_FIFO override + diagnostics, failed in 6m38s). The daemon pushed everything; remote `origin/main` = `4f5d012` = local HEAD. | Root-cause (or explicit mitigation), one green run, cite it in the FEATURES CI row. |
| **M34 — aarch64 validation** | Builds + eval done (see a).                                                                                                                                                                                                                  | FEATURES aarch64 row update; optional aarch64 VM boot; final commit.                |

### The M20 evidence (new this session)

The diagnostics fired on CI (`32537142983`) and in two local failures
(`/tmp/tel-attempt-1.log`, an earlier `nix build -L` run). Consistent picture
across CI and local, on any node (machine, machine2):

- freeswitch process **alive, sleeping, ~1–2% CPU** — not spinning, not
  livelocked; main thread in `pselect6` (the console loop — init "finished"
  from the main thread's perspective); 23 threads.
- `ss -ltn`: **5066 (sofia WS transport) and 8021 (event socket) are bound;
  5060/5061/5080 are not.** The internal profile start wedged after the WS
  bind, before/at the SIP bind.
- systemd shows `active (running)`, `Type=simple` (so `wait_for_unit` passing
  means nothing — only the port wait catches this).
- Journal tails differ between runs (nat.auto list in some, sndfile module
  output in others) → the "always stops at nat.auto" reading was journal
  truncation, not the freeze point.

**Eliminated theories:** boot contention/`start_all` (reproduced with a single
VM up, lazy boot active); `SCHED_FIFO` starvation (reproduced with
`CPUSchedulingPolicy = "other"` both locally and on CI); host CPU pressure
(prior session's `taskset` tests).

**Reproduction:** multi-node `telephony` suite failed 2 of ~5 forced local
runs; single-node suites 0 failures in ~6 runs (sample too small to call them
immune). CI: 3 of 3 runs failed.

## c) NOT STARTED

- Root-cause fix (or decided mitigation) for the sofia profile wedge.
- v0.2.0 tag + release (gated on CI green; CHANGELOG Unreleased is large).
- B1 secrets manager, B2 browser E2E, B3 directory rename — all still blocked
  on user decisions from the prior session's report.

## d) TOTALLY FUCKED UP (honest ledger)

1. **Pushed hope twice.** The lazy-boot fix and then the SCHED_FIFO override
   were both framed as fixes on theory, before evidence. The lazy-boot change
   is harmless and kept (staggering is still sensible); but the CHANGELOG and
   module comment claim SCHED_FIFO caused a "CI-only livelock … during core
   init" — **my own later evidence disproved exactly that** (it reproduces
   under CFS locally, and the wedge is after init's main path, at profile
   start). The claim must be reworded to "hardening"; the freeze is unsolved.
2. **Diagnostics were one revision behind the bug.** First draft used `pidof`
   (absent in the guest; caught before commit). More importantly they dump
   only the **main** thread's stack — which is exactly where the bug ISN'T.
   Per-thread dumps (`/proc/PID/task/*/comm|wchan|stack`) are still missing,
   and we didn't use the live event socket (8021 is up during the wedge —
   `fs_cli 'sofia status'` could interrogate sofia mid-wedge before the VM
   dies).
3. **aarch64 false positive:** `nix build --system aarch64-linux` was silently
   ignored ("not a trusted user") and built x86_64; I briefly reported it as
   success. Caught by checking the derivation's `system` field; redone via
   `.#packages.aarch64-linux.*`. Lesson: verify the platform in the drv, not
   the exit code.
4. **Session restart killed background jobs** (test loop + aarch64 builds)
   — known risk from the handoff; restarted both, but one test-loop result
   was lost.
5. **Unchecked background job for ~3 h** (freeswitch aarch64 cross-build) —
   it had succeeded; luck, not discipline.
6. Three burned CI runs (~40 min of shared-runner time) on unverified
   theories.

## e) WHAT WE SHOULD IMPROVE

- **Evidence before fix, always, for environment-dependent bugs:** land
  diagnostics → capture one reproducing run's evidence → then theorize.
  This session did that order only the second time around.
- **Interrogate the live system before killing it:** the wedge leaves fs_cli
  usable (8021 up); future failure paths should query sofia in-place.
- **Verify claims, not exits:** derivation platform, journal-tail truncation,
  `Type=simple` semantics — all bit us because a green checkmark or a log tail
  was mistaken for ground truth.
- **When a theory dies, fix the prose the same session** (CHANGELOG, module
  comment, TODO row) — it is still unfixed at the time of this report and
  must not fossilize into a release.
- Keep long builds restart-survivable (out-link + explicit exit-status file).

## f) NEXT (ranked, ~30 items)

**Wedge evidence & root cause**

1. Add per-thread dumps to `bootWait` (`/proc/$pid/task/*/comm`, `wchan`, `stack`).
2. On wedge, run `fs_cli 'status'`, `'sofia status'`, `'sofia status profile internal'` via the live 8021 socket before raising.
3. Local repro loop with `--rebuild` on the multi-node suite; measure the rate on single-node suites too (larger sample).
4. Boot the demo VM (`nix run .#vm`) ×20 — does a non-test QEMU boot wedge?
5. Bisect topology: single-NIC test node (drop the second `virtualisation.vlans` NIC; coturn bound `192.168.1.1` = eth1 — multi-NIC + `getifaddrs`/NAT detection interplay is a prime suspect given our AF_NETLINK history).
6. Try `freeswitch -nonat` in a throwaway test (disables NAT auto-detection).
7. Try dropping our `RestrictAddressFamilies` override in a repro loop (isolate our hardening as a factor).
8. Read the fetched FS source (`/tmp/fs-src`) around internal-profile start: code between WS bind and SIP bind; look for DNS/`gethostbyname`/timing-dependent blocking.
9. Search upstream (signalwire/freeswitch, nixpkgs) for "5066 binds 5060 doesn't" / QEMU / interface-enumeration hangs.
10. Candidate mitigation (needs your call, see Q2): on port-wait timeout → dump diagnostics → `systemctl restart freeswitch` → retry once; keeps CI green-with-evidence while root-causing.

**Correctness of what already landed**
11. Reword CHANGELOG + module comment + TODO_LIST M20 row: SCHED_FIFO override = hardening, NOT the freeze fix (it failed CI run `32537142983`).
12. Re-verify the three single-node suites still pass after any diagnostic changes; full `nix flake check` before pushing again.

**M20 completion**
13. After fix/mitigation: push, `gh run watch`, cite the green run URL in the FEATURES CI row, flip TODO row to done, delete row.
14. Consider `--all-systems` in CI once green (aarch64 eval is already proven).

**M34 completion**
15. Update the FEATURES aarch64 row: packages cross-built (webphone, sounds, nixpkgs freeswitch), full-system eval OK, boot untested.
16. Optionally attempt a real aarch64 boot (qemu-aarch64 VM test or cross `run-pbx-vm`); otherwise record "boot untested" honestly and park it.

**Release & hygiene**
17. Post-green: cut CHANGELOG → v0.2.0, tag, `gh release create`.
18. Commit this status report (verify daemon didn't mangle it).
19. Add the drift-alarm check (fail if TODO_LIST rows duplicate FULLY_FUNCTIONAL FEATURES rows).
20. `nix develop -c pre-commit run --all-files` over the new files (webphone/common tests, runbook).
21. If root cause lands upstream-worthy: nixpkgs PR on the freeswitch unit (unbounded SCHED_FIFO default is a footgun regardless of our freeze).

**Blocked on user (carried over)**
22. B1 secrets manager choice (sops-nix vs agenix) — highest-impact remaining item.
23. B2 browser E2E with chromium (~1–2 GB closure).
24. B3 local directory rename to match the public repo.

## g) Questions I cannot answer myself

1. **SCHED_FIFO override:** keep it (my recommendation — unbounded RT without
   a budget is a genuine footgun) with corrected "hardening" wording, or
   revert entirely to keep the diff honest-to-intent until the real cause is
   known?
2. **Mitigation policy:** if root-causing stalls, is a test-side
   "diagnose → restart freeswitch → retry once" acceptable to get CI green
   (explicitly documented as masking), or must the gate stay strictly red
   until truly fixed — noting that blocks v0.2.0 and everything behind a
   green badge?
3. **Instrumentation appetite:** may I add temporary heavy tooling to the VM
   test closure (strace, or debug symbols + gdb) and/or push experimental
   repro-loop commits, or should such experiments stay local/branch-only to
   keep CI lean?

**Now waiting for instructions.**

---

## Annotation (2026-08-22, ~04:15 — later session, READ THIS FIRST)

**The §b "sofia profile-start wedge" diagnosis above is wrong. There is no wedge.**

The DIAG dump from CI run `32537142983` (landed after this report was written)
disproved it: `ss -ltn` shows 5060/5061/5080 **bound — on `10.0.2.15` (eth0)** —
alongside the loopback-pinned 5066/8021. FreeSWITCH was fully healthy in every
"failure"; it just bound a different address than the tests probed.

- **Root cause:** `switch_find_local_ip` (FreeSWITCH `switch_utils.c`) resolves
  `$${local_ip_v4}` by UDP-`connect()`-ing toward `82.45.148.209` and **falls
  back to `127.0.0.1` when no default route exists**. Whether the route is
  installed before freeswitch starts is a boot race: loopback bind → tests
  that probe `localhost:5060` pass; eth0 bind → they time out while the PBX
  is happily serving on `10.0.2.15`. CI (slow) skewed red, local runs skewed
  green — matching every "repro rate" in §b, and explaining why the process
  always looked healthy (it was).
- **All §f items below are moot** except "cite the green run in FEATURES".
- **§g questions resolved by evidence:** Q1 moot (SCHED_FIFO was never causal;
  the override stays as pure hardening with reworded rationale), Q2 rejected
  (no mitigate-on-timeout masking — nothing to mask), Q3 moot (no heavy
  instrumentation needed; the shipped DIAG dump was exactly enough).
- **Fix landed:** freeswitch now orders after `network-online.target` (a PBX
  must never silently bind loopback), and every test wait/assert derives the
  bound address from `ss` instead of assuming `localhost`.
