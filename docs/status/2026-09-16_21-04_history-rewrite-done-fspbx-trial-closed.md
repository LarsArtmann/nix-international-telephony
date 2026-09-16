# Status #4: history rewrite executed; fspbx trial closed with evidence

Point-in-time: **2026-09-16 21:04 CEST**. Scope: the owner's five G2
answers executed — P19.2 (history rewrite) and P7 (fspbx trial closure) —
plus the Pareto plan P0–P25 (19:05) that ordered them. Format: `.md` + a–g
per standing owner override of the status-report skill.

## a) FULLY DONE

1. **P6 owner decision pack**: consent = record ALL calls by default
   (P4 ungated); fspbx = close properly; deploy = not now; security =
   history rewrite now (key rotation stays blocked); DIDs = defer. All
   recorded in TODO_LIST/plan log.
2. **P19.2 history rewrite COMPLETE**: git-filter-repo replaced all 23
   pattern spellings (blobs + 1 commit message) across the 3 offending
   09-03 commits; `scrub-check.sh --history` OK for the first time;
   force-push with lease; origin/main re-verified 0 pickaxe hits; tags
   v0.1.0/v0.2.0 predate the leak (hashes unchanged); CHANGELOG Security
   entry warns old-clone holders; local gc + temp files purged.
   Discovery en route: the scan's 4th "hit" commit (51dc0fe) was the
   daemon's own CLEANUP commit (pickaxe counts removals) — not a leak.
3. **P7 fspbx trial closure COMPLETE** (cycles 009–017, snapshot
   `pre-sip-wiring` first):
   - Extensions 1001/1002 created via fspbx's own models/services from a
     Laravel CLI bootstrap; Sanctum PAT minted the same way.
   - End-to-end from the host with this repo's `tests/vmclient.py`:
     REGISTER+digest ✓, INVITE→200 answered ✓, BYE ✓, **CDR rows for all
     6 test calls** via `/api/v1/domains/{uuid}/cdrs` (bearer API) ✓.
   - Their runtime sync verified: `SipProfileService::save()` → ESL
     `xml_locate` regen + profile rescan (config truth IS the DB;
     `sip_profiles/*.xml.noload` inert by design).
   - Fax/SMS apps: present in fork + API (untested — needs T.38 trunk).
4. Plan P0 self-resolved: the daemon's push loop recovered (23 commits
   were already on origin at commit time).
5. Docs: trial doc gained the SIP-wiring round + license sections;
   TODO_LIST harvested (14 rows) + decision annotations; plan §6 log.

## b) PARTIALLY DONE

1. **RTP audio in the trial**: NOT achieved. Five NAT mechanisms tried
   (DB ext-ips, generated files, service sync, `apply-nat-acl`,
   `local-network-acl`); sofia kept advertising the unroutable guest IP
   in SDP. Honest verdict: **slirp sandbox artifact, not an fspbx
   defect** — a public-IP deployment does not have this problem class.
   Everything else about calling is proven (see a.3).
2. **9196 echo**: dialplan miss (480) — the seed ships no echo extension
   under `admin.localhost`; extension-to-extension (via voicemail
   fallback) used as the answer-proof instead.
3. The GUI's `/api/*` cookie-session flow still 302s for scripted
   sessions (SPA-stateful middleware archaeology abandoned for the PAT
   route, which works perfectly) — noted, not chased further.

## c) NOT STARTED

P1–P5 deployment lane (owner-deferred), P8+ UX lanes, P9 trunk
hardening, P15/P16 SMS/fax enablement, P18 release, P19.1 key rotation.

## d) TOTALLY FUCKED UP

1. **Wrong FS config path, twice**: assumed `/usr/local/freeswitch/conf`
   (source-install default) — this appliance uses Debian layout
   `/etc/freeswitch` (binary `/usr/bin/freeswitch`, no `-conf`); then my
   self-locating `find` lost a race to `/etc/freeswitch.orig` (the
   pristine backup). Two cycles burned on a path the unit file printed
   on cycle one. Lesson: read the ExecStart BEFORE the first sed.
2. **The License section header got eaten** by my own trial-doc edit
   (insert-without-anchoring) — caught and restored immediately.
3. The eternal redirect trap: urllib following the portless 302 AGAIN
   (third time this project) before I reached for the NoRedirect handler
   — it is now muscle memory one step too late.

## e) WHAT WE SHOULD IMPROVE

1. Verify config paths from process/unit evidence first; never from
   install-method assumptions.
2. slirp trials: accept that SDP advertisement is a sandbox wall —
   time-box NAT gymnastics to 2 attempts next time (this round: 5).
3. Bearer-PAT-via-CLI-bootstrap beats fighting SPA session middleware —
   mint early, skip the archaeology.

## f) NEXT (delta over plan §2; full list lives there)

1. P7.7 verdict memo was folded into this report + trial doc (below)
2. Owner verdict on the recommendation: kill the trial VM (evidence
   gathered) and stay NixOS-first, with fspbx as feature reference
3. P1 deploy lane when the owner is ready (rescue-boot + reinstall)
4. P8 webphone transfer (first UX lane item)
5. P23.1 AGENTS.md: encode the slirp/pickaxe/cleanup-commit lessons
6. TODO_LIST: P7 row retired this commit; P19 row already gone

## g) Question I cannot figure out myself

1. Accept the verdict recommendation? (kill VM; NixOS-first stands;
   fspbx kept as reference for features their stack proves out — fax/SMS
   apps, fail2ban posture, ESL-integrated profile sync). The VM is left
   RUNNING with disk + `pre-sip-wiring` snapshot intact until you say.

— Reported. Waiting for instructions.
