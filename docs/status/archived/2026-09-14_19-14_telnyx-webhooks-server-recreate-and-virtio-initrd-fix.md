# Status Report: Telnyx Inbound Wiring, Server Recreate, and the Virtio-Initrd First-Boot Hang

**Date:** 2026-09-14 19:14 CEST
**Scope:** This session only (≈16:20–19:14): Telnyx number-state audit, outbound SMS/call tests, webhook-receiver build-out, old-server death and new-server creation, first nixos-anywhere install, virtio-initrd root-cause and fix. Point-in-time snapshot — verify before building on it.

**Entry state:** Warsaw DID believed "pending KYC" (2026-09-03 report); PBX install still "one VNC paste away" on the old server; messaging profile had no inbound webhook; no Call Control app.
**Exit state:** US DID proven active; Warsaw DID proven DELETED by Telnyx; webhook receiver built and unit-tested but NOT live; old server abandoned mid-rebuild; NEW server created, installed once with an unbootable initrd, root cause fixed in both flake repos — reinstall pending one user action (rescue boot). Sensitive values (DIDs, IPs, key material) are intentionally absent; they live in the private flake, `~/.pbx-prod-secrets/`, and `~/.telnyx-integration/`.

---

## a) FULLY DONE (verified)

1. **Telnyx number state audited against the live API** (staged key): US DID `status=active` (order `success`); Warsaw DID order **DELETED 2026-09-04 ≈48h after purchase** with all 5 KYC requirements still `awaiting-value` — released, must be re-purchased; DE national never ordered. Evidence: `GET /v2/phone_numbers`, `GET /v2/number_orders/{id}` output in session.
2. **2026-09-03 status report annotated inline** (2 resolution markers: §c.8 and §f.26) so no future session treats the Warsaw DID as merely pending KYC.
3. **Outbound SMS verified end-to-end**: test SMS from the US DID to the user's test target accepted by Telnyx (queued, carrier = Bandwidth CLEC, no errors) and **delivered** — proven by the target's reply reaching Telnyx. (The reply itself was dropped — see d.2.)
4. **Call Control prerequisites created via API**: CC app `api-dial-test` with webhook `https://pbx.artmann.tech/telnyx/webhooks`, plus an outbound voice profile (conversational/rate-deck, $5 monthly cap, 0.10 max destination rate) assigned to the app. IDs staged as `~/.telnyx-integration/cc_app_id` and `outbound_voice_profile_id`. The final dial returned 200 with a `call_control_id`.
5. **Webhook receiver built into the private flake** (`~/projects/pbx-artmann`): `hosts/pbx/webhooks.nix` (`telnyx-webhooks.service`: stdlib Python on 127.0.0.1:8069, DynamicUser + `SupplementaryGroups=turnserver`, ProtectSystem=strict et al.) + `hosts/pbx/telnyx-webhooks.py` (POST `/telnyx/webhooks` → JSONL log; token-gated `GET /recent`; open `/health`); nginx exact-match locations merge into the ACME vhost; `telephony_webhook_token` generated into `~/.pbx-prod-secrets/` and `push-secrets.sh` extended to install it (640/turnserver). **Unit-tested locally**: POST 200+logged, no-token 403, valid-token 200 with payload, health 200. Full closure builds; `telnyx-webhooks.service` unit and the three nginx locations verified present in the built `nginx.conf`.
6. **Latent install blocker fixed**: the private flake's `telephony` input pointed at the pre-rename directory (`nix-internatial-…`) — eval would have failed at install time. Now points at the real checkout.
7. **`cloud-init.yaml` committed to pbx-artmann**: installs the evo-x2 root key at server creation, `ssh_pwauth: false` — this is what made the new server's key auth work.
8. **New server created by the user** (Hel1, Debian 13, cloud-init user data) — IPv4 recorded in the private flake defaults and the domains repo; SSH banner verified live before install.
9. **DNS updated via the domains repo** (scoped Terraform apply, 1 change): `pbx` A → new IP, stale AAAA removed (returns with the /64). Authoritative NS verified answering the new A; local resolver still serves the cached old record (TTL 1799).
10. **First nixos-anywhere install ran mechanically clean**: kexec → disko (GPT + EF02 BIOS-boot + ext4 root) → full closure upload (mostly cache substitutes) → GRUB `i386-pc` install → reboot. Proves key auth, disko layout, closure copy, and bootloader on this hardware.
11. **First-boot hang root-caused and fixed in BOTH repos**: the initrd contained **zero virtio drivers** (no `hardware-configuration.nix` exists in the flake flow to detect them; the module list was IDE-era). Hetzner Cloud disks are virtio-SCSI → kernel blind to `/dev/sda` → infinite systemd wait for `dev-disk-by…-disk-main-root` — exactly the console hang observed. Fix: `boot.initrd.availableKernelModules = [ "virtio_pci" "virtio_blk" "virtio_scsi" ]` in the private host AND the public `hosts/pbx-prod` template. **Verified** `virtio_blk.ko.xz`/`virtio_scsi.ko.xz`/`virtio_pci.ko.xz` inside the rebuilt initrd (`zstdcat | cpio -t`).
12. **"Why did the VM test not catch this" answered with source evidence**: `tests/prod-boot.nix` `mkForce`s root to `/dev/vda` (QEMU virtio-blk stand-in) and neutralizes NIC/grub — the metal boot path is replaced wholesale in every VM suite. Lesson recorded in the public `AGENTS.md` hard-won-knowledge section.
13. `nix fmt` on the public repo (0 changed); all background watcher jobs explicitly closed; pbx-artmann README rewritten for the recreate flow (install defaults, webhook wiring, file inventory).

## b) PARTIALLY DONE

- **Webhook receiver: built and tested, NOT live.** The server is wedged (see d.1). Remaining: rescue-boot + reinstall with the fixed closure; `push-secrets.sh`; then `GET /health` over HTTPS (IPv4-forced; local DNS cache may lag). Effort: S after install. → open — deploy lane (TODO_LIST High row; docs/deploy.md §5)
- **Messaging profile inbound webhook: not yet set** (still `webhook_url: null`) — deliberately deferred until the endpoint answers; the CC app already points at the same URL (Telnyx retries against it, harmless). Effort: S (one PATCH + user texts the DID). → open — deploy lane (P3)
- **Outbound call test: outcome unverified.** Dial accepted (200 + call_control_id) but no event sink existed; `GET /v2/calls/{id}` exposes no state and both CDR list endpoints 404'd. Open question "did the target phone ring" still unanswered. Effort: S once webhooks are live (redial + read the event log). → open — deploy lane (P3.3)
- **IPv6: intentionally absent.** Private flake is v4-only (old /64 belongs to the dead server); new server's /64 never read from the panel; AAAA record removed. Effort: S once the /64 is known (g.1). → open — deploy lane (P5.1–P5.2)
- **Domains repo state:** apply done, but commit/push hygiene (daemon messages, stray tfplan from the prior session) not verified. Effort: S. → open — out-of-repo (domains repo)

## c) NOT STARTED

1. Live stack verification (ACME/HTTPS, sshd, freeswitch/coturn/nginx units, gateway REG state) — blocked on reinstall. → open — deploy lane (docs/deploy.md §5)
2. First real calls (webphone register 1000 → outbound E.164; inbound to the US DID) and CDR confirmation. → open — deploy lane (P4)
3. Warsaw DID re-purchase + KYC upload **inside the ~48h release window** (user task). → open — TODO_LIST blocked row (Warsaw DID)
4. DE national DID order (user task, per docs/providers/telnyx.md). → open — TODO_LIST blocked row (Warsaw/DE DIDs)
5. Trunk hardening (`allowedCidrs`, `firewall.restrictExternalTo`) — deliberately post-first-call. → open — deploy lane (P9)
6. `services.qemuGuest.enable` decision (panel screenshots / graceful shutdown; does not affect networking). → open — ROADMAP open question 6
7. Old-server deletion; `infra/hcloud.tf` reconciliation (TWO manually-created servers now exist). → partial — hcloud retired 2026-09-16; old-server deletion → open — deploy lane §P5.3 (owner)
8. Telnyx API key rotation (old key still live and now load-bearing for scripts). → open — TODO_LIST blocked row (key rotation)
9. Backups (restic/Hetzner snapshots for `/var/lib/freeswitch` + secrets), fail2ban, alerting sink. → done — backups + fail2ban + alerting all shipped and VM-proven; pbx-prod enables them
10. Public-repo full `nix flake check` for this session's template + AGENTS.md edits (CI will run it on push; not run locally this session). → done — full local nix flake check green 2026-09-16 18:01; CI green on every push since

## d) TOTALLY FUCKED UP (honest ledger)

1. **I shipped an unbootable system and told the user to install it.** I verified eval, full closure build, webhook unit tests, even the nginx config — but never audited the initrd against the target's actual storage bus. The 10-second `zstdcat | cpio -t | grep virtio` I ran _after_ the failure would have caught it _before_. Severity: one full install cycle burned, a wedged server, hours of user frustration. Root cause: "eval/build green = deployable" blind spot + no `hardware-configuration.nix` in the flow to ever detect hardware. Mitigation: virtio modules now explicit; initrd audit should become a gate (e.1).
2. **The user's SMS reply was permanently dropped.** The session's opening goal was receiving inbound SMS; I fired the outbound test while `webhook_url` was null and Telnyx has no retrieval API — the reply content is unrecoverable. Root cause: wired the outbound path without first wiring the return path it existed to test.
3. **`install-pbx.sh` v1 omitted `-i ~/.ssh/id_ed25519`** → nixos-anywhere's temp-key `ssh-copy-id` fell back to a password prompt the user did not have. One round trip lost; fixed the same hour.
4. **Machine ambiguity in my instructions.** The user executed from a second LAN box with a stale `pbx-artmann` checkout while my fixes lived on evo-x2; several confusing failures (temp-key dance, "keys already exist" vs password) trace to me not pinning host + repo freshness in every instruction.
5. **Call-test loop left open**: no CDR/event evidence path, and I moved on to the SMS question without closing it — "did it ring" is still unknown.

## e) WHAT WE SHOULD IMPROVE

- **Pre-install initrd audit as a hard gate**: script that greps the built initrd for the target platform's bus drivers (virtio for any cloud, nvme/ahci otherwise) before any install hand-off. Would have saved today's wedge outright.
- **Return-path-first rule for tests**: never fire a one-way integration test whose whole purpose is the round trip (SMS reply) before the return path exists.
- **Pin the execution environment**: deployment instructions must name the machine and require repo freshness ("run from evo-x2; the 150-box copy is stale").
- **Persist the Namecheap workaround**: `NAMECHEAP_CLIENT_IP` must be exported per Terraform invocation, and dnsblockd (HaGeZi) blocks ipify-family echo services — use `dig TXT o-o.myaddr.l.google.com @ns1.google.com`. This belongs in the domains repo's AGENTS.md, not in session memory.
- **Don't daemon-ship public-repo changes without the local gate**: the pbx-prod virtio fix and AGENTS.md lesson went out on the auto-commit daemon without a local `nix flake check` — rely on CI only deliberately.
- **Close every user-visible loop** (ring? delivered? REGED?) explicitly before switching topics; open loops compound into d.2/d.5.

## f) NEXT (ordered)

| #      | Task                                                                                                                                                                                                          | Impact     | Effort | Category      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------ | ------------- |
| 1      | USER: Hetzner panel → enable rescue system (evo-x2 key in project SSH keys) → power-cycle → open — deploy lane (TODO_LIST High row)                                                                           | Critical   | S      | Ops           |
| 2      | USER: `install-pbx.sh` (fixed closure) + `push-secrets.sh` from evo-x2 → open — deploy lane (TODO_LIST High row)                                                                                              | Critical   | S      | Ops           |
| 3      | Verify `https://<new-ip-host-header>/telnyx/webhooks/health` (force IPv4 past the cached A record) → open — deploy lane (P2.1)                                                                                | Critical   | S      | Quality       |
| 4      | PATCH messaging profile `webhook_url` → the live endpoint; user texts the US DID; read the reply via `/recent` → open — deploy lane (P3)                                                                      | Critical   | S      | Feature       |
| 5      | Close the call loop: redial the test target; confirm ring/answer from webhook events → open — deploy lane (P3.3)                                                                                              | High       | S      | Quality       |
| 6      | Read new server's /64 from the panel → static IPv6 + fe80::1 gateway in the private flake → redeploy → open — deploy lane (P5.1)                                                                              | High       | S      | Feature       |
| 7      | Re-add the `pbx` AAAA record via the domains repo; verify v6 reachability → open — deploy lane (P5.2)                                                                                                         | High       | S      | Ops           |
| 8      | Delete the old server (still billing) once the new one is proven → open — deploy lane (P5.3)                                                                                                                  | High       | S      | Ops           |
| 9      | deploy.md §5 checklist: units, ACME cert issuer, gateway REGED (user-run `fs_cli`) → open — deploy lane (P2.4)                                                                                                | High       | M      | Quality       |
| 10     | First real calls (webphone 1000 → E.164; inbound to the US DID) + CDR rows → open — deploy lane (P4)                                                                                                          | High       | M      | Feature       |
| 11     | `allowedCidrs` + `firewall.restrictExternalTo` with Telnyx source nets; redeploy → open — deploy lane (P9, after first calls)                                                                                 | High       | S      | Quality       |
| ~~12~~ | ~~Initrd-audit gate script (e.1) wired into the deploy flow~~ done — packages/initrd-audit + checks.initrd-audit landed 2026-09-16                                                                            | ~~High~~   | ~~S~~  | ~~Quality~~   |
| ~~13~~ | ~~Full `nix flake check` locally for the public-repo changes~~ done — full gate green locally 2026-09-16 18:01 and on CI since                                                                                | ~~High~~   | ~~M~~  | ~~Quality~~   |
| 14     | Warsaw DID: re-purchase in the portal + submit the 5 KYC requirements within ~48h → open — TODO_LIST blocked row (Warsaw DID)                                                                                 | High       | S      | Ops           |
| 15     | DE national DID order + KYC (personal-identity path) → open — TODO_LIST blocked row (Warsaw/DE DIDs)                                                                                                          | Medium     | S      | Ops           |
| 16     | Rotate the Telnyx API key (now load-bearing for cc_app/outbound-profile scripts) → open — TODO_LIST blocked row (key rotation)                                                                                | Medium     | S      | Security      |
| 17     | Decide + wire `services.qemuGuest.enable` (panel screenshots/graceful shutdown) → open — ROADMAP open question 6                                                                                              | Low        | S      | Feature       |
| ~~18~~ | ~~Reconcile `infra/hcloud.tf` (two manual servers; import or retire)~~ done — retired 2026-09-16 (docs/deploy.md §4 documents the real path)                                                                  | ~~Medium~~ | ~~S~~  | ~~Cleanup~~   |
| ~~19~~ | ~~Backups for `/var/lib/freeswitch` + secrets (restic or Hetzner snapshots)~~ done — services.telephony.backups shipped; pbx-prod enabled                                                                     | ~~Medium~~ | ~~M~~  | ~~Ops~~       |
| ~~20~~ | ~~fail2ban + health-timer alerting sink on prod~~ done — fail2ban.enable + alerts.* shipped; OnFailure sink VM-proven                                                                                         | ~~Medium~~ | ~~S~~  | ~~Security~~  |
| 21     | Browser E2E against the prod webphone → open — deploy lane (needs the live host)                                                                                                                              | Medium     | M      | Quality       |
| ~~22~~ | ~~Real-disk-boot VM test (disko image + `virtualisation.diskInterface`) covering the metal boot path~~ done — checks.telephony-metal-boot landed 2026-09-16 (kexec into the real kernel+initrd)               | ~~Medium~~ | ~~M~~  | ~~Quality~~   |
| 23     | Domains repo: persist `NAMECHEAP_CLIENT_IP`/dig workaround in its AGENTS.md; commit/push hygiene; stray tfplan → open — out-of-repo (domains repo)                                                            | Medium     | S      | Documentation |
| 24     | pbx-artmann TODO_LIST/FEATURES refresh (the 18:41 docs-health report predates the install run) → open — out-of-repo (private flake)                                                                           | Medium     | S      | Documentation |
| 25     | CHANGELOG entries both repos: webhook receiver, virtio fix, virtio lesson → done (this repo) — virtio fix + initrd gate are in CHANGELOG [Unreleased]; private-repo half → open — out-of-repo (private flake) | Medium     | S      | Documentation |
| ~~26~~ | ~~Recording consent posture decision (g.3) — before first real traffic~~ done — answered 2026-09-16 — record ALL calls, consent accepted                                                                      | ~~High~~   | ~~S~~  | ~~Decision~~  |
| ~~27~~ | ~~Scrub-checklist script (carried from 2026-09-03 §e.1; today's masked values prove the habit)~~ done — scripts/scrub-check.sh shipped, armed 2026-09-16, and the history rewrite executed (d7ac48f)          | ~~Medium~~ | ~~S~~  | ~~Security~~  |
| 28     | Pin private-flake `telephony` input to the GitHub rev (drop `path:` coupling) → open — out-of-repo (private flake)                                                                                            | Low        | S      | Cleanup       |
| 29     | Hetzner Cloud firewall posture (currently NixOS firewall only) → open — ROADMAP theme 1 (hoster-level firewall posture)                                                                                       | Medium     | S      | Security      |
| 30     | Post-first-call status report + CHANGELOG release entry → open — deploy lane (P4.5) + TODO_LIST blocked row (v0.3.0)                                                                                          | Medium     | S      | Documentation |

## g) QUESTIONS I CANNOT ANSWER MYSELF

1. **The new server's IPv6 /64** (Hetzner panel → server → Networks). Needed to re-pin the private flake's static v6 and restore the AAAA record; not discoverable via API without an hcloud token (none staged — searched) and the box has no SSH yet. → open — deploy lane (P5.1)
2. **Delete the old server now, or keep it until the new one is proven?** It bills while it exists; nothing on it matters (Debian mid-rebuild), but that is a money decision only you can make. → open — deploy lane (P5.3, owner money call)
3. **Recording posture (carried from 2026-09-03 §g.3, now urgent):** the template default records all calls to disk. Keep that for the first real calls, or disable (`recording.enable = false` in the private flake) until the GDPR consent/notification posture for PL/DE/US legs is decided? → done — answered 2026-09-16 (record ALL calls, consent accepted; ROADMAP open question 5)

---

**Bottom line:** the session proved the Telnyx account state (US active, Warsaw gone), built and tested the entire inbound webhook path, replaced the dead server with a clean cloud-init one, and paid one full install cycle to learn that a green VM suite never boots the metal disk path — the virtio-initrd fix is verified in both repos, and the deployment is one rescue-boot + reinstall away from the first live webhook-delivered SMS reply.
