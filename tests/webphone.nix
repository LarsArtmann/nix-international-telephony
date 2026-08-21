# NixOS VM test for the web-facing half of the stack:
#   * nginx serves the webphone over TLS, shipping the multi-call keypad,
#     remember-me and history markup, and the app bundle with reconnect
#     and DTMF logic
#   * config.js carries strict JSON after the JS wrapper with the SIP
#     domain and REST-style (expiry-prefixed username) TURN credentials
#   * the vhost sets a strict Content-Security-Policy (self + wss:)
#   * a non-WebSocket request through the /sip proxy reaches FreeSWITCH
#     (anything but 502/504 proves nginx talks to sofia's ws transport)
let
  common = import ./common.nix;
in
{
  name = "telephony-webphone";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;
    };

  testScript = ''
    ${common.bootWait}

    # NOTE: no start_all() — machines start lazily at their first command
    # (staggering sofia's heavy startup phase; see tests/dialplan.nix).
    wait_for_freeswitch(machine, "test-es-4d5e6f")

    # Web endpoints.
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)
    page = machine.succeed("curl -k -f https://localhost/")
    assert "WebPhone" in page, page
    assert "sip.min.js" in page, page
    # The served UI ships the multi-call keypad, remember-me and history
    # markup; the app bundle carries reconnect + DTMF INFO logic.
    assert 'id="keypad"' in page and 'id="remember"' in page, page
    assert 'id="history-list"' in page, page
    app_js = machine.succeed("curl -k -f https://localhost/app.js")
    assert "dtmf-relay" in app_js and "userAgent.reconnect()" in app_js, app_js[:200]

    cfg = machine.succeed("curl -k -f https://localhost/config.js")
    assert "pbx.test" in cfg and "stun:" in cfg, cfg

    # config.js carries strict JSON after the JS wrapper; TURN creds are
    # REST-style (expiry-prefixed username) ephemeral credentials.
    machine.succeed(
        "curl -k -f https://localhost/config.js"
        " | sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//'"
        " | python3 -c 'import json,sys; c=json.load(sys.stdin);"
        " assert c[\"sipDomain\"]==\"pbx.test\", c;"
        " t=[s for s in c[\"iceServers\"] if any(u.startswith(\"turn:\") for u in s[\"urls\"])];"
        " assert t and t[0][\"username\"] and t[0][\"credential\"], c;"
        " assert \":\" in t[0][\"username\"], c'"
    )

    # Content-Security-Policy: same-origin only, wss allowed for the SIP
    # proxy, everything else denied.
    csp = machine.succeed("curl -k -sI https://localhost/ | grep -i content-security-policy")
    assert "default-src 'self'" in csp and "wss:" in csp, csp

    # A non-WebSocket request through the proxy must reach FreeSWITCH
    # (anything but 502/504 proves nginx talks to sofia's ws transport).
    machine.wait_until_succeeds(
        "curl -k -s -o /dev/null -w '%{http_code}' https://localhost/sip"
        " | grep -vE '^(502|504|000)$'"
    )
  '';
}
