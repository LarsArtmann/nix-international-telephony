# Status Report: Production hardening & secrets (ROADMAP theme 1) execution (2026-09-18 15:25)

> Scope: this session only (~10:00–15:25). Trigger: user pasted ROADMAP
> theme 1 ("Production hardening & secrets") and asked for
> breakdown → execution → verification. Everything below was re-verified
> against the tree at 15:25; `nix flake check` was green at ~15:10
> (FLAKE-CHECK-EXIT=0, log: ~/.cache/suite-logs/flake-check2.log).
> Nothing outside this theme was re-audited.

**Verdict:** theme 1 is executed to its in-repo limit. The nginx/443
scanner jail and five deeper edge-verification asserts are shipped and
VM-proven; the security hardening guide exists; the remaining theme
items are owner-gated (live host) or refined into TODO_LIST work
(two-NIC NAT suite). The full CI gate is green.

## a) FULLY DONE (this session, verified)

| Item                                                                                          | Evidence                                                                                                                                                                                                                                                                                                                                                                      |
| --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| nginx/443 scanner jail: `services.telephony.fail2ban.nginxScanner` (default on with webphone) | `modules/telephony/security.nix` (jail + shipped filter), `web.nix` (access_log pinned to `/var/log/nginx/telephony-access.log` via `shared.nix` const); VM-proven: bot-path prober from 198.51.100.8 banned in `nginx-scanner`, localhost fetches and the SIP jail untouched (`tests/fail2ban.nix`, `checks.telephony-fail2ban` green)                                       |
| Event socket loopback-only assert (8021)                                                      | `tests/tls-turn.nix`: every 8021 listener must be 127.0.0.1; suite green                                                                                                                                                                                                                                                                                                      |
| Real TLS handshake on 5061 (not just a listener)                                              | `tests/tls-turn.nix` `openssl s_client` assert (cert presented, cipher negotiated); suite green                                                                                                                                                                                                                                                                               |
| Manual `tls.mode` runtime proof                                                               | new `manual` node in `tests/tls-turn.nix` with a generated fixture cert (CN=manual-tls.test); the vhost is validated by trusting EXACTLY the operator cert (`curl --cacert ... --resolve`); suite green                                                                                                                                                                       |
| RTP port-window enforcement assert                                                            | `tests/pbx.nix`: during a live SIP call every freeswitch UDP listener must sit in 16384-16584 or be 5060/5080 (column-drift-tolerant token parse); multi-node suite green                                                                                                                                                                                                     |
| wsprobe as suite assertions                                                                   | `tests/wsprobe.py --assert` mode (101+sip subprotocol, Via/WSS REGISTER → 401, PING→PONG, Via/WS dropped); wired into `tests/webphone.nix` (proxied + direct); suite green                                                                                                                                                                                                    |
| Security hardening guide                                                                      | `docs/security.md`: exposed-surface table, Hetzner Cloud Firewall → NixOS firewall → SIP-ACL layering, TURN exposure, SSH posture (per-user keys, rotation procedure, host-key persistence, ssh-audit triage), property→check provenance table, going-live checklist; linked from README docs index, AGENTS.md, ops-runbook                                                   |
| Docs churn (one-home rule held)                                                               | CHANGELOG [Unreleased] Security/Added/Changed; FEATURES (fail2ban row rewritten — incl. fixing its stale "watches the journal" claim — RTP range + manual TLS promoted FULLY_FUNCTIONAL, guide row added); ROADMAP theme 1 pruned with a shipped-summary; TODO_LIST (NAT two-NIC suite row; deploy lane extended with the live security pass); ops-runbook nginx-scanner note |
| Cheap gates + full gate                                                                       | `nix fmt` clean, pre-commit all-files clean (incl. gitleaks/scrub-check), eval/statix/deadnix/docs-drift/format green, then full `nix flake check` EXIT=0                                                                                                                                                                                                                     |

## b) PARTIALLY DONE

| Item                                     | What exists                                                                                              | What's missing                                                                                                                                             |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SSH posture / Hetzner firewall (theme 1) | Documented end to end in `docs/security.md` (incl. rule table, rotation runbook, ssh-audit expectations) | The live apply + one real `ssh-audit` run need the deployed host (owner-blocked deploy lane)                                                               |
| fail2ban filter regression guarding      | Filter VM-tested via the expensive suite                                                                 | No cheap eval-time `fail2ban-regex` check; a failregex regression costs a full VM run to notice                                                            |
| wsprobe.py lint coverage                 | bandit clean (`-q`, zero findings)                                                                       | vulture not runnable standalone here (buildflow-orchestrated; not in devShell/nixpkgs top-level) — new symbols are all referenced, risk low but unverified |

## c) NOT STARTED (deliberate, this session)

- **NAT two-NIC VM suite** (`natAddress` runtime proof): refined into a
  bounded TODO_LIST row (Medium/L) instead of built — right call for
  session scope, honest gap in FEATURES (row stays PARTIALLY_FUNCTIONAL).
- **turn.tls runtime validation**: documented as an eval-only gap in the
  new guide's provenance table; suite not built (ROADMAP theme 4 item,
  needs a real-cert story).
- **sops-nix wiring into an example host**: unchanged, owner-gated
  (ROADMAP open question 1 remainder).
- **Basic-auth failure jailing** (`/recordings/`, `/operator/` brute
  force): not modelled anywhere — the scanner filter deliberately only
  matches bot paths (see questions).

## d) TOTALLY FUCKED UP (honesty section)

1. **fail2ban failregex shipped unverified and took THREE VM runs
   (~25 min) to converge.** The killer detail: fail2ban strips the
   matched date region from the line before applying failregex, so my
   `\[[^\]]+\]` timestamp span could never match. I own the tooling
   knowledge (`fail2ban-regex` exists, I used it — but only AFTER two
   red suites). Rule going forward: every hand-written failregex gets a
   5-second `fail2ban-regex` probe against a sample line BEFORE any VM
   run. Same class as py_compile-first.
2. **Re-committed the exact trap an adjacent comment warns about.** The
   freeswitch-sip jail's `ignoreself = false` carries a comment
   explaining loopback-source skipping; I wrote the new jail without it
   and burned a third suite run. Diagnosed only by inserting a
   diagnostics block (`Ignore 198.51.100.8 by ignoreself rule` in the
   fail2ban journal). Reading a warning ≠ applying it to new code.
3. **Diagnostics output lost to /tmp.** Background-shell /tmp is not
   stable across tool calls in this environment — the decisive
   fail2ban journal tail vanished, forcing a re-run purely to recover
   it. Logs belong in a stable path (~/.cache/...) from run #1.
4. **Blind positional ss parsing.** `listener.split()[4]` crashed with
   `int('*')` on a column-shape variant I never captured (the offending
   line was never dumped). The fix is a tolerant first-address-shaped-
   token regex, but it is validated only by the suite going green — I
   still do not know what the original odd line looked like.
5. **Test-flow design flaw:** the scanner scenario initially reused the
   SIP section's offender IP — predictably already banned
   (connection-refused). Dedicated IP per scenario from the start.
6. **Classic Nix FOD mistake:** `runCommand` fixture writing into
   `$out/key.pem` without `mkdir -p $out` — cost one tls-turn run.

## e) WHAT WE SHOULD IMPROVE (systemic, from d)

- **Cheap-probe-first ladder for external-engine syntax** (failregex,
  nginx directives, systemd units): every DSL with a local
  validator gets the local validation before a VM boot.
- **Diagnostics-in-failure pattern**: `wait_for_freeswitch` dumps
  evidence on failure; my new asserts should do the same (the ss-parse
  crash printed nothing; the diag block I added was removed again —
  the permanent asserts remain silent on failure).
- **Stable log location for background suite runs** (~/.cache, not /tmp).
- **Derive, don't hardcode**: the RTP assert hardcodes {5060, 5080} and
  the window 16384-16584 instead of reading `services.telephony.rtp.*`
  from the fixture; a range change silently orphans the assert.

## f) Up to 50 things next (1 = highest leverage; owner-gated marked)

1. [owner] First real deployment lane incl. the NEW live security pass
   (Hetzner Cloud Firewall apply + one `ssh-audit` run) — TODO_LIST
   Critical row now carries it explicitly.
2. Eval-time failregex check: `runCommand` running `fail2ban-regex` over
   both shipped filters against canned lines (green in ~seconds, guards
   the date-strip and ignoreself traps forever).
3. NAT two-NIC VM suite (TODO_LIST Medium/L) — promotes the last
   PARTIALLY_FUNCTIONAL edge row.
4. turn.tls runtime suite (turns:/DTLS listener + handshake).
5. Failure-dump blocks for the new asserts (8021/5061/RTP-window) in the
   `wait_for_freeswitch` style.
6. Derive the RTP assert's SIP-port set + window from the fixture config.
7. Shared "offender IP on lo + probe" helper in tests/common.nix
   (fail2ban test now repeats the pattern twice).
8. Scanner-jail filter hardening decision: add basic-auth failure
   counting (`/recordings/`, `/operator/`) vs false-positive/lockout
   risk (see question 1).
9. Aggressive mode for the scanner filter (broader bot-path list) —
   same FP decision.
10. docs/security.md provenance table → machine-checked (a drift-alarm
    style check that cited check names exist in flake outputs).
11. [owner] Cut v0.3.0 — the [Unreleased] section grew again (Security
    - hardening entries this session).
12. [owner] sops-nix example host wiring (unchanged, open question 1).
13. sshd fail2ban jail as a documented nix-ssh-config companion recipe
    (currently one paragraph in security.md).
14. Consider pinning `vulture` into devShells.default so the python
    test files are lintable outside buildflow (bandit is pinned, vulture
    is not — discovered today).
15. Re-run buildflow full pipeline (`--build-mode full --max-time 60m`)
    to cover the linters `nix flake check` does not run (ruff/bandit on
    tests/*, mypy, lychee incl. the new security.md links).
16. wsprobe.py: `read_frames` (manual mode) and `assert_target` now
    share little; consider unifying the probe/assert readers.
17. Document the `ss` column-shape that broke parsing (needs one
    captured line from a VM — fold into item 5's failure dumps).
18. TLS 5061 assert: also pin the negotiated protocol floor (≥TLSv1.2)
    instead of only "a cert was presented".
19. Add the nginx-scanner jail to the operator window's health cards
    (fail2ban jail state is currently CLI-only).
20. [owner] Q3 answer gates: STIR/SHAKEN check + provider CIDR pinning
    ride the deploy lane anyway.

## g) Questions I cannot answer myself

1. **Jail appetite for auth failures:** should repeat 401s on
   `/recordings/`//operator/ basic auth earn bans (real brute-force
   resistance, real lockout risk for a fat-fingered operator), or does
   the scanner-path-only scope stay?
2. **Hoster firewall as code:** apply the Hetzner Cloud Firewall via
   the existing `infra/` Terraform/OpenTofu lane (reviewable, in-repo)
   or keep it a manual console step in the runbook (simpler, no second
   toolchain on the deploy path)?
3. **v0.3.0 timing:** cut now (Unreleased is large and Security-heavy
   again) or hold to the original "after first real call" gate?
