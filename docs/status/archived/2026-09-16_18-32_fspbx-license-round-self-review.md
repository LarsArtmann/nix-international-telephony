# Status #3: license round + brutal self-review of the fspbx arc

Point-in-time: **2026-09-16 18:32 CEST**. Scope: this session's arc —
SIP ecosystem research → owner decision "use nemerald-voip/fspbx for now"
→ local trial appliance (login-verified) → license verification round.
Self-review per brutal-self-review skill, merged into one report by owner
instruction.

State right now: trial VM **alive** (pid 1603615, 37 min uptime,
GUI https://127.0.0.1:18443/login). Git tree **clean** — the auto-commit
daemon absorbed everything, including a **parallel session ("session2")**
working this repo concurrently (reports `18-00_todo-blitz-session2`,
`18-03_session2-self-review`, `18-15_medium-todos…hcloud-retired`; the
pre-existing `flake.nix` / `tests/backup.nix` modifications were theirs
and are now committed by the daemon). I never touched those files.

## a) FULLY DONE

1. **SIP/Go ecosystem survey** (`docs/research/2026-09-16_sip-ecosystem-survey.md`):
   every star count / release / push date pulled via `gh api` same-day;
   reputation claims labeled; LiveKit verdict (not used, deliberately).
2. **GUI decision captured**: owner picked fspbx; my templ/HTMX console
   concept correctly shelved (owner call, recorded in report #1).
3. **Trial appliance live**: Debian 13 QEMU VM, cloud-init-only management
   (no ssh from harness), fspbx installer run end-to-end, FreeSWITCH
   v1.11 + Postgres + Redis + supervisor stack inside.
4. **GUI login verified E2E**: API `POST /login` → 200 + session →
   `GET /dashboard` 200 (2026-09-16). Login mechanics solved and
   documented (XSRF cookie needs `unquote`; field is `user_email`).
5. **Four install traps diagnosed and documented** (composer HOME,
   dnsblockd-poisoned `checkip.amazonaws.com` → `EXTERNAL_IP`, portless
   redirect, urllib redirect-following).
6. **License verdict (this round)**: fspbx = **Apache-2.0** (verified from
   the canonical 201-line LICENSE file, not GitHub's badge); bundled GUI
   (nemerald-voip/fusionpbx fork, unpacked into `public/`) = **MPL 1.1 via
   file headers** (verified on fork `login.php` + upstream `index.php`);
   the $500/$1000 readme tables are a paid support membership, not a code
   license (installer ran with zero gating). Recorded as a "License"
   section in `docs/research/2026-09-16_fspbx-trial.md`.
7. Status reports #1 (16:43), #2 (18:00), this one; trial + research docs
   all `git add`ed for the daemon.

## b) PARTIALLY DONE

1. **License verification is repo-level, not artifact-level**: I verified → open — folds into the verdict sign-off row (only relevant if the VM is kept)
   file headers in the fork/upstream git trees, but NOT the release
   **tarball** the installer actually unpacks (tarball ≠ tree is possible).
2. **The installer's pinned fusionpbx release tag was never positively → open — same (verdict row)
   identified**: my grep of `install/install.sh` for the release URL
   returned EMPTY and I proceeded anyway, inferring v1.2.6 from
   `version.json` + latest release. Unclosed evidence — worst item of
   this round.
3. **Header sweep sampled, not exhaustive**: 2 files checked; the fork's → open — same (verdict row)
   new fspbx-integration files (Laravel `index.php` etc.) carry no header
   at all, and I did not sweep `app/`/`resources/` systematically.
4. **Trial durability**: VM state lives in `/var/tmp` (dies on host → done — pre-sip-wiring snapshot taken (21:04); VM fate = verdict row
   reboot); **no `qemu-img` snapshot** taken of the known-good disk.
   Known since report #2, still unfixed.
5. **SIP wiring**: zero (gated on owner question g2). → done — SIP wiring round executed 21:04
6. **docs-health HARVEST** of reports #1/#2 into TODO_LIST/ROADMAP: not → done — harvested by the 19:05 plan + TODO_LIST
   run (I self-imposed an "owner gate"; the skill says harvest is my job).
7. Ecosystem survey's verification-status table has no license → done — license cross-ref added 2026-09-16 docs-health round
   cross-reference to the trial doc's new License section.

## c) NOT STARTED

1. A real call through the appliance (no extension, no softphone, no RTP). → moot — a real call was placed via vmclient.py (21:04)
2. fspbx update path (`update.sh`) — never exercised. → Won't-implement — trial closed; update path never relevant
3. Appliance backup (pg_dump / file copy) — nothing backed up. → Won't-implement — trial closed; nothing to back up
4. Production plan: Hetzner Debian box, DID/trunk choice (docs/providers → moot — gated on the adopt/kill verdict, answered: NixOS-first
   re-verification) — all gated on the adopt/kill verdict.
5. FEATURES/README/AGENTS reconciliation for the fspbx direction; archiving → done — verdict recorded + FEATURES reconciled 2026-09-16 docs-health round
   the 16:43 console-concept milestones if superseded.
6. Coordination with the parallel session2 (its reports mention → moot — both sessions merged; trial closed
   "hcloud-retired" — possible direction overlap with the prod-plan work).

## d) TOTALLY FUCKED UP

1. **Three ghost hunts during the trial** (owned in report #2, still
   true): theorized about firewalls while guest iptables counters showed
   ZERO packets arrived; sed-patched a `fastcgi_param HTTP_HOST` that does
   not exist (grep-before-sed violated); read `ECONNREFUSED` as a
   first-hop failure when it was urllib silently following the portless
   redirect. Each cost a VM cycle.
2. **Missed pre-flight dependency audit**: I read the installer source
   before running it but did not enumerate its outbound URL dependencies
   — `checkip.amazonaws.com` is dnsblockd-poisoned on this host, which
   cost a full install cycle.
3. **`agentic_fetch` flail early in research**: retried a tool failing
   with a json unmarshal bug twice before pivoting to `gh api`.
4. **This round's API flail**: fetched `contents/readme.md` (404) before
   using the `/readme` endpoint; and the empty release-pin grep (b2) —
   same class as a security scanner reporting `Issues: 0` on `Files: 0`:
   an instrument that measured nothing is not a pass.
5. **Trial superadmin password is in git history** (`FspbxTrial!2026` in
   docs). Accepted for a loopback-only throwaway VM; it must NEVER be
   reused anywhere real.

## e) WHAT WE SHOULD IMPROVE

1. **Pre-flight outbound-URL audit** of any third-party installer before
   first run on this host (dnsblockd poisons specific domains).
2. **Verify shipped artifacts, not repos**: the thing deployed is the
   release tarball; license/supply-chain checks must inspect that.
3. **Empty evidence = failure**: never proceed past a verification probe
   that returned nothing; close it or mark it unverified.
4. **Snapshot-before-mutate** VM state; relocate long-lived state out of
   `/var/tmp`.
5. **Default to a no-redirect HTTP probe** when debugging web endpoints.
6. **Parallel-session awareness**: check `git status`/`docs/status/` for
   sibling sessions at round start; coordinate instead of discovering
   their work via daemon commits.

## f) Next things (grouped by gate; ~43 items, brainstorm not commitment)

Decision-gated (owner g1/g3):

1. Verdict g1: fspbx production candidate or evaluation-only? → answered 19:20 — close properly (verdict: NixOS-first)
2. Verdict g3: repo pivots to surround fspbx, or stays NixOS-first? → answered 19:20 — stays NixOS-first
3. Verdict g2: wire SIP into the trial? → answered 19:20 — wire SIP (executed 21:04)

Trial hardening (do regardless):
4. `qemu-img snapshot` the known-good `disk.qcow2`. → done — snapshot taken 21:04
5. Relocate `/var/tmp/fspbx-trial` to a persistent path. → open — verdict row (relocation only if kept)
6. Read `install/install.sh` fully; positively identify the pinned → open — verdict row (loose end b.2)
fusionpbx release tag (closes b2).
7. Download that pinned release tarball; confirm MPL headers inside the → open — verdict row (loose end b.1)
artifact (closes b1).
8. Systematic license-header sweep of the fork's added files → open — verdict row (loose end b.3)
(`app/`, `resources/`, new top-level php).
9. Check `composer.json`/`package.json` license fields + vendored deps. → open — verdict row (loose end)
10. Draft a NOTICE/compliance note (only relevant if we ever redistribute). → Won't-implement — no redistribution planned
11. Document appliance backup procedure (pg_dump + `/var/www/fspbx`). → open — verdict row
12. Scrub the plaintext password from `console.log` if the VM lives on. → open — verdict row (kill path destroys the logs)
13. Exercise `update.sh` on a snapshot copy. → Won't-implement — trial closed
14. Re-verify the VM restart procedure after any QEMU arg change. → done — restart procedure documented in the trial doc

SIP wiring (if g2 = yes):
15. Add `hostfwd tcp/udp 127.0.0.1:15060→:5060`. → done 21:04 — hostfwd 15060 + RTP window added
16. Add a narrow RTP-range hostfwd aligned with guest iptables ACCEPTs. → done 21:04 — extensions created via their own models
17. Create extensions 1001/1002 via GUI (or API with the solved XSRF flow). → done 21:04 — vmclient.py REGISTER/INVITE/BYE proven
18. Register Linphone/MicroSIP from the host. → done 21:04 — 1001→1002 answered; RTP blocked by slirp (sandbox artifact)
19. Call 1001→1002; verify two-way audio (QEMU slirp NAT is the risk). → partial — 9196 was a dialplan miss (480); CDR verified via API, GUI render = verdict row
20. Call echo 9196; verify a CDR row appears in the GUI. → done 21:04 — CDR rows for all 6 calls via the bearer API
21. Verify voicemail/recordings render in the GUI. → open — verdict row (GUI rendering unverified)
22. If audio fails: set FreeSWITCH `ext-rtp-ip`/`ext-sip-ip` advertisement → done — verdict: slirp artifact, documented as a dead end
for the slirp NAT shape.

If adopt:
23. Hetzner Debian box plan (sizing, image, firewall baseline). → Won't-implement — verdict: not adopting
24. Re-verify DID/trunk provider claims in `docs/providers/` (drift rule). → Won't-implement — verdict: not adopting
25. Feature-parity checklist vs FEATURES.md (dialplan, ring groups, → Won't-implement — verdict: not adopting
voicemail, IVR, time routing, fax posture).
26. Migration plan: current NixOS config → fspbx DB. → Won't-implement — verdict: not adopting
27. Webphone parity: point the repo's sip.js phone at the appliance wss 7443. → Won't-implement — verdict: not adopting
28. Prod firewall: installer iptables + our hardening review. → Won't-implement — verdict: not adopting
29. Monitoring: supervisor units, CDR pipeline, fail2ban events. → Won't-implement — verdict: not adopting
30. Scheduled offsite backups. → Won't-implement — verdict: not adopting
31. fail2ban tuning + enable admin 2FA. → Won't-implement — verdict: not adopting
32. ACME TLS on the appliance (trial runs self-signed). → Won't-implement — verdict: not adopting

If kill:
33. `pkill -9 -f "disk.qcow2"`; `trash /var/tmp/fspbx-trial`. → open — TODO_LIST blocked row (verdict sign-off: kill path)
34. Annotate the trial doc with the verdict; research docs stay archived. → done — trial doc carries the verdict annotation; research docs stay as reference
35. Resume the NixOS-first TODO_LIST backlog. → done — NixOS-first backlog resumed (19:05 plan)

Docs hygiene (either way):
36. docs-health HARVEST of reports #1/#2/#3 → TODO_LIST/ROADMAP. → done — harvested (19:05 plan + TODO_LIST)
37. Collapse the 16:43 console-concept milestones if superseded → done — owner verdict NixOS-first collapsed it; P22 diff-drafter is the surviving remnant
(split-brain rule).
38. Cross-ref the License section from the survey's verification table. → done — cross-ref added 2026-09-16
39. CHANGELOG entry once the direction settles. → done — research-docs CHANGELOG entry added 2026-09-16
40. AGENTS.md pointers once fspbx knowledge becomes enduring. → done — AGENTS.md + ROADMAP reference the trial doc
41. Run the `git log --all -S` tripwire over the daemon's recent commits → done — history rewritten (d7ac48f); gate green
(scrub discipline; parallel session committed too).
42. Review what session2 actually changed (flake.nix, tests/backup.nix) → done — session2 work identified and gates green 18:01
before building on the tree.
43. Run `nix flake check` after session2's changes landed (repo gate). → done — full gate green 18:01

## g) Questions I cannot answer myself

1. **g1 (business)**: is fspbx a production candidate or eval-only? I can → answered — close properly; verdict NixOS-first, fspbx kept as feature reference (sign-off pending, TODO_LIST blocked row)
   verify the software, not your risk appetite for DB-as-config-truth on a
   Debian appliance vs this repo's declarative NixOS model.
2. **g2 (time/ports)**: wire SIP into the trial now (host port → done — SIP wired and calls proven 21:04
   commitments + ~1–2 h of cycles), or is GUI-only enough for the verdict?
3. **Coordination**: a parallel session2 is committing to this repo → moot — both threads merged into the 19:05 plan
   concurrently (reports 18:00–18:15, "hcloud-retired"). What direction is
   that work taking, and should the fspbx track coordinate with or stay
   clear of it? I can read its diffs but not its intent.

— Reported, waiting for instructions.
