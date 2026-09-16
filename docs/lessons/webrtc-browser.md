# WebRTC/browser lessons (long-form)

Moved verbatim from AGENTS.md 2026-09-16 to keep that file under its
line cap. AGENTS.md carries one-line pointers; the full stories live
here. Annotate, never rewrite — append new lessons at the bottom.

## SIP.js/JsSIP npm tarballs ship no dist/ browser bundle

We fetch the sip.js tarball (0.21.2, zero runtime deps) and
esbuild-bundle `lib/index.js --format=iife --global-name=SIP` (see
packages/webphone/default.nix). esbuild's `--legal-comments=external`
emits nothing (sip.js `lib/*.js` carry no license comment) — ship the
tarball's `package/LICENSE.md` as `sip.min.js.LEGAL.txt` instead.

## WebRTC/browser stack — four stacked reasons browser calls failed

(All fixed, each verified by the browser E2E.)

1. nginx `location /sip` is a PREFIX match — it captured `/sip.min.js`
   and proxied the bundle to sofia (400). Exact-match `= /sip`; the
   webphone suite asserts a 200 bundle fetch as the regression guard.
2. **FreeSWITCH drops SIP requests whose Via transport token mismatches
   the connection transport, silently** (no 4xx, no log at default
   level; only `siptrace` shows the recv). Browsers only speak `wss://`
   from https pages (Via/WSS), so the proxy hop MUST be TLS to sofia's
   `wss-binding` (7443) — a plain `ws-binding` eats every browser
   REGISTER. (A later A/B — browser suite green with the `ws-binding`
   removed — DISPROVED the early claim that a plain ws listener is
   needed for outbound legs: after the dial-string fix in item 4, sofia
   bridges to WS-registered contacts over wss alone; 5066 is gone.)
3. Without `apply-candidate-acl`, sofia screens ICE candidates against
   `wan.auto`, which DENIES all private ranges — every LAN/lab browser
   (no srflx candidates) gets 488 INCOMPATIBLE_DESTINATION. Profile
   sets `apply-candidate-acl localnet.auto`.
4. The directory `dial-string` template's `dialed_user`/`dialed_domain`
   are RUNTIME dial variables (single `${}`), not `$${}` pre-processor
   vars — over-escaping them breaks every `bridge(user/N)` with "No
   origination URL specified". TCP regs happened to work via a
   fallback; WS regs (with fs_path contacts) did not.

`tests/wsprobe.py` (stdlib RFC 6455 client, shipped into the browser
test VM) probes the whole path by hand: handshake + REGISTER with
Via/WSS vs Via/WS controls — the decisive tool for transport issues.

## Selenium/browser-test traps

`.text` returns "" for elements inside hidden parents (read
`textContent` via `execute_script` for the webphone's `#log`, which
sits in the hidden-until-login phone view) and returns RENDERED text,
so CSS `text-transform: uppercase` breaks case-sensitive substring
waits. A bare `python3` on the VM PATH shadows a
`python3.withPackages` interpreter — run E2E scripts through a
`writeShellScriptBin` wrapper naming the exact interpreter
(`writeShellScript` alone is a file and buildEnv-rejected in
`systemPackages`). `environment.systemPackages` entries producing the
same binary name collide nondeterministically. Keep E2E-script wait
timeouts BELOW the testScript's marker timeouts so the script's own
failure dumps land in the log before the driver aborts.
