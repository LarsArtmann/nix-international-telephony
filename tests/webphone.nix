# NixOS VM test for the web-facing half of the stack:
#   * the webphone v2 service (Go binary) runs and nginx proxies the vhost
#     to it: the served shell ships the multi-call keypad, remember-me and
#     history markup, and the island modules are served VERBATIM with
#     reconnect and DTMF logic
#   * config.js is served by nginx from the runtime-rendered file (NOT the
#     app's own): strict JSON after the JS wrapper with the SIP domain and
#     REST-style (expiry-prefixed username) TURN credentials
#   * the app sends its own strict Content-Security-Policy (self + wss:)
#     through the proxy
#   * a non-WebSocket request through the /sip proxy reaches FreeSWITCH
#     (anything but 502/504 proves nginx talks to sofia's ws transport)
#
# Parametrized for the aarch64 CI runner (GitHub arm64 hosts expose no
# /dev/kvm): kvm = false drops the derivation's kvm system-feature
# requirement so the suite may run under same-arch TCG; slowBoot extends
# the FreeSWITCH boot waits accordingly.
{
  telephonyModule,
  webphonePackage,
  kvm ? true,
  slowBoot ? false,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  # Under TCG the guest boots and starts sofia far slower than under KVM.
  # wait_for_freeswitch takes plain seconds (it builds the timedeltas).
  bootTimeouts = if slowBoot then ", port_timeout=900, unit_timeout=900" else "";
in
{
  name = if kvm then "telephony-webphone" else "telephony-webphone-tcg";

  requiredFeatures.kvm = kvm;

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;
      environment.etc."wsprobe.py".source = ./wsprobe.py;
    };

  testScript = ''
    ${common.bootWait}

    # NOTE: no start_all() — machines start lazily at their first command
    # (staggering sofia's heavy startup phase; see tests/dialplan.nix).
    wait_for_freeswitch(machine, "test-es-4d5e6f"${bootTimeouts})

    # The webphone service itself, then the proxied web endpoints.
    machine.wait_for_unit("webphone.service")
    machine.wait_for_open_port(8080)
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)
    machine.succeed("curl -sf http://127.0.0.1:8080/healthz | grep -q '^ok$'")
    machine.succeed("curl -k -sf https://localhost/healthz | grep -q '^ok$'")

    page = machine.succeed("curl -k -f https://localhost/")
    assert "WebPhone" in page, page
    # The served shell ships the multi-call keypad, remember-me and history
    # markup plus the voicemail/contacts/ICE panels (the same island DOM
    # contract the browser E2E drives; asserted upstream in the webphone
    # repo's TestServedPageHoldsTheDomContract).
    assert 'id="keypad"' in page and 'id="remember"' in page, page
    assert 'id="history-list"' in page, page
    assert 'id="vm-wrap"' in page and 'id="contacts-wrap"' in page, page
    assert 'id="ice-wrap"' in page, page

    # The island modules are served VERBATIM (no bundling): every logic
    # marker the browser E2E greps survives by construction. Prove the
    # same strings on the wire here.
    base = "https://localhost/assets/island/app"
    calls_js = machine.succeed(f"curl -k -f {base}/calls.js")
    assert "dtmf-relay" in calls_js, calls_js[:200]
    # Transfer: REFER is sent via sip.js; FreeSWITCH executes it server-side.
    assert ".refer(" in calls_js, calls_js[:200]
    assert "blindTransfer" in calls_js and "attendedTransfer" in calls_js, calls_js[:200]
    conn_js = machine.succeed(f"curl -k -f {base}/connection.js")
    assert "userAgent.reconnect()" in conn_js, conn_js[:200]
    # Incoming-call UX: notifications, audible ring, tab-title flash.
    notify_js = machine.succeed(f"curl -k -f {base}/notify.js")
    assert "Notification.requestPermission" in notify_js, notify_js[:200]
    assert "titleFlashStart" in conn_js and "ringToneStart" in conn_js, conn_js[:200]
    # Phone-API consumers: voicemail panel, server history, ICE diagnostics.
    panels_js = machine.succeed(f"curl -k -f {base}/panels.js")
    assert "phone-api/history" in panels_js and "phone-api/voicemail" in panels_js, panels_js[:200]
    ice_js = machine.succeed(f"curl -k -f {base}/ice.js")
    assert "candidate-pair" in ice_js and "currentRoundTripTime" in ice_js, ice_js[:200]

    # The vendored SIP.js bundle is served by the app under /assets/ —
    # still a plain static file the wss proxy location can never capture
    # (= /sip is an exact match).
    bundle = machine.succeed("curl -k -f https://localhost/assets/vendor/sip.min.js")
    assert "SIP" in bundle, bundle[:100]

    # The phone API is off in the base fixture: config.js says so, and the
    # app's /phone-api proxy demands a session first (401; the nginx
    # /phone-api location of the static-site era is gone — the app itself
    # proxies with session-injected credentials).
    cfg = machine.succeed("curl -k -f https://localhost/config.js")
    assert '"phoneApi": false' in cfg, cfg
    code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}' https://localhost/phone-api/history"
    ).strip()
    assert code == "401", f"phone-api without a session must be 401, got {code}"

    cfg = machine.succeed("curl -k -f https://localhost/config.js")
    assert "pbx.test" in cfg and "stun:" in cfg, cfg

    # config.js is the runtime-rendered file served BY NGINX (shadowing
    # the app's own): strict JSON after the JS wrapper; TURN creds are
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

    # Content-Security-Policy: sent by the app through the proxy —
    # same-origin only, wss allowed for the SIP proxy, rest denied.
    csp = machine.succeed("curl -k -sI https://localhost/ | grep -i content-security-policy")
    assert "default-src 'self'" in csp and "wss:" in csp, csp

    # A non-WebSocket request through the proxy must reach FreeSWITCH
    # (anything but 502/504 proves nginx talks to sofia's ws transport).
    machine.wait_until_succeeds(
        "curl -k -s -o /dev/null -w '%{http_code}' https://localhost/sip"
        " | grep -vE '^(502|504|000)$'"
    )

    # Raw wss probes as suite assertions (the ops runbook's manual probe,
    # asserted): the upgrade carries the sip subprotocol, a Via/WSS
    # REGISTER (real SIP.js behaviour) is auth-challenged by sofia, PINGs
    # are PONGed, and a Via/WS REGISTER over wss is dropped silently —
    # the transport-consistency contract of the four-reason postmortem.
    machine.succeed("python3 /etc/wsprobe.py --assert proxied")
    machine.succeed("python3 /etc/wsprobe.py --assert direct")
  '';
}
