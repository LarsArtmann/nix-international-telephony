# AGENTS.md

Enduring context for AI sessions working in this repo.

## What this is

A NixOS telephony stack flake: FreeSWITCH PBX (via upstream
`services.freeswitch`) with a generated XML config, the webphone v2
service (a single Go binary from the `github:LarsArtmann/webphone` input,
wired through that repo's own `services.webphone` NixOS module) behind an
nginx TLS vhost (`wss://<host>/sip` -> TLS to sofia's `wss` transport on
loopback 7443), coturn for NAT, an ITSP gateway option, and optional
passkey (WebAuthn) login for the webphone
(`services.telephony.webphone.passkey.*` — defaults derived from the
vhost domain + the extensions' `passwordFile` options, fail-closed eval
assertions, VM-proven wiring in `tests/webphone.nix`; operator recipe in
the runbook's "Passkey surfaces"). **No
FusionPBX/FreePBX** — not Nix-packageable sanely; we generate FreeSWITCH
XML from Nix instead. The example host also enables a hardened keys-only
sshd from the `nix-ssh-config` flake input (`services.ssh-server`,
tracked `sshKeys`).

The webphone UI lives in its own repo (v2 Go service since 2026-09-18):
the input's package defaults `services.telephony.webphone.package` AND
its `nixosModules.default` is imported by the `nixosModules.telephony`
wrapper — consumers importing the raw `modules/telephony` set must
import BOTH themselves; every VM suite imports the wrapper via
`tests/common.nix`. The UI's DOM/bundle contract (what
`tests/webphone.nix`, `tests/configjs_check.py` and
`tests/browser-e2e.py` assert) is documented in that repo's AGENTS.md;
changing markup or bundle flags requires re-running those suites here.

Public repository: https://github.com/LarsArtmann/nix-international-telephony
(the local directory name predates it and keeps the historical `internatial`
typo — do not "fix" the directory, the GitHub name is the correct one).

Two example hosts: `hosts/pbx` is the throwaway demo VM (QEMU-shaped,
store-plaintext demo secrets by design); `hosts/pbx-prod`
(`nixosConfigurations.pbx-prod`) is the production template (`*File`
secrets only, ACME TLS, CDR, CHANGEME markers; toplevel eval forced by
`nix flake check`, `checks.telephony-prod-boot` boot-proves the shape
with stubbed secrets). Deployment runbook: `docs/deploy.md` — real
deployments point at `.#pbx-prod`, never `.#pbx`. sops-nix stays a
docs-only recipe (owner decision: no flake input).

Operator procedures for a deployed host (fs_cli cheat-sheet, cert
rotation, gateway REG-state debugging) live in `docs/ops-runbook.md`.
Provider evaluations (SIP-trunk/DID/CPaaS) live in `docs/providers/` —
re-verify before purchasing; prices and KYC rules drift. Security
hardening guide: `docs/security.md`.

## Commands

```console
nix flake check            # eval + build + lint + NixOS VM test (the CI gate)
nix fmt                    # treefmt: nixfmt (nix) + prettier (operator webroot)
nix build .#webphone       # webphone v2 Go binary (from the webphone input)
nix build .#freeswitch-sounds
nix run .#vm               # ephemeral demo VM (root autologin)
nix run .#initrd-audit -- --platform cloud <initrd-or-toplevel>  # driver gate
gh run view <id> --json headSha,status,conclusion,event,jobs && gh run list -b main --limit 3  # airtight CI verdict: a canceled run is GitHub infra, not code (2026-09-26/29 reds were that). Infra-kill variants: "The operation was canceled" mid-eval AND step exit 143/SIGTERM (2026-09-30 ledger: 10 consecutive x86 kills, aarch64 green throughout, protocol capped at 3 reruns — beyond that it is an owner/support lane)
python3 scripts/markers_check.py          # per-item marker gate over archived snapshots + git-history verdict-count monotonicity arm (--self-test covers both); ALSO wired as checks.markers-check
python3 scripts/lock_guard.py             # tracked-input lock-move attribution gate (flake.lock webphone rev must appear in CHANGELOG.md; --self-test six arms); ALSO wired as checks.lock-guard — a webphone relock without a CHANGELOG rev mention fails CI
python3 -m unittest tests.test_telnyx_bridge tests.test_telnyx_reconcile tests.test_operator_sms tests.test_voice_agent  # 119 stdlib tests: messaging-bridge contracts (SMS/MMS + WhatsApp lane incl. string-`to` statuses + 16 MiB cap) + Telnyx reconciler engine (incl. WABA report lane) + operator SMS-store flattening + the Gemini voice agent (Interactions-API request shapes verified against ai.google.dev primary docs + OpenAPI spec, ESL client, call loop)
PW=$(cat <trunk-password-file>) TELNYX_TRUNK_USER=<user> python3 tests/vantage_probe.py --did <e164-did>  # trunk vantage probe from this IP (exit 0 SUCCESS / 2 BLOCKED_403 / 3 UNEXPECTED / 4 AUTH_LOOP; run from several machines to map Telnyx IP screening)
TELNYX_API_KEY=$(cat <key>) TELNYX_WEBHOOK_TOKEN=$(cat <token>) python3 tests/whatsapp_probe.py --from <wa-did> --to <mobile> --bridge https://<host>  # WhatsApp round-trip smoke probe (exit 0 ROUND_TRIP / 2 SEND_FAILED / 3 NO_ECHO / 4 UNREACHABLE; replies on the phone close the loop)
```

No Makefile, no justfile — everything through flake.nix. First command of
any session here: `git status` + `ps aux | grep -E "nix|statix"` — the
auto-commit daemon and sibling agent sessions share this tree; detect
lanes before editing.

BuildFlow's local default is `build_mode: fast` (.buildflow.yml); a full
pipeline must be explicit: `buildflow --build-mode full --max-time 60m`
(1h is the flag maximum — no config key, and `BUILDFLOW_MAX_TIME` is NOT
honored; flag only). Without the cap the 5-minute hard-kill lands
mid-`nix-build`, which realizes all VM-test checks (20-60 min after any
source change). Fast gates before slow: `nix fmt` + cheap checks
(treefmt/statix/deadnix/`telephony-eval`) precede any VM-realizing run.
Full mode SKIPS markdown-lint, gitleaks, codespell (pytest-test RUNS) —
the pre-commit battery is their home.

Pre-commit hooks (nixfmt, statix, deadnix, gitleaks, changelog-headings,
scrub-check) are wired through git-hooks.nix: `nix develop` installs them
into `.git/hooks/pre-commit` and regenerates `.pre-commit-config.yaml` as
a store symlink (gitignored — never commit it). Run without a shell:
`nix develop -c pre-commit run --all-files`.

CI: GitHub Actions (`.github/workflows/ci.yml`) runs the same
`nix flake check` on `ubuntu-latest` (a udev rule opens `/dev/kvm` for the
NixOS VM test). Releases: update CHANGELOG.md, tag `vX.Y.Z`, then
`gh release create vX.Y.Z`.

## Stack conventions (mirrors SystemNix)

- **flake-parts** (`mkFlake { inherit inputs; }`): `flake = { nixosModules,
  nixosConfigurations }` at the top; `packages`/`checks`/`devShells`/`treefmt`
  in `perSystem`. Use `self'` inside perSystem, `self` only outside.
- **treefmt-nix** flakeModule provides `formatter` + `checks.format`.
- **statix + deadnix** as checks; `statix.toml` disables `repeated_keys`
  because `services` is deliberately split across mkIf blocks.
- After adding files, `git add` them: with a git repo, the flake source is the
  git tree — untracked files are invisible to `nix build/check` (this bit us:
  a stale cached source copy made statix.toml appear missing).

## Hard-won knowledge

Long-form lessons live in `docs/lessons/` — **freeswitch.md** (XML
escaping, dialplan anti-action, DTMF, mod_voicemail, sofia bind race),
**vm-testing.md** (clock jumps, initrd gaps, TCG, interactive driver,
eval-check patterns), **webrtc-browser.md** (SIP.js bundling, the
four-reason browser postmortem, Selenium traps), **operating.md**
(systemd hardening, SSH, ACME CAA, history surgery). Read the relevant
one before touching that area. The sharpest traps, inline:

- In-VM stub upstreams for the messaging bridge: the bridge's Telnyx API
  base is env-overridable (`TELNYX_API_BASE`, default the real host) —
  the messaging VM suite points it at `tests/telnyx_stub.py` on loopback
  and asserts the REAL unit→bridge→HTTP wiring (never mock that path
  again in suites). The CDR cancelled-leg reproduction (2026-09-30, ten
  VM runs) could NOT get a registered-but-never-answering endpoint:
  FreeSWITCH silently never places the B-leg INVITE toward a scripted
  TCP listener (host-IP contact AND 127.0.0.2 alike) — `tests/sip.py
  missed-call` documents the fight; reproduce on a live host instead.
  mod_cdr_csv source verdict: no hangup-cause filter, no suppression
  vars set by this stack — cancelled A-legs SHOULD write Master.csv rows
  (TODO row carries the live-host next step). LOOPBACK channels never
  reach mod_cdr_csv at all (2026-10-03 probe: a loopback originate
  writes zero rows, the same call via a real sofia self-INVITE writes
  rows instantly) — CDR suites must drive real sofia legs;
  `tests/cdr-visibility.nix` (ex-cdr-cancel, never green as a loopback
  harness) is the green shape: unregistered ring groups fail the bridge
  INSTANTLY (USER_NOT_REGISTERED) and continue_on_fail hands the caller
  to answer+voicemail, so `originate ...loopback/2000` lands `+OK` in
  ~0.2s, never `-ERR` after 5s of ring.

- Nix-to-FreeSWITCH XML escaping: `''$''${var}` for a literal `$${var}`,
  `''${var}` for a literal `${var}`; `nix eval` prints `\$` — do not
  "fix" doubled dollars. Shell-level `''` inside Python testScript
  blocks TERMINATES the Nix indented string (use `""`/`'''`).
- Dialplan `anti-action` fires on CONDITION failure, never on bridge
  failure — bridge fallbacks are plain `<action>`s listed after `bridge`
  with `continue_on_fail=true` (SIP cause mappings in the lessons file).
- sofia binds `$${local_ip_v4}` and silently falls back to 127.0.0.1
  without a default route — our unit orders after network-online.target;
  VM tests derive listener IPs from `ss -ltn`, never assume localhost.
- The metal boot path IS CI-proven (`checks.telephony-metal-boot`):
  kexec into the real pbx-prod kernel+initrd against a GPT
  `disk-main-root` behind a `virtio-scsi-pci` HBA (framework
  `diskInterface = "scsi"` is lsi53c895a — wrong bus). Mechanism
  lessons in the lessons file; `checks.initrd-audit` is the cheap
  eval-time gate.
- `PasswordAuthentication no` is NOT keys-only on NixOS (PAM answers
  keyboard-interactive); the nix-ssh-config module defaults close that
  door, tests/ssh.nix asserts it. `sshd -T` prints mixed-case directive
  names — compare case-insensitively.
- WebRTC via nginx→sofia needs exact-match `location = /sip`, TLS to
  sofia's wss-binding (a Via/transport mismatch is dropped SILENTLY),
  `apply-candidate-acl localnet.auto`, and runtime `${}` (not `$${}`) in
  the directory dial-string — four-reason postmortem in the lessons file.
- ACME failure ladder: `dig CAA <registered-domain>` FIRST (RFC 8659 —
  lego's error names the ZONE, not the host), then crt.sh (zero CT
  entries = issuance never succeeded anywhere), then the unit journal.
- Auto-commit daemon: it commits untracked files within minutes — scrub
  personal data BEFORE it does. `scripts/scrub-check.sh --history
  --strict` (patterns from gitignored `secrets/scrub-patterns.txt`,
  template: `secrets/scrub-patterns.example`) is the gate; run it before
  any history surgery and after every squash. Its `--history` pickaxe
  hits count REMOVALS too — a cleanup commit can look like a
  reintroduction; check the diff direction before treating a hit as a
  leak. Sweep forensics (2026-10-03): the daemon
  (`projects-management-automation`, auto_stage/on-change over
  `/home/lars/projects`) only stages and commits, it never runs nix —
  flake.lock UPDATE sweeps are unidentified LOCAL `nix flake update`
  executions (three on 2026-10-02; no scheduler/timer matched,
  crush-daily and PMA ruled out), so lock-guard remains the only gate.
  The daemon ALSO PUSHES (2026-10-05: eight heuristic lane shards
  landed on origin/main while a rebase-recovery was still in flight —
  "unpushed, so soft-reset and re-author" is a RACE, not a guarantee;
  after a reset, re-author immediately and expect remote shards to
  appear; recover via rebase, never force-push).
  The daemon can land a heuristic commit SECONDS after an edit (it
  beat a ritual commit by 7s on 2026-10-03): when both commits are
  yours and unpushed, `git reset --soft` and re-author. A
  pattern-flagged DID literal remains in PUSHED history (a0c78ca,
  landed through the 2026-10-02 hook gap) — history surgery is an
  owner decision; never write the literal into new files.
- nix registry pinning needs BOTH halves (ops.nix): `nix.registry.nixpkgs
  .to = pkgs.path` alone is not enough — nix eagerly fetches the global
  flake registry for any indirect ref and a failed fetch ABORTS lookup
  even when the local entry matches; `nix.settings.flake-registry = ""`
  disables it. Never let a VM test hash a path flake (tree walk →
  virtiofsd fd exhaustion); assert via `nix registry list` +
  `test -f <path>/flake.nix`. Long-form: docs/lessons/operating.md,
  docs/lessons/vm-testing.md.
- Pre-commit hook fragility: git-hooks.nix cannot heal a lost hook (it
  refuses while `.pre-commit-config.yaml` exists) and `pre-commit install`
  refuses whenever `core.hooksPath` is set (the global `~/.gitconfig`
  points it at a nonexistent `.githooks`). The auto-commit daemon itself
  NEVER bypasses an installed hook (plain `git commit`, no `--no-verify`,
  source-verified 2026-09-29) — restore with
  `scripts/heal-pre-commit-hook.sh`; a scrub canary proved the restored
  hook blocks.
- Edit mechanics (5 recurrences 2026-08→09): match structurally (row-start
  prefixes, the annotator scripts' ID grammar) — never re-type full-line
  anchors. `git mv` fails deterministically on UNTRACKED files (write →
  `git add` → then `git mv`). Diagnose from the error text, never from a
  narrative — the 2026-09-29 "race" misdiagnosis shipped a false root
  cause into a commit message.
- BuildFlow noise is DECIDED (2026-09-16), not ambient: bandit clean
  (inline `# nosec` at the ISSUE line — findings attribute to the
  innermost call line, which ruff-format rewraps), vulture clean
  (tests/vulture_whitelist.py holds load-bearing references),
  todo-check clean, lychee reads `lychee.toml` (`docs/status/**`
  excluded), pytest-test runs the two stdlib suites (73 tests since
  2026-09-30). The lint binaries buildflow orchestrates (ruff, bandit,
  mypy, dprint, prettier, vulnix; plus vulture and gh) are pinned in
  `devShells.default`: unpinned, buildflow falls back to the moving
  registry revision — the formatter version-skew class excluded in
  `.buildflow.yml`. Accepted remainder: nix-checker FOD-hash and
  port-collision advisories (bare ports compared across unrelated
  mechanisms), flake-meta-checker mainProgram (data packages have no
  executable), bandit's banner + cosmetic "nosec encountered" warning,
  and the vulnix output class: since 2026-09-29 it no longer crashes on
  NVD's retired 2.0 feed but reports ~68 advisories against
  BUILD-closure toolchain derivations (ShellCheck, perl Diff, ...), not
  the deployed host surface — unmanageable at repo level (BuildFlow#10
  class); treat as noise. The 4 gate-blocking nix-checker port-collision
  errors are the two documented pairs (443 QEMU-forward vs service
  port; NAT tcp+udp sourcePort pair) — a full-mode run therefore ends
  at the findings gate with exactly those; that IS the green shape.
  Upstream feedback filed 2026-09-29 (own repos): BuildFlow#25
  (max-time/budget config keys), BuildFlow#26 (FOD-hash advisory),
  BuildFlow#27 (mainProgram data carve-out), BuildFlow#28 (findings-
  gate ignore mechanism for the port-collision noise class),
  nix-ssh-config#5 (unmerged flake-lock update branch), pma#341 (dead
  `skip_hooks` config), and git-hooks.nix#754 upstream (non-convergent
  hook healing, external repo); a further BuildFlow item (todo-checker
  marker text) was NOT filed — scanner.go:73-78 already embeds the
  marker text at HEAD. `scripts/markers_check.py` is the standing
  marker gate (zero unmarked across all archived snapshots; negative
  self-test).
- WhatsApp lane (2026-09-30): the bridge (`modules/telephony/telnyx-webhooks.py`)
  routes `whatsapp:+E164` destinations via Telnyx's SEPARATE endpoint
  `POST /v2/messages/whatsapp` (a `whatsapp_message` object; NOT /v2/messages).
  The channel selector is the destination prefix, and the THREAD CONTRACT is
  cross-repo: webphone's `ParsePhone` sanitizer keeps letters and strips the
  colon, so `whatsapp:+49…` becomes `whatsapp+49…` — the bridge tags inbound
  WhatsApp senders with the SAME `whatsapp+<digits>` key
  (`whatsapp_thread_address`) or one conversation splits into two webphone
  threads. Changing either the sanitizer alphabet or the tag breaks thread
  coherence — tests pin the bridge side (`tests/test_telnyx_bridge.py`).
  Templates stay portal-side by design; free-form sends outside the 24h
  window fail with humanized 40008 guidance. The from-number is `WHATSAPP_FROM`
  (option `messaging.whatsapp.did`, nullOr — never defaulted from
  `messaging.did`; empty = lane fails closed with setup guidance).
- The webphone input TRACKS UPSTREAM MAIN (no rev in flake.nix; only
  flake.lock pins revisions — owner decision 2026-09-18). Safe since
  the v2 switchover: the stack imports upstream's `services.webphone`
  module (unit, user, hardening, JSON config rendering stay in sync
  with the binary); `web.nix` owns only the
  nginx integration. Switchover invariants: the app serves
  `/config.js` itself and derives TURN REST credentials PER RESPONSE
  from `settings.turn_rest.secret` or `WEBPHONE_TURN_REST__SECRET`
  (file-sourced via `services.webphone.environmentFiles` + the
  `telephony-webphone-env` boot renderer); the app's `/phone-api`
  proxy (session-injected Basic auth) fronts the read-model API;
  `= /sip` still proxies WSS straight to sofia. NEVER resurrect the
  dead patterns: the nginx config.js shadow + daily timer (a
  restart-to-rotate anti-pattern), or the static-site `share/webphone`
  webRoot copy of the 2026-09-18 pin era (vanished upstream; deploy
  died on `cp: cannot stat`). A lock update can import upstream
  breakage the same day (2026-09-24: stale vendorHash) — forward-pin
  to the first green rev and say so in the commit
  (docs/lessons/operating.md). The webphone binary has no `--version`
  flag; its version is the store path name (e.g. webphone-2.7.0) —
  upstream tags trail the version literal (they trailed at v2.6.0 once;
  v2.8.0 was tagged 2026-09-30 — run `git tag` in the webphone checkout
  before citing tag state), so
  cite revs, never "webphone >= X.Y".
- The webphone RELOCK RITUAL is codified in docs/ops-runbook.md
  ("Lock-bump runbook" — read it there): binary build first, fast
  gates, webphone suites, browser E2E on markup/bundle deltas, then a
  HAND-AUTHORED commit naming old→new revs and the why (daemon
  heuristic messages on lock moves are how the 2026-09-24/25 breakages
  landed unattributed). Upstream build CI landed 2026-09-29 (build +
  go tests on push, first run green) — it proves a rev builds, but
  this repo's suites remain the integration gate. `nix flake update
  --dry-run` is not a flag on this nix; check freshness per-input with
  `gh api repos/<owner>/<name>/commits/HEAD`. Proven at scale
  2026-10-01 (67-commit jump, f706575, first try green — commit
  d8bd34c): minimize the relock→commit window, the daemon swept the
  lock mid-ritual twice; pre-check the DOM-contract selectors in
  upstream .templ files BEFORE the browser E2E (the contacts revert
  6989b99 kept the scratchpad — the E2E survived only because the
  selectors were verified first); probe evidence for reports comes
  from the suites' own asserted curls (greppable in `nix log`), never
  from ad-hoc VM sessions; `git show <rev>:<path>` (not worktree
  reads) is the first-choice tree inspection; never write reconstructed
  counts into durable docs — label reconstructions as reconstructions.
  The GitHub `flake-update` bot refreshes every top-level input EXCEPT
  webphone since 2026-10-03 (ritual-gated; a blind bump would fail its
  own PR's lock-guard) — it is never a webphone sweep source, and its
  PR needs the owner toggle "Allow GitHub Actions to create and approve
  pull requests" (Settings → Actions → General; the Sep/Oct 2026 runs
  died on the missing toggle and an infra kill; a stale
  `chore/flake-update-2026-09` branch lingers on origin).

## Conventions

- **One home per fact**: README sells, FEATURES inventories status,
  TODO_LIST holds open work, CHANGELOG logs history, DOMAIN_LANGUAGE
  defines vocabulary, this file keeps session-durable knowledge with
  long-form lessons in docs/lessons/. When a fact moves, delete it from
  its old home in the same commit — never maintain two copies. Done work
  is deleted from TODO_LIST, never struck through; `checks.docs-drift`
  (tests/drift_alarm.py) enforces this by failing when a TODO row
  duplicates a FULLY_FUNCTIONAL FEATURES row, cites ANY docs/status/ or
  docs/planning/ snapshot (archived or not) as evidence, or cites a
  repo-relative path missing from the tree (`--self-test` runs the
  negative tests for every arm). Status reports and plans under `docs/` are
  point-in-time snapshots: annotate, never rewrite — once every item
  in one carries an inline resolution marker (`~~…~~ done at` /
  `Won't implement` strikes or `→ done/open/…` routed arrows in markdown;
  `<del>` tags in the HTML-era snapshots), `git mv` it to
  `docs/status/archived/` or `docs/planning/archived/`. Marker
  convention (recorded 2026-09-29 after the retro sweep): per-item
  verdicts scope to the open-work sections (§b/§c/§f/§g); §a/§d/§e
  stay bare (achievements/process reflections). Planning snapshots:
  `## Step 2` M-tables are scoped like open-work sections (wired into
  `scripts/markers_check.py` AND `checks.markers-check` 2026-09-30),
  while `## Step 3` fine rows stay bare by the inheritance-note
  convention. An UNSTRUCK row with
  a routed `→ open`/`→ routed` verdict beats the row-uniformity
  heuristic — check-rows "CLEAN row in a struck table" warnings on
  open rows and PARTIAL rows carrying done+open-remainder verdicts are
  the accepted house style; a stale marker gets a `→ corrected`
  append, never a rewrite. The gate also runs a git-history
  monotonicity arm (2026-09-30): an archived snapshot's verdict-marker
  count may never permanently decrease — a decrease that no later
  commit repairs back to the historical peak is a finding, and the
  remedy is the same restore-by-append (count recovery clears it; the
  arm reads the working tree for its newest point and auto-skips
  outside a git repo, so `checks.markers-check` proves it via
  synthetic-repo self-test arms). The arm exists for the formatter
  incident class: prettier turns a line-start `~~~` into a CommonMark
  fence and mangled an archived strike tail that way (2026-09-30,
  repaired in place) — keep strike content fence-immune. Every newly
  archived snapshot also gets a
  `check-rows` uniformity pass in the same session that archives it.
- Cite stable names (option names, package/file names), not `file:line`
  — line numbers rot on every edit.
- Options: every `mkOption` has `type` + `description`; secret options come
  in plain/`*File` pairs with exactly-one-of assertions.
- Generated XML lives in `modules/freeswitch.nix` (pure function, no module
  system); `modules/telephony/` owns options and service wiring
  (`options.nix` interface, `pbx.nix` FreeSWITCH + secrets splice,
  `messaging.nix` Telnyx messaging bridge, `web.nix` nginx + webphone
  service wiring + config.js, `edge.nix` coturn
  - firewall, `shared.nix`
    derived values as a plain function — sibling bindings inside its returned
    attrset are NOT in scope for each other; define cross-referencing values
    in the `let`).
- Domain vocabulary lives in `docs/DOMAIN_LANGUAGE.md`; feature status in
  `FEATURES.md`; next work in `TODO_LIST.md`.
- Tests assert real behaviour (`fs_cli` queries, an `originate loopback/9196`
  call through the dialplan, nginx/coturn ports), not just unit states.
  KVM-less TCG variants need `pkgs.testers.runNixOSTest` + `requiredFeatures`
  (legacy `nixosTest` rejects the argument); template scripts with
  `pkgs.replaceVars` (`substituteAll` is gone). The browser E2E lives in
  `legacyPackages.telephony-browser`, deliberately outside `checks`.
