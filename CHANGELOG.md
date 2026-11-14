# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added (2026-11-14 — utilization audits: webphone re-scored, pbx-lens audited first time)

- Both tracked-input libraries got library-deep-dive audits
  (`docs/research/2026-11-14_webphone-deep-dive.html`,
  `docs/research/2026-11-14_pbx-lens-deep-dive.html`, renders under
  `docs/research/assets/`, indexed in `docs/research/README.md`).
  webphone: 73/100 (high), 22/31 applicable rows fully leveraged,
  0 anti-patterns; supersedes the 2026-10-25 audit — every prior Fully
  row held, the 80&rarr;73 move is upstream inventory growth (32&rarr;38
  rows across five minor releases), and the top findings are the oauth2
  facade/upstream-twin parity decision, ASR (whispercpp now
  local-capable), push transports, the crm seam (a real Kith CRM sits in
  the fleet), the flight recorder, and metrics consumption. pbx-lens:
  78/100 (high), 20/29, 0 anti-patterns (first audit); deploy surface
  superb, gaps clustered in the source-access render beyond `cdrFile`
  (the live host hand-wires webhook/transcripts/recordings), the
  freshness/alert arm, and the `refresh` backfill recipe. Findings became
  six TODO_LIST rows; the resolved webphone re-score and lens-vhost
  decision rows are deleted (done/decided externally — the vhost landed
  in pbx-artmann as `lens.artmann.tech`, Track A 2026-11-12). Stale
  htpasswd mentions healed in FEATURES.md and the demo host comment
  (upstream removed htpasswd 2026-11-11); AGENTS.md audit paragraphs
  updated.

### Changed (2026-11-14 — morning-sweep relock healed: webphone `fc458b13` → `b09f70c5`, pbx-lens `aa9e51bf` → `0ecf1c1e`)

- Both tracked inputs moved in the 10:00/10:15 unattributed sweep hops
  (`85e0403`, `25edf69` — the standing `nix flake update` sweep class),
  webphone in TWO hops (`fc458b13` → `f83ba3cf` → `b09f70c5`). This
  entry is the attribution heal; verdicts below were gathered at the
  final revs before anything else rode them.
- `webphone` `fc458b13d9c1` → `b09f70c5648a` (95 upstream commits,
  still version-literal 2.14.0): the load-bearing consumer item is the
  T10 privacy change — the shared contact directory left the pre-auth
  `/config.js` (an anonymous fetcher can no longer enumerate who
  shares the phone); `tests/configjs_check.py` already value-pins the
  resulting 8-key set (the `contacts` no-op flag is kept). The three
  NEW config.js keys at this pin (`dialCooldownSeconds`, `metrics`,
  `asrLocality`) are pointer/`omitempty` opt-in-off by upstream
  doctrine — statically verified ABSENT under this stack's config
  (none of `dial.cooldown` / `metrics.island_beacon` / `asr.*` is
  set), so the set-equality assert holds. Browser-contract selectors
  verified at source: `login-form`/`ext`/`pass` live in
  `internal/web/views/login_page.templ` and are pinned by upstream's
  own `login_page_test.go`; the view IDs (`tab-content`,
  `voicemail-panel`, `toasts`, `dest`, `dial-form`, `accept-btn`) and
  the island class vocabulary (`wp-row`, `wp-vm-play`,
  `wp-compose-new`, `wp-danger`) all resolve at the pin. Binary
  build green at the exact rev (`nix build .#webphone`, exit 0).
- `pbx-lens` `aa9e51bfbbfe` → `0ecf1c1eeb1f` (4 upstream auto-commit
  hops, 19 files +518/−135): the post-identity cleanup train — ingest
  dead-code deletion (cdr.go/telnyx map.go), dashboard/queries
  refactor, backup tweak, the dedup-to-zero retrospective docs.
  Package builds green through this flake's locked input
  (`pbx-lens-0ecf1c1eeb1f…` store path, exit 0).
- Full-suite verdict at both pins: `nix flake check --no-eval-cache`
  (the post-lock-move rerun rule) PASSED 2026-11-14 — all checks
  green with the VM suites (telephony-webphone, telephony-lens,
  operator, messaging, dialplan, backup among them) running at the new
  pins; the configjs 8-key and login-selector contract checks inside
  tests/webphone.nix rode along inside the guest.

### Changed (2026-11-13 — pbx-lens relock: the groups-scope fix for lens.oidc.groups_denied)

- Relocked `pbx-lens` `9ae27540262f` → `aa9e51bfbbfe` — TWO upstream
  commits carrying the first real-login bug of the Track-A lens lane,
  root-caused and source-proven against Pocket ID 2.19.1 (the live
  nixpkgs pin): the built-in claim policy releases the `groups` claim
  ONLY under the `groups` scope (`claimmappingpolicy/bootstrap.go`,
  `Scope: {"groups"}, IDToken: true`), while `oidclogin.New` requested
  just `openid email profile` — so the id_token carried no groups at
  all and the allowlist denied every user (`lens.oidc.groups_denied`)
  despite correct membership. The fix auto-appends `groups` when an
  allowlist is set (the oauth2-proxy `--allowed-group` doctrine this
  login ported missed it; the stub IdP ignored scopes, so tests were
  green without it). Lens-repo CI green at `aa9e51b` (run
  43394045558, the first push's `wsl_v5` blank-line finding repaired
  same-session), the lens package built green locally
  (`pbx-lens-aa9e51bfbbfe…` store path, checkPhase included), and the
  live login proof rides the consumer's next switch. The consumer
  (pbx-artmann) relocks onto this tree for the lens-login switch.

### Changed (2026-11-12 evening II — the 75d4cd4 sweep healed: webphone docs-only hop + pbx-lens Track-A OIDC)

- Daemon commit `75d4cd4` swept two tracked inputs past the vetted
  lock with no hand-authored record (the `b7d5a7c` CI run exposed it
  as the `checks.lock-guard` red, every other check green). This
  entry attributes both moves:
- `webphone` `2847fe1d2c1c` → `fc458b13d9c1` — ELEVEN upstream
  commits, ALL docs/planning/status + daemon heuristic churn (verified
  by the compare listing: `docs(status)`, `docs(planning)`, `docs(plan)`
  + `chore: auto-commit` rows; zero code files). Built green at the
  swept rev (`webphone-2.14.0` store path, NIX_EXIT=0) — the
  docs-only-hop precedent class.
- `pbx-lens` `5d777f3e68f8` → `9ae27540262f` — the Track-A native
  OIDC login train (the nginx-exit plan's L1-01): the app now owns its
  Pocket-ID login end to end (`internal/oidclogin`, the serve-flag
  wiring), passkey stays the break-glass lane. Lens-repo CI green at
  `9ae2754` (run 43273704151) + full-tree `-race` green; the
  `auth.oidc` module options + eval twins that consume it ride this
  repo's same-day commits. The consumer (pbx-artmann) relocks onto
  this tree for the Track-A switch.

### Changed (2026-11-12 — webphone relock to main + healing the sweep past the v2.14.0 pin)

- Relocked `webphone` `c211d42fe952` → `2847fe1d2c1c` (webphone main; gate-0
  prove-before-lock built the exact rev green BEFORE the lock moved). This
  entry also heals the unattributed daemon sweep that rode main past the
  gate-proven `v2.14.0` tag pin (daemon commit `641ccbe`:
  `2834810ea06d` → `c211d42fe952` with no hand-authored record — the
  `641ccbe` CI run exposed it as the `checks.lock-guard` red, every other
  check green including the aarch64 `telephony-boot` VM at the swept pins).
  The `2834810e..2847fe1d2` range carries the auth carve (both login
  modes + the session spine into `internal/server/auth`; wire shapes
  unchanged — `session.create`/`session.switch` keep the one-credential-
  field contract), the platform carve (`internal/server/platform`), the
  views view-owned-shapes restructure + the DE locale, and the post-call
  card family's move into `island/app/calls.js`. Auth-surface re-checks at
  the new tree: `wp-ended-card` + `close-ended-btn` present in
  `island/app/calls.js`, `/config.js` keys `phoneApi`/`crm`/`agent` present
  at `internal/server/platform/configjs.go`, login DOM selectors intact.
  Also attributed: `pbx-lens` `27fd19a72355` → `5d777f3e68f8` (the same
  daemon pass; already upstream HEAD — no further move, relock proved a
  no-op). The relock itself was swept by the daemon race (heuristic commit
  `88a6157`, byte-intact: flake.lock + the draft of this entry); this
  hand-authored commit completes the attribution with the real verdicts.
  Gate ladder (`scripts/relock-ladder.sh --browser-e2e --full-check` plus
  the `telephony-lens` VM suite): gate-0 prove-before-lock GREEN
  (`webphone-2.14.0` store path at the exact rev, pre-lock); binary-proof,
  fast-fmt, fast-eval GREEN; all six webphone VM suites GREEN
  (webphone, dynamic-directory, empty-secret, textagent, fax, fax-feed);
  `telephony-lens` GREEN; browser E2E RED under the documented gate-5
  flake signature (stalled past `THEME-THROTTLE-ARMED` at host load 122 —
  the multi-project build storm; runbook "flake signature" clause) and
  GREEN on retry (`THEME-CHECK-DONE`, script finished 364.7s); gate-6
  `nix flake check --no-eval-cache` GREEN, all checks passed — the
  lock-guard red on `641ccbe` is healed by this entry.

### Changed (2026-11-11/12 — webphone relock: the v2.14.0 release tag)

- Relocked `webphone` `9b47bc783527` → `2834810ea06d` (the `v2.14.0`
  release tag: the auth-front-door /login train + the indigo-vetoed
  redesign + the visual craft pass). The release dance pinned the
  lock to the TAG after the branch-tip update rode past it mid-tail
  (`b0e71aaf6187` — the sessionAnswer refactor, whose race tests fail
  on the tip — never entered the prod pin). Gates on this pin: the
  browser E2E green (five suite-leg fixes + webphone's reduced-motion
  View-Transition gate landed on the way), the telephony-webphone VM
  green after its front-door assertions were taught the 303.

### Changed (2026-11-11 — lock sweep attribution: the daemon's second pass + the marker restoration)

- Relocked `webphone` `99953a95785b` → `9b47bc783527` (webphone main;
  the sweep continued riding main after the previous entry landed —
  this range carries the outbound-HTTP connection-pool fix
  `20a8796d` plus the island/shell test pins). The sweep landed as
  daemon commit `aceaf598` without hooks, so the CHANGELOG mention
  lives here. Also attributed: `pbx-lens` `51777b6e` → `27fd19a72355`
  (routine ride-main sweep of the leaf tooling input, same daemon
  pass; `disko` moved too but is not a tracked input). The b65f2c2
  CI run exposed both gaps: the lock-move-guard names every tracked
  input whose CURRENT rev has no CHANGELOG mention, and the
  marker-history arm found the 10-07 archived snapshot's f#1 verdict
  cell re-dropped by a later sweep — restored byte-identical to its
  peak state.

### Changed (2026-11-11 — webphone relock: the post-release sweep)

- Relocked `webphone` `c5074bf80ccb` → `99953a95785b` (webphone main;
  the release freeze lifted when v2.13.0 shipped — the gh release was
  cut at 23:47 UTC on 2026-11-10 — and the lock sweep resumed its
  ride-main duty). This entry names the swept rev for the
  lock-move-guard's attribution contract: the sweep landed as daemon
  commit `c10827b` (flake.lock + TODO_LIST + one archive move) without
  hooks, so the CHANGELOG mention lives here.

### Changed (2026-11-10 — webphone relock: the v2.13.0 release)

- Relocked `webphone` `6936be2adec6` → `bef565204e8e` (webphone main;
  the signed tag `v2.13.0` — commit `55069a9d012f` — sits inside this
  range; the lineage ran `6936be2adec6` → `368e0e252f86` (the C1/E2
  code trains) → `3ba8af1bb91f` (C2 + the lychee-heal + lessons) →
  `bef565204e8e` (the harvest + the plan archive) → `c5074bf80ccb` (the
  canonical strike shapes; the terminal pin — webphone pushes frozen for
  the release window)). This is the release
  train's step 7 executed deliberately: attempt 4's identical move was
  refused by the lock-move-guard (its message carried no ritual
  marker), the swept copy became the fourth-sweep incident, and the
  parallel session's restore (`c404978`) is preserved verbatim in the
  Changed entry above. Release content: the 2.13.0 CHANGELOG fold
  (voicemail playback contracts, Reports tab, push transports) plus two
  release-blocking fixes (summary-draft port-reuse race, wirefixture
  cqrs-lint directive). Gates follow in this push (telephony-browser
  E2E, telephony-webphone, flake check).

### Fixed (2026-11-10 — the 18:47 BuildFlow run driven to green: cue policy, ruff 44 → 0, docs gates, markers heal)

- **cue-vet is green.** Two-part fix: the fleet schema
  (`~/projects/cue-policy`, commit `f0ed5f5`) widens the runner
  allowlist to `ubuntu-latest | ubuntu-24.04-arm` so `check-aarch64`
  can keep its native arm64 TCG boot lane, and `.github/workflows/ci.yml`
  gains the fleet-required top-level `permissions: contents: read`
  (the runs-on conflict had masked it — cue reports one error at a
  time). `buildflow -s cue-vet`: 0 findings. Note: BuildFlow's result
  cache serves stale detector verdicts across external-file edits —
  rerun detect steps with `--no-result-cache-for <tool>`.
- **ruff 44 → 0** (direct `ruff check .` with the fleet user config —
  7× EXE001 via `chmod +x` on the shebang'd scripts/stubs; BLE001
  narrowed to `CookieError` in `oidc_session.py` and `# noqa`-ed on the
  three deliberate reader/route guards in `text-agent.py`; SIM115
  NamedTemporaryFile dances rewritten as context managers; RUF059/RUF015/
  F841 dead-binding cleanups; UP031 percent-format → f-string; RUF046
  redundant `int()` dropped; ISC004 implicit concat parenthesized;
  TRY004 non-object request bodies now raise `TypeError` with the route
  handler catching it as 400; SIM102 combined; B017 narrowed to
  `SipError`; N999 quieted with file-level pragmas on the two
  VM-deployed hyphenated scripts whose names are suite contracts —
  renaming them would churn every suite + history doc for a
  scripts-not-modules false positive). `ruff format --check` green;
  mypy and bandit steps green; all 365 stdlib tests green after.
- **docs-gates all five green** via the fleet consumer pattern:
  `.docs-gates.json` ratchets (`annotate_max: 48`, `audit_max: 111`)
  pin the historical annotate/audit backlog — the same mechanism
  webphone (203/72) and BuildFlow (skip) use; the 48 include the
  pre-existing F/spacing sweep damage, E/ref phantom-tag `8711531`
  claims, and G/uniform cell strikes that are content surgery on
  archived snapshots, not this session's honest scope. The genuinely
  open item was fixed for real: the newest handoff's §f push-transports
  item harvested into a TODO_LIST row (`push.ntfy`/`push.fcm`), so
  freshness passes with zero unharvested.
- **markers/rendering healed again**: the 15:48 dprint sweep
  (`3f25884`) had truncated the 2026-10-07 snapshot's row-1 Category
  cell a SIXTH time (file count 146 → 144, f:1 → 1); restored by append
  from the `91fa748` peak text (count recovery clears both
  monotonicity findings); `markers_check` and `rendering_audit` green
  over 109 files; `docs-drift` and doc-counts green (365 stable).
- **nix-checker at the documented green shape** (2 accepted NAT 5060
  sourcePort errors + 4 accepted sounds.nix infos + 2 accepted
  privileged-port warnings) — its findings gate fails only when run as
  a bare single step without the pipeline's budget. The pipeline's
  `nix-build` kills were budget+load, not code: 1m50 per-step deadline
  mid-VM-build and 0s starvation mass-kills under a loaded machine
  (rerun verdicts ride CI's `nix flake check`; the LOCAL full gate went
  green on this tree 2026-11-10 ~20:40 — all checks incl. every VM
  suite — proving the kills were budget+load, not code).
- The run's own repair step was the FOURTH sweep's executor —
  attribution and lock restore in the Changed entry below (commit
  `276b3d7`).

### Changed (2026-11-10 — webphone relock: the voicemail-playback fixes)

- Relocked `webphone` `2c2cc9501e5d` → `6936be2adec6` (webphone main;
  the voicemail train surveyed at `d537ed735151`, then the tip's own
  contracts-fixture fix landed with a green producer CI run and the lock
  rides the tip). The train this chases: voicemail play failures surface
  an honest toast (the silent dead-button class) with the waveform
  fallback deferring to it, the `/phone-api` proxy forwards `Range` and
  passes `Accept-Ranges`/`Content-Range` back (exercised end-to-end by
  the operator.nix through-vhost Range arm), anonymous deep links render
  the sign-in door, and the Reports tab's undated caveat renders through
  one home. Gate-0 build proofs ran for BOTH revs before the lock moved;
  the ladder verdict rides the relock commit.

### Changed (2026-11-10 — handoff closeout: marker heal + CI history lane, Range seek gated end-to-end, gate-5 base attribution)

- **The hereditary `markers_check` red is healed and CI can see the
  class now.** The `a9aa62f0` daemon sweep had renumbered the 2026-10-28
  snapshot's section-f list and dropped the 2026-10-07 snapshot's row-1
  corrected cell — 7 monotonicity findings that CI could never show
  (the wired check sweeps store copies with no `.git`, so the history
  arms auto-skip there). Repaired by append per the
  `428f2f4`/`7445752`/`bb8f49d8` precedent (displaced verdicts restated,
  arrows re-added, dated correction records); `markers_check` and
  `rendering_audit` green over 109 files. A new five-minute
  `markers-history` CI job runs the same live sweep on a full checkout
  so the next sweep-damage lands as CI red instead of living only in
  local runs.
- **The 2.12.0 Range/seek capability is gated in THIS repo.**
  `tests/operator.nix` now drives the full chain the browser rides —
  nginx vhost -> webphone proxy (session-injected Basic auth) ->
  operator — and asserts `206` + `Content-Range: bytes 0-3/...` +
  `Accept-Ranges: bytes` + the RIFF body head, plus `416` on an
  unsatisfiable range. The upstream Go unit test covers only the proxy
  hop; until this leg the delivered capability had no consumer-side
  gate here (first run caught the placement: the suite's own delete
  drill empties the mailbox before a late-fetched `audio_url` exists).
- **Gate 5's red is base-attributed** (details in the relock entry
  above): suite-level flake class proven at the pre-relock pin, exact
  assertion not reproduced — the runbook's attribution clause is
  satisfied with an honest boundary.
- **The audit addendum landed** (`docs/research/2026-10-25_webphone-
  deep-dive.html`, section `addendum-2026-11-10`): every delta claim
  re-verified at the pinned rev (`2c2cc950`) before writing — proxy
  Range forwarding + header passthrough, the `shell.js` voicemail
  failure toast, the Tailwind v4.3.4 artifact headers, and
  `webphoneVersion = "2.12.0"` — and the parked draft's three false
  leads disproven at source (deliberate `agent:false` value-pin;
  `usermgmt.db` IS in `state.sqliteDatabases`; the operator keeps no
  OIDC database — its only sqlite is the voicemail DB, read-only).
- **Unattributed sweep incident (13:51, commit `268c091`) attributed and
  repaired.** The daemon sweep re-demoted both archived snapshots'
  verdict markers (fourth row-1 drop on the 2026-10-07 snapshot) AND
  moved `flake.lock`: the three child inputs reverted to their
  pre-refresh pins, and webphone jumped FORWARD from the gate-proven
  `2c2cc950` to upstream's `41eab05d` — a heuristic-commit tip past
  upstream's reports feature train that no integration gate had ever
  seen (the lock-move-guard gates CLI commits only; the daemon
  structurally bypasses it). Repaired: the lock restored to the
  `bd3c0e4` gate-proven state (exactly 12 lines, the four swept
  inputs), both snapshots re-healed by append with dated correction
  records, and — for the record — the swept rev DOES build
  (gate-0 `nix build` green, `webphone-2.12.0`); it still has no VM
  suite or browser E2E verdict, so adopting the upstream reports train
  means a fresh relock ritual, not this sweep.
- **Second sweep the same afternoon (15:31, commit `3ae07bf`), same
  class, worse.** The f:1 corrected cell dropped a FIFTH time, the
  three child inputs reverted AGAIN, and webphone moved from the
  sibling's fresh `d537ed73` relock to yet another ungated upstream tip
  (`6936be2a`). Lock restored to the `8dd37ea` gate-proven state
  (webphone back at `2c2cc950`, children back at the refreshed pins),
  the cell restored with a dated record, gates re-green. Two sweeps in
  one afternoon, both re-pinning the tracked input to moving upstream
  tips: until the executor is identified (TODO row) or the tracked
  input gets a rev pin, EVERY session must treat flake.lock as
  hostile — diff it against the last gate-proven commit before
  trusting any verdict.
- **Fourth sweep (19:01, commit `a772faf`) — the executor was a repair
  tool, not the daemon.** BuildFlow's `nix-flake-update` repair step
  inside the 18:47 run rewrote `flake.lock` (webphone `6936be2` →
  `433ca171`, an ungated upstream tip past the ladder-proven
  voicemail-playback relock), and the daemon landed it as a heuristic
  commit 14 minutes later. Lock restored to the gate-proven `6936be2`
  state; no gate ever saw `433ca171`, so adopting the upstream tip
  means a fresh relock ritual, not this sweep. New rule for the ritual:
  a repair tool that updates the lock IS a sweep source — diff
  `flake.lock` after every BuildFlow run until the sweep class is
  closed.

### Added (2026-11-10 — destination-aware caller-id routes: `services.telephony.callerIdRoutes`)

- **New option `services.telephony.callerIdRoutes`** (list of
  `{ destinationPrefix; callerId; }`): a dialled PSTN number starting
  with the prefix presents the listed caller id on the outbound leg
  instead of the gateway's `callerIdNumber`, so callers into that
  country appear local (local presence lifts answer rates; the provider
  must authorize the number — Telnyx allows account-owned numbers,
  foreign ones die with D36 403). Rendered as nested conditions inside
  `pstn_international` between the caller-id sets and the recording
  actions: a failing nested condition skips only its own actions, so a
  non-matching prefix costs nothing and the LCR bridge always runs.
  Overlapping prefixes render longest-prefix first (most specific wins);
  the literal `+` renders as the optional `\+?` mirroring the outer
  condition's tolerance of dialled numbers without the leading plus.
  **The default `[]` is byte-identity proven**: the generated
  `dialplan/default.xml` hashes identical to pre-change with no routes
  configured (sha256 A/B eval of the pure generator). First consumer:
  the pbx deployment presents +496920085788 (its Frankfurt DID) on all
  +49-dialled calls. NOTE for consumers still trunk-screened: this
  fixes caller-ID PRESENTATION only — the outbound lane itself stays
  subject to the provider's fraud screening.

### Changed (2026-11-10 — webphone relock `dbc3693` -> `2c2cc95`, the voicemail playback ride)

- **webphone input dbc36933013e -> 2c2cc9501e5d (two commits past the
  v2.12.0-era pin)**: (1) the silent voicemail-play defect is fixed
  upstream — a recording that fails to load (404/403/undecodable) now
  surfaces ONE honest toast per failure episode (the `play()`
  rejection was swallowed and the element carried no `error` listener;
  benign `AbortError` interruptions stay silent and a later success
  re-arms reporting); (2) the app's `/phone-api` proxy now forwards the
  browser's `Range` header upstream and passes
  `Accept-Ranges`/`Content-Range` back, COMPLETING a chain this stack
  already carried half of — `packages/telephony-operator`'s
  `send_file` has answered single-range 206s (and 416 for
  unsatisfiable ranges) since the recordings-view work, so Safari-class
  browsers can play and every browser can seek from the app hop (the
  operator half is pinned by `tests/operator.nix` and
  `tests/test_recordings_view.py`, and — since this same day — the
  through-vhost chain by the suite's Range seek leg: `206` +
  `Content-Range`/`Accept-Ranges` passthrough + RIFF body + `416`,
  driven through nginx and the app proxy with a real session); (3) a
  Tailwind v4.3.4 artifact rebuild (same class set minus the unused
  `.row-8`). Gate ladder at the pinned rev: gate-0 build proof, gate-2
  binary build, gate-3 eval (`nix flake check --no-build`), all six
  webphone-config VM suites under `--no-eval-cache`, and the full
  `nix flake check` GREEN. Gate 5 (browser E2E, required by the
  `internal/web` delta) came back RED once with both browsers
  unregistered after the suite's own nginx stop/start reconnect drill
  (host load ~23) and GREEN on the retry at the same pin (load ~16).
  **Base attribution (2026-11-10, later the same day):** the runbook's
  required pre-relock proof ran the suite twice at the OLD pin
  (`dbc3693`): GREEN 398 s, then RED at 850 s under load ~27 with a
  DIFFERENT load-sensitive assertion (`data-dial buttons survived
  logout: 1`) after heavy wss 1006 reconnect churn. The red class
  therefore lives in the suite-under-load, not in the 2.12 delta; the
  original red's exact assertion did not reproduce (stochastic class,
  not a proof of that specific failure mode).

### Changed (2026-11-10 — recursive child-input refresh: nix-ssh-config's `home-manager`, `flake-parts`, `treefmt-nix`)

- **The `nix-ssh-config` sub-flake's OWN inputs are current again** (the
  recursive-update lane: the monthly bot only refreshes ROOT inputs, and
  the 2026-11-07 hand pass left `home-manager` on its 2026-09-18 rev).
  `home-manager` 4ac5a2ae -> 82ce401a, `flake-parts`
  31729ca8 -> ea2630b7, `treefmt-nix` 27b3b12a -> 0d6d739a (the last two
  now deduped onto the root pins). Proof it changes nothing we evaluate:
  per-check `drvPath` byte equality over all 50 checks — exactly the 8
  self-embedding checks moved (`doc-counts`, `docs-drift`, `format`,
  `lock-guard`, `markers-test`, `pre-commit`, `rendering-audit`,
  `treefmt`), every VM suite and eval check stayed bit-identical; the
  eval is green under `--no-eval-cache` and all 8 moved checks rebuilt
  green. `pbx-lens`'s `go-nix-helpers` children stay as upstream pins
  them (a tracked input's build tooling, not this stack's evaluation).

### Changed (2026-11-10 — staged webphone upgrades documented; the 2.12.0 audit refresh recorded where it belongs)

- **The cross-release staging constraint now sits in the deploy path.**
  Upstream's one-time data importers lived in webphone 2.10.0/2.11.0 and
  2.12.0+ stops opening `readmodels.db`, so a deployed host jumping from a
  pre-2.10 pin straight to current main would skip the import train — and
  the lock-bump gates cannot see it (they prove a FRESH VM). `docs/deploy.md`
  §6 carries the hop recipe (rebuild through a 2.10/2.11 lock, boot once,
  then move to HEAD) and the runbook's Lock-bump section says why the
  ladder is blind to it. Also: the 2026-10-25 webphone capability audit's
  refresh trigger has fired twice (the ringhook push producer 2026-11-08,
  v2.12.0 2026-11-09). The refresh now has a TODO row carrying the
  source-verified deltas plus the three leads a subagent audit produced
  that did NOT survive source verification — so the next session re-derives
  instead of trusting them.

### Added (2026-11-09 — the fax lane, end to end: /gateway/fax transmits, fax.delivered/failed forward as verdicts)

- **Outbound fax is real.** `messaging.fax.enable` (+ `fax.connectionId`,
  `fax.from`) turns the bridge's `/gateway/fax` from the honest 503 into a
  pass-through to the Telnyx Programmable Fax API (`POST /v2/faxes`,
  multipart `contents` — the API takes the PDF itself, no media staging),
  answered with the fax id as `provider_ref`. The final webhooks
  `fax.delivered` / `fax.failed` forward to webphone `/hooks/fax/status`
  as transmitted/failed verdicts (pages + failure_reason ride along;
  intermediate `fax.*` events stay log-only); the per-fax `webhook_url`
  override pins them to the stack's own receiver regardless of
  portal-side wiring. Honest 422s: missing `to`/document, non-PDF magic
  bytes, oversize bodies; unconfigured lane or PLACEHOLDER key fails
  closed with the actionable text. web.nix derives
  `webphone.settings.fax.send` from the lane (the compose form appears
  only when sending is real). Bridge suite 71 -> 82 tests. Live-proven
  2026-11-09: real-PDF send queued -> media.processed -> sending.started
  (call placed) -> fax.failed `fax_initial_communication_timeout` (a fax
  dialed the voice-answered DID — expected), every webhook on the
  receiver.
- **The faxes API rejects voice connections** (live-proven, 10015 "Only
  valid faxes connections are accepted"): `fax.connectionId` names a
  FAX APPLICATION, not a trunk connection — its nested
  `outbound.outbound_voice_profile_id` owns the D13 destination
  allowlist for faxes. The reconciler grew the matching
  `fax_applications` desired-state lane (id-keyed pins, same shape as
  call-control apps; engine suite +3).

### Changed (2026-11-09 — pbx-lens relock `ca1dd821 -> 51777b6`, the recurring vendorHash repair)

- **Relock of the `pbx-lens` flake input onto the repaired hash.** The
  pinned rev `ca1dd821` carried the PLACEHOLDER `sha256-AAAA…` in
  `vendorHash.nix` (the 2026-11-02 interrupted-run class, recurring:
  commits `5ce9a25`/`ca1dd82`) — every downstream toplevel BUILD would
  have died at the lens fixed-output derivation while evals stayed
  green (surfaced as the eval-time placeholder warning during the fax
  train's path-override eval). The upstream fix runs the hardened
  `update-vendor-hash` app (real hash
  `sha256-BVxzTkszzzRFIJPIJb/tvxiiJPMYWGyEnxozOyTC+fg=`, green-build
  verified) and commits it deliberately.

### Changed (2026-11-09 — webphone relock, closeout sweep)

- **webphone input fe31b3e1 -> dbc36933013e (via the daemon lock sweep;
  attribution recorded after the fact by the fax-train session — the
  sweep floated the pin past the recorded fe31b3e1 and lock-guard
  redded)**: the v2.12.0 closeout session's tail — a daemon commit of
  its working tree (stdlib-modernization refactors in `dial.go`/
  `threads.go` (`maps.Copy`/`slices`), regenerated templ views, test
  churn, the webphone-smoke script) plus the round-2 self-review docs
  commit. No wire-behavior delta expected; this repo's gates re-prove
  the closure at the pinned rev.

### Changed (2026-11-09 — webphone relock to v2.12.0)

- **webphone input 3da66985 -> fe31b3e1 (v2.12.0, via the transient
  efb0ff1a + the daemon lock sweep; attribution corrected after the
  fact — the sweep floated the pin past the first-recorded efb0ff1a and
  lock-guard redded, the 2026-11-09 fax-train session)**: the SUPERB
  closeout train — the journal unification
  (ONE system.db world; readmodels.db retired from the backup set and
  the boot), the faxes aggregate, retention over `TrimStream`, and the
  fix this repo's enroll-verify VM check forced: webphone's
  `-enroll-passkey` CLI minted into the retired readmodels.db while
  the server verifies from system.db (fresh-token 403 on this check at
  BOTH the v2.10.0 and first v2.12.0 relocks) — the CLI now rides the
  same journal with an await before exit (the swept delta past
  efb0ff1a adds the `cqrs.enroll_boot` registration + the enroll clone
  baseline re-key, commits `4bbe6f48`/`fe31b3e1`). webphone's gates
  green end-to-end at the pinned rev; this repo's gates re-prove
  below.

### Changed (2026-11-09 — webphone relock)

- **webphone input e762f5af -> 3da66985 (v2.10.0)**: the per-train
  lock bump riding webphone's 2.10.0 release — the conversation core
  (threads/messages/attachments) and its importer + journal-trim
  retention gate land in system.db, riding the upstream journal-trim
  wave (metaengine v4.23.0 / sqliteengine v4.8.0 / system v4.18.0).
  webphone's own gates were green end-to-end (buildflow 74/74, flake
  check, smoke 90/90) and this repo's telephony-browser +
  telephony-webphone VM checks re-proved green against the new pin
  before this push.

### Added (2026-11-08 — the ringhook wiring leg: shim -> service module -> dialplan)

- **The ring-while-closed hook is now a complete, switchable lane**
  (`services.telephony.ringhook.{enable,port,webphoneUrl,webhookSecretFile}`).
  The `ringhook.py` shim (landed earlier as groundwork) is wired as a
  hardened systemd service (`DynamicUser`, `ProtectSystem=strict`,
  `LoadCredential webphone_secret`, `Restart=on-failure`, after
  `webphone.service`), the secret DEFAULTS to the messaging bridge's
  `gatewaySecretFile` (one secret, one home; explicit override wins, and
  a ringhook-only deployment names its own file), and the FreeSWITCH
  dialplan arms the two mod_curl actions per extension (ring POST before
  the bridge, `api_hangup_hook` end POST) ONLY when the lane is enabled —
  off stays byte-identical. Assertions: ringhook requires `webphone.enable`
  and a secret file. Verified by a new eval arm
  (`ringhookCheck` in `tests/eval.nix`: unit env + credential derivation +
  the rendered curl arms + the off-dialplan carries none) and
  `tests/test_ringhook.py` (7 stdlib-unittest specs: signed forward,
  end-fact, malformed 400s, dead-webphone 202, missing-credential 503,
  health, 404 paths).

### Fixed (2026-11-08 — verdict-truth train: eval gate healed, sweep damage restored)

- **Eval gate green again: every inline TURN secret moved to the file
  form.** The daemon's webphone lock sweeps (`a4b9a0c -> e762f5a`,
  commits `1e2a60a` + `4c94117`) imported upstream's inline-secret
  guard — any secret-shaped settings key carrying an inline value now
  fails eval, because the value would render into the world-readable
  config JSON. Three tree sites violated it (`hosts/pbx`'s demo turn
  secret, the `tests/tls-mode-host.nix` eval fixture, and
  `tests/common.nix`'s shared suite fixture — the last failing EVERY
  VM suite toplevel, the shape the CI eval job had been tripping since
  the sweep). The d66fc3b commit message attributed the red to
  `ringGroupDidToplevel`/the nix-native refactor — wrong: its inner
  trace is this same scrutiny failure. All three sites now ride
  `turn.authSecretFile` (same values, runtime file via
  `environment.etc`; coturn splices the file natively, the boot
  renderer carries `WEBPHONE_TURN_REST__SECRET`), and the eval arms
  keep BOTH renderer lanes covered (crmEval forces the inline form
  explicitly, turnFileEval mkForces its own file path, the negative
  turn arm forces both-set).
- **Sweep-damaged verdict markers restored in three archived
  snapshots** (the 2026-11-08 treefmt sweep `1e2a60a`, 54 files):
  prettier column-drops in the 2026-10-07 pair (the b1 row tail, the
  b1 Effort cell, the f:1 Category cell — restored in-cell with
  corrected notes) and a list renumbering in the 2026-10-28 snapshot
  (done-marked section-f items demoted into continuation lines,
  displacing the verdict blocks of items #11/#6 — the archived list
  structure restored verbatim, plus count-recovery appends for the
  keys the renumbered shape had inflated). `markers_check` back to
  0 findings across 108 files.
- **CI main-gate verdict truth restored (M01/M04).** The twin 1h CI
  deaths were runner starvation: the default-concurrent
  `nix flake check` ran ~10 NixOS VM tests at once on a 7 GB runner.
  Fix `7ec6556`: ci.yml pre-builds the VM suites one at a time via the
  repo's `check-vm` driver with per-suite `CHECK_VM_TIMEOUT` budgets.
  Five consecutive push-event runs completed green over successive
  heads (47-58 min each: `42436537760`/8342f2b8, `42436496246`/47a9f0f0,
  plus `42439341506`, `42438505651`, `42437708582`; the one red in the
  series, pre-fix `42434684049`, failed exactly as the textagent
  503-diagnosis predicted and the pushed fix addressed precisely
  that).
- **The two leftover eval conflicts behind the 2026-11-08 CI red
  healed** (commit `eafb839`-lane): the daemon's webphone lock sweeps
  imported upstream's inline-secret guard, and two suites predated it —
  `tests/secrets.nix` now `mkForce`s `turn.authSecretFile` over
  baseNode's own stand-in, and `tests/fax-feed.nix` moves the hook
  secret to the file form (`gateway.webhook_secret_file`, the
  messaging-suite pattern). Full flake-check eval (every suite
  toplevel) green locally before the push; the three red runs
  (`42480111527`, `42480376875`, `42480633487`) pointed at exactly
  these two sites, and the heal landed on top of the same train (CI
  `42496030807`/`42499047060`). The earlier attribution in the
  `d66fc3b` message (`ringGroupDidToplevel`/the nix-native refactor)
  was wrong — the real cause is the lock sweeps' upstream guard.

### Added (2026-11-08 — verdict-truth train: MWI truth surface + suite greens)

- **MWI assert in the dialplan suite, backed by an in-VM probe** (commit
  `eafb839`): the driverInteractive probe settled that mod_voicemail
  exposes NO fsapi count command (`msgcount` is not a command; the
  `voicemail` api is rss/load/unload/reload only) — the message-waiting
  truth surface is the MESSAGE_WAITING event (`MWI-Messages-Waiting:
  yes`, `Update-Reason: NEW`, fired by mod_voicemail's `update_mwi`)
  that mod_sofia consumes for NOTIFY. The suite subscribes an in-VM ESL
  listener, deposits a real µ-law-noise message through a dedicated 6 s
  ring group (vmclient's 20 s SIP socket timeout cannot sit through
  group 2000's 25 s ring — first-run evidence), and asserts the
  yes/NEW event; suite green (run `DIALPLAN_RC=0`, MWI grep 0.02 s).
- **Voicemail storage dir joins `state.paths`** (same commit): message
  WAVs and recorded greetings
  (`/var/lib/private/freeswitch/storage`) were uncovered while the
  `voicemail_default.db` index was already backed up — a restored DB
  could index audio that was never backed up. The runbook gains the
  `*98` mailbox recipe (storage paths, index DB, MWI observation).
- **M20 messaging depth closed, suite green**: WhatsApp/MMS media
  roundtrip arm in tests/messaging.nix (real bridge wire), the
  `.chan-mms` operator badge CSS, and the 40008 answer pinned to the
  humanized portal guidance (previously a catch-all self-description).
- **M18 passkey run 7 green with the post-mint restart countermeasure**
  (`systemctl restart webphone.service` + healthz re-prove after token
  mint): the suite's minted-credential phase is proven; the enroll
  ceremony remains upstream-blocked — go-cqrs-lite#120 (filed with a
  source-proven evidence pack) marshals go-webauthn's CredentialCreation
  under a `publicKey` wrapper that webphone's enroll.js does not unwrap,
  so the browser leg throws on `toBytes(undefined)` until upstream
  fixes and the input relocks.
- **Theme-only browser E2E suite first green** (recorded in the runbook
  E2E section): the fast relock-ritual lane exists in code and has its
  first live proof.
- **`pkgs.system` stale alias retired** (2 real eval sites →
  `pkgs.stdenv.hostPlatform.system`; the "~20 sites" estimate was a
  grep overcount — most hits were comments).
- **CI extras proven live**: the canary workflow's first dispatch fired
  (deliberate red, by design — do not "fix"), the demo-wallclock suite
  gained the FreeSWITCH wall-clock-stamp assert
  (`/var/lib/freeswitch/log/freeswitch.log` 2026-11-11 pin, green), and
  `wait_webphone` deduplicated the six per-suite copies of the #238
  port-poll workaround into `tests/common.nix`.

### Changed (2026-11-08 — mkForce audit: every force load-bearing, inert block deleted)

- **Full `lib.mkForce` review (19 live sites across 6 files → 14, all
  required-or-guarded with the why)** —
  `docs/research/2026-11-08_mkforce-audit.md` (probe-recipe inside).
  Verdicts per site: pbx.nix's two forces override upstream plain defs
  (nixpkgs freeswitch `CPUSchedulingPolicy = "fifo"` + the ExecStart
  config-dir); web.nix's `caddy.enable` force is the assertion-paired
  vhost split-brain guard; secrets.nix's four clear/swap the shared
  fixture's lanes under the exactly-one-of arithmetic; metal-boot's
  drives force replaces a concatenated list; prod-boot's tls/NIC/gateway
  forces adapt the deliberately plain pbx-prod template.
- **Zero-effective-config-delta cleanups, each probe-proven**: the three
  eval.nix forces with no competing definition normalized to plain
  assignments (telephony-eval resolved to the byte-identical drv
  `1j9psf51479vnc9vdpxd3clnmyzdpc0j`, `--rebuild` verified, verdicts
  unchanged), and prod-boot's inert `fileSystems."/"` mkForce block
  deleted — the VM framework overrides fileSystems at `mkVMOverride`
  priority 10 which beats `mkForce` 50, so the machine always booted
  `/dev/disk/by-label/nixos` regardless (evalTest probe A/B
  byte-identical before/after; the vm-testing lesson's claim that the
  suite "neutralizes fileSystems" is corrected). A fourth normalization
  attempt (grub.devices plain) was CAUGHT and REVERTED by the same A/B
  probe within minutes — grub's device→devices mirror concats a second
  plain-priority boot device; the line now carries a comment recording
  the trap.

### Added (2026-11-08 — M17/M21 verdicts + voicemail disk quota)

- **M17 provider re-verification — all nine docs/providers/ files
  stamped 2026-11-07** (commit `d90993c`): telnyx (messaging
  enablement +$0.10/mo per number, WhatsApp platform fee + Meta
  passthrough), didlogic (PSTN $0.007/min, $8/mo FREE tier), commpeak
  (100+ countries DDx, A-Z 150+), didww (8763 areas, emergency 39,
  pricing now public: Local from $1.20/mo + $0.010/min), twilio
  (per-country pricing publicly unverifiable; HK OFCA CLI restriction
  confirmed), bandwidth (still gated), zadarma (prices held; DE setup
  28 -> 8 zl, per-country line counts), others.md (Skyetel + sipgate
  dismissals changed — both grew international DID products), README
  pass note.
- **M21 CI topology batch** (commit `e82ca47`): the `--system`
  sentinel (aarch64 eval answer must name the real boot-tcg check
  drv), per-arch eval timings into `$GITHUB_STEP_SUMMARY`, the
  aarch64 webphone binary build proof as a named step, `canary.yml`
  (deliberate weekly red, Mon 04:17 UTC, through the same
  failure->notification wiring as notify-failure), and the E2E runner
  user unit in the runbook (solo-rule enforcement via ExecCondition).
- **`voicemail.diskQuota` option** (per-mailbox capacity cap): renders
  the `vm-disk-quota` directory param on every extension —
  mod_voicemail's REAL capacity mechanism, and its unit is SECONDS of
  stored voicemail, not bytes (source-verified 2026-11-08:
  `voicemail_leave_main` compares `sum(message_len)` against the param,
  and `message_len` is a duration — `measure_file_len` divides the file
  position by the samplerate, `create_file` divides `samples_out` by
  the rate, and the generated email bodies read "%u second Voicemail";
  the upstream param name and its "disk quota is exceeded" log line
  are misleading). The same-day predecessor `voicemail.maxMessages`
  (commit `d66fc3b`) rode a fictional "max-messages" profile param:
  the first suite BUILD caught the vanilla template carrying no such
  line, the runtime probe then recorded a third message with the quota
  set, and the mod_voicemail.c source has ZERO matches for
  max-messages. The option was replaced before any release; the byte
  reading in the interim shard cost one red CI run (42508659445 — the
  arm set 102400 "bytes" that no real recording could reach), healed
  the same evening by calibrating to a cap BELOW mod_voicemail's
  min-record-len (2 s < 3 s), which makes the refusal arm deterministic
  from the source invariants — any STORED message's `message_len`
  exceeds the cap by construction. The VM suite's quota arm proves the
  refusal live by the stored state: after the over-quota deposit the
  index DB's (count, sum(message_len)) row is frozen and no wav lands,
  with the param read back through sofia's own `user_data` lookup
  (mod_voicemail's quota-exceeded NOTICE line never reaches the VM
  journal — the FS console floods the serial console and kernel printk
  ratelimiting swallows it — so the contract is asserted on stored
  state, not on a log line). The passkey suite in the original commit
  sources its TURN secret via `authSecretFile` — superseded by the
  tree-wide file-form move in the Fixed section above.

### Added (2026-11-08 — nix-native consolidation train)

- **`flake.lib.telephony.mkFreeSwitchConfig`**: the FreeSWITCH XML
  generator (modules/freeswitch.nix) is now a plain library output —
  evaluable and callable without instantiating a whole `nixosSystem`
  (proven by an eval that renders the ring-group bridge verbatim).
  First consumer: the hermetic `checks.dialplan-sim` lane.
- **`checks.catalog-export`**: the EventCatalog exporter's golden
  selftest (determinism, idempotence, isolated refs, `--plain` parity)
  ran only on authoring machines since the exporter landed; it is now a
  hermetic gate, so renderer regressions fail in seconds instead of
  silently forking the hub's federated catalog tree.
- **`checks.dialplan-sim`**: hermetic dialplan dry-run. Renders the same
  generated dialplan XML through `flake.lib` with a fixture mirroring
  the option defaults, then proves seven routing lanes in
  build-seconds: in-window ring-group bridge, echo test, after-hours
  transfer, inbound DID transfer, the international toll_allow gate
  (allowed vs call_rejected), IVR entry and conference join. Routing
  regressions no longer cost a VM boot to see.

### Changed (2026-11-08 — nix-native consolidation train)

- **Table-driven suite wiring**: the 29 plain-closure VM suites in
  flake.nix and the four on-demand legacyPackages lanes now ride
  one-line table rows (tester + file, comments at their rows); suites
  with extra arguments stay explicit. A/B-proven: attrNames identical
  and every value-level derivation's drvPath byte-identical — only the
  seven derivations embedding the flake source via `${self}` moved (the
  by-design class).
- **One home for the placeholder-token contract**: the `@TELEPHONY_*@`
  tokens were constructed inline in five places (shared.nix's fsSecrets
  blocks + gateway swap, pbx.nix's consumer swaps); a token typo in one
  home would splice nothing at service start, silently. The contract
  now lives once in shared.nix (`fsPlaceholder` + `exactlyOneSecret`);
  tests/eval.nix keeps its literal needles as the independent verifier.
  A/B-proven byte-identical XML surfaces and assertion fingerprints, in
  the eval lane and by the full telephony-secrets VM suite.
- **Single-homed fixture secrets** (tests/common.nix): the three fixture
  credentials each have exactly one let definition instead of drifting
  between `baseTelephony` and the `sip_call` helper; suite testScript
  proven byte-identical.

### Changed (2026-11-07 — pbx-lens relock `a69ce8d -> 9c98f9c`, the upstream CI heal rides in)

- **Relock of the `pbx-lens` flake input, landing the upstream CI
  heal.** The sibling repo's CI had been red since
  2026-11-06 (run `42162572870`: cqrs-lint, Build & Test, Lint and
  Vulnerability Check all dying in "Generate templ code"): the same
  Dependabot commit that bumped templ v0.3.1070 → v0.3.1100 also moved
  the indirect `a-h/parse` to 2026-10-27 (db268905), whose parser
  refactor dropped the embedded `Match` method templ's parser structs
  rely on — `templ generate` failed to compile at BOTH templ versions
  (verified at source and reproduced locally at this repo's pin
  lineage). The upstream fix pins `a-h/parse` back to 20250122 with
  templ v0.3.1070 + templ-components v1.26.0 (the CI-green trio),
  repairs the `vendorHash` the go.sum change moved, and indexes the
  11-05 art-dupl report its live-row gate counted missing. Proven
  before the lock moved (gate 0: the candidate rev's package builds),
  proven after (`checks.telephony-lens` suite green at the new pin),
  and the upstream runs (`42408333610` at `7a81358`,
  `42409402619` at `9c98f9c`) are green at exactly these revs. go.mod/
  go.sum/vendorHash churn only — the CLI/config contract with
  `modules/telephony/lens.nix` is untouched.

### Changed (2026-11-07 — lagging nested inputs refreshed: nix-ssh-config's flake-parts + home-manager)

- **`nix-ssh-config/flake-parts`** (`31729ca8cbdb` 2026-09-03 →
  `ea2630b74709` 2026-11-01): the sub-flake's flake-parts now matches the
  root input's rev (the same-rev alias class). **`nix-ssh-config/home-manager`**
  (`4ac5a2ae9025` 2026-09-18 → `2c0c1f015214` 2026-11-06): the monthly
  refresh contract the flake-update bot cannot cover (it refreshes only
  root-level inputs) restored by hand. nix-ssh-config itself stays pinned;
  no tracked input (webphone/pbx-lens) moved. Eval-proven:
  `nix flake check --no-build` green at the refreshed lock (2026-11-07,
  exit 0).

### Fixed (2026-11-07 — CI main-gate heal: the intermittent lens-eval race)

- **The CI full-check step died intermittently at eval time with
  `path '<hash>-src' is not valid` on `telephony-lens`** (red at run
  `42363454044`, green at `42352615092`, same tree): the pbx-lens
  allowUnfree instance re-imports the locked nixpkgs non-flake-style
  (`import inputs.nixpkgs { config.allowUnfree = true; }`), so its path
  literals become raw addToStore'd sources (bare `-src` store paths), and
  on a cold runner store the parallel check eval can validate a derivation
  whose inputSrc another eval thread has not finished inserting. The full
  check now forces the lens tree once serially and writable
  (`nix eval --raw .#checks.x86_64-linux.telephony-lens.drvPath`) before
  running `nix flake check --no-eval-cache` — the cache switch also
  excludes the stale/GC'd eval-cache class documented in AGENTS.md. No
  assertion changed: the check still evaluates and builds everything.
- **The `telephony-metal-boot` mkfs settle fix (`7707333`) was still
  CI-unproven** — its run was killed by a runner shutdown at 12 min
  (infra class); locally it builds green with KVM. This train proves it.
- **The Nov 6 15:14 "green" verdict was a phantom**: run `42241108662`
  (`a3f3937`) was a Dependabot-metadata-only run (event `dynamic`) — no
  CI job ran. The real last green full check remains the round-11-era
  `38213939150` over `3b63222`.

### Added (2026-11-07 — gateway INVITE identity: the Telnyx connection-username fix)

- **`gateways.<name>.inviteIdentityHeader`** + **`gateways.<name>.extraInviteHeaders`**:
  the outbound screening fix Telnyx engineering named (thread 2026-11-05/06,
  ticket 832080): INVITEs that digest-authenticate without identifying the
  connection answer 403 CALL_REJECTED because no call record is created —
  the verdict is NOT source-IP based. `inviteIdentityHeader = true` renders
  the gateway's OWN username as the `X-Telnyx-Username` header (gateway
  `<variables>` → `sip_h_*` channel variables, applied to every outbound
  INVITE through the gateway), so the value can never drift from the digest
  credentials; `extraInviteHeaders` carries arbitrary custom headers the
  same way. A manual `X-Telnyx-Username` entry next to the flag is an eval
  error (ambiguous identity). Both default off — no behavior change for any
  existing deployment. Pinned in `tests/eval.nix` (identity header + custom
  header render; default host renders NO variables block; the conflict
  fires and blocks). Registration posture (NOREG) and per-call digest auth
  are untouched — this adds identity to the INVITE, nothing else.

### Added (2026-11-07 — docs-health round 11: missed-record backfills)

- **The typed CSRF settings wiring never got a CHANGELOG record.** The
  TLS-fronting CSRF shape (`csrf.trusted_proxies` / `csrf.trusted_origins`
  rendered into the webphone app settings, with the rendered-runtime
  contract pinned by `tests/webphone.nix`) landed with the 2026-10-24/25
  auth-seam rework and its session report
  (`2026-10-25_12-44_webphone-flake-audit-typed-csrf-wiring`, now archived)
  but no entry here — this closes the gap. Found by the 2026-11-07
  docs-health corpus sweep; the remaining eval-time pin is tracked in
  TODO_LIST.
- **The `c043434` battery re-run verdict never got a CHANGELOG record
  either.** The round-11-era tree was CI-proven by run `38242096364` over
  `c043434` (success; re-verified via gh 2026-11-07) and the recording
  commit landed without an attribution line here — this closes that gap.
- **The `c19bdea` CI fix (2026-10-06) never got a CHANGELOG record.**
  `fix(ci): stop the cross-arch eval step from starving the 60-min gate`
  split the eval-only check per system (fresh heap per nix process) and
  raised the step budget 20 → 60 min, ending the 22-consecutive-cancel
  streak on main (the 2026-10-01 → 10-05 infra-red era; one process
  evaling ~140 derivations across both arches degraded from ~0.2 s to
  ~7 min per check). The per-system split + budget are visible in
  `.github/workflows/ci.yml` today; the fix commit and its rationale
  were only recorded in the archived session report until now.
- **The unattributed nixpkgs lock move of the 2026-10-01 23:22 daemon
  sweep (`b4fd65b19 -> c59305bab`) gets its attribution record here.**
  The sweep-era report
  (`docs/status/archived/2026-10-02_11-06_buildflow-failures-relock-attribution-and-hook-gap.md`)
  attributes four same-day lock moves with zero CHANGELOG footprint —
  three webphone (repaired then) and one nixpkgs (unfenced: lock-guard
  tracks only webphone/pbx-lens). The nixpkgs move was the historically
  dangerous half — the 2026-10-01 restore incident proved an unvetted
  nixpkgs sweep breaks the aarch64 FreeSWITCH compile. Recorded as
  attribution, not endorsement; the nixpkgs-fencing idea stays on
  ROADMAP.

### Added (2026-11-06 — the webphone CRM typed front grows the private-CA knob)

- **`services.telephony.webphone.crm.caFile`** (2026-11-06, webphone issue
  #9): an optional PEM bundle rendered as `crm.ca_file` in the app settings,
  so a CRM behind a private CA the PBX host does not otherwise trust (the
  dnsblockd CA on the Kith vhost) works without host-wide PKI changes. A
  plain host path — a CA certificate is public material, so unlike the token
  it does not ride the env file; the app validates the file's content at
  boot. Merged INSIDE the existing `crm` settings value: the settings
  attrset merges are shallow (`//`), and a second top-level `crm.*` block
  would silently replace the whole `crm` value and drop `crm.url` — the
  same trap the auth merge comment documents. Eval-pinned both ways
  (`tests/eval.nix` crmCheck: with `caFile` both facts render; without it
  only `url` does).

### Changed (2026-11-06 — input attribution for the daemon lock sweep: webphone `9cb5c64d -> 36f0c6f4`, pbx-lens `f0d275d8 -> a69ce8d3`)

- **Both tracked inputs moved unattributed in the 2026-11-06 daemon sweep**
  (`71ed5eb`, which also carried the nixpkgs ride `0bb2eedc -> 1d060086`),
  so `checks.lock-guard` answers two FAILs at HEAD. This record attributes
  the webphone move (the floating main tip riding the same sweep; CI
  re-verifies its suites at this pin) and the pbx-lens move (the upstream
  sweep past the 2026-11-02 placeholder-pin repair `f0d275d8`).

### Added (2026-11-06 — EventCatalog export: the inbound call routing model)

- **`scripts/export-catalog.py`** renders this repo's share of the
  architecture catalog that `eventcatalog-hub` federates: a `telephony`
  domain fragment that joins the pbx-lens domain by membership union, three
  services (`pbx`, `pbx-voice-agent`, `pbx-voicemail`), six call events with
  real JSON Schemas (`call.invited`, `call.agent.answered`,
  `call.ringgroup.offered`, `call.voicemail.deposited`,
  `call.voicemail.notified`, `call.abandoned.unrecorded`), two flows
  (`inbound-call-routing` — the intended ladder including the `timeWindow` /
  `afterHoursDestination` branch — and `inbound-call-unrecorded-loss`, which
  documents the branch that has no edge today: an agent-owned call that
  fails with no voicemail hand-off), and one proposed ADR
  (`call-routing-layering`: the mailbox is the floor on every number, the
  agent is a ceiling on the numbers whose lane and language it can serve).
  Stdlib only, deterministic, `-o` / `--plain` / `--check` / `--selftest`;
  the hub consumes it as the `telephony` source (parked in its
  `sources.manual.json` until this file is pushed — the Forgejo mirror is
  what CI clones). Authoring facts worth keeping: the hub's own doctrine
  forbids hand-writing its content dirs (they are generated and wiped), the
  per-source lint runs ISOLATED so every ref must resolve inside this tree,
  and `services/pbx` deliberately reuses the platform inventory's id —
  authored bodies beat derived deployment facts, and its badge unions
  through.

### Added (2026-11-06 — number-level inbound call recording, converged for EVERY number)

- **`phone_number_recording`** (OPTIONAL desired key): converges the
  per-number inbound recording triple — `inbound_call_recording_enabled`,
  `inbound_call_recording_channels` (`single`/`dual`),
  `inbound_call_recording_format` (`wav`/`mp3`) — on **every** phone
  number the account holds, one `PATCH /phone_numbers/{id}/voice` per
  drifting DID. The key names PROPERTIES, not DIDs, so a number bought
  later converges at the next `--apply` instead of riding silently
  unrecorded (the deployment that motivated the lane carried the setting
  on 1 of its 5 numbers). Discovery costs one `/voice` read per number and
  is gated on the key, so a deployment that pins no recording pays
  nothing. Unknown keys and out-of-enum values are FATAL (an outbound
  `inbound_call_recording_type` pasted here would record every outbound
  call), and numbers still in a provisioning state are included on
  purpose: Telnyx accepts the PATCH before the number can take a call.
- Live-proven end to end 2026-11-06 on the pbx-artmann account: all five
  DIDs read `enabled=true, channels=dual, format=mp3` afterwards, and a
  real inbound call recorded through the trunk — `GET /v2/recordings/{id}`
  answered `channels: dual`, `initiated_by: Trunking`, `connection_id` =
  the FQDN trunk connection, `download_urls.mp3` only (the stored
  format). NB Telnyx-side recordings of TRUNK legs are API/portal-only: no
  `call.recording.saved` webhook is delivered to a SIP connection, so
  nothing downstream observes them live.
- Engine suite 44 -> 50 tests (converged-no-step, whole-triple PATCH,
  every-number coverage, out-of-enum refusal, unknown-key refusal,
  absent-key pays no `/voice` reads); the stdlib total 332 -> 338
  (`scripts/doc_counts.py`-derived, AGENTS + FEATURES re-pinned — the
  reconciler row's long-stale "13 stdlib tests" claim corrected to the
  real count).

### Changed (2026-11-02 — input attribution, and the pbx-lens relock off a placeholder pin: `e6fb14db -> 2d25c3f7`, `ab569dbe -> f0d275d`)

- **Both tracked inputs moved unattributed in the 2026-11-01 daemon sweep**
  (`dabe301`, "relock five inputs"), so `checks.lock-guard` answers two
  FAILs at HEAD. This record attributes the webphone move (upstream daemon
  churn riding the same sweep; CI re-verifies its suites at this pin) and
  the pbx-lens move below.
- **pbx-lens main shipped a placeholder vendor hash, so every consumer nix
  build died at the go-modules FOD**: the 2026-11-01 heuristic auto-commit
  captured the `update-vendor-hash` probe mid-run, leaving the fake
  `sha256-AAAA…` sentinel in `vendorHash.nix` and in the go-cqrs-lite source
  hash while cqrs-lint's vendor hash had pbx-lens's value pasted over it.
  `go.mod`/`go.sum` never moved across that window, so the pre-sweep hashes
  were the correct ones rather than a re-probe guess. Same class as
  2026-10-26, and again the PBX toplevel build surfaced it first (2026-11-02,
  `pbx-lens-ab569db…-go-modules`). The relock picks up the repair `f0d275d`
  (three pins restored, plus the repair app now restores on ANY exit, so an
  interrupted probe cannot strand the sentinel for the daemon to commit).
  Binary proof: lens `nix build .#default` green with its tests,
  `checks.vendor-hash` green, the devShell closure green (cqrs-lint pins
  restored), and the pbx-artmann x86 toplevel built green against this rev
  with the lens input overridden to the fix.

### Added (2026-10-30 evening — pagination guard, extra-DID map, app pins, retire lane; the whole stdlib suite rides CI)

- **Pagination guard (`get_list`)**: every list read follows `page[number]`
  until `meta.total_results` is met (a short page terminates when the API
  omits meta; MAX_PAGES 50 is the loud stop). Page 1 keeps the historical
  single-page URL byte-identical — the canned suite shapes key on it.
  Previously a family past 100 objects silently truncated discovery.
- **`phone_numbers` map (extra managed DIDs)**: every extra DID is a
  desired-file row mapping it onto a connection and/or the messaging
  profile by NAME; unknown number/connection/profile rows are report-only.
  A row naming the CORE messaging profile attaches against the profile the
  core steps create this run.
- **`call_control_applications` pins grew**: `webhook_event_url` + nested
  `outbound.outbound_voice_profile_id` (live-verified shapes) now converge
  beside `active` — a console-side webhook swap previously shipped invisibly.
- **`retired_outbound_voice_profiles` (retire lane)**: live survivors of the
  desired retired-name list surface as report-only NOTICE steps; the
  deletion stays owner-gated. A retired name still referenced (by ID or by
  an OVP-whitelist key) is called out as a conflict.
- **CI: the whole stdlib Python suite (328 tests across 10 modules) now
  runs as the `python-tests` job** — none of it ran in CI before; an engine
  regression could land CI-green.
- Tests: 27 → 40 (pagination ×3, phone map ×4, app pins ×2, retire ×4).

### Added (2026-10-30 — the Telnyx reconciler covers the credential trunk lane + the messaging allowlist/alpha identity)

- **Three new OPTIONAL desired-state families close the drift blind spots that
  burned production** (the 2026-10-26 +41 CALL_REJECTED incident: a destination
  widening landed on the trunk connections while the credential lane kept its
  trial-era US/CA profile, and every non-US/CA dial died in ~1 s):
  - `credential_connection_ovps` (name -> outbound voice profile id) pins the
    nested `outbound.outbound_voice_profile_id` of a CREDENTIAL connection via
    the live-proven nested PATCH (a flat PATCH is accepted and silently
    ignored); name-keyed like `ovp_whitelisted_destinations`, unknown names are
    report-only, and the defensive read survives the mixed `/connections`
    summary's flat field shape.
  - `messaging_profile_whitelisted_destinations` (alpha-2 list, set-compared)
    and `messaging_profile_alpha_sender` (string) pin the SMS allowlist and the
    alpha identity on the messaging profile — both ride ONE PATCH, the create
    path attaches them in a follow-up step (the create body stays minimal),
    and the profile LIST endpoint already carries both fields so discovery
    costs nothing extra. Unknown/unset keys change nothing for existing
    deployments; suite 21 -> 27 tests.

### Changed (2026-10-30 15:5x — webphone input relock `b035e74e -> e6fb14db`, the always-on-Settings ride, two bumps one absorption)

- **Second same-day ride so ONE production switch lands the complete UI
  truth** (the staged root otherwise ships the pre-rename gateway row).
  Upstream delta `b035e74e -> e6fb14db` (the intermediate `62b52069`
  lock move never left this repo — its CI was cancelled by the
  Dependabot github_actions race, so the pin rides straight to the
  settled tip): the Settings fax row goes unconditional/symmetric
  (owner decision 2, view test + smoke pin), the gateway row renames
  to "Message gateway" (EN/DE), the T20 fax test batch, the live-proof
  `--fax-off` ui-capture mode, the Paperless archive Settings row
  (conditional, the capability audit's gap), the smoke-in-CI lane
  (first green run on `e6fb14db`) with the trash-fallback fix, and the
  aftermath docs. CI green on the target rev (run for `e6fb14db`,
  2026-10-30 ~16:0x). Eval verdict unchanged:
  `{"receive":false,"send":false}`.

### Changed (2026-10-30 — webphone input relock `b43d1ab -> b035e74e`, the fax-truth ride)

- **The tracked webphone input moves to the fax-capability train so the
  deployed binary finally READS the `settings.fax` block this module
  emits.** Upstream delta: `fax.send`/`fax.receive` pointer-bool
  declaration end-to-end (panel, Settings, SSE), the always-on Settings
  fax row, the unknown-config-key boot WARN, and the ui-capture
  `--fax-off` evidence surface — CI green on `b035e74e` (run
  40995068292). The lock bump itself is `b2d96cf`; the preceding
  `f25341e` fixed the `telephony-fax` VM flake (mod_spandsp now waits
  instead of probing once — CI run 40993671868 green on it). Eval
  verdict unchanged: `pbx-prod` declares `{"receive":false,"send":false}`.

### Added (2026-10-30 — webphone's fax lanes are declared from the deployment)

- **The stack now tells webphone which fax lanes actually exist, so the
  Fax tab stops offering an affordance it cannot honour.** `modules/web.nix`
  writes `settings.fax`: `receive` follows `services.telephony.fax.feed.enable`
  (the feed is the only path into the app's Fax tab) and `send` is OFF,
  because nothing here transmits faxes — the messaging bridge answers
  `/gateway/fax` with an honest 503. Both are `mkDefault`, so a deployment
  with a real provider path flips them in its own host. Pinned eval-only by
  a new `faxCheck` in `tests/eval.nix` (feed on ⇒ receive only; default
  fixture ⇒ neither).

### Fixed (2026-10-28 — the voice agent's turn recorder: the "agent never answers" root cause)

- **The blocking `record` app never worked on real parked channels, and
  every caller heard the greeting followed by dead air.** Live forensics
  on the deployed PBX (2026-10-28): per-second RMS analysis of the
  session recording proves the caller's speech clearly present on the
  caller leg INSIDE the record window, yet the turn file came back
  empty; an internal silence probe proves records were cap-paced (~10 s
  plus a wasted transcription round trip each), never silence-closed —
  the record app's silence detection simply never fired, on real RTP or
  on digital silence. Every inbound agent call since deployment ended
  `hung up during record` (or, on silent channels, a cap-paced farewell
  ~43 s in) with zero conversational turns. The E2E suites never caught
  it because the stub event socket fakes the record app — real
  FreeSWITCH semantics were never exercised.
- **Turn recording now rides the `uuid_record` media bug (the same
  mechanism the dialplan's `record_session` uses, which provably
  captures the caller leg) with agent-side energy VAD over the growing
  WAV** (`GrowingWav` incremental RIFF reader + `TurnVad` endpointing in
  `voice-agent.py`): speech clears `AGENT_SILENCE_THRESHOLD` (16-bit RMS
  units), `AGENT_SILENCE_HITS` × 20 ms of trailing quiet closes the
  utterance, and the new `AGENT_INITIAL_SILENCE_MS` (module option
  `agent.initialSilenceMs`, default 3000) closes a no-speech turn
  quickly so a silent caller hears the retry loop in seconds, not
  `turnMaxSeconds` dead air. A caller hangup mid-turn still aborts
  within one poll window and the transcript still says
  `hung up during record`. VAD windows before the recorder's data chunk
  is visible are ignored (the recorder waking up is not caller silence).
- **Tests**: `tests/test_voice_agent.py` gains `GrowingWavTest` +
  `TurnVadTest` (header walk, stereo caller-leg split, growing-file
  semantics, threshold gating, trailing-silence and initial-silence
  closing) and reshapes the stub ESL to fake the `uuid_record` media
  bug; `tests/test_voice_agent_e2e.py`'s harness serves
  `api uuid_record` with a speech-burst WAV (the record gate now holds
  the turn open via a loud-bytes writer). The VM E2E
  (`tests/agent.nix`) is recalibrated: the parked channel sends no
  filler RTP during a turn, so the received-byte assert now matches the
  stub's two 0.4 s spoken bursts (~6.9 kB measured, threshold 4000; the
  old 20000 only passed because the blocking record app coincidentally
  kept RTP flowing). The VM run proves the real-FS path end to end:
  uuid_record captures the caller leg, the turn closes at the cap on
  continuous noise, the stub transcript drives the `[ACTION: end]`
  goodbye. Residual: no VM variant streams speech-then-stops to prove
  the VAD's trailing-silence close against real FreeSWITCH (the unit +
  E2E suites pin it; the vmclient streams continuous noise).

### Changed (2026-10-28 — webphone input relock `5362e40 -> b43d1ab`, attributed after the fact; nixpkgs swept `3ec6363 -> 31ecbac` in the same daemon commit)

- **The daemon (`00598ae`, 10:17) moved the tracked webphone input past
  the relock-ritual session's final vetted pin minutes after its report
  landed (`5362e40` — every webphone-lane gate green there); this entry
  is the attribution `checks.lock-guard` demands.** Upstream delta
  `+3 real commits` (`2866097` deps: go-health v0.8.1, `3ebfff3` status
  docs, `212d41b` fix(registry): register the call-review error codes —
  review_api + callreviews readmodel + tests, 21 files, no boot-path or
  `internal/web` bundle changes). Gate 2 (binary proof) green at
  `b43d1ab` (webphone-2.9.0 builds); the heavier VM suites and gate 6
  were NOT run at this pin — the next relock ritual owns them.

### Fixed (2026-10-28 — configjs fixture follows the agent-key contract move, webphone `27adf4e`)

- **tests/configjs_check.py pinned the pre-M12 `/config.js` key set.**
  Webphone `27adf4e` added `agent` to the wire contract (the M12
  summarize-affordance flag: ended call cards grow a summarize button
  when webphone's internal textagent seam is on — the same seam as the
  ended-card Close contract). The strict key-set assert now expects
  `agent` and type-checks it bool; this stack does not wire webphone's
  internal textagent, so deployments here serve `false`. Surfaced by
  the full gate at the `5362e40` pin (the suite had not run since the
  sweep landed).

### Changed (2026-10-28 — attribution for the ~03:00 daemon sweep `b8a12fe -> 5362e40`, forward-pinned proof)

- **The daemon moved the tracked webphone input again (heuristic
  `63300a2`); this entry is the attribution `checks.lock-guard`
  demands.** `+5 commits` upstream — overwhelmingly test-side (review
  API tests +222, shell island-tests churn, ~2000 lines of retired
  test scaffolding); zero non-test `internal/web` files moved, so the
  browser-E2E ended-card contract is untouched by this hop. Gate 2
  proven at the exact rev via a direct
  `github:LarsArtmann/webphone/5362e40#webphone` build (upstream CI
  shows mixed verdicts there — one workflow green, one red — our own
  binary proof is the deciding evidence per the runbook). Upstream
  main is a moving target tonight (daemon landing heuristic commits
  minute-by-minute; HEAD already past this pin at `ae2782f`, CI
  in_progress) — this pin is the latest rev our gate ladder has
  proven.

### Changed (2026-10-28 — attribution for the 01:46 daemon sweep `baab847 -> 7f02257` (pbx-lens), gate heal)

- **The daemon moved the tracked pbx-lens input alongside the webphone
  sweep in `afcd2d5`; this entry is the attribution
  `checks.lock-guard` demands.** The `+5 commit` tail is docs-only
  (AGENTS.md, docs/gotchas.md, a nix-review self-assessment snapshot,
  upstream-filings notes) — no Go or nix source moved, so the package
  and its `modules/telephony/lens.nix` contract stand exactly as proven
  at `baab847` in the entry below.

### Changed (2026-10-28 — webphone input relock `5f331e6 -> b8a12fe`, forward-pinning past the broken daemon sweep `edf2c3f`)

- **Relock of the `webphone` flake input `+16 commits`, forward-pinning
  past the 01:46 daemon sweep (`afcd2d5`) that landed `edf2c3f` — a
  broken mid-series rev (`internal/server/api/review_api.go: undefined:
  agentAudit`; upstream CI shows a failure verdict there, and our gate-2
  binary build reproduced the break).** `b8a12fe` carries the completing
  `1fda735` (agent-audit seam for the review API) and passed gate 2 at
  the exact rev before the lock moved (webphone-2.9.0 built via a direct
  `github:LarsArtmann/webphone/b8a12fe#webphone` build). Delta over
  `5f331e6` is web/island/types work (shell.js rework, the calls island,
  the island type-check pin test) plus the review-API audit — no
  boot-path or `internal/server/hooks` changes.

### Changed (2026-10-28 — pbx-lens input relock `a4b99ae -> baab847`)

- **Relock of the `pbx-lens` flake input `+5 commits`.** The bump makes
  the package's proprietary license honest and buildable: upstream now
  declares `licenses.unfree` (the repo is "All rights reserved";
  go-standard had hardcoded `mit`) and re-instantiates its locked
  nixpkgs with `allowUnfree` per perSystem module — without the
  instance any eval of `inputs.pbx-lens.packages.*.default` refuses on
  the unfree license (A/B-proven in the upstream repo), with it the
  package builds and runs (`pbx-lens 0.3.0`). Also folded in: eval-time
  flake.lock follow guards, `goAttr` as the single Go-toolchain source
  of truth, hermetic `update-vendor-hash` runtime inputs, `cqrs-lint`
  package meta, and the 2026-10-27 session-closeout docs wave. **No Go
  source changed since the prior pin** — CLI/config contract with
  `modules/telephony/lens.nix` is untouched (go.mod/go.sum churn is a
  tidy cleanup, net 26 stale sums removed).

### Changed (2026-10-28 — webphone input relock `814fdb5 -> 5f331e6`, and attribution for the 2026-10-27 daemon sweep `49c50b2 -> 814fdb5`)

- **Relock of the `webphone` flake input `+10 commits`, plus the
  attribution `checks.lock-guard` demanded for the unattributed daemon
  sweep that landed `49c50b2 -> 814fdb5` on 2026-10-27 (`9caf8a0`,
  heuristic message — the gate sat red on main since).** The swept hop
  carried upstream's enforced island type gate (208 files: the
  `types/*.d.ts` island contracts, 601 type errors retired). This bump
  picks up the dedup fix rendering filter select rows from one
  component (`15a5a8d`, new `filters.templ`), a package-surface file
  reorg (`package/oauth2.nix` + `package/crm.nix` extracted from
  `nixos-module.nix` — option names unchanged,
  `nix/module-output.golden` moves only backup-script quoting), and
  view rework under `internal/web` (messages/history) — the gate-5
  trigger: every pinned DOM selector pre-checked present in the
  upstream `.templ` sources, auth-seam scan clean. Upstream CI green
  at `5f331e6`; verified at this pin: binary proof, webphone VM
  suites, browser E2E, full `nix flake check`.
  **CORRECTION (appended 2026-11-07):** the "full `nix flake check`"
  claim above is false. The full check was NEVER green at `5f331e6` —
  it failed at `telephony-textagent` and the pin moved on before any
  rerun (the producing session's own admission,
  `docs/status/archived/2026-10-28_10-10_webphone-relock-ritual-session.md`
  §Opening self-review item 1: the claim was written in anticipation,
  before gate 6 ran). What actually held at that pin: binary proof,
  webphone VM suites, browser E2E. The suites green while the binary
  provably serves the new `agent` key remains the gate-4 anomaly,
  tracked separately (TODO_LIST).

### Fixed (2026-10-26 — telephony-webphone fixture follows the webphone auth-seam rework)

- **The webphone VM suite pinned the pre-rework passkey surfaces.**
  Webphone `49c50b2` moved the login ceremony to the cqrs-htmx
  loginpage (`/login`, `lp-*` ids, `/api/auth/webauthn/login/begin`)
  and declared the hand-rolled island form (`passkey-login-form`,
  `passkey-email`) DEAD — exactly the runbook gate-5 auth-surface
  crossing. The suite now pins the new card shape (the `/login` link +
  `passkey-breakglass` disclosure, extension ids surviving, dead ids
  absent), probes the library `/login` front door (200 + `lp-*` +
  the begin endpoint), and drives the anti-enumeration 401 against
  the new webauthn begin path instead of the removed
  `/api/auth/passkey/begin` route.

### Changed (2026-10-26 — attribution for the 06:0x lock sweep `643b109`: webphone `50c4ac2 -> 49c50b2`)

- **The daemon moved the tracked webphone input without a record; this
  entry is the attribution `checks.lock-guard` demands.** Webphone
  `+24 commits` (`50c4ac2 -> 49c50b2`, landed 2026-10-25 evening):
  auth-seam work (projection readiness wired into healthz,
  clone-detection pin, both FinishLogin test stubs adapted to the
  credential-returning seam — the gate-5 auth-surface clause applies),
  the asyncapi generator now owning its generated bytes (docs/contracts
  off dprint), the visual harness extended to the /login surfaces +
  dark theme, and a large docs/ui-shots tail riding as daemon commits.
  Same sweep class as 2026-10-25 `60093f9`; the push's CI re-verifies
  the webphone VM suites at this pin.

### Changed (2026-10-26 — pbx-lens input relock `f57cebec -> 18382a23`, the vendorHash repair)

- **Upstream main broke every consumer nix build at the go-modules FOD**
  (its 2026-10-25 go.mod/toolchain sweep outpaced the `vendorHash.nix`
  pin; our CI never noticed because it does not build the nix package —
  the PBX toplevel build surfaced it first). The relock picks up the
  upstream fix commit `18382a23` ("fix: re-pin vendorHash for the swept
  module set", learned + verify-green via its own
  `update-vendor-hash` app) plus the two unpushed daemon commits that
  rode it (the cqrs-lint devShell vendorHash re-pin from the same
  toolchain bump, and a recent-views UI contract pair). Binary proof:
  the lens package built green at the new rev before this relock.

### Added (2026-10-25 — wall-clock ownership: host timezone + derived webphone zone)

- **Both example hosts now set `time.timeZone = "Europe/Berlin"`, and the
  webphone facade derives `settings.timezone` from it** (`mkDefault`, `UTC`
  when a deployment leaves the host zone unset — the deep-dive finding was
  "no zone set anywhere, every wall clock renders UTC"). One correctness
  edge made honest in the same change: ring-group `timeWindow` hours are
  evaluated by FreeSWITCH in the server's local time, so with the zone
  unset the default 9–17 window ran on UTC wall-clock; on the hosts it now
  reads as Central European wall time (option description names
  `time.timeZone`). VM suites set no zone and are unaffected.

### Added (2026-10-25 — OIDC SSO deployment recipe)

- **docs/ops-runbook.md gains an "OIDC SSO surfaces" section beside
  "Passkey surfaces"** (deep-dive opportunity #4): the IdP client
  registration (verbatim issuer, default redirect URI), runtime
  client-secret staging, the shared email→extension users map, the
  optional fail-closed `allowedGroups` second gate, and passkey/SSO
  coexistence — plus a commented `webphone.users` + `oauth2` block in
  `hosts/pbx-prod` following the host's CHANGEME pattern.

### Changed (2026-10-25 — state.paths derive from the webphone module's own options)

- **`services.telephony.state.paths`/`sqliteDatabases` no longer hardcode
  `/var/lib/webphone-backup`, `webphone.db` and `usermgmt.db`** — they now
  derive from `services.webphone.backup.destDir` and `services.webphone.dataDir`
  (deep-dive "partially used" finding: an operator overriding the upstream
  options silently un-registered their state from the backup tooling).
  Values are identical at the defaults; behavior-preserving.

### Changed (2026-10-25 — attribution for the 07:11 lock sweep `60093f9`: webphone `6274c85 -> 50c4ac2`, pbx-lens `6bbcd5c -> 1f82b964`, nixpkgs `02c087f3 -> 3ec636362e`)

- **The daemon moved three inputs at 07:11 without a record; this entry is
  the attribution `checks.lock-guard` demands.** Webphone `+36 commits`
  (`6274c85 -> 50c4ac2`): the catalog/OpenAPI contract-documentation trains
  (eleven session-gated JSON surfaces documented, contract error codes
  registered, smoke pin re-trued after a red main), a module FOD re-pin, and
  the `ssoerror.js` line-wrap fix — no `.templ` markup delta; the island
  bundle changes by that one file, so the runbook's browser-E2E trigger
  fires (owed, see below). pbx-lens `+120 commits`
  (`6bbcd5c -> 1f82b964`): the go-cqrs-lite adoption wave, testing depth
  and catalog read surface (style/docs/CI; no index-schema break — the
  module's poll contract is unchanged). nixpkgs
  (`02c087f3 -> 3ec636362e`): routine bump, rides the in-tree gcc-16 assert
  shim (FreeSWITCH rebuilds from source; the 2026-10-01 mod_enum incident
  class is covered). Verification at exactly this pin: `checks.telephony-eval`
  green and the typed-csrf rendered-settings identity proven 2026-10-25
  12:44 CET; full `nix flake check` and the browser E2E (ssoerror bundle
  delta) remain owed and ride CI / the next ritual.

### Fixed (2026-10-25 — telephony-dialplan CI flake: sofia nonce race + one-round INVITE auth)

- **`tests/sip.py` now answers 401/407 digest re-challenges the way a
  real UA does** (bounded, up to 3 rounds), closing the
  `telephony-dialplan` CI flake. Root cause, reproduced deterministically:
  mod_sofia's nonce store (`sip_authentication`) lost a FRESH nonce row
  between challenge and verify under build-load vCPU stalls on CI
  runners — a correct digest then answered `407 stale=true`, and the
  one-round test client gave up with `INVITE 407` (first seen 2026-10-25
  02:52; never reproducible on an idle host, 12/12 clean in loop mode).
  The one-shot race was simulated in-VM by deleting a single nonce row
  at the challenge boundary: old client fails with the exact CI
  signature, fixed client re-auths over the re-challenge's surviving
  nonce and converges (`INVITE 503`). The failure was exposure, not
  regression — earlier CI reds cancelled the suite before it ran.

### Fixed (2026-10-25 — browser E2E: wedged chromedriver session startup)

- **The browser E2E runner no longer dies to a chromedriver session-
  creation hang.** Evidence from the owed ssoerror-delta E2E run
  (2026-10-25): WRONGPASS passed, then the theme driver sat on its
  initial `data:,` URL while the selenium client blocked forever inside
  the `webdriver.Chrome` constructor — no exception, no marker (selenium
  has no constructor timeout), and the stall diagnostics tailed only the
  FUTURE 1000/1001 drivers' logs, never the live `chromedriver-theme.log`.
  `make_driver` now bounds every attempt with a 60s watchdog thread
  (killing the service unwinds the stuck constructor; the thread is
  daemon so a truly stuck one cannot block runner exit), retries up to
  3x on a fresh chromedriver with per-attempt log files, and the stall
  diagnostics dump every `/tmp/chromedriver-*.log`.

### Fixed (2026-10-25 — webphone module: the passkey+SSO auth clobber)

- **The webphone settings merge dropped `auth.passkey` whenever OAuth2 SSO
  was also on.** The two mode branches contributed top-level
  `auth.passkey = ...` and `auth.oauth2 = ...` through the same `//` chain;
  `//` is SHALLOW, so the later branch's whole `auth` attrset replaced the
  former's and `auth.passkey.rp_id` vanished from the rendered config.
  Live burn on the PBX host (2026-10-25 02:22 UTC): the SSO-train webphone
  (`6274c85`) treats the shared identity map (`auth.users`) as passkey
  mode configured and rejects the config at boot —
  `[rejection:config.auth.passkey.rp_id]`, exit-1 restart loop, the whole
  phone UI 502 — while the pre-SSO binary had booted the same clobbered
  config silently (passkey login quietly OFF). Fix: both mode branches now
  merge INSIDE one `auth` attrset (passkey + oauth2 + the shared users map
  coexist), proven by rendering the PBX host config through the patched
  module (all four keys present, `rp_id = pbx.artmann.tech`).

### Changed (2026-10-24 — webphone input relock `02cf671 -> 4da4fec -> 6274c85`, the SSO train + hardening batch; pbx-lens `754905e -> 6bbcd5c`, attributed after the fact)

- **Relock of the `webphone` flake input in two hops.** Hop one
  (`02cf671 -> 4da4fec`) is the attribution for the daemon heuristic
  commit `53669ea` (2026-10-23) that moved the lock without a record —
  `lock-guard` went red on CI run 39985544489 (the `nix flake check`
  step, exit 1 on the guard derivation, NOT an eval timeout), the gate
  working as designed. Hop two (`4da4fec -> 6274c85`, deliberate) rides
  the SSO train: upstream webphone gains the in-app group allowlist
  (`sso.groups_denied`, fail-closed, default off) plus the hardening
  batch — the Basic-auth TLS stub pin (H8), single-flight discovery
  with a 15-minute positive cache (H7), the groups-claim journal-only
  audit line (H3), the `sso_error` read-then-strip (H2) and the
  directory-rejection reason (H1). **The `pbx-lens` move
  (`754905e -> 6bbcd5c`) rides the same sweep** (the read-model key
  fix already recorded 2026-10-23, now at its merged rev). Proofs THIS
  entry runs on (all at `6274c85`): `nix build -L .#webphone` green
  (sandboxed checkPhase), the four webphone/fax VM suites green —
  `telephony-fax-feed` FIXED this train (its end-to-end assert read the
  retired SQL `fax_jobs` table; the fax truth moved to the metaengine
  read models, and the assert now reads `meta_planned_faxes`), the
  browser E2E suite green (`WRONGPASS-DONE` in the run log), and the
  consuming PBX repo's x86 toplevel build + aarch64 eval green at its
  absorbed lock (lock-drift-probe ALL OK, webphone pin matches this
  lock).

### Added (2026-10-23 — textagent: configurable drafting model + runtime auto-reply mode)

- **The drafting model is configurable and has a standby chain.** The
  engine hardcoded `gemini-3.8-flash`; on 2026-10-23 that model answered
  `503 service_unavailable` and then hung every Interactions call for the
  full 60 s window while `gemini-3.5-flash` answered the same prompt in
  ~3 s — every draft failed and only the journal said so. New
  `textagent.llmModel`, `llmFallbackModels` and
  `llmAttemptTimeoutSeconds` options (env `GEMINI_LLM_MODEL`,
  `GEMINI_LLM_FALLBACKS`, `GEMINI_LLM_ATTEMPT_TIMEOUT`): the Gemini
  client walks the chain, gives non-final attempts the short leash so a
  hung model cannot eat the whole window, and surfaces the whole failure
  chain in its honest error.
- **The auto-reply mode is switchable at runtime.** `POST /mode` pins
  `off` / `drafts` / `after-hours` / `full` in `state/mode.json` (it
  survives a restart), `{"reset": true}` returns to the configured
  default, and `/reviews` + `/health` report `mode`, `mode_source`,
  `default_mode` and the ladder. The webphone's drafts panel drives it;
  the STOP suppression, VIP, kill-switch and confidence gates are
  unchanged by a flip.
- The textagent suite grew to 86 tests: the standby chain (503 on the
  primary, the request order as the audit trail, the full-chain error),
  the override lifecycle (persistence across a restart, reset, invalid
  mode, live gate change, audit trail) and the review-API mode route.

### Changed (2026-10-23 — pbx-lens input relock `0ee06c9 -> 754905e`, read-model key contract)

- **Relock of the `pbx-lens` flake input, `0ee06c960f04 -> 754905e7f1bd`**:
  the pinned rev could not build at all (its `vendorHash.nix` was stale
  after a `go.mod` sweep) and, once past that, the package's own tests
  failed against `projectionadapter` v4.6.x. Root cause at source: v4.6.0
  flipped `EventWithID.ID` from the marker-prefixed `StreamID.String()` to
  the bare `StreamID.Get()` value, and the index's readers still asked for
  the marker form — every projection lookup missed. Upstream fix `754905e`
  makes `internal/calls.RecordKey` the single owner of the row-key format
  (readers, ingest, ops, seeds, tests), keeps a legacy-key fallback for
  rows written under v4.5.x, and passes `go test ./...` plus a nix build
  of `packages.pbx-lens` with the sandboxed checkPhase. Proofs here:
  `checks.x86_64-linux.telephony-eval` green at this lock; the PBX
  toplevel build is the deploy-side proof.

### Changed (2026-10-16 — webphone input relock `9ff67309 -> 05cbafda`, attributed after the fact)

- **Relock of the `webphone` flake input, `9ff67309b72b -> 05cbafda499c`**
  (attribution for the daemon heuristic commit `6380e2c` that moved the
  lock without a record — `lock-guard` went red on the next `nix flake
  check`, the gate working as designed). The move rides upstream webphone
  `release: v2.9.0` (two commits: the release bump + a daemon sweep);
  contents not individually vetted here. Proofs THIS entry runs on: the
  same CI run that flagged the guard PASSed `pre-commit` with the
  2026-10-15 gitleaks `args`-pin fix (run 38862955118) and the aarch64
  boot VM. NOT yet proven: a full green `nix flake check` at this lock
  (the flagged run cancelled most VM checks) — schedule the VM suites
  with the next deploy window and treat 05cbafda as eval-verified only
  until then.

### Added (2026-10-12 — forward-auth mode for recordings/operator surfaces)

- **`recording.serve.authMode` + `operator.authMode`** (`basic` default |
  `forwardAuth`): forwardAuth delegates each surface to an external auth
  service via nginx `auth_request` — the generic hook the pbx-artmann SSO
  stage drives with oauth2-proxy (the module stays gate-agnostic:
  `forwardAuth.authUrl` + `forwardAuth.signInUrl` per surface). Semantics,
  proven by the new VM suite: gate 401 → 302 to `signInUrl` with the
  original absolute URL appended (never a BASIC prompt — no `auth_basic`
  behind `satisfy any`); gate 403 → 403 passes through (authenticated,
  wrong permission); gate 200 → the surface serves; loopback sources
  (the host itself, ssh -L break-glass) bypass even a denying gate.
- **Htpasswd single-writer interplay**: forwardAuth surfaces render NO
  htpasswd line — `telephony-recordings-auth` disappears entirely and
  `telephony-operator-auth` keeps writing only its non-htpasswd
  credentials (ESL password, stream token), preserving the single-writer
  rule (`htpasswdWriterCheck` extends to both modes; `telephony-eval`
  gains `forwardAuthCheck` + `forwardAuthMixedCheck`).
- **8 new assertions**: forwardAuth requires both URLs, forbids leftover
  `*PasswordFile` from basic mode (and vice versa), and rejects
  non-http(s) URLs on both surfaces.
- **`telephony-forward-auth` VM suite** (`tests/forward-auth.nix`): two
  nodes — a server with both surfaces in forwardAuth plus a fake gate on
  loopback deciding by the inherited `X-Test-Gate` header, and a curl
  client (requests from the server's own loopback would hit the
  break-glass allow). Covers all four legs on `/recordings/`,
  `/operator/`, `/operator-api/health`, the no-htpasswd render, the
  esl-password write, and the operator-auth oneshot result.

### Added (2026-10-12 — brokering-train hardening harvest)

- **`nix run .#check-vm`**: sequential VM-suite driver (all
  `vm-test-run-*` checks one at a time, subset names as arguments) —
  `nix flake check` builds every suite concurrently and ~10 concurrent
  VM boots saturated one host into a broken-pipe flake; the local
  driver sidesteps that class.
- **FS module-mirror eval check**: the freeswitch module override now
  consumes ONE home (`modules/telephony/freeswitch-modules.nix`), and
  `telephony-eval` resolves every entry against nixpkgs' module
  universe — an upstream rename/removal fails eval in seconds with
  `attribute '<name>' missing at freeswitch-modules.nix:<line>`
  instead of a freeswitch build failure one VM run in.

### Changed (2026-10-12 — brokering-train hardening harvest)

- `telephony-webphone-dynamic-directory` suite asserts MORE:
  `config.js` must answer `"sipCredential":true` under xml_curl
  (module → settings → island-flag pin; the browser E2E's fixture
  covers the false arm), the `auth logout` audit line is load-bearing
  (a silent no-op logout — the fixture bug the five-red-run chain
  burned on — can no longer pass), and the bridge's answer-count
  journal + seam-content asserts stay as the seam-truth template.
- `telephony-webphone` gained a positive authenticated static REGISTER
  leg (digest dance, proxied lane, extension 1001) — the `--assert`
  probes only ever proved 401 challenges.
- wsprobe.py documents its exit codes; fs-directory.py's no-store
  comment now states the header covers BOTH 200 shapes (credential +
  not-found fall-through).

## [0.4.0] - 2026-10-12

### Added (2026-10-12 — dynamic SIP directory: webphone credential brokering)

- **`telephony.directory` options + the `fs-directory.service` bridge**
  (stdlib-only `modules/telephony/fs-directory.py`): under
  `directory.mode = "xml_curl"` FreeSWITCH validates REGISTERs against
  webphone's per-session DERIVED SIP credentials instead of stored
  passwords — the bridge proxies sofia's xml_curl lookup to webphone's
  `GET /internal/directory/<ext>` (loopback + the shared
  `webphone_directory_secret`, presented by mod_xml_curl as HTTP Basic
  `webphone:<secret>` — 1.11.1's auth-scheme parser silently ignores
  `bearer`; the bridge also accepts Bearer for probes) and renders the
  directory XML; ANY failure (unknown extension, webphone down) answers
  `<not-found/>` so sofia falls through to the static binding, which
  then carries only `directory.staticFallbackExtensions`. Logout
  revokes the credential at the next REGISTER; webphone is
  default-wired (`settings.sip.credential_secret_file`) and the
  pairing xml_curl⇒secretFile is asserted. `mode = "static"` (default)
  renders the full static directory byte-identical to before
  (eval-golden pinned) — rollback is a mode flip + switch. The
  FreeSWITCH package now mirrors nixpkgs' default module list plus
  `xml_int.curl` (mod_xml_curl — absent upstream, fatal silently
  without it). Covered by the new `telephony-webphone-dynamic-directory`
  VM suite (bridge wiring, scoped directory, derived-credential
  REGISTER 200, wrong-credential denial, logout revocation, static
  fallback registration).

### Changed (2026-10-12 — pbx-lens input relock `fa3d338 -> d436dea`, attributed)

- **Relock of the `pbx-lens` flake input, `fa3d338 -> d436dea`**: picks
  up the CDR bare-quote parser fix — vanilla mod_cdr_csv writes
  `,"", ""` in every Master.csv tail and pbx-lens's strict CSV reader
  rejected the whole line, so polled CDR ingest recorded nothing
  (caught live by the new `telephony-lens` VM suite: `poll cdr:
  [corruption:cdr.parse.read]` at a 2s cadence against a real placed
  call). Also carries the cqrs-lint CI install fix (module-path casing
  at the pinned rev) and upstream's dashboard-day R-lane work. Gates:
  pbx-lens `go test ./...` green upstream-side; the lens VM suite is
  the integration proof here.

### Added (2026-10-12 — round 11: per-item monotonicity arm, rendering audit, normalization lesson)

- `scripts/markers_check.py` gains the PER-ITEM monotonicity arm: verdict
  markers are counted per scoped item (section + `#N`/first-cell key,
  same line-plus-block attribution as the content sweep) and a key
  whose count permanently drops below its peak is a finding — the net
  for the count-preserving evasion class (a verdict stripped from one
  surviving item and compensated by a new marker elsewhere leaves the
  FILE count flat). Scope is POST-ARCHIVE revisions only: the first
  live sweep surfaced 17 drops, 16 of them benign verdict-twin dedup
  and supersede edits from the 2026-08-22 annotation era (live-file
  churn), and one REAL damage residue — the webphone-ui row-36 verdict
  cell (`04562e78`-class normalization dropped it post-archive; the
  earlier repair restored only the arrow of the two-marker
  `→ **Won't implement` verdict). Row 36 repaired by the house
  `→ corrected` append (marker restored, count recovered); self-test
  arms cover the post-archive strip, the live-churn exemption and the
  recovery shape.
- `scripts/rendering_audit.py`: the residual rendering sweep over the
  archived snapshots (the class the marker gates cannot see) —
  line-start `~~~` fence openers, unclosed code fences, strikes still
  open at paragraph boundaries (legal multi-line strikes stay
  silent), odd `**` parity in table rows; code-span content is
  stripped before counting and the del-tag class is retired (the .md
  archives carry only prose MENTIONS of `<del>`, which parity cannot
  separate from markup). Live sweep: 77 files, 0 rendering damage —
  the earlier in-place repairs held.
- `docs/lessons/markdown-normalization.md`: the formatter-over-archives
  incident class in full — all three incidents (`5ba5d2b` verdict
  column, `04562e787` fence destruction, the 2026-10-12 row-36
  partial-repair find), the CommonMark/GFM mechanics behind them
  (fence openers, paragraph-bounded strikes, literal code spans,
  table re-wraps), the recovery-by-append grammar, and the monotonicity
  arm's mechanism deviation (pickaxe edge-counting → `--follow` +
  per-revision peak/recover counts).
- AGENTS.md marker-convention paragraph slimmed to rules + pointers
  (incident history, CommonMark mechanics and arm mechanics moved to
  the new lesson); `docs/DOMAIN_LANGUAGE.md` gains verdict marker,
  verdict-marker count, monotonicity arm, recovery-by-append and
  fence-immune.
- `tests/test_markers_check.py`: the marker-gate regression suite
  (15 stdlib tests porting the load-bearing arms into the BuildFlow
  pytest lane — ID-header regression, count-preserving evasion class
  in pure-function form, exit-code/docstring parity, rendering-audit
  arms, the incident triangle at HEAD); wired as
  `checks.markers-test`.
- `scripts/archive_snapshot.py` + `checks.archive-checklist`: the
  archive-time ordering as the only path — content gate BEFORE
  `git mv`, check-rows when the docs-health annotator is reachable
  (loud skip otherwise), post-move markers + rendering gates after;
  self-test proves the refusal arm (an unmarked snapshot never moves)
  and the green path on a synthetic repo. `checks.rendering-audit`
  runs the sweep plus the triangle in the sandbox (`--repo-root`).
- `scripts/doc_counts.py` (round-11 spike): derives the flake-check
  and stdlib-test counts and diffs them against the FEATURES/AGENTS
  literals — caught both claims stale the moment it ran (39→44 checks,
  154→169 tests); wiring it as a standing gate is the owner call.
- `services.telephony.pbx-lens` + `checks.telephony-lens` (the round-11
  lens lane): CDR ingest now rides the operator API's three-layer
  FS-state read path (ro bind + telephony-fs group + ACL ordering,
  eval-asserted in `telephony-eval` with a bare-lens negative arm), the
  backup oneshot preStarts the staging dir (sqlite VACUUM INTO refuses
  to mkdir), and the VM suite proves the real chain — a sofia leg's
  Master.csv row reaching `/api/export.jsonl` at a 2s cadence plus a
  verified staged snapshot. The suite also drove the eval fixtures'
  latent readOnly double-import out (tls-mode-host/file-secrets-host
  imported the module set alongside the wrapper; first read of
  `state.paths` surfaced it).

### Changed (2026-10-12 — round 11: relock gate-5 auth-surface clause)

- `docs/ops-runbook.md` Lock-bump runbook: gate 5 now carries an
  auth-surface clause for the upstream "unified auth on cqrs-htmx +
  server-side SIP credential brokering" wave — seam scan on the
  webphone delta, the `/config.js` strict-key contract
  (`tests/configjs_check.py`), the pinned login DOM selectors, and the
  `/phone-api` Basic-auth gate; a moved contract is fixed in the SAME
  commit as the relock, never a follow-up.

### Changed (2026-10-12 — webphone input relock `db741fd0 -> 4547c62`, attributed after the fact)

- **Relock of the `webphone` flake input, `db741fd0bed6 -> 4547c6212bae`**
  (attribution for the daemon heuristic commit that moved the lock without
  a record — `lock-move-guard` went red on the next `nix flake check`, the
  gate working as designed, caught by the 2026-10-12 pbx-lens module-wave
  re-eval). Second hop of the day on the same upstream plan wave; the
  previous hop's proofs (2026-10-12 ~05:10-05:25 CEST) cover the wave.
  Proofs THIS entry runs: hosts `pbx`/`pbx-prod` eval green with the new
  lock plus the pbx-lens `pollMaxAge`/`recordingTimeout` module options;
  `nix flake check` re-run green with this entry (lock-move-guard back to
  PASS). NOT yet re-run for this hop: the webphone VM suites and the
  browser gate — schedule them with the next deploy window; until then
  treat 4547c62 as eval-verified only.

### Changed (2026-10-12 — webphone input relock `4547c62 -> 706e97d`, attributed)

- **Relock of the `webphone` flake input, `4547c6212bae -> 706e97d19f47`**
  (attribution for the daemon heuristic commits `df4c56d` + `63b8563`
  that moved the lock in two hops — `4547c62 -> c2caead8 -> 706e97d` —
  without a record; `lock-guard` went red on origin, the gate working
  as designed, burning a 53-minute CI cycle that every other check in
  the run passed). Upstream delta is three auto-commits on the same
  unified-auth wave the previous hops rode: the island-JS slimming pass
  (20 files, 153 insertions / 452 deletions across
  `internal/web/assets/island/app/*` + `shell.js`), docs-only updates
  (error-contract + the SUPERB train status reports), and a README
  touch. Proofs THIS entry has: local `nix flake check --all-systems
  --no-build` eval-green at the moved lock; `nix fmt` clean. The VM
  ladder rides the CI run this entry triggers — until it completes,
  treat 706e97d as eval-verified only (same honest stance as the
  4547c62 hop above).

### Changed (2026-10-12 — webphone input relock `dffdb5f -> db741fd0`, attributed)

- **Relock of the `webphone` flake input, `dffdb5f06 -> db741fd0bed6`**
  (attribution for the daemon heuristic commit that moved the lock at
  ~03:28; `lock-guard` went red on origin within the hour — the gate
  working as designed). Upstream delta is 37 commits: the "unified auth
  on cqrs-htmx + server-side SIP credential brokering" plan wave (Go
  seams across app/asr/blob/config/crm/domain/fax/paperless/pbx/server/
  store/vcard) plus a `.templ` + island-JS markup/bundle pass (icon
  system, thread previews). Proofs, per the Lock-bump runbook ladder:
  binary build green (`nix build .#webphone` → `webphone-2.8.0`);
  `nix fmt` clean; `nix flake check --no-build` eval-green; VM suites
  `telephony-webphone`, `telephony-fax` and `telephony-fax-feed` green;
  the markup delta triggered the browser gate and
  `legacyPackages.telephony-browser` is green (all run locally
  2026-10-12 ~05:10–05:25 CEST). The rev was confirmed on upstream
  origin/main before attribution.

### Added (2026-10-12 — docs-health round 10: snapshot sweep, gate header arm, living-doc refresh)

- Docs-health round 10 over the open 2026-0* snapshots: the markers-arm
  session report, the round-9 harvest report and the round-10 lockdown
  plan are fully annotated inline (every §b/§c/§f/§g item and Step-2
  M-row carries a verdict) and archived with per-dir manifests
  (`docs/{status,planning}/archived/README.md`); the research and
  decision docs keep their standing classifications (dated,
  self-resolving records, not work trackers). Archive set now 75
  snapshots; gates green (markers 77 files / 0 findings including the
  monotonicity arm, check-rows complete, drift PASS).
- `scripts/markers_check.py`: `ID` joins the table-header exclusion
  words — a `| ID |`-headed Step-2 M-table (the round-10 plan shape)
  was flagged as one unmarked item; self-test arm added.
- Living-doc truth pass: FEATURES.md (39 checks re-derived 2026-10-12,
  AI voice agent row added, webphone lock line refreshed to
  `db741fd0`), README.md (voice agent / pbx-lens / passkey capability
  rows + architecture nodes), AGENTS.md (154-test count, voice-agent
  intro paragraph, complete `modules/telephony/` module map),
  ROADMAP.md (OQ7 answered by the lock-guard shipping; docs-gate
  raw-idea cluster harvested; agent theme marked shipped).

### Fixed (2026-10-09 — the registry-slimming flip was a closure no-op)

- **`opsTools.embedNixpkgsRegistry = false` did not shrink the closure.**
  Found the same day it shipped, by measuring instead of trusting the
  option: the staged closure still carried the ~200 MiB nixpkgs source.
  Root cause: nixpkgs ITSELF registers the same `nixpkgs` registry entry
  via `nixpkgs.flake.setFlakeRegistry` (mkDefault,
  `nixos/modules/misc/nixpkgs-flake.nix`), and the option's `mkIf`
  disables only its own duplicate definition — a disabled duplicate
  cannot beat a default. Fix: flipping the option now also disables
  `nixpkgs.flake.setFlakeRegistry` and `nixpkgs.flake.setNixPath` (the
  pair is assertion-coupled upstream). Measured after the fix: the
  source leaves the closure (-199.7 MiB on the consumer toplevel).
  Both directions are now pinned by an eval-time `assertions` pair in
  `ops.nix` — the disabled arm is exactly the check that would have
  caught this bug at eval instead of at a closure-size audit.

### Added (2026-10-09 — TCP trunk shape, fs-cert renewal suite, anti-spoof eval warning, registry slimming)

- **`telephony-noreg-gateway-tcp` VM suite** (`tests/noreg-gateway-tcp.nix`,
  TCP-speaking extension of the fake ITSP in `tests/itsp_stub.py`): pins the
  WORKING production trunk shape `host:port;transport=tcp` end to end — the
  407 challenge is answered with a digest retry (the anti-spoof check
  ACCEPTS it) and the call answers, all with `;transport=tcp` still in the
  routed URI. This is shape (b) from the 2026-10-08 lesson: the port's
  colon keeps `sofia_glue_get_host_from_cfg`'s last-":" truncation on the
  clean host while TCP stays in the INVITE.
- **`telephony-fs-cert-renewal` VM suite** (`tests/fs-cert-renewal.nix`,
  routed gap from report 2026-09-18_14-47 §f.22): pins the whole
  `telephony-fs-cert` contract — boot render into sofia's tls-cert-dir
  layout, DynamicUser ownership handoff, the hash-guarded redundant fire
  (no call-dropping restart), and the RENEWAL path: fresh ACME bytes →
  PathChanged → re-render → freeswitch restart → profile RUNNING again.
  Hermetic: the fake `/var/lib/acme` dir is seeded by a boot unit, the
  webphone vhost (and with it the only security.acme cert) stays off.
- **Eval-time warning for the gateway anti-spoof trap**
  (`modules/telephony/default.nix`): a gateway `proxy` carrying URI
  params (`";..."`) WITHOUT a `":port"` before them now warns at eval
  (that shape silently abandons every outbound 407 — caller 480
  cause 96, zero journal lines). Eval-proven in both directions: the
  trapped shape fires, `host:port;params`, bare host, and port-only
  stay silent.
- **`opsTools.embedNixpkgsRegistry` option** (default `true`,
  `modules/telephony/options.nix` + `ops.nix`): the pinned
  `nix.registry.nixpkgs.to` path entry drags the nixpkgs SOURCE tree
  (~200 MiB) into the system closure via `/etc/nix/registry.json`;
  appliance consumers can now opt out (`nixpkgs` refs then fail closed —
  the global registry stays disabled either way, nothing floats).
- **`docs/deploy.md` §5.1 "Outbound trunk (gateway) diagnosis"** (routed
  gap from report 2026-09-16_14-33 §c.2): the gateway-down ladder —
  NOREG-is-healthy semantics, the silent 480/96 anti-spoof shape,
  provider datacenter-IP fraud screening, REGISTER backoff, and the
  CDR-first read.

### Fixed (2026-10-08 — eval-only checks demand a build again: agentCheck readFile)

- **`tests/eval.nix` `agentCheck` no longer reads the generated
  dialplan from the store at evaluation time** (local commit `355f7b6`,
  UNPUSHED — the fix that un-reds main CI). The bilingual-DID train's
  two `ai_agent_did`/`ai_agent_lang` needle checks used
  `builtins.readFile` on the configDir value, but upstream types that
  option `attrsOf path`, so the value is a coerced store path whose
  content only exists after a build — every `--no-build` check run
  (CI's cross-arch eval step) died with
  `path '...dialplan-public.xml.drv' is not valid`, red on all four
  2026-10-08 runs (07:53Z, 13:00Z, 13:10Z, 15:21Z). The module now
  exposes the generated public.xml content as a read-only internal
  option `services.telephony.generatedPublicDialplan` (pure string from
  the generator's writeText `.text`, pbx.nix sets it config-side), and
  the check asserts against that. Proven locally: full
  `nix flake check --all-systems --no-build` GREEN at the fix. The
  build-time greps (`grep -F ... $agentPublicXml` inside the runCommand)
  were already build-side and stay.

### Fixed (2026-10-08 — fs_cli could never connect: empty builtin host)

- **`-H 127.0.0.1` added to both `fs_cli` call sites** (the `opsTools`
  wrapper in `modules/telephony/ops.nix` and the `telephony-health`
  `fs_cli()` in `modules/telephony/monitoring.nix`). fs_cli's builtin
  profile carries an EMPTY host, so a bare call dies
  `[ERROR] fs_cli.c:1699 main() Error Connecting []` against a perfectly
  healthy event socket — proven against the built 1.11.1 binary
  2026-10-08 (the `127.0.0.1` string in the binary is not the profile
  host). Two consequences of the bug, both now dead: every operator
  one-liner in the runbook failed with `Error Connecting []` despite
  the password wrapper, and `telephony-health` could NEVER pass — its
  five-retry loop failed unconditionally, so the unit reported "event
  socket unresponsive" regardless of the socket's real state (also
  poisoning the health-watchdog trust for the 2026-10-03 ESL outage
  readout). The ops-runbook cheat-sheet's manual fallback function now
  carries `-H` too and documents the trap.
- **`tests/agent.nix` was nixfmt-dirty** (surfaced 2026-10-09 by the
  first CI run to reach the pre-commit gate past the old eval-step
  reds): the flake `nix fmt` (treefmt's bundled nixfmt) reported 0
  changed while the pre-commit hook's store-pinned nixfmt-1.5.0
  rejected the file — two different formatters behind one name. The
  pinned binary re-indented the embedded VM-driver block (40/42 lines,
  whitespace-only); formatted with the pin itself.

### Added (2026-10-08 — noreg-gateway suite GREEN, agent E2E + reload, golden bodies)

- **`telephony-noreg-gateway` VM suite green end to end** (check
  `telephony-noreg-gateway`, `tests/noreg-gateway.nix` +
  `tests/itsp_stub.py`): the production trunk shape — a register=false
  gateway sits NOREG, never emits a REGISTER, and an outbound INVITE
  digest-auths PER CALL against the scripted ITSP (407 challenge ->
  Proxy-Authorization retry with `username="noregtest"` -> caller sees
  200). Getting there cost nine driver runs and found two real
  FreeSWITCH 1.11.1 truths, both now pinned in
  `docs/lessons/freeswitch.md`: (1) a gateway `proxy` value carrying a
  `;transport=` suffix silently disables 407 digest —
  `sofia_glue_get_host_from_cfg` leaks URI params into
  `proxy_host_cfg`, the anti-spoof check `is_legitimate_gateway` then
  rejects the challenge, and the caller dies 480 cause=96 with zero
  journal explanation; the test uses a bare IP. Production's
  `sip.telnyx.com;transport=tcp` (pbx-artmann) carries the same latent
  breakage — routed there as owner work. (2) in multi-node VM tests
  sofia binds the default-route egress (the per-VM-isolated QEMU
  user-net) — the pbx node now pins `useDHCP = false` + a VLAN default
  gateway so `$${local_ip_v4}` resolves to the eth1 address and stub
  replies are routable.
- **Agent behavior-spec + E2E layer** (`tests/test_voice_agent_e2e.py`):
  `EndToEndCallSpec` drives the real service over the real protocols
  (ESLClient socket vs a scripted event-socket peer, GeminiClient HTTP
  vs the stub, the real `Agent.run_forever()` loop — the wiring layer
  the unit stubs mock out), plus `EntrypointSpec` pinning the two FATAL
  credential branches of `main()` (exit 2, incl. the empty-file
  variant). 9 spec functions.
- **`ExecuteWaiter`** (`modules/telephony/voice-agent.py`): replaces
  ad-hoc `myevents` sleeps on the ESL leg with a waiter that completes
  on the app's EXECUTE-complete event — exercised via
  `_register_execute_waiter` in the suites.
- **Golden request bodies** (`GoldenRequestBodyTest`): the COMPLETE
  transcribe/chat wire bodies as goldens (F72) — regenerating a golden
  is a deliberate contract change, never a reflex.
- **SIGHUP reload for `telephony-agent`**
  (`modules/telephony/agent.nix` `ExecReload` + `ReloadSpec`): reload
  re-reads the prompt credential, refreshes + re-renders the greeting,
  and keeps the old greeting on TTS failure (fail-soft, logged).
- **AGENTS "Git-tree flake visibility" section**: the
  experiment-driven rules for untracked-file invisibility to flake
  evals (proven 2026-10-08).
- **Webphone input relock `1658966d -> dffdb5f`** (attribution for
  BOTH moves; the earlier one landed via the daemon without a
  CHANGELOG line): the 15:11 pbx-artmann daemon lock sweep onto
  `1658966d` hit the 2026-10-03 breakage class verbatim — webphone's
  dependency bumps (cqrs-htmx v4.13.2 / usermgmt v4.14.2, koanf
  v2.3.8) had landed without the vendorHash repin, so the go-modules
  FOD silently served the stale module set and every consumer
  closure build died on missing-zip read errors. `dffdb5f` carries
  the repin (webphone `7c87501`, pushed); the webphone-2.8.0 build
  re-proven green at the new pin before relocking.

### Added (2026-10-07 — bilingual agent by DID, agent health watchdog, VM E2E, fs_cli wrapper)

- **Bilingual agent by DID** (`services.telephony.agent.languageByDid` /
  `greetingByDid`): an inbound call to a mapped agent DID is greeted,
  replied and failed-over in its own language — per-call TTS language,
  a prompt directive ("Always hold this conversation in <lang>"),
  localized fallback lines (EN/DE silence farewell, error apology,
  transfer line, time-up goodbye; ASCII-safe German), and per-DID
  greeting rendering at boot (one TTS call per distinct entry, any
  failure fails the render). The public context stamps
  `ai_agent_did`/`ai_agent_lang` channel variables ahead of the
  agent-extension transfer (tests/eval.nix pins the env JSON + both
  variables; 5 new unit tests in BilingualByDidTest).
- **`telephony-agent` VM E2E** (`tests/agent.nix` +
  `tests/gemini_stub.py`, check `telephony-agent`): the real systemd
  wiring end to end — dial 9100, the parked leg is picked up over the
  event socket, the loopback Gemini stub answers one turn with
  `[ACTION: end]`, the caller gets RTP and a server BYE, the transcript
  records `agent_end`, the call WAV lands in the recordings dir, and
  `/health` reports `esl:true` + `calls_total:1` (driver-verified
  2026-10-07, 73 s script time).
- **Agent watchdog in `telephony-health`**: the loopback-only
  `/health` endpoint is now probed with the `esl` flag checked — an
  agent that is up but ESL-disconnected answers nothing and previously
  no gate noticed (the 2026-10-05 outage class). Bounded retries absorb
  the reconnect race after a FreeSWITCH restart.
- **`fs_cli` password wrapper** (`opsTools`): bare `fs_cli …` works
  verbatim for operators — the wrapper injects the event-socket
  password as a per-invocation runtime read (rotations take effect on
  the next call, nothing secret in the store; hiPrio over the
  freeswitch package's own binary).
- **Agent loop hardening tests**: the `AGENT_MAX_CALL_SECONDS`
  deadline (zero-turn farewell, never a hung channel), two concurrent
  calls on one agent, a `walk_collect` envelope-shape matrix, and the
  loud `sendmsg` execute-timeout message (names app + uuid). Suites:
  test_voice_agent 35 -> 50.


### Changed (2026-10-07 — webphone input relock `d84df26 -> 77f2a16`, attributed post-sweep)

- **Attribution record for the SIXTH unattributed daemon lock sweep**:
  commit `5c811e5` (heuristic message, 05:49:55) moved the pin
  `d84df26 -> 77f2a16` about 60 s after upstream pushed `77f2a16`.
  The commit-msg tripwire did not fire despite being installed and
  canary-proven — root-caused this session: the daemon commits through
  go-git (go-commit's `git.NewGoGitWithRetry`), which never executes
  git hooks; the earlier "no `--no-verify`" source verification was
  vacuous. CLI commits stay gated. Verified for the new rev: binary
  builds (`webphone-2.8.0`), and the upstream delta is 9 regenerated
  `*_templ.go` files whose only change is the templ error `FileName`
  gaining a `webphone/` path prefix (261/261 symmetric lines, zero
  markup — DOM contract unaffected by construction, no browser-E2E
  trigger).

### Changed (2026-10-07 — webphone input relock `3928dbd1 -> d84df26`, attributed)

- **Relock of the `webphone` flake input, `3928dbd1 -> d84df26`** (71
  commits / 31 code files past the last attributed rev; the pin moved
  again mid-ritual — FIVE unattributed auto-commit daemon lock sweeps
  total: `208bf6e`, `f2bf1ee`, `bc9406e`, `f4f0d75`, then `98323e2`
  moving `f0772e1 -> d84df26` while the ritual ran). This entry is the
  missing hand-authored record the lock-guard gate demanded. The
  substantive delta (71 commits / 31 code files: passkey/session/enroll
  UI work in `enroll.js`/`auth.js`/`tw.css`, CRM surfaces, the
  Paperless archive seam, upstream nix packaging) landed entirely by
  `f0772e1`; `f0772e1 -> d84df26` is verified docs-only (28 markdown
  files, zero code — same binary, same module surface, same DOM).
  Ritual verdicts: binary builds (`webphone-2.8.0`), all 30
  browser-E2E DOM selectors verified in the upstream tree before any
  VM time, webphone (incl. configjs contract) + empty-secret +
  messaging + fax-feed suites green, browser E2E green under quiet
  load (one load-44 flake exonerated per the runbook protocol: the
  restart drill's 30s graceful-shutdown deadline expired under a
  sibling build storm while every server-side contacts request
  returned 200). Upstream `d84df26..origin/main` is docs-only — the
  pin is code-current; no fresh bump taken.

### Changed (2026-10-07 — flake-inputs remediation train: gate hardening)

- **Commit-msg tripwire `lock-move-guard`**: any commit that moves the
  webphone lock rev without a `relock:` / `lock-bump` marker in the
  message is refused (staged-vs-HEAD flake.lock comparison, six-arm
  self-test; `scripts/heal-pre-commit-hook.sh` installs both stages).
  Unattributed daemon lock sweeps become blocked commits instead of
  post-hoc lock-guard findings.
- **`checks.changelog-headings`**: hermetic flake check over
  `tests/changelog_headings.py` (duplicate/decay sweep +
  `--self-test`).
- **statix + deadnix consolidated onto treefmt programs**: the
  standalone `checks.statix`/`checks.deadnix` and `statix.toml` are
  gone (`checks.format` runs them; findings-equivalence proven before
  deletion).
- **Verification capstone green**: full-mode BuildFlow ends at the
  documented findings-gate shape (exactly the four nix-checker
  port-collision errors); origin CI run `37555437689` GREEN at
  `86f3d3d` — the first fully green run since the lock went red (the
  pre-fix run `37552875317` failed on lock-guard). Closes the
  CI-gate-green and kill-ledger TODO rows.

### Fixed (2026-10-06 — voice agent: two call-loop bugs, found by new E2E specs)

- **ESL event-queue race**: `run_forever`'s dispatch loop and each call's
  handler read the same `ESLClient.events` queue, so a
  `CHANNEL_EXECUTE_COMPLETE` could be consumed by the dispatch loop (which
  ignores it) while the handler that issued the `sendmsg` waited for it
  forever — the "agent answers silent after the greeting / sendmsg execute
  never completes" symptom. Completing execute events are now routed to a
  registered waiter in the reader thread before the dispatch loop can see
  them.
- **Transcription fed the record path, not the audio**: `_handle_call`
  passed the recorded WAV *path string* to `GeminiClient.transcribe`,
  which carries the audio inline (base64) — the real client raised
  `TypeError: a bytes-like object is required` on every first utterance.
  The FakeGemini stub masked it (string slicing "worked"); the new E2E
  specs, which drive the real client, caught it. The handler now reads the
  file to bytes.
- New contracts (`tests/test_voice_agent_e2e.py`, 7 tests): behavior/E2E
  specs over a real event-socket peer and a real Gemini HTTP stub through
  `Agent.run_forever` (greeting, transfer on `[ACTION: transfer]`, transfer
  on DTMF 0, fail-closed on a placeholder key, ignored non-agent park), plus
  the `main()` FATAL credential branches (missing/empty `esl_pass`, missing
  `system_prompt`) in a subprocess. `tests/test_voice_agent.py`'s DTMF
  dispatch spec, previously flaky (~1 in 5), is now deterministic.

### Fixed (2026-10-06 — FreeSWITCH 1.11.1 builds under GCC 16)

- **Root cause of the source-build breakage on the GCC-16 nixpkgs flip**
  (`b4fd65b`): glibc 2.44's `assert.h` is deliberately RE-INCLUDABLE (it
  unguards `_ASSERT_H` on every include), GCC 16 mis-merges the identical
  re-parsed `__assert_single_arg` declaration into a hard "conflicting
  types" error, and the C23 assert macro's
  `sizeof (__assert_single_arg (expr))` expansion hard-errors on the
  codebase's ubiquitous pointer asserts. A `-std=gnu17` recipe does NOT
  fix it (`config.h`'s `_GNU_SOURCE` re-enables `__GLIBC_USE(ISOC23)`
  regardless of the language revision).
- **Fix**: a self-guarded, NDEBUG-honoring assert shim
  (`modules/telephony/freeswitch-assert-shim/assert.h` — classic
  `__assert_fail` macro; the NDEBUG branch is REQUIRED because libvpx
  builds with NDEBUG while glibc only declares `__assert_fail` when
  asserts are on), carried into `services.freeswitch.package`
  (`mkDefault`) via `env.CFLAGS` so configure embeds the `-I` in every
  generated Makefile. `env.CFLAGS` is the robust carrier: a store path
  interpolated into an env STRING from an inline `--expr` gets no closure
  membership (sandbox can't see it), `NIX_CFLAGS_COMPILE` proved
  unreliable in this build's wrapper flow, and `configureFlags` entries
  are word-split (a spaced `CFLAGS=...` argument dies as an unrecognized
  option). Full x86_64 build proven green on `b4fd65b` through the module
  path; the aarch64 lane builds FS under GCC 16 with the shim in CI.
- The trunk/oxipng side of the same flip (libdeflate-sys `evex512`
  attribute) is fixed deployment-side in the pbx-artmann flake overlay
  (`hosts/pbx/trunk-libdeflate-gcc16.patch`), not here.

### Added (2026-10-05 — passkey (WebAuthn) login, wired stack-side)

- `services.telephony.webphone.passkey.*`: the upstream identity layer
  (in-process usermgmt, own `usermgmt.db`) behind a stack-derived
  surface — `rpId`/`rpOrigins` default from the vhost domain, `users`
  maps email→extensions, password files default from the extensions'
  `passwordFile` options (per-extension override for inline-password
  setups like the demo host). Eval-time assertions fail closed on half
  a config (upstream re-validates at boot); `usermgmt.db` joins the
  restic sqlite backups when the mode is on. VM-proven wiring in
  `tests/webphone.nix`: rendered config shape, conditional login DOM,
  `userauth` healthz leg, unknown-email 401 anti-enumeration, and the
  CLI token lifecycle (mint → verify 200 → burned 503). The WebAuthn
  ceremony itself stays upstream's island-tests. Operator procedure
  (enable + enroll) in `docs/ops-runbook.md` "Passkey surfaces"; demo
  host ships it enabled. Default OFF — zero config keeps the login card
  byte-identical.

### Changed (2026-10-05 — webphone relock `52f4d212` → `3928dbd1`: passkey-session hardening tail)

- 20 commits of passkey-train hardening: the CSRF token reader moved to
  a shared `csrf.js` module (island session, passkey and the standalone
  enroll page import one home), the session identity response became a
  typed wire shape (identical JSON via omitempty), `whoamiLine` moved
  from passkey.js to ui.js, and a new `enrollTokenMissing` i18n message
  guides empty-token enrollment attempts. `/healthz` gains a `userauth`
  readiness check ONLY when passkey identity is wired — deployments
  without `auth.passkey.*` (ours) keep the two-check probe surface. No
  `.templ` markup and no Go module changes; the last commit in the
  range is docs-only. Gates: binary 2.8.0, fast eval, webphone/fax/
  fax-feed VM suites, browser E2E over the moved JS (two load-induced
  theme-check flakes proven red at base `52f4d212` first — relock
  exonerated, green on retry).

### Fixed (2026-10-03 — `telephony-cdr-cancel` restructured into `telephony-cdr-visibility`)

- The suite was deterministically red and had NEVER been green (sibling
  WIP swept in by an auto-commit 2026-10-01; proven red at the
  pre-relock base `1e7df77` — the 2026-10-01 collision report
  exonerated the relock, but the check kept failing every full run).
  Root cause was two-fold: the premise (ring group rings nobody for 5s
  → `originate` returns `-ERR`) died on reality — unregistered members
  fail the bridge INSTANTLY (`USER_NOT_REGISTERED`) and
  `continue_on_fail` hands the caller to answer+voicemail, so the
  originate lands `+OK` in ~0.2s; and the loopback harness was
  structurally CDR-blind — loopback channels never reach mod_cdr_csv
  (probe: a loopback originate writes zero Master.csv rows; the same
  call through a real sofia self-INVITE writes rows immediately),
  retro-explaining the 2026-09-30 VM-side confusion. The restructured
  check drives the caller leg via a sofia self-INVITE and proves the
  missed-call→voicemail failover leaves Master.csv rows (missed-call
  visibility in the phone-API History). The mid-ring
  ORIGINATOR_CANCEL question stays on the live-host TODO track.

### Fixed (2026-10-03 — monthly flake refresh + scrub gate unblocked)

- The `flake-update` workflow never delivered its PR in two scheduled
  runs: Sep 1 died at PR creation (the repo blocks GITHUB_TOKEN-created
  PRs — "Allow GitHub Actions to create and approve pull requests" must
  be enabled by the owner under Settings → Actions → General), Oct 1
  was an infra kill mid-eval. The update step now refreshes every
  top-level input EXCEPT webphone (derived from `nodes.root.inputs`;
  webphone relocks are ritual-gated, a blind bump would fail
  checks.lock-guard on the PR), and a PR-open failure keeps the pushed
  branch and names the settings toggle plus the compare URL.
  Targeted-update semantics verified against a full update: the
  all-but-webphone set leaves the webphone lock node untouched.
- The scrub gate was blocking every commit: the 2026-10-02 hook-gap
  report quoted the exact DID-shaped literal it described scrubbing.
  The quote now describes the literal instead of carrying it; the
  literal remains in pushed history (a0c78ca) — history surgery is an
  owner decision.

### Changed (2026-10-03 — webphone relock `ffaa03fd5ce5` → `f27525b693e5`: attribution restored after three more daemon sweeps)

- The webphone input moved three more times without a hand-authored
  record: `ffaa03fd5ce5` → `35688a171988` → `66f16ad1f5a4` →
  `f27525b693e5` (2026-10-02 11:18 through 13:56, automated
  `nix flake update` sweeps committed by the auto-commit daemon — third
  recurrence of lock-guard's exact failure class). This entry restores
  the attribution and records the gate ladder run at the new tip:
  binary proof (`nix build .#webphone` → webphone-2.8.0), fast gates
  (`nix fmt` + `nix flake check --no-build` + every cheap check built),
  the 122-test stdlib suite, the webphone + fax + fax-feed VM suites,
  and the browser E2E (green; the six DOM-contract ids and the
  `.call-state-text`/`.transfer-row` selectors were pre-verified in the
  upstream `phone.templ`/`calls.js` at this rev before the run). Delta
  shape across the 40 commits: `a00dadc` (message organization,
  snippet replies, trust feedback seams), `65b7f0d` (boot failures
  classified via error-chain), `66f16ad` (T23 close-out with two
  harness-found product fixes); the rest is chores/docs/ui-shots. The
  markup delta is real (messages/settings/fax templ, shell.js) but no
  DOM-contract selector moved. Upstream tip `f27525b693e5` is proven by
  this repo's suites, not by upstream CI.

### Changed (2026-10-02 — webphone relock `f706575b5285` → `ffaa03fd5ce5`: attribution restored after three daemon sweeps)

- The webphone input moved three times without a hand-authored record:
  `f706575b5285` → `8b575c9898e5` → `d0ee9f5b0d34` → `ffaa03fd5ce5`
  (2026-10-01 23:22 through 2026-10-02 08:33, automated
  `nix flake update` sweeps — lock-guard's exact failure class). This
  entry restores the attribution and back-fills the gate ladder: binary
  proof at the new tip (`nix build .#webphone` → webphone-2.8.0),
  `nix fmt` + `nix flake check --no-build`, the webphone + fax +
  fax-feed VM suites, the 122-test stdlib suite, and the browser E2E
  (one run stalled in the theme-flash check while three VM suites ran
  concurrently; a re-run on the idle machine passed clean — the DOM
  contract ids were also pre-verified in the upstream templ sources,
  so the stall was tooling-side, not markup-side). Delta shape: island
  growth in pcsetup/mic/panels, history/layout/phone templ upgrades,
  modulepreload links in the shell; no DOM-contract or served-asset
  path changes. Upstream tip `ffaa03fd5ce5` is proven by this repo's
  suites, not by upstream CI.

### Fixed (2026-10-02 — ops.nix eval warning rename + lint loop)

- `nix.nixPath` → `nix.settings.nix-path` in the ops-tooling module
  (the rename NixOS has warned about on every eval; it rode this lock
  move as planned). Eval-only flake check is now warning-free.
- ruff is clean again after the checker gained new rules: the three
  shebang scripts (`scripts/lock_guard.py`, `tests/telnyx_stub.py`,
  `tests/whatsapp_probe.py`) are executable again (EXE001), the
  markers-check git walkers pass explicit `check=False` (PLW1510), and
  the operator-SMS test uses `next()` over a slice-of-comprehension
  (RUF015). 122 stdlib tests pass unchanged.

### Fixed (2026-10-01 — backup truth-up: webphone, recordings and CDR actually ride restic)

- `state.paths` existed so backup tooling never hardcodes module paths,
  yet it omitted the webphone entirely, and the pbx-prod template
  promised "voicemail/CDR/recordings are not single-copy" while its
  restic `paths` shipped none of recordings, `cdr-csv` (despite
  `cdr.enable = true`) or any webphone data. Now: `state.paths` gains
  the webphone online-snapshot dir (upstream's drill-verified
  `sqlite .backup` + blob-rsync timer, default-on via
  `services.webphone.backup.enable = mkDefault true`), the restic unit
  `Wants`+`After`s `webphone-backup` so every run archives a fresh
  consistent snapshot, `state.sqliteDatabases` names the live
  `webphone.db`, and the pbx-prod template consumes `state.paths`
  (`lib.unique` against the wholesale freeswitch dir). VM-proven:
  webphone-blob + recording + CDR-row canaries round-trip
  byte-exact through a real restic backup/restore, the restored db is
  a genuine SQLite file (`tests/backup.nix`).

### Fixed (2026-10-01 — restore the last-CI-green flake.lock)

- The 8cf9e48 daemon sweep carried an unvetted monthly-refresh catch-up
  into main's `flake.lock`: nixpkgs `7a0f122f5090` → `b4fd65b198c5` and
  webphone `0e1d17436296` → `241b9083e95b` (a floating main rev past the
  vetted v2.8.0-train pin, unattributed — `lock_guard`'s exact failure
  class). The nixpkgs half broke the aarch64 lane outright: FreeSWITCH
  1.11.1 fails to compile against the newer glibc 2.44 headers
  (`conflicting types for '__assert_single_arg'` in `mod_enum.c` via the
  ldns assert path; CI runs 36795217002/36796288402). Both nodes are
  restored to the last-green pins (`7a0f122f5090`, `0e1d17436296` — the
  lock is byte-identical to 3afcf57, the 2026-09-30 12:20 green run);
  the aarch64 FreeSWITCH at the restored pin substitutes clean from the
  cache. The 2026-09 monthly refresh stays on
  `chore/flake-update-2026-09` and needs an aarch64 FreeSWITCH fix
  (nixpkgs fix or overlay patch) before it can merge.

### Changed (2026-10-01 — webphone relock `0e1d1743` → `f706575`: the v2.8.0 UX train)

- The webphone input rides upstream main forward 67 commits to the
  2026-10-01 tip `f706575` (binary reports 2.8.0), picking up the whole
  post-v2.8.0 UX train: mic pre-warm while a call RINGS (mic acquisition
  leaves the answer path — the Bluetooth-headset answer-latency fix),
  honest hold UI + `#offline-banner` (new DOM-contract id) driven by the
  same registration truth as the status pill, mobile bottom tab bar +
  call-prominent island + sized tap targets, a11y skip link + error
  associations + reader theme state, loading skeletons + panel
  transitions on tab swaps, transcript day-grouping with unread
  markers, and a Settings-surfaced command palette. Two NEW
  capabilities arrive off-by-default: a Paperless-ngx archive for
  inbound faxes (`paperless.url` + `paperless.token`, both-or-neither)
  and the go-health dashboard at `/health`
  (`settings.dashboard.enable`). The upstream NixOS module was
  refactored into `options.nix` + `caddy-vhost.nix` +
  `backup-script.nix` — consumer-transparent for this stack: `settings`
  stays a freeform-JSON submodule and every seam we ride
  (`backup.enable`/`destDir`, `memoryMax`, `environmentFiles`,
  `gateway.webhook_secret_file`, `identities`) evaluates unchanged.
  Upstream's contacts-manager CRUD was REVERTED (`6989b99` — contact
  depth is Ledger's domain); the personal scratchpad survives, so the
  browser E2E's contacts round-trip and logged-out data-dial guard
  still pass as written. Verified green at the new rev: `nix build
  .#webphone` (checkPhase included), `nix fmt`, `nix flake check
  --no-build`, and the `telephony-webphone` + `telephony-fax` +
  `telephony-fax-feed` VM suites; the browser E2E re-proved the DOM
  contract on the new markup (`CONTACTS-ROUNDTRIP-OK` through `E2E-OK`).

### Added (2026-09-30 — Gemini AI voice agent)

- **Wire shapes verified against primary docs 2026-10-01** (ai.google.dev
  speech-generation guide + the Interactions OpenAPI spec,
  `/static/api/interactions.openapi.json`): conversation steps are
  type-tagged (`{"type": "user_input"|"model_output", "content": [...]}`,
  not `role`), the persona prompt rides the top-level `system_instruction`
  field, `response_format` (`{"type": "audio", "mime_type": "audio/wav",
  "sample_rate": 8000}` — 8 kHz explicitly supported, plus
  `audio/mulaw`/`audio/alaw` telephony encodings) sits at the request top
  level next to `generation_config.speech_config` (a LIST of
  `{voice, language}`), and every request sets `store: false` so caller
  audio and transcripts are not retained server-side (server-side state
  via `previous_interaction_id` is deliberately unused; the agent resends
  its own transcript). Input audio content carries `sample_rate`/`channels`
  metadata. The response walker stays envelope-tolerant (documented
  `steps[].content[]`, legacy `candidates[].parts[]`).
- `services.telephony.agent` (`modules/telephony/agent.nix` +
  `voice-agent.py` + dialplan wiring in `modules/freeswitch.nix`): a
  loopback stdlib-Python service that answers inbound calls over the
  FreeSWITCH event socket and runs a turn-based conversation with
  Google's Gemini models — record one caller utterance, transcribe +
  answer with the chat model (audio input), speak the reply with the
  Gemini 3.8 text-to-speech model (`gemini-3.8-flash-lite-tts`), repeat
  until the model requests a transfer (`[ACTION: transfer]` to
  `agent.transferDestination`), an end (`[ACTION: end]`), the caller
  dials 0, or a turn/time cap trips. Reach: `agent.answerDids`
  (intercepted in the public dialplan ahead of the gateway
  didDestination) and the internal `agent.extension` (default 9100).
  The agent extension records through the same dialplan path as every
  other destination (full stereo WAV; requires `recording.enable`) and
  writes a per-call JSONL transcript next to it; per-turn audio is
  deleted after transcription. Secrets ride LoadCredential (Gemini API
  key, event-socket password, system prompt); a `PLACEHOLDER*` key
  fails closed honestly (farewell tone, transfer to the human
  destination when configured, zero Gemini calls). `GET /health` on the
  loopback httpPort reports liveness, call counters and credential
  state. Honest v1 limits: no barge-in (turn-based), endpointing is
  the record app's silence detector, DTMF-0 transfers land at the next
  step boundary. Eval contracts pinned in `tests/eval.nix`
  (`agentCheck` + five rejection rows), service behavior pinned by
  `tests/test_voice_agent.py` (29 stdlib tests: WAV normalization,
  shape-tolerant response walker, request shapes against a loopback
  HTTP stub, ESL client against a fake event socket, and the call
  loop's decisions against stub collaborators).

## [0.3.0] - 2026-09-30

### Added (2026-09-30 — round-10 first-call-lockdown execution wave)

- WhatsApp correctness pair (TODO rows done): `forward_message_status`
  now reads BOTH Telnyx envelope shapes — the SMS `to`-list AND the
  WhatsApp/Meta envelope (string `to`, verdicts in `statuses`/flat
  `status`, pinned by `message.echo` in the webhook catalog) — mapping
  Meta's `read` onto delivered (the webphone hook accepts only
  delivered|failed), so a string-`to` status event can no longer be a
  silent no-forward. Inbound WhatsApp media rides a 16 MiB per-medium
  cap (MMS stays 5 MiB; the webphone hook's 40 MiB body cap accepts the
  base64 inflation) instead of being a permanent silent loss. Eight new
  stdlib tests; the 5 MiB oversize-image fixture is monkeypatched tight
  (the suite drops ~50 s of multipart pushing).
- Bridge WhatsApp VM suite against an in-VM stub Telnyx (TODO row
  done): `tests/telnyx_stub.py` + five new arms in the messaging suite —
  outbound whatsapp send through the REAL unit → bridge → HTTP wiring
  (spec-shaped `whatsapp_message` asserted from the stub's log), the
  40008 window refusal surfacing the 24-hour/template guidance,
  inbound Meta-body tagging (`whatsapp+` thread key end to end into the
  real webphone DB), and the string-`to` status verdict riding the full
  production path to a delivered row. The bridge's Telnyx API base is
  now env-overridable (`TELNYX_API_BASE`) for exactly this.
- WhatsApp smoke probe (TODO row done): `tests/whatsapp_probe.py` — the
  vantage-probe pattern for the messaging lane: real round trip (send
  via the Telnyx WhatsApp API, await the human echo nonce-matched in
  the receiver log), verdict table + exit codes (0 ROUND_TRIP / 2
  SEND_FAILED / 3 NO_ECHO / 4 UNREACHABLE); the probe's send payload
  was corrected BY the OpenAPI cross-check (below).
- Reconciler WABA lane (TODO row done): optional `whatsapp_did`
  desired-state key — `GET /v2/whatsapp/phone_numbers` (schema verified
  against the OpenAPI spec) asserted read-only; an unregistered or
  disabled number reports as a `VERIFY whatsapp` step that is
  report-only (never drift-exit-2: no API call converges a Meta
  signup). Three new reconciler tests.
- Operator SMS tab channel lane (TODO rows done): the operator API now
  flattens the bridge's envelope JSONL (the raw
  `{received_at, remote, body:{data:{…}}}` rows the receiver actually
  writes — the old parser expected a flat shape that never existed on
  this bridge, so real rows rendered empty) with a normalized
  `channel`; the operator window renders non-SMS channels as a badge
  (WhatsApp distinctly). Five stdlib tests + the operator VM suite now
  drives two envelope fixture rows through the real service. FEATURES
  legend-vs-usage lint added as a drift-alarm arm (self-tested).
- WhatsApp docs bundle + OpenAPI cross-check (TODO rows done):
  deploy.md §2 step 6 (embedded signup, VOICE-OTP warning, round trip,
  window/template rules, preview_url note), ops-runbook WhatsApp
  debugging (40008 ladder, conversation-window endpoint, media-fetch
  fallback, thread-split symptoms, status-envelope note), the commented
  `messaging.whatsapp` block in hosts/pbx-prod, and the
  providers-doc §WhatsApp cross-checked against team-telnyx/openapi
  `spec3.json` (fetched 2026-09-30): send key `whatsapp_message`, text
  `{body, preview_url=false}`, media `{link, caption, filename}`,
  response `data.id`, `WhatsappPhoneResponse` fields — bridge conformant
  on every point; the cross-check caught one wrong probe payload.
- Eval warning (TODO row done): `messaging.whatsapp.enable` without
  `messaging.enable` warns instead of silently no-oping (mkMerge
  restructure of messaging.nix; pinned by a new eval-check case).
- CDR cancelled-leg investigation (TODO row advanced, still open):
  source-level verdict — mod_cdr_csv has no hangup-cause filter and
  this stack sets none of the suppression vars, so a cancelled-mid-ring
  A-leg SHOULD write a Master.csv row; the live no-row is therefore not
  core behavior and needs live-host reproduction. The VM harness fight
  (ten runs, FreeSWITCH never dials a scripted TCP listener from a
  bridge) is documented in `tests/sip.py` missed-call; a `missed-call`
  UAS subcommand (register → 180 → CANCEL → 487) ships as tooling.
- CI posture packet (owner applies): `docs/ci-posture.md` — branch
  protection payloads (interim aarch64-only required context while the
  x86 infra-kill streak is live), the notification options, and what
  the agent lane already verified (README badge present).

### Added (2026-09-30)

- Relock attribution, third same-day move (was daemon heuristic
  `3afcf57`, no hand-authored line): webphone input `a8868fd` →
  `0e1d174` = upstream **v2.8.0**. Delta includes the operator pages /
  panels wave and a serving change this repo had to answer: webphone
  v2.8.0 stopped relying on the nginx-only vhost guard, so
  `5067ef4` flipped `web.nix` to the caddy-shaped guard in the same
  lane. Proven by the FIRST completed green origin full gate over a
  webphone lock move: run 36714029522 (17m, both jobs green) at
  `3afcf57` — the 2026-09-24/25 incident class (unattributed move,
  stale vendorHash) is now both attributed here and fenced by the new
  `lock-guard` check (below).
- Lock-move guard check (TODO_LIST row done): `scripts/lock_guard.py`
  fails `nix flake check` when a tracked input (webphone, the only
  input riding a moving upstream) sits at a rev CHANGELOG.md never
  mentions — the drift-alarm pattern applied to lock governance, hermetic
  over two committed files (flake.lock ↔ CHANGELOG.md) because the
  sandboxed check cannot read git history. Attribution counts from any
  CHANGELOG section (a release moving the mention into a dated heading
  stays green), needs a >=7-hex-char rev prefix, and the first live run
  caught today's `0e1d174` bump unattributed — repaired by the entry
  above. Wired as `checks.lock-guard` with a six-arm negative
  self-test (attributed, unattributed, dated-section, too-short prefix,
  renamed input, unreadable lock).
- `markers_check` monotonicity arm (TODO_LIST row done): the
  archive-marker gate now also walks each archived snapshot's full git
  history (`git log --follow`, renames included) and flags
  verdict-marker counts that drop and never recover to the historical
  peak — the net for the `5ba5d2b` incident class, where a table
  normalization dropped a verdict column while a prose arrow masked
  the loss from the per-row sweep. Recovery by append clears it (the
  house remedy); the newest point reads the working tree so an
  uncommitted repair already satisfies the gate; outside a git repo
  (the sandboxed flake check) the arm skips with a notice and
  `--self-test` proves it on a synthetic git repo (`pkgs.git` added to
  the `markers-check` derivation). First live sweep immediately caught
  a REAL second incident the per-row sweep never saw: auto-commit
  `04562e7877f7` (2026-09-29) had normalized item 29's strike tail
  (leading `~~~`) of the round-2 advisory report into a fenced code
  block, destroying the strikethrough — repaired in place in a
  fence-immune shape (`~~ ~2.2x …`), count recovered 135 -> 137 against
  the historical peak 136.
- Docs-health round 9 (WhatsApp-report harvest + archive): the WhatsApp
  session report's open-work sections are fully routed — 41 scoped items
  (§b/§c/§f/§g) carry inline routed verdicts pointing at their new homes,
  and the snapshot is archived. Harvest: 11 new TODO_LIST rows (the
  lock-tail verdict debt, WhatsApp status-event `to`-shape
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
  (webphone-2.7.0). The webphone VM suites ride the lock-tail TODO row —
  the lock moves have not been through a full gate yet (the `542443a`
  green verdict predates both).
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

- Origin CI verdict lane, kill-streak CLOSED: run 36696533753 completed
  GREEN on `542443a`, giving main its first completed green verdict over
  the WhatsApp + CDR-attribution feature lanes (all 32 checks — the
  WhatsApp session's full-check debt is paid at CI level). The completed
  verdicts bracket it: 36695596874 (`b3f1633`) a REAL red — the
  pre-commit check caught daemon-committed nix files in unformatted
  shape, fixed two minutes later by the nixfmt commit `542443a` — and
  36692071358 (`a207ad3`), 36700215494 (`dcaa818`), 36700659069
  (`0303301`) as no-failed-step-log infra-shaped failures (aarch64 green
  each time). The two webphone lock moves and the docs-health commits
  were still riding unpushed at audit time; the "no code red anywhere"
  claim in the earlier ledger entry is superseded. The full current
  state lives in the TODO_LIST verdict row.
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
