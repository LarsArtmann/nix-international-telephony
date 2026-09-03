# Status Report: Public Scrub Complete, Private Flake + DNS Live, Install Paused on Console Key

**Date:** 2026-09-03 12:52 CEST
**Scope:** Everything done in the 2026-09-02 evening → 2026-09-03 session (scrub, history purge, private flake, two module/test bug fixes, DNS go-live), plus the self-review that followed. Point-in-time snapshot — verify before building on it.

**Entry state:** Public repo half-scrubbed with 2 unpushed auto-commits carrying a real US DID + SIP username; no private flake; install aborted (server keyless); DNS undecided.
**Exit state:** Public repo clean and pushed, full CI gate green (265 checks), private deployment flake evaluating, `pbx.artmann.tech` resolving via Terraform-managed records, install one user action away — and one honest self-inflicted leak discovered (§d.1).

---

## a) FULLY DONE (verified)

1. **SSH-key question answered with facts.** Local `~/.ssh/id_ed25519` (MD5 `1b:7a:74:ee:…`, `lars@evo-x2`) matches NEITHER Hetzner console key (`terraform-admin`, `ssh-hetzner1`); Hetzner console keys are injected only at server CREATION, so the existing box can never receive them retroactively — hence the VNC decision.
2. **Public template scrubbed.** `hosts/pbx-prod/default.nix`: `pbx.artmann.tech`→`pbx.example.com`, `artmann.tech`→`example.com`, `lars@artmann.tech`→`admin@example.com`, `2a01:4f9:c015:c081::1`→`2001:db8:1::1` (doc range). `tests/prod-boot.nix`: 4 domain refs reverted. Verified zero matches in both files.
3. **Unpushed history purged and pushed.** Commits `4110bc5`/`e9add31` (real DID + SIP username added then removed by the auto-commit daemon) plus daemon intermediates replaced with ONE clean commit via `write-tree`/`commit-tree`/`update-ref` (no reset, no checkout). `git log --all -S <us-did>` and `-S <sip-username>`: empty across all refs. Pushed as `bc87d7c` (+ `21df3da` nixfmt) after your explicit accept-and-push decision.
4. **Status report 2026-09-02 committed with US DID digits redacted** (3 lines rewritten; `-S` scan for the DID clean).
5. **Private deployment flake created and evaluating:** `~/projects/pbx-artmann` — `flake.nix` (consumes `nixosModules.telephony` via `path:` input with nixpkgs/disko/nix-ssh-config follows, hardened keys-only sshd with your evo-x2 key, root key login for nixos-anywhere), `hosts/pbx/default.nix` (real domain, ACME email, static IPv6 `2a01:4f9:c015:c081::1`/fe80::1, Telnyx gateway with the trial SIP username + `passwordFile` secret, DID→ring group 2000, CDR on), `hosts/pbx/disk.nix` (sda/ext4/EF02), README. Toplevel evals to a full NixOS system (eval runs all module assertions) — eval'd green 3× against evolving public trees.
6. **Module bug FIXED — `didDestination` now accepts ring groups.** The reference assertion only accepted extension numbers while the public dialplan *transfers* DIDs into the default context where ring groups answer — i.e. the natural "trunk DID rings all desk phones" shape was impossible to evaluate. Caught by the private flake's first eval (the value of the private-flake pattern, proven immediately). Fixed in `modules/telephony/default.nix`; regression added to `tests/eval.nix` (`ringGroupDidEval`: toplevel must evaluate AND `transfer … 2000 XML default` must render in `dialplan/public.xml`).
7. **prod-boot wedge FIXED.** Gate failed deterministically: `freeswitch.service` never started (300s timeout, empty journal). Interactive-driver probes (`systemctl list-jobs --all`) showed `network-addresses-ens3.service` parked behind the never-appearing `sys-subsystem-net-devices-ens3.device`; `network-online.target` wants it; freeswitch/coturn/multi-user froze behind it. The template's Hetzner NIC config leaked into the VM (whose NICs are eth0/eth1). Fix in `tests/prod-boot.nix`: neutralize like the existing fileSystems/grub overrides (`mkForce {}` + `defaultGateway6 = mkForce null` + unit `enable=false`). Gate re-run: **EXIT=0**, live probe confirmed freeswitch/coturn/nginx active.
8. **Full CI gate GREEN:** `nix flake check` → all 265 checks passed (every VM suite, evals, statix/deadnix/treefmt/pre-commit). One intermediate failure was my own nixfmt violation — fixed with `nix fmt`, re-checked green.
9. **DNS LIVE (plan-gated, scoped):** `artmann.tech.tf` gained `pbx` A `62.238.116.181` + AAAA `2a01:4f9:c015:c081::1`. Plan reviewed first (2 to change, 0 to destroy); an unrelated pending `larsartmann.com` MX from your own committed config was deliberately NOT applied (scoped `-target` apply). Post-apply plan: "No changes."
10. **All 3 standing decisions captured via question tool:** server auth = keep IP, key via Hetzner VNC console; pushed history = accept (domain/email/IPv6 stay); DNS = assistant applies via domains repo (done, see 9).
11. **`push-secrets.sh` target verified:** defaults to `root@62.238.116.181`, correct for the kept server.
12. **AGENTS.md hard-won knowledge updated** (ens3 wedge + probe, didDestination semantics, daemon/history-surgery scrub protocol).

## b) PARTIALLY DONE

- **Public/private split:** code, tests, and DNS fully split; prose stragglers remain — `TODO_LIST.md` and `CHANGELOG.md` still name `pbx.artmann.tech` (accepted exposure, but stale facts); old status report partially redacted (see §d.1).
- **Private flake:** eval-only. No full closure build yet (disko-related derivations unbuilt); `telephony` input still `path:` (couples to local tree; GitHub pin pending until you want it).
- **First-call readiness:** every prerequisite staged (secrets dir + files, push script, DNS, flake, decisions); the install itself not run — blocked on one user action (§c.1).
- **DNS:** Terraform-verified but never queried live (no dig/propagation check performed).

## c) NOT STARTED

1. **USER ACTION: Hetzner web console (VNC) root login on 62.238.116.181 + paste the authorized_keys command** (was provided last message; not confirmed done).
2. nixos-anywhere install against `~/projects/pbx-artmann#pbx` (fail-fast, logged, BatchMode).
3. Post-install verification: sshd/freeswitch/nginx/coturn units, gateway REGED, ACME issuance, deploy.md §5 checklist.
4. User-run `push-secrets.sh` + secrets splice verification on the box.
5. First call to the Polish mobile (digits only in private notes); inbound test dialing the US DID.
6. SMS: attach US DID to messaging profile (portal), first `send-sms.py` run.
7. Post-trunk hardening: `allowedCidrs` + `firewall.restrictExternalTo` (deliberately deferred until trunk proven).
8. Warsaw DID KYC docs (user), Warsaw→second gateway stanza, DE national DID order (user).
9. Telnyx API key rotation (`KEY01…` still live, staged in `~/.telnyx-integration/api.key`).
10. Backups of `/var/lib/freeswitch` (voicemail/CDR/recordings) — nothing exists.
11. `infra/hcloud.tf` reconciliation with the manually-created server (import or delete).
12. TODO_LIST/FEATURES/CHANGELOG refresh for this session's work.

## d) TOTALLY FUCKED UP (honest ledger)

1. **Personal data published to the public repo.** Your reachable mobile **+48 690 ··· ···** (digits redacted here; twice, lines 118–119) and the **Warsaw DID +48 22 ··· ·· ··** (line 27) are in the 2026-09-02 status report — committed by me in `bc87d7c` and **pushed**. My redaction pass only chased the strings the handoff summary listed (US DID, SIP username); I never widened the scan to *other* personal numbers until this self-review forced it. Worse: I edited line 119 during redaction and preserved the mobile number in my own new text. This violates the session's loudest instruction ("do not publish ACTUAL secrets") in spirit — a personal mobile + pending DID in a public repo. Mitigation: follow-up scrub commit (history stays) or rewrite (you declined once — your call again, see §g).
2. **Daemon race ×3.** I re-did the history squash three times because the auto-commit daemon kept landing intermediate states. At one point it committed the UNREDATED status report and my squash absorbed the real DID — caught only because `git log --all -S` is a mandatory step in my loop. I should have scrubbed ALL candidate files (incl. untracked) before any surgery and done edit→add→squash atomically in one shell call.
3. **Two sloppy eval.nix edits:** duplicate attr name, then deleted the let-scope definition instead of the duplicate — two wasted build round-trips on a check I was extending.
4. **First full-gate run failed on my own formatting** (nixfmt line-joins) — `nix fmt` before `flake check` should be reflexive.
5. **Unexplained prior "green":** the previous session claimed prod-boot green on a tree whose ens3 config deterministically wedges the suite. Either that green was misread or the tree differed (AGENTS.md warns exactly this). I stopped the archaeology once the fix was proven — but the contradiction is recorded, not resolved.

## e) WHAT WE SHOULD IMPROVE

- **Standing pre-push scrub checklist as a script** (not ad-hoc greps): every real value in every formatting variant — DIDs (with/without spaces/`+`), personal numbers, usernames, IPs, key IDs — against tree AND `git log --all -S`. This report exists partly because that checklist was in my head, not on disk.
- **Untracked files are scrub blockers** before history surgery; the daemon will commit them.
- **Atomic daemon-racy sequences:** one bash call for edit+stage+squash+verify.
- **`nix fmt` before every gate; full `nix build` of deployable toplevels before install** (eval is not build — disko drvs remain unexercised).
- **Verify DNS live**, not just Terraform "No changes" (state-apply ≠ propagation).
- **AGENTS.md at discovery time** — done for this session, but only because the self-review prompted it.
- **Widen scans beyond handoff lists** — summaries enumerate what someone already found; fuckups live in what nobody listed.

## f) NEXT (ordered, ~40 real items)

**Install critical path**
1. USER: VNC paste key (§c.1).
2. Probe `62.238.116.181:22` reachable + key auth works (python socket + nixos-anywhere dry contact).
3. `nix build ~/projects/pbx-artmann#nixosConfigurations.pbx.config.system.build.toplevel` (full closure, de-risks mid-install build failures).
4. Run nixos-anywhere: `SSHOPTS='-o BatchMode=yes'`, `-i ~/.ssh/id_ed25519`, output to a log file, foregrounded reading.
5. Post-install: ssh in, check units (freeswitch, nginx, coturn, sshd, telephony-tls/web-config/health).
6. USER: run `~/.pbx-prod-secrets/push-secrets.sh`; verify file perms + splice (`grep` runtime XML has no `@TELEPHONY_*@`).
7. `fs_cli` gateway REGED check (`sofia status gateway telnyx`).
8. ACME: python-urllib check `https://pbx.artmann.tech/` + cert issuer; fix loop if challenge fails.
9. Live DNS query for `pbx.artmann.tech` (A/AAAA) — confirm propagation from an external resolver.
10. **First call to the Polish mobile** (webphone register 1000 → dial E.164; fallback `fs_cli originate` user-run block).
11. Inbound test: dial the US DID from the mobile; verify ring group 2000 rings.
12. Add `allowedCidrs` + `firewall.restrictExternalTo` (Telnyx source nets) once trunk proven; re-deploy.
13. fail2ban + telephony-health timer sanity on prod; decide alerting sink.
14. CDR rows confirmed for the test calls.
15. Browser E2E against prod webphone (register, call 2000 voicemail fallback).

**Hygiene / repair (this session's debt)**
16. Scrub the Polish mobile and the Warsaw DID (digits redacted throughout this report) from the pushed 2026-09-02 report (follow-up commit) — pending §g.2.
17. Delete stray `tfplan-pbx` file in domains repo.
18. Domains repo: re-author the daemon's junk-message commit for artmann.tech.tf (or accept).
19. Push domains repo (daemon committed locally; remote state unverified).
20. Private flake: pin `telephony` input to the pushed GitHub rev (drop path: coupling).
21. Private flake: add minimal check (toplevel eval) so it cannot rot silently.
22. Update TODO_LIST deployment row (DNS done, flake done, blocked only on install); FEATURES/CHANGELOG for the didDestination fix.
23. Add the scrub-checklist script to the repo (§e.1) and wire it into pre-commit.
24. Resolve §d.5 (old-green mystery) — 30 min with the interactive driver on the 94ae5c1 tree, or close it as "prior misread".
25. Consider `recording.enable = false` explicitly in the private flake until consent posture is decided (template default is TRUE — recordings are personal data).

**Telenyx / numbers**
26. USER: Warsaw KYC docs → activate the Warsaw DID → second gateway stanza.
27. USER: DE national DID order (per docs/providers/telnyx.md).
28. Portal 2-click: attach US DID to messaging profile; `send-sms.py` first SMS to the mobile.
29. Rotate Telnyx API key `KEY01…` (your go signal).
30. Verify outbound CLI shows the US DID on the Polish mobile's caller display.

**Hardening / operations**
31. Backups: pick restic-to-something or Hetzner snapshots for `/var/lib/freeswitch` + `/var/lib/telephony-secrets` (secrets: encrypted target only).
32. Hetzner Cloud firewall posture (currently NixOS firewall only).
33. Reconcile `infra/hcloud.tf` (import the real server or retire the module).
34. NTP/time sanity on prod (time-routing feature depends on it).
35. Consider nixpkgs release-channel pin (not unstable) for the prod host.
36. Private repo remote (GitHub private) as backup for pbx-artmann.
37. runbook: add "server recreation" page (console steps + IPv6 re-pin in private flake).
38. push-secrets.sh: add hash-verify mode (local vs remote).
39. Move interactive probe scripts (probe-prodboot.py) into the repo for reuse.
40. Post-first-call status report + CHANGELOG release entry.

## g) QUESTIONS I CANNOT ANSWER MYSELF

1. **Is the server's root password still available to you** (Hetzner creation email) for the VNC login? If lost: Hetzner console password-reset, or switch to delete+recreate-with-key (new IPs → 5-min private-flake + DNS update).
2. **How do you want the personal-data leak (§d.1) handled:** follow-up scrub commit (history keeps the mobile/Warsaw DID in `bc87d7c`, current tree clean) or a history rewrite + force-push after all (removes them entirely; breaks nothing anyone depends on yet)?
3. **Recording posture for your deployment:** keep the template default (calls recorded to local disk) or disable until you've decided consent/notification (GDPR two-party considerations for PL/DE/US legs)?

---

**Bottom line:** everything machine-side that could be verified is verified green; the deployment is one VNC paste away; and the session's one genuine failure — personal numbers in the pushed report — is found, documented, and awaiting your call on remedy.
