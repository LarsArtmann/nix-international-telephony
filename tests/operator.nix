# Operator window + phone API end-to-end:
#   * telephony-operator service comes up after FreeSWITCH, reads its
#     read-only bind of FreeSWITCH's private state
#   * voicemail deposit (scripted RTP caller) → /phone-api summary shows
#     unread → messages list → token-authed audio fetch (RIFF bytes) →
#     DELETE (via mod_voicemail's vm_delete) → summary back to zero
#   * per-extension auth: the extension's SIP credentials are the API
#     credentials; anything else gets 401 (probed on the operator's
#     loopback listener — over HTTPS the webphone app's session-gated
#     proxy fronts /phone-api now, exercised at the end of this suite)
#   * CDR row from the deposit call shows up in /phone-api history (own
#     accountcode only) and in the operator /operator-api/cdr viewer
#   * operator surface sits behind nginx basic auth (shared htpasswd):
#     no creds → 401, operator creds → health/cdr/sms/simulate + the
#     static dashboard
#   * dialplan simulator answers "what happens to 3000 / 9196"
{ telephonyModule, webphonePackage }:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

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

    # The API is alive on loopback; the webphone app proxies /phone-api
    # to it (exercised at the end of this suite through a real session).
    machine.succeed("curl -sf http://127.0.0.1:8071/healthz | grep -q '\"ok\": true'")
    machine.wait_for_unit("webphone.service")

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
        "curl -s -o /dev/null -w '%{http_code}'"
        " -H 'Authorization: Basic MTAwMDp3cm9uZw=='"
        " http://127.0.0.1:8071/phone-api/voicemail/1000/summary"
    ).strip()
    assert code == "401", f"wrong extension password must be 401, got {code}"
    code = machine.succeed(
        "curl -s -o /dev/null -w '%{http_code}'"
        f" -H 'Authorization: Basic {auth1000}'"
        " http://127.0.0.1:8071/phone-api/voicemail/1001/summary"
    ).strip()
    assert code == "401", f"cross-mailbox access must be 401, got {code}"

    # --- summary: the deposit is unread for 1000 ---
    summary_status, summary_body = machine.execute(
        f"curl -s -H 'Authorization: Basic {auth1000}'"
        " -w '\\n%{http_code}' http://127.0.0.1:8071/phone-api/voicemail/1000/summary"
    )
    summary_lines = summary_body.rsplit("\n", 1)
    summary_code = summary_lines[-1].strip()
    summary = summary_lines[0] if len(summary_lines) > 1 else ""
    if summary_code != "200" or '"new": 1' not in summary:
        # Dump-first failure evidence: unit journal, the ACL unit's state,
        # what the voicemail DB actually contains, and the CDR of the
        # deposit call (hangup cause + timestamps).
        _, debug_dump = machine.execute(
            "echo OPJOURNAL:; journalctl -u telephony-operator --no-pager -n 30;"
            " echo ACLUNIT:; systemctl status telephony-fs-state-acl --no-pager -n 10 2>&1 | head -15;"
            " echo FSACL:; getfacl -p /var/lib/private/freeswitch/db 2>&1 | head -8;"
            " echo VMDB:; python3 -c \"import sqlite3; c=sqlite3.connect('file:/var/lib/private/freeswitch/db/voicemail_default.db?mode=ro', uri=True); print(c.execute('select username, in_folder, read_flags, read_epoch, message_len, uuid from voicemail_msgs').fetchall())\" 2>&1;"
            " echo VMSTORE:; find /var/lib/private/freeswitch/storage/voicemail -type f 2>&1 | head -10;"
            " echo CDR:; cat /var/lib/private/freeswitch/cdr-csv/Master.csv 2>&1"
        )
        print(
            f"OPERATOR-DEBUG: code={summary_code} body={summary}\n"
            f"OPERATOR-DEBUG-DUMP:\n{debug_dump}",
            flush=True,
        )
    assert summary_code == "200", f"summary must be 200, got {summary_code}: {summary}"
    assert '"new": 1' in summary, summary

    # --- messages list + token-authed audio playback ---
    listing = machine.succeed(
        f"curl -sf -H 'Authorization: Basic {auth1000}'"
        " http://127.0.0.1:8071/phone-api/voicemail/1000/messages"
    )
    assert '"uuid"' in listing and '"seconds"' in listing, listing
    # The listing JSON only ever contains double quotes, so single-quoting
    # it for the shell is safe; the earlier r'''-triple-quote trick had its
    # inner double quotes eaten by the shell (SyntaxError -> empty URL ->
    # the SPA's HTML served for "/" instead of the audio stream).
    audio_url = machine.succeed(
        "printf '%s' '"
        + listing
        + "' | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"messages\"][0][\"audio_url\"])'"
    ).strip()
    audio_status, audio_body = machine.execute(
        f"curl -s -H 'Authorization: Basic {auth1000}'"
        f" -w '\\n%{{http_code}}' 'http://127.0.0.1:8071{audio_url}'"
    )
    audio_lines = audio_body.rsplit("\n", 1)
    audio_code = audio_lines[-1].strip()
    audio_head = audio_lines[0][:4] if len(audio_lines) > 1 else ""
    if audio_code != "200" or audio_head != "RIFF":
        _, audio_journal = machine.execute(
            "journalctl -u telephony-operator --no-pager -n 25"
        )
        print(
            f"AUDIO-DEBUG-TEST: code={audio_code} head={audio_head!r}\n"
            f"AUDIO-DEBUG-JOURNAL:\n{audio_journal}",
            flush=True,
        )
    assert audio_code == "200", f"audio fetch must be 200, got {audio_code}: {audio_body[:200]}"
    assert audio_head == "RIFF", f"audio stream must be WAV bytes, got {audio_head!r}"

    # --- history: the depositing caller (1001) has a CDR row; 1000 does not ---
    machine.wait_until_succeeds(
        "grep -q '1001' /var/lib/private/freeswitch/cdr-csv/Master.csv",
        timeout=datetime.timedelta(seconds=60),
    )
    history = machine.succeed(
        f"curl -sf -H 'Authorization: Basic {auth1001}'"
        " http://127.0.0.1:8071/phone-api/history?limit=20"
    )
    assert '"accountcode": "1001"' in history, history
    own_only = machine.succeed(
        f"curl -sf -H 'Authorization: Basic {auth1000}'"
        " http://127.0.0.1:8071/phone-api/history?limit=20"
    )
    assert '"entries": []' in own_only, own_only

    # --- delete the message through the API (mod_voicemail does the work) ---
    uuid = machine.succeed(
        "printf '%s' '"
        + listing
        + "' | python3 -c 'import json,sys; print(json.load(sys.stdin)[\"messages\"][0][\"uuid\"])'"
    ).strip()
    deleted = machine.succeed(
        f"curl -sf -X DELETE -H 'Authorization: Basic {auth1000}'"
        f" http://127.0.0.1:8071/phone-api/voicemail/1000/messages/{uuid}"
    )
    assert '"deleted"' in deleted, deleted
    summary = machine.succeed(
        f"curl -sf -H 'Authorization: Basic {auth1000}'"
        " http://127.0.0.1:8071/phone-api/voicemail/1000/summary"
    )
    assert '"new": 0' in summary, summary
    # vm_boxcount prints a BARE count for its default "new" query
    # (boxcount_api_function: write_function "%d"); the |all form prints
    # new:saved:new-urgent:saved-urgent, so assert the all-empty tuple.
    gone = machine.succeed(f"{fs_cli} 'vm_boxcount 1000@pbx.test|all'")
    assert "0:0:0:0" in gone, gone

    # --- the webphone app fronts /phone-api with a session: login as
    # 1001 (the island's POST /api/session after REGISTER), then the
    # session cookie rides the app's server-side proxy, which injects
    # the Basic auth — exactly the path the browser island takes ---
    login_code = machine.succeed(
        "curl -k -s -c /tmp/wp-cookies -o /dev/null -w '%{http_code}'"
        " -H 'Content-Type: application/json'"
        " -d '{\"extension\": \"1001\", \"password\": \"test-1001-u6t5s4\"}'"
        " https://localhost/api/session"
    ).strip()
    assert login_code == "201", f"webphone session login must be 201, got {login_code}"
    island_history = machine.succeed(
        "curl -k -sf -b /tmp/wp-cookies https://localhost/phone-api/history?limit=20"
    )
    assert '"accountcode": "1001"' in island_history, island_history
    no_session = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}'"
        " https://localhost/phone-api/history"
    ).strip()
    assert no_session == "401", f"phone-api without a session must be 401, got {no_session}"

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
