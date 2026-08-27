# Status Report: "Deploy for real" session (2026-08-27)

> Scope: this session only (07:30–10:19). Trigger: "What do we need to get
> this deployed for real?" — pareto plan, production host template,
> deployment runbook, gate, secrets-history scan. This report is honest
> self-criticism plus project state as left by that run; nothing outside it
> was re-audited.
>
> Format note: user explicitly requested `.md`; the status-report skill's
> HTML default was overridden.

**Verdict:** the repo-side deployment path is built and green
(`nix flake check` end-to-end, all pre-commit hooks pass, git history
provably secret-free). One real defect was discovered during this
self-review — **ACME mode cannot complete issuance on a default-firewalled
host because nothing opens port 80** — detailed in (d). Remaining work is
either that fix, doc truth-polish, or owner-gated (server/DNS/ITSP/secrets).
**Nothing is committed** (10 files staged/modified; see question 1).

## a) FULLY DONE (this session, verified)

| Item | Evidence |
| ---- | -------- |
| Pareto plan artifact `docs/planning/2026-08-27_07-34_real-deployment-readiness.html` (Bauhaus, inlined D2 SVG graph) | file written, badge classes verified against template |
| Production host template `hosts/pbx-prod/default.nix` (`nixosConfigurations.pbx-prod`) | full toplevel evals: `nix eval ...toplevel.drvPath` returns a real drv; `security.acme.acceptTerms = true`, vhost `pbx.example.com` with `enableACME`, `cdr.enable = true` spot-checked |
| flake.nix wiring for `pbx-prod` (telephony + ssh-server modules, root login off, kbd-interactive off) | evals; forced by `nix flake check` from now on |
| Deployment runbook `docs/deploy.md` (prerequisites, CHANGEME checklist, secrets provisioning sops/manual, 3 install paths, verify checklist, rollback, known gaps) | written; commands not executed (no target host — owner-gated) |
| README "Deploying for real" section + layout table; stale deploy hint in `hosts/pbx` header now points at `.#pbx-prod` | files edited |
| Docs hygiene: TODO_LIST (new BLOCKED first-deployment task, 0.2.0 scan prerequisite marked done), FEATURES (`pbx-prod` row, honestly PARTIALLY_FUNCTIONAL), CHANGELOG (Unreleased/Added), AGENTS.md (two-host model) | files edited, one-home-per-fact respected |
| Full gate: `nix flake check` — **exit 0, all VM suites + eval checks passed** (after fixing deadnix/statix findings in the new template) | log captured |
| gitleaks full-history scan: 96 commits, **0 real secrets**; all 5 hits inspected and individually dismissed (RFC 6455 sample nonce, `%{http_code}` curl format string, labeled VM-test fixture passwords) | report inspected line-by-line in history |

## b) PARTIALLY DONE

| Item | What exists | What's missing |
| ---- | ----------- | -------------- |
| `hosts/pbx-prod` as a deployable host | Template + flake output + eval guard + runbook | Never booted (no VM test, no real server). The CHANGEMEs (domain, disk, gateway, secrets) are unfilled — by design, they are owner inputs. FEATURES honestly says PARTIALLY_FUNCTIONAL |
| Pre-0.2.0 release hygiene | gitleaks history scan done (clean) | CHANGELOG cut, tag, `gh release create` still TODO |
| Deployment verification story | runbook §5 checklist + ops-runbook health checks | The checklist has never been executed against a real host; `nixos-anywhere`/`nixos-install` command shapes are unvalidated |

## c) NOT STARTED (deliberately, this session)

- Filling real deployment values (domain, DNS, disk, ITSP gateway, secrets) — owner-gated, tracked BLOCKED in TODO_LIST.
- sops-nix wiring in the example host — owner decision, docs-only recipe stands (`docs/secrets.md`).
- Any monitoring/alerting, fail2ban, backups (ROADMAP theme 1; listed in deploy.md known gaps so nobody is surprised).
- Browser-E2E RTP byte-flow assertion and CI promotion (pre-existing TODOs, untouched).

## d) TOTALLY FUCKED UP (honesty section)

1. **ACME mode + firewall: port 80 is never opened — first-boot certificate issuance fails on a default NixOS host.** Found during THIS review, not during the session (ACME cannot run in VM tests; the eval check proves wiring, not reachability). Chain: `tls.mode = "acme"` → nginx vhost `enableACME` (HTTP-01) → challenge must be served on **port 80**; `modules/telephony/edge.nix` opens 443/5060/5061/5080/3478 but **not 80**; NixOS `networking.firewall.enable` defaults true; nixpkgs' acme module does not open ports. Result: challenge times out → no cert → nginx SSL vhost dead → webphone/wss down (SIP parts still up). Compounding: `docs/deploy.md` §1 says "ACME needs ports 80 and 443 reachable" but its port table (what the stack opens) omits 80, so an operator following the table blocks it twice. Severity: blocks the exact scenario `pbx-prod` exists for. Not fixed — see questions 2/3 and next-task #1.
2. **Sloppy first flake edit:** I wrote `inputs.nix-ssh-config.niosModules.ssh or inputs.nix-ssh-config.nixosModules.ssh` — a typo'd nonsense fallback — and removed it one step later. Zero impact (caught before any build), but it should never have been typed.
3. **Two failed edits from guessing whitespace** (FEATURES.md table alignment; the `_:` swap in `pbx-prod`) — each cost a round trip because I didn't re-read the exact lines first. Rule violated: read before edit, copy exactly.

## e) WHAT WE SHOULD IMPROVE

- **Split-brain risk: two port tables.** `docs/deploy.md` §1 and `docs/ops-runbook.md` "Health checks" now both tabulate ports with different scopes (hoster-facing vs on-host listeners). They will drift. Make one canonical (runbook: listeners; deploy.md links to it and only adds hoster-firewall framing).
- **deploy.md imprecision:** "Five short random strings" — the table actually lists 4 mandatory + 2 optional; the SSH port 22 row is missing entirely (an operator could firewall themselves out); §5 uses `fs_cli "…"` without reminding file-mode operators how to get the password (`fs_cli -p "$(cat /run/secrets/telephony_event_socket)"`).
- **The `_:` module header in `hosts/pbx-prod`** satisfies statix but is unusual for a NixOS module file (`{ ... }:` convention, as in `hosts/pbx`). Harmless; noted for consistency.
- **No boot-level proof for the `pbx-prod` shape.** Eval-forcing is the right cheap guard, but a one-time boot smoke test (secrets stubbed via tmpfiles, tls overridden self-signed) would prove the template's unit graph starts on a non-QEMU host shape.
- **Plan/report HTML artifacts are never rendered-checked** — I verify classes/structure exist, not visual correctness. Acceptable, but say so honestly.
- **Session work is uncommitted** — 10 files staged/modified. My rules forbid committing unasked; the pareto/status skills ask for commits. Resolved by asking (question 1) instead of guessing.
- **ROADMAP open question 4 (deployment target) was not annotated** even though this session made it concretely gating (it decides whether the port-80 fix is urgent ACME work or LAN-first doc work).

## f) Next tasks (sorted by impact; brainstorm beyond ~10 is ROADMAP fuel)

| # | Task | Impact | Effort |
| - | ---- | ------ | ------ |
| 1 | Fix the ACME/port-80 gap: module opens 80 when `tls.mode = "acme"` + `openFirewall` (or explicit owner decision to document instead) | Critical | 30m |
| 2 | Extend `tests/eval.nix` to assert firewall port 80 in acme mode (regression guard for #1) | High | 20m |
| 3 | deploy.md truth pass: port 80 + 22 rows, exact secret count, `fs_cli -p "$(cat …)"` in §5 | High | 15m |
| 4 | De-duplicate the port tables (one canonical home) | Medium | 15m |
| 5 | Commit this session's work (10 files) — question 1 | Medium | 2m |
| 6 | First real deployment: server + DNS, fill CHANGEMEs, provision secrets, run deploy.md §5 checklist | Critical (gated) | 2h+ |
| ~~7~~ | ~~Annotate ROADMAP open question 4 with the session's outcome~~ done (docs-health pass 2026-08-27) | ~~Low~~ | ~~5m~~ |
| 8 | Boot-smoke VM test for the `pbx-prod` shape | Medium | 45m |
| 9 | 0.2.0 release: CHANGELOG cut, tag, `gh release create` | Medium | 45m |
| 10 | Validate `nixos-anywhere` / `nixos-install` command shapes on the real target (with #6) | Medium | 30m |
| 11 | Wire sops-nix into the real host when it exists (recipe is ready) | Medium | 30m |
| 12 | Monitoring: timer-driven health checks (runbook block) with alerts on profile/gateway down | Medium | 2h |
| 13 | fail2ban / rate-limiting for SIP scanners on 5060/5080 | Medium | 1h |
| 14 | Backups: recordings/voicemail/CDR are single-copy on-host | Medium | 2h |
| 15 | RTP byte-flow assertion in browser E2E (pre-existing TODO) | Low | 1h |
| 16 | Browser E2E CI promotion decision (pre-existing, owner) | Low | 15m |
| 17 | Emergency-calling provider research or stronger disclaimers | Low | — |
| 18 | IVR / conference / DISA options (ROADMAP theme 2) | Low | — |
| 19 | Voicemail-to-email (`vm-mailto`) | Low | — |
| 20 | Time-based routing per ring group | Low | — |
| 21 | DB-backed directory (mod_pgsql) for large extension counts | Low | — |
| 22 | 16 kHz sounds package variant | Low | — |
| 23 | Webphone i18n (de/en) | Low | — |
| 24 | IPv6 SIP profiles behind `ipv6.enable` | Low | — |
| 25 | Kamailio edge spike (defer until load) | Low | — |
| 26 | Upstream `services.telephony` toward nixpkgs | Low | — |

## g) Questions I cannot answer myself

1. **Commit?** All session work (10 files) is staged/modified but uncommitted — my standing rule is never to commit unless explicitly told. Say the word (one commit? split docs/code?) and it lands.
2. **Port 80 ownership:** should `services.telephony` open 80 in acme mode when `openFirewall = true` (consistent with the option's contract, my recommendation), or keep the firewall surface minimal and document port 80 as operator-owned in deploy.md?
3. **First deployment target** (ROADMAP open question 4): public VPS with ACME, or LAN-first with self-signed TLS? This decides whether the port-80 fix (#1) is the immediate next task or can ride behind the first real deployment — and which TLS path gets validated first.
