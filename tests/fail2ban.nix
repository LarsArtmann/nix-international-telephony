# fail2ban SIP-jail VM test (M17 of the live-PBX plan): repeated
# REGISTER auth failures from one source IP end in a fail2ban ban of
# that address (the jail watches the FreeSWITCH journal). The scripted
# bad client binds 127.0.0.2 so the ban cannot cut the test's own leg.
{ webphonePackage }:
let
  common = import ./common.nix { inherit webphonePackage; };
in
{
  name = "telephony-fail2ban";

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;

      environment.systemPackages = [ pkgs.fail2ban ];

      services.telephony.fail2ban = {
        enable = true;
        maxretry = 3;
        findtime = 60;
        bantime = 60;
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")

    sip_ip = sip_server(machine)

    # Auth-failure spam from a dedicated source address.
    # fail2ban's default ignoreself rule skips loopback sources (they
    # count as "self"), so the scripted offender needs a non-loopback
    # source: a TEST-NET-2 address parked on lo for this test.
    machine.succeed("ip addr add 198.51.100.7/32 dev lo")
    bad = (
        "python3 /etc/sip.py --server " + sip_ip + " --bind 198.51.100.7 "
        + "--domain pbx.test --user 1000 --password definitely-wrong register"
    )
    for i in range(4):
        status, out = machine.execute(bad)
        print(f"BAD-REGISTER[{i}] status={status} out={out[:300]}")
        assert status != 0, out

    # fail2ban itself starts only once the freeswitch log file exists
    # (preStart wait) — feed the jail lines that are guaranteed to land
    # after its pyinotify watcher is up.
    machine.wait_until_succeeds(
        "fail2ban-client status freeswitch-sip | grep -q 'Status for the jail'",
        timeout=90,
    )
    for i in range(4, 8):
        status, out = machine.execute(bad)
        print(f"BAD-REGISTER[{i}] status={status} out={out[:300]}")
        assert status != 0, out

    # The jail sees the failures and bans 198.51.100.7.
    machine.wait_until_succeeds(
        "fail2ban-client get freeswitch-sip banned | grep -q 198.51.100.7",
        timeout=90,
    )
    # The other tests' source addresses stay unbanned.
    machine.succeed(
        "! fail2ban-client get freeswitch-sip banned | grep -q 127.0.0.1"
    )

    # --- nginx/443 scanner jail: bot-path probes get banned from 443 ---
    # A SECOND dedicated offender (the SIP ban above already blocks
    # 198.51.100.7): scanner probes against the webphone vhost (served
    # by the base fixture) earn a 443 ban; legit asset fetches never
    # match the filter, so only the offender accumulates strikes.
    machine.succeed("ip addr add 198.51.100.8/32 dev lo")
    machine.wait_for_unit("nginx.service")
    machine.wait_until_succeeds(
        "fail2ban-client status nginx-scanner | grep -q 'Status for the jail'",
        timeout=90,
    )
    # First probe must reach the vhost (404 for the bot path); later
    # probes may legitimately hit the ban (curl exit 7, code 000) once
    # fail2ban has seen maxretry strikes.
    scanner = (
        "curl -k -s -o /dev/null -w '%{http_code}'"
        " --interface 198.51.100.8 https://198.51.100.8/wp-login.php"
    )
    first_code = machine.succeed(scanner).strip()
    assert first_code == "404", first_code
    for i in range(3):
        status, out = machine.execute(scanner)
        print(f"SCANNER-PROBE[{i}] status={status} out={out[:200]}")
        assert status == 0 or "000" in out, out
    # DIAG: where did the access lines land?
    with machine.nested("nginx scanner diagnostics"):
        for cmd in [
            "ls -la /var/log/nginx/ || true",
            "wc -l /var/log/nginx/telephony-access.log || true",
            "tail -5 /var/log/nginx/telephony-access.log || true",
            "fail2ban-client status nginx-scanner || true",
            "nginx -T 2>/dev/null | grep -n 'access_log' || true",
            "journalctl -u fail2ban -q --no-pager | tail -n 25 || true",
        ]:
            _, out = machine.execute(cmd)
            print(f"DIAG: {cmd}\n{out}")
    machine.wait_until_succeeds(
        "fail2ban-client get nginx-scanner banned | grep -q 198.51.100.8",
        timeout=90,
    )
    # Legitimate traffic (an ordinary webphone fetch from localhost)
    # stays unbanned, and the scanner never touched the SIP jail.
    machine.succeed("curl -k -f https://localhost/")
    machine.succeed(
        "! fail2ban-client get nginx-scanner banned | grep -q 127.0.0.1"
    )
    machine.succeed(
        "! fail2ban-client get freeswitch-sip banned | grep -q 198.51.100.8"
    )
  '';
}
