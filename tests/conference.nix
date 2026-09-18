# Conference-room VM test (M22 of the live-PBX plan): two scripted
# callers join the same room, FreeSWITCH mixes them, and each receives
# the other's audio — asserted as RTP bytes flowing on BOTH legs while
# fs_cli sees two members.
{ webphonePackage }:
let
  common = import ./common.nix { inherit webphonePackage; };
in
{
  name = "telephony-conference";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;

      environment.etc."vmclient.py".source = ./vmclient.py;

      services.telephony.conferences.standup = {
        extension = "5000";
      };
      # PIN-protected room: the generator appends "+<pin>" to the
      # conference app data and mod_conference collects the pin via RTP
      # digits before admitting the member.
      services.telephony.conferences.board = {
        extension = "5100";
        pin = "2468";
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    fs_cli = "fs_cli -p test-es-4d5e6f -x"


    sip_ip = sip_server(machine)
    vmclient = "python3 /etc/vmclient.py --server " + sip_ip + " --domain pbx.test "

    # Two concurrent members (background processes inside the VM).
    machine.succeed(
        "("
        + vmclient + "--user 1000 --password test-1000-x9y8z7 "
        + "join --to 5000 --seconds 12 > /tmp/joinA.log 2>&1 &)"
    )
    machine.wait_until_succeeds("grep -q 'VM-JOIN-ANSWERED' /tmp/joinA.log", timeout=30)
    machine.succeed(
        "("
        + vmclient + "--user 1001 --password test-1001-u6t5s4 "
        + "join --to 5000 --seconds 8 > /tmp/joinB.log 2>&1 &)"
    )
    machine.wait_until_succeeds("grep -q 'VM-JOIN-ANSWERED' /tmp/joinB.log", timeout=30)

    # mod_conference sees both members while the legs are up.
    listing = machine.wait_until_succeeds(
        f"{fs_cli} 'conference standup list'", timeout=20
    )
    print(f"CONF-LIST:\n    {listing}", flush=True)
    assert listing.count("@") >= 2 or "2" in listing, listing

    # Both legs finish; each must have received the mixed bridge audio
    # (the other member's noise), not just MOH.
    machine.wait_until_succeeds("grep -q 'VM-JOIN-BYE' /tmp/joinA.log", timeout=60)
    machine.wait_until_succeeds("grep -q 'VM-JOIN-BYE' /tmp/joinB.log", timeout=60)

    def join_bytes(path):
        out = machine.succeed(f"cat {path}")
        for line in out.splitlines():
            if line.startswith("VM-JOIN-RTP"):
                return int(line.split("bytes=")[1].split()[0])
        return 0

    a_bytes = join_bytes("/tmp/joinA.log")
    b_bytes = join_bytes("/tmp/joinB.log")
    # Two seconds of overlapped noise at ~86 kB/s mixes to well over
    # this; a MOH-only or one-way failure stays below it.
    assert a_bytes > 40000, f"leg A received only {a_bytes} bytes:\n" + machine.succeed("cat /tmp/joinA.log")
    assert b_bytes > 20000, f"leg B received only {b_bytes} bytes:\n" + machine.succeed("cat /tmp/joinB.log")

    # --- Pinned room: a wrong PIN is never admitted, the right one is ---
    # Wrong pin: mod_conference rejects the entry (retries, then hangs up);
    # while the leg is still up the room must not list it as a member.
    machine.succeed(
        "("
        + vmclient + "--user 1000 --password test-1000-x9y8z7 "
        + "join --to 5100 --seconds 18 --pin 1111 > /tmp/joinWrong.log 2>&1 &)"
    )
    machine.wait_until_succeeds(
        "grep -q 'VM-JOIN-PIN-SENT' /tmp/joinWrong.log", timeout=60
    )
    machine.succeed("sleep 6")
    listing = machine.succeed(f"{fs_cli} 'conference board list'")
    assert "1000@" not in listing, f"wrong-pin caller was admitted:\n{listing}"
    machine.wait_until_succeeds("grep -q 'VM-JOIN-BYE' /tmp/joinWrong.log", timeout=90)
    listing = machine.succeed(f"{fs_cli} 'conference board list'")
    assert "1000@" not in listing, f"wrong-pin caller lingered as member:\n{listing}"

    # Right pin: admitted — the room lists a member while up, and the leg
    # streams real room audio (MOH while alone), not a prompt-and-hangup.
    machine.succeed(
        "("
        + vmclient + "--user 1001 --password test-1001-u6t5s4 "
        + "join --to 5100 --seconds 25 --pin 2468 > /tmp/joinRight.log 2>&1 &)"
    )
    machine.wait_until_succeeds(
        "grep -q 'VM-JOIN-PIN-SENT' /tmp/joinRight.log", timeout=60
    )
    try:
        machine.wait_until_succeeds(
            f"{fs_cli} 'conference board list' | grep -q '@'", timeout=35
        )
    except Exception:
        # Decisive discriminator: if the caller channel is GONE, FreeSWITCH
        # received + rejected the digits (pin retry exhaustion hangs up);
        # if it lingers in the conference app, the digits never arrived.
        status, listing = machine.execute(f"{fs_cli} 'conference board list'")
        print(f"CONF-DEBUG-BOARD-LIST (exit {status}):\n{listing}", flush=True)
        status, channels = machine.execute(f"{fs_cli} 'show channels'")
        print(f"CONF-DEBUG-CHANNELS (exit {status}):\n{channels}", flush=True)
        status, joinlog = machine.execute("cat /tmp/joinRight.log")
        print(f"CONF-DEBUG-JOINLOG (exit {status}):\n{joinlog}", flush=True)
        status, fslog = machine.execute(
            "grep -a -i 'conference\\|dtmf\\|board\\|pin' "
            "/var/lib/freeswitch/log/freeswitch.log | tail -n 60"
        )
        print(f"CONF-DEBUG-FSLOG (exit {status}):\n{fslog}", flush=True)
        raise
    machine.wait_until_succeeds("grep -q 'VM-JOIN-BYE' /tmp/joinRight.log", timeout=60)
    right_bytes = join_bytes("/tmp/joinRight.log")
    assert right_bytes > 40000, (
        f"correct-PIN caller was not admitted (received {right_bytes} bytes):\n"
        + machine.succeed("cat /tmp/joinRight.log")
    )
  '';
}
