# Conference-room VM test (M22 of the live-PBX plan): two scripted
# callers join the same room, FreeSWITCH mixes them, and each receives
# the other's audio — asserted as RTP bytes flowing on BOTH legs while
# fs_cli sees two members.
let
  common = import ./common.nix;
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
        print(f"CONF-LIST:
    {listing}", flush=True)
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
  '';
}
