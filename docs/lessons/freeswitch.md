# FreeSWITCH lessons (long-form)

Moved verbatim from AGENTS.md 2026-09-16 to keep that file under its
line cap. AGENTS.md carries one-line pointers; the full stories live
here. Annotate, never rewrite — append new lessons at the bottom.

## Nix string escaping for FreeSWITCH XML

In indented strings write `''$''${var}` for a literal `$${var}` (FS
pre-processor variable) and `''${var}` for a literal `${var}` (channel
variable). `nix eval` prints dollars escaped as `\$` — do not "fix"
working code because output looks doubled. Same trap in Python
`testScript` blocks: any shell-level `''` (e.g. `ssh-keygen -N ''`)
TERMINATES the indented Nix string — use `""` or `'''` there, or you
get a baffling "syntax error, unexpected '>'" pointing at unrelated
later lines.

## Sounds URLs need the rate component

`freeswitch-sounds-en-us-callie-8000-1.0.52.tar.gz` (the name without
`-8000-` 404s). Music pack: `freeswitch-sounds-music-8000-1.0.52.tar.gz`.

## Upstream module shape

The upstream `services.freeswitch` module copies `${package}/share/
freeswitch/conf/vanilla` and overlays `configDir`; our overrides must not
rely on `X-PRE-PROCESS` includes of template subdirectories we replaced.
`freeswitch` builds/substitutes from cache.nixos.org; VM tests are cheap.

Module list loaded by our config is deliberately minimal and must match
the modules compiled into nixpkgs' freeswitch (no mod_av, no
mod_signalwire, no mod_verto in ours). The nixpkgs build ships
`mod_spandsp` (the `rxfax`/`txfax`/`t38gateway` fax apps) but NOT the
legacy `mod_fax` — any fax work starts from mod_spandsp (fax posture:
docs/providers/).

`event_socket.conf.xml` is overridden to 127.0.0.1 with a configured
password; `fs_cli -p <password> -x "<cmd>"` in tests/ops. Sofia profiles
up ≠ event socket ready: mod_event_socket binds 8021 late in startup;
`fs_cli` right after the 5060 listener check raced it (`Error
Connecting`). The shared `wait_for_freeswitch` helper waits for a 8021
listener too.

Vanilla `acl.conf.xml` `domains` list (default deny) is unused by us:
our internal profile has no `apply-inbound-acl`, auth is digest
(`auth-calls`). When `gateway.allowedCidrs` is set we emit our own
`acl.conf.xml` (list `trusted-itsp`) and point the external profile's
`apply-inbound-acl` at it.

## Dialplan anti-action fires on CONDITION failure, never bridge failure

Shipping anti-action voicemail fallbacks inside extension/ring-group
entries made FreeSWITCH answer (200 OK + voicemail) every call whose
number did not match that entry — E.164 denial paths and unknown numbers
never reached their reject extensions. Found via VM-test siptrace +
`console loglevel debug` EXECUTE lines. Correct pattern for
bridge-failure fallback: plain `<action>`s listed after `bridge` with
`continue_on_fail=true` and `hangup_after_bridge=true` (they only run
when the bridge fails). Denial extensions use `hangup` with a mapped
cause; observed SIP mappings: `call_rejected`→603,
`normal_temporary_failure`→503, `unallocated_number`→404.

## SIP auth challenge specifics for scripted clients (tests/sip.py)

REGISTER is challenged with 401 + `WWW-Authenticate`, INVITE with 407 +
`Proxy-Authenticate`; answer with `Authorization` vs
`Proxy-Authorization` accordingly. In the test VM sofia binds
5060/5061/5080 on 127.0.0.1.

## DTMF from scripted clients must be RFC 4733 telephone-event RTP

(`RtpStream.send_digit` in tests/vmclient.py). sofia's ONLY dtmf-relay
INFO parser looks for `Signal=` (equals) behind the off-by-default
`extended-info-parsing` profile flag — "Signal: <d>" (colon) INFOs are
200-OK'd and silently dropped, so every Signal-colon digit in this
repo's history was theater (the voicemail PIN legs passed vacuously on
re-prompt phrase audio; the IVR suite never actually passed). Digits
sent WHILE a phrase macro or prompt plays are eaten as its cancel
input — send them after the collector starts (voicemail *98 asks for
the MAILBOX ID first, then the PIN).

## mod_dialplan_xml parses a whole extension BEFORE executing it

Nested conditions and action-data `${vars}` are evaluated at PARSE
time, so routing on a variable set by play_and_get_digits in the same
extension can never work. Runtime menus use mod_dptools' `ivr` app
(registered name "ivr", NOT "menu") with menu definitions generated
into ivr.conf.xml — digits there are config data, immune to the trap.

## mod_voicemail emails

Go through the core `mailer-app` param in switch.conf.xml (verified in
switch_core.c), invoked as `/bin/cat <msg> | <app> -f <from> <args>
<to>` with the full RFC 5322 message on stdin — and `/bin/cat` DOES NOT
EXIST on stock NixOS, so the module symlinks it via tmpfiles when
`voicemail.mailerCommand` is set (without it the mailer silently
receives an empty message). vm-mailto alone sends NOTHING —
`vm-email-all-messages` is required (the generator emits both plus
`vm-attach-file`; insert_db defaults to 1 so the local copy for *98
stays). A VM catch-all writes under /var/lib/freeswitch
(StateDirectory, host-readable via /var/lib/private); NOT /tmp
(PrivateTmp).

## Gateway didDestination may target extensions OR ring groups

(The public-context transfer lands in the default dialplan where the
group answers). The reference assertion used to accept extensions only,
failing the natural trunk-DID-to-desk-phones shape; tests/eval.nix
`ringGroupDidEval` pins the behavior.

## sofia binds $${local_ip_v4} and silently falls back to 127.0.0.1

…when no default route exists yet (`switch_find_local_ip` UDP-connects
toward `82.45.148.209` and keeps its loopback pre-fill on failure). A
slow-network boot therefore yields a PBX bound to loopback only
(unreachable-until-restart in production); our unit orders after
`network-online.target`, and VM tests derive listener addresses from
`ss -ltn 'sport = :<port>'` instead of assuming `localhost` (this race
masqueraded as a "sofia profile-start wedge" for two sessions — the
DIAG `ss` dump eventually showed 5060/5061/5080 bound on eth0). When a
test dials the external profile while an ACL lists `127.0.0.1`, the
scripted client must `--bind 127.0.0.1` explicitly (the source address
follows the destination address otherwise).

## VM-test journal gotcha (sofia channels)

Sofia-channel dialplan `EXECUTE` lines for `sofia/internal/...`
channels do NOT reach the VM journal (loopback channels' do). Grep
`Processing <cid>-><dest>` INFO lines instead, or use `sofia global
siptrace on` + `console loglevel debug` for evidence. Post-startup
evidence in general (voicemail app lines, DTMF) is only in
`/var/lib/freeswitch/log/freeswitch.log` — green suites grep the FILE.
