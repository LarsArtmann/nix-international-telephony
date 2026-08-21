# NixOS VM test for the whole telephony stack:
#   * FreeSWITCH loads the generated config and opens SIP + WebSocket listeners
#   * the generated directory (extensions) is queryable
#   * the generated dialplan actually executes (loopback call through echo test)
#   * a scripted SIP client (tests/sip.py) registers over TCP with digest
#     auth, gets rejected on bad credentials, places an answered call and
#     holds two registrations at once (multi-device)
#   * a configured ITSP gateway shows a live REG state, international dialling
#     without toll_allow is denied (403) and E.164 without a gateway 503s
#   * nginx serves the webphone and its config over TLS
#   * the /sip WebSocket proxy reaches FreeSWITCH
#   * coturn listens for STUN/TURN
#   * recorded calls land in the shared recordings dir, which nginx serves
#     behind basic auth, and the retention timer prunes aged files
let
  # Scripted SIP client for SIP-level assertions.
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

  # machine2 only: a fictitious ITSP gateway (TEST-NET-3 proxy that never
  # answers) plus an extension denied international dialling. The inbound
  # ACL lists a TEST-NET-2 range so the test client (127.0.0.1) is denied.
  gatewayTelephony = {
    services.telephony = {
      gateways.primary = {
        proxy = "203.0.113.99:5060";
        username = "testuser";
        password = "test-gw-pass";
        did = "15551230000";
        didDestination = "1000";
        priority = 10;
        # 127.0.0.1 is the test client's address; 127.0.0.2 plays a
        # non-listed source for the ACL rejection test.
        allowedCidrs = [ "127.0.0.1/32" ];
      };
      gateways.backup = {
        proxy = "203.0.113.100:5060";
        username = "backupuser";
        password = "test-gw-backup";
        did = "15551239999";
        didDestination = "1001";
        priority = 20;
      };
      firewall.restrictExternalTo = [ "198.51.100.0/24" ];
      extensions."1002" = {
        password = "test-1002-m3n4o5";
        displayName = "No International";
        allowInternational = false;
      };
    };
  };

  # machine only: CSV call detail records enabled.
  cdrTestConfig = {
    services.telephony.cdr.enable = true;
  };

  # machine only: serve recordings over HTTPS behind basic auth, plus a
  # retention window. The password file is an /etc symlink into the store —
  # throwaway credentials, fine for the test VM.
  recordingServeConfig = {
    environment.etc."telephony-recordings-password".text = "test-recordings-pw";
    services.telephony = {
      recording.serve = {
        enable = true;
        basicAuthPasswordFile = "/etc/telephony-recordings-password";
      };
      recording.retentionDays = 7;
    };
  };

  # machine3 only: recording disabled — no files may appear.
  noRecordingTelephony = {
    services.telephony.recording.enable = false;
  };

  # machine3 only: the extraConfigFiles escape hatch — an additive file
  # must land in the generated config directory verbatim.
  extraFileTelephony = {
    services.telephony.extraConfigFiles."dialplan/zz-extra-test.xml" = ./extra-dialplan.xml;
  };
in
{
  name = "telephony";

  nodes.machine =
    { ... }:
    {
      imports = [
        ../modules/telephony.nix
        sipClientModule
        baseTelephony
        cdrTestConfig
        recordingServeConfig
      ];

      networking.firewall.enable = true;
      system.stateVersion = "26.05";
    };

  nodes.machine2 =
    { ... }:
    {
      imports = [
        ../modules/telephony.nix
        sipClientModule
        baseTelephony
        gatewayTelephony
      ];

      networking.firewall.enable = true;
      system.stateVersion = "26.05";
    };

  nodes.machine3 =
    { ... }:
    {
      imports = [
        ../modules/telephony.nix
        sipClientModule
        baseTelephony
        noRecordingTelephony
        extraFileTelephony
      ];

      networking.firewall.enable = true;
      system.stateVersion = "26.05";
    };

  testScript = ''
    # NOTE: no start_all() — machines start lazily at their first command.
    # Booting all three QEMU VMs at once stalled one node's sofia mid-start
    # on shared CI runners (nested KVM, 100% reproducible there, never
    # locally even pinned to a single core); staggering the heavy sofia
    # startup phase recreates the known-green one-VM-at-a-time condition.
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
    # Tear the parked loopback call down so later `show channels` greps
    # only see calls placed by the scripted SIP client.
    machine.succeed(f"{fs_cli} 'hupall'")
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'")

    # CDR: the finished call leaves a row in Master.csv.
    machine.wait_until_succeeds(
        "grep 9196 /var/lib/freeswitch/cdr-csv/Master.csv", timeout=30
    )

    # --- SIP-level checks with the scripted client (tests/sip.py) ---
    def sip_server(node):
        listener = node.succeed("ss -ltn 'sport = :5060' | grep -v State").strip()
        ip = listener.split()[3].rsplit(":", 1)[0]
        return "::1" if ip.startswith("[") else ip

    sip_ip = sip_server(machine)
    sip = (
        f"python3 /etc/sip.py --server {sip_ip} --domain pbx.test "
        "--user 1000 --password test-1000-x9y8z7"
    )

    # REGISTER with correct credentials is accepted and listed by sofia.
    out = machine.succeed(f"{sip} register")
    assert "REGISTER 200" in out, out
    machine.wait_until_succeeds(
        f"{fs_cli} 'sofia status profile internal reg' | grep 1000"
    )

    # REGISTER with a wrong password must be rejected after the challenge.
    status, wrong = machine.execute(
        f"python3 /etc/sip.py --server {sip_ip} --domain pbx.test "
        "--user 1000 --password definitely-wrong register"
    )
    assert status != 0, wrong
    assert "REGISTER 401" in wrong or "REGISTER 403" in wrong, wrong

    # A second registration from another client (different source port)
    # must coexist: multiple-registrations is on.
    machine.succeed(f"{sip} register")
    regs = machine.succeed(f"{fs_cli} 'sofia status profile internal reg'")
    assert regs.count("Call-ID:") == 2, regs

    # INVITE through the dialplan: the echo test must answer (200 with
    # SDP), stay up while we check channel state, then hang up cleanly.
    machine.succeed(
        f"nohup {sip} invite --to 9196 --hold-seconds 6 >/tmp/invite.log 2>&1 &"
    )
    machine.wait_until_succeeds(
        f"{fs_cli} 'show channels' | grep 'sofia/internal/1000@pbx.test'", timeout=60
    )
    media = machine.succeed(f"{fs_cli} 'show detailed_calls'")
    assert "9196" in media and "PCMU" in media, media
    machine.wait_until_succeeds("grep -q 'CALL COMPLETE' /tmp/invite.log", timeout=60)
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'")
    # Drop the helper's registrations so later bridge tests hit clean
    # USER_NOT_REGISTERED failures instead of dead TCP contacts.
    machine.succeed(f"{fs_cli} 'sofia profile internal flush_inbound_reg'")

    # Denial: with no gateway configured, E.164 calls answer 503.
    machine.succeed(
        f"{fs_cli} 'console loglevel debug' && {fs_cli} 'sofia global siptrace on'"
    )
    status503, unavailable = machine.execute(
        f"{sip} invite --to 12345678901 --expect-status 503"
    )
    status404, unknown = machine.execute(
        f"{sip} invite --to 555 --expect-status 404"
    )
    if status503 != 0 or status404 != 0:
        print(machine.succeed("journalctl -u freeswitch -q --no-pager | tail -n 150"))
    machine.succeed(
        f"{fs_cli} 'sofia global siptrace off' && {fs_cli} 'console loglevel info'"
    )
    assert status503 == 0, unavailable
    assert "INVITE 503" in unavailable, unavailable
    assert status404 == 0, unknown
    assert "INVITE 404" in unknown, unknown

    # --- Recording: dialled extension calls leave a growing WAV on disk ---
    # The directory is shared (root:telephony 2770) so nginx can serve it.
    machine.succeed("rm -f /var/lib/telephony/recordings/*.wav")
    machine.succeed(
        "test \"$(stat -c %a /var/lib/telephony/recordings)\" = 2770"
    )
    recorded = machine.succeed(f"{fs_cli} 'originate loopback/1001 &park()'")
    assert recorded.startswith("+OK"), recorded
    machine.wait_until_succeeds(
        "test \"$(stat -c %s /var/lib/telephony/recordings/*_1001.wav 2>/dev/null || echo 0)\" -gt 10000",
        timeout=60,
    )
    machine.succeed(f"{fs_cli} 'hupall'")

    # --- Recordings serving: basic auth gates the listing, the WAV is
    # browsable with credentials (htpasswd rendered from the password file) ---
    machine.wait_until_succeeds("test -s /var/lib/telephony/recordings.htpasswd")
    no_auth = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}' https://localhost/recordings/"
    ).strip()
    assert no_auth == "401", no_auth
    bad_auth = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}'"
        " -u admin:wrong https://localhost/recordings/"
    ).strip()
    assert bad_auth == "401", bad_auth
    listing = machine.succeed(
        "curl -k -f -u admin:test-recordings-pw https://localhost/recordings/"
    )
    assert "_1001.wav" in listing, listing

    # --- Retention: files past the window are pruned, fresh ones survive ---
    machine.succeed("touch -d '30 days ago' /var/lib/telephony/recordings/aged.wav")
    machine.succeed("systemctl start telephony-recording-retention.service")
    machine.succeed("test ! -e /var/lib/telephony/recordings/aged.wav")
    machine.succeed("ls /var/lib/telephony/recordings/*_1001.wav >/dev/null")

    # --- Ring-group fallback: an unanswered 2000 rings (early media),
    # times out after the group's 25s and is answered by the voicemail
    # fallback — the only possible 200 for this call. ---
    machine.succeed(
        f"nohup {sip} invite --to 2000 --hold-seconds 3 >/tmp/ringgroup.log 2>&1 &"
    )
    machine.wait_until_succeeds("grep -q 'CALL COMPLETE' /tmp/ringgroup.log", timeout=120)
    ringgroup_log = machine.succeed("cat /tmp/ringgroup.log")
    assert "ANSWERED" in ringgroup_log, ringgroup_log
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'", timeout=60)

    # --- *98 reaches the voicemail-check application (answered by it) ---
    machine.succeed(
        f"nohup {sip} invite --to '*98' --hold-seconds 3 >/tmp/vmcheck.log 2>&1 &"
    )
    machine.wait_until_succeeds("grep -q 'CALL COMPLETE' /tmp/vmcheck.log", timeout=60)
    vmcheck_log = machine.succeed("cat /tmp/vmcheck.log")
    assert "ANSWERED" in vmcheck_log, vmcheck_log
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'", timeout=60)

    # --- SIP-over-TLS (5061) and the external profile (5080) listen ---
    machine.wait_until_succeeds("ss -ltn | grep ':5061'")
    machine.wait_until_succeeds("ss -ltn | grep ':5080'")
    machine.wait_until_succeeds("ss -lun | grep ':5080'")

    # Web endpoints.
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)
    page = machine.succeed("curl -k -f https://localhost/")
    assert "WebPhone" in page, page
    assert "sip.min.js" in page, page

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

    # A non-WebSocket request through the proxy must reach FreeSWITCH
    # (anything but 502/504 proves nginx talks to sofia's ws transport).
    code = machine.succeed("curl -k -s -o /dev/null -w '%{http_code}' https://localhost/sip").strip()
    assert code not in ("502", "504", "000"), code

    machine.wait_for_unit("coturn.service")
    machine.wait_for_open_port(3478)

    # --- TURN: STUN answers, REST credentials allocate, wrong secret 401 ---
    machine.succeed("test -s /var/lib/telephony/config.js")
    turnpy = "python3 /etc/turn.py"
    machine.succeed(f"{turnpy} stun --server 127.0.0.1")
    turn_username, turn_credential = machine.succeed(
        "curl -k -f https://localhost/config.js"
        " | sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//'"
        " | python3 -c 'import json,sys; c=json.load(sys.stdin);"
        " t=[s for s in c[\"iceServers\"] if any(u.startswith(\"turn:\") for u in s[\"urls\"])][0];"
        " print(t[\"username\"], t[\"credential\"])'"
    ).split()
    # The served credential must equal the coturn REST derivation
    # (HMAC-SHA1 over "<expiry>:webphone" with the configured secret).
    machine.succeed(
        "curl -k -f https://localhost/config.js"
        " | sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//'"
        " | python3 -c 'import base64,hashlib,hmac,json,sys;"
        " c=json.load(sys.stdin);"
        " t=[s for s in c[\"iceServers\"] if any(u.startswith(\"turn:\") for u in s[\"urls\"])][0];"
        " u=t[\"username\"].encode();"
        " e=base64.b64encode(hmac.new(b\"test-turn-rest-4d5e6f\", u, hashlib.sha1).digest()).decode();"
        " assert e == t[\"credential\"], (e, t[\"credential\"])'"
    )
    machine.succeed(
        f"{turnpy} allocate --server 127.0.0.1"
        f" --username '{turn_username}' --password '{turn_credential}'"
    )
    machine.succeed(
        f"{turnpy} allocate --server 127.0.0.1"
        " --username '9999999999:evil' --password 'wrong' --expect-401"
    )

    # --- Gateway node (machine2): REG state + denial paths ---
    machine2.wait_for_unit("freeswitch.service")
    machine2.wait_for_open_port(5060)
    machine2.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep internal")

    # The gateway object is live; the fictitious proxy never answers, so
    # any active REG state machine (not an unknown gateway) is the proof.
    gateway_status = machine2.wait_until_succeeds(
        f"{fs_cli} 'sofia status gateway primary'", timeout=60
    )
    assert "203.0.113.99" in gateway_status, gateway_status
    backup_status = machine2.wait_until_succeeds(
        f"{fs_cli} 'sofia status gateway backup'", timeout=60
    )
    assert "203.0.113.100" in backup_status, backup_status
    assert any(
        state in gateway_status
        for state in ("TRYING", "FAILED", "FAIL_WAIT", "NOREG", "REGED")
    ), gateway_status

    # Denial path 1: an extension without international toll_allow is
    # declined (hangup cause call_rejected -> SIP 603 in this FreeSWITCH).
    machine2.succeed(f"{fs_cli} 'sofia global siptrace on'")
    sip2 = (
        f"python3 /etc/sip.py --server {sip_server(machine2)} --domain pbx.test "
        "--user 1002 --password test-1002-m3n4o5"
    )
    denial_status, denied = machine2.execute(
        f"{sip2} invite --to 12345678901 --expect-status 603"
    )
    if denial_status != 0:
        print(machine2.succeed("journalctl -u freeswitch -q --no-pager | tail -n 120"))
    machine2.succeed(f"{fs_cli} 'sofia global siptrace off'")
    assert denial_status == 0, denied
    assert "INVITE 603" in denied, denied

    # Inbound ACL: an INVITE from a non-listed source on the external
    # profile (5080) is rejected before the dialplan.
    acl_status, acl_denied = machine2.execute(
        "python3 /etc/sip.py --server 127.0.0.1 --port 5080 --bind 127.0.0.2 "
        "--domain pbx.test --user 1002 --password test-1002-m3n4o5 "
        "invite --to 15551230000 --skip-register --expect-status 403"
    )
    if acl_status != 0:
        print(machine2.succeed("journalctl -u freeswitch -q --no-pager | tail -n 120"))
    assert acl_status == 0, acl_denied
    assert "INVITE 403" in acl_denied, acl_denied

    # DID routing: an allowed source dialling a configured DID is
    # transferred into the default context (answered by the extension's
    # voicemail fallback); an unknown DID stays in the public context and
    # answers 404.
    machine2.succeed(
        "python3 /etc/sip.py --server 127.0.0.1 --port 5080 "
        "--domain pbx.test --user 1002 --password test-1002-m3n4o5 "
        "invite --to 15551239999 --skip-register --hold-seconds 2"
    )
    unknown_did = machine2.succeed(
        "python3 /etc/sip.py --server 127.0.0.1 --port 5080 "
        "--domain pbx.test --user 1002 --password test-1002-m3n4o5 "
        "invite --to 19999999999 --skip-register --expect-status 404"
    )
    assert "INVITE 404" in unknown_did, unknown_did

    # LCR: the generated dialplan tries gateways in ascending priority
    # with serial failover.
    dialplan = machine2.succeed(
        "grep 'sofia/gateway/' /nix/store/*freeswitch-config-*/dialplan/default.xml"
    )
    bridge_line = [l for l in dialplan.splitlines() if "gateway/primary/" in l][0]
    assert "gateway/primary/" in bridge_line and "gateway/backup/" in bridge_line, bridge_line
    assert bridge_line.index("gateway/primary/") < bridge_line.index("gateway/backup/"), bridge_line

    # Denial path 2 (see the 503 check on machine above): kept adjacent to
    # the gateway asserts; machine2 differs only by having a gateway.

    # --- Recording disabled (machine3): same call, no files appear ---
    machine3.wait_for_unit("freeswitch.service")
    machine3.wait_for_open_port(5060)
    machine3.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep internal")
    # With recording off the module provisions no shared directory at all.
    machine3.succeed("test ! -e /var/lib/telephony/recordings")
    unrecorded = machine3.succeed(f"{fs_cli} 'originate loopback/1001 &park()'")
    assert unrecorded.startswith("+OK"), unrecorded
    machine3.succeed("sleep 3")
    machine3.succeed("test ! -e /var/lib/telephony/recordings")
    machine3.succeed(f"{fs_cli} 'hupall'")

    # Recording directory provisioned by the module.
    machine.succeed("test -d /var/lib/telephony/recordings")

    # Escape hatch: the extraConfigFiles file is merged verbatim into the
    # generated config directory (and the generated dialplan still loads).
    machine3.succeed(
        "grep -q 'Escape-hatch smoke test' /nix/store/*freeswitch-config-*/dialplan/zz-extra-test.xml"
    )
  '';
}
