# Integration NixOS VM test for the multi-node scenarios:
#   * recorded calls land in the shared recordings dir, which nginx serves
#     behind basic auth, and the retention timer prunes aged files (machine)
#   * a configured ITSP gateway shows a live REG state, international
#     dialling without toll_allow is denied (603), inbound ACL rejects
#     non-listed sources (403), DIDs route and unknown DIDs 404, and the
#     dialplan bridges gateways in LCR order (machine2)
#   * with recording disabled no files appear, and the extraConfigFiles
#     escape hatch lands files verbatim in the generated config (machine3)
#
# Single-node behaviour (dialplan execution, SIP auth, webphone serving,
# TLS/TURN) lives in tests/dialplan.nix, tests/webphone.nix and
# tests/tls-turn.nix.
let
  common = import ./common.nix;

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
      imports = common.baseNode ++ [ recordingServeConfig ];
    };

  nodes.machine2 =
    { ... }:
    {
      imports = common.baseNode ++ [ gatewayTelephony ];
    };

  nodes.machine3 =
    { ... }:
    {
      imports = common.baseNode ++ [
        noRecordingTelephony
        extraFileTelephony
      ];
    };

  testScript = ''
    ${common.bootWait}

    # NOTE: no start_all() — machines start lazily at their first
    # command, which staggers the heavy sofia startup across the three
    # nodes (and mirrors how the single-node suites behave anyway).
    wait_for_freeswitch(machine, "test-es-4d5e6f")

    es_password = "test-es-4d5e6f"
    fs_cli = f"fs_cli -p {es_password} -x"

    machine.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep internal")

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
        timeout=datetime.timedelta(seconds=60),
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

    # Recording directory provisioned by the module.
    machine.succeed("test -d /var/lib/telephony/recordings")

    # --- Gateway node (machine2): REG state + denial paths ---
    # sofia binds $${local_ip_v4} (egress interface, or loopback when
    # no default route exists yet), so derive each profile's actual
    # listen address instead of assuming localhost.
    machine2.wait_for_unit("freeswitch.service")
    wait_for_freeswitch(machine2, "test-es-4d5e6f", port_timeout=datetime.timedelta(seconds=120))
    machine2.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep internal")

    # The gateway object is live; the fictitious proxy never answers, so
    # any active REG state machine (not an unknown gateway) is the proof.
    gateway_status = machine2.wait_until_succeeds(
        f"{fs_cli} 'sofia status gateway primary'", timeout=datetime.timedelta(seconds=60)
    )
    assert "203.0.113.99" in gateway_status, gateway_status
    backup_status = machine2.wait_until_succeeds(
        f"{fs_cli} 'sofia status gateway backup'", timeout=datetime.timedelta(seconds=60)
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
        f"python3 /etc/sip.py --server {sip_server(machine2, 5080)} --port 5080 "
        "--bind 127.0.0.2 "
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
    # answers 404. Bind the client source to 127.0.0.1 explicitly: the
    # external profile's ACL lists exactly that address, and without a
    # bind the source would follow the server address.
    machine2.succeed(
        f"python3 /etc/sip.py --server {sip_server(machine2, 5080)} --port 5080 "
        "--bind 127.0.0.1 "
        "--domain pbx.test --user 1002 --password test-1002-m3n4o5 "
        "invite --to 15551239999 --skip-register --hold-seconds 2"
    )
    unknown_did = machine2.succeed(
        f"python3 /etc/sip.py --server {sip_server(machine2, 5080)} --port 5080 "
        "--bind 127.0.0.1 "
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

    # --- Recording disabled (machine3): same call, no files appear ---
    machine3.wait_for_unit("freeswitch.service")
    wait_for_freeswitch(machine3, "test-es-4d5e6f", port_timeout=datetime.timedelta(seconds=120))
    machine3.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep internal")
    # With recording off the module provisions no shared directory at all.
    machine3.succeed("test ! -e /var/lib/telephony/recordings")
    unrecorded = machine3.succeed(f"{fs_cli} 'originate loopback/1001 &park()'")
    assert unrecorded.startswith("+OK"), unrecorded
    machine3.succeed("sleep 3")
    machine3.succeed("test ! -e /var/lib/telephony/recordings")
    machine3.succeed(f"{fs_cli} 'hupall'")

    # Escape hatch: the extraConfigFiles file is merged verbatim into the
    # generated config directory (and the generated dialplan still loads).
    machine3.succeed(
        "grep -q 'Escape-hatch smoke test' /nix/store/*freeswitch-config-*/dialplan/zz-extra-test.xml"
    )
  '';
}
