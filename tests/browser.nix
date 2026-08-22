# NixOS VM test for the browser leg of the stack: two headless chromium
# instances (fake capture devices, auto-granted media permissions) log
# into the webphone, register over wss://pbx.test/sip (nginx -> FreeSWITCH
# WebSocket transport), place a real 1000 -> 1001 WebRTC call with
# DTLS-SRTP media, and hang up. The FreeSWITCH side of the bridge is
# asserted via fs_cli while the call is up.
#
# This is the only suite that exercises the full webphone stack the way a
# user's browser does (TLS, CSP, config.js, SIP.js bundle, ICE/TURN
# candidates, DTLS-SRTP); it costs ~1-2 GB of test closure for chromium.
let
  common = import ./common.nix;
in
{
  name = "telephony-browser";

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;

      # The webphone derives its WebSocket URL from location.host, so the
      # browsers must reach the vhost by its configured name.
      networking.extraHosts = "127.0.0.1 pbx.test";

      # chromium + two chromedriver sessions need headroom.
      virtualisation.memorySize = 4096;

      environment.systemPackages = [
        (pkgs.python3.withPackages (ps: [ ps.selenium ]))
      ];

      environment.etc."browser-e2e.py".source = pkgs.replaceVars ./browser-e2e.py {
        chromedriver = "${pkgs.chromedriver}/bin/chromedriver";
        chromium = "${pkgs.chromium}/bin/chromium";
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)

    es_password = "test-es-4d5e6f"
    fs_cli = f"fs_cli -p {es_password} -x"

    machine.succeed("nohup python3 /etc/browser-e2e.py > /tmp/e2e.log 2>&1 &")

    # Both browsers registered through the wss proxy: sofia must list two
    # WebSocket registrations.
    machine.wait_until_succeeds("grep -q '1000-REGISTERED' /tmp/e2e.log", timeout=420)
    machine.wait_until_succeeds("grep -q '1001-REGISTERED' /tmp/e2e.log", timeout=120)
    regs = machine.succeed(f"{fs_cli} 'sofia status profile internal reg'")
    assert regs.count("Call-ID:") == 2, regs

    # Ring, accept, established on both sides.
    machine.wait_until_succeeds("grep -q 'INCOMING-SHOWN' /tmp/e2e.log", timeout=120)
    machine.wait_until_succeeds("grep -q 'CALL-ESTABLISHED' /tmp/e2e.log", timeout=180)

    # Server-side proof while the call is up: two bridged sofia channels
    # carrying the WebRTC legs.
    machine.wait_until_succeeds(
        f"{fs_cli} 'show channels' | grep 'sofia/internal/1000@pbx.test'", timeout=60
    )
    machine.wait_until_succeeds(
        f"{fs_cli} 'show channels' | grep 'sofia/internal/1001@pbx.test'", timeout=60
    )

    machine.wait_until_succeeds("grep -q 'E2E-OK' /tmp/e2e.log", timeout=180)
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'", timeout=60)

    e2e_log = machine.succeed("cat /tmp/e2e.log")
    assert "CALL-ESTABLISHED" in e2e_log, e2e_log
  '';
}
