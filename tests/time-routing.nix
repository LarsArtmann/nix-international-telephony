# Time-based routing VM test (M23 of the live-PBX plan): a ring group
# with a timeWindow rings during business hours and transfers to the
# after-hours destination outside them.
#
# Clock strategy: each leg runs on its own node whose QEMU RTC base is
# fixed at build time, so the guest (and FreeSWITCH with it) BOOTS
# inside/outside the window. Moving a running VM's clock does not work:
# FreeSWITCH's internal clock is monotonic-plus-offset and never follows
# a backwards `date -s` jump (probed live), a post-jump unit restart
# re-reads the wall clock but CI runners saw the system clock itself
# revert to host time between the jump and the restart — RTC-based
# per-node boots eliminate the entire class.
let
  common = import ./common.nix;

  ringGroup = {
    members = [ "1000" ];
    timeoutSec = 4;
    timeWindow = {
      # Ring only in the 03:00-04:59 window (the RTC bases below place
      # one node inside it and one outside, deterministically).
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

  node =
    rtcBase:
    { ... }:
    {
      imports = common.baseNode;

      virtualisation.qemu.options = [ "-rtc base=${rtcBase}" ];

      services.telephony.ringGroups."2100" = ringGroup;
    };
in
{
  name = "telephony-time-routing";

  nodes.inwindow = node "2026-08-29T03:30:00";
  nodes.afterhours = node "2026-08-29T12:00:00";

  testScript = ''
    ${common.bootWait}

    # Post-startup sofia/dialplan lines do not reach the journal (the
    # console logger detaches) — the freeswitch.log FILE has them.
    def assert_file_log(node, pattern, what):
        node.wait_until_succeeds(
            "grep -q '" + pattern + "' /var/lib/freeswitch/log/freeswitch.log",
            timeout=datetime.timedelta(seconds=30),
        )


    def call(node, hold_seconds):
        sip_ip = sip_server(node)
        return node.succeed(
            "python3 /etc/sip.py --server " + sip_ip + " --domain pbx.test "
            "--user 1001 --password test-1001-u6t5s4 invite --to 2100 "
            "--hold-seconds " + hold_seconds + " --expect-status 200"
        )


    start_all()

    # --- Inside the window (03:30): the group rings, then member voicemail ---
    wait_for_freeswitch(inwindow, "test-es-4d5e6f")
    # Loud precondition: if anything dragged the clock back to host time,
    # fail here with evidence instead of silently routing the wrong leg.
    hour = inwindow.succeed("date +%H").strip()
    assert hour == "03", "inwindow node clock is " + hour + ", expected 03"
    call(inwindow, "12")
    assert_file_log(
        inwindow, "voicemail(default pbx.test 1000)", "voicemail fallback"
    )

    # --- Outside the window (12:00): after-hours destination (echo) answers ---
    wait_for_freeswitch(afterhours, "test-es-4d5e6f")
    hour = afterhours.succeed("date +%H").strip()
    assert hour == "12", "afterhours node clock is " + hour + ", expected 12"
    out = call(afterhours, "4")
    assert "ANSWERED" in out, out
    assert_file_log(
        afterhours, "Processing 1001.*->9196", "after-hours transfer"
    )
  '';
}
