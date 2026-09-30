# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added (2026-09-30)

- Docs-health round 9 (WhatsApp-report harvest + archive): the WhatsApp
  session report's open-work sections are fully routed — 41 scoped items
  (§b/§c/§f/§g) carry inline routed verdicts pointing at their new homes,
  and the snapshot is archived. Harvest: 12 new TODO_LIST rows (the
  full-gate-over-merged-tree debt, WhatsApp status-event `to`-shape
  tolerance, per-channel 16 MiB media cap, bridge WhatsApp VM suite,
  docs/runbook/prod-example bundle, OpenAPI spec cross-check, smoke
  probe, reconciler WABA lane, operator channel rendering, test fixture,
  eval warning), a WhatsApp-depth raw-idea cluster + webphone-side
  channel affordances in ROADMAP, and two new ROADMAP open questions
  (WhatsApp product direction, number topology); the WABA/live-lane row
  already existed and was deduped against. Living-doc truth fixes:
  AGENTS BuildFlow pytest count 45 → 73, FEATURES WhatsApp row status to
  the legend vocabulary (`PARTIALLY_FUNCTIONAL`), TODO_LIST CI-verdict
  row rewritten to the post-kill-streak facts. Skill lane:
  docs-health `annotate-prose.py` gained kind `r` (routed verdict, no
  strike — the prose mirror of the 2026-09-30 annotate-rows `r` kind),
  fixture-tested.
- Relock chain attribution (the runbook's say-so rule — both moves
  landed as daemon heuristic commits with no hand-authored line):
  webphone input `4b769a5` → `93d3a53` → `a8868fd` (2026-09-30
  11:49/11:57). Upstream delta `4b769a5…93d3a53` is the 24-commit
  go-error-family adoption wave (store/session/pbx/crm/config seams,
  server webhook page-count validations, SECURITY.md + docs); the
  `93d3a53…a8868fd` tail is docs + `internal/web/assets/app.css` only.
  No `.templ` markup or bundle delta in either move, so browser E2E was
  not triggered; `nix build .#webphone` green at `a8868fd`
  (webphone-2.7.0). The webphone VM suites ride the full-gate TODO row —
  the merged tree has not been through a full gate yet.
- CDR attribution for inbound PSTN calls: DID entries in the public
  dialplan now stamp `accountcode` (the dialled extension itself, or a
  ring group's `voicemailMember`) before transferring into the default
  context, so inbound calls appear in that extension's phone-API
  History instead of being invisible to every panel (only
  REGISTER-originated legs carried an accountcode before). Any other
  `didDestination` (IVR, conference) stays unstamped — no honest single
  owner. VM-proven in `tests/pbx.nix`: generated-dialplan stamp for
  both arms plus a real inbound DID call landing in `Master.csv` with
  the accountcode column set (found live on pbx.artmann.tech where
  callers' calls never showed in the webphone History, 2026-09-30).
- WhatsApp support in the Telnyx messaging bridge: `whatsapp:+E164`
  destinations (typed in the webphone composer) ride Telnyx's
  dedicated WhatsApp API (`POST /v2/messages/whatsapp`) — free-form
  text (≤ 4096 B) and exactly one medium per message (image/video/
  audio natively; gif/tiff/vcard/mov honestly as documents with
  filename; caption ≤ 1024 B; 5 MiB image pre-flight; HEIC keeps the
  iPhone-fix copy), with 24-hour-window rejections humanized to name
  the template fix. Inbound `type: WHATSAPP` events (both documented
  payload shapes) forward to the webphone with a `whatsapp+<digits>`
  sender tag so threads key identically in both directions — the tag
  deliberately rides webphone's dialable sanitizer, which keeps
  letters. Fails closed with setup guidance until
  `services.telephony.messaging.whatsapp.enable` + `.did` name a
  portal-verified number (never defaulted from `messaging.did`);
  eval-checked happy + rejection paths. Template sends stay
  portal-side by design (28 new stdlib tests → 63 in the bridge
  suite, 73 total; API shape verified against Telnyx docs
  2026-09-30, see docs/providers/telnyx.md §WhatsApp).
- Round-6 arc closed: full-gate buildflow run completed in the
  documented green shape (3m21s, 93% cache; local `nix flake check`
  ALL green over 32 checks in 194s; findings gate carries EXACTLY the
  4 documented port-collision errors; bandit's 257 rows are banner
  rows with `file: "."`, vulnix advisories 68 -> 15 toolchain-class —
  accepted envelope; plan-gate deviation recorded: origin CI
  infra-blocked, so the local pipeline stands as the tail's proof).
  The round-6 plan is annotated (all 27 M-rows routed, Step-3
  inheritance note) and archived; markers gate 69 files / 0 unmarked.
  Docs-health round 8: living-doc truth pass (AGENTS: markers preset
  + flake-check wiring, CI-kill protocol variants; FEATURES: check
  count 32; TODO_LIST: verdict row rerouted to the owner support
  lane, M11 closed, M23 closed).

- Relock chain attribution (the runbook's say-so rule, recorded here
  because the moves landed in daemon-absorption commits): webphone
  input `045edfe` -> `1bbc446` (CI-file-only upstream delta, commit
  `04562e7`) -> `a610845` (Go config handling + tests, no markup or
  bundle delta, commit `5ba5d2b`) -> `4b769a5` (vendorHash repair,
  attributed commit `3a77579`; webphone's own CI green on it and on
  `baa9c2f`). Browser E2E not triggered anywhere in the chain (no
  markup/bundle deltas); the webphone VM suites ride the flake check.
- Webphone `SECURITY.md` authored and landed upstream (`baa9c2f`,
  webphone CI completed green, run 36675268502): private-reporting
  first, per-surface triage, posture facts verified at module source,
  tags-trail-versions note for lock-riding consumers.
  `docs/DOMAIN_LANGUAGE.md` exists upstream as a draft; ratification
  is webphone ROADMAP open question g2 (owner).
- Skill lane: docs-health `annotate-rows.py` gained kind `r` (routed
  verdict, no strike — the house table grammar; refusal guard trips on
  existing routed markers, self-tested + fixture-tested against this
  repo's archived plan tables); drift-alarm cross-file port evaluated
  and recorded (not now; trigger = second adopter) in the skill's
  references/.

### Changed (2026-09-30)

- Origin CI verdict lane, kill-streak CLOSED: two completed FAILURE runs
  landed after the 10-kill ledger was written. Run 36695596874
  (`b3f1633`) is a REAL red — the pre-commit check caught
  daemon-committed nix files in unformatted shape — fixed two minutes
  later by the nixfmt commit `542443a`; run 36692071358 (`a207ad3`)
  failed with no failed-step logs (the infra shape); a third run
  (36696533753) was in flight on `542443a`. Three commits (the WhatsApp
  report + the two webphone lock moves above) were still unpushed at
  audit time. The "no code red anywhere" claim in the earlier ledger
  entry is superseded; the full current state lives in the TODO_LIST
  verdict row.
- Origin CI verdict lane: rerun protocol exhausted (3 attempts on run
  36642261029, all infra-killed). Kill ledger 2026-09-29 22:42 UTC ->
  now: 10 consecutive x86 `nix flake check` push-run kills (9×
  "The operation was canceled", 1× exit 143 SIGTERM at attempt 3),
  every evaluated check green at each death; aarch64 job 10/10 green;
  webphone-repo x86 runs (including `nix build`) completed green in
  the same window; repo public, no concurrency group, no timeout hit,
  no code red. No completed verdict exists for the pushed tail;
  last completed green remains `b8f211d` (run 36538651011). Owner
  lane: support ticket vs wait-out vs job-split — the full ledger and
  run IDs live in the TODO_LIST verdict row.

- `checks.markers-check` flake gate wired (docs-drift pattern): the
  archive-marker sweep now runs in CI, self-test included. The
  plan-preset question is settled in the checker itself: `## Step 2`
  M-tables of planning snapshots are scoped like open-work sections
  (every archived plan already satisfies it — 68-file sweep zero,
  including the round-4/round-5 tables), while `## Step 3` fine rows
  stay bare by the recorded inheritance convention (the italic
  "every fine task inherits its parent M-row verdict" note). Check
  count derived: 32 on x86_64-linux.
- The new gate immediately paid for itself: the first full sweep
  caught a real annotation loss — commit `5ba5d2b`'s table
  normalization had dropped the verdict column from four §b rows of
  the archived round-4 M01–M16 report. Restored in house grammar
  (in-cell `→ done` appends, immune to column re-normalization).

- Host-identity reality check answered: `scripts/verify-live.sh
  pbx.artmann.tech` passed 14/0 (1 WARN reverse-DNS stall, 1 SKIP
  token-gated reader) and the service shape proves the live host IS the
  v2 telephony deployment — webphone `/healthz` 200 + `/phone-api` 401
  gate (v2-only traits; the old billing server was abandoned
  mid-Debian-rebuild 2026-09-14), receiver health ok, TURN/SIP listeners
  open, LE cert notBefore 2026-09-16 postdating the initrd fix. The
  rescue-boot/reinstall path is dead; the P1–P5 row rerouted to
  owner-close-out (webhook URL PATCH, outbound loop, IPv6+AAAA — AAAA
  confirmed absent —, old-server delete, §5 checklist, first calls).
  CI tonight: four pushes (f868e24..5ba5d2b) all died as
  runner-reclamation cancels (`The operation was canceled` mid-eval, no
  check red; aarch64 job green each time); rerun of the tip run in
  flight.

### Changed (2026-09-29)

- CI verdict proven: the third post-relock run (`36514948861`, head
  `b99ff74`) also died as an infra cancellation (`##[error]The operation
  was canceled` mid-eval, no code error); its rerun completed **green**,
  giving main its first completed green verdict at/after the relock.
- Relock: webphone input `3d8df3f` -> `045edfe`, picking up the MMS
  Content-Type stamping producer (`f6239fa`, verified reachable from
  origin/main first). Upstream delta is docs + flake restructuring +
  module hardening (StateDirectoryMode 0750, UMask 0077, backup destDir
  assertion); no markup or bundle change, so browser E2E was not
  triggered. Proof: `nix build .#webphone` (webphone-2.7.0), fast
  gates, and the webphone VM suites (`telephony-webphone`,
  `telephony-fax`, `telephony-fax-feed`) all green. The bridge's
  preferred typed-attachment path is now live at the lock.
- Messaging bridge: outbound MMS attachments are typed by the part's
  declared Content-Type when the producer sends one (the producer-side
  stamping landed in webphone main AFTER this repo's locked rev
  `3d8df3f` — upstream is still version-labeled 2.7.0 and its tags stop
  at v2.6.0, so cite revs, never "webphone >= X.Y"); magic-byte
  sniffing stays as the fallback and remains the active path at the
  current lock until the next relock picks the stamping up. The HEIC
  rejection fires on the declared type now too. Cross-repo verified on
  real webphone wire bytes; 3 new bridge contract tests (35 total).
- Lock refresh: webphone input relocked `932c181` -> `3d8df3f` and
  nixpkgs to the 2026-09-28 unstable rev (`nix build .#webphone` ->
  webphone-2.7.0 proves the lock builds). The two CI runs after the
  relock (2026-09-26/29) were canceled by GitHub runner-shutdown
  signals while green — infrastructure, not code failures; the last
  completed verdict stays green at `f2aa2be`.
- Dev shell: `vulture` and `gh` pinned next to the BuildFlow lint
  binaries (dead-code checks and CI-verdict reads no longer depend on
  the moving nixpkgs registry revision).

### Fixed (2026-09-29)

- Full-mode BuildFlow triage (first full run since the binfmt outage):
  the pipeline surfaced a 24-finding Python lint backlog across files
  that had never seen a full-mode run — all fixed: ruff (PLW1510
  explicit `check=False` in lock-doctor, PIE810 startswith tuple,
  FLY002 f-strings in drift_alarm, EXE001 exec bits on two test
  scripts), mypy (Optional guards in the telnyx test loaders, regex
  match guards in vantage_probe, a `list[dict]` annotation), bandit
  medium+ curated to zero (12 `# nosec` on the 2026-09-26 bridge-wave
  urlopen/MD5 sites), vulture back to zero (whitelist extended with the
  http.server dispatch surface; genuinely dead code deleted: api.py's
  consumer-less MAX_JSON_BODY, dialplan_sim's unreferenced
  CDR_TEMPLATE_FIELDS/WDAY_NAMES, whose comment even claimed a reference
  that never existed). Side finding fixed: the bridge test's
  `responses` attribute shadowed http.server's error-message catalog —
  renamed to `stub_responses`. The full gate's only remaining exit
  errors are the two documented port-collision noise pairs; vulnix
  changed shape (no longer crashes; reports ~68 build-closure toolchain
  advisories — recorded as the noise class). nix-flake-check green at
  the final tree inside the run.

- Pre-commit gate was silently absent: the auto-commit daemon cannot
  bypass an *installed* hook (source-verified: it shells out to
  `git commit` with no `--no-verify`; its `skip_hooks` option is dead
  code), but the hook file itself was missing — git-hooks.nix refuses
  to reinstall while `.pre-commit-config.yaml` exists, and
  `pre-commit install` refuses whenever `core.hooksPath` is set (the
  global `~/.gitconfig` points it at a nonexistent `.githooks`). A
  canary with a scrub-pattern-shaped fake key was correctly BLOCKED
  once the hook was restored. New `scripts/heal-pre-commit-hook.sh`
  makes recovery one command (devshell entry, then HOME-masked manual
  install fallback).

### Added (2026-09-29)

- Docs-health round 7: the five loose 2026-09-29 snapshots (round-6 docs
  report, round-4 M17–M27 completion, round-5 status, round-4 + round-5
  Pareto plans) now carry inline verdict markers on every scoped item
  (§b/§c/§f/§g — the round-6 50-row §f table included; plan fine tasks
  inherit their M-row verdicts, recorded in-plan) and are archived; both
  snapshot dirs hold zero loose files and the marker gates pass over all
  64 archived snapshots. Living-doc truth fixes: TODO_LIST gained the
  host-identity reality-check (round-5 M05) and markers-gate flake-check
  wiring rows, the P1–P5 evidence now cites the completed green CI
  verdict at `b8f211d` (the stale "local main 1 commit ahead" webphone
  evidence corrected to the pushed `89502ee`), FEATURES inventories the
  2026-09-29 gate scripts and the `telephony-failregex` check, README's
  layout gains `scripts/` and the real devShell inventory, ROADMAP's
  vulnix wording matches the no-longer-crashes reality, and the AGENTS
  marker-gate line is count-agnostic.
- Docs-health round 7 self-review arc: the archived round-7 report's false
  claims corrected inline (commit count, "zero daemon races", the git-mv
  "race" misdiagnosis — `git mv` fails deterministically on untracked
  files), its health-report math recomputed under the skill's actual
  format (audit-time Accuracy 5.25 / Fitness 9.25), the evening debts
  drained instead of queued (full pre-commit battery 6/6 + targeted nix
  checks at the final tree; webphone `89502ee` verified at primary source
  — CI green on push, and the red `a206fe4` run is a Dependabot PR branch,
  not main), the flake check count pinned exactly (31 on x86_64-linux, via
  `nix eval` — a first-draft \"32\" was a miscount and is corrected here
  and in FEATURES in the same arc), and the structural-anchors +
  git-add-before-git-mv lessons codified in
  AGENTS.

- Origin CI verdict secured for the whole round-3/4/5 train: after five
  consecutive GitHub runner-shutdown cancels (07:16-07:45 UTC, all
  mid-eval, ci.yml unchanged since the 02:56 green run, aarch64 job
  green each time — fleet churn, not code), run 36538651011 completed
  **success** at `b8f211d`, giving main its first completed green
  verdict covering the relock, all guards/checks/scripts, and the
  round-5 plan commits. The webphone repo's CI also went green at the
  pushed cross-link rev `89502ee`.

- `scripts/markers_check.py`: the per-item archive-marker gate, promoted
  from a one-off session heredoc — scoped sections (§b/§c/§f/§g),
  block-aware verdict detection, header/separator exclusion, word-boundary
  marker matching ("unanswered" is not a verdict), planted-miss
  `--self-test`. Its first standing sweep over all 59 archived snapshots
  reports zero unmarked items — and it caught one real miss the original
  heredoc sweep had skipped (a 2026-08-29 review-only item), now
  annotated. Upstream filings batch 2 landed with it: BuildFlow#28
  (findings-gate ignore mechanism for the accepted-noise class),
  git-hooks.nix#754 (non-convergent hook healing, external),
  pma#341 (dead `skip_hooks` config); the webphone repo's local
  cross-link commit is pushed upstream (CI verdicts it).

- Operator security hardening: FreeSWITCH-state read ACLs now target a
  new operator-only `telephony-fs` group (nginx keeps the shared
  `telephony` group for htpasswd/recordings and can no longer read the
  FS state tree, `core.db` included), and audio-stream tokens are
  HMAC-keyed with a dedicated secret — `operator.streamTokenSecret` /
  `operator.streamTokenSecretFile` (at most one; unset means a fresh
  random secret each boot), rendered `0640 root:telephony-fs` so only
  the API process can read it. The API binary gains
  `--stream-token-secret-file` (ESL password remains only as the bare
  binary's fallback). Operator VM suite extended: nginx group
  non-membership, ACL group on the state tree, secret file mode,
  nginx-read-denied, plus the existing token-authed audio flow green.
- `tests/configjs_check.py`: the webphone `/config.js` wire contract
  (exact key set, lowercase contact keys, per-response TURN REST pairs)
  extracted from `tests/webphone.nix` into a reusable, self-documenting
  fixture (positive + negative arms proven locally, suite green in-VM).
  The contacts seam is now cross-linked in all three places: the
  fixture, `tests/browser-e2e.py`'s round-trip, and upstream's
  `internal/server/configjs_test.go` (producer side).
- Marker meta: the open-row marker convention (routed `→ open` verdicts
  beat row-uniformity; §b/§c/§f/§g scoping; `→ corrected` appends for
  stale markers) is recorded in AGENTS.md Conventions, and a retro
  per-item + row-uniformity sweep ran over ALL archived snapshots —
  90 evidence-cited verdicts added across 15 files (the 2026-09-18
  extraction report's 50-row §f table included), zero unmarked scoped
  items remaining; the 3 PARTIAL and 128 open-routed rows are the
  recorded accepted style.
- AGENTS.md slimming: 16.7 KB -> 15.2 KB — history moved out (relock
  ritual now points at its ops-runbook home), stale facts fixed
  (upstream webphone HAS build CI since 2026-09-29), prose compressed
  with every load-bearing trap kept inline.

- `checks.telephony-failregex`: an eval-time `runCommand` gate running
  real `fail2ban-regex` over both shipped fail2ban filters against
  canned SIP-scanner log lines, with exact match-count assertions —
  the date-strip and `ignoreself` traps are now caught in seconds
  instead of only by the full fail2ban VM suite. Proven both ways:
  green on the shipped filters, and a deliberately broken filter makes
  the check FAIL (negative arm exercised before landing).
- Vhost split-brain guard: the stack wiring now forces
  `services.webphone.nginx.enable = false`, and an eval assertion turns
  any harder override into a legible error — upstream's optional nginx
  vhost generator can no longer silently stand a second, colliding
  vhost next to the stack's own if an upstream default ever flips.
- Health-check unit: a `/healthz` probe for the webphone app (when
  enabled) — the UI has been a service that could die quietly since the
  v2 switchover. The monitoring VM suite gained a stop-webphone →
  FAIL → recover arm proving the probe actually fires.
- `scripts/lock-doctor.py`: mechanizes the lock review — locked revs
  vs upstream HEADs per input plus the last completed CI verdict per
  head, treating runner-canceled runs as NO VERDICT instead of red;
  `--self-test` included.
- `scripts/verify-live.sh`: the deploy.md §5 checklist as a
  parameterized off-host probe (domain required; TLS-issuer check with
  a single glob; `/healthz`, `/phone-api` 401 and messaging-receiver
  arms). Live-proven against the deployed host: 14 checks, 0 failures.
- docs/ops-runbook.md: lock-bump runbook section for the tracked-main
  webphone input — pre-flight checks, the gate ladder (fast checks →
  binary build → webphone VM suites → browser E2E when markup/bundle
  moved → full gate), the forward-pin-to-first-green-rev rule on
  upstream breakage, and the hand-authored commit convention.
- github:LarsArtmann/webphone now runs build CI on push (Go build +
  `go test ./...` + fast checks, action refs pinned by SHA); its first
  run completed green, so "first green rev" is provable upstream
  instead of only through this repo's suites.

### Added (2026-09-26)

- `services.telephony.messaging.*`: the Telnyx messaging bridge, moved
  upstream from a private deployment repo where the public module had
  been assuming it (the `operator.smsMessageStore` example pointed at
  its JSONL all along). Loopback stdlib receiver + inbound webphone
  bridge + outbound gateway (`modules/telephony/messaging.nix` +
  `telnyx-webhooks.py`), nginx locations owned by the module's vhost
  (`web.nix`), copytruncate logrotate, three LoadCredential-backed
  secret options, and eval-checked happy/rejection paths. The 32-test
  contract suite travels with it (`tests/test_telnyx_bridge.py`).
- `services.telephony.state.*`: read-only derived options exporting
  module-owned state paths (plain-copy dirs, sqlite-consistent
  databases, messaging media dir) for deployment backup tooling.
- `scripts/telnyx_reconcile.py` + `tests/test_telnyx_reconcile.py`
  (10 tests): the Telnyx account reconciler engine, now generic — the
  desired state rides a deployment-owned `--desired` JSON instead of a
  hard-coded dict. `tests/vantage_probe.py`: the Telnyx trunk vantage
  probe (source-IP screening diagnosis), parameterized.
- pytest-test un-skipped in BuildFlow: the two new stdlib suites are
  collectible now; VM checks remain the system-level gate.

### Fixed (2026-09-26)

- Webphone lock breakage chain, tail: `2bbbc2e` itself
  shipped an upstream wire bug — `SharedContact` carried no JSON tags,
  so `/config.js` emitted Go-style `Name`/`Number` while the suites
  assert lowercase `name`/`number` (`checks.telephony-webphone` died
  with `KeyError: 'name'`; CI red across four runs 2026-09-24/25).
  Upstream fixed it in `e43fea8` (lowercase marshaling + a wire test
  pinning the shape); the 2026-09-26 relock to `0230ead` (webphone
  2.7.0, with nixpkgs `e94cb152`) picked the fix up. Verified green
  on all three arms: `nix build .#webphone`, CI `nix flake check` on
  the relock commit (eval, packages, VM suites, aarch64 TCG boot), and
  the on-demand browser E2E re-run — v2.7.0 changed markup (EmptyState,
  `tw.css`), so `CONTACTS-ROUNDTRIP-OK` through `E2E-OK` had to be
  re-proven. Note for future relocks: upstream webphone has NO build
  CI (only Dependabot/Dependency Graph workflows) — "first green rev"
  can only be proven by this repo's suites, never read off upstream
  checks.

### Fixed (2026-09-25)

- Webphone lock breakage chain (2026-09-24 evening): the 13:52 lock
  update imported an upstream-broken webphone revision (stale
  `vendorHash` — the go-modules proxy served no zips for four deps);
  root-caused via GitHub compare and forward-pinned to the first green
  upstream rev (`94ae28d`, vendorHash-only fix), then onward with the
  evening's lock moves (`2bbbc2e`). `nix build .#webphone`,
  `checks.telephony-webphone` and `checks.telephony-tls-turn` verified
  green at each relock; the 1776c3e..94ae28d delta was checked against
  every wire contract the suites assert. The forward-pin rule (tracked
  main means a lock update can import upstream breakage — pin to the
  first green rev and say so) is recorded in `docs/lessons/operating.md`.
- Formatter war closed at the root: BuildFlow's oxfmt and the flake's
  treefmt both reformatted `operator.js` (two formatters, one file set),
  and daemon commits shipped unformatted intermediates — `checks.format`
  went red three times over it. `.buildflow.yml` now excludes the
  treefmt-owned operator webroot from BuildFlow's formatters (the proven
  webphone-repo pattern) and the file is prettier-canonical again
  (verified with the pinned prettier 3.9.6 after the last re-mangling).
- Bandit repo-wide signal restored to zero real findings: the four true
  positives in `tests/browser-e2e.py` (B101 assert + three `/tmp` marker
  paths) annotated at the issue lines in the file's existing `# nosec`
  style; the other ~80 were banner/log noise.
- nix-checker triage recorded in `AGENTS.md`: the four port-collision
  advisories are false positives by construction (a QEMU guest port
  forward compared against a fail2ban jail `port`, and the NAT suite's
  deliberate tcp+udp forward pair); accepted alongside the FOD-hash
  advisories.

### Added (2026-09-24)

- `checks.docs-drift` (`tests/drift_alarm.py`) grew two citation arms on
  top of the duplication alarm: a TODO row citing a `docs/status/` or
  `docs/planning/` snapshot now fails (archived citations already did;
  live ones rot into that class the day the snapshot is filed away),
  and a row citing a repo-relative path missing from the tree fails
  (the ghost-citation class the 2026-09-18 round-4 rebuild repaired by
  hand). Both arms plus the originals are negative-tested by
  `drift_alarm.py --self-test`, which the check runs before the real
  gate.
- deploy.md §5 verify checklist: operator-window login + health-card
  probe, phone-API history/voicemail-summary probes with extension SIP
  credentials, and the fax feed-unit/directory probe (P38 remainder).
- ops-runbook: extension-password rotation note — the phone API auth
  cache (`AUTH_CACHE_TTL`, 300s) keeps the OLD password valid after a
  rotation; wait it out or restart `telephony-operator` to drop it.
- Operator API tail (phone API + operator window): CDR pagination
  (`offset` + `more` past the 500 clamp) with prev/next paging in the
  dashboard, CSV export of the CDR viewer (`/api/cdr.csv`), a
  per-extension brute-force damper for the phone API (5 failures lock
  the extension for 15 min — 429 even for correct credentials, the
  lock beats the auth cache), single-range HTTP seek on voicemail
  audio (206 + 416), mark-read/unread via mod_voicemail's `vm_read`
  (box counts re-asserted through `vm_boxcount`), and a
  voicemail-db-reachability probe in `/healthz` (503 when the DB is
  unreachable). The API now also verifies a message uuid belongs to
  the authenticated mailbox before delegating `vm_delete`/`vm_read`
  (mod_voicemail's own SQL scopes by uuid only — an authenticated
  extension could have deleted any mailbox's message by uuid).
- NAT runtime suite (`checks.telephony-nat`, `tests/nat.nix`): a
  two-NIC VM topology (port-forwarding router + PBX behind it) drives
  a real call from the OUTER network and asserts `natAddress` lands in
  the 200 OK's Via, Contact and SDP connection line with no
  private-address leak — the FEATURES `natAddress` row moves to
  FULLY_FUNCTIONAL. `tests/sip.py` gained `--dump-dialog` for the
  advertisement asserts.
- Backup suite now proves the recovery path, not just the snapshot:
  canary → backup → `restic ls` → delete → `restic restore` returns
  the exact bytes; the SSH host-key identity (`/etc/ssh`) rides in the
  snapshot (also added to the pbx-prod template's backup paths, so a
  disaster restore keeps the host's SSH identity instead of breaking
  every client's known_hosts).

### Fixed (2026-09-24)

- `checks.telephony-tls-turn`: the suite still asserted the removed
  nginx config.js shadow file at `/var/lib/telephony/config.js` and
  never waited for the webphone app that serves `/config.js` now —
  both fixed (suite was red since the 2026-09-23 switchover).
- `checks.telephony-webphone`: the `phoneApi` grep expected the old
  pretty-printed config.js; the app renders MINIFIED JSON since the
  v2 switchover. Also pins the contacts wire keys as `Name`/`Number`
  (upstream `SharedContact` carries no json tags while the island
  reads lowercase `name`/`number` — shared contacts silently drop
  client-side; fix prepared in the webphone clone, flip pending its
  push + relock).
- `scripts/ahead-check.sh` never actually fetched: it passed the
  tracking ref (`origin/main`) to `git fetch` instead of the remote,
  so every run exited 2 "cannot judge". Now fetches the remote (and
  the `@{upstream}` ref is quoted — the shellcheck SC1083 batch is
  curated away; the scrub-check `cd` gained its `|| exit`).
- Bandit detect-only findings in `packages/telephony-operator`
  curated inline (B404/B607 on the fixed-argv subprocess calls, B405
  + B314 on parsing the operator-generated dialplan XML); the
  AUDIO-DEBUG prints in `tests/operator.nix` are annotated as
  deliberate failure evidence.

### Fixed (2026-09-22)

- Browser E2E harness, the 2026-09-22 run-1 failure chain (found while
  validating the webphone registration-loss fix): `recover_via_reload`
  filled the login form blindly and crashed with
  ElementNotInteractable whenever a live cookie session RESUMED without
  it (the SQLite store survives restarts) — it now only fills the form
  when it is actually displayed. The notification-permission marker is
  conditional on the boot mode (a resumed page never clicks login, so
  `requestPermission` legitimately cannot run; `NOTIF-SKIPPED-RESUMED-BOOT`).
  Pre-call-phase failures now dump BOTH pages' island #log, pill and
  console (only the call phase did; run 1 lost all browser state).
  The FS-OUTAGE-READY marker window is 300s (dial_into_call's
  reload-recovery worst case legitimately exceeded the old 120s).

### Fixed (2026-09-19)

- `config.js` render: contacts were double-escaped — `escapeJs` ran
  before `builtins.toJSON`, which escaped the inserted backslashes again
  (a contact name with a quote rendered as `O\\\"Brien` instead of
  `O\"Brien`). toJSON alone produces the correct JSON/JS string; the
  webphone VM test now pins a contact with a quote through a full
  JSON round-trip.
- `config.js` render: the `phoneApi` flag mirrored
  `phoneApi.enable || operator.enable`, so an operator-only deployment
  told the island the phone API existed while `phone_api_url` stayed
  unset — History/Voicemail panels erroring. It now mirrors
  `webphone.phoneApi.enable` only (matching the setting that actually
  wires the proxy), and the VM test asserts the exact key set
  (`sipDomain`, `websocketPath`, `iceServers`, `phoneApi`, `contacts`)
  plus `phoneApi` being a boolean.

### Security

- `services.telephony.fail2ban.nginxScanner` (default on with the
  webphone): a second fail2ban jail guards the HTTPS surface — the
  webphone vhost's access log (pinned to a deterministic path) is tailed
  for scanner probes (wp-login/phpMyAdmin/.env/...) and repeat sources
  are banned from 443. Like the SIP jail it cuts scanner noise, it is
  not an access gate. VM-tested in `checks.telephony-fail2ban` alongside
  the SIP jail.
- History rewritten to purge the pre-scrub-gate personal-data leak
  (personal numbers, DIDs, host IPs) from all blobs and one commit
  message across the 3 offending 2026-09-03 commits; 23 spellings
  replaced with `[REDACTED]` via git-filter-repo, verified clean by
  `scripts/scrub-check.sh --history` locally and against the pushed
  `origin/main` (0 pickaxe hits), then force-pushed with lease.
  Consequence: every commit after 2026-09-03 has a new hash — re-clone
  or `git pull --rebase` if you hold an old copy. Residual exposure:
  GitHub may serve the old commits from cached PR refs/forks until its
  garbage collection, and existing clones keep them until discarded.

### Added

- Security hardening guide (`docs/security.md`): the exposed-surface
  inventory (what listens, who needs it, where it is enforced), layered
  firewall posture (Hetzner Cloud Firewall → NixOS firewall → SIP ACL),
  TURN exposure, SSH posture incl. per-user keys, key rotation and an
  ssh-audit triage recipe, plus a going-live checklist with a
  property-to-check provenance table.
- Deeper edge verification in the VM suites: the event socket (8021) is
  asserted loopback-only, 5061 must complete a real TLS handshake (not
  just listen), manual `tls.mode` is runtime-proven (the vhost presents
  the operator-provided certificate pair, validated by trusting exactly
  it), RTP media is asserted to stay inside the configured port window
  during a live call, and the raw wss probe (`tests/wsprobe.py`) gained
  an asserted `--assert` mode wired into `checks.telephony-webphone`
  (Via/WSS REGISTER challenged, Via/WS dropped, PING PONGed).
- `services.telephony.gateways.<name>.retrySeconds`: wires the gateway
  param `retry-seconds` so operators can tighten the REGISTER retry
  cadence. Motivated by Telnyx's anycast edges re-challenging authed
  requests within one TCP connection (observed 2026-09-18): each lost
  REGISTER cycle grows FreeSWITCH's backoff (`retry-seconds ×
  failures`), leaving a gateway DOWN for minutes between attempts.
  Null (default) omits the param. Asserted in `checks.telephony-pbx`
  (set value present in `sip_profiles/external.xml`, unset value
  omitted).
- Operator read-model API + operator window
  (`services.telephony.operator.*`, `webphone.phoneApi.enable`): a
  hardened loopback service reads FreeSWITCH's state through a read-only
  bind (`telephony-fs-state-acl` grants the telephony group POSIX-ACL
  read access; the API keeps its own ephemeral uid and cannot write) and
  serves the per-extension phone API (voicemail summary/list/stream/delete
  with stream tokens, per-extension CDR history) and the basic-auth-gated
  operator surface (health view with sofia/units/cert cards, CDR viewer,
  SMS inbox, dialplan dry-run simulator). Proven end to end by
  `checks.telephony-operator`: deposit -> summary unread -> messages ->
  token-authed WAV stream -> DELETE -> summary zero, auth denials (401),
  operator surface 401/success paths, and the simulator's group/echo/DROP
  routing answers.
- Conference calling hardening: prompts resolve through a flattened
  compat tree
  (`freeswitch-conference-sounds-8000-flattened`) because no plain
  `sound_prefix` can bridge vanilla's rate-shipped prompt layout
  (source-verified in `conference_file.c`). VM-tested with real DTMF pins:
  right-pin joins stay joined, wrong-pin legs are rejected
  (`checks.telephony-conference`).
- Inbound fax receive proof: `checks.telephony-fax` asserts spandsp is
  loaded, the fax extension answers a G.711 call and runs `rxfax` with
  T.38 disabled (the Telnyx trunk posture), the TIFF lands in the fax
  directory, and the leg hangs up `NORMAL_CLEARING`.
- Hardened-SSH pinning asserts in `checks.telephony-ssh`: the effective
  sshd config must carry `permittunnel no`, the 300s/2 ClientAlive
  keepalives, the pinned HostKeyAlgorithms list, and a new `prodshaped`
  node proves the `allowRootLogin = true` production posture (root login
  WITH key, keyless access refused) instead of only the no-root shape.
- Messaging posture decision docs: `docs/decisions/` records the SMS lane
  (Telnyx HTTP API only — no mod_sms/chatplan detour), the MMS posture
  (API-only, won't-implement-for-now: no SIP MMS standard), and the nix
  diff-drafter verdict (don't-build-now) with their evidence.
- Repo hygiene: `scripts/ahead-check.sh` (ahead/behind vs upstream with a
  fail-loud threshold — the daemon's silent push stalls left origin red
  three times) and `scripts/scrub-check.sh --history` now labels each HIT
  as ADDED, REMOVED (a cleanup, not a reintroduction) or edited via
  pickaxe counts.
- Operator tooling baseline on deployed hosts
  (`services.telephony.opsTools.enable`, on by default): the monitors
  and diagnostics the ops runbook assumes (btop, htop, dig, tcpdump,
  jq, lsof, sqlite, tmux, vim, openssl) plus a flake-enabled nix CLI
  with the `nixpkgs` registry entry pinned to the exact nixpkgs source
  the running system was built from — `nix run nixpkgs#<tool>` works
  out of the box instead of dying on disabled experimental features.
- Telephony research snapshots in `docs/research/`: a SIP ecosystem
  survey (best-of-breed layer map — Kamailio/rtpengine/FreeSWITCH/SIP.js,
  the Go SIP library inventory, and a verified "LiveKit: not used,
  deliberately" verdict with revisit conditions) and an fspbx
  (nemerald-voip) trial doc with end-to-end SIP/CDR evidence from this
  repo's own scripted client plus a from-source license analysis
  (Apache-2.0; the bundled FusionPBX GUI is MPL 1.1 per file headers;
  readme pricing is a support membership, not a code license). Verdict:
  retire the trial, stay NixOS-first, keep fspbx as a feature reference
  (owner sign-off pending).
- Real disk layout for the production host: `hosts/pbx-prod/disk.nix`
  (disko — ext4 on /dev/sda, GPT + BIOS-boot partition, shaped for
  Hetzner Cloud cx22) wired into `nixosConfigurations.pbx-prod` via a
  new `disko` flake input; the manual fileSystems fixture is gone and
  `docs/deploy.md` §4 now documents the one-command
  `nixos-anywhere --flake .#pbx-prod --target-host` install.
- Public template genericized (public/private split): real deployment
  values moved to a private deployment flake consuming
  `nixosModules.telephony`; `hosts/pbx-prod` and `tests/prod-boot.nix`
  carry neutral example values again (`pbx.example.com`, doc-range
  IPv6), and the secrets directory persists across reboots
  (`secretsDir = "/var/lib/telephony-secrets"`, was `/run`).
- `infra/hcloud.tf`: Terraform (Hetzner Cloud provider) for the PBX
  server lifecycle — cx22 in Falkenstein, operator SSH keys, public
  v4+v6 outputs; validated with OpenTofu (DNS stays in the domains
  repo per one-home-per-fact).

- Provider evaluations in `docs/providers/`: a 53-question evaluation
  framework (coverage, trunk fit, agent readiness, KYC, commercial,
  messaging, exit, fax) plus one verified file each for Telnyx, DIDWW,
  didlogic, Zadarma, Twilio, Bandwidth, CommPeak, and a
  dismissed-others summary. Comparison matrix and verdict: Telnyx
  primary trunk + agent-calling platform, DIDWW failover +
  emergency calling (only candidate with PSAP access in
  DE/CH/PL/HK/US), Zadarma budget DIDs. Fax posture recorded:
  self-hostable via the already-shipped `mod_spandsp`
  (`rxfax`/`txfax`/`t38gateway`), DIDWW the only candidate with an
  explicit fax product, Twilio Programmable Fax retired. Every claim
  carries a verification-status row (verified-from-source / sourced /
  unverified); facts verified 2026-08-27/29 against provider pages.
- Metal-path boot proof (`checks.telephony-metal-boot`, x86_64): a base
  VM carves the disko layout (GPT partition named `disk-main-root`) on a
  second disk attached to a `virtio-scsi-pci` HBA — Hetzner's actual bus;
  the framework's `diskInterface = "scsi"` emulates lsi53c895a and proves
  the wrong driver — populates it with the pbx-prod closure (a single
  tarball stream; file-by-file copying exhausts virtiofsd's 65536-fd
  budget) and kexec's into the REAL pbx-prod kernel+initrd with the prod
  boot cmdline (`root=fstab`). Asserted from the serial console: the
  initrd binds the Virtio SCSI HBA, mounts the by-partlabel root (the
  exact 2026-09-14 hang point), and stage-2 systemd boots to the login
  prompt. The bootloader hop stays nixos-anywhere's (grub-install);
  initrd↔device was the incident.
- Initrd driver audit gate: `packages/initrd-audit` (`nix run
  .#initrd-audit -- --platform cloud <initrd>`) decompresses any initrd
  format and asserts the target bus drivers are present, wired as the
  x86_64 `checks.initrd-audit` CI gate over `pbx-prod`'s real initrd and
  as a pre-install step in `docs/deploy.md` §4 — the 10-second check
  that would have caught the unbootable 2026-09-14 first install.
- Backups and failure alerting: `services.telephony.backups.*`
  (restic — `repository`/`repositoryFile` pair, `passwordFile`, `paths`,
  `calendar`, `pruneOpts`; delegates to NixOS' restic module with
  `initialize = true` and a `Persistent` timer) and
  `services.telephony.alerts.*` (`url`/`urlFile` pair; a
  `telephony-alert@%N` OnFailure template POSTs the failed unit's name
  and journal tail to the webhook). VM-proven together
  (`checks.telephony-backup`): a real restic round-trip snapshots the
  FreeSWITCH state dir (the real `/var/lib/private/freeswitch` path —
  restic archives the `/var/lib/freeswitch` symlink as a link) and a
  real unit failure lands in an HTTP sink. `hosts/pbx-prod` ships it
  enabled with `CHANGEME`-marked secret files (`docs/deploy.md` §3).
- Personal-data scrub gate: `scripts/scrub-check.sh` greps the tree
  (and `git log --all -S` with `--history`) for the patterns in the
  gitignored `secrets/scrub-patterns.txt` (template:
  `secrets/scrub-patterns.example`), wired as a pre-commit hook — the
  2026-09-02 leaked-DID class of incident gets a mechanical tripwire.

### Removed

- `infra/hcloud.tf` (Terraform for the Hetzner Cloud server lifecycle,
  added 2026-08-29): retired. Terraform was initialized but never
  applied (no state ever existed) and both live servers were created
  manually via the console with cloud-init, so the definition — one
  cx22 in Falkenstein — described a third server nobody has; keeping it
  invited an accidental extra-server `apply`. `docs/deploy.md` §4 now
  names the real creation path (console/API + cloud-init user-data).

### Fixed

- The `webphone` input is pinned to the last static-site revision
  (`github:LarsArtmann/webphone/2821dfee…`): the upstream 2026-09-18 v2
  rebuild turned the webphone into a Go server and deleted `src/` plus
  the `share/webphone` layout this module serves, so a floating update
  broke every consumer's build (`webphone-root`: `cp: cannot stat
  …/share/webphone/.`, first seen as a failed pbx deploy). The pin
  restores the deployed, VM-proven static UI; the v2 switchover (service
  unit, nginx reverse proxy, config migration) is its own follow-up task
  in TODO_LIST.md and releases the pin.
- Voicemail audio streaming 404'd on every request: the DB path rewrite
  consumed the `/` in `/var/lib/freeswitch/` and glued the bind root to
  the remainder (`freeswitch-rostorage/...`). The voicemail query also
  filtered `in_folder = 'INBOX'` while mod_voicemail stores the default
  folder lowercase (`inbox`, `mod_voicemail.c` `myfolder` default), so
  summaries showed 0 new messages right after a deposit, and the CDR
  parser left the upstream templates' whitespace in the accountcode field
  (`sql`/`snom` templates emit `, "${accountcode}"` with a space after
  the comma) so per-extension history always came back empty. All three
  surfaced at once when the operator suite first reached these routes and
  are regression-covered there now.
- `gateway.didDestination` (and the multi-trunk `gateways` equivalent)
  now accepts ring groups, not just extensions: the public-context
  transfer lands in the default dialplan where the group answers, so
  the natural trunk-DID-to-desk-phones shape evaluates. Regression
  pinned by `tests/eval.nix` (`ringGroupDidEval`).
- `hosts/pbx-prod` boots on virtio hardware: the initrd contained zero
  storage bus drivers (no `hardware-configuration.nix` exists in the
  flake flow to detect them), so the first real Hetzner install hung
  forever waiting for the root device while every VM suite stayed green
  — the VM test `mkForce`s the root onto QEMU's virtio-blk stand-in.
  `virtio_pci`/`virtio_blk`/`virtio_scsi` are now listed explicitly and
  verified inside the rebuilt initrd.
- TLS certificate renewal no longer restarts FreeSWITCH for nothing:
  the ACME path unit fires on every cert-file write during issuance,
  and a redundant restart drops calls; the rendered `agent.pem`/
  `cafile.pem` are now compared first and the unit exits early when
  unchanged (observed 2026-09-16: two fires 8 minutes apart).
- The disko layout and the manual bootloader fixture no longer double-
  register the grub device (drop the duplicated `boot.loader.grub.device`).

### Changed

- Webphone v2 switchover: the stack now runs the webphone as a SERVICE —
  the v2 Go binary from the `github:LarsArtmann/webphone` input, wired
  through that repo's own `services.webphone` NixOS module (imported by
  `nixosModules.telephony`), with the nginx vhost reverse-proxying to it
  instead of serving the old static-site docroot copy. The daily-rotated
  TURN credentials keep working unchanged: nginx still serves the
  runtime-rendered `config.js` OVER the app's own, so rotation never
  restarts the app (its sessions are in-memory). The old nginx
  `/phone-api/` location is gone — the app proxies the browser island's
  `/phone-api` calls itself, injecting Basic auth from the signed-in
  extension's session (asserted end-to-end in `checks.telephony-operator`).
  Raw-module consumers must now import the webphone repo's
  `services.webphone` module alongside `modules/telephony` (the flake
  wrapper does this for `nixosModules.telephony`).
- Flake inputs track their upstream default branches with no hard-coded
  revisions — only `flake.lock` pins exact versions: the `webphone` pin
  to the last static-site revision (the 2026-09-18 v2 rebuild had deleted
  `share/webphone`, breaking every consumer) is released by the switchover
  above, and `nix-ssh-config` drops its `v0.1.3` tag pin.
- RTP port-range options (`rtp.startPort`/`rtp.endPort`) and manual TLS
  mode are now covered by runtime VM assertions (previously
  eval/listener-verified only): during a live SIP call every FreeSWITCH
  UDP listener must sit inside the configured media window, and the
  manual-mode vhost must present the operator-provided certificate.
- The webphone UI moved to its own repo:
  [LarsArtmann/webphone](https://github.com/LarsArtmann/webphone) (new
  flake input, follows `nixpkgs`). `nixosModules.telephony` now defaults
  `services.telephony.webphone.package` to that input's package via
  `mkDefault`; `packages/webphone/` is deleted, so consumers importing
  the raw `modules/telephony` set the option themselves (every VM suite
  threads it explicitly through `tests/common.nix`). The served bundle
  keeps the same DOM/bundle contract — the VM and browser E2E suites
  assert identical hooks; the UI repo additionally gains an ES-module
  restructure and a light theme.
- Conference rooms no longer hang up on `#`: the vanilla caller-controls
  default binds `hangup` to `#`, so a 4-digit PIN + `#` admitted the
  caller and the same trailing `#` instantly expelled them (~120 ms —
  mod_conference's pin collector stops reading digits at the pin length,
  so the terminator lands in the in-conference DTMF handler). The
  generated `conference.conf.xml` drops that binding: join with pin +
  `#`, and `#` inside the room is inert. User-visible for anyone who
  relied on `#` to leave; regression-covered by
  `checks.telephony-conference` (right-pin leg stays joined 25 s).
- Scrub gate armed: `secrets/scrub-patterns.txt` (gitignored) now holds the
  real values — 23 patterns covering both DIDs, the personal mobile, the
  Telnyx SIP credential and API-key prefix, and the Hetzner server
  addresses, each in every spelling — and the values it immediately
  tripped on were redacted from the 2026-09-02/03 status reports
  (annotation-style, incl. the spaced US-DID spelling the 2026-09-03
  redaction pass had missed). Pre-commit is no longer warning-only;
  pushed history still carries the old values (TODO_LIST blocked row).
- Production SSH posture matches the runbook: `hosts/pbx-prod` allows
  keys-only root login (`allowRootLogin = true` ≡ `prohibit-password`,
  `allowUsers = [ "root" ]`), so the documented
  `nixos-rebuild --target-host root@<host>` updates work again; the
  redundant `KbdInteractiveAuthentication` overrides are gone (module
  default since `nix-ssh-config` v0.1.2).
- Audited every `flake.lock` mutation and kept them: the failed 09-14
  run's mid-run `nix-flake-update` repair moved `flake-parts` and
  `nixpkgs` (verified as the base of every green run since), a 09-16
  `git-hooks-nix` bump landed via the auto-commit daemon, and a 09-16
  `nixpkgs` bump shipped with the cert-restart fix below. Nothing
  reverted; previously none of these had been eyeballed or logged.
- `nix-ssh-config` pinned to `v0.1.3`, where keys-only finally means
  keys-only (keyboard-interactive follows `passwordAuthentication`
  upstream); the downstream `KbdInteractiveAuthentication` workaround
  is retired and the VM test asserts the effective sshd config instead.
- Demo VM (`nix run .#vm`) now runs headless (console on stdio) and
  forwards the webphone to `https://localhost:8443/` (SSH still 2222):
  binds unprivileged and no longer clashes with services already
  listening on 443 of a LAN address.
- Quality-gate plumbing for AI-driven sessions: a `.buildflow.yml`
  excludes `packages/webphone/assets/**` from BuildFlow's oxfmt so the
  flake's treefmt (nixfmt + prettier) stays the single formatter for
  those files (formatter split-brain fixed); a minimal `mypy.ini`
  (selenium stubs only); genuine type bugs fixed in `tests/drift_alarm.py`
  and `tests/vmclient.py`; `ruff` narrowed over-broad exception handlers
  in `tests/browser-e2e.py`; a duplicated BYE-wait epilogue in
  `tests/vmclient.py` extracted; `meta` attrs added to both flake
  packages.
- BuildFlow noise triaged at the root instead of hidden by config:
  `.buildflow.yml` skips `pytest-test` (no pytest suite exists) and sets
  `build_mode: fast` as the local default; `lychee.toml` excludes
  `docs/status/**` (point-in-time localhost snapshots); bandit findings
  fixed for real (`tests/turn.py` MD5 with `usedforsecurity=False` —
  TURN REST mandates MD5) or `# nosec`-annotated at the 11 intentional
  test sites; `tests/vulture_whitelist.py` pins the load-bearing TLS
  attr assignments.
- `AGENTS.md` halved (400 → 162 lines): long-form hard-won knowledge
  moved verbatim to `docs/lessons/{freeswitch,vm-testing,webrtc-browser,operating}.md`
  with one-line pointers, keeping session headroom for new lessons.
- Quality-gate reproducibility: the lint binaries BuildFlow orchestrates
  (`ruff`, `bandit`, `mypy`, `dprint`, `prettier`, `vulnix`) are pinned in
  `devShells.default` so runs use this flake's nixpkgs instead of the
  moving `nix run nixpkgs#X` registry revision; remaining ruff findings
  in `packages/telephony-operator` fixed at the source (`check=False`
  with handled return codes, timezone-rule-clean local-time use); and the
  remote `v0.1.0`/`v0.2.0` tags were force-moved off the pre-scrub
  history onto their post-scrub equivalents (identical trees) — the 2-week
  leftover that broke every `git fetch --tags` after the history rewrite.

## [0.2.0] - 2026-08-29

### Added

- Voicemail deposit and retrieval, scripted end to end with a real
  media client (`tests/vmclient.py`: SIP + PCMU RTP noise + DTMF as
  real RFC 4733 telephone-event RTP): a ring-group timeout falls
  through to voicemail and the audio lands as `msg_*.wav`; `*98`
  login (mailbox ID, then PIN) auto-plays messages (asserted as real
  RTP bytes streaming back); a wrong PIN never reaches the messages
  while the correct one plays them (an order of magnitude more
  audio). Digits must be telephone-event RTP — sofia's only
  dtmf-relay INFO parser wants `Signal=` behind the off-by-default
  `extended-info-parsing` flag, so `Signal:`-style INFOs are silently
  dropped (source-verified in sofia.c; earlier runs of this suite
  passed vacuously on re-prompt phrase audio).
- Voicemail-to-email, wired end to end: `voicemail.mailerCommand`
  sets the core `mailer-app` (invoked as `/bin/cat <msg> | <app> ...`
  with the full RFC 5322 message on stdin — the module also provides
  the missing-on-NixOS /bin/cat via a tmpfiles symlink), and setting
  an extension's `vmEmail` now emits `vm-email-all-messages` +
  `vm-attach-file` alongside `vm-mailto` (vm-mailto alone never
  sends, source-verified in mod_voicemail.c). VM-tested with a
  catch-all mailer: the deposited message arrives addressed to the
  configured recipient.
- Declarative IVR menus (`services.telephony.ivrs.<name>`): greeting,
  key collection with retries, per-key destinations (digits and `*`,
  multi-digit keys included) and an after-exhaustion fallback —
  built on mod_dptools' `ivr` menu application with menu definitions
  generated into `ivr.conf.xml`. mod_dialplan_xml parses a whole
  extension before executing it, so the original
  play_and_get_digits + nested-condition design could never route
  (source-verified in parse_exten; the menu-as-data approach is
  immune). VM-tested: mapped keys transfer to the echo test (real
  audio streams back) and to a ring group's voicemail fallback,
  `*` and multi-digit keys route, and an unmatched key exhausts
  retries into the fallback hangup.
- Conference rooms (`services.telephony.conferences.<name>`, optional
  pin): VM-tested with two concurrent scripted legs — fs_cli sees both
  members and each leg receives the mixed audio of the other.
- Time-based ring-group routing (`ringGroups.<n>.timeWindow`):
  in-window the group rings; evenings/weekends transfer to
  `afterHoursDestination`. Built on FreeSWITCH's date-time condition
  attributes (semantics verified against switch_xml.c) and VM-tested by
  setting the clock into and out of the window.
- Health monitoring (`services.telephony.monitoring.enable`): a
  timer-driven check unit that fails loudly — naming the sick
  component — when the event socket dies, a sofia profile goes down or
  a register=true gateway loses REGED. Loopback-only network scope,
  bounded connect retries against the cold-boot accept race.
- fail2ban SIP jail (`services.telephony.fail2ban.enable`): bans
  sources of repeated SIP auth failures (source-verified failregex;
  the normal first-contact `auth challenge` line does not count), with
  the honest posture (digest auth stays the real gate) and unban path
  documented in the runbook.
- Webphone i18n (EN/DE) with a persisted language toggle: every UI
  string (login, call cards, history, errors) goes through a strings
  table; the event log stays English as operator-facing diagnostics.
- Webphone error surfacing: the status pill now says WHY — transport
  disconnect reasons and post-login registration rejection ("check
  credentials") instead of a bare "offline".
- Per-extension options: `vmEmail` (voicemail-to-email, see the
  mailerCommand entry above), `callerIdNumber` (per-extension outbound
  CID overriding the gateway DID), and `*97<ext>` dialing with
  per-call recording skipped (VM-proven: the same destinations route,
  and no recording file appears).
- TURN-over-TLS listener (`turn.tls.enable`, default port 5349): wires
  coturn's turns:/DTLS listener with operator-provided certificate/key
  and opens the port with `openFirewall`.
- Monthly flake-input refresh workflow (`.github/workflows/
  flake-update.yml`): runs `nix flake update` + the cross-arch eval
  gate on the 1st and opens a reviewable refresh PR.
- Upstream contribution tracker (`docs/upstream.md`): the nix-ssh-config
  keys-only gap (KbdInteractiveAuthentication left on by the module —
  source-verified, workaround asserted by our VM tests) is filed
  upstream; the nixpkgs freeswitch network-online ordering PR is
  prepped with a reproduction checklist.
- Repo hygiene: `sip_server` helper deduplicated into tests/common.nix
  (parametrized port), VM-test timeouts migrated to
  `datetime.timedelta` (driver deprecation), a favicon for the
  webphone, and a CHANGELOG lint (pre-commit + gate) rejecting repeated
  `### <type>` headings inside one version.
- Production-shape boot smoke (`checks.telephony-prod-boot`,
  `tests/prod-boot.nix`): the `hosts/pbx-prod` template (hardened sshd,
  file-based secrets, CDR, nginx webphone, coturn) booted as a VM with
  stubbed secrets and self-signed TLS — sofia bound on a real interface,
  nginx served the webphone over TLS, the spliced file secrets
  authenticated a scripted REGISTER, and nothing `CHANGEME`-shaped
  leaked into the runtime config. The template was eval-forced only
  before; now its unit graph provably starts.
- Negative eval assertions in `checks.telephony-eval`: setting both
  sides of a plain/`*File` secret pair (event socket, extension,
  gateway, TURN) is proven to trip the exactly-one-of assertion AND
  block the toplevel build — the rejection paths were never exercised
  before.
- Doc drift alarm (`checks.docs-drift`, `tests/drift_alarm.py`): a
  TODO_LIST row duplicating a `FULLY_FUNCTIONAL` FEATURES row fails
  the gate (two shared stable identifiers, or one option-style
  identifier); verified to fire on injected duplicates.
- Production host template `hosts/pbx-prod` (`nixosConfigurations.pbx-prod`):
  the deployable counterpart to the demo VM — real disk/bootloader
  fixtures, file-based secrets only (`*File` options, no credential in the
  store), `tls.mode = "acme"`, CDR, commented ITSP gateway + ACL posture,
  and hardened keys-only SSH (no root login). `nix flake check` evaluates
  its toplevel, so the template cannot rot; every operator decision is a
  marked `CHANGEME`.
- Deployment runbook (`docs/deploy.md`): prerequisites table (server, DNS,
  ITSP, ports), placeholder checklist, secrets provisioning (sops-nix or
  manual runtime files with a single `secretsDir` knob), three install
  paths (nixos-anywhere, NixOS installer, `nixos-rebuild --target-host`),
  a post-deploy verification checklist, day-2/rollback notes and an honest
  known-gaps list. README gained a "Deploying for real" section; the
  misleading deploy hint in the demo host header now points at `.#pbx-prod`.
- Eval-only regression check (`checks.telephony-eval`, `tests/eval.nix`):
  forces a full NixOS evaluation of every `tls.mode` variant
  (self-signed/manual/acme via the `tests/tls-mode-host.nix` fixture)
  and greps the generated directory XML for the dial-string's
  single-dollar runtime dial variables — the over-escaped
  `$${dialed_user}` pre-processor form breaks every `user/N` bridge and
  was previously only catchable by the browser E2E suite. First run
  caught a real bug (see Fixed). Extended to also assert the internal
  profile's `wss-binding 127.0.0.1:7443` and
  `apply-candidate-acl localnet.auto` (the two WebRTC lifelines), the
  acme-only TCP-80 firewall policy, and — via the all-`*File`
  `tests/file-secrets-host.nix` fixture — exactly one `@TELEPHONY_*@`
  placeholder per configured secret-file option in the generated XML.
- Gateway `passwordFile` coverage in the `telephony-secrets` VM test:
  store purity for the provider secret, runtime splice into
  `sip_profiles/external.xml`, and a live gateway REG state machine off
  the spliced config.
- sops-nix recipe (`docs/secrets.md`): age key setup, `.sops.yaml`, the
  exact `sops.secrets` shape (including `owner = "turnserver"` for
  coturn) and verification steps; option defaults verified against the
  sops-nix module source. Docs-only by design — no flake input added.
- CI `check` job gained a `nix flake check --all-systems --no-build` step:
  cross-arch eval breakage (the drv string-context bug class) is caught
  in about a minute, before the aarch64 job spends an hour building.
- Manual browser-E2E CI job (`workflow_dispatch` in ci.yml): runs
  `legacyPackages.telephony-browser` on demand; promotion to
  periodic/per-push gating stays an owner call.
- Runbook: listening-port reference table and a wss health check
  (`ss -ltn | grep 7443`) plus a webphone-failure troubleshooting note
  about the silent Via-transport drop.
- File-based secrets for everything that used to bake into the
  world-readable store: `eventSocketPasswordFile`,
  `extensions.<n>.passwordFile`, `gateways.<n>.passwordFile` and
  `turn.authSecretFile` (exactly-one-of with their plain counterparts is
  asserted). The generated FreeSWITCH XML carries `@TELEPHONY_*@`
  placeholders; the freeswitch unit assembles a private
  `/var/lib/freeswitch/conf` copy at start and splices the real values
  from systemd `LoadCredential` files (`replace-secret`), and coturn
  consumes its native `static-auth-secret-file`. Manager-agnostic by
  design (sops-nix/agenix only need to render the runtime files);
  covered by the `telephony-secrets` VM test (store purity, runtime
  privacy/modes, mixed plain/file registrations, TURN allocation).
- Browser E2E suite (`legacyPackages.telephony-browser`, deliberately
  outside the `checks` gate for its ~1-2 GB chromium closure): two
  headless chromium instances with fake media register as extensions
  1000/1001 through the nginx wss proxy and complete a real WebRTC call
  (DTLS-SRTP), asserted server-side via fs_cli while up. Failures dump
  browser console, the webphone's event log, chromedriver logs, nginx
  access logs, a raw WebSocket-to-SIP probe and sofia's siptrace journal.
- Minimal boot VM suite (`telephony-boot`) proving
  kernel -> systemd -> freeswitch -> sofia with the smallest closure;
  its `telephony-boot-tcg` variant drops the `kvm` system feature and
  runs same-arch TCG in CI on GitHub's KVM-less arm runners
  (`ubuntu-24.04-arm`). Full VM suites cannot pass the test driver's
  fixed 300s serial-shell connect window under TCG.
- `telephony-secrets` and `telephony-boot` single-node checks (see
  above); the shared `tests/common.nix` boot helper now also waits for
  the event-socket listener (8021) before any `fs_cli` use — sofia
  profiles coming up does not mean mod_event_socket accepts yet.
- Hardened SSH on the example host: the new `nix-ssh-config` flake input
  (post-quantum, keys-only sshd) is wired into `nixosConfigurations.pbx`
  with the tracked operator keys authorized and keyboard-interactive
  disabled (NixOS + PAM would otherwise accept Unix account passwords,
  breaking keys-only); the demo VM forwards host port 2222 to the guest
  sshd. Covered by a new `telephony-ssh` VM test asserting the effective
  sshd config, a real key-based login negotiating the
  `mlkem768x25519` hybrid kex, and the password/root denial paths.
- Per-component NixOS VM test suites for fast bisect: `telephony-dialplan`,
  `telephony-webphone` and `telephony-tls-turn` (single-node, on shared
  `tests/common.nix` fixtures) alongside the multi-node `telephony`
  integration check.
- Operator runbook (`docs/ops-runbook.md`): service inventory, fs_cli
  cheat-sheet, health checks, certificate rotation per `tls.mode`, gateway
  REG-state debugging table, recordings/TURN credential rotation and
  emergency actions; plus a Mermaid architecture diagram in the README.
- Pre-commit hooks via git-hooks.nix: entering `nix develop` installs
  nixfmt, statix, deadnix and gitleaks (wrapped from nixpkgs) as git
  pre-commit hooks; the generated `.pre-commit-config.yaml` store symlink
  is gitignored.
- Recordings serving (`recording.serve.enable`): nginx directory listing
  of recorded calls at `https://<domain>/recordings/` behind HTTP basic
  auth (`basicAuthUser` + `basicAuthPasswordFile`, the htpasswd is
  rendered at runtime). VM-tested: 401 without/wrong credentials, listing
  with correct ones.
- Recordings retention (`recording.retentionDays`): daily timer deletes
  WAV files older than the window (`null` keeps them forever). VM-tested
  with an aged file.
- `extraConfigFiles`: escape hatch merging operator-supplied files into
  the generated FreeSWITCH config (keys are config-relative paths and
  override generated files on collision; validated against path traversal).
- systemd hardening for the telephony units: the root oneshots now run
  under `ProtectSystem=strict` (writing only to a tmpfiles-precreated
  `/var/lib/telephony`), `NoNewPrivileges` and restricted address
  families; freeswitch gains `NoNewPrivileges`/`ProtectHome` and an
  address-family set including `AF_NETLINK`, which sofia's interface
  enumeration requires (without it the first inbound INVITE stalls).
- Webphone multi-call and resilience: concurrent calls with hold/focus
  switching, a DTMF keypad (application/dtmf-relay INFO), call history
  and per-call duration timer, locally generated ringback, automatic
  transport reconnection with exponential backoff and re-registration,
  and opt-in "remember extension" (never the password). All sip.js API
  use verified against the pinned 0.21.2 type definitions.
- `natSipAddress`/`natRtpAddress`: advertise different public addresses
  in SIP vs SDP (asymmetric NAT, SIP edge proxies); each falls back to
  `natAddress` (or the local address when that is null).
- Content-Security-Policy header on the webphone vhost (same-origin
  plus `wss:` for the SIP proxy, everything else denied; asserted in the
  VM test).
- Demo VM polish: host port 443 forwarded into the VM and a console
  banner on every root shell listing URLs, extensions, demo passwords
  and the fs_cli invocation.
- `packages/webphone/update.sh`: repins the bundled sip.js tarball to a
  given npm version (default: latest), recomputes the hash and rebuilds
  the esbuild bundle as a smoke test.
- Multiple ITSP gateways (`services.telephony.gateways`) with per-gateway
  inbound DIDs and least-cost routing: outbound calls fail over across
  gateways in ascending priority. The single `gateway` option remains as a
  deprecated alias. VM-tested with two fictitious trunks.
- `cdr.enable`: CSV call detail records under `/var/lib/freeswitch/cdr-csv`
  (VM-tested).
- `tls.mode = "acme"`: wires `security.acme` for the domain and provisions
  the certificate to FreeSWITCH's SIP-over-TLS listener (agent.pem/cafile.pem
  plus a renewal path unit); `tls.acmeEmail` is required.
- `gateway.allowedCidrs` option: restricts inbound ITSP calls to the
  provider's addresses via a generated `acl.conf.xml` and
  `apply-inbound-acl` on the external profile (VM-tested).
- Scripted SIP client (`tests/sip.py`, stdlib only) and SIP-level VM tests:
  REGISTER with digest auth (MD5/SHA-256), wrong-password rejection,
  multi-device registrations, answered INVITE with PCMU media, gateway REG
  state, toll-allow denial (603), no-gateway 503, unknown-number 404,
  inbound-ACL rejection on 5080.
- Behavioural VM tests: call recording leaves a growing WAV (and none when
  disabled), ring-group voicemail fallback answers, `*98` is answered by
  voicemail check, `config.js` parses as strict JSON with TURN credentials,
  ports 5061/5080 (TCP+UDP) are listening.
- `config.js` body is now strict JSON after the JS assignment wrapper.
- Documentation set built and verified against the code by a docs-health
  audit: TODO_LIST.md, FEATURES.md, ROADMAP.md and docs/DOMAIN_LANGUAGE.md.

### Changed

- `modules/telephony.nix` split into `modules/telephony/` (options, pbx,
  web, edge, shared derived values) with unchanged option semantics.
- `tls.mode = "acme"` now delegates certificate wiring to the nginx
  vhost's `enableACME` (HTTP-01 challenge location, nginx group and
  reloads included) instead of a hand-rolled `security.acme.certs`
  entry.
- Removed the loopback plain-ws listener (5066): an A/B run of the
  browser E2E suite without it stayed green, disproving the
  outbound-transport hypothesis it was added on — after the dial-string
  fix, sofia bridges to WS-registered contacts over the wss transport
  alone. The internal profile now binds 5060/5061/7443 only.
- The webphone WebSocket path is now TLS end to end: nginx terminates the
  browser's `wss://` and proxies TLS to FreeSWITCH's new `wss-binding`
  on `127.0.0.1:7443` instead of a plain-ws hop (see Fixed).
- FreeSWITCH no longer runs under `SCHED_FIFO` (nixpkgs unit default):
  the upstream unit grants realtime priority with no RT time budget, so
  a runaway task could starve the whole host. This stack needs no
  realtime guarantees, so the module forces normal CFS scheduling —
  hardening only, unrelated to the boot flake fixed below.
- VM tests dump process-level diagnostics (blocked syscall, wchan, thread
  count, unit state, journal tail) when FreeSWITCH fails to come up,
  instead of aborting with a bare port timeout.
- Recordings moved from FreeSWITCH's private `/var/lib/freeswitch/recordings`
  to the shared `/var/lib/telephony/recordings` (group-readable, required
  for serving/retention); migrate existing hosts with
  `mv /var/lib/freeswitch/recordings/. /var/lib/telephony/recordings/`.
- `freeswitch-sounds` now declares `meta.license` as `lib.licenses.mpl11`
  (matching nixpkgs' FreeSWITCH packaging) instead of a raw string; the
  music-on-hold pack ships no license file and is documented as CC-BY
  upstream — mind attribution before redistributing it.
- TURN authentication switched from a static username/password pair to
  REST-style ephemeral credentials: coturn runs with `use-auth-secret`
  and a systemd unit derives short-lived username/password pairs (48 h
  validity, renewed daily) into the runtime-rendered `config.js`.
  `turn.username`/`turn.password` are replaced by `turn.authSecret`.

### Fixed

- The time-routing VM test never actually passed: it moved a running
  VM's clock with `date -s` and expected FreeSWITCH's date-time conditions
  to follow, but FreeSWITCH's internal clock is monotonic-plus-offset and
  never picks up a backwards jump (probed live: 60s of `strepoch` polling
  kept the pre-jump time) — the in-window leg deterministically routed
  after-hours on every independent run (local twice + CI), and a restart
  based rework still lost the clock to host-time reverts on CI runners.
  The suite now runs one node per leg with a fixed QEMU RTC base (each
  guest boots inside/outside the window; nothing can drag the clock
  back), asserts the hour as a loud precondition, and checks both legs
  against the freeswitch.log file (post-startup app lines never reach
  the journal). First genuine green.
- The webphone could hang forever on "reconnecting (try N)" after a
  network blip: SIP.js 0.21's `userAgent.reconnect()` never settles.
  Every reconnect attempt is now bounded by a watchdog that tears the
  wedged agent down and rebuilds it, with the browser E2E's
  reload-recovery drill as the final backstop.
- `*97<ring-group>` never matched its no-record dialplan twin: the
  generated condition shipped a double-escaped `\\*97` regex (Nix
  indented strings keep backslashes literal). Now single-escaped and
  VM-proven as a routing + no-recording leg in `tests/pbx.nix`.
- CI failed on the daemon-pushed tree twice over: the changelog-headings
  pre-commit hook never received its CHANGELOG.md argument (usage exit
  on every run), and the TCG boot/webphone suites passed already-built
  `timedelta` objects into `wait_for_freeswitch`, which wraps plain
  seconds itself (runtime TypeError on aarch64 only, where those
  variants run).
- `tls.mode = "acme"` + `openFirewall` never opened TCP 80, so ACME's
  HTTP-01 challenge timed out on a default-firewalled host: no certificate,
  and nginx/wss/webphone dead on the first boot — exactly the
  `hosts/pbx-prod` scenario. The firewall now opens TCP 80 only in acme
  mode, guarded by a `checks.telephony-eval` assertion (open in acme,
  closed in every other mode).
- `tls.mode = "acme"` failed a full NixOS evaluation: the module defined
  `security.acme.certs.<domain>` without any HTTP-01 challenge provider,
  which trips security.acme's exactly-one-challenge assertion. Found by
  the new `checks.telephony-eval` on its first run; fixed by delegating
  to the nginx vhost's `enableACME`.
- Webphone calls never worked from a real browser, for four stacked
  reasons found by the new browser E2E suite:
  - the nginx `location /sip` prefix match also captured `/sip.min.js`
    and proxied the SIP.js bundle to FreeSWITCH (400, dead webphone);
    now an exact-match `= /sip` location with a regression assert in the
    webphone suite;
  - the plain-ws proxy hop silently dropped every browser REGISTER:
    browsers only speak `wss://` from https pages, so SIP.js sends
    `Via: SIP/2.0/WSS`, and FreeSWITCH discards requests whose Via
    transport does not match the connection transport; nginx now proxies
    TLS to the internal profile's `wss-binding`;
  - WebRTC INVITEs from LAN/lab browsers were rejected with
    488 INCOMPATIBLE_DESTINATION because FreeSWITCH screens ICE
    candidates against `wan.auto` (which denies all private ranges)
    when no `apply-candidate-acl` is set; the profile now sets
    `localnet.auto`;
  - `bridge(user/N)` died with "No origination URL specified": the
    directory `dial-string` template over-escaped its runtime dial
    variables (`$${dialed_user}` pre-processor form instead of
    `${dialed_user}`), so contact expansion never produced a URL.
- FreeSWITCH silently bound its SIP listeners to `127.0.0.1` whenever no
  default route existed yet when it started: FreeSWITCH resolves
  `$${local_ip_v4}` by UDP-connecting toward an external address and
  falls back to loopback when that fails, leaving the PBX unreachable
  from the network until a manual restart. The same race made the VM
  tests nondeterministically time out (on slower machines sofia bound
  the real interface while the tests probed `localhost`). The service
  now orders after `network-online.target`, and the tests derive each
  listener's actual address instead of assuming `localhost`.
- Dialplan voicemail fallbacks used `<anti-action>` (which runs when the
  condition does NOT match), so FreeSWITCH answered unrelated calls with
  voicemail before denial extensions could reject them; fallbacks are now
  plain actions after `bridge` gated by `continue_on_fail`/`hangup_after_bridge`.
- Denial extensions now hang up with explicit causes
  (`call_rejected`/`normal_temporary_failure`/`unallocated_number`) instead of
  the `respond` app.

## [0.1.0] - 2026-08-21

First public release.

### Added

- `services.telephony` NixOS module: extensions, ring groups, voicemail, call
  recording, RTP port range, TLS (self-signed or manual certificates), NAT
  address, firewall toggle — fully typed options with 8 configuration
  assertions.
- FreeSWITCH XML configuration generated from Nix options (no FusionPBX or
  FreePBX): sofia internal/external profiles, directory, dialplan (echo test
  `9196`, `*98` voicemail check, ring groups, toll-allow-gated E.164 routing),
  event socket bound to localhost with a configured password.
- Static SIP.js 0.21 WebRTC webphone (esbuild-bundled, no CDN) served by nginx
  behind `wss://<domain>/sip`, with the SIP.js MIT notice shipped next to the
  bundle.
- coturn STUN/TURN wiring, credentials delivered to the webphone via
  `config.js`.
- Optional ITSP gateway for international calls and inbound DIDs (null makes
  PSTN dialling answer 503).
- FreeSWITCH prompts and music-on-hold package.
- Example host (`hosts/pbx`) and ephemeral demo VM (`nix run .#vm`).
- NixOS VM test (`tests/pbx.nix`): sofia profiles, directory lookups, a real
  `originate` dialplan call, webphone and `config.js` over TLS, WSS proxy to
  sofia, coturn, recordings directory.
- flake-parts project layout: packages, VM app, checks (VM test, treefmt
  format, statix, deadnix) and a dev shell (treefmt wrapper, nil, jq).
- CI: GitHub Actions running `nix flake check` (with a KVM udev rule for the
  NixOS VM test); MIT `LICENSE`.

### Known limitations

- All secrets (extension, gateway, TURN, event-socket passwords) end up in the
  world-readable Nix store — wire a secret manager for exposed deployments.
- Emergency calling (911/112) is not wired.
- The webphone has not yet been validated with a real end-to-end browser call.
