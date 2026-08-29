# Time-based routing VM test (M23 of the live-PBX plan): a ring group
# with a timeWindow rings during business hours and transfers to the
# after-hours destination outside them. The VM clock is set explicitly
# to place the call inside and outside the window (FreeSWITCH evaluates
# date-time conditions against its OWN monotonic-offset clock, which a
# restart re-reads from the system clock — see move_clock below).
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

    # FreeSWITCH's internal clock is monotonic-plus-offset and NEVER
    # follows a backwards system-clock jump (probed live: 60s of
    # strepoch/strftime polling kept printing the pre-jump wall time,
    # so the original date-s + reloadxml design routed the in-window
    # leg after-hours). A unit restart reads the wall clock at init —
    # the only deterministic way to move date-time conditions.
    def move_clock(node, when):
        node.succeed("date -s '" + when + "'")
        node.succeed("hwclock -w 2>/dev/null || true")
        node.succeed("systemctl restart freeswitch")
        wait_for_freeswitch(node, "test-es-4d5e6f")


    # Stop time synchronization first: timesyncd would otherwise snap
    # the clock back to host time between the legs.
    machine.succeed("systemctl stop systemd-timesyncd.service || true")
    machine.succeed("timedatectl set-ntp false || true")

    # --- Inside the window: the group rings (falls to member voicemail) ---
    move_clock(machine, "03:30:00")
    sip_ip = sip_server(machine)
    machine.succeed(
        "python3 /etc/sip.py --server " + sip_ip + " --domain pbx.test "
        "--user 1001 --password test-1001-u6t5s4 invite --to 2100 "
        "--hold-seconds 12 --expect-status 200"
    )
    # Post-startup sofia/dialplan lines do not reach the journal (the
    # console logger detaches) — the freeswitch.log FILE has them.
    machine.wait_until_succeeds(
        "grep -q 'voicemail(default pbx.test 1000)'"
        " /var/lib/freeswitch/log/freeswitch.log",
        timeout=datetime.timedelta(seconds=30),
    )

    # --- Outside the window: after-hours destination (echo) answers ---
    move_clock(machine, "12:00:00")
    sip_ip = sip_server(machine)
    out = machine.succeed(
        "python3 /etc/sip.py --server " + sip_ip + " --domain pbx.test "
        "--user 1001 --password test-1001-u6t5s4 invite --to 2100 "
        "--hold-seconds 4 --expect-status 200"
    )
    assert "ANSWERED" in out, out
    machine.wait_until_succeeds(
        "grep -q 'Processing 1001.*->9196'"
        " /var/lib/freeswitch/log/freeswitch.log",
        timeout=datetime.timedelta(seconds=30),
    )
  '';
}
