# SUPERB backlog execution — status + owner packet (2026-11-14 13:28)

Point-in-time snapshot. Trigger: owner directive "the WHOLE TODO LIST"
over `docs/planning/2026-11-14_11-41_SUPERB-pareto-execution-plan.md`
(M01–M32, F01–F131). This report is the honest ledger: what is DONE and
at which proof tier, and the exact remainder that is owner-hands.

## Verdict table (M-tasks)

| Task | Verdict | Proof tier |
| ---- | ------- | ---------- |
| M03 passkey rerun | **DONE** — ceremony green end to end; suite migrated to the 2.14.0 login flow | suite-green (`legacyPackages.telephony-passkey` exit 0) |
| M32 process hardening | **DONE** — rc-capture MUST + verdict-tier rule; wrapper arm decided NO (documented) | session-proof (gates green) |
| M24 docs batch | **DONE** — 2 dropped facts restored; rest verified already-landed (row was stale) | session-proof (grep) |
| M29 crush-config lessons | **DONE** — 3 lessons committed there (`f280f8d`) | session-proof |
| M06 lens source-access | **DONE** — module renders bind/ACL/group/arg-rewrite; suite override deleted | suite-green (`telephony-lens` exit 0) |
| M07 lens freshness | **DONE** — check unit over /api/ops, alert lane, fail-closed assertions (auth-off required, threshold derived) | suite-green (unit ran live in VM: "OK: 0.41s (max 6s)") |
| M22 refresh recipe + dryRun | **DONE** — runbook classify→apply recipe + `retention.dryRun` | suite-green + eval arm |
| M31 pii docs + CSP | **DONE** — runbook pii=hash paragraph + `csp.nonce`/`reportOnly` env pair | suite-green + eval arm |
| M05 push transports | **DONE** — `webphone.push.ntfy/fcm` facade (settings + env lane + fail-closed) | suite-green (eval arms) |
| M13 flight recorder | **DONE** — demo on, prod comment, runbook fetch recipe | session-proof (upstream option + module check) |
| M15 system.db | **DONE** — registered in `state.sqliteDatabases` beside webphone.db | suite-green (eval arm) |
| M17 CRM | **HALF** — route-level Kith compatibility PROVEN (401, not 404); token + flip = owner | session-proof (live probe) |
| M12 browser E2E 2.14.0 | **DONE** — green, zero selector fixes | suite-green (`telephony-browser` exit 0) |
| M10 oauth2 twin | **DONE** — deliberate FORK documented in the option description (the why: shared identity map) | session-proof (source-verified) |
| M11 metrics | **DONE** — scrape arm + islandBeacon option, demo-on | suite-green (eval arm) |
| M16 ASR | **FACADE DONE, DARK** — full option surface, fail-closed; G1 only gates the flip | suite-green (eval arms) |
| M21 ring wire lock | **DONE** — vendored contract + field-for-field test + gate-5 step | suite-green (8/8 ringhook tests) |
| M23 ops/test depth | **DONE** — livez/readyz/version probes, browser-smoke.py, DID convention; row-shape verified landed; sim-curl scoped OUT (rationale in CHANGELOG) | session-proof (366 tests green) |
| M25 docs-gates | **DONE** — 6 fixed, ratchet 48→43, exempt classes documented | session-proof (gate green) |
| M26 lint ownership | **DONE** — ruff.toml frozen selection; REAL bug fixed (TimeoutException import) | session-proof (`ruff check .` green) |
| M30 nixpkgs draft | **DONE (draft)** — verified at pin; configDir already upstream; file-ready | session-proof |
| M20 pma gating | **DONE (draft + sweep)** — lever verified hardcoded; 218-repo exposure; fix file-ready | session-proof |
| M09 sweep instrumentation | **DOC HALF DONE** — G4 packet (auditd vs wrapper, costs); containment verified complete | session-proof |
| M08 CDR live track | **EVIDENCE HALF** — host reachable; 0 mid-ring cancels in 14d; repro needs trunk creds | session-proof (live journal) |
| M02 CI trust | **ADMIN HALF DONE** — branch protection LIVE (4 contexts, enforce_admins off); secret + drill owner | airtight (API echo) |
| M27 owner misc | **PACKETED** below | — |
| M28 fspbx sign-off | **PACKETED** (PAT revocation is the one step) | — |
| M01/M04/M14/M18/M19 | **OWNER HANDS-ON** — packeted below | — |

Session commits (hand-authored, this repo): `17e2a83`, `894c396`,
`a9a7808`, `adf8a0a`, `7cef4b2`, `8149375`, `e810f47` (+ daemon
content intermediates between them; crush-config `f280f8d`).
The final `nix flake check --no-eval-cache` verdict lands in the
CHANGELOG same-commit per house rule (running at report time).

## The owner packet (everything only hands can do)

1. **G1 (ASR)**: whispercpp local vs none. The facade is dark-shipped;
   `services.telephony.webphone.asr.provider = "whispercpp"` + a loopback
   URL flips it. Default-off until you say local.
2. **G2**: SETTLED (documented fork) — no action.
3. **G3 (CRM)**: issue a Kith machine token, verify the by-phone
   response shape, then `webphone.crm.*` on the live host. Routes
   verified compatible 2026-11-14.
4. **G4 (sweep)**: auditd vs wrapper — 5-minute call, packet in the
   runbook ("Sweep executor instrumentation").
5. **G5 (deploy close-out)**: the docs/deploy.md §3–5 hands-on afternoon
   (webhook URL patch, outbound loop, IPv6+AAAA, old-server delete,
   first calls, trunk hardening, security pass).
6. **M02 remainder**: `gh secret set ALERT_WEBHOOK -b <url>` + one
   deliberate red. Protection is live; the alert lane is the missing
   half.
7. **M04**: Warsaw DID re-purchase + KYC in the ~48h window (then DE
   national).
8. **M14**: rotate the Telnyx API key in the portal; update consumers +
   the KEY-prefix scrub pattern.
9. **M18**: WhatsApp embedded signup + VOICE-OTP verify; flip
   `messaging.whatsapp.{enable,did}` on the host.
10. **M19**: fix/drop the global `~/.gitconfig core.hooksPath` in
    home-manager.
11. **M20 apply**: the pma PR + daemon config (draft file-ready:
    `docs/drafts/2026-11-14_pma-committer-exclude-pathspecs.md`).
12. **M27 misc**: scrub-pattern placeholders (fill or delete), sops-nix
    example wiring, GitHub residual-exposure call, retentionDays +
    /metrics-card offers (close), browser-E2E CI promotion call.
13. **M28**: revoke the fspbx Sanctam PAT, then the sign-off row dies.
14. **M30 submit**: file the nixpkgs issue from
    `docs/drafts/2026-11-14_nixpkgs-freeswitch-mkdefaults.md`.
15. **M08 finish**: run `tests/vantage_probe.py` with the trunk creds,
   journal the cancel, pick the fix (log-b-legs vs sofia flag; NEVER
   answer-before-cancel).
16. **PUSH**: this session's commits are local; push when the final
   check verdict is in (branch protection requires the four checks —
   the push triggers them).

## Incidents en route

- The daemon raced three commits (healed by reset-soft + re-author each
  time, per the runbook protocol); one python double-write clobbered a
  new eval arm (caught immediately, re-inserted).
- Two unverified-upstream-claim classes caught and corrected at source
  before shipping: the lens /metrics gauge name (does not exist — the
  freshness check reads /api/ops, auth-off asserted) and the passkey
  `#passkey-login` selector (removed at 2.14.0; the suite now drives
  the front-door flow) + the POST /api/session probe (GET is the
  resume probe; POST is the CSRF-gated extension login).
