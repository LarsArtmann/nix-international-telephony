# The theme-ONLY slice of the browser E2E: the fast relock-ritual lane
# for markup/theme-only deltas (one browser, no call, minutes instead of
# the full suite's ~20). Run:
#   nix build -L .#legacyPackages.x86_64-linux.telephony-theme
# THEME_ONLY=1 gates tests/browser-e2e.py's main to just the theme FOUC
# check (preload blocked/allowed evidence pair). Its green NEVER
# substitutes for the full browser suite's — markup deltas still owe the
# full run (the DOM contract, the call drills, the ended-card pins).
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-theme";

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;

      # Same browser surfaces as tests/browser.nix: the vhost by its
      # configured name, headroom for chromium.
      networking.extraHosts = "127.0.0.1 pbx.test";
      virtualisation.memorySize = 4096;

      environment.systemPackages = [
        # THEME_ONLY=1: the E2E script runs just the theme FOUC check.
        (pkgs.writeShellScriptBin "theme-e2e-runner" ''
          export THEME_ONLY=1
          exec ${pkgs.python3.withPackages (ps: [ ps.selenium ])}/bin/python3 /etc/browser-e2e.py "$@"
        '')
      ];

      environment.etc."browser-e2e.py".source = pkgs.replaceVars ./browser-e2e.py {
        chromedriver = "${pkgs.chromedriver}/bin/chromedriver";
        chromium = "${pkgs.chromium}/bin/chromium";
      };
    };

  testScript = ''
    ${common.bootWait}

    def wait_marker(marker, timeout):
        try:
            machine.wait_until_succeeds(f"grep -q '{marker}' /tmp/e2e.log", timeout=datetime.timedelta(seconds=timeout))
        except Exception:
            with machine.nested(f"theme e2e stalled before {marker}: diagnostics"):
                dumps = [
                    "cat /tmp/e2e.log || true",
                    "for f in /tmp/chromedriver-*.log; do echo \"== $f\"; tail -n 120 \"$f\" 2>/dev/null; done || true",
                    "ps aux | grep -E 'chromium|chromedriver' | grep -v grep || true",
                    "journalctl -u nginx --no-pager -n 30 || true",
                    "curl -k -s -o /dev/null -w 'vhost status: %{http_code}\\n' https://pbx.test/ || true",
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

    machine.succeed("nohup theme-e2e-runner > /tmp/e2e.log 2>&1 &")
    wait_marker("THEME-CHECK-DONE", 300)
    wait_marker("E2E-THEME-ONLY-DONE", 60)
  '';
}
