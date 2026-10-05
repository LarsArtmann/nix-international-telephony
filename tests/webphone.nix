# NixOS VM test for the web-facing half of the stack:
#   * the webphone v2 service (Go binary) runs and nginx proxies the vhost
#     to it: the served shell ships the multi-call keypad, remember-me and
#     history markup, and the island modules are served VERBATIM with
#     reconnect and DTMF logic
#   * config.js is served BY THE APP (the nginx shadow + daily timer are
#     gone): strict JSON after the JS wrapper with the SIP domain and
#     REST-style TURN credentials derived per response (bare unix-expiry
#     username)
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
      environment.etc."configjs_check.py".source = ./configjs_check.py;
      # A contact with a quote in the name pins the app-side JSON escaping
      # of the contacts payload in config.js (the old stack-side
      # escapeJs+toJSON combination double-escaped it).
      services.telephony.webphone.contacts = [
        {
          name = ''O"Brien'';
          number = "1000";
        }
      ];
      # Passkey mode ON (the only suite that wires it): proves the
      # stack's derived config shape (rp_id/origins from the vhost
      # domain, password-file override for an inline-password extension)
      # against the real service. The conditional DOM, the userauth
      # healthz leg and the token lifecycle are asserted below; the
      # WebAuthn ceremony itself stays upstream's island-tests.
      services.telephony.webphone.passkey = {
        enable = true;
        users."alice@pbx.test" = {
          extensions = [ "1000" ];
          displayName = "Alice";
        };
        extensionPasswordFiles."1000" = "/etc/telephony/passkey-ext-1000";
      };
      # Alice's SIP password as the file passkey login sources (same
      # value as the extension's inline password; 0600 webphone-only,
      # the readability contract a sops-rendered file carries).
      environment.etc."telephony/passkey-ext-1000" = {
        text = "test-1000-x9y8z7\n";
        user = "webphone";
        mode = "0600";
      };
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
    # /healthz ships the readiness contract (library JSON, verified live):
    # overall status plus the named backing-resource checks — not the old
    # constant-"ok" body this test asserted before the readiness migration.
    machine.succeed("curl -sf http://127.0.0.1:8080/healthz | grep -q '\"status\":\"ok\"'")
    machine.succeed(
        "curl -sf http://127.0.0.1:8080/healthz | grep -q '\"sqlite\":{\"status\":\"ok\"}'"
    )
    machine.succeed(
        "curl -sf http://127.0.0.1:8080/healthz | grep -q '\"blob-dir\":{\"status\":\"ok\"}'"
    )
    machine.succeed("curl -k -sf https://localhost/healthz | grep -q '\"status\":\"ok\"'")

    # /metrics is fenced loopback-only (aggregates-only upstream, but
    # unconsumed + internet-facing is pure exposure): a non-loopback
    # source gets 403 from the vhost, loopback scrapes get the
    # Prometheus text (build_info + uptime), and the app's own port —
    # what a local scraper would use — stays open.
    import re

    route = machine.succeed("ip -4 route get 1.1.1.1")
    match = re.search(r"src ([0-9.]+)", route)
    assert match is not None, route
    egress_ip = match.group(1)
    code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}' https://" + egress_ip + "/metrics"
    ).strip()
    assert code == "403", f"external /metrics must be 403, got {code}"
    metrics = machine.succeed("curl -k -sf https://localhost/metrics")
    assert "webphone_build_info" in metrics, metrics[:200]
    assert "webphone_uptime_seconds" in metrics, metrics[:200]
    machine.succeed(
        "curl -sf http://127.0.0.1:8080/metrics | grep -q webphone_build_info"
    )

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

    # Passkey mode is ON here (wired via webphone.passkey above): the
    # conditional login surfaces exist and the userauth readiness leg
    # probes the identity store. The extension form stays too — the
    # lifeline property (signing in must never depend on more than
    # FreeSWITCH and the webphone process).
    assert 'id="passkey-login-form"' in page and 'id="passkey-email"' in page, page[:2000]
    healthz = machine.succeed("curl -sf http://127.0.0.1:8080/healthz")
    assert '"userauth":{"status":"ok"}' in healthz, healthz[:400]
    enroll_code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}' https://localhost/enroll"
    ).strip()
    assert enroll_code == "200", f"/enroll must render with passkey on, got {enroll_code}"

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
    # The app renders MINIFIED JSON (encoding/json v2): match without
    # the spaces the old pretty-printed nginx-era render carried.
    assert '"phoneApi":false' in cfg, cfg
    code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}' https://localhost/phone-api/history"
    ).strip()
    assert code == "401", f"phone-api without a session must be 401, got {code}"

    cfg = machine.succeed("curl -k -f https://localhost/config.js")
    assert "pbx.test" in cfg and "stun:" in cfg, cfg

    # config.js is served BY THE APP: strict JSON after the JS wrapper.
    # The full wire contract — exact key set, phoneApi mirroring
    # telephony.webphone.phoneApi.enable (never the operator flag),
    # LOWERCASE contact name/number keys (the 2026-09-24 breakage seam;
    # the quote in the fixture name doubles as the JSON-escaping test),
    # TURN REST pairs derived PER RESPONSE from the fixture secret —
    # lives in tests/configjs_check.py, the shared fixture whose docstring
    # documents the cross-repo seam: the webphone repo's
    # internal/server/configjs_test.go asserts the producer side of the
    # same contract, this suite and tests/browser-e2e.py the consumer
    # side.
    machine.succeed(
        "curl -k -f https://localhost/config.js"
        " | sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//'"
        " | python3 /etc/configjs_check.py --sip-domain pbx.test"
        " --turn-rest-secret test-turn-rest-4d5e6f"
        " --contact 'O\"Brien=1000'"
    )

    # The TLS-fronting csrf shape must land in the RENDERED runtime
    # config (read from the running unit's environment, the store path
    # the module generated): loopback proxy + https origin derived from
    # the vhost name. A regression here 403s every browser login behind
    # the proxy — the class the browser E2E's SESSION-CREATED gate now
    # also catches end to end.
    cfg_path = machine.execute(
        "tr '\\0' '\\n' < /proc/$(systemctl show -p MainPID --value webphone)/environ"
        " | sed -n 's/^WEBPHONE_CONFIG=//p'"
    )[1].strip()
    assert cfg_path.startswith("/nix/store/"), f"WEBPHONE_CONFIG not found: {cfg_path!r}"
    import json

    rendered = json.loads(machine.succeed(f"cat {cfg_path}"))
    assert rendered["csrf"]["trusted_proxies"] == ["127.0.0.1"], rendered.get("csrf")
    assert rendered["csrf"]["trusted_origins"] == ["https://pbx.test"], rendered.get("csrf")

    # Passkey wiring (mode ON in this suite): the derived shape from the
    # stack lands in the RENDERED config — rp_id/origins from the vhost
    # domain, the email→extension mapping, and the password-file
    # override (the file path is config, its CONTENT is not).
    pk = rendered["auth"]["passkey"]
    assert pk["rp_id"] == "pbx.test", pk
    assert pk["rp_origins"] == ["https://pbx.test"], pk
    assert pk["users"]["alice@pbx.test"]["extensions"] == ["1000"], pk
    assert pk["users"]["alice@pbx.test"]["display_name"] == "Alice", pk
    assert pk["extension_password_files"]["1000"] == "/etc/telephony/passkey-ext-1000", pk

    # Enrollment token lifecycle, driven through the operator CLI
    # (runuser to the service user, same WEBPHONE_CONFIG as the unit):
    # mint → one verify answers 200 → the burned token answers the same
    # 503 an unknown/expired one gets. No browser: the one-time token is
    # the real gate; the WebAuthn ceremony stays upstream's island-tests.
    bin_path = machine.execute(
        "systemctl show -p ExecStart --value webphone | awk '{print $1}'"
    )[1].strip()
    assert bin_path.startswith("/nix/store/"), bin_path
    out = machine.succeed(
        f"runuser -u webphone -- env WEBPHONE_CONFIG={cfg_path}"
        f" {bin_path} -enroll-passkey alice@pbx.test"
    )
    token_match = re.search(r"token=([A-Za-z0-9_-]+)", out)
    assert token_match is not None, out
    token = token_match.group(1)
    jar = machine.succeed("curl -k -sf -c /tmp/pk-jar https://localhost/api/csrf")
    csrf_match = re.search(r'"token":"([^"]+)"', jar)
    assert csrf_match is not None, jar
    csrf = csrf_match.group(1)

    def enroll_verify(tok):
        return machine.execute(
            "curl -k -s -o /dev/null -w '%{http_code}' -b /tmp/pk-jar"
            f" -H 'X-CSRF-Token: {csrf}' -H 'Content-Type: application/json'"
            f" -d '{json.dumps({'token': tok})}'"
            " https://localhost/api/auth/passkey/enroll/verify"
        )[1].strip()

    first = enroll_verify(token)
    assert first == "200", f"fresh enrollment token must verify 200, got {first}"
    burned = enroll_verify(token)
    assert burned == "503", f"burned token must 503 like unknown/expired, got {burned}"

    # Anti-enumeration (CSRF-authenticated, like the island's own
    # fetches): an unknown email answers the SAME 401 a credential-less
    # account gets — never a distinguishable not-registered signal.
    unknown = machine.execute(
        "curl -k -s -o /dev/null -w '%{http_code}' -b /tmp/pk-jar"
        f" -H 'X-CSRF-Token: {csrf}' -H 'Content-Type: application/json'"
        " -d '{\"email\":\"nobody@pbx.test\"}'"
        " https://localhost/api/auth/passkey/begin"
    )[1].strip()
    assert unknown == "401", f"unknown-email passkey begin must be 401, got {unknown}"

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
