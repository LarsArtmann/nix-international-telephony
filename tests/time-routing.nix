# Time-based routing VM test (M23 of the live-PBX plan): a ring group
# with a timeWindow rings during business hours and transfers to the
# after-hours destination outside them. The VM clock is set explicitly
# to place the call inside and outside the window (FreeSWITCH evaluates
# date-time conditions against the live system clock).
let
  common = import ./common.nix;
in
{
  name = "telephony-time-routing";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;

      services.telephony.ringGroups."2100" = {
        members = [ "1000" ];
        timeoutSec = 4;
        timeWindow = {
          # Ring only in the 03:00-04:59 window (the test sets the clock
          # into and out of it deterministically).
          days = [
            "sun"
            "mon"
            "tue"
            "wed"
            "thu"
            "fri"
            "sat"
          ];
          startHour = 3;
          endHour = 4;
          afterHoursDestination = "9196"; # echo test: audible proof
        };
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    fs_cli = "fs_cli -p test-es-4d5e6f -x"


    sip_ip = sip_server(machine)
    sip = (
        "python3 /etc/sip.py --server " + sip_ip + " --domain pbx.test "
        "--user 1001 --password test-1001-u6t5s4"
    )

    # --- Inside the window: the group rings (falls to member voicemail) ---
    # Stop time synchronization FIRST: timesyncd snaps the clock back to
    # host time otherwise and the "03:30" leg silently runs out-of-window.
    machine.succeed("systemctl stop systemd-timesyncd.service || true")
    machine.succeed("timedatectl set-ntp false || true")
    machine.succeed("date -s '03:30:00'")
    machine.succeed("hwclock -w 2>/dev/null || true")
    machine.succeed(f"{fs_cli} 'reloadxml'")
    machine.succeed(
        f"{sip} invite --to 2100 --hold-seconds 12 --expect-status 200"
    )
    machine.wait_until_succeeds(
        "journalctl -u freeswitch --no-pager | grep -q 'voicemail(default pbx.test 1000)'",
        timeout=30,
    )

    # --- Outside the window: after-hours destination (echo) answers ---
    machine.succeed("date -s '12:00:00'")
    machine.succeed("hwclock -w 2>/dev/null || true")
    machine.succeed(f"{fs_cli} 'reloadxml'")
    out = machine.succeed(
        f"{sip} invite --to 2100 --hold-seconds 4 --expect-status 200"
    )
    assert "ANSWERED" in out, out
    machine.wait_until_succeeds(
        "journalctl -u freeswitch --no-pager | grep -q 'Processing 1001 <1001>->9196'",
        timeout=30,
    )
  '';
}
