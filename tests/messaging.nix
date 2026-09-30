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
      environment.etc."bridge-secrets/webphone_gateway_secret".text =
        "test-gw-secret-4d5e6f\n";
      environment.etc."bridge-secrets/telnyx_api_key".text = "KEYtest-not-real\n";
      environment.etc."bridge-secrets/telephony_webhook_token".text =
        "test-receiver-token-4d5e6f\n";
      services.telephony.messaging = {
        enable = true;
        ownerExtension = "1000";
        # baseNode configures no gateway, so the sole-gateway default
        # has nothing to derive from — name the DID explicitly.
        did = "+15550001111";
        gatewaySecretFile = "/etc/bridge-secrets/webphone_gateway_secret";
        telnyxApiKeyFile = "/etc/bridge-secrets/telnyx_api_key";
        webhookTokenFile = "/etc/bridge-secrets/telephony_webhook_token";
      };
      # The same secret on the consumer side: webphone's /hooks gate
      # compares against it, so a mismatch would fail at the 401 and
      # the bridge would 503 — asserted implicitly by the row landing.
      services.webphone.settings.gateway.webhook_secret = "test-gw-secret-4d5e6f";
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
    machine.succeed(
        "sqlite3 /var/lib/webphone/webphone.db \""
        "insert into threads (id, owner, remote, last_activity_at) values "
        "('thrvM3SABMVKYDQ6MS332', '1000', '+15550002222', strftime('%s','now'));"
        "insert into messages (id, thread_id, owner, remote, direction, channel, "
        "body, status, provider_ref, created_at) values "
        "('msgV1StGXR8Z5jdHi6Bmy', 'thrvM3SABMVKYDQ6MS332', '1000', '+15550002222', 'out', 'sms', "
        "'vm outbound probe', 'sent', 'msg-vm-test-ref', strftime('%s','now'));\""
    )
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

    # Every event above went through the receiver: the JSONL holds them.
    entries = int(
        machine.succeed("wc -l < /var/lib/telnyx-webhooks/inbound.jsonl").strip()
    )
    if entries < 4:
        raise Exception(f"receiver log holds {entries} entries, expected >= 4")
  '';
}
