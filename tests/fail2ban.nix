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

    def sip_server(node):
        listener = node.succeed("ss -ltn 'sport = :5060' | grep -v State").strip()
        ip = listener.split()[3].rsplit(":", 1)[0]
        return "::1" if ip.startswith("[") else ip

    sip_ip = sip_server(machine)

    # Auth-failure spam from a dedicated source address.
    bad = (
        "python3 /etc/sip.py --server " + sip_ip + " --bind 127.0.0.2 "
        + "--domain pbx.test --user 1000 --password definitely-wrong register"
    )
    for _ in range(4):
        status, out = machine.execute(bad)
        assert status != 0, out

    # The jail sees the failures and bans 127.0.0.2.
    machine.wait_until_succeeds(
        "fail2ban-client get freeswitch-sip banned | grep -q 127.0.0.2",
        timeout=60,
    )
    # The other tests' source addresses stay unbanned.
    machine.succeed("! fail2ban-client get freeswitch-sip banned | grep -q 127.0.0.1")
  '';
}
