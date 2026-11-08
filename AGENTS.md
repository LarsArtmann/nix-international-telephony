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
the runbook's "Passkey surfaces"). The Gemini voice agent
(`services.telephony.agent`, `modules/telephony/agent.nix`) answers
designated DIDs and drives the call over the event socket — system prompt

- API key as runtime files, per-DID language selection, health watchdog,
  VM-proven (`tests/agent.nix`, check `telephony-agent`). **No
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

The call-history index (pbx-lens, extracted 2026-10-11) rides the same
pattern: a flake input's Go binary plus THIS repo's module
(`modules/telephony/lens.nix`, `services.telephony.pbx-lens.*` — service,
credentials, poll cadence, backup staging, retention purge). Unlike the
webphone it ships NO NixOS module of its own; the wrapper only defaults the
package. Read-only over the stack's sources (CDR CSV, webhook JSONL,
transcripts); the index DB is disposable and re-derivable, so the module
registers only `state.*` paths and staged snapshots for the backup tool.
The package is honestly `licenses.unfree` (proprietary repo) and stays
consumable only because UPSTREAM re-instantiates its locked nixpkgs with
`allowUnfree` for its own package output (A/B-proven 2026-10-28: without
that instance, THIS flake's eval of `inputs.pbx-lens.packages.*.default`
refuses on the unfree license) — an unfree-license eval error at a future
pin is an upstream bug, not a gap here.

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
gh run view <id> --json headSha,status,conclusion,event,jobs && gh run list -b main --limit 3  # airtight CI verdict: a canceled run is GitHub infra, not code (2026-09-26/29 reds were that). Infra-kill variants: "The operation was canceled" mid-eval AND step exit 143/SIGTERM (2026-09-30 ledger: 10 consecutive x86 kills, aarch64 green throughout, protocol capped at 3 reruns — beyond that it is an owner/support lane). RECLASSIFIED 2026-10-06: the Oct-1→5 22-run cancelled stretch was NOT infra — the cross-arch `--all-systems --no-build` step outgrew the 60-min job timeout (one nix process evaling ~140 derivations across both arches degrades from ~0.2s to ~7min/check; 63/70 checks done at the last kill); fixed by the per-system eval split + 120-min budget in ci.yml. A cancelled run now needs the job-log step timestamps read before calling it infra
python3 scripts/markers_check.py          # per-item marker gate over archived snapshots + git-history verdict-count monotonicity arm (--self-test covers both); ALSO wired as checks.markers-check
python3 scripts/lock_guard.py             # tracked-input lock-move attribution gate (flake.lock webphone + pbx-lens revs must appear in CHANGELOG.md; --self-test seven arms, incl. per-input independence); ALSO wired as checks.lock-guard — a webphone/pbx-lens relock without a CHANGELOG rev mention fails CI
python3 -m unittest tests.test_telnyx_bridge tests.test_telnyx_reconcile tests.test_operator_sms tests.test_voice_agent tests.test_voice_agent_e2e tests.test_markers_check  # 344 stdlib tests (re-derived 2026-11-07; `python3 scripts/doc_counts.py` and the wired `checks.doc-counts` gate re-derive — count drift fails the flake check now): messaging-bridge contracts (SMS/MMS + WhatsApp lane incl. string-`to` statuses + 16 MiB cap) + Telnyx reconciler engine (incl. the WABA report lane and the number-level inbound-recording lane) + operator SMS-store flattening + the Gemini voice agent (Interactions-API request shapes verified against ai.google.dev primary docs + OpenAPI spec, ESL client, call loop) + the agent's behavior/E2E specs (tests/test_voice_agent_e2e.py: real-socket ESL peer + real Gemini HTTP stub through Agent.run_forever, and the main() FATAL credential branches in a subprocess) + the marker-gate regression suite (tests/test_markers_check.py: markers_check + rendering_audit arms, ID-header regression, per-item evasion class, incident triangle)
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
the pre-commit battery is their home. `buildflow doctor` findings are
PATH-dependent: missing-tool advisories fire or clear depending on the
calling shell's PATH, so run doctor inside `nix develop` (where the
pinned lint binaries live) before trusting either polarity of a
missing-tool finding.

Pre-commit hooks (nixfmt, gitleaks, changelog-headings, scrub-check,
lock-move-guard at commit-msg) are wired through git-hooks.nix: `nix
develop` installs them into `.git/hooks/pre-commit` and
`.git/hooks/commit-msg` and regenerates `.pre-commit-config.yaml` as
a store symlink (gitignored — never commit it). Run without a shell:
`nix develop -c pre-commit run --all-files`.

CI: GitHub Actions (`.github/workflows/ci.yml`) runs the same
`nix flake check` on `ubuntu-latest` (a udev rule opens `/dev/kvm` for the
NixOS VM test). Releases: update CHANGELOG.md, tag `vX.Y.Z`, then
`gh release create vX.Y.Z`.

## Catalog export (EventCatalog, added 2026-11-06)

`scripts/export-catalog.py` renders THIS repo's share of the architecture
catalog that `eventcatalog-hub` federates (catalog.home.lan): the inbound
call routing model, as one domain fragment (`telephony` — it joins the
pbx-lens domain by membership union, so the union keeps one body while the
`services:` list grows), three services (`pbx`, `pbx-voice-agent`,
`pbx-voicemail`), six call events each with a JSON Schema, two flows
(`inbound-call-routing` and `inbound-call-unrecorded-loss` — the second
documents the missing agent→voicemail edge, deliberately), and one proposed
ADR (`call-routing-layering`: mailbox floor, agent ceiling).

```bash
python3 scripts/export-catalog.py --selftest        # golden test, no repo needed (wired as checks.catalog-export since 2026-11-08)
python3 scripts/export-catalog.py -o /tmp/ec        # render the tree
python3 scripts/export-catalog.py -o /tmp/ec --check # exit 1 if stale
```

Rules that are easy to break and expensive to debug:

- **Never hand-write catalog content into the hub.** Its content dirs are
  generated and wiped by `build.sh`; a source repo's exporter is the only
  durable path.
- **The hub lints each source IN ISOLATION** (`owner-required`,
  `summary-required`, `refs/file-exists`, `structure/duplicate-resource-ids`
  are errors; `refs/resource-exists` is a warn). That is why every resource
  carries an owner and a summary, every `schemaPath` file is emitted, and
  every ref in this tree points at a resource this tree also emits.
- **`version` is 1.0.0 by contract** (lockstep with the hub's
  `render-inventory.py`). `services/pbx` deliberately reuses the platform
  inventory's id: an authored body wins over the derived inventory stub,
  while its deployment badge unions through.
- **Shared ids mean agreed identity.** The `telephony` domain's summary must
  match pbx-lens's text; a third distinct summary deepens a finding the
  hub's collision baseline already carries.
- The hub consumes this tree only after the exporter is pushed: the Forgejo
  mirror `lars/nix-international-telephony` is what CI clones, so a local
  commit that is not pushed is invisible to the catalog.

## Stack conventions (mirrors SystemNix)

- **flake-parts** (`mkFlake { inherit inputs; }`): `flake = { nixosModules,
  nixosConfigurations }` at the top; `packages`/`checks`/`devShells`/`treefmt`
  in `perSystem`. Use `self'` inside perSystem, `self` only outside.
- **treefmt-nix** flakeModule provides `formatter` + `checks.format`.
- **statix + deadnix** as treefmt programs (since 2026-10-07 — the
  standalone `checks.statix`/`checks.deadnix` are gone; treefmt's
  `checks.format` runs them): `repeated_keys` stays disabled because
  `services` is deliberately split across mkIf blocks. `statix.toml`
  returned 2026-10-12 as a single `disabled = ["repeated_keys"]` line:
  direct `statix check` (and buildflow's statix step) default `--config .`
  and read it from cwd — without it they ignore treefmt's disabled-lints
  and exit 1 on ~20 mkIf-split findings; only `disabled` is load-bearing
  (ignore/nix_version proven inert before the retirement).
- After adding files, `git add` them: with a git repo, the flake source is the
  git tree — untracked files are invisible to `nix build/check` (this bit us:
  a stale cached source copy made statix.toml appear missing).

## Git-tree flake visibility (proven 2026-10-08, experiment-driven)

- **Untracked files are INVISIBLE to flake evals** — an import of an
  untracked file fails, and nix itself prints the fix
  (`git add <file>`). `git add -N` (intent-to-add, nothing staged) is
  enough to make it visible.
- **Dirty TRACKED content IS visible immediately**: an uncommitted edit
  to a tracked file moves the evaluated drvPath on the next eval (no
  commit needed for CONTENT, only for NEW files). Proven by the
  telephony-eval drvPath A/B/A probe (czyz3r23 -> w0599i1 -> czyz3r23).
- **A clean-tree `nix flake check` failing `path 'X.drv' is not valid`
  is the EVAL CACHE serving a GC'd input derivation**, not a source
  problem: rerun with `--no-eval-cache` (it re-instantiates the missing
  .drvs) before suspecting the tree. Same class as pbx-artmann's
  `nix-fresh-cache*` incidents — the historical "dirty-tree behaves
  inconsistently" observations were almost certainly this cache, not
  the fetcher.
- **The eval cache can green-light a SUITE against the WRONG pin —
  proven both directions (2026-11-07).** Gate-4 anomaly RESOLVED: the
  2026-10-28 webphone suite green at `5f331e6` (while the binary
  demonstrably served the new `agent` key the suite's exact-key-set
  assert rejects) was the cached 814fdb5-era check derivation;
  rerunning the suite at the `be53c99` base with `--no-eval-cache` is
  RED at the `configjs_check.py` key-set assert, exactly as the pin
  honestly should be. No ordering bug exists. Corollary: any suite
  verdict that predates a lock move needs the `--no-eval-cache`
  rerun before it counts (the runbook's post-move note encodes this);
  and an intermittent "path ... is not valid" during CI's parallel
  check eval on a cold store is the same family — raw addToStore'd
  sources from a non-flake nixpkgs re-import losing the race (fixed
  in ci.yml 2026-11-07: serial pre-force + --no-eval-cache).
- **drvPath A/B across flake.nix edits: the plan-era "impossible" claim
  was WRONG, proven 2026-11-08.** vm-test-run derivations (and every
  value-level check) are STABLE under flake.nix edits — the derivation
  inputs are evaluated values (store paths, strings), not the flake
  source. Only derivations embedding `${self}` move on any tree edit
  (format/treefmt, doc-counts `src = self`, docs-drift, markers-test,
  rendering-audit, pre-commit). So the strongest possible refactor
  proof is per-check drvPath byte-equality (covers tester, args, nodes,
  testScript at once) — capture attrNames + drvPaths before, diff
  after, expect only the self-embedding set to move. (Gotchas learned
  the same day: `nix eval .#checks...<suite>.testScript` does NOT work
  — the testers passthru hides testScript behind a self-recursive
  `.test`; eval the suite module import directly instead. And forcing
  `config.assertions` messages can crash on lazily-null interpolations
  — some passing assertions' messages interpolate null values NixOS
  never forces; fingerprint assertion PREDICATE booleans instead.)

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
  hits count REMOVALS too — check the diff direction before treating a
  hit as a leak. Sweep forensics (2026-10-03): the daemon
  (`projects-management-automation`) only stages, commits and PUSHES —
  it never runs nix; the flake.lock UPDATE sweeps are unidentified
  LOCAL `nix flake update` executions (lock-guard remains the only
  gate). Sweep forensics ROUND 2 (2026-11-07): the 11-05 sweeps
  (abbe2de 02:00, 71ed5eb 21:19) moved the TRACKED inputs too
  (webphone, pbx-lens, plus git-hooks-nix and nixpkgs in one commit) —
  the sweeps are not leaf-input-only, they relock everything, so any
  of them can import a broken webphone/pbx-lens rev (the 10-28
  `edf2c3f` class); the nix-daemon journal at the 21:19 window shows
  the executor runs as user `lars` through ordinary daemon connections
  during active-session minutes — consistent with a concurrent session
  (human or agent) running a bare `nix flake update`, with the daemon
  lane only COMMITTING the result; identifying WHICH lars process needs
  per-process audit instrumentation (auditd or a nix wrapper) = owner
  lane; until then lock-guard + the commit-msg tripwire remain the
  only gates and every sweep still needs its attribution healed. Push
  evidence (2026-10-05): "unpushed, so soft-reset and
  re-author" is a RACE, not a guarantee — after a reset, re-author
  immediately, expect remote shards to appear, recover via rebase,
  never force-push. The daemon can land a heuristic commit SECONDS
  after an edit: when both commits are yours and unpushed,
  `git reset --soft` and re-author (race mechanics:
  docs/lessons/operating.md). A pattern-flagged DID literal remains in
  PUSHED history (a0c78ca, landed through the 2026-10-02 hook gap) —
  history surgery is an owner decision; never write the literal into
  new files.
- nix registry pinning needs BOTH halves (ops.nix): `nix.registry.nixpkgs
  .to = pkgs.path` alone is not enough — nix eagerly fetches the global
  flake registry for any indirect ref and a failed fetch ABORTS lookup
  even when the local entry matches; `nix.settings.flake-registry = ""`
  disables it. Never let a VM test hash a path flake (tree walk →
  virtiofsd fd exhaustion); assert via `nix registry list` +
  `test -f <path>/flake.nix`. Long-form: docs/lessons/operating.md,
  docs/lessons/vm-testing.md.
- Pre-commit hook fragility: git-hooks.nix cannot heal a lost hook and
  `pre-commit install` refuses on the visible global `core.hooksPath`;
  the updater's update branch (fires after ANY tracked-file edit)
  used to strip ALL hooks and leave the repo ungated — the devShell
  shellHook now wraps the installationScript with
  `GIT_CONFIG_GLOBAL=/dev/null` and re-anchors local `core.hooksPath`
  (narrative + root cause: docs/lessons/operating.md, git-hooks.nix#754
  filed). `scripts/heal-pre-commit-hook.sh` heals hook-file loss
  outside an entry — a heal must install BOTH stages. The auto-commit
  daemon bypasses every hook structurally (go-git executes no hooks);
  only CLI commits are gate-guarded. The commit-msg stage
  (`lock-move-guard`, scripts/lock_move_hook.py) refuses any commit
  whose staged flake.lock moves a tracked input's rev (webphone,
  pbx-lens — keep in lockstep with lock_guard.py's TRACKED_INPUTS)
  without a `relock:` / `lock-bump` marker; runs always_run at
  commit-msg with the message file as $1 (a `files` filter would
  mis-match the msg path; pass_filenames=false would strip it) —
  CLI commits only; the daemon lane needs its guard inside pma/go-commit
  (owner lane, fleet-wide).
- Edit mechanics (5 recurrences 2026-08→09): match structurally (row-start
  prefixes, the annotator scripts' ID grammar) — never re-type full-line
  anchors. `git mv` fails deterministically on UNTRACKED files (write →
  `git add` → then `git mv`). Diagnose from the error text, never from a
  narrative — the 2026-09-29 "race" misdiagnosis shipped a false root
  cause into a commit message.
- VM probe mechanics (long-form: docs/lessons/vm-testing.md): pipes
  mask exit codes — run verdict probes with output to a file and read
  the rc after (`> /tmp/x.log 2>&1; RC=$?`), never `| tail` a probe.
  `systemctl show -p ExecStart --value` prints a property OBJECT on
  current systemd — extract the binary with `grep -o 'path=[^ ;]*' |
  head -1 | cut -d= -f2` (passkey suite pattern) or read
  `/proc/<MainPID>/exe`. VM guests read the QEMU `-rtc base=` as UTC:
  pinning `21:30Z` boots the guest at 21:30 UTC, which is 22:30 Berlin
  (demo-wallclock suite's one-assert lesson).
- BuildFlow noise is DECIDED (2026-09-16), not ambient. Load-bearing
  mechanics: bandit `# nosec` goes at the ISSUE line (findings
  attribute to the innermost call line; ruff-format rewraps);
  `tests/vulture_whitelist.py` holds the load-bearing references;
  `tests/` is a REGULAR package — the empty `tests/__init__.py` keeps
  unittest/pytest/mypy on the same `tests.*` names (deleting it
  reintroduces the pytest collection error and silently blocks mypy);
  the lint binaries are pinned in `devShells.default` (unpinned,
  buildflow falls back to the moving registry — the formatter
  version-skew class is excluded in `.buildflow.yml`); the
  github-actions pinning checker compares the `# vX.Y.Z` annotation
  against the latest release NAME, not the resolved SHA — keep the
  annotation current when bumping. The
  findings gate's green shape (budget/kill mechanics in the archived
  2026-10-07 triage report; upstream items BuildFlow#25–#28,
  nix-ssh-config#5, pma#341, git-hooks.nix#754): exactly 2
  error-severity nix-checker findings — the NAT 5060 tcp+udp
  sourcePort pair in tests/nat.nix — plus 4 infos (sounds.nix pinned
  hashes + hash.nix extraction suggestions); that IS green. The vulnix
  advisory class (~15, BUILD-closure toolchain derivations, not the
  deployed surface) and the flake-meta mainProgram advisory are
  accepted noise. `scripts/markers_check.py` is the standing marker
  gate (zero unmarked across all archived snapshots; negative
  self-test).
- Webphone consumer contracts moved by the 2026-10-27/28 sweeps
  (upstream 27adf4e et al.): `/config.js` gained the `agent` key (the
  M12 summarize-affordance flag — type-checked in
  `tests/configjs_check.py`; this stack wires no webphone-internal
  textagent, so it serves `false`), and ended call cards now PERSIST as
  `.wp-ended-card` with an explicit `.close-ended-btn` — they never
  auto-dismiss — so `tests/browser-e2e.py` drives `settle_and_close()`
  instead of waiting for cards to vanish. The textagent suite waits for
  webphone's HTTP port 8080 before bridge POSTs (the listener binds
  only after the read-model boot work; a unit-wait alone raced the
  first webhook into a bridge 503 under a loaded full check). The
  daemon can sweep the lock onto a BROKEN upstream rev (`edf2c3f`,
  2026-10-28: `review_api.go` agentAudit undefined, upstream CI mixed
  green/red) — the forward-pin rule applies with OUR gate-2 binary
  build as the decider, provable at the exact rev via
  `nix build github:LarsArtmann/webphone/<rev>#webphone` BEFORE the
  lock moves (zero daemon window on an unproven rev).
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
- Webphone adoption is AUDITED (docs/research/2026-10-25_webphone-deep-dive.html,
  supersedes 2026-10-01; index: docs/research/README.md): 80/100 (high),
  21/27 capabilities fully leveraged, 0 anti-patterns; open gaps by
  priority = the push seam (upstream's ring-while-closed waits on OUR
  dialplan hook — zero references here) and ASR transcription (owner
  provider decision). The same-evening execution closed timezone,
  state.paths, the owed ssoerror-delta browser E2E (green; the runner's
  chromedriver session-creation hang is watchdog+retry hardened), and
  the "OIDC SSO surfaces" runbook recipe. Refresh the audit when the
  push or ASR facade lands, or on the next webphone release tag.
- The webphone RELOCK RITUAL is codified in docs/ops-runbook.md
  ("Lock-bump runbook" — read it there): binary build first, fast
  gates, webphone suites, browser E2E on markup/bundle deltas, then a
  HAND-AUTHORED commit naming old→new revs and the why (daemon
  heuristic messages on lock moves are how the 2026-09-24/25 breakages
  landed unattributed). Since 2026-11-07 the ladder itself is
  scriptable: `scripts/relock-ladder.sh` runs gates 2–6 with per-gate
  verdict capture (tee'd logs + `NIX_EXIT`, verdict table for the
  commit message) — the manual bookkeeping is what produced the
  `5f331e6` CHANGELOG overclaim. Upstream build CI landed 2026-09-29 (build +
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
  The runbook's gate-5 clause carries the two load-bearing delta
  checks: the flake-signature paragraph (red-under-load is not
  attribution; prove the suite at the pre-relock base) and the
  auth-surface clause (seam scan, `/config.js` key set, login DOM
  selectors, `/phone-api` gate) — read both before ANY relock whose
  upstream delta touches `internal/web` or an auth seam.
  The GitHub `flake-update` bot refreshes every top-level input EXCEPT
  webphone since 2026-10-03 (ritual-gated; a blind bump would fail its
  own PR's lock-guard) — it is never a webphone sweep source, and its
  PR needs the owner toggle "Allow GitHub Actions to create and approve
  pull requests" (Settings → Actions → General; the Sep/Oct 2026 runs
  died on the missing toggle and an infra kill; a stale
  `chore/flake-update-2026-09` branch lingers on origin).
- Dynamic SIP directory (2026-10-12, SUPERB train): under
  `telephony.directory.mode = "xml_curl"` the `fs-directory.service`
  bridge answers sofia's directory lookups from webphone's derived
  per-session credentials (`GET /internal/directory/<ext>`, loopback +
  shared secret on an HTTP Basic wire — mod_xml_curl 1.11.1 SILENTLY
  IGNORES `auth-scheme=bearer`, verified in source; the bridge also
  accepts Bearer for probes); ANY bridge failure answers
  `<not-found/>` and sofia falls
  through to the static binding, which then carries ONLY
  `staticFallbackExtensions` — keep that set populated with everything
  that must survive a webphone outage (operator, ring groups). The
  bridge NEVER caches (revocation latency) and NEVER invents a
  credential. nixpkgs' FreeSWITCH omits `mod_xml_curl`; `pbx.nix`
  mirrors the default module list + `xml_int.curl` — re-diff that list
  when nixpkgs' set moves. Rollback = flip mode to `static` + switch
  (runbook § Dynamic SIP directory).

## Process rules (codified 2026-11-07 from the sweep-era postmortems)

**Gates and verdicts:**

- Gate FIRST after any nix/python edit (format + eval immediately —
  the daemon commits within minutes; batching gates after other
  verifications is how two of the 2026-10-26 commit races happened).
- Exit codes captured as reflex (`echo EXIT=$?`, `PIPESTATUS[0]`,
  redirect-then-`$?`); never `| tail` alone — an unpiped tail eats
  the status and the evidence (the 2026-10-07 battery discipline).
- Same-window changelog bookkeeping: the CHANGELOG entry is drafted
  BEFORE the verification that proves it, and lands in the same
  commit — a verdict written after the fact is the `5f331e6`
  overclaim class.
- Write verdicts into durable docs only after they exist (the
  2026-10-07 stash ritual held only because the commit was delayed).
- Read-only probe discipline: CI logs are for TRIAGE, local
  reproduction is for VERDICTS — prefer reproducing the failing
  artifact locally whenever it is reproducible.

**Lanes and probes:**

- Lane-probe before editing: `git status` + `ps aux | grep nix` at
  session start, and GREP the tree for twin implementations before
  minting a row or a fix — agent-reported routes are verified
  against the tree first (the vulture-whitelist near-miss: the file
  existed; the route was false).
- Grep-twins: diagnose from the error text, widen the grep scope
  before concluding absence (the dialplan_sim near-miss: the first
  grep covered only modules/tests and missed `packages/`).
- Proof tiers: session-proof < suite-green < airtight origin verdict
  (`gh run view` with step timestamps; a cancel is not a verdict) —
  claims in durable docs must name the tier they ride.

**Fleet and store hygiene:**

- Subagent concurrency: start ≤3 concurrent, stagger resumes, never
  re-burst into a draining fleet (six-at-once killed four on
  rate limits, 2026-11-07 round 11).
- Verification-neutral commit messages: heuristic daemon messages
  never carry verdicts or relock markers — every lock move and every
  CI-verdict claim rides a HAND-AUTHORED commit (lock-move-guard
  enforces the relock marker at commit-msg for CLI commits).
- `gh` default-repo context can drift mid-session (a sibling
  session's side effect was the 2026-10-01 suspect): pass `--repo`
  habitually, or `gh repo set-default` once per session when
  verdicts matter.
- Workflow-filter verdict rule: a run listing "success" for a
  commit can still be a phantom — check the run's EVENT and JOB LIST
  (the 2026-11-06 Dependabot-only phantom green; event `dynamic`,
  zero CI jobs).
- Treefmt race caution: `nix fmt` and a parallel nix build can
  interleave; run fmt BEFORE build gates, never concurrently.
- Status mtime scan: when hunting stale claims, `ls -dt` the
  snapshot dirs and READ the newest report before re-deriving facts
  from code (the as-found accuracy gap in round 11 came from
  three-week-old claims).
- Sweep-source instrumentation: unattributed `nix flake update`
  runs are an open incident class (six sweeps by 2026-10-07); any
  new lock move without a hand-authored commit gets attributed AND
  reported, not just repaired.
- `checks.lock-guard` FAIL shape: the gate's error names the input,
  both revs and the fix path — when it fails, the CHANGELOG is
  missing an attribution for a CURRENT locked rev; heal by appending
  to the existing entry, never by rewriting sections.
- Fresh-boot calibration: a suite green on a warm local store and
  red on a cold CI store is a STORE-STATE delta, not a code delta —
  reach for `--no-eval-cache` and the pre-force pattern before
  touching the check (the 2026-11-07 lens-eval race).

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
  convention: per-item verdicts scope to the open-work sections
  (§b/§c/§f/§g); §a/§d/§e stay bare (achievements/process reflections);
  planning `## Step 2` M-tables are scoped like open-work sections,
  `## Step 3` fine rows stay bare by the inheritance-note convention.
  An UNSTRUCK row with a routed `→ open`/`→ routed` verdict beats the
  row-uniformity heuristic (check-rows "CLEAN row"/PARTIAL warnings on
  such rows are accepted house style); a stale marker gets a
  `→ corrected` append, never a rewrite. The marker gates
  (`scripts/markers_check.py`, `checks.markers-check`) run the content
  sweep plus TWO git-history monotonicity arms — file-level (whole
  history) and per-item (post-archive revisions only) — where a
  verdict count that drops and is never repaired back to its peak is a
  finding; the remedy is restore-by-append (count recovery clears it);
  outside a git repo the arms auto-skip and the synthetic-repo
  self-test carries the proof. Rendering damage the marker gates
  cannot see is netted by `scripts/rendering_audit.py` (fence/strike/
  emphasis classes; keep strike content fence-immune). Full incident
  history, CommonMark mechanics, the pickaxe→follow mechanism
  deviation and the recovery-by-append grammar live in
  `docs/lessons/markdown-normalization.md` — read it before touching
  archived snapshots or the gates. Every newly archived snapshot also
  gets a `check-rows` uniformity pass in the session that archives it.
- Cite stable names (option names, package/file names), not `file:line`
  — line numbers rot on every edit.
- Options: every `mkOption` has `type` + `description`; secret options come
  in plain/`*File` pairs with exactly-one-of assertions.
- Generated XML lives in `modules/freeswitch.nix` (pure function, no module
  system); `modules/telephony/` owns options and service wiring
  (`options.nix` interface, `pbx.nix` FreeSWITCH + secrets splice,
  `agent.nix` Gemini voice agent, `lens.nix` pbx-lens index module,
  `messaging.nix` Telnyx messaging bridge, `monitoring.nix` health checks,
  `resilience.nix` backups + failure alerts, `security.nix` fail2ban jails,
  `fax-feed.nix` fax-to-webphone feed, `ops.nix` opsTools + nixpkgs
  registry pin, `web.nix` nginx + webphone service wiring + config.js,
  `edge.nix` coturn - firewall, `shared.nix`
  derived values as a plain function — sibling bindings inside its returned
  attrset are NOT in scope for each other; define cross-referencing values
  in the `let`. shared.nix owns the placeholder-token contract
  (`fsPlaceholder`) and the exactly-one-of secret predicate
  (`exactlyOneSecret`): every @TELEPHONY_*@ token and every plain/*File
  assertion derives from there; tests/eval.nix's literal needles are the
  INDEPENDENT verifier — do not "DRY" them onto the registry).
- `flake.lib.telephony.mkFreeSwitchConfig` exposes the pure XML
  generator without a nixosSystem; `checks.dialplan-sim` rides it to
  dry-run routing semantics in build-seconds (adding a routing lane =
  one fixture-aware row there, not a VM suite). VM suites ride the
  `plainSuites` table in flake.nix (one row: tester + file; the tester
  choice per row is load-bearing) — extra-arg suites stay explicit.
- Domain vocabulary lives in `docs/DOMAIN_LANGUAGE.md`; feature status in
  `FEATURES.md`; next work in `TODO_LIST.md`.
- Tests assert real behaviour (`fs_cli` queries, an `originate loopback/9196`
  call through the dialplan, nginx/coturn ports), not just unit states.
  KVM-less TCG variants need `pkgs.testers.runNixOSTest` + `requiredFeatures`
  (legacy `nixosTest` rejects the argument); template scripts with
  `pkgs.replaceVars` (`substituteAll` is gone). The browser E2E lives in
  `legacyPackages.telephony-browser`, deliberately outside `checks`.
