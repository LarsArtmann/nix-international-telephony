# On-demand wall-clock smoke for the EXAMPLE DEMO HOST (hosts/pbx) —
# deliberately outside `checks` (boots the full demo stack: agent, lens,
# messaging, backups; the module boot shape is covered by telephony-boot
# and the timeWindow runtime semantics by time-routing). Run:
#   nix build -L .#legacyPackages.x86_64-linux.telephony-demo-wallclock
# Proves the wall clock surfaces everywhere the stack renders it (the
# 2026-10-26 timezone facade): the host zone, FreeSWITCH's runtime view
# (the ring-group timeWindow evaluates in the host zone), the webphone
# facade (/config.js settings.timezone), and the demo host's rendered
# after-hours window end to end — the RTC is pinned OUTSIDE the window,
# so the caller hears the echo test, not the ring group.
{
  telephonyModule,
  webphonePackage,
  sshModule,
  sshKeys,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  demoHost =
    { pkgs, ... }:
    {
      imports = [
        telephonyModule
        sshModule
        {
          services.ssh-server = {
            enable = true;
            authorizedKeys = sshKeys;
            allowRootLogin = true;
          };
        }
        ../hosts/pbx
        common.sipClientModule
      ];

      # Clock strategy from tests/time-routing.nix: a fixed RTC base boots
      # the guest outside the demo host's 8-20 window (Wednesday 22:30
      # Europe/Berlin), making the after-hours leg deterministic.
      virtualisation.qemu.options = [ "-rtc base=2026-11-11T22:30:00" ];
    };
in
{
  nodes.demo.imports = [ demoHost ];

  testScript = ''
    import datetime

    ${common.helpers}

    def demo_call(node, to, hold_seconds, password):
        sip_ip = sip_server(node)
        return node.succeed(
            "python3 /etc/sip.py --server " + sip_ip + " --domain pbx.example.com "
            "--user 1001 --password " + password + " invite --to " + to + " "
            "--hold-seconds " + hold_seconds + " --expect-status 200"
        )

    start_all()

    wait_for_freeswitch(demo, "demo-es-9f1e2c")
    # Loud clock precondition: the guest must have booted at 22:xx, the
    # pinned RTC (a backwards clock drift would silently re-enable the
    # ring group instead of the after-hours echo).
    hour = demo.succeed("date +%H").strip()
    assert hour == "22", f"guest clock is {hour}, expected 22"

    # The host zone itself + the abbreviation it renders.
    zone = demo.succeed("timedatectl show -p Timezone --value").strip()
    assert zone == "Europe/Berlin", zone
    abbr = demo.succeed("date +%Z").strip()
    assert abbr in ("CET", "CEST"), abbr

    # FreeSWITCH evaluates the timeWindow in the host zone: its runtime
    # view of the zone must agree with the system's.
    fs_zone = demo.succeed("fs_cli -p demo-es-9f1e2c -x 'strftime %Z'").strip()
    assert fs_zone in ("CET", "CEST"), fs_zone

    # The webphone facade derives settings.timezone from the host zone
    # (2026-10-26): the served config.js must carry it.
    demo.wait_for_unit("webphone.service")
    demo.wait_for_open_port(8080)
    configjs = demo.succeed("curl -sf http://127.0.0.1:8080/config.js")
    assert "Europe/Berlin" in configjs, configjs

    # The rendered dialplan carries the demo host's window (8-20, five
    # weekdays) and the after-hours transfer to the echo test.
    dialplan = demo.succeed(
      "grep -r 'hour=\"8-20\"' /etc/freeswitch/ | head -1"
    )
    assert 'hour="8-20"' in dialplan, dialplan

    # End to end OUTSIDE the window: the call to the ring group is
    # transferred to 9196 and the echo test answers (200 with media).
    out = demo_call(demo, "2000", 4, "demo-1001-d4e5f6")
    assert "ANSWERED" in out, out
    assert_file_log(demo, "Processing 1001.*->9196", "after-hours transfer")
  '';
}
