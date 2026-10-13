# NixOS VM test: the pbx-lens call-history index against the REAL stack.
#
# The lens is the daily driver's History surface: it must ingest the
# FreeSWITCH CDR through the same DynamicUser-crossing read path the
# operator API uses (ro bind + telephony-fs ACLs), re-ingest on its poll
# cadence, and stage a verified snapshot for the stack backups. Proven
# here end to end: a real sofia leg writes a Master.csv row, the poller
# (2s cadence) carries it into /api/export.jsonl, and pbx-lens-backup
# produces a snapshot that passes sqlite integrity_check.
#
# Eval-level twins live in tests/eval.nix (access wiring + state.*
# registration); this suite proves the runtime behavior.
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  lensConfig =
    { pkgs, ... }:
    {
      services.telephony = {
        cdr.enable = true;
        pbx-lens = {
          enable = true;
          # The ro-bind path (the module binds /var/lib/private/freeswitch
          # there): the same convention operatorApiArgs uses.
          cdrFile = "/var/lib/telephony/freeswitch-ro/cdr-csv/Master.csv";
          # The two hosts-side sources (report §f.4: the VM suite covered
          # cdrFile only): the receiver JSONL through the messaging
          # ro-bind, and the agent transcripts through the telephony
          # group — both read paths proven below end to end.
          webhookLog = "/var/lib/telephony/telnyx-webhooks-ro/inbound.jsonl";
          transcriptsDir = "/var/lib/telephony/recordings/transcripts";
          pollEvery = "2s";
        };
        # The bridge (writes inbound.jsonl) + the operator API (the
        # production posture that runs telephony-sms-store-acl, whose
        # telephony-fs ACLs make the bridge files readable).
        messaging = {
          enable = true;
          ownerExtension = "1000";
          did = "+15550001111";
          gatewaySecretFile = "/etc/bridge-secrets/webphone_gateway_secret";
          telnyxApiKeyFile = "/etc/bridge-secrets/telnyx_api_key";
          webhookTokenFile = "/etc/bridge-secrets/telephony_webhook_token";
        };
        operator = {
          enable = true;
          apiPasswordFile = "/etc/bridge-secrets/operator_api_password";
        };
      };
      environment.etc."bridge-secrets/webphone_gateway_secret".text = "test-gw-secret-4d5e6f\n";
      environment.etc."bridge-secrets/telnyx_api_key".text = "KEYtest-not-real\n";
      environment.etc."bridge-secrets/telephony_webhook_token".text = "test-receiver-token-4d5e6f\n";
      environment.etc."bridge-secrets/operator_api_password".text = "test-operator-pass\n";
      # The HOSTS-side override shape (hosts/pbx/default.nix in the
      # deployment repo): list options merge with the module's own
      # telephony-fs render, so the lens unit crosses BOTH private
      # trees — the bind makes the bridge dir walkable, the telephony
      # group reads the recordings transcripts tree.
      systemd.services.pbx-lens = {
        serviceConfig = {
          SupplementaryGroups = [ "telephony" ];
          BindReadOnlyPaths = [
            "/var/lib/private/telnyx-webhooks:/var/lib/telephony/telnyx-webhooks-ro"
          ];
        };
        # Cold-start ordering (the hosts chain gets it via
        # telephony-sms-store-acl, which is after+wants the bridge):
        # systemd binds an EMPTY directory when the BindReadOnlyPaths
        # source does not exist yet, and the bridge's DynamicUser state
        # dir only appears when telnyx-webhooks first starts — without
        # this ordering the lens would bind emptiness on a fresh host.
        after = [ "telnyx-webhooks.service" ];
        wants = [ "telnyx-webhooks.service" ];
      };
      environment.systemPackages = [ pkgs.sqlite ];
    };
in
{
  name = "telephony-lens";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode ++ [ lensConfig ];
    };

  testScript = ''
    ${common.bootWait}
    ${common.helpers}

    import json

    start_all()
    wait_for_freeswitch(machine, "test-es-4d5e6f")

    # Service up, loopback-only listener, and the module's access wiring
    # actually rendered into the unit (bind + group + ACL ordering).
    machine.wait_for_unit("pbx-lens.service")
    machine.succeed("ss -ltn | grep -q '127.0.0.1:8300'")
    machine.succeed("systemctl cat pbx-lens | grep -F '/var/lib/private/freeswitch:/var/lib/telephony/freeswitch-ro'")
    machine.succeed("systemctl cat pbx-lens | grep -F 'telephony-fs'")
    # is-active on a finished Type=oneshot reports "inactive" (exit 3),
    # so this reads the state string instead of requiring exit 0.
    acl_state = machine.execute(
        "systemctl is-active telephony-fs-state-acl.service"
    )[1].strip()
    assert acl_state == "inactive", f"ACL oneshot should have run cleanly, got {acl_state}"

    # A real sofia leg (loopback channels never reach mod_cdr_csv) — the
    # missed-call failover shape from tests/cdr-visibility.nix, chosen so
    # the CDR row lands deterministically without registered endpoints.
    es_password = "test-es-4d5e6f"
    fs_cli = f"fs_cli -p {es_password} -x"
    sip_ip = sip_server(machine)
    out = machine.succeed(
        f"{fs_cli} 'originate {{originate_timeout=5}}sofia/internal/2000@{sip_ip}:5060 &park()'"
    )
    print("ORIGINATE:", out)
    machine.wait_until_succeeds(
        f"{fs_cli} 'show channels' | grep '^0 total'", timeout=60
    )
    machine.succeed("sleep 2")
    rows = machine.execute(
        "cat /var/lib/private/freeswitch/cdr-csv/Master.csv 2>&1 || true"
    )
    print("MASTER-CSV:", rows)
    assert rows[1] != "" and '"2000"' in rows[1], rows

    # The cdr-csv dir may have been created by FS on first write, AFTER
    # the boot-time ACL pass — the same caveat a live host has. Re-run
    # the oneshot so the tree (and its default ACLs) cover the new dir,
    # then let the poller's 2s cadence carry the row into the index.
    machine.succeed("systemctl start telephony-fs-state-acl.service")

    machine.wait_until_succeeds(
        "curl -sf http://127.0.0.1:8300/api/export.jsonl | grep -F '2000'",
        timeout=60,
    )
    # Poller health surfaces: the cdr source counters and freshness.
    ops = machine.succeed("curl -sf http://127.0.0.1:8300/api/ops")
    print("OPS:", ops)
    assert "cdr" in ops.lower(), ops
    machine.succeed("curl -sf http://127.0.0.1:8300/api/freshness")

    # Snapshot staging: the oneshot must produce a verified copy of the
    # index (VACUUM INTO + integrity_check inside the binary).
    machine.succeed("systemctl start pbx-lens-backup.service")
    staged = machine.succeed(
        "test -s /var/lib/pbx-lens/backups/index.db && echo staged"
    ).strip()
    assert staged == "staged", "no staged index snapshot"
    check = machine.succeed(
        "sqlite3 /var/lib/pbx-lens/backups/index.db 'PRAGMA integrity_check'"
    ).strip()
    assert check == "ok", f"staged snapshot failed integrity_check: {check}"

    # ---- webhookLog read path (bridge JSONL through the ro-bind) ------
    # A REAL receiver write (the bridge logs every event) — not a file
    # dropped from outside — so the asserted chain is: bridge writes →
    # telephony-sms-store-acl ACLs → bind + group → poller ingests.
    machine.wait_for_unit("telnyx-webhooks.service")
    machine.wait_for_unit("telephony-operator.service")
    # Diagnostics for the webhook read path (bind + perms), printed so a
    # failure names the broken layer instead of a bare ingest timeout.
    unit_cat = machine.execute("systemctl cat pbx-lens")[1]
    print("LENS-UNIT:", unit_cat)
    probe = machine.execute(
        "ls -la /var/lib/telephony/ /var/lib/telephony/telnyx-webhooks-ro/ 2>&1; "
        "ls -la /var/lib/private/telnyx-webhooks/ 2>&1 || true"
    )
    print("WEBHOOK-PATHS:", probe)
    # CALL-CONTROL shaped (what the lens folds: events without
    # call_control_id + occurred_at are skipped BY DESIGN — messages
    # reach the lens through the Telnyx conversations poller, not the
    # webhook source). The api-dial-test app's webhooks land here in
    # production with exactly this shape.
    event = json.dumps(
        {
            "data": {
                "event_type": "call.initiated",
                "occurred_at": "2026-10-13T12:00:00Z",
                "payload": {
                    "call_control_id": "lens-e2e-ccid",
                    "call_session_id": "lens-e2e-csid",
                    "direction": "incoming",
                    "from": "+15550009999",
                    "to": "+15550001111",
                },
            }
        }
    )
    machine.succeed(
        "curl -sf -X POST -H 'Content-Type: application/json' --data-binary '"
        + event
        + "' http://127.0.0.1:8069/telnyx/webhooks"
    )
    machine.succeed(
        "test -s /var/lib/private/telnyx-webhooks/inbound.jsonl"
    )
    # The bridge created inbound.jsonl on first write, AFTER the boot-time
    # ACL pass — the exact caveat the CDR leg has above. Re-run the
    # oneshot so the file carries the telephony-fs read ACLs, then let
    # the 2s poller carry the event into the index.
    machine.succeed("systemctl start telephony-sms-store-acl.service")
    machine.wait_until_succeeds(
        "curl -sf http://127.0.0.1:8300/api/export.jsonl | grep -F '+15550009999'",
        timeout=60,
    )

    # ---- transcriptsDir read path (agent JSONL through the group) -----
    # The tree the voice agent's tmpfiles would own (2770 root
    # telephony); a transcript without a matching CDR still becomes its
    # own observation (DefaultDirection), keyed by the file name uuid.
    machine.succeed(
        "install -d -m 2770 -o root -g telephony /var/lib/telephony/recordings/transcripts"
    )
    transcript = "\n".join(
        [
            json.dumps({"type": "start", "ts": 1760000000, "uuid": "lens-e2e-uuid", "models": ["m"]}),
            json.dumps({"type": "turn", "role": "caller", "text": "lens transcript ingest probe"}),
            json.dumps({"type": "end", "reason": "agent_end"}),
        ]
    )
    machine.succeed(
        f"printf '%s\\n' '{transcript}' | install -m 0640 -o root -g telephony /dev/stdin /var/lib/telephony/recordings/transcripts/lens-e2e-uuid.jsonl"
    )
    machine.wait_until_succeeds(
        "curl -sf http://127.0.0.1:8300/api/export.jsonl | grep -F 'lens transcript ingest probe'",
        timeout=60,
    )
  '';
}
