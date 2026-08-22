# Status Report: nix-ssh-config Integration (2026-08-22 05:06)

> Point-in-time snapshot of the session that integrated `../nix-ssh-config`
> into this flake. Written immediately after the work, including the honest
> self-review. Annotate, never rewrite.

## Mission

"Integrate ../nix-ssh-config/" — bring the hardened, post-quantum SSH
modules of the sibling flake into this telephony stack, end to end:
input, wiring, demo-host ops story, VM-tested proof, docs.

## Session commits (auto-commit daemon landed these during the run)

| Commit     | What                                                          |
| ---------- | ------------------------------------------------------------- |
| `e873418`  | feat(pbx): hardened SSH server with tracked operator keys     |
| `cc94cc5`  | test(ssh): NixOS VM test for the hardened SSH integration     |
| `2c3285b`  | docs(ssh): document the nix-ssh-config integration            |
| `d8eafcf`  | test(ssh): define testuser group (NixOS does not auto-create) |
| `533e2db`  | refactor(tests): configurable freescript unit wait timeout    |
| `34d8770`  | fix(ssh): close keyboard-interactive PAM password hole        |
| `8a94e5d`  | docs(ssh): clarify keys-only disables keyboard-interactive    |

Plus (this report session): stale-doc fixes to `tests/common.nix` header
and the FEATURES.md CI row.

## a) FULLY DONE

1. **Flake input**: `nix-ssh-config` added with `inputs.nixpkgs.follows =
   "nixpkgs"` (single nixpkgs in the closure); `flake.lock` pinned at
   `6bd1107` — the exact rev that was synced to the upstream GitHub
   remote at integration time (verified via `git ls-remote`).
2. **Host wiring**: `nixosModules.ssh` wired into `nixosConfigurations.pbx`
   (in flake.nix, where `inputs` are in scope — hosts/pbx stays
   input-free, matching the architecture convention) with:
   - `authorizedKeys = builtins.attrValues sshKeys` (tracked operator keys)
   - `allowRootLogin = true` — demo-only convenience, documented in three
     places (flake comment, README Security, FEATURES)
   - `extraSettings.KbdInteractiveAuthentication = false` — see (d)
3. **Demo VM ops path**: host port 2222 forwarded to guest 22; console
   banner teaches `ssh -p 2222 root@localhost`.
4. **New VM test suite** `checks.telephony-ssh` (`tests/ssh.nix`), green:
   - effective config via `sshd -T`: keys-only (password AND
     keyboard-interactive off), no root login, `mlkem768x25519-sha256`
     kex first, AEAD-only ciphers, ETM-only MACs, X11/TCP forwarding off,
     MaxAuthTries 3, banner present on disk
   - behavioural: real ed25519 key login that negotiates the ML-KEM
     hybrid kex (asserted from client `-vv` output)
   - denial: server offers ONLY publickey (password attempt gets
     `Permission denied (publickey)`); root refused with a valid user key
   - co-boot: the full telephony stack boots next to sshd
5. **Demo VM builds**: `nix build .#nixosConfigurations.pbx.config.system.build.vm` OK.
6. **Full gate**: `nix flake check` passed (all checks incl. statix,
   deadnix, pre-commit/gitleaks, format). `nix fmt` clean.
7. **Docs updated** (one-home-per-fact): README (What-you-get, Quick
   start, integration snippet with the kbd-interactive caveat, Security,
   layout), FEATURES (new "Host integration" section + suite list),
   CHANGELOG (Unreleased/Added), AGENTS (SSH integration gotchas),
   ops-runbook (sshd in the service inventory).

## b) PARTIALLY DONE

1. **CI verification**: local gate green, but nothing pushed — GitHub
   Actions has never run `telephony-ssh`. FEATURES.md says so honestly
   now (the "all four suites" claim was corrected to distinguish).
2. **aarch64**: the new check exists on aarch64-linux via `perSystem`
   but was never evaluated there (`nix flake check` omitted incompatible
   systems; `--all-systems` not run). Consistent with the repo's
   pre-existing aarch64 TODO, but now also true for the SSH suite.
3. **Other VM suites**: cache-validated, not re-executed after the
   integration (their derivations unchanged — shared fixtures untouched
   — so Nix legitimately skipped them). The claim "all checks passed"
   rests on that caching logic, which I verified by derivation identity
   but not by re-running.

## c) NOT STARTED

1. **Home Manager client module** (`homeManagerModules.ssh` /
   `ssh-config.*`) — only the NixOS server side is integrated. Operator
   workstation client config (hosts, PQ client defaults) untouched.
2. **Upstream feedback loop** — the kbd-interactive finding (below)
   invalidates nix-ssh-config's advertised "keys only" default for NixOS
   consumers; no issue/PR filed upstream.
3. **Host-side demo smoke test** — never booted `nix run .#vm` to prove
   `ssh -p 2222 root@localhost` from the host with a real key (guest-side
   sshd behaviour is proven; the QEMU forward itself is not).
4. **Runbook depth** — sshd added to the service inventory only; no SSH
   health-check line, no key-rotation procedure, no deploy-over-ssh notes.

## d) TOTALLY FUCKED UP (then fixed — root causes kept)

1. **The big one — `PasswordAuthentication no` is NOT keys-only on
   NixOS.** The upstream module ships exactly that claim, but NixOS's
   default `KbdInteractiveAuthentication yes` + `UsePAM` let
   keyboard-interactive prompts accept Unix account passwords. On our
   demo VM root carries an `initialPassword` — a real hole. Found only
   because the denial-path test printed `Permission denied (publickey,
   keyboard-interactive)` and I read it instead of pattern-matching
   "denied". Fixed downstream via `extraSettings.KbdInteractiveAuthentication
   = false` (both wiring and test); upstream module left untouched — its
   defaults are its maintainers' call.
2. **`ssh-keygen -N ''` inside the Nix indented testScript string** —
   the `''` terminated the Nix string; baffling `syntax error, unexpected
   '>'` pointing at an unrelated later line. Two builds wasted across the
   session (this and the casing bug). Lesson captured in AGENTS.md.
3. **Wrong assertion casing** — `sshd -T` prints canonical mixed-case
   directives; my lowercase asserts failed on first run. Fixed with
   `.lower()`.
4. **`install -g testuser` failed** — NixOS does not auto-create a
   matching group for `users.users.<name>` without a uid. Declared
   `users.groups.testuser`.
5. **Self-inflicted doc rot (found in this retrospective)**: I updated
   the per-component suite row but left the CI row saying "all four
   suites", and forgot `tests/common.nix`'s header list — both fixed in
   this session's tail commits.

## e) WHAT WE SHOULD IMPROVE

1. **Read assertion output before pattern-matching it.** The
   kbd-interactive catch was pure luck of careful reading; make
   "assert exact server-offered method list" the standard denial test
   (it is now, keep it).
2. **Nix string hygiene in testScripts**: any `''` in embedded shell is
   a landmine. Consider a lint (grep testScript blocks for `''` outside
   escapes) or a convention to always use `\"\"`.
3. **Upstream contract testing**: when consuming a sibling flake that
   advertises security defaults, encode the advertised claim as a local
   test — that is exactly what caught the hole. Do this for every
   security-relevant claim we depend on.
4. **Cheap eval-checks for host wiring**: the pbx host's sshd settings
   were only eval-verified manually in this session; a no-VM
   `nixosConfigurations.pbx` eval check would guard the wiring
   permanently.
5. **Doc-row coupling**: suite-list mentions live in common.nix header,
   FEATURES rows, README layout, AGENTS — five homes for one fact. A
   single "test suites" source (README Development section) referenced
   elsewhere would reduce the rot I caused.

## f) NEXT (ranked, ~30 real items, not padded to 50)

**Verify / close the loop**
1. Push and watch CI run `telephony-ssh` on GitHub Actions (needs user
   go-ahead — I never push unprompted).
2. Boot `nix run .#vm`, `ssh -p 2222 root@localhost` with a real tracked
   key; confirm banner + PQ kex from the host side.
3. `nix flake check --all-systems` (or `--system aarch64-linux`) to
   eval-verify the new check on aarch64.
4. Update TODO_LIST.md from this report's decisions.

**Upstream (nix-ssh-config)**
5. Verify-then-file: kbd-interactive default undermines "keys only" on
   NixOS — issue or PR defaulting `KbdInteractiveAuthentication false`.
6. Upstream: its README "X11 and TCP forwarding disabled" — but
   `AllowAgentForwarding yes` and `AllowStreamLocalForwarding yes`
   remain; decide and document stance (possible second PR).
7. Mirror a kbd-interactive regression test into nix-ssh-config's own
   suite.
8. Consider `nix flake update` cadence for the input (lock is pinned at
   a verified rev; decide bump policy).

**Hardening posture (this repo)**
9. Per-user key authorization instead of global `/etc/ssh/authorized_keys`
   (least privilege: today the tracked keys open EVERY account incl.
   root — intended for the demo, questionable for real deployments).
10. `allowUsers` on real deployments (option exists, unused here).
11. fail2ban / sshguard in front of an exposed 22.
12. Document host-key persistence for non-tmpfs deployments (NixOS
    generates on first boot; demo VM regenerates per boot — fine, but a
    real host section should say so).
13. Add `HostKeyAlgorithms` + `permittunnel no` + `ClientAlive*`
    assertions to tests/ssh.nix (settings the module sets but the test
    doesn't pin yet).
14. Run `ssh-audit` against the VM once; triage findings.
15. Watch ML-DSA (post-quantum signatures) upstream availability.

**Tests**
16. Cheap eval-check derivation asserting the pbx host's
    `services.openssh.settings` (no VM, catches wiring regressions).
17. Optional second test node with `allowRootLogin = true` proving the
    demo host's positive root-key path (currently only the denial side
    is tested; the positive path exists only on the unbuilt-in-CI host).
18. Assert the pre-auth banner is actually delivered to a denied client.

**Docs / DX**
19. ops-runbook: SSH health check (`systemctl is-active sshd`,
    `ss -ltn 'sport = :22'`).
20. ops-runbook: operator key rotation procedure (rotate sshKeys
    upstream → `nix flake update nix-ssh-config` → rebuild).
21. README deploy section: `nixos-rebuild --target-host` now requires a
    tracked key (password deploy is dead by design) — say so explicitly.
22. README architecture Mermaid diagram: add the sshd box.
23. Consider a single canonical "test suites" list (see improvement 5).
24. CHANGELOG: cut a release (tag vX.Y.Z + `gh release create`) once CI
    green — the Unreleased section is substantive.

**Client side (not started, decide appetite)**
25. Integrate `homeManagerModules.ssh` for operator workstations
    (client PQ defaults, host aliases for pbx hosts).
26. Publish the PBX host alias (`ssh-config.hosts.pbx`) pattern in the
    README once 25 exists.

**Housekeeping**
27. The pre-existing TODO_LIST "Verify CI green directly (gh run list)"
    item overlaps with item 1 — merge them when doing it.
28. `tests/__pycache__` and `.pytest_cache` exist in the tree (look
    gitignored — confirm nothing tracked).
29. Re-check `docs/status/2026-08-21_*` retrospectives for items made
    stale by this session (not done here — out of this report's scope).

## g) QUESTIONS (cannot be answered from the repo)

1. **Upstream kbd-interactive fix**: do you want me to file the issue/PR
   against `LarsArtmann/nix-ssh-config` (defaulting
   `KbdInteractiveAuthentication = false`, since its README advertises
   "keys only")? It changes upstream defaults — your call as owner.
2. **Demo posture**: keep `allowRootLogin = true` on the demo VM, or
   switch the ops story to a mortal user + sudo (closer to what a real
   deployment should look like)?
3. **Push/release**: should I push main now so CI exercises
   `telephony-ssh`, and do you want the CHANGELOG cut as a tagged
   release once it's green?

## State at report time

- Working tree: the two stale-doc fixes from this retrospective
  (common.nix header, FEATURES CI row) staged for the daemon; everything
  else committed through `8a94e5d`.
- Local gates: `nix flake check` green, `nix fmt` clean, demo VM builds,
  `telephony-ssh` VM test green (47 s).
- Remote: not pushed (by design — awaits instruction).
