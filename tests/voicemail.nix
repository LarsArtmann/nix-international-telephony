# Voicemail deposit and retrieval flows (M10 of the live-PBX plan):
#   * deposit: a scripted caller (tests/vmclient.py — SIP + real RTP +
#     RFC 4733 DTMF on top of tests/sip.py) dials a ring group whose
#     member never answers; after the group timeout the voicemail
#     fallback answers, the caller streams >= min-record-len seconds of
#     µ-law NOISE (silence would be discarded by mod_voicemail's
#     record-silence handling), and the message lands in the member's
#     box — proven by the msg_*.wav file appearing.
#   * retrieval: dial *98, enter the PIN as telephone-event digits;
#     mod_voicemail auto-plays new messages after login, which the
#     client measures as real RTP bytes flowing back.
#   * denial: three wrong PINs exhaust max-login-attempts and the
#     server plays goodbye and hangs the session up — the wrong-PIN
#     path is asserted server-side, not just by absence of playback.
#
# mod_voicemail facts relied on (min-record-len=3, auto-play after
# login, max-login-attempts=3) verified against upstream v1.10.12
# src/mod/applications/mod_voicemail/mod_voicemail.c.
let
  common = import ./common.nix;
in
{
  name = "telephony-voicemail";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;

      environment.etc."vmclient.py".source = ./vmclient.py;

      services.telephony = {
        # Explicit PIN proves the vm-password wiring (default would be
        # the extension number).
        extensions."1000".vmPassword = "1234";

        # Dedicated group with a short timeout so the deposit leg
        # reaches voicemail quickly (extension dial hardcodes 30 s).
        ringGroups."3000" = {
          members = [ "1000" ];
          timeoutSec = 6;
          voicemailMember = "1000";
        };
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")

    sip_ip = sip_server(machine)
    vmclient = (
        "python3 /etc/vmclient.py --server " + sip_ip + " --domain pbx.test "
    )

    # --- Deposit: ring group times out, voicemail answers, noise lands ---
    # The spoken greeting ("the person at extension ... is unavailable")
    # runs ~10 s before the record beep; the noise window must cover it
    # plus >= min-record-len (3 s) of actual recording.
    out = machine.succeed(
        vmclient
        + "--user 1001 --password test-1001-u6t5s4 "
        + "deposit --to 3000 --seconds 25"
    )
    assert "VM-DEPOSIT-ANSWERED" in out, out
    assert "VM-DEPOSIT-BYE" in out, out

    try:
        # NOTE: freeswitch runs as a DynamicUser, so its StateDirectory is
        # namespaced — on the host filesystem the box lives under
        # /var/lib/private/freeswitch (and /var/lib/freeswitch is a
        # symlink find does not follow). Search /var/lib wholesale.
        machine.wait_until_succeeds(
            "test -n \"$(find /var/lib -path '*voicemail*' -name 'msg_*.wav' 2>/dev/null)\"",
            timeout=datetime.timedelta(seconds=30),
        )
    except Exception:
        for cmd in [
            "find / -name 'msg_*.wav' 2>/dev/null | head -5",
            "find /var/lib -name '*.wav' -mmin -5 2>/dev/null | head -10",
            "ls -la /var/lib/freeswitch/ /var/lib/freeswitch/storage 2>&1",
            "journalctl -u freeswitch --no-pager -n 120",
        ]:
            _, dump = machine.execute(cmd)
            print(f"DIAG: {cmd}\n{dump}")
        raise

    # --- Denial: a wrong PIN never reaches the message ---
    # Deterministic proof via the voicemail index DB: the deposited
    # message is UNREAD (read_epoch = 0) until a successful login plays
    # it. After a wrong-PIN session it must stay untouched.
    vm_db = "/var/lib/private/freeswitch/db/voicemail_default.db"
    read_sql = (
        "python3 -c 'import sqlite3;"
        "c=sqlite3.connect(\"" + vm_db + "\");"
        "print(c.execute(\"select read_epoch from voicemail_msgs\").fetchone()[0])'"
    )
    machine.succeed("test -s " + vm_db)
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "check --pin 9999 --listen-seconds 12"
    )
    assert "VM-CHECK-ANSWERED" in out, out
    unread = machine.succeed(read_sql).strip()
    assert unread == "0", f"wrong PIN marked the message read (read_epoch={unread})"

    # --- Retrieval: *98 + PIN navigates and the message actually plays ---
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "check --pin 1234 --listen-seconds 15"
    )
    assert "VM-CHECK-ANSWERED" in out, out
    rtp_bytes = 0
    for line in out.splitlines():
        if line.startswith("VM-CHECK-RTP"):
            rtp_bytes = int(line.split("bytes=")[1].split()[0])
    # Phrase macros + the deposited message at ~86 kB/s PCMU. The
    # hello-only failure mode streams ~2.4 kB; a real summary+message
    # playback is an order of magnitude more.
    assert rtp_bytes > 12000, f"message playback streamed only {rtp_bytes} bytes:\n{out}"
    assert "VM-SERVER-HANGUP no" in out, out
    assert "VM-CHECK-BYE" in out, out
    # The successful login PLAYED the message: mod_voicemail marks
    # played new messages read at the end of the pass — impossible
    # without the correct PIN.
    machine.wait_until_succeeds(
        f"! {read_sql} | grep -q '^0$'", timeout=30
    )
  '';
}
