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
    { ... }:
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
      # the guest outside the demo host's 8-20 window. QEMU interprets the
      # base as UTC and the guest reads the RTC as UTC, so 21:30 UTC is
      # 22:30 Europe/Berlin (the smoke's hour assert catches any drift).
      virtualisation.qemu.options = [ "-rtc base=2026-11-11T21:30:00" ];
    };
in
{
  name = "telephony-demo-wallclock";
  nodes.demo.imports = [ demoHost ];

  testScript = ''
    ${common.bootWait}
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

    # FS-side RENDERING (2026-11-08): freeswitch.log stamps wall-clock
    # in the host zone (proven shape "2026-11-11 22:30:24.898053" — no
    # offset suffix). The pinned RTC is 21:30Z = 22:30 Berlin wall, so
    # the log's first stamp must carry that date+hour: FS renders the
    # SAME wall the timeWindow evaluates, not UTC.
    fs_first_stamp = demo.succeed(
      "head -c 2048 /var/lib/freeswitch/log/freeswitch.log | grep -o"
      " '^[0-9][0-9-]* [0-9][0-9]:' | head -1 || true"
    ).strip()
    assert fs_first_stamp == "2026-11-11 22:", (
      f"FS log not Berlin-wall-stamped (want 2026-11-11 22:): {fs_first_stamp!r}"
    )

    # The webphone facade derives settings.timezone from the host zone
    # (2026-10-26): the RENDERED settings JSON (WEBPHONE_CONFIG) must
    # carry Europe/Berlin — /config.js is the browser contract and does
    # not surface the timezone (the first smoke run proved exactly
    # that by failing on the PBX_CONFIG payload).
    demo.wait_for_unit("webphone.service")
    demo.wait_for_open_port(8080)
    demo.succeed(
      "grep -q '\"timezone\": *\"Europe/Berlin\"' \"$(systemctl show webphone"
      " -p Environment --value | tr ' ' '\\n' | grep '^WEBPHONE_CONFIG='"
      " | cut -d= -f2-)\""
    )

    # The rendered dialplan carries the demo host's window (8-20, five
    # weekdays). The demo host has no *File secrets, so FreeSWITCH runs
    # against the STORE config dir straight off the unit's ExecStart
    # (-conf /nix/store/...-freeswitch-config-d) — no /etc/freeswitch,
    # no /var/lib/freeswitch/conf private copy.
    demo.succeed(
      "P=$(systemctl show freeswitch -p ExecStart --value"
      " | grep -o '/nix/store/[^ ]*-freeswitch-config-d');"
      " grep -q 'hour=\"8-20\"' \"$P/dialplan/default.xml\""
    )

    # End to end OUTSIDE the window: the call to the ring group is
    # transferred to 9196 and the echo test answers (200 with media).
    out = demo_call(demo, "2000", "4", "demo-1001-d4e5f6")
    assert "ANSWERED" in out, out
    assert_file_log(demo, "Processing 1001.*->9196", "after-hours transfer")
  '';
}
