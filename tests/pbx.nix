# NixOS VM test for the whole telephony stack:
#   * FreeSWITCH loads the generated config and opens SIP + WebSocket listeners
#   * the generated directory (extensions) is queryable
#   * the generated dialplan actually executes (loopback call through echo test)
#   * nginx serves the webphone and its config over TLS
#   * the /sip WebSocket proxy reaches FreeSWITCH
#   * coturn listens for STUN/TURN
{
  name = "telephony";

  nodes.machine =
    { ... }:
    {
      imports = [ ../modules/telephony.nix ];

      services.telephony = {
        enable = true;
        domain = "pbx.test";
        eventSocketPassword = "test-es-4d5e6f";
        turn.password = "test-turn-1a2b3c";
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

      networking.firewall.enable = true;
      system.stateVersion = "26.05";
    };

  testScript = ''
    start_all()

    machine.wait_for_unit("freeswitch.service")
    machine.wait_for_open_port(5060)

    es_password = "test-es-4d5e6f"
    fs_cli = f"fs_cli -p {es_password} -x"

    # FreeSWITCH must have loaded the generated sofia profiles.
    machine.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep internal")
    machine.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep external")
    internal = machine.succeed(f"{fs_cli} 'sofia status profile internal'")
    assert "Context" in internal and "default" in internal, internal

    # The WebSocket transport for the nginx TLS proxy must be bound to loopback.
    assert "127.0.0.1:5066" in internal, internal

    # Directory: generated users exist with the configured password.
    password = machine.succeed(f"{fs_cli} 'user_data 1000@pbx.test param password'")
    assert password.strip() == "test-1000-x9y8z7", password

    # Dialplan executes end to end: a loopback call into the echo-test
    # extension must be answered by the echo application.
    originate = machine.succeed(f"{fs_cli} 'originate loopback/9196 &park()'")
    assert originate.startswith("+OK"), originate

    # Web endpoints.
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)
    page = machine.succeed("curl -k -f https://localhost/")
    assert "WebPhone" in page, page
    assert "sip.min.js" in page, page

    cfg = machine.succeed("curl -k -f https://localhost/config.js")
    assert "pbx.test" in cfg and "stun:" in cfg, cfg

    # A non-WebSocket request through the proxy must reach FreeSWITCH
    # (anything but 502/504 proves nginx talks to sofia's ws transport).
    code = machine.succeed("curl -k -s -o /dev/null -w '%{http_code}' https://localhost/sip").strip()
    assert code not in ("502", "504", "000"), code

    machine.wait_for_unit("coturn.service")
    machine.wait_for_open_port(3478)

    # Recording directory provisioned by the module.
    machine.succeed("test -d /var/lib/freeswitch/recordings")
  '';
}
