# Status Report: Pareto Plan Execution — Tiers 1–2 Complete, M15 Interrupted

**Date:** 2026-08-21 20:58 CEST
**Session:** Full execution run of `docs/planning/2026-08-21_09-51_pareto-trustworthy-telephony-stack.md`
**Git:** HEAD `f64e544`, working tree **clean**. Remote `origin/main` still at `bf13e2d` — **the 5 session commits are NOT pushed.**
**Gate:** `nix flake check` green at every commit point (last green gate: before/at `f64e544`).

---

## a) FULLY DONE (committed, gate green, VM-tested)

Five commits this session:

| Commit    | Content                                 |
| --------- | --------------------------------------- |
| `8c411aa` | M1–M5 + shipped-bug fix (details below) |
| `ec3ca47` | M6 firewall restriction                 |
| `4e34dc4` | M7–M9 TURN REST auth                    |
| `a6f198e` | M10–M12 CDR + ACME TLS                  |
| `f64e544` | M13–M14 multi-gateway LCR               |

1. **M1 — Scripted SIP client (`tests/sip.py`, stdlib-only) + REGISTER/INVITE VM tests.**
   Digest auth (MD5/SHA-256, qop), correct 401/`WWW-Authenticate` (REGISTER) vs 407/`Proxy-Authenticate` (INVITE) handling, full INVITE→200→ACK→hold→BYE dialog, `--expect-status` denial assertions, `--skip-register`, `--bind` (source-address control). VM asserts: REGISTER 200 + sofia reg listing, wrong-password rejected, two coexisting registrations (multi-device), answered echo call with PCMU in `show detailed_calls`, clean teardown.
2. **M2 — Gateway + denial-path tests.** Gateway REG state machine live (fictitious TEST-NET-3 proxy), toll-allow denial, no-gateway E.164, unknown number.
3. **M3 — Recording behavioural test.** `*_1001.wav` grows on disk after a dialled call; `recording.enable = false` leaves the directory empty (machine3).
4. **M4 — Voicemail/config/port tests.** Ring-group fallback answers via a real SIP INVITE to 2000 (only possible 200 = voicemail), `*98` answered by voicemail-check, `config.js` strict-JSON parse with TURN creds, ports 5061/5080 TCP+UDP listening.
5. **M5 — `gateway.allowedCidrs`.** Emits `acl.conf.xml` (list `trusted-itsp`, default deny) + wires `apply-inbound-acl` on the external profile only when set; ACL rejection proven with an INVITE from non-listed `127.0.0.2`.
6. **Latent v0.1.0 dialplan bug found & fixed (highest-value change of the session).** Voicemail fallbacks were `<anti-action>`s — FreeSWITCH runs anti-actions when the CONDITION fails, so every call that didn't match a group/extension entry was answered 200+voicemail and denial extensions were unreachable. Fixed to plain actions after `bridge` with `continue_on_fail`/`hangup_after_bridge`; denial entries switched from `respond` to `hangup` with mapped causes.
7. **M6 — `firewall.restrictExternalTo`.** When set, 5080 TCP+UDP only accepted from listed CIDRs (nftables `extraInputRules`); default behaviour unchanged.
8. **M7+M8 — TURN REST auth.** `turn.authSecret` replaces static username/password: coturn `use-auth-secret`, runtime-rendered `/var/lib/telephony/config.js` (oneshot + daily timer, 48 h credential validity), nginx serves it; store-baked creds gone. README + demo host migrated.
9. **M9 — `tests/turn.py` (stdlib STUN/TURN client) + allocation proof.** STUN binding, TURN allocation with the served ephemeral credential (cross-checked against the HMAC derivation), wrong-credential 401.
10. **M10 — `cdr.enable`.** Generated `cdr_csv.conf.xml`; CSV rows land in `/var/lib/freeswitch/cdr-csv/Master.csv` (VM-asserted after a finished call).
11. **M11+M12 — `tls.mode = "acme"` + FS 5061 cert provisioning.** `security.acme` wiring (`tls.acmeEmail` required, assertion enforced), nginx on ACME paths, `telephony-fs-cert` oneshot builds `agent.pem`(cert+key)+`cafile.pem` into the profile's `tls-cert-dir`, systemd path unit re-provisions + restarts the internal profile on renewal. All three TLS modes eval-verified (`tests/tls-mode-host.nix`); real ACME needs a public host.
12. **M13+M14 — `gateways` attrsOf + least-cost routing.** Per-gateway `priority` (ascending = tried first, serial `|` failover bridge), per-gateway DID routing, merged `allowedCidrs` ACL, unique-DID assertion, deprecated single `gateway` shim. Two-gateway VM test: REG states, generated bridge order, DID transfer + unknown-DID 404.
13. **Docs discipline held throughout:** every feature flip = FEATURES row update + TODO removal + CHANGELOG entry in the same commit; AGENTS.md gained four hard-won-knowledge entries (anti-action trap, hangup-cause→SIP mappings, 401/407 scripted-client specifics, sofia journal gap).

**Plan progress: 14 of 34 medium tasks (M1–M14). Tiers T1 (1%→51%) and T2 (→64%) fully landed; T3 begun.**

---

## b) PARTIALLY DONE (design settled, zero lines landed)

**M15+M16 — recordings serving + retention.**
Design decided: move recordings out of FreeSWITCH's DynamicUser-private state to `/var/lib/telephony/recordings` (shared `telephony` group; `SupplementaryGroups` on freeswitch + nginx; `install -d -g telephony -m 0770` oneshot), nginx `location /recordings/` (alias, autoindex, `auth_basic` via htpasswd file option), `recording.retentionDays` daily `find -mtime +N -delete` timer.
**State: two python-heredoc patch attempts aborted on quoting errors; nothing written — `modules/telephony.nix` is at its committed state.** (Verified: working tree clean.)

**Open anomaly:** the final `nix eval .#nixosConfigurations.pbx...` before interruption failed with an odd "flake does not provide attribute 'packages.x86_64-linux.nixosConfigurations…'" error, and a `nix build .#webphone --dry-run` hung (background job interrupted by session end). Un-diagnosed; the flake itself gated green minutes earlier, so likely transient/invocation issue — re-verify before resuming.

---

## c) NOT STARTED

- **M17–M23** (extraConfigFiles, sounds license, nix-review pass, CI direct verify, aarch64 eval, pre-commit hooks, doc-lifecycle/citations)
- **M24–M34** (systemd hardening, ext-ip split, demo polish + CSP, sip.js update script, webphone reconnect/remember-me/multi-call/DTMF+history, test-suite split, ops runbook, aarch64 full validation)
- **Gates B1–B3** (secrets tooling, browser E2E, directory rename) — still blocked on Q1–Q3.

---

## d) TOTALLY FUCKED UP (honest mistakes; all recovered)

1. **Wrong root-cause twice on denial paths.** First blamed the `respond` app (it was actually fine to keep blaming the wrong layer for two VM cycles) — real culprit was the anti-action fallback bug. The `respond`→`hangup` rewrite was kept (correct), but I burned cycles arguing with symptoms.
2. **Assumed `call_rejected`→403; actual SIP mapping is 603** in this FreeSWITCH build. One VM cycle.
3. **`tests/turn.py` birth defects:** wrong ALLOCATE_ERROR constant (0x0111 vs 0x0113), `--server` flag not visible to subcommands (argparse parents fix), ERROR-CODE misparse (read 1025, meant 401), and the MESSAGE-INTEGRITY construction wrong (zeroed-placeholder vs coturn's truncated-before-MI rule — needed a local coturn + `turnutils_uclient` tee-capture + brute-force over key/input variants to pin down).
4. **Python-heredoc patching repeatedly collided with Nix `''` quoting** (SyntaxError/AssertionError rounds; one round injected broken escaping into `tests/pbx.nix`). Biggest time sink of the session.
5. **`nix fmt` reflowed files between my read and my edit** several times → edit-tool failures → more python patching (feedback loop with #4).
6. **Journal-grep test approach flaked** (loopback+ringback+record stall; sofia EXECUTE lines don't reach the VM journal) — cost ~3 cycles before rewriting as SIP-level asserts.
7. **Debug `cat $(find /etc …)` with no match hung the test driver on stdin** (900 s timeout).
8. **`tests/turn.py` accidentally landed inside the M6 commit** (stash-pop mishap) — harmless but untidy history.
9. **`wait_for_unit` on a completed oneshot** (telephony-web-config) — inactive-unit trap; replaced with artifact assert.
10. **`lib.mkIf` inside a `let` binding** for `tlsCertDir` (merge marker ≠ conditional) — caught immediately, but a sloppy reach for module-system idioms.
11. **Un-diagnosed eval error + hung build at session end** (see b).

---

## e) WHAT WE SHOULD IMPROVE

- **Stop writing python heredocs to patch Nix files.** Use the edit tool against freshly-read exact context, `write` for whole blocks, or single-line `sed`. The `''`-quoting collisions are systematic, not bad luck.
- **Re-read after every `nix fmt`** before the next edit (fmt reflow invalidates remembered whitespace).
- **Default to SIP/behavioural asserts, never journal greps**, for sofia-channel evidence — now encoded in AGENTS.md; follow it.
- **Check the packaged vanilla config first** when generating FreeSWITCH XML (cdr `base_dir` vs `log-base` cost a cycle; the answer was in the store the whole time).
- **Kill background nix jobs before ending a session**; verify daemon push state with `ls-remote` at every commit (right now 5 commits sit unpushed).

---

## f) NEXT — up to 50 items

1. ~~Re-verify flake eval sanity (explain the odd eval error / hung dry-run)~~ done (transient invocation issue - every later gate green)
2. ~~Decide push: publish the 5 local commits (needs user OK)~~ done (pushed; CI green runs cited in FEATURES)
3. ~~M15.1 `recording.serve.enable` + `basicAuthUser/PasswordFile` options~~ done at `71fea3b`
4. ~~M15.2 shared `/var/lib/telephony/recordings` + `telephony` group + SupplementaryGroups~~ done at `71fea3b`
5. ~~M15.3 nginx `location /recordings/` (alias, autoindex, auth_basic)~~ done at `71fea3b`
6. ~~M15.4 VM test: 401 without creds / 200 with creds~~ done at `71fea3b`
7. ~~M15.5 README: consent-law reminder at the browse URL~~ done at `71fea3b`
8. ~~M16.1 `recording.retentionDays` option~~ done at `71fea3b`
9. ~~M16.2 retention service + daily timer (`find -mtime +N -delete`)~~ done at `71fea3b`
10. ~~M16.3 VM test: aged file removed, fresh kept~~ done at `71fea3b`
11. ~~M17 `extraConfigFiles` (attrsOf path → configDir merge, documented semantics)~~ done at `0f44e2d`
12. ~~M17 README paragraph + eval-check example~~ done at `0f44e2d`
13. ~~M18 `sounds.nix` license → `lib.licenses.mpl11` + CC-BY music note; `nix build .#freeswitch-sounds`~~ done at `bc2a3fc`
14. ~~M19 run `nix-review` skill checklist; fix ≤5-min findings, ticket the rest~~ done at `951a083`
15. ~~M20 `gh run list` CI verify first-hand; cite run URL in FEATURES~~ done at `e8c9eb9`
16. ~~M21 `nix flake check --all-systems` (aarch64 eval) + fallout fixes~~ done (M21 - --all-systems eval green 2026-08-24)
17. ~~M22 `.pre-commit-config.yaml` (nixfmt/statix/deadnix/gitleaks) + `run --all-files` clean~~ done at `bc4c9cc`
18. ~~M23 AGENTS.md doc-lifecycle block (one home per fact, TODO deletes done items)~~ done (M23 - AGENTS.md doc-lifecycle block)
19. ~~M23 swap `file:line` cites for option names in TODO/FEATURES~~ done (M23 - option-name citations)
20. ~~M24 systemd hardening audit (freeswitch, telephony-tls, telephony-web-config, fs-cert)~~ done (M24 - systemd hardening landed incl. AF_NETLINK)
21. ~~M24 apply safe directives, keep VM test green~~ done (M24 - hardening kept VM test green)
22. ~~M25 `natSipAddress` / `natRtpAddress` split (null → natAddress)~~ done (M25 - natSipAddress/natRtpAddress landed)
23. ~~M26 `virtualisation.forwardPorts` 443 in demo host~~ done at `375c9d4`
24. ~~M26 console banner (URL, extensions, demo passwords)~~ done at `375c9d4`
25. ~~M26 CSP header on webphone vhost + test assert~~ done at `56df068`
26. ~~M27 `packages/webphone/update.sh` (fetch latest version+hash, rewrite default.nix)~~ done at `b50dcf9`
27. ~~M28 transport disconnect → backoff reconnect~~ done at `5a52c1f`
28. ~~M28 re-register after reconnect + retry-count status~~ done at `5a52c1f`
29. ~~M28 registration refresh before TTL~~ done at `5a52c1f`
30. M28 manual check: kill nginx in VM, watch reconnect
31. ~~M29 remember-me (localStorage, never the password)~~ done at `5a52c1f`
32. ~~M30 session array (no singletons); hold current on new incoming~~ done at `5a52c1f`
33. ~~M30 active-call list UI + per-call controls~~ done at `5a52c1f`
34. ~~M31 DTMF keypad (RTP events) when established~~ done at `5a52c1f`
35. ~~M31 call history (last 20) + duration timer~~ done at `5a52c1f`
36. ~~M31 ringback tone on Inviter Progress~~ done at `5a52c1f`
37. ~~M32 split `tests/webphone.nix` (serving, config.js, proxy)~~ done at `76a49d4`
38. ~~M32 split `tests/dialplan.nix` (echo, extensions, groups, denial, VM)~~ done at `d96484b`
39. ~~M32 split `tests/tls-turn.nix` (cert bootstrap, 5061, coturn)~~ done at `d96484b`
40. ~~M32 shared node-config module + per-file flake checks~~ done at `d96484b`
41. ~~M33 `docs/ops-runbook.md` (fs_cli cheat-sheet)~~ done at `76a49d4`
42. ~~M33 cert-rotation + gateway-debug walkthroughs~~ done at `195bf3a`
43. ~~M33 mermaid architecture diagram in README~~ done at `76a49d4`
44. ~~M34 aarch64 cross-build of packages~~ done (M34 - aarch64 cross-builds + eval proven; TCG boot ceiling recorded in FEATURES)
45. ~~M34 aarch64 QEMU VM boot if feasible; record in FEATURES~~ done (M34 - boot attempted under TCG; disk timeout, needs native runner (FEATURES row honest))
46. ~~B1 secrets tooling (BLOCKED on Q2) — highest impact in whole plan once unblocked~~ done at `97ea2b3`
47. ~~B2 browser E2E chromium test (BLOCKED on Q3)~~ done (B2 - browser E2E green + manual workflow_dispatch CI job)
48. ~~B3 local directory rename (BLOCKED on Q1)~~ **Won't implement — owner keeps the historical directory name - typo deliberate.**
49. ~~Sweeps: re-run full gate once after M15–M23 cluster; annotate the plan file via docs-health ANNOTATE at the end (never rewrite)~~ done (docs-health pass 2026-08-27)
50. ~~Final: update FEATURES/TODO/CHANGELOG single-home discipline for all flips; consider `v0.2.0` tag + release notes~~ done (single-home discipline held; 0.2.0 release queued in TODO_LIST)

---

## g) QUESTIONS FOR THE USER

1. **Push?** The 5 session commits (`8c411aa`…`f64e544`) are local-only; remote still sits at `bf13e2d`. Push now, or wait for the auto-git daemon / your explicit go?
2. **Secrets tooling (gates B1):** sops-nix or agenix — and hard requirement or soft support? This is the single highest-impact item left in the plan.
3. **Browser E2E (gates B2):** add chromium + fake-media to the VM test (~1–2 GB closure) for a full WebRTC media-path proof, or keep the suite lean and leave webphone verification at the SIP/WSS level?
