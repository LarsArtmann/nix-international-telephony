# Health-monitoring VM test (M16 of the live-PBX plan): the
# telephony-health unit passes when the stack is up, fails loudly when a
# sofia profile is down, and fails when a register=true gateway cannot
# register (pointed at a port nothing listens on).
{ telephonyModule, webphonePackage }:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
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
      services.telephony = {
        monitoring.enable = true;
        # Exercise the health unit's webphone arm: /healthz is probed
        # only with the webphone enabled (the v2 UI is a service that
        # can die quietly — exactly what this arm makes loud).
        webphone.enable = true;
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    fs_cli = "fs_cli -p test-es-4d5e6f -x"

    # --- Healthy stack: the check unit passes ---
    wait_for_freeswitch(healthy, "test-es-4d5e6f")
    healthy.wait_for_unit("webphone.service")
    healthy.succeed("systemctl start telephony-health.service")
    healthy.succeed("journalctl -u telephony-health --no-pager | grep -q 'telephony-health: ok'")

    # --- Webphone probe: a dead webphone service fails the unit ---
    healthy.succeed("systemctl stop webphone.service")
    healthy.wait_until_fails("systemctl start telephony-health.service")
    journal = healthy.succeed("journalctl -u telephony-health --no-pager | tail -5")
    assert "webphone /healthz probe failed" in journal, journal
    # ... and recovers once the service is back.
    healthy.succeed("systemctl start webphone.service")
    healthy.wait_until_succeeds("systemctl start telephony-health.service")

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
