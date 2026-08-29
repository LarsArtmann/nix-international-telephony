# fail2ban SIP-jail VM test (M17 of the live-PBX plan): repeated
# REGISTER auth failures from one source IP end in a fail2ban ban of
# that address (the jail watches the FreeSWITCH journal). The scripted
# bad client binds 127.0.0.2 so the ban cannot cut the test's own leg.
let
  common = import ./common.nix;
in
{
  name = "telephony-fail2ban";

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;

      environment.systemPackages = [ pkgs.fail2ban ];

      services.telephony.fail2ban = {
        enable = true;
        maxretry = 3;
        findtime = 60;
        bantime = 60;
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")

    sip_ip = sip_server(machine)

    # Auth-failure spam from a dedicated source address.
    # fail2ban's default ignoreself rule skips loopback sources (they
    # count as "self"), so the scripted offender needs a non-loopback
    # source: a TEST-NET-2 address parked on lo for this test.
    machine.succeed("ip addr add 198.51.100.7/32 dev lo")
    bad = (
        "python3 /etc/sip.py --server " + sip_ip + " --bind 198.51.100.7 "
        + "--domain pbx.test --user 1000 --password definitely-wrong register"
    )
    for i in range(4):
        status, out = machine.execute(bad)
        print(f"BAD-REGISTER[{i}] status={status} out={out[:300]}")
        assert status != 0, out

    # fail2ban itself starts only once the freeswitch log file exists
    # (preStart wait) — feed the jail lines that are guaranteed to land
    # after its pyinotify watcher is up.
    machine.wait_until_succeeds(
        "fail2ban-client status freeswitch-sip | grep -q 'Status for the jail'",
        timeout=90,
    )
    for i in range(4, 8):
        status, out = machine.execute(bad)
        print(f"BAD-REGISTER[{i}] status={status} out={out[:300]}")
        assert status != 0, out

    # The jail sees the failures and bans 198.51.100.7.
    machine.wait_until_succeeds(
        "fail2ban-client get freeswitch-sip banned | grep -q 198.51.100.7",
        timeout=90,
    )
    # The other tests' source addresses stay unbanned.
    machine.succeed(
        "! fail2ban-client get freeswitch-sip banned | grep -q 127.0.0.1"
    )
  '';
}
