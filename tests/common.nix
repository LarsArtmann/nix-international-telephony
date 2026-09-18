# Shared fixtures for the telephony VM tests (tests/dialplan.nix,
# tests/webphone.nix, tests/tls-turn.nix, tests/ssh.nix, tests/pbx.nix).
#
# Every test node imports `baseNode`: the flake's wrapper module (which
# brings the webphone repo's services.webphone module), the scripted
# protocol clients and the shared PBX config (two extensions, one ring
# group, no gateway). Tests then add their scenario-specific config on top.
{
  telephonyModule,
  webphonePackage,
}:
let
  # Scripted SIP client for SIP-level assertions (tests/sip.py), plus the
  # TURN client (tests/turn.py).
  sipClientModule =
    { pkgs, ... }:
    {
      environment.etc."sip.py".source = ./sip.py;
      environment.etc."turn.py".source = ./turn.py;
      environment.systemPackages = [ pkgs.python3 ];
    };

  # Shared PBX under test: two extensions and one ring group, no gateway.
  baseTelephony = {
    services.telephony = {
      enable = true;
      webphone.package = webphonePackage;
      domain = "pbx.test";
      eventSocketPassword = "test-es-4d5e6f";
      turn.authSecret = "test-turn-rest-4d5e6f";
      extensions = {
        "1000" = {
          password = "test-1000-x9y8z7";
          displayName = "Alice";
        };
        "1001" = {
          password = "test-1001-u6t5s4";
          displayName = "Bob";
        };
      };
      ringGroups."2000" = {
        members = [
          "1000"
          "1001"
        ];
        timeoutSec = 25;
      };
    };
  };

  # Node boilerplate shared by every machine in every test.
  nodeSettings = {
    networking.firewall.enable = true;
    system.stateVersion = "26.05";
  };

  # Everything every test node imports: the flake's wrapper module — the
  # same interface real consumers get from nixosModules.telephony (raw
  # telephony set + the webphone input's services.webphone module). Each
  # suite still sets webphone.package explicitly above, proving the
  # explicit-consumer path over the wrapper's mkDefault.
  baseNode = [
    telephonyModule
    sipClientModule
    baseTelephony
    nodeSettings
  ];

  # Python helper for the test scripts: wait for FreeSWITCH to come up,
  # and if it does not, dump process-level evidence (wchan, blocked
  # syscall, thread count, unit state, journal tail) before re-raising.
  # The short timeouts leave room for the dumps inside the driver's
  # per-action budget; a plain 15-minute wait would abort without them.
  bootWait = ''
    import datetime

    def sip_server(node, port=5060):
        # sofia binds $${local_ip_v4}: the egress interface when a
        # default route exists, loopback otherwise — derive the address
        # from the listener instead of assuming localhost.
        listener = node.succeed(f"ss -ltn 'sport = :{port}' | grep -v State").strip()
        ip = listener.split()[3].rsplit(":", 1)[0]
        return "::1" if ip.startswith("[") else ip

    def wait_for_freeswitch(node, es_password, port=5060, port_timeout=300, unit_timeout=300):
        try:
            node.wait_for_unit(
                "freeswitch.service", timeout=datetime.timedelta(seconds=unit_timeout)
            )
            # sofia binds $${local_ip_v4}: the egress interface when a
            # default route exists, loopback otherwise — so probe for a
            # listener on ANY local address; wait_for_open_port would
            # pin the check to localhost and miss the real binding.
            node.wait_until_succeeds(
                f"ss -ltn 'sport = :{port}' | grep -q ':{port}'",
                timeout=datetime.timedelta(seconds=port_timeout),
            )
            # sofia's profiles coming up does NOT imply mod_event_socket
            # is accepting yet (it binds late in startup); fs_cli calls
            # right after the 5060 check raced it in the boot suite.
            node.wait_until_succeeds(
                "ss -ltn 'sport = :8021' | grep -q ':8021'",
                timeout=datetime.timedelta(seconds=port_timeout),
            )
        except Exception:
            with node.nested("freeswitch boot failure diagnostics"):
                dumps = [
                    "systemctl status freeswitch --no-pager -l || true",
                    "systemctl show freeswitch -p Type,MainPID,ActiveState,SubState,Result || true",
                    "ps -o pid,stat,psr,pcpu,wchan:32,cmd -C freeswitch || true",
                    'pid=$(pgrep -x freeswitch | head -1); if [ -n "$pid" ]; then'
                    " grep -E 'State|Threads|voluntary' /proc/$pid/status;"
                    " echo \"wchan: $(cat /proc/$pid/wchan)\";"
                    " echo \"syscall: $(cat /proc/$pid/syscall)\";"
                    " cat /proc/$pid/stack 2>/dev/null;"
                    " echo \\\"threads: $(ls /proc/$pid/task | wc -l)\\\";"
                    "fi",
                    "ss -ltn || true",
                    "journalctl -u freeswitch --no-pager -n 100 || true",
                    "dmesg | tail -n 30 || true",
                ]
                for cmd in dumps:
                    _, out = node.execute(cmd)
                    print(f"DIAG: {cmd}\\n{out}")
            raise
  '';

  # Shared test-script helpers (each testScript destructures what it uses).
  helpers = ''
    # Loud clock precondition for RTC-pinned suites: fail with the actual
    # hour when anything dragged the guest clock back to host time.
    def assert_fs_hour(node, expected):
        hour = node.succeed("date +%H").strip()
        assert hour == expected, (
            f"{node.name}: guest clock is {hour}, expected {expected}"
        )

    # Post-startup sofia/dialplan lines do not reach the journal (the
    # console logger detaches) — the freeswitch.log FILE has them.
    def assert_file_log(node, pattern, what, timeout=30):
        node.wait_until_succeeds(
            "grep -q '" + pattern + "' /var/lib/freeswitch/log/freeswitch.log",
            timeout=datetime.timedelta(seconds=timeout),
        )

    # Scripted caller places one call to `to` and holds it, expecting
    # an answered 200 (the fixtures' 1001 account dials, 1000 answers).
    def sip_call(node, to, hold_seconds, expect_status=200):
        sip_ip = sip_server(node)
        return node.succeed(
            "python3 /etc/sip.py --server " + sip_ip + " --domain pbx.test "
            "--user 1001 --password test-1001-u6t5s4 invite --to " + to + " "
            "--hold-seconds " + hold_seconds + " --expect-status "
            + str(expect_status)
        )
  '';
in
{
  inherit baseNode bootWait helpers;
}
