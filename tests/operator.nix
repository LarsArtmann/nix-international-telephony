# Operator window + phone API end-to-end:
#   * telephony-operator service comes up after FreeSWITCH, reads its
#     read-only bind of FreeSWITCH's private state
#   * voicemail deposit (scripted RTP caller) → /phone-api summary shows
#     unread → messages list → token-authed audio fetch (RIFF bytes) →
#     DELETE (via mod_voicemail's vm_delete) → summary back to zero
#   * per-extension auth: the extension's SIP credentials are the API
#     credentials; anything else gets 401
#   * CDR row from the deposit call shows up in /phone-api history (own
#     accountcode only) and in the operator /operator-api/cdr viewer
#   * operator surface sits behind nginx basic auth (shared htpasswd):
#     no creds → 401, operator creds → health/cdr/sms/simulate + the
#     static dashboard
#   * dialplan simulator answers "what happens to 3000 / 9196"
let
  common = import ./common.nix;

  operatorPass = "test-operator-pass";
  auth1000 = "MTAwMDp0ZXN0LTEwMDAteDl5OHo3"; # 1000:test-1000-x9y8z7
  auth1001 = "MTAwMTp0ZXN0LTEwMDEtdTZ0NXM0"; # 1001:test-1001-u6t5s4
in
{
  name = "telephony-operator";

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;

      environment.etc."vmclient.py".source = ./vmclient.py;

      services.telephony = {
        # Short-timeout group so the deposit reaches voicemail quickly.
        ringGroups."3000" = {
          members = [ "1000" ];
          timeoutSec = 6;
          voicemailMember = "1000";
        };
        cdr.enable = true;
        webphone.phoneApi.enable = true;
        operator = {
          enable = true;
          apiUser = "admin";
          # Test fixture: store-rendered, like every other test secret.
          apiPasswordFile = "${pkgs.writeText "operator-pass" operatorPass}";
        };
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")

    machine.wait_for_unit("telephony-operator.service")
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)

    fs_cli = "fs_cli -p test-es-4d5e6f -x"
    auth1000 = "${auth1000}"
    auth1001 = "${auth1001}"
    op_auth = "-u admin:${operatorPass}"

    # The API is alive on loopback and nginx proxies both API prefixes.
    machine.succeed("curl -sf http://127.0.0.1:8071/healthz | grep -q '\"ok\": true'")

    # --- deposit: ring group times out, voicemail answers ---
    sip_ip = sip_server(machine)
    vmclient = "python3 /etc/vmclient.py --server " + sip_ip + " --domain pbx.test "
    out = machine.succeed(
        vmclient + "--user 1001 --password test-1001-u6t5s4 deposit --to 3000 --seconds 25"
    )
    assert "VM-DEPOSIT-ANSWERED" in out, out
    assert "VM-DEPOSIT-BYE" in out, out

    # --- per-extension auth: wrong credentials never list a mailbox ---
    code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}'"
        " -H 'Authorization: Basic MTAwMDp3cm9uZw=='"
        " https://localhost/phone-api/voicemail/1000/summary"
    ).strip()
    assert code == "401", f"wrong extension password must be 401, got {code}"
    code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}'"
        f" -H 'Authorization: Basic {auth1000}'"
        " https://localhost/phone-api/voicemail/1001/summary"
    ).strip()
    assert code == "401", f"cross-mailbox access must be 401, got {code}"

    # --- summary: the deposit is unread for 1000 ---
    try:
        summary = machine.succeed(
            f"curl -k -sf -H 'Authorization: Basic {auth1000}'"
            " https://localhost/phone-api/voicemail/1000/summary"
        )
    except Exception:
        _, journal = machine.execute(
            "journalctl -u telephony-operator-api --no-pager -n 30"
        )
        print(f"OPERATOR-DEBUG-JOURNAL:\n{journal}", flush=True)
        raise
    assert '"new": 1' in summary, summary

    # --- messages list + token-authed audio playback ---
    listing = machine.succeed(
        f"curl -k -sf -H 'Authorization: Basic {auth1000}'"
        " https://localhost/phone-api/voicemail/1000/messages"
    )
    assert '"uuid"' in listing and '"seconds"' in listing, listing
    audio_url = machine.succeed(
        "python3 -c \"import json; print(json.loads(r'''"
        + listing
        + "''')['messages'][0]['audio_url'])\""
    ).strip()
    head = machine.succeed(f"curl -k -sf 'https://localhost{audio_url}' | head -c 4")
    assert head == "RIFF", f"audio stream must be WAV bytes, got {head!r}"

    # --- history: the depositing caller (1001) has a CDR row; 1000 does not ---
    machine.wait_until_succeeds(
        "grep -q '1001' /var/lib/private/freeswitch/cdr-csv/Master.csv",
        timeout=datetime.timedelta(seconds=60),
    )
    history = machine.succeed(
        f"curl -k -sf -H 'Authorization: Basic {auth1001}'"
        " https://localhost/phone-api/history?limit=20"
    )
    assert '"accountcode": "1001"' in history, history
    own_only = machine.succeed(
        f"curl -k -sf -H 'Authorization: Basic {auth1000}'"
        " https://localhost/phone-api/history?limit=20"
    )
    assert '"entries": []' in own_only, own_only

    # --- delete the message through the API (mod_voicemail does the work) ---
    uuid = machine.succeed(
        "python3 -c \"import json; print(json.loads(r'''"
        + listing
        + "''')['messages'][0]['uuid'])\""
    ).strip()
    deleted = machine.succeed(
        f"curl -k -sf -X DELETE -H 'Authorization: Basic {auth1000}'"
        f" https://localhost/phone-api/voicemail/1000/messages/{uuid}"
    )
    assert '"deleted"' in deleted, deleted
    summary = machine.succeed(
        f"curl -k -sf -H 'Authorization: Basic {auth1000}'"
        " https://localhost/phone-api/voicemail/1000/summary"
    )
    assert '"new": 0' in summary, summary
    gone = machine.succeed(f"{fs_cli} 'vm_boxcount 1000@pbx.test'")
    assert "new:0" in gone.replace(" ", ""), gone

    # --- operator surface: basic-auth gated by nginx (shared htpasswd) ---
    code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}' https://localhost/operator-api/cdr"
    ).strip()
    assert code == "401", f"operator API without creds must be 401, got {code}"
    page = machine.succeed(f"curl -k -sf {op_auth} https://localhost/operator/")
    assert "PBX Operator" in page, page[:200]
    health = machine.succeed(f"curl -k -sf {op_auth} https://localhost/operator-api/health")
    assert '"internal"' in health and "RUNNING" in health, health
    cdr = machine.succeed(f"curl -k -sf {op_auth} 'https://localhost/operator-api/cdr?limit=20'")
    assert '"destination_number"' in cdr, cdr
    sms = machine.succeed(f"curl -k -sf {op_auth} https://localhost/operator-api/sms")
    assert '"entries": []' in sms, sms

    # --- dialplan simulator: group routing, echo, fax posture ---
    sim_group = machine.succeed(
        f"curl -k -sf {op_auth} 'https://localhost/operator-api/simulate?dest=3000'"
    )
    assert '"type": "bridge"' in sim_group and '"1000"' in sim_group, sim_group
    sim_echo = machine.succeed(
        f"curl -k -sf {op_auth} 'https://localhost/operator-api/simulate?dest=9196'"
    )
    assert '"type": "echo"' in sim_echo, sim_echo
    code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}'"
        f" {op_auth} 'https://localhost/operator-api/simulate?dest=DROP%3Btable'"
    ).strip()
    assert code == "400", f"non-dialable simulator input must be 400, got {code}"
  '';
}
