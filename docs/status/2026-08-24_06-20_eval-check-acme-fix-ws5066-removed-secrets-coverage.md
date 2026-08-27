# Status Report — eval-check hardening, ACME fix, 5066 removal, secrets coverage

**Date**: 2026-08-24 06:20 CEST
**Scope**: the follow-up session after `2026-08-22_13-52` (this file reports that
session's run only, per instruction). Predecessor report:
[`2026-08-22_13-52_browser-e2e-green-secrets-complete-aarch64-ci-green.html`](./2026-08-22_13-52_browser-e2e-green-secrets-complete-aarch64-ci-green.html)
(annotated with a postscript by this session).
**Verification state at time of writing**: local `nix flake check` GREEN,
`nix flake check --all-systems --no-build` GREEN, all four pre-commit hooks
GREEN, working tree clean, HEAD `5af3346`, **not pushed** (no push was
requested).

---

## a) FULLY DONE (this session, verified)

| # | Item | Evidence |
|---|------|----------|
| 1 | **Eval-only regression check** `checks.telephony-eval` (`tests/eval.nix`): forces full NixOS eval of all three `tls.mode` variants and greps the generated directory XML for the dial-string's single-dollar runtime vars | Built green; first run caught a real bug (item 2) |
| 2 | **Real bug fixed: `tls.mode = "acme"` failed full system eval** — hand-rolled `security.acme.certs` entry had no HTTP-01 challenge provider (security.acme assertion kills the eval). Fixed by delegating to the nginx vhost's `enableACME` (challenge location, group, reloads included) | `nix eval` fails before fix, passes after; `modules/telephony/web.nix` |
| 3 | **`tests/tls-mode-host.nix` resolved**: registered as the eval fixture behind the new check (was orphaned since it predates the last session); gained boot fixtures (`fileSystems`/`grub`/`stateVersion`) so forcing `toplevel` passes NixOS's own assertions | Wired in `flake.nix` checks |
| 4 | **5066 plain-ws binding removed after A/B disproof**: browser E2E suite ran GREEN with the `ws-binding` gone — the "outbound legs need plain ws" hypothesis is disproven; after the dial-string fix sofia bridges WS contacts over wss alone. Internal profile now binds 5060/5061/7443 only | `nix build -L .#legacyPackages.x86_64-linux.telephony-browser` EXIT:0 |
| 5 | **Gateway `passwordFile` coverage** in `telephony-secrets` VM test: store purity for the provider secret, placeholder in `sip_profiles/external.xml`, runtime splice, live gateway REG state machine off the spliced config | Suite green in 57s |
| 6 | **sops-nix recipe doc** `docs/secrets.md` (docs-only, conservative G.3 default): age keygen, `.sops.yaml`, `sops.secrets` incl. `owner = "turnserver"` for coturn, verify steps. Facts verified against sops-nix module source (cloned, read): `/run/secrets/<name>`, mode `0400`, owner/group `root` defaults, `age.keyFile` null default | Source-verified, no unverified claims |
| 7 | **README Security section rewritten** around the `*File` options (was still describing the pre-`*File` "secrets land in the store" limitation); options tour mentions the `*File` twins | `README.md` |
| 8 | **Browser E2E manual CI job**: `workflow_dispatch` trigger + `browser-e2e` job in ci.yml (conservative G.2 default; promotion stays an owner call) | YAML parses; jobs: check, check-aarch64, browser-e2e |
| 9 | **Runbook hardened**: listening-port reference table (443/5060/5061/5080/7443/8021/3478, loopback-only marked), `ss -ltn \| grep 7443` health check, wss/Via-transport troubleshooting note | `docs/ops-runbook.md` |
| 10 | **G.1–G.3 resolved by conservative defaults** and recorded everywhere they belong: ROADMAP Q1/Q3 closed-by-default, TODO_LIST updated, predecessor HTML report annotated (postscript; tag balance validated — annotated, never rewritten) | ROADMAP/TODO_LIST/report postscript |
| 11 | **Docs fully synced**: TODO_LIST (resolved-this-cycle pruned, 0.2.0 release queued as top item), FEATURES (manual/acme TLS rows, secrets row, CI row, sops recipe row, planned-section swap), CHANGELOG (Added/Changed/Fixed incl. the ACME bug and the 5066 removal), DOMAIN_LANGUAGE + README diagram (5066 gone) | One-home-per-fact respected |
| 12 | **Two deprecation/warning cleanups**: `pkgs.system` → `stdenv.hostPlatform.system` (tests/eval.nix + flake.nix); drvPath string context discarded in the eval check so `--all-systems --no-build` works cross-arch | Both gates green, zero eval warnings introduced remain |

## b) PARTIALLY DONE

| Item | What's there | What's missing |
|------|--------------|----------------|
| Browser E2E CI gating (G.2) | Manual `workflow_dispatch` job landed in ci.yml | **Never executed on GitHub** — commits not pushed, so the job's YAML is unverified in a real run; promotion decision (periodic/push) still open |
| 5066-removal A/B evidence | One green browser-suite run without the ws-binding | A single run; the suite has no known flake history, but a second confirmation run would harden the claim |
| Eval-check breadth | TLS modes + dial-string escaping asserted | Other XML invariants are cheap to assert and not yet: `apply-candidate-acl`, `wss-binding`, per-`*File` placeholder tokens |
| aarch64 story (G.1 default) | Boot-proof-only accepted, documented | Full suites still impossible on GitHub arm runners (no KVM); needs owner hardware or stays as-is |
| docs/secrets.md | sops-nix recipe, source-verified | No agenix variant section; no wired example host (deliberate default, owner can override) |

## c) NOT STARTED

- 0.2.0 release: gitleaks full-history scan, CHANGELOG cut, tag, `gh release` (top TODO_LIST item).
- RTP media-flow assertion in the browser E2E (suite proves signaling + bridging, not byte flow).
- Real-ITSP validation (ROADMAP Q2 still open — no provider/DID).
- Pushing this session's 5 commits and watching CI (both jobs + optionally dispatching browser-e2e).
- Everything in section (f) marked "not started" below.

## d) TOTALLY FUCKED UP (self-inflicted, all caught and recovered — nothing reached main)

1. **Corrupted `tests/secrets.nix` with a multiedit** — produced `nlet` (stray `n` in the
   replacement), discovered only when the suite failed to eval with a baffling
   `syntax error, unexpected '='`. Fixed by re-reading and repairing. Root cause:
   did not visually verify a large multiedit before building.
2. **False-positive eval smoke** — first `nix eval ... | tail -5; echo EXIT:$?` printed
   `EXIT:0` because the exit code measured `tail`'s pipe, not `nix`; the eval had
   actually failed. Re-ran with output-to-file + separate echo. (The handoff
   briefing explicitly warned about pipe discipline — I still stepped on it once.)
3. **statix failure late in the session** — wrote `enableACME = (cfg.tls.mode == "acme")`
   (useless parens); pre-commit only ran at the end, costing a fix+re-run cycle.
4. **drvPath string context broke `--all-systems --no-build`** — my eval check carried
   drv string context into a derivation attribute, so cross-system no-build checks
   demanded foreign-arch drvs be valid. Fixed with `unsafeDiscardStringContext`
   (commit `5af3346`). Root cause: only ran the dual gate (`flake check` AND
   `--all-systems --no-build`) at the very end instead of per-change.
5. **Environment, not repo**: LAN binary cache (`cache.home.lan`) 502ed and poisoned
   one `nix flake check` run; re-ran with `--option substituters https://cache.nixos.org/`.
   Not fixable from here, but it burned a full gate cycle.

**Nothing in this session left the machine in a broken state; every failure above
was detected by a gate and fixed before the next commit.**

## e) WHAT WE SHOULD IMPROVE (honest hindsight — answers to "forgot / better / still")

**What I forgot:**
- To run the pre-commit hooks early (statix catch came late).
- To run `--all-systems --no-build` per-change rather than only at the end.
- To visually verify a big multiedit before triggering a 5-minute VM build.
- That the new browser-e2e CI job is unverified until pushed (cannot be verified locally).
- Initially re-committed the pipe-exit-code trap the briefing had already warned about.

**What I could have done better:**
- Batch verification discipline: after each edit, `nix fmt` + quick eval smoke BEFORE
  any VM build; VM builds are the expensive asset, edits are cheap.
- The `nlet` corruption and the parens lint would both have been caught by a
  2-second `nix eval` or `pre-commit run <files>` before the long builds.
- A/B evidence: run the browser suite twice (or three times) without the ws-binding
  before declaring the hypothesis dead; one green run is good, two is convincing.

**What could still be improved (project-level):**
- The eval check is a pattern, not a one-off: every generated-XML invariant we ever
  debugged in a VM (candidate ACL, wss binding, placeholders, exact-match location)
  can become a one-line grep there — seconds instead of VM minutes.
- CI has no cheap `--all-systems --no-build` step; adding one would catch cross-arch
  eval breakage (like the context bug) before the arm job wastes 2 hours.
- The repo's strongest debugging tools (`wsprobe.py`, the self-diagnosing browser
  dumps) are invisible to operators — the runbook should teach them.

## f) NEXT — up to 50, ranked by impact

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 1 | Push the 5 session commits; watch both CI jobs green | High | 15m |
| 2 | Dispatch the new browser-e2e workflow once to verify the job | High | 30m |
| ~~3~~ | ~~gitleaks full-history scan (pre-release safety)~~ done 2026-08-27: 96 commits, 0 real secrets | ~~High~~ | ~~30m~~ |
| 4 | Cut 0.2.0: CHANGELOG release section, tag, `gh release create` | High | 1h |
| 5 | RTP media-flow assert in browser E2E (byte flow, not just bridging) | High | 1h |
| 6 | Real-ITSP validation config (blocked on provider/DID answer) | High | — |
| 7 | Extend eval check: assert `apply-candidate-acl localnet.auto` in internal profile | Med | 15m |
| 8 | Extend eval check: assert `wss-binding 127.0.0.1:7443` present | Med | 10m |
| 9 | Extend eval check: assert one placeholder token per configured `*File` option | Med | 30m |
| 10 | Second browser-suite run without 5066 (A/B confirmation) | Med | 30m |
| 11 | Add `nix flake check --all-systems --no-build` step to CI | Med | 15m |
| 12 | agenix variant section in docs/secrets.md | Med | 45m |
| ~~13~~ | ~~Document `checks.telephony-eval` in README Development section~~ done (docs-health pass 2026-08-27) | ~~Low~~ | ~~15m~~ |
| 14 | Runbook: teach wsprobe.py + browser-dump diagnostics to operators | Med | 45m |
| 15 | Voicemail deposit/retrieval scripted test | Med | 2h |
| 16 | NAT runtime test (two-NIC VM topology, `natAddress` advertisement) | Med | 3h |
| 17 | Manual TLS mode runtime test | Low | 1h |
| 18 | Assert RTP port range actually enforced (switch.conf + firewall) | Low | 30m |
| 19 | Monitor: fs_cli health timer + alert on profile down / REG fail | Med | 2h |
| 20 | fail2ban rules for SIP scanning | Med | 2h |
| 21 | Security hardening guide (firewall-to-provider, TURN exposure) | Med | 2h |
| 22 | Webphone i18n (de/en) | Med | 4h |
| 23 | Tree-shaken SIP.js bundle (import only needed modules) | Low | 2h |
| 24 | SIP.js version-bump path doc + try 0.22/0.23 | Low | 2h |
| 25 | mod_verto spike (drop the nginx proxy hop) | Low | 4h |
| 26 | IVR (declarative menus) | Med | 6h |
| 27 | Conference rooms | Med | 4h |
| 28 | DISA | Low | 3h |
| 29 | Time-based routing (business hours) per ring group | Med | 4h |
| 30 | Voicemail-to-email (`vm-mailto`) | Med | 3h |
| 31 | Per-extension outbound caller-id override | Low | 1h |
| 32 | `*97` per-call recording toggle (+ announcement option) | Low | 2h |
| 33 | DB-backed directory (mod_pgsql + PostgreSQL) for scale | Low | 6h |
| 34 | CDR to database (not just CSV) | Low | 4h |
| 35 | 16 kHz sounds package (prompt quality) | Low | 1h |
| 36 | IPv6 SIP profiles behind `ipv6.enable` | Low | 6h |
| 37 | Kamailio edge-proxy spike (defer until load demands) | Low | — |
| 38 | Upstream `services.telephony` module to nixpkgs | High | days |
| 39 | coturn TLS listener option (`tls-listening-port`) | Low | 2h |
| 40 | QoS/DSCP marking options for RTP | Low | 2h |
| 41 | Scheduled `nix flake update` PR (Dependabot-style cadence) | Low | 30m |
| 42 | Third-party license notice audit (sounds pack redistribution) | Low | 30m |
| 43 | Browser E2E runtime reduction (profile reuse / parallel) | Low | 2h |
| 44 | Webphone reconnect backoff test | Low | 1h |
| 45 | SELF-hosted ARM runner with KVM if hardware materializes (G.1) | Med | — |
| 46 | Promote browser E2E CI (periodic/push) once stable (G.2) | Low | 15m |
| 47 | Wire sops-nix into example host if owner opts in (G.3) | Med | 3h |
| 48 | GitHub repo metadata polish (topics, description) at 0.2.0 | Low | 15m |
| 49 | Demo-VM smoke script for humans (register→call→recording in one command) | Low | 2h |
| ~~50~~ | ~~Roadmap review: promote/refine after 0.2.0 decisions~~ done (docs-health pass 2026-08-27) | ~~Low~~ | ~~30m~~ |

## g) QUESTIONS I CANNOT ANSWER MYSELF

1. **Push authorization**: the session's 5 commits are local and unpushed. Should I
   push to `main` now and watch CI (including dispatching the new browser-e2e job)?
   I never push without an explicit ask.
2. **Real ITSP (ROADMAP Q2)**: which provider (digest username/password vs IP-peer)
   should the gateway options be validated against first, and is there a DID I may
   target in a demo config? This gates the only remaining "partially functional"
   gateway feature.
3. **Defaults confirmation**: I proceeded on conservative defaults for G.1
   (boot-proof-only aarch64), G.2 (manual browser CI) and G.3 (docs-only sops
   recipe). Confirm them as-is, or override any — each override is a queued task
   in section (f).

---

*Point-in-time snapshot. Annotate, never rewrite. Section (f) feeds TODO_LIST /
ROADMAP via docs-health HARVEST — TODO_LIST already carries items 1–5, 10–12; the
rest are ROADMAP fuel.*
