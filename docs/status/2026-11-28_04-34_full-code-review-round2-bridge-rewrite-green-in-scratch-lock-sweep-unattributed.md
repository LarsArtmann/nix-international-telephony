# Full code review, round 2, session 3: main's Python suites are green again, the bridge rewrite is green in scratch (not landed), an unattributed lock sweep sits on main

> Snapshot written 2026-11-28 04:34 CET. Trigger: owner directive "READ,
> UNDERSTAND, RESEARCH, REFLECT ... Execute and Verify them one step at the
> time", then the interrupt for this report. Tree at `b39c4a8` (equal to
> `origin/main`; working tree clean except this report).

## Scope line: what this report verified, and what it did not

VERIFIED in this session, each by a command whose exit code was read
(tier in brackets):

- The stale bridge test rewritten against the opener the rewrite uses;
  `python3 -m unittest tests.test_telnyx_bridge` 82 of 82 (LOCAL), and
  the same job green in CI: run `46099802343` at `b39c4a8`, job "stdlib
  python suites (engine, bridge, agents, oidc)" success, with the job
  and step list read (CI).
- The rewritten bridge and its new tests IN SCRATCH (`/tmp/review-work`,
  a plain copy of the tree, outside git): 195 tests, four runs with
  ResourceWarning as error: runs 1, 3 and 4 OK (27 to 29 s each), run 2
  one failure, a timing margin in one test (section b). `ruff check` and
  `ruff format --check` clean on both files (LOCAL).
- The Ed25519 verifier and the tests' signer: four RFC 8032 vectors
  (TEST 1, 2, 3, SHA(abc)) extracted programmatically from
  rfc-editor.org/rfc8032.txt; the verifier accepts all four; the signer
  reproduces all four public keys and signatures byte for byte; OpenSSL
  3.5.9 verifies six generated keypairs (LOCAL, the OpenSSL oracle is
  not portable into CI).
- The media fetch mechanics on real loopback sockets: plain and TLS
  origins, a trickling body, trickled headers, a silent origin, a
  handshake that never completes, each cut at its deadline; certificate
  and host-name verification on (LOCAL).
- The public-address judgement for 50 addresses, probed against the
  bridge function (LOCAL); three gaps found and closed (section b).
- Telnyx's docs re-read on 2026-11-28: "Webhook fundamentals", "Python
  SDK webhooks", "Receiving Webhooks for Messaging" (READ).
- Relock gates 0 and 2 for the swept webphone rev `70d91cb784a9`: `nix
  build -L --no-link github:LarsArtmann/webphone/70d91cb784a9#webphone`
  exit 0 and `nix build -L --no-link .#webphone` exit 0 (LOCAL).
- The lock sweep attributed node by node from `git show` of the two
  lock files (READ); `python3 scripts/lock_guard.py` exit 1 with two
  FAIL lines (LOCAL).
- CI state read with `gh run list` and `gh run view` (CI), section d.

NOT verified, and why:

- Nothing of the rewrite is in the repo. Every "green" below means
  green in the scratch copy. The repo's bridge is the half-landed
  intermediate of the last session plus the test fix.
- No Nix evaluation ran on my changes. The five Nix files I edited in
  scratch passed `nix-instantiate --parse` only. `tests/eval.nix`'s two
  new arms, the conditional credential, the warning and the nginx
  directive have never been evaluated.
- The scratch `flake.nix` has a row for `tests/messaging-signature.nix`
  and that file DOES NOT EXIST YET. Landing `flake.nix` before the suite
  is written breaks the eval of every check.
- The full unittest discovery (now 479 tests in scratch: 366 minus 82
  plus 195) did not run. mypy, bandit and BuildFlow did not run on the
  new files.
- CI at `b39c4a8` was still running at report time: cross-arch eval
  green, VM suites in progress since 03:55 CET, the aggregate verdict
  pending.
- The lock sweep's gates 3 to 6 (fast eval, the six webphone suites
  with `--no-eval-cache`, the lens package build) did not run.

Proof tiers follow AGENTS.md: CI = origin run verdict with event and
job list read; LOCAL = command run in this session with its exit code
captured; READ = verified by reading, not executed.

## Verdict in one paragraph

Main's Python suites are green again (the one stale test is fixed and
CI proves it). The bridge rewrite of the last session turned out to
carry real defects on re-reading, among them a media deadline that
bounded nothing and a key parser that accepted the identity element, for
which every forged signature verifies. I rewrote those parts in a
scratch copy, grew the bridge tests from 82 to 195, and the work is
green there, but none of it is landed, the Nix side is parsed and never
evaluated, and one VM suite file is still missing. Separately, an
unidentified `nix flake update` sweep landed on main at 03:33 CET and
moved the webphone and pbx-lens pins without a CHANGELOG record, so
lock-guard is red locally and the aggregate CI step of run `46099802343`
is expected to fail on it. Of the 27-task plan, T01 to T05 are about 80
percent done in scratch; T06 to T27 are untouched.

## a) FULLY DONE

1. **Main's red cause removed.** `test_fetch_media_custom_cap_bounds_the_read`
   rewritten against the opener the bridge uses, asserting that no read
   asks for more than the headroom under the cap; `bridge.reset_caches()`
   added to the fixture. Daemon commit `caf5a70`. CI: run `46099802343`
   at `b39c4a8`, stdlib job success (CI).
2. **The bridge, re-reviewed line by line and rewritten where the
   reading found defects** (scratch `modules/telephony/telnyx-webhooks.py`,
   1,825 to 2,121 lines, 986 changed lines):
   - Ed25519: the key parser now refuses the identity element. Before,
     a credential of `01` followed by 31 zero bytes parsed, and for that
     key every forged signature verifies. The timestamp must be plain
     digits (the former `int()` accepted underscores and non-ASCII
     digits and could crash the request). The comma-separated signature
     list of the last session is removed: the docs do not describe it.
   - One inbound message is forwarded once, whatever Telnyx's retries
     do. A copy that arrives while the first is being forwarded now
     WAITS for that outcome instead of racing it (double post) or
     trusting it (a lost message when the first forward then fails); a
     copy that cannot wait gets 503. The delivered mark's expiry is
     checked when it is looked up (a bug the new tests found).
   - The media fetch is built on `http.client` instead of `urllib`:
     https only, no userinfo, and every address the host name yields
     must be public before a socket opens (name, judgement and connect
     in one step, so a name cannot answer public to the check and
     private to the connect), the
     certificate and host name verified, the TLS handshake under a
     select loop, and connect, handshake, headers and body under ONE
     total deadline per message. Redirects are followed only to https
     and public hosts, up to three hops. A declared length over the cap
     is refused before a byte is read; a truncated or empty body is
     refused; at most ten media are fetched per message.
   - The address judgement refuses multicast, the deprecated site-local
     space and NAT64 forms that carry a private IPv4 (three gaps the
     probe table found: `ipaddress` calls all three global).
   - Sends: an HTTP error's socket is always released; an error body
     that cannot be read is empty instead of a crash; the three Telnyx
     send functions share one call path; a success without a string
     `data.id` is an honest 502; `telnyx_rejection` survives every
     response shape (an `errors` object used to raise KeyError).
   - Credentials: one read path for all four files; a byte-order mark is
     tolerated; a Telnyx key with whitespace or non-ASCII inside is an
     actionable 502 instead of a crash.
   - The HTTP handler: an unexpected crash on a gateway route answers
     503 with "the message MAY already be on its way" instead of
     dropping the connection; the drain of an over-cap request is
     bounded in time as well as bytes (2 s); an unknown POST path gets
     one 404 and a close; a body that is not JSON is logged cut to
     64 KiB with its original length; a 100,000-deep nested body no
     longer crashes the handler; one journal line per event with id,
     type, status and outcome, written before the answer; the public
     peer is recorded from `X-Real-IP` when it is an address.
   - Attachments: one refusal text builder for both lanes; nothing is
     staged before every attachment passed (a refused caption or a bad
     second file used to leave orphans).
3. **The tests for it** (scratch `tests/test_telnyx_bridge.py`, 1,559 to
   3,494 lines, 82 to 195 tests): RFC 8032 vectors extracted from the
   RFC text by a script, an independent signer with its own point
   encoder, negative arms (tampered bits, non-canonical S and R, wrong
   lengths, nine refused key spellings including identity, order-2,
   order-4 and an off-curve point), the retry contract of `http_send`
   as a truth table, the delivery bookkeeping under concurrent copies,
   35 malformed event shapes, request framing on raw sockets (a lying
   Content-Length, 8.5 MiB really sent, a trickling peer), the SSRF pin
   (loopback, localhost, `::1`, `10.0.0.1`, the metadata address: no
   connection is even opened), TLS with an openssl-generated
   certificate (trusted, untrusted, mis-named, never-completing
   handshake). The fixture's servers stop in 50 ms, so the module runs
   in 27 s where 82 tests took 66 s.
4. **Relock gates 0 and 2 for the swept webphone rev** (section d).
5. **Scratch work backed up outside `/tmp`**:
   `~/.cache/nix-telephony-review-backup/` (a tarball and a full copy
   of `/tmp/review-work`, made 04:34 and 04:36 CET).

## b) PARTIALLY DONE

### T01 to T05: the bridge batch (in scratch, not landed)

- The Python part is complete and green (three of four runs). One
  test is timing sensitive: the HTTP-level signature test offsets its
  timestamps by 301 s, and under load a second can pass between
  capturing "now" and the delivery, which puts the offset on the 300 s
  boundary. The fix is a wider offset (the exact boundary is pinned by
  the unit test with a patched clock). Not applied.
- Nix wiring, parsed only:
  - `messaging.webhookPublicKeyFile` option
    (`modules/telephony/options.nix`, +22 lines);
  - the fourth `LoadCredential` when the option is set, and a warning
    when messaging is on without it (`modules/telephony/messaging.nix`);
  - `clientAddressHeader = "X-Real-IP"` on the webhook route-table
    entry and `proxy_set_header X-Real-IP $remote_addr;` on the nginx
    location (`modules/telephony/web.nix`), with the option description
    extended;
  - two eval arms in `tests/eval.nix` (`messagingSignatureCheck`,
    `messagingNoKeyCheck`, +58 lines) wired into the check list and the
    shell loop;
  - a `telephony-messaging-signature` row in `flake.nix`.
- `tests/sign_webhook.py` is written (89 lines): signs and posts one
  webhook the way Telnyx does, for the VM suite.
- NOT done in this batch: the VM suite `tests/messaging-signature.nix`
  (design below), any `nix eval` or `nix fmt` on these files, the
  CHANGELOG entry, the runbook recipe, the FEATURES and
  DOMAIN_LANGUAGE rows, the Telnyx doc facts, the documented test and
  check counts (479 tests, 55 checks once the suite exists), mypy and
  bandit, and the landing itself.

Design decided for the VM suite (to write next): `common.baseNode` with
messaging on and the key file set, `tests/sign_webhook.py` installed to
`/etc`, a deterministic seed and public key (already generated with the
RFC-pinned signer); asserts the mounted `telnyx_public_key` credential,
`"webhook_signature": "required"` on `/gateway/health`, an unsigned POST
403 on loopback and through `https://pbx.test` with no line in
`inbound.jsonl`, a signed POST 200 on both paths (the two headers must
survive the edge), a tampered body 403, and a client-sent `X-Real-IP`
overwritten by the edge but honoured on the direct loopback path.

### The lock sweep on main (noticed, gates 0 and 2 run, nothing healed)

Commit `b39c4a8` (2026-11-28 03:33 CET, daemon, heuristic message, seven
files) moved seven lock nodes: `webphone` `75913f1a9a31` to
`70d91cb784a9`, `pbx-lens` `0b83c4f1f0a7` to `f22a5d4edaef`, `nixpkgs`,
`treefmt-nix`, `git-hooks-nix`, `disko`, and `docs-gates` (whose
declaration changed from a pinned rev to `ref: v0.3.1`, inherited from
the moved inputs). The same commit carried a formatter sweep
(`FEATURES.md`, `docs/DOMAIN_LANGUAGE.md`, two status reports,
`tests/browser-e2e.py`, and one line in the bridge: `.encode("utf-8")`
to `.encode()`). No nix process was running in this tree when I looked
at 03:50 CET; the nix processes on the machine belonged to SystemNix,
crush-daily and a worktree. `scripts/lock_guard.py` fails: neither
tracked rev is mentioned in `CHANGELOG.md`.

## c) NOT STARTED

- T06 and T07: operator `api.py`. T08: `oidc_session.py`. T09 to T11:
  `text-agent.py`. T12 to T14: `fs-directory.py` and `voice-agent.py`.
  T15 and T16: `dialplan_sim.py`, `operator.js`, `recordings_view.py`.
  T17 and T18: `telnyx_reconcile.py`, `verify-live.sh`, the lock and
  hook scripts. T19 to T22: the Nix items. T23: the remaining review
  slices. T24 and T25: doc drift, TODO harvest, archive ritual. T26:
  the review HTML. T27: final verification.
- Everything listed as not done under section b.

## d) TOTALLY FUCKED UP

1. **Main was red for about seven hours because of me.** The daemon
   pushed the half-landed rewrite at 18:46 CET; the stdlib job failed
   from 18:48 CET (runs `46044392762`, `46072803974`, `46072844583`,
   `46088071210`); the fix landed at 03:47 CET. I spent the first hour
   of this session on CI forensics and design reading before I touched
   the failing test.
2. **The last session's rewrite was reported as better than it was.**
   Its report said the media fetch "reads under one total deadline".
   As implemented, the deadline was only checked between reads, a peer
   trickling one byte per timeout window could hold a thread for days,
   and a body cut by the deadline was returned as a complete medium. The
   `urllib` opener also honoured proxy environment variables, so a set
   `https_proxy` would have bypassed the public-address gate. The
   identity-key hole, the in-flight redelivery race, the KeyError in
   `telnyx_rejection`, the leaked HTTP error sockets and the unbounded
   raw log entry were all in that code. I wrote that code and then
   documented it from intent, not from probes.
3. **A doc "fact" of the last session was my invention.** "Several
   signatures may travel in one header during a key rotation" is in no
   Telnyx page I read. The code comment asserted it as Telnyx's
   behaviour. Removed.
4. **The lesson about `/tmp` was written down and then not followed.**
   The last report says subagent findings belong in the repo. This
   session I found `/tmp/review-plan` gone at the start and
   `/tmp/review-notes` gone by 04:36 CET; with it the file holding the
   20 docs-tooling findings. The list survives in the last report
   (section f, item 24); the detail is lost. My own scratch sat in
   `/tmp/review-work` for five hours before I backed it up.
5. **The scratch `flake.nix` is broken on purpose and must not land**:
   it names a suite file that is not written.
6. **The todo list was not touched for the whole session.** It still
   showed the state of 22:53 CET.
7. **The lock sweep was seen at 03:50 CET and not reported until now.**
   I started the two cheap gates and went back to the bridge. The
   executor is unidentified; the remaining gates and the CHANGELOG
   record are not done; the aggregate CI step of run `46099802343` is
   expected to fail on lock-guard (prediction, the run was still going).
8. **Pace.** Five and a half hours moved two of 27 tasks. The plan's
   30-hour estimate for all 27 at this depth is wrong by a large factor;
   the plan needs re-basing on what this session measured.
9. A sibling edit to the bridge (the `.encode()` line, 03:33 CET) shows
   another session touches the file I am rewriting. My scratch copy
   would overwrite that one line (the rewrite subsumes it), but I did
   not coordinate.

## e) WHAT WE SHOULD IMPROVE

Process:

- Land in small green batches. A file saved to the repo is pushed
  within minutes; a rewrite must be developed outside the tree (as this
  session did) and copied in complete, with its tests and its documented
  counts, in one command.
- Restore a red main before anything else. The fix here was a ten-line
  test change that waited an hour behind reading.
- Keep every scratch artifact outside `/tmp` from the first minute
  (`~/.cache/...`), and put subagent findings into the repo the moment
  they arrive.
- A claim about behaviour in a durable doc needs the probe that shows
  it. "Reads under a deadline" needed a trickling peer to be true.
- Verify external facts at the moment they are encoded, and re-verify
  on return: the docs changed nothing, but my memory of them had.
- After a daemon commit, read what it contains before building on the
  tree: `b39c4a8` mixed a formatter sweep, a sibling's edit and a lock
  move in one commit.

Technical, in priority order:

- The webhook handler acknowledges Telnyx only after the media fetch and
  the webphone forward. Telnyx documents a 2-second limit and says not
  to download media before acknowledging; our nginx location cuts the
  upstream read at 10 s. Today correctness rests on the new claim and
  wait logic plus Telnyx's retries. The sound shape is acknowledge
  first, process in a worker with a durable record (the JSONL already
  holds every event).
- The delivered set is in memory: a unit restart forgets it. A restart
  inside Telnyx's retry window, or a replay of a captured signed
  request within five minutes after a restart, forwards twice. Telnyx's
  docs ask for a persistent store.
- The media fetch is synchronous per medium; a message with ten large
  media can hold a handler thread for the whole 30 s deadline.
- nginx has no `client_max_body_size` on the webhook location (default
  1 MiB, the bridge's cap is the same); fine today, but two homes for
  one number.
- The key option is opt-in with a warning. The default stays open until
  the owner decides (question 1 of the last report, still open).
- In "external" edge mode the host renders its edge from the route
  table; the new `clientAddressHeader` field is a contract that
  renderer must learn (pbx-artmann).

## f) NEXT (ranked; 1 to 9 close what is in flight)

1. Land the Python batch: copy the scratch bridge and test file into
   the repo in one command together with the AGENTS.md test count
   (366 to 479); run the module, the full discovery, `ruff check` and
   `ruff format --check`; read CI after the daemon pushes.
2. Widen the HTTP-level timestamp offsets of the signature test (301 to
   600 s) so the boundary cannot be hit under load; re-run the module
   four times.
3. Write `tests/messaging-signature.nix` per the design in section b;
   run it: `nix build -L --no-eval-cache .#checks.x86_64-linux.telephony-messaging-signature`.
4. Evaluate the Nix wiring: `nix build -L .#checks.x86_64-linux.telephony-eval --no-link`
   (the two new arms must print PASS), then `nix fmt`.
5. Land the Nix batch (options, messaging, web, eval, flake row, the
   suite, the signer) with the FEATURES check count (54 to 55); read
   CI.
6. CHANGELOG [Unreleased]: Security (signature gate, SSRF gate, media
   deadline), Fixed (identity key, the race, the crashes), Changed (the
   new option, the warning, `X-Real-IP`), each with its gate.
7. Docs: runbook recipe "Webhook signatures" (where the key lives, how
   to spell it, the 503 on a bad key, the health field), FEATURES row
   text, a DOMAIN_LANGUAGE term, the Telnyx facts in
   `docs/providers/telnyx.md` with the access date 2026-11-28.
8. Lock sweep `b39c4a8`: read the verdict of run `46099802343`; run
   `scripts/relock-ladder.sh` (gates 3 to 4; gate 5 only on upstream
   markup deltas); build the lens package; write the CHANGELOG record
   with old and new revs and the why; name the executor if the owner
   knows it (question 1).
9. Update `AGENTS.md`: the loopback-only lessons that endure (a socket
   timeout is per read; `socket.socket(fileno=)` takes the descriptor,
   it does not duplicate it; `ipaddress` calls multicast and NAT64 of a
   private address global; RFC 8032 long-message vectors are garbled in
   the text rendering).
10. Re-base the round-2 plan on the measured pace: 27 tasks at the
    depth of T01 to T05 is several sessions; move T06 to T27 into
    `TODO_LIST.md` with a size estimate each.
11. Persist the 20 docs-tooling findings in `TODO_LIST.md` from the
    last report (section f, item 24) before the detail is needed again.
12. T06 and T07: operator `api.py` (report items 8, 23, 24, 28): the
    `CONFIG is None` 500 on `/healthz` seen in every CI log, plus its
    unit tests.
13. T08: `oidc_session.py` (items 9, 10).
14. T09 to T11: `text-agent.py` (items 11 to 17).
15. T12 to T14: `fs-directory.py` and `voice-agent.py` (items 18 to 22).
16. T15 and T16: `dialplan_sim.py`, `operator.js`, `recordings_view.py`
    (items 25 to 27).
17. T17: `telnyx_reconcile.py` and `verify-live.sh` (items 32 to 36).
18. T18: the lock and hook scripts (items 32 to 36) and the 20
    docs-tooling fixes.
19. T19 to T22: the Nix items (items 29 to 31, 37 to 44): one-home
    literals, warnings, lens, agent and fax-feed hardening, types.
20. T23: the three remaining review slices by two read-only subagents
    at a time (Python tests, VM suites and `eval.nix`,
    `packages/`, `hosts/`, CI).
21. Follow-up session: acknowledge-first webhook processing with a
    worker and a durable record (section e).
22. Follow-up: a persistent delivered set (section e).
23. Follow-up: the default for webhook signatures (owner decision).
24. pbx-artmann: set `messaging.webhookPublicKeyFile`, and teach its
    edge renderer the `clientAddressHeader` route field.
25. Add the bridge's `/gateway/health` to the operator dashboard as a
    card that shows `webhook_signature` (today only curl shows it).
26. T24: doc drift (FEATURES, DOMAIN_LANGUAGE) after the batches land.
27. T25: harvest both 2026-11-27 reports and this one into
    `TODO_LIST.md`; archive ritual with the marker and rendering gates.
28. T26: the review report HTML at `docs/reviews/`.
29. T27: final verification (full discovery, `nix fmt`, telephony-eval,
    BuildFlow, CI tip verdict).
30. Decide the pure-Python verifier against PyNaCl (question 3 of the
    last report, still open; the identity and subgroup findings are an
    argument for a maintained implementation).

## g) QUESTIONS FOR THE OWNER

1. **The lock sweep in `b39c4a8` (03:33 CET).** Was that you or another
   session updating the inputs on purpose? If yes, who writes the
   CHANGELOG record and runs the relock ladder; if no, it is another
   unidentified `nix flake update` and I will run the ladder and write
   the record. I cannot tell a deliberate relock from a sweep: the
   daemon's message carries neither.
2. **Who else edits this tree?** Something ran a formatter sweep and
   changed one line of the bridge at 03:33 CET while I was rewriting it.
   Is a session assigned to this repo besides mine, and is
   `modules/telephony/telnyx-webhooks.py` in its lane? My copy would
   overwrite that one line (it is subsumed), but I would rather know
   before I copy a 2,100-line file over someone's work.
3. **The webhook design.** Telnyx documents a 2-second acknowledgement
   limit and advises against downloading media before acknowledging;
   the bridge fetches media and calls webphone first, so nginx cuts it
   at 10 s and Telnyx retries. Do you want the acknowledge-first
   redesign (worker plus durable record) planned as its own session, or
   the synchronous design kept with the claim and wait logic as its
   safety net?
