# Browser E2E bring-up for the front-door flow — eight attempts, five real leg fixes

> Claims verified as of 2026-11-11 ~18:10 local. The run IS the record:
> the suite is green end-to-end against webphone `9cb5174c` (the
> pre-release pin carrying the front-door + restyle trains).

## Verdict

`nix build -L .#telephony-browser` — **RC=0 in 269 s** (budget 445 s),
attempt 8. `E2E-OK` + every post-run assertion in `tests/browser.nix`
green after the assertion set learned the front-door shapes. The
pre-tag served-markup obligation (webphone release-runbook §2b) is
FULFILLED for the auth-front-door train: only the cross-repo E2E
drives the new flow, and it now does.

## What the suite proves about the new flow

- Wrong password surfaces visibly (`WRONGPASS-PILL-REJECTED:
  registration rejected — check credentials`) — the fail-open posture
  named by the boot WARN (`pbx credential verification disabled`), not
  the prod 401 shape; the leg asserts whichever posture the boot
  journal names.
- Theme FOUC evidence pair intact on the signed-in shell: blocked
  preload = 61 unthemed rAF ticks then settles dark; allowed preload =
  0 unthemed ticks. `theme-preload.js` is still load-bearing.
- Both browsers register through the front door: `1000/1001-REGISTERED`
  - `1000/1001-SESSION-RESUMED-FRONT-DOOR` (the boot resume GET 200 is
    the server-side session proof; the login page's POST proof dies with
    its document).
- The real call: establish, DTMF (Signal= form), blind transfer with
  callee media bytes, FS outage → `RECONNECT-RECOVERY: auto
  (watchdog)`, contacts roundtrip, dial-guard + logged-out dial.

## The five real defects the first execution found (all in the E2E legs,

## none in webphone)

1. **Wrongpass leg assumed verification ON.** The browser VM boots
   without `phone_api_url` (the documented fail-open posture,
   `tests/messaging.nix` pins the same one), so the wrong password
   minted a session (201) and the driver sat on the signed-in shell
   where `#login-error` can never exist. Fix: probe the boot journal,
   assert the documented behavior of whichever posture runs.
2. **The poll could never see the pill.** It read
   `#login-error.textContent` unconditionally; on the shell that throws
   and the `except: continue` skipped the `#reg-status` check on every
   iteration — 300 s of polling with the proof on screen. Fix: both
   probes read independently, every documented visible outcome accepted.
3. **The theme leg's anonymous deep link bounces.** The door renders
   ~2 s, then the island's no-session boot redirect lands on `/login`
   (server log: `GET /messages 200` then `GET /login` two lines later).
   Fix: sign in through the front door; run the FOUC pair on the
   signed-in deep link.
4. **The session gate demanded the island-login shape.** `session=None
   csrf=None` while the island's own log said "session resumed;
   registered". The interceptor is per-document; the front-door POST's
   proof dies with the login page's document. Fix: the interceptor
   records `__wpSessionResumed`; the gate accepts either shape.
5. **The nix-side final assertion named only the old marker** (`1001-
   CSRF-ADOPTED`). Fix: accept the resume marker too. Plus: the theme
   leg hung twice for chromedriver's full default 300 s page-load
   timeout with zero output — page loads now cap at 90 s and every
   phase prints a marker.

## Attempt ledger

| n | verdict   | what died                                                                       |
| - | --------- | ------------------------------------------------------------------------------- |
| 1 | red       | wrongpass: neither `#login-error` nor pill (defects 1+2)                        |
| 2 | red       | wrongpass FAILOPEN branch asserted "registered" — unreachable without brokering |
| 3 | red       | theme: anonymous deep-link bounce (defect 3)                                    |
| 4 | red       | `E2E-OK` reached; `1000-SESSION-GATE-FAILED` (defect 4)                         |
| 5 | red       | `E2E-OK` reached; nix assert `1001-CSRF-ADOPTED` (defect 5)                     |
| 6 | red       | theme hang #1 (300 s page load, silent)                                         |
| 7 | red       | theme hang #2 — same step twice: dug in, bounded the timeouts                   |
| 8 | **green** | 269 s, every leg + assertion                                                    |

## Evidence

Full logs are ephemeral (`/tmp/pre-e2e-2.14.0*.log`, tmpfiles will
purge them); the durable record is this file + the six fix commits
(`301a8f4`, `dc3d8ea`, `358e184`, `ccf4d82`, `347b96c`, `d599ed6`) +
the run's verdict in `gh run`/nix log for the green attempt. The
stack's ci-posture ledger carries the unrelated transient proxy flake
(run 43027908794).
