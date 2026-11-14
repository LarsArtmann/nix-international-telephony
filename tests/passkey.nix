# NixOS VM test for the passkey (WebAuthn) ceremony — browser-level proof
# for the passkey lane, deliberately OUTSIDE `checks` (a chromium closure
# + a solo-run browser suite; run it explicitly with):
#   nix build -L .#legacyPackages.telephony-passkey
#
# What it proves that tests/webphone.nix cannot (its ceremony stays
# upstream's island-tests by design): the FULL round trip through real
# browser surfaces — the CLI-minted one-time enroll token, the /enroll
# page's navigator.credentials.create, and the /login page's
# navigator.credentials.get minting a session. A CDP virtual
# authenticator (ctap2, internal transport) answers both ceremonies, so
# no human and no hardware is involved. Run SOLO (the browser-E2E rule).
#
# Upstream surfaces pinned here (webphone repo):
#   /enroll:      #enroll-form, #enroll-token (prefilled from ?token=),
#                 #enroll-credential-name, #enroll-status, #enroll-error
#   /login:       the loginpage library — #lp-email, #lp-login-btn,
#                 redirect to config.redirect ("/"). Single front door
#                 since 2.14.0: an anonymous shell visit redirects to
#                 /login (the old shell #passkey-login link is gone);
#                 POST /api/session gates the session
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-passkey";

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;

      networking.extraHosts = "127.0.0.1 pbx.test";
      virtualisation.memorySize = 4096;

      # Passkey mode ON — the same fixture shape tests/webphone.nix
      # proves at the render/DOM level (users map + password-file
      # override for an inline-password extension).
      services.telephony.webphone.passkey = {
        enable = true;
        users."alice@pbx.test" = {
          extensions = [ "1000" ];
          displayName = "Alice";
        };
        extensionPasswordFiles."1000" = "/etc/telephony/passkey-ext-1000";
      };
      environment.etc."telephony/passkey-ext-1000" = {
        text = "test-1000-x9y8z7\n";
        user = "webphone";
        mode = "0600";
      };

      # The upstream module's inline-secret guard refuses any
      # secret-shaped settings key with an inline value; baseNode now
      # carries the file form itself (same path, same value), so the
      # overrides below only re-state the file form for clarity and the
      # settings stay secret-free: the boot renderer carries the value
      # as WEBPHONE_TURN_REST__SECRET. Empty string is authSecret's
      # "unset" (the type is plain str, null is not legal) and the
      # exactly-one-of assertion demands exactly one form.
      services.telephony.turn.authSecretFile = "/etc/telephony/turn-secret";
      environment.etc."telephony/turn-secret" = {
        text = "test-turn-rest-4d5e6f\n";
      };

      environment.systemPackages = [
        (pkgs.writeShellScriptBin "passkey-e2e-runner" ''
          exec ${pkgs.python3.withPackages (ps: [ ps.selenium ])}/bin/python3 /etc/passkey-e2e.py "$@"
        '')
      ];
      environment.etc."passkey-e2e.py".source = pkgs.replaceVars ./passkey-e2e.py {
        chromedriver = "${pkgs.chromedriver}/bin/chromedriver";
        chromium = "${pkgs.chromium}/bin/chromium";
      };
    };

  testScript = ''
    ${common.bootWait}

    def wait_marker(marker, timeout):
        # Poll for a phase marker; on stall dump every evidence source
        # before re-raising (the browser.nix discipline).
        try:
            machine.wait_until_succeeds(f"grep -q '{marker}' /tmp/passkey-e2e.log", timeout=datetime.timedelta(seconds=timeout))
        except Exception:
            with machine.nested(f"passkey e2e stalled before {marker}: diagnostics"):
                dumps = [
                    "cat /tmp/passkey-e2e.log || true",
                    "for f in /tmp/chromedriver-passkey-*.log; do echo \"== $f\"; tail -n 120 \"$f\" 2>/dev/null; done || true",
                    "ps aux | grep -E 'chromium|chromedriver' | grep -v grep || true",
                    "journalctl -u webphone --no-pager -n 60 || true",
                    "journalctl -u nginx --no-pager -n 30 || true",
                    "curl -k -s -o /dev/null -w 'vhost status: %{http_code}\\n' https://pbx.test/ || true",
                    "curl -k -s -o /dev/null -w 'login page: %{http_code}\\n' https://pbx.test/login || true",
                ]
                for cmd in dumps:
                    _, out = machine.execute(cmd)
                    print(f"DIAG: {cmd}\\n{out}")
            raise

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    machine.wait_for_unit("webphone.service")
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)
    machine.wait_until_succeeds(
        "curl -k -s -o /dev/null -w '%{http_code}' https://pbx.test/healthz | grep -q 200",
        timeout=datetime.timedelta(seconds=60),
    )

    # Mint the one-time enrollment link EXACTLY as the runbook's
    # "Passkey surfaces" recipe: the CLI runs as the service user with
    # the SAME config and data dir as the server.
    token = machine.succeed(
        "CFG=$(tr '\\0' '\\n' </proc/$(systemctl show -p MainPID --value webphone)/environ"
        " | sed -n 's/^WEBPHONE_CONFIG=//p');"
        # ExecStart --value prints a property OBJECT ("{ path=... ;
        # argv[]=... ; ... }") on this systemd — cut field 1 and you get
        # "{", which env then tries to EXEC (proven twice). Extract the
        # path= field instead.
        " BIN=$(systemctl show -p ExecStart --value webphone"
        " | grep -o 'path=[^ ;]*' | head -1 | cut -d= -f2);"
        " runuser -u webphone -- env WEBPHONE_CONFIG=$CFG \"$BIN\" -enroll-passkey alice@pbx.test"
        " | grep -o 'token=[A-Za-z0-9_-]*' | head -1 | cut -d= -f2"
    ).strip()
    assert token, "enroll token mint failed (empty grep)"
    print(f"ENROLL-TOKEN minted, length {len(token)}")

    # The CLI registers the user as an EVENT; the server's users_view
    # projection consumes it asynchronously. verify reads the token from
    # the event store (immediate), but begin reads the PROJECTION — the
    # first suite run proved the race (begin 30ms after verify answered
    # user_not_found while the projection lagged). Wait for the
    # projection to carry the email before driving the browser.
    machine.wait_until_succeeds(
        "python3 -c \"import sqlite3; c=sqlite3.connect('/var/lib/webphone/usermgmt.db');"
        " assert list(c.execute('select 1 from users_view where email=?', ('alice@pbx.test',)))\"",
        timeout=datetime.timedelta(seconds=30),
    )
    print("USER-PROJECTED")

    # Run-6 countermeasure: the projection wait above went green while
    # begin STILL answered user_not_found — the running server held a
    # stale projection view. Boot replay re-projects every event from
    # the store, so restart the service post-mint and re-prove both
    # the health gate and the projection before the browser phase.
    machine.succeed("systemctl restart webphone.service")
    machine.wait_for_unit("webphone.service")
    machine.wait_until_succeeds(
        "curl -k -s -o /dev/null -w '%{http_code}' https://pbx.test/healthz | grep -q 200",
        timeout=datetime.timedelta(seconds=60),
    )
    machine.wait_until_succeeds(
        "python3 -c \"import sqlite3; c=sqlite3.connect('/var/lib/webphone/usermgmt.db');"
        " assert list(c.execute('select 1 from users_view where email=?', ('alice@pbx.test',)))\"",
        timeout=datetime.timedelta(seconds=30),
    )
    print("USER-PROJECTED-POST-RESTART")

    machine.succeed(f"nohup passkey-e2e-runner {token} > /tmp/passkey-e2e.log 2>&1 &")
    wait_marker("ENROLL-CEREMONY-DONE", 300)
    wait_marker("PASSKEY-E2E-DONE", 300)
  '';
}
