# Status: webphone v2 switchover + flake inputs unpinned (2026-09-18 22:03)

Session goal (owner directive): **"NEVER HARD CODE THIS VERSION! I want to be
on the latest version for ALL! Only the flake.lock should say!"** — i.e.
remove every hard-coded input revision; flake.lock is the single version
authority. Releasing the webphone pin required landing the full v2
switchover first (the pin existed because upstream deleted the static-site
layout this module served).

Headline: **`nix flake check` is GREEN (all 27 checks incl. 18 VM suites)
with both inputs tracking upstream main.** The browser E2E (outside
checks) rings but cannot answer — that is an upstream webphone v2 bug
(accept/reject buttons reference functions that are never imported),
root-caused to the exact line, fix not yet pushed.

---

## a) FULLY DONE

1. **Inputs unpinned, lock is the only version authority**
   - `flake.nix`: `webphone` → `github:LarsArtmann/webphone` (was pinned
     to static-site rev `2821dfee…`); `nix-ssh-config` →
     `github:LarsArtmann/nix-ssh-config` (was `v0.1.3` tag). No revs in
     flake.nix anymore.
   - `flake.lock` updated: webphone @ `3a59647`, nix-ssh-config @
     `391088b` (verified remote main heads; local webphone checkout has
     zero diff vs the locked rev in every contract file I depend on).
2. **Webphone v2 switchover (modules)**
   - `telephonyModule` wrapper now imports the webphone repo's own
     `nixosModules.default` (services.webphone: unit, user, hardening,
     JSON config rendering stay in sync with the binary upstream).
   - `modules/telephony/web.nix`: wires `services.webphone` (enable,
     package, settings: loopback addr 8080, sip_domain, contacts,
     phone_api_url → operator loopback when phoneApi enabled); nginx vhost
     now reverse-proxies `/` (+ `/events` SSE: unbuffered, HTTP/1.1, 3600s)
     to the app; static `webRoot` copy DELETED; nginx `/phone-api/`
     location DELETED (the app proxies it itself with session-injected
     Basic auth); vhost-level CSP dropped (app sends its own), strict CSP
     kept on `/recordings/` + `/operator/` + `/operator-api/`.
   - **TURN rotation preserved without restarts**: nginx still serves the
     runtime-rendered `/var/lib/telephony/config.js` OVER the app's own
     `/config.js` (the app's island script tag loads the same URL), so the
     daily 48h REST-credential timer keeps working and the app's
     in-memory sessions never drop.
   - `options.nix` / `default.nix` descriptions updated (service, not
     static site; raw consumers must import the webphone module too).
3. **Tests**
   - `tests/common.nix` + all 18 suites + flake call sites: import the
     flake wrapper (`telephonyModule`) instead of the raw module path —
     tests now exercise the shipped consumer interface.
   - `tests/webphone.nix` rewritten for the v2 contract: webphone unit +
     8080 + healthz (direct + proxied), island ids on the served shell,
     island modules asserted VERBATIM on the wire (calls/connection/
     notify/panels/ice), sip bundle at `/assets/vendor/sip.min.js`,
     `/phone-api` without session = 401, runtime config.js assertions
     unchanged, CSP from the app through the proxy, `= /sip` + wsprobe
     unchanged.
   - `tests/operator.nix`: all phone-api curls moved to the operator
     loopback (8071); NEW end-to-end chain: fetch shell → extract
     csrf-token meta → POST /api/session (201) → session-cookie
     `/phone-api/history` (proxied with injected Basic auth) → 401 without
     session.
   - `tests/ssh.nix`: golden updated for the upstream PermitRootLogin
     matrix — keys-only root now emits `prohibit-password` (deliberate,
     documented upstream hardening; runtime-identical; verified against
     upstream CHANGELOG + module source before accepting).
   - `tests/tls-turn.nix` + `tests/fail2ban.nix`: wait for
     `webphone.service` before proxied `/` curls (nginx-up-before-app boot
     race — caused the two intermediate check failures).
   - `tests/prod-boot.nix`: wrapper import; duplicate `mkDefault
     webphone.package` removed (unique-option conflict).
4. **Gates**
   - Fast gates green: `nix fmt`, statix (incl. an `inherit` fix in my own
     code), deadnix, format check, docs-drift, changelog-headings.
   - **Full `nix flake check` GREEN on attempt 5** (attempt 1 killed as
     stale by my own mid-run edit; 2 real failures found and fixed:
     operator CSRF 403 → token-aware login; ssh golden → upstream matrix;
     tls-turn/fail2ban boot races → waits).
   - `nix build .#webphone` (v2 Go binary) builds from the locked rev and
     smoke-starts.
5. **Docs (one home per fact)**
   - AGENTS.md: "What this is" (v2 service), wrapper contract (raw
     consumers import BOTH), commands; the pin paragraph replaced by the
     tracking-main invariant + switchover lessons (config.js shadowing
     rationale, dead static-layout warning).
   - CHANGELOG `[Unreleased]` Changed: switchover + inputs-unpinned
     entries (merged into the existing Changed section — headings gate).
   - FEATURES.md: webphone rows rewritten (v2 service row replaces
     static-serving row; sip bundle row; voicemail panel row now names the
     session proxy; /sip regression-guard path updated; ssh row
     de-pinned).
   - TODO_LIST.md: switchover row DELETED (done work leaves the list).
   - README.md (capability table, options, module map), ops-runbook
     (webphone.service row, config.js shadow note, failure playbook items
     1+2 rewritten for proxy + new bundle path), upstream.md, security.md.
6. Everything auto-committed by the daemon along the way; nothing lost.

## b) PARTIALLY DONE

- **Browser E2E (`legacyPackages.telephony-browser`)**: wrongpass leg ✓,
  both browsers REGISTER over wss ✓, reconnect drill (stop/start nginx,
  auto-stuck → reload fallback) ✓, DIAL ✓, INCOMING-SHOWN ✓,
  notifications + title flash ✓ — **fails waiting for CALL-ESTABLISHED**.
  Root cause (from the suite's own console dumps, then verified in
  source): upstream `internal/web/assets/island/app/main.js:6` imports
  `{placeCall, renderCalls, sendDtmf, teardownAll}` from calls.js but
  lines 107/111 call `answerIncoming()` / `rejectIncoming()` — both are
  EXPORTED by calls.js but never imported → the accept click throws
  `Uncaught ReferenceError: answerIncoming is not defined`, the callee
  never answers, ring times out as "missed". One-line upstream fix
  identified; not yet written/pushed (push needs explicit owner
  approval). **→ done — fixed upstream; the browser E2E full path (answer, DTMF, transfer) is green since the 2026-09-20 relock (`8c527ac`)**

## c) NOT STARTED

- The upstream webphone fix (edit main.js import, commit, push) and the
  follow-ups it gates here: `nix flake update webphone`, browser E2E
  re-run, deploy verification. **→ done — fix landed upstream; relocks since (`77e3932` → `94ae28d` → `2bbbc2e`); E2E green 2026-09-20/09-22; deploy-verify rides the deploy lane (TODO_LIST High row)**
- Upstream CSRF-403 deep-dive conclusion (see d): investigation reached
  httputil csrf.go's origin comparison (line ~782) before this report was
  requested. **→ done — resolved upstream; real-browser logins (form POST /api/session) green in the E2E since the 09-20 relock**
- Updating the webphone repo's own AGENTS/TODO ("who ships the NixOS
  module" is now answered: this stack imports theirs) — sibling repo,
  out of this session's scope. **→ open — webphone repo (out-of-repo)**

## d) TOTALLY FUCKED UP (upstream webphone v2 bugs found by the E2E; not caused by this repo's changes)

1. **Accept/reject buttons are dead** (main.js missing imports —
   product-blocking: no browser user can answer a call with the mouse;
   keyboard shortcut `A` still works because shortcuts.js imports
   answerIncoming correctly). THE E2E blocker. **→ done — fixed upstream; E2E answer leg green since 2026-09-20**
2. **`POST /api/session` returns 403 in real browsers** (CSRF). curl with
   cookie + meta token succeeds (proven in the operator suite), the
   island's fetch with the same token fails → messages/fax/voicemail tabs
   and the phone-api proxy are dead in real browsers. Difference vs curl:
   browsers send Origin/Sec-Fetch-Site headers; suspicion is the
   httputil CSRF origin path behind a proxy, but NOT yet root-caused. **→ done — resolved upstream (real-browser session logins green in the E2E; the module also gained CSRF precedence hardening at the 09-20 relock)**
3. The served page violates its own CSP (an inline script on `/` blocked
   — hash `AO4OqWm6…`, likely templ-components layout.Base) + htmx inline
   style violations + `/favicon.ico` 404 (app serves favicon.svg).
   Cosmetic-noisy, but a CSP violation on every page load is wrong. **→ open — upstream cosmetic; verify on the next visual pass**
4. Latent: the app's own `/config.js` would marshal shared contacts with
   capitalized keys (`Name`/`Number` — SharedContact has no JSON tags)
   while the island reads lowercase `name`/`number`; masked in our
   deployment by the nginx config.js shadow. **→ done upstream `e43fea8` (2026-09-25): json tags + wire regression test; stack relock + assert flip in flight (TODO_LIST row)**

## e) WHAT WE SHOULD IMPROVE (process, this session)

- **Run the browser E2E before burning three full flake-check passes.**
  It was the only suite that clicks accept; it found the one bug that
  matters. Order should have been: cheap suites → browser E2E → full gate.
- **Read upstream CHANGELOGs before unpinning inputs.** The ssh golden
  break (PermitRootLogin matrix) was documented verbatim in
  nix-ssh-config's CHANGELOG; the pin comment even warned about the
  golden snapshot.
- **Beware sed -i touching files you'll later edit** (mtime invalidation
  cost me two edit retries) — cosmetic, but avoidable.
- **Fail-fast ordering inside my own suites**: two of the three check
  failures were boot races my new waits fixed; the webphone suite already
  had the right pattern — replicate its "wait for the app, then the proxy"
  ordering anywhere a proxied URL is curled.
- Consider a tiny eval-time check that the island's served JS modules
  pass an import/reference lint (upstream concern, but our E2E is the
  only automated tripwire for it).

## f) NEXT (prioritized, not started unless noted)

1. Fix upstream webphone main.js imports (answerIncoming, rejectIncoming)
   — one line + comment; run webphone repo gates (prettier/nix flake
   check). **→ done — fixed upstream; E2E green since 2026-09-20**
2. Commit the upstream fix (daemon will auto-commit; make it explicit per
   task) — then **push needs owner approval**. **→ done — landed on upstream main**
3. `nix flake update webphone` here once pushed; re-run
   `nix build -L .#telephony-browser` → expect CALL-ESTABLISHED and the
   transfer/DTMF/media assertions to be exercised for the first time on
   v2. **→ done — relock `8c527ac` (2026-09-20); E2E-OK with transfer/DTMF legs green**
4. Root-cause the browser `/api/session` CSRF 403 (httputil csrf.go,
   Origin-vs-Host/X-Forwarded handling behind nginx; reproduce with
   curl + Origin/Sec-Fetch-Site headers through the vhost to bisect
   proxy vs app). **→ done — resolved upstream (browser logins green in the E2E since 09-20)**
5. Upstream: add the missing JSON tags to domain.SharedContact (or a
   marshal test) so the app's own /config.js matches the island contract. **→ done — upstream `e43fea8` (2026-09-25): json tags + wire regression test**
6. Upstream: fix the CSP-violating inline script in the shell (nonce or
   external file) + favicon.ico redirect/404 handling. **→ open — upstream cosmetic (§d.3)**
7. File upstream issues/PRs for 1/4/5/6 (verify-before-filing: each now
   has source-level evidence from this session). **→ overtaken — bugs 1/2/4 were since fixed upstream without filings; only the CSP cosmetic (§d.3) remains, below filing threshold**
8. Add `webphone.service` + `/healthz` to the telephony-health profile
   (monitoring.nix) — the UI is now a service that can die quietly. **→ open — TODO_LIST row (added 2026-09-25)**
9. Consider exposing `services.telephony.webphone.*` pass-throughs for
   the webphone gateway (SMS/MMS/fax webhook mode +
   environmentFile) — currently documented as a raw
   services.webphone.settings override only. **→ open — ROADMAP theme 3**
10. Update the webphone repo's AGENTS/TODO: the module-ownership question
    is resolved (stack imports their module); their "consumers" section
    should describe the config.js shadowing contract. **→ open — webphone repo (out-of-repo)**
11. Re-verify docs/deploy.md §5 human checklist against v2 (login → 9196
    echo still valid; add webphone.service healthz probe line). **→ done — 2026-09-24 (P38 remainder; CHANGELOG Added)**
12. CHANGELOG: after upstream fix lands + E2E green, note the v2 E2E
    proof in the switchover entry (it currently cites the operator-suite
    session chain only). **→ done — the v2 E2E state is recorded in FEATURES (webphone rows cite the browser E2E) + the 2026-09-22 harness entries**
13. Add a TODO row (or upstream issue): browser E2E in CI on webphone
    input rev bump (the flake-update PR runs `flake check --all-systems
    --no-build` — it will NOT catch browser-only regressions). **→ open — ROADMAP theme 5 (repo plumbing)**
14. After first v2 deploy: confirm SSE `/events` streams behind the
    proxy on a real network path (VM-proven only implicitly; no suite
    asserts SSE data through nginx yet). **→ open — deploy lane + ROADMAP theme 3**
15. Consider a VM assertion for `/events` (session-gated 401 without
    cookie; buffering-off header behavior) — cheap curl addition to
    tests/webphone.nix. **→ open — ROADMAP theme 3 (suite depth)**
16. Consider asserting the `/api/session` 403-without-CSRF path in
    tests/webphone.nix (currently only operator.nix covers the happy
    path). **→ open — ROADMAP theme 3 (suite depth; the 401-no-session phone-api leg is covered)**
17. Re-run `scripts/scrub-check.sh --strict` before any history surgery
    this session might motivate (none planned). **→ done — standing gate; re-run clean repeatedly since (most recently 2026-09-24)**
18. Cut v0.3.0 (TODO row exists; the switchover + unpin entries make the
    section even bigger). **→ open — TODO_LIST blocked row (v0.3.0)**
19. Optional: dependabot `docker`/`pip` ecosystems are absent; only
    github-actions is covered — flake inputs rely on the monthly
    flake-update workflow; consider shortening its cron or adding
    workflow_dispatch on webphone pushes. **→ open — ROADMAP theme 5**
20. Watch niri.cachix 522s seen during substitution — cosmetic (fallback
    to local build) but slows CI; consider pruning that substituter from
    the environment if it is not ours. **→ overtaken — environment-level substitution noise; not repo-owned**

(21–50: the above 20 are the real backlog; padding further would be
invention, not work.)

## g) QUESTIONS (cannot be answered from the repos)

1. **May I push?** The upstream fix (webphone main.js imports) must be on
   GitHub for `nix flake update webphone` to pick it up. Pushing is
   forbidden without your explicit say-so: say "push the webphone fix
   (and this repo afterwards)" and I'll do both + refresh the lock +
   re-run the browser E2E. **→ answered — the fix landed on upstream main; the relock + E2E followed 2026-09-20**
2. **Tracking policy for your own inputs**: main (current, what you asked
   for — CI can break on upstream pushes, like today's ssh golden) vs
   latest release tag per repo (still "no hard-coded versions", but
   release-gated). Keep main for both, or tags for either? **→ answered — tracks main for both (owner decision 2026-09-18; AGENTS records the invariant)**
3. **The upstream CSRF 403**: continue the deep-dive in the webphone repo
   as part of this effort, or park it as a filed upstream issue and keep
   this repo's scope closed? (This stack's phone-api path is proven via
   the operator suite; only real-browser tabs are affected.) **→ answered — resolved upstream; the repo scope stayed closed**
