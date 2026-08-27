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
        # Explicit runner (not a bare python3 on PATH): the shared fixtures
        # from common.nix install a plain python3 for tests/sip.py, which
        # would shadow the selenium-enabled interpreter and crash the E2E
        # script at import time.
        (pkgs.writeShellScriptBin "browser-e2e-runner" ''
          exec ${pkgs.python3.withPackages (ps: [ ps.selenium ])}/bin/python3 /etc/browser-e2e.py "$@"
        '')
      ];

      # Raw WebSocket-to-SIP probe (stdlib): direct to sofia's wss on 7443
      # and through the nginx wss proxy.
      environment.etc."wsprobe.py".source = ./wsprobe.py;

      environment.etc."browser-e2e.py".source = pkgs.replaceVars ./browser-e2e.py {
        chromedriver = "${pkgs.chromedriver}/bin/chromedriver";
        chromium = "${pkgs.chromium}/bin/chromium";
      };
    };

  testScript = ''
    ${common.bootWait}

    def wait_marker(marker, timeout):
        # Poll for a phase marker from the E2E script; when a phase
        # stalls, dump every evidence source (script log incl. traceback,
        # both verbose chromedriver logs, process table, nginx/freeswitch
        # journals) BEFORE re-raising — a bare "grep never matched"
        # timeout localises nothing.
        try:
            machine.wait_until_succeeds(f"grep -q '{marker}' /tmp/e2e.log", timeout=datetime.timedelta(seconds=timeout))
        except Exception:
            with machine.nested(f"browser e2e stalled before {marker}: diagnostics"):
                dumps = [
                    "cat /tmp/e2e.log || true",
                    "tail -n 150 /tmp/chromedriver-1000.log 2>/dev/null || true",
                    "tail -n 150 /tmp/chromedriver-1001.log 2>/dev/null || true",
                    "ps aux | grep -E 'chromium|chromedriver' | grep -v grep || true",
                    "journalctl -u nginx --no-pager -n 30 || true",
                    "tail -n 30 /var/log/nginx/access.log 2>/dev/null || true",
                    "tail -n 30 /var/log/nginx/error.log 2>/dev/null || true",
                    "journalctl -u freeswitch --no-pager | grep -iE"
                    " 'recv |send |register|challenge|unauthorized|forbidden|siptrace|websocket|nua' | tail -n 80 || true",
                    "journalctl -u freeswitch --no-pager -n 40 || true",
                    "ss -ltn | grep -E ':(443|7443|8021)' || true",
                    "curl -k -s -o /dev/null -w 'vhost status: %{http_code}\\n' https://pbx.test/ || true",
                    # Raw WebSocket upgrade through the same path the browser
                    # uses, WITH the sip subprotocol (sofia refuses without
                    # it): 101 proves nginx<->sofia ws framing, 400/426 means
                    # sofia saw it, silence means the proxy path is broken.
                    "curl -s -i -N --max-time 4"
                    " -H 'Connection: Upgrade' -H 'Upgrade: websocket'"
                    " -H 'Sec-WebSocket-Version: 13'"
                    " -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ=='"
                    " -H 'Sec-WebSocket-Protocol: sip'"
                    " http://127.0.0.1:7443/sip | head -n 3 || true",
                    "python3 /etc/wsprobe.py 2>&1 || true",
                    f"{fs_cli} 'sofia_contact internal/1001@pbx.test' || true",
                    f"{fs_cli} 'sofia status profile internal reg' || true",
                    f"{fs_cli} 'sofia status profile internal' || true",
                ]
                for cmd in dumps:
                    _, out = machine.execute(cmd)
                    print(f"DIAG: {cmd}\\n{out}")
            raise

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)

    es_password = "test-es-4d5e6f"
    fs_cli = f"fs_cli -p {es_password} -x"

    # Raw SIP trace into the journal: if a browser REGISTER never gets a
    # response, the failure dump below shows whether it reached sofia.
    machine.succeed(f"{fs_cli} 'console loglevel debug'")
    machine.succeed(f"{fs_cli} 'sofia global siptrace on'")

    machine.succeed("nohup browser-e2e-runner > /tmp/e2e.log 2>&1 &")

    # Wrong-password leg: the on-screen error must appear (M11).
    wait_marker("WRONGPASS-DONE", 300)

    # Both browsers registered through the wss proxy: sofia must list two
    # WebSocket registrations.
    wait_marker("1000-REGISTERED", 420)
    wait_marker("1001-REGISTERED", 120)
    regs = machine.succeed(f"{fs_cli} 'sofia status profile internal reg'")
    assert regs.count("Call-ID:") == 2, regs

    # Reconnect drill: stop nginx when the e2e script is watching, bring
    # it back once the pill shows the backoff (M11).
    wait_marker("RECONNECT-READY", 120)
    machine.succeed("systemctl stop nginx")
    machine.wait_until_succeeds("grep -q 'RECONNECT-DETECTED' /tmp/e2e.log", timeout=datetime.timedelta(seconds=180))
    machine.succeed("systemctl start nginx")
    wait_marker("RECONNECTED", 300)
    # Capture the registration state at the exact moment the call is placed
    # (WS registrations vanish with the connection once the browsers quit,
    # so post-mortem dumps cannot see them).
    machine.wait_until_succeeds("grep -q 'DIAL-SUBMITTED' /tmp/e2e.log", timeout=datetime.timedelta(seconds=60))
    _, regs_at_dial = machine.execute(f"{fs_cli} 'sofia status profile internal reg'")
    print(f"REGS-AT-DIAL:\n{regs_at_dial}")
    _, contact_at_dial = machine.execute(f"{fs_cli} 'sofia_contact internal/1001@pbx.test'")
    print(f"CONTACT-AT-DIAL: {contact_at_dial}")


    # Ring, accept, established on both sides.
    wait_marker("INCOMING-SHOWN", 120)
    wait_marker("CALL-ESTABLISHED", 180)

    # Server-side proof while the call is up: two bridged sofia channels
    # carrying the WebRTC legs. The caller leg is named from its From
    # (1000@pbx.test); the callee leg carries the registered WS contact
    # (an .invalid host from SIP.js), so count channels instead.
    machine.wait_until_succeeds(
        f"{fs_cli} 'show channels' | grep 'sofia/internal/1000@pbx.test'", timeout=datetime.timedelta(seconds=60)
    )
    machine.wait_until_succeeds(f"{fs_cli} 'show channels count' | grep -q '^2'", timeout=datetime.timedelta(seconds=60))

    wait_marker("E2E-OK", 180)
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'", timeout=datetime.timedelta(seconds=60))

    e2e_log = machine.succeed("cat /tmp/e2e.log")
    assert "CALL-ESTABLISHED" in e2e_log, e2e_log
    assert "WRONGPASS-ERROR-SHOWN" in e2e_log, e2e_log
    assert "RECONNECTED" in e2e_log, e2e_log
    assert "DTMF-SENT" in e2e_log, e2e_log
    assert "MEDIA-BYTES" in e2e_log, e2e_log
  '';
}
