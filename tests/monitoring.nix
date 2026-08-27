# Health-monitoring VM test (M16 of the live-PBX plan): the
# telephony-health unit passes when the stack is up, fails loudly when a
# sofia profile is down, and fails when a register=true gateway cannot
# register (pointed at a port nothing listens on).
let
  common = import ./common.nix;
in
{
  name = "telephony-monitoring";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;

      services.telephony = {
        monitoring.enable = true;
        # Nothing listens here: the gateway registration can never succeed.
        gateways.dead = {
          proxy = "127.0.0.1:9";
          username = "user";
          password = "gw-secret";
          did = "15557770000";
          didDestination = "1000";
        };
      };
    };

  nodes.healthy =
    { ... }:
    {
      imports = common.baseNode;
      services.telephony.monitoring.enable = true;
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    fs_cli = "fs_cli -p test-es-4d5e6f -x"

    # --- Healthy stack: the check unit passes ---
    wait_for_freeswitch(healthy, "test-es-4d5e6f")
    healthy.succeed("systemctl start telephony-health.service")
    out = healthy.succeed("journalctl -u telephony-health --no-pager | tail -1")
    assert "telephony-health: ok" in out, out

    # --- Gateway REG check: dead gateway fails the unit ---
    # (give sofia a moment to attempt registration and settle on a bad state)
    machine.sleep(5)
    machine.wait_until_fails("systemctl start telephony-health.service")
    journal = machine.succeed("journalctl -u telephony-health --no-pager | tail -5")
    assert "dead is not REGED" in journal, journal

    # --- Profile check: stopping a profile fails the unit too ---
    machine.succeed("systemctl stop telephony-health.service || true")
    machine.succeed(f"{fs_cli} 'sofia profile internal stop'")
    machine.wait_until_fails("systemctl start telephony-health.service")
    journal = machine.succeed("journalctl -u telephony-health --no-pager | tail -5")
    assert "profile internal is not RUNNING" in journal, journal

    # --- Timer wiring: both hosts run the check automatically ---
    machine.succeed("systemctl list-timers telephony-health.timer --no-legend | grep -q telephony-health")
    healthy.succeed("systemctl is-enabled telephony-health.timer")
  '';
}
