# Status 2026-09-17 14:06 — Conference pin + caller-controls fixed, fax suite + browser E2E green, operator bind-diagnosis two rounds deep

Session window: 2026-09-17 ~08:45–14:06 CEST (single assistant session,
continuing the 08:10 report's "WAIT FOR INSTRUCTIONS" handoff; directive
was "execute and verify step by step until everything works").

## Executive summary

Three suites went from red/unexecuted to **green** (telephony-conference,
telephony-fax new, telephony-browser E2E), two module-level root causes
were fixed at the source (rate-flattened conference sounds; vanilla
caller-controls `#`-hangup dropping 4-digit-PIN users), the P15/P20/P22
decision docs landed, and five P23.3 test-depth items closed. The
operator suite advanced from "fails at first phone-api call with an
unexplained 500" to "auth gates green, exact 500 body + traceback
captured": the voicemail-DB bind mount design is wrong in a subtle way
(0700 `/var/lib/private` traversal + a symlink-collision on fix attempt
#1); fix #2 is applied and eval-clean but **not yet VM-verified**.

---

## a) FULLY DONE

| #  | Item                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Evidence                                                                                                                                         |
| -- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1  | **Conference PIN suite green** (was the known-red gate)                                                                                                                                                                                                                                                                                                                                                                                                                | `/tmp/conf6.log` CONFERENCE-EXIT=0                                                                                                               |
| 2  | **Root cause 1 fixed at module level**: conference prompt paths are bare `<sound_prefix>/<relative>` concatenation; defaults already carry `conference/`, sounds ship rate-shipped `conference/8000/` — no prefix can bridge; module now builds `freeswitch-conference-sounds-8000-flattened` (compat dir of symlinks) and points the conference entry's `sound_prefix` at it                                                                                          | `modules/freeswitch.nix` conferenceSoundsCompat; sndfile error line in `/tmp/conf5.log` proved the double-`conference` path                      |
| 3  | **Root cause 2 fixed at module level**: vanilla default caller-controls bind `hangup` to `#`; the pin collector stops at maxpin (4 digits) and never consumes `#`, which then lands in the in-conference DTMF handler and instantly expels the freshly admitted member (RECV DTMF timestamps + "Channel leaving conference, cause: NONE" 120 ms after admit). Module ships a patched `conference.conf.xml` without that binding via the new `conferenceTemplate` param | `modules/freeswitch.nix` conferenceTemplate + sed; `modules/telephony/pbx.nix` wiring; vanilla line verified in store; `/tmp/conf5.log` timeline |
| 4  | **Fax VM suite written AND green** (P16 test half): spandsp module loaded, fax dir tmpfiles'd, G.711 noise call to 6000 answered, `set(fax_use_t38=false)` + `rxfax(` EXECUTE markers, clean NORMAL_CLEARING BYE                                                                                                                                                                                                                                                       | `tests/fax.nix`, `checks.telephony-fax` in flake.nix, `/tmp/fax2.log` FAX-EXIT=0                                                                 |
| 5  | **Browser E2E green — first ever full run**: transfer leg (blind REFER → NOTIFY → caller card released → callee keeps media), notifications permission, title-flash, ICE panel — E2E-OK                                                                                                                                                                                                                                                                                | `/tmp/browser1.log` BROWSER-EXIT=0; verifies P8/P10/P17 end-to-end                                                                               |
| 6  | P15 SMS decision memo (Telnyx-API-only; mod_sms/chatplan rejected — no SIP MESSAGE feed exists on this trunk)                                                                                                                                                                                                                                                                                                                                                          | `docs/decisions/2026-09-17_sms-lane-telnyx-api-only.md`                                                                                          |
| 7  | P20 MMS posture doc (HTTP-API-only, Won't-implement-now) + ROADMAP flip                                                                                                                                                                                                                                                                                                                                                                                                | `docs/decisions/2026-09-17_mms-posture-http-api-only.md`, ROADMAP.md                                                                             |
| 8  | P22 diff-drafter verdict: don't-build-now + explicit trigger conditions                                                                                                                                                                                                                                                                                                                                                                                                | `docs/decisions/2026-09-17_nix-diff-drafter-verdict.md`                                                                                          |
| 9  | P23.3d recordings-not-served negative (`/recordings/` must 404 with `recording.serve.enable = false`)                                                                                                                                                                                                                                                                                                                                                                  | `tests/pbx.nix` machine3 section                                                                                                                 |
| 10 | P23.3e sshd pinning asserts (`permittunnel no`, `clientaliveinterval 300`, `clientalivecountmax 2`, `hostkeyalgorithms ssh-ed25519,`) — values verified against the pinned nix-ssh-config v0.1.3 module source                                                                                                                                                                                                                                                         | `tests/ssh.nix`                                                                                                                                  |
| 11 | P23.3f prod-shaped ssh node: `allowRootLogin = true` → effective `permitrootlogin yes`, root key-login positive, keyless user refused, keys-only holds                                                                                                                                                                                                                                                                                                                 | `tests/ssh.nix` nodes.prodshaped                                                                                                                 |
| 12 | P23.3h `wait_for_freeswitch` port param (positional-compatible default 5060)                                                                                                                                                                                                                                                                                                                                                                                           | `tests/common.nix`                                                                                                                               |
| 13 | P23.3g verified already-done (deprecated-gateway file-secret leg existed in secrets.nix — handoff was stale)                                                                                                                                                                                                                                                                                                                                                           | `tests/secrets.nix` gw-itsp leg                                                                                                                  |
| 14 | P28 scrub-gate labels: `--history` HITs now label each commit ADDED / REMOVED (cleanup, not a reintroduction) / edited via per-commit `git show` +/- counting                                                                                                                                                                                                                                                                                                          | `scripts/scrub-check.sh`, smoke-tested both paths                                                                                                |
| 15 | P29 push-staleness script + hooksPath probe recorded: `core.hooksPath` unset, `.git/hooks` only samples — nothing shadows the daemon; ahead/behind check exits non-zero past a threshold                                                                                                                                                                                                                                                                               | `scripts/ahead-check.sh`                                                                                                                         |
| 16 | api.py fixes: `authed` NameError (every /phone-api/voicemail route raised → 500), server-side tracebacks to the journal, `--fs-root` default aligned                                                                                                                                                                                                                                                                                                                   | `packages/telephony-operator/api.py`                                                                                                             |
| 17 | Lessons corrected + extended: the sound_prefix lesson (which documented the WRONG value) rewritten; new caller-controls lesson with the evidence pattern                                                                                                                                                                                                                                                                                                               | `docs/lessons/freeswitch.md`                                                                                                                     |
| 18 | Wrong/cross-password 401 gates in the operator suite now pass (auth machinery proven: fs_cli user_data + compare works)                                                                                                                                                                                                                                                                                                                                                | `/tmp/operator4.log`, `/tmp/operator5.log` 401 lines                                                                                             |

## b) PARTIALLY DONE

1. **Operator suite still RED — bind design iteration 2 applied, unverified.**
   Chain of established facts: auth 401s pass → correct-password summary
   500s → body: `{"error": "internal error: voicemail database not
   present yet"}` → journal traceback confirms `os.path.exists` fails on
   `/var/lib/private/freeswitch/db/voicemail_default.db` → root cause:
   the dynamic user cannot WALK 0700 `/var/lib/private`, and
   `os.path.exists` reports False on EACCES; a bind ON a path below
   private still requires the walk. Attempt #1 (bind onto
   `/var/lib/freeswitch`) failed the same way — that name is a **host
   symlink into /var/lib/private** (NixOS DynamicUser StateDirectory
   layout), and the mount destination followed it straight back into the
   trap. Attempt #2 (applied in tree, eval OK): bind
   `/var/lib/private/freeswitch:/var/lib/telephony/freeswitch-ro` (fresh
   collision-free path) + the three API args (cdr-file, fs-root,
   voicemail-db) moved to that root. Next run should be the verdict.
2. **Full gate not run.** Today's module changes (conference.conf.xml
   override, compat sounds) touch every suite's FS config; individual
   greens exist (conference, fax, browser) but the whole check set plus
   BuildFlow full has not run as a batch.
3. **Docs harvest not done** — TODO_LIST still shows P8/P10–P17/P20/P21/
   P23/P26 as TODO; FEATURES lacks the operator window, fax, phoneApi,
   transfer, ICE panel, both conference fixes; CHANGELOG has nothing from
   today; drift_alarm will bite if only one side is updated (harvest both
   together).
4. **pbx-artmann absorb not done** — and now MANDATORY before any deploy:
   the module's generated FS config changed (patched conference.conf.xml,
   compat-sounds prefix). Private flake must `nix flake update telephony`
   and confirm the telephony-fs-cert/webphone-root store paths moved.
   Owner runs the deploy commands.
5. Operator window polish tail (pagination, CSV export, auth lockout,
   Range requests, vm_read flip) — implemented-not-at-all, listed in f).

## c) NOT STARTED

1. P23.3i demo-VM host-side ssh smoke (`nix run .#vm` + real key login;
   needs the private half of a tracked key).
2. P27 backup-restore proof: assert a real `restic restore` round-trip in
   the backup suite (only backup+ls proven today).
3. P31 hygiene probes: batch `git show --stat` over the ~25 hashes cited
   by docs-health round 2; `buildflow doctor --verbose` vs reality;
   `buildflow upgrade` + db VACUUM; the "1 skipped" step; webphone app.js
   formatting-only review; mypy-coverage decision.
4. P32 docs-health arrow-annotator contribution (line-count-preserving
   writes + per-shape dry-runs).
5. P7 fspbx owner sign-off execution (recommendation delivered 2026-09-16:
   retire VM, stay NixOS-first; the kill-VM/keep-VM hands are the owner's).
6. P18 release (0.3.0 tag + GitHub release) — gated per plan on the first
   real call + owner call.

## d) TOTALLY FUCKED UP (own failures this session, honestly)

1. **Inherited and briefly trusted a wrong "source-verified" fix.** The
   prior session's `sound_prefix=<sounds>/…/conference/8000` value was
   itself the bug (double-conference path); its lesson doc documented the
   wrong value confidently. Cost: one 5-minute burn (conf5) before the
   sndfile error line exposed it. Fix: rewrote the lesson.
2. **Operator bind blind spot, twice.** (a) The prior session's
   `BindReadOnlyPaths=/var/lib/private/freeswitch` could never work
   (0700 walk), and (b) my first fix mounted onto `/var/lib/freeswitch`
   without grepping the repo's own comments — options.nix and pbx.nix
   BOTH already document that this path is a symlink into private. Two
   6-minute burns on one concept. The repo told me; I didn't ask it.
3. **The `authed` NameError shipped untested**: the operator suite was
   written last session and never executed; its first execution died on
   an unbound variable in the file's primary feature. An api.py boot
   smoke existed but only exercised /api routes, not /phone-api.
4. **Wasted one burn on a wrong journalctl unit** (`-u
   telephony-operator-api`; the unit is `telephony-operator`) — got
   "-- No entries --" and had to re-run.
5. **fax.nix named a variable `log`**, shadowing the NixOS test driver's
   `AbstractLogger` builtin — failed at driver typecheck (one burn).
6. **Surgical-add etiquette breached under concurrency**: my `git add -A`
   staged a concurrent session's in-progress `opsTools.enable` edit in
   options.nix (harmless — daemon commits anyway — but sloppy).

## e) WHAT WE SHOULD IMPROVE

1. **Dump-first debugging as default**: the conference dump run (board
   list + show channels + client log + FS log on failure) settled in one
   burn what three blind retries could not. Bake such failure dumps into
   every new suite from the start.
2. **Timestamped DTMF timelines** (RECV DTMF lines vs admit markers)
   beat assumptions about who consumes digits — use for any future IVR/
   pin/DTMF work.
3. **Never build on inherited "source-verified" claims** — re-verify the
   referenced line/file before designing on top (two of three conference
   "verified" facts were wrong in the new codebase).
4. **Grep the repo's own comments before designing mounts/permissions** —
   the symlink layout was documented twice.
5. **Run never-executed suites early, in parallel** (4 concurrent VM
   suites worked fine on this machine).
6. **Avoid driver-builtin names** (`log`, `machine`, `start_all`) as test
   variables; the typecheck catches it but costs a burn.
7. **Module behavior changes ⇒ flag the private-flake re-lock
   immediately**, not at harvest; the stale-lock trap in pbx-artmann's
   AGENTS.md burned three blackouts already.
8. Status-report claims decay: three items the handoff marked "not
   started" were already done by concurrent sessions — check
   TODO_LIST/plan logs before executing a lane.

## f) NEXT (ranked, ~50 items)

1. Run `checks.x86_64-linux.telephony-operator` → verify bind fix #2 (or
   iterate on its evidence).
2. Full local gate: `buildflow --build-mode full --max-time 60m` (or
   explicit per-suite `nix build` sweep + `nix flake check`), fix fallout.
3. Docs harvest (one commit): TODO_LIST delete rows P8, P10–P17, P20, P21,
   P22, P23, P26, P28, P29 (done work is deleted, never struck).
4. FEATURES rows: operator window + 4 API surfaces, fax receive, phoneApi,
   contacts/history, ICE panel, call transfer, CDR default-template fix,
   conference caller-controls + sound fixes, sshd pinning asserts,
   prod-shaped ssh node, recordings negative, scrub labels, ahead-check.
5. CHANGELOG entry for today (module behavior change: `#` no longer
   hangs up in conferences — call it out explicitly).
6. pbx-artmann: `nix flake update telephony` → build toplevel → CONFIRM
   fs-cert/webphone-root/telephony-operator store paths moved; report.
7. Owner decision: deploy or hold (all deploy commands are owner-run).
8. Operator window: CDR pagination + total-count.
9. Operator window: CDR CSV export button.
10. Operator window: auth lockout (backoff) for phone-api brute force.
11. phone-api history: merge SMS entries when smsMessageStore is set.
12. Simulator: ivr.conf.xml menu entries in the model + UI hints.
13. phone-api audio: HTTP Range support (seek in browser player).
14. Voicemail: read/unread flip endpoint via `vm_read` (mark-listened).
15. Voicemail: MWI badge refresh after delete (scheduleVoicemailRefresh
    covers call-end; add post-delete refresh).
16. Operator health: gateway REG state + trunk last-REGISTER age card.
17. Operator health: disk/mem sparkline (or link to monitoring page).
18. Simulator UI: `--when` datetime picker + context selector.
19. Dialplan simulator: expose in nginx at read-only path for curl use.
20. CDR viewer: hangup-cause decode column (NORMAL_CLEARING etc.).
21. Recordings player in operator window (streamed via existing auth).
22. Fax: mailer notification on received TIFF (voicemail mailer pattern).
23. Fax: T.38 posture note in deploy.md (trunk-level enable checklist).
24. Fax: page-count/TIFF validation helper script.
25. P23.3i demo-VM ssh smoke (owner key pointer needed — see g1).
26. P27 restic restore round-trip in the backup suite.
27. Backup: consider /etc host keys in backup paths (row note).
28. P31 batch `git show --stat` sweep of docs-health-cited hashes.
29. P31 `buildflow doctor --verbose` vs reality probe.
30. P31 `buildflow upgrade` + result-cache VACUUM.
31. P31 identify the "1 skipped" BuildFlow step.
32. P31 webphone app.js formatting-only review (Prettier vs hand style).
33. P31 mypy-coverage decision (adopt or drop the typing gate).
34. P32 docs-health arrow-annotator contribution.
35. fspbx trial disposal execution once the owner signs off (kill VM,
    revoke PAT, trash /var/tmp/fspbx-trial OR relocate+snapshot).
36. Trunk hardening P9 (owner-gated until first calls): allowedCidrs +
    fail2ban on 5080.
37. Warsaw DID re-purchase + KYC (owner, 48h window).
38. DE national DID order (owner) then second-gateway stanza + tests.
39. Telnyx API key rotation (owner) + scrub-pattern update in same action.
40. Browser-E2E CI cadence promotion (owner: periodic vs per-push).
41. flake-meta-checker mainProgram policy (upstream BuildFlow thread).
42. Upstream BuildFlow feedback items (max_time keys, nix-checker FOD
    advisory, data-package mainProgram).
43. sops-nix example host (owner-gated).
44. GitHub residual-exposure appetite decision (owner) + stale-clone
    inventory.
45. Ops-runbook: operator-window section (URLs, auth, what each card
    means), fax receive procedure, conference pin notes.
46. deploy.md: verify checklist gains the operator/fax/phoneApi probes.
47. README: mention operator window + fax + transfer in features list.
48. DOMAIN_LANGUAGE.md: add operator read-model terms (window-not-editor,
    phone-api, HMAC stream token).
49. P29 hardening: wire ahead-check into a systemd user timer or shell
    prompt; alert channel for repeated failures.
50. If the full gate is green and the owner wants it: cut 0.3.0 (tag +
    gh release) with the caller-controls behavior change prominent.

## g) QUESTIONS (cannot resolve myself)

1. **Concurrent sessions**: a `gwAuthAcl` gateway-auth-ACL feature (landed
   earlier) and a fresh uncommitted `opsTools.enable` option (appeared in
   options.nix during this session) are in the tree. Are both yours and
   expected to survive the full gate as-is, or should the gate run after
   they settle?
2. **Release posture**: if the full gate goes green — cut 0.3.0 now (the
   `#`-no-longer-hangs-up conference change is user-visible), or hold the
   tag until the first real call per the original P18 gating?
3. **Demo-VM ssh smoke (P23.3i)**: which private key on this machine
   matches a key in `nix-ssh-config.sshKeys` (path), or should the smoke
   generate a throwaway VM-local keypair instead (weaker proof, no owner
   dependency)?

---

## Session artifact map

- Suite logs: `/tmp/conf5.log`, `/tmp/conf6.log` (green),
  `/tmp/fax1.log`, `/tmp/fax2.log` (green), `/tmp/browser1.log` (green),
  `/tmp/operator{2,3,4,5}.log` (diagnosis ladder).
- Research source: `/home/lars/tmp-research/` (1.10.12 files — NOTE: the
  running nixpkgs FreeSWITCH is a NEWER split codebase
  (`conference_loop.c` etc.); the authoritative unpacked source fetched
  this session is `/nix/store/0094qdpwq56q585hzb1dkmmn6kqhbwf5-source`).
- Key commands that worked: per-suite
  `nix build --no-link -L --impure --expr 'let f = builtins.getFlake
  (toString /home/lars/projects/nix-international-telephony); in
  f.checks.x86_64-linux.<name>'` (honest exit codes, no pipes);
  parallel suites OK (124 GB RAM).
