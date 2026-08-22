# Shared fixtures for the telephony VM tests (tests/dialplan.nix,
# tests/webphone.nix, tests/tls-turn.nix, tests/pbx.nix).
#
# Every test node imports `baseNode`: the module under test, the scripted
# protocol clients and the shared PBX config (two extensions, one ring
# group, no gateway). Tests then add their scenario-specific config on top.
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

  # Everything every test node imports.
  baseNode = [
    ../modules/telephony.nix
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
    def wait_for_freeswitch(node, es_password, port_timeout=300, unit_timeout=300):
        try:
            node.wait_for_unit("freeswitch.service", timeout=unit_timeout)
            # sofia binds $${local_ip_v4}: the egress interface when a
            # default route exists, loopback otherwise — so probe for a
            # listener on ANY local address; wait_for_open_port would
            # pin the check to localhost and miss the real binding.
            node.wait_until_succeeds(
                "ss -ltn 'sport = :5060' | grep -q ':5060'",
                timeout=port_timeout,
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
in
{
  inherit baseNode bootWait;
}
