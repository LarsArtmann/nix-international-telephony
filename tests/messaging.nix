# NixOS VM test for the Telnyx messaging bridge (modules/telephony/
# messaging.nix + telnyx-webhooks.py): the receiver logs every Telnyx
# event to inbound.jsonl, a message.received event becomes a REAL
# webphone inbound row for the owner extension, a bridge whose forward
# fails answers Telnyx 503 (the retry contract) and Telnyx's retry
# lands once webphone is back, and the token gate guards /recent.
#
# The suite runs against the real webphone service (not a stub sink):
# the hook-secret check, the row and the 503 answer are all production
# behavior. The outbound leg (webphone → /gateway/message → the Telnyx
# Messages API) stays unit-test-covered — this VM has no Telnyx to
# answer, and a fake one would assert the stub, not the product.
{
  telephonyModule,
  webphonePackage,
  kvm ? true,
  slowBoot ? false,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  bootTimeouts = if slowBoot then ", port_timeout=900, unit_timeout=900" else "";
in
{
  name = if kvm then "telephony-messaging" else "telephony-messaging-tcg";

  requiredFeatures.kvm = kvm;

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;
      environment.systemPackages = [ pkgs.sqlite ];
      # The three bridge credentials as plain /etc files: the unit's
      # LoadCredential entries point here (a missing source file fails
      # the unit start, so they must exist even in the test).
      environment.etc."bridge-secrets/webphone_gateway_secret".text = "test-gw-secret-4d5e6f\n";
      environment.etc."bridge-secrets/telnyx_api_key".text = "KEYtest-not-real\n";
      environment.etc."bridge-secrets/telephony_webhook_token".text = "test-receiver-token-4d5e6f\n";
      # The in-VM stub Telnyx (WhatsApp arms): the bridge's outbound API
      # base points at it, so the REAL unit → bridge → HTTP wiring is
      # exercised against a scripted server instead of unit mocks.
      environment.etc."telnyx_stub.py".source = ./telnyx_stub.py;
      systemd.services.telnyx-webhooks.environment.TELNYX_API_BASE = "http://127.0.0.1:4545/v2";
      services.telephony.messaging = {
        enable = true;
        ownerExtension = "1000";
        # baseNode configures no gateway, so the sole-gateway default
        # has nothing to derive from — name the DID explicitly.
        did = "+15550001111";
        gatewaySecretFile = "/etc/bridge-secrets/webphone_gateway_secret";
        telnyxApiKeyFile = "/etc/bridge-secrets/telnyx_api_key";
        webhookTokenFile = "/etc/bridge-secrets/telephony_webhook_token";
        whatsapp = {
          enable = true;
          did = "+15550003333";
        };
      };
      # The gateway seam is auto-wired: the bridge module derives
      # webphone's gateway mode/URL/secret-file from
      # messaging.gatewaySecretFile (both sides read the SAME file), so
      # the old inline `settings.gateway.webhook_secret` line is gone —
      # a mismatch is now structurally impossible, asserted below via
      # the rendered runtime config.
    };

  testScript = ''
    ${common.bootWait}

    # Only the web half matters here: no sofia wait, no calls — the
    # bridge is an HTTP producer and webphone is the consumer.
    machine.wait_for_unit("webphone.service"${bootTimeouts})
    machine.wait_for_open_port(8080)
    machine.wait_for_unit("telnyx-webhooks.service")
    machine.wait_for_open_port(8069)

    import json

    # Gateway auto-wire proof: the rendered runtime config (the store
    # JSON the unit booted with) carries webhook mode, the loopback
    # bridge URL and the shared secret FILE — never an inline secret.
    cfg_path = machine.execute(
        "tr '\\0' '\\n' < /proc/$(systemctl show -p MainPID --value webphone)/environ"
        " | sed -n 's/^WEBPHONE_CONFIG=//p'"
    )[1].strip()
    assert cfg_path.startswith("/nix/store/"), f"WEBPHONE_CONFIG not found: {cfg_path!r}"
    rendered = json.loads(machine.succeed(f"cat {cfg_path}"))
    assert rendered["gateway"]["mode"] == "webhook", rendered.get("gateway")
    assert rendered["gateway"]["webhook_url"] == "http://127.0.0.1:8069/gateway", rendered["gateway"]
    assert rendered["gateway"]["webhook_secret_file"] == "/etc/bridge-secrets/webphone_gateway_secret", rendered["gateway"]
    assert "webhook_secret" not in rendered["gateway"], rendered["gateway"]

    # Receiver health + gateway health (all three credentials present).
    machine.succeed(
        "curl -sf http://127.0.0.1:8069/telnyx/webhooks/health | grep -q '\"ok\": true'"
    )
    machine.succeed(
        "curl -sf http://127.0.0.1:8069/gateway/health | grep -q '\"webphone_secret\": true'"
    )
    machine.succeed(
        "curl -sf http://127.0.0.1:8069/gateway/health | grep -q '\"telnyx_api_key\": true'"
    )

    # The /recent reader is token-gated: closed without, open with.
    machine.fail("curl -sf http://127.0.0.1:8069/telnyx/webhooks/recent")
    machine.succeed(
        "curl -sf -H 'Authorization: Bearer test-receiver-token-4d5e6f' "
        "'http://127.0.0.1:8069/telnyx/webhooks/recent?limit=5' | grep -q '\"entries\"'"
    )

    def post_event(event_type, payload):
        body = json.dumps({"data": {"event_type": event_type, "payload": payload}})
        return machine.succeed(
            "curl -sf -X POST -H 'Content-Type: application/json' --data-binary '"
            + body
            + "' http://127.0.0.1:8069/telnyx/webhooks"
        )

    def post_event_code(event_type, payload):
        body = json.dumps({"data": {"event_type": event_type, "payload": payload}})
        return machine.succeed(
            "curl -s -o /dev/null -w '%{http_code}' -X POST "
            "-H 'Content-Type: application/json' --data-binary '"
            + body
            + "' http://127.0.0.1:8069/telnyx/webhooks"
        ).strip()

    def received_payload(text):
        return {
            "from": {"phone_number": "+15550001111"},
            "to": [{"phone_number": "+15550002222"}],
            "text": text,
        }

    def inbound_rows():
        return machine.succeed(
            "sqlite3 /var/lib/webphone/webphone.db "
            "\"select count(*) from messages where owner='1000' and remote='+15550001111' "
            "and direction='in' and channel='sms'\""
        ).strip()

    # Inbound bridge end to end: the webhook becomes a REAL webphone
    # row (hook-secret check, normalization, insert — production path).
    post_event("message.received", received_payload("hello from the vm test"))
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/webphone.db "
        "\"select count(*) from messages where owner='1000' and remote='+15550001111' "
        "and direction='in' and channel='sms' and body='hello from the vm test'\")\" = 1",
        timeout=30,
    )

    # The retry contract: with webphone down the bridge answers Telnyx
    # 503 and logs the event anyway; the retry (same bytes) lands once
    # webphone is back.
    machine.succeed("systemctl stop webphone.service")
    code = post_event_code(
        "message.received", received_payload("sent while webphone was down")
    )
    if code != "503":
        raise Exception(f"expected 503 while webphone down, got {code}")
    rows = inbound_rows()
    if rows != "1":
        raise Exception(f"failed forward must not create a row, found {rows}")

    machine.succeed("systemctl start webphone.service")
    machine.wait_for_open_port(8080)
    code = post_event_code(
        "message.received", received_payload("sent while webphone was down")
    )
    if code != "200":
        raise Exception(f"expected 200 on the Telnyx retry, got {code}")
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/webphone.db "
        "\"select count(*) from messages where owner='1000' and remote='+15550001111' "
        "and direction='in' and channel='sms'\")\" = 2",
        timeout=30,
    )

    # Status events: a final verdict for a KNOWN provider_ref rides the
    # full production path (bridge → webphone hook → DB update). Seed
    # the outbound row a prior send would have left — the send itself is
    # unit-test-covered (this VM has no Telnyx to answer) — then deliver.
    # NB webphone stores branded ids in their debug-prefixed form
    # ("Message:<nanoid>", "Thread:<nanoid>"): the status UPDATE matches
    # on that stored shape, so the fixture must use it too.
    machine.succeed(
        "sqlite3 /var/lib/webphone/webphone.db \""
        "insert into threads (id, owner, remote, last_activity_at) values "
        "('Thread:thrvM3SABMVKYDQ6MS332', '1000', '+15550002222', strftime('%s','now'));"
        "insert into messages (id, thread_id, owner, remote, direction, channel, "
        "body, status, provider_ref, created_at) values "
        "('Message:msgV1StGXR8Z5jdHi6Bmy', 'Thread:thrvM3SABMVKYDQ6MS332', '1000', "
        "'+15550002222', 'out', 'sms', 'vm outbound probe', 'sent', 'msg-vm-test-ref', "
        "strftime('%s','now'));\""
    )
    seeded = machine.succeed(
        "sqlite3 /var/lib/webphone/webphone.db "
        "\"select count(*) || '/' || direction || '/' || provider_ref from messages "
        "where provider_ref='msg-vm-test-ref'\""
    ).strip()
    if seeded != "1/out/msg-vm-test-ref":
        raise Exception(f"seed probe: {seeded!r}")
    post_event(
        "message.finalized",
        {
            "id": "msg-vm-test-ref",
            "to": [{"phone_number": "+15550002222", "status": "delivered"}],
        },
    )
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/webphone.db "
        "\"select status from messages where provider_ref='msg-vm-test-ref'\")\" = delivered",
        timeout=30,
    )

    # An intermediate status is log-only: 200, no forward, row untouched.
    code = post_event_code(
        "message.finalized",
        {
            "id": "msg-vm-test-ref",
            "to": [{"phone_number": "+15550002222", "status": "sending"}],
        },
    )
    if code != "200":
        raise Exception(f"expected 200 for an intermediate status, got {code}")
    status = machine.succeed(
        "sqlite3 /var/lib/webphone/webphone.db "
        "\"select status from messages where provider_ref='msg-vm-test-ref'\""
    ).strip()
    if status != "delivered":
        raise Exception(f"intermediate status moved the row: {status}")

    # A final verdict for an UNKNOWN ref is refused 503 (Telnyx retries)
    # and logged — the bridge never silently drops a final verdict.
    code = post_event_code(
        "message.finalized",
        {
            "id": "msg-vm-unknown",
            "to": [{"phone_number": "+15550002222", "status": "delivered"}],
        },
    )
    if code != "503":
        raise Exception(f"expected 503 for an unknown-ref final verdict, got {code}")

    # --- WhatsApp arms against the in-VM stub Telnyx -----------------
    # The stub proves the REAL outbound wiring (unit → bridge → HTTP),
    # closing the "no Telnyx in this VM" gap the SMS send lane still
    # leaves to the unit tests.
    machine.succeed(
        "nohup python3 /etc/telnyx_stub.py --port 4545 "
        "--log /tmp/telnyx-stub.jsonl >/tmp/telnyx-stub.out 2>&1 &"
    )
    machine.wait_for_open_port(4545)
    machine.succeed("curl -sf http://127.0.0.1:4545/healthz | grep -q 'true'")

    # The whatsapp lane is live: /gateway/health reports the from-number.
    machine.succeed(
        "curl -sf http://127.0.0.1:8069/gateway/health "
        "| grep -q '\"whatsapp_from\": \"+15550003333\"'"
    )

    # Outbound WhatsApp: the gateway posts the whatsapp:-prefixed send,
    # the stub answers with a provider ref, and the logged request must
    # carry the spec-shaped whatsapp_message object.
    gateway_auth = "-H 'Authorization: Bearer test-gw-secret-4d5e6f'"
    out = machine.succeed(
        "curl -sf " + gateway_auth + " "
        "-F 'to=whatsapp:+15550002222' -F 'body=hello from the wa vm arm' "
        "http://127.0.0.1:8069/gateway/message"
    )
    assert '"provider_ref": "stub-' in out, out
    machine.wait_until_succeeds(
        "grep -q '/messages/whatsapp' /tmp/telnyx-stub.jsonl"
    )
    stub_rows = machine.succeed("cat /tmp/telnyx-stub.jsonl")
    assert "hello from the wa vm arm" in stub_rows, stub_rows
    assert '"type": "text"' in stub_rows, stub_rows

    # Window refusal surfaces as guidance, not a bare 502: the stub's
    # 40008 answer must reach the caller with the 24-hour explanation.
    _, http_code = machine.execute(
        "curl -s -o /tmp/wa-window.json -w '%{http_code}' " + gateway_auth + " "
        "-F 'to=whatsapp:+15550002222' -F 'body=WINDOW_CLOSED probe' "
        "http://127.0.0.1:8069/gateway/message"
    )
    window_body = machine.succeed("cat /tmp/wa-window.json")
    assert http_code.strip() == "502", f"expected 502, got {http_code}: {window_body}"
    assert "24 hours" in window_body and "template" in window_body, window_body

    # Inbound WhatsApp: the Meta-style body shape forwards tagged — the
    # webphone row must key the SAME thread both directions
    # (whatsapp+<number>).
    post_event(
        "message.received",
        {
            "id": "wa-vm-1",
            "type": "WHATSAPP",
            "from": "+15550004444",
            "to": "+15550003333",
            "body": {"type": "text", "text": {"body": "wa inbound vm arm"}},
        },
    )
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/webphone.db "
        "\"select count(*) from messages where owner='1000' "
        "and remote='whatsapp+15550004444' and direction='in' "
        "and body='wa inbound vm arm'\")\" = 1",
        timeout=30,
    )

    # Status verdict on the WhatsApp/Meta envelope (to as a STRING, the
    # verdicts in statuses) must ride the FULL production path: seed the
    # outbound row the stub-ref send would own, deliver, assert the DB.
    machine.succeed(
        "sqlite3 /var/lib/webphone/webphone.db \""
        "insert into threads (id, owner, remote, last_activity_at) values "
        "('Thread:thrwa0000000000000001', '1000', 'whatsapp+15550002222', strftime('%s','now'));"
        "insert into messages (id, thread_id, owner, remote, direction, channel, "
        "body, status, provider_ref, created_at) values "
        "('Message:msgwa0000000000000001', 'Thread:thrwa0000000000000001', '1000', "
        "'whatsapp+15550002222', 'out', 'whatsapp', 'wa outbound probe', 'sent', "
        "'stub-wa-ref-1', strftime('%s','now'));\""
    )
    out = post_event(
        "message.finalized",
        {
            "id": "stub-wa-ref-1",
            "type": "WHATSAPP",
            "to": "+15550002222",
            "statuses": [{"status": "delivered"}],
        },
    )
    assert '"forwarded": true' in out, out
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/webphone.db "
        "\"select status from messages where provider_ref='stub-wa-ref-1'\")\" = delivered",
        timeout=30,
    )

    # Every event above went through the receiver: the JSONL holds them.
    entries = int(
        machine.succeed("wc -l < /var/lib/telnyx-webhooks/inbound.jsonl").strip()
    )
    if entries < 7:
        raise Exception(f"receiver log holds {entries} entries, expected >= 7")
  '';
}
