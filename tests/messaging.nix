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
      # The media-download arm curls the PUBLIC hostname shape (the URL
      # Telnyx fetches); map it like the passkey suite does.
      networking.extraHosts = "127.0.0.1 pbx.test";
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
    ${common.helpers}

    # Only the web half matters here: no sofia wait, no calls — the
    # bridge is an HTTP producer and webphone is the consumer.
    wait_webphone(machine${bootTimeouts})
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
            "sqlite3 /var/lib/webphone/system.db "
            "\"select count(*) from meta_planned_thread_messages where json_extract(value,'$.owner')='1000' "
            "and json_extract(value,'$.remote')='+15550001111' "
            "and json_extract(value,'$.direction')='in' and json_extract(value,'$.channel')='sms'\""
        ).strip()

    # Inbound bridge end to end: the webhook becomes a REAL webphone
    # row (hook-secret check, normalization, insert — production path).
    # Since webphone's SUPERB unification the truth is the journal:
    # messages land as facts and read back from system.db's
    # meta_planned_thread_messages projection (the legacy webphone.db
    # messages table stays frozen-empty by design).
    post_event("message.received", received_payload("hello from the vm test"))
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/system.db "
        "\"select count(*) from meta_planned_thread_messages where json_extract(value,'$.owner')='1000' "
        "and json_extract(value,'$.remote')='+15550001111' "
        "and json_extract(value,'$.direction')='in' and json_extract(value,'$.channel')='sms' "
        "and json_extract(value,'$.body')='hello from the vm test'\")\" = 1",
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
        "test \"$(sqlite3 /var/lib/webphone/system.db "
        "\"select count(*) from meta_planned_thread_messages where json_extract(value,'$.owner')='1000' "
        "and json_extract(value,'$.remote')='+15550001111' "
        "and json_extract(value,'$.direction')='in' and json_extract(value,'$.channel')='sms'\")\" = 2",
        timeout=30,
    )

    # Status events: a final verdict for a KNOWN provider_ref rides the
    # full production path (webphone send → bridge → stub Telnyx →
    # receipt → journal → projection). The outbound row comes from a
    # REAL send through webphone's own /messages lane — the seed-by-SQL
    # era ended with the journal (webphone.db's tables are frozen import
    # sources, inserts there never reach the truth), and posting to the
    # BRIDGE's /gateway/message directly bypasses webphone entirely
    # (that lane is webphone's provider target, not a webphone surface).
    # The stub must be up before the send (webphone forwards at send
    # time); the WhatsApp arms below reuse it.
    machine.succeed(
        "nohup python3 /etc/telnyx_stub.py --port 4545 "
        "--log /tmp/telnyx-stub.jsonl >/tmp/telnyx-stub.out 2>&1 &"
    )
    machine.wait_for_open_port(4545)
    machine.succeed("curl -sf http://127.0.0.1:4545/healthz | grep -q 'true'")
    gateway_auth = "-H 'Authorization: Bearer test-gw-secret-4d5e6f'"

    def webphone_send(body):
        # Session + CSRF + POST /messages/send: webphone's real send
        # lane (this VM boots without phone_api_url, so directory verify
        # is disabled — any password mints the session; the WARN is the
        # documented fail-open). Login ROTATES the CSRF token, so the
        # send re-fetches /api/csrf on the session jar first (the same
        # adoption the island does).
        machine.succeed(
            "curl -sf -c /tmp/wp-jar http://127.0.0.1:8080/api/csrf"
            " > /tmp/wp-csrf.json"
        )
        wp_csrf = machine.succeed(
            "grep -o '\"token\":\"[^\"]*\"' /tmp/wp-csrf.json | cut -d'\"' -f4"
        ).strip()
        _, login_code = machine.execute(
            "curl -s -o /tmp/wp-login.json -w '%{http_code}' "
            "-c /tmp/wp-jar -b /tmp/wp-jar "
            "-H 'X-CSRF-Token: " + wp_csrf + "' "
            "-H 'Content-Type: application/json' "
            "-d '{\"extension\":\"1000\",\"password\":\"vm-test\"}' "
            "http://127.0.0.1:8080/api/session"
        )
        if login_code.strip() not in ("200", "201"):
            raise Exception(f"webphone login failed: {login_code}")
        wp_csrf = machine.succeed(
            "curl -sf -b /tmp/wp-jar -c /tmp/wp-jar "
            "http://127.0.0.1:8080/api/csrf"
            " | grep -o '\"token\":\"[^\"]*\"' | cut -d'\"' -f4"
        ).strip()
        _, send_code = machine.execute(
            "curl -s -o /tmp/wp-send.out -w '%{http_code}' "
            "-b /tmp/wp-jar -H 'X-CSRF-Token: " + wp_csrf + "' "
            "-F 'to=+15550002222' -F 'body=" + body + "' "
            "http://127.0.0.1:8080/messages/send"
        )
        if send_code.strip() not in ("200", "204"):
            raise Exception(f"webphone send failed: {send_code}")

    def outbound_ref(body):
        # The provider ref lands on the row via the bridge's receipt;
        # read it back from the projection (the one home for sent rows).
        return machine.succeed(
            "sqlite3 /var/lib/webphone/system.db "
            "\"select json_extract(value,'$.provider_ref') from meta_planned_thread_messages "
            "where json_extract(value,'$.direction')='out' "
            "and json_extract(value,'$.body')='" + body + "'\""
        ).strip()

    webphone_send("vm outbound probe")
    machine.wait_until_succeeds(
        "test -n \"$(sqlite3 /var/lib/webphone/system.db "
        "\"select json_extract(value,'$.provider_ref') from meta_planned_thread_messages where "
        "json_extract(value,'$.direction')='out' and "
        "json_extract(value,'$.body')='vm outbound probe'\")\"",
        timeout=30,
    )
    sms_ref = outbound_ref("vm outbound probe")
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/system.db "
        "\"select count(*) from meta_planned_thread_messages where "
        "json_extract(value,'$.provider_ref')='" + sms_ref + "'\")\" = 1",
        timeout=30,
    )
    post_event(
        "message.finalized",
        {
            "id": sms_ref,
            "to": [{"phone_number": "+15550002222", "status": "delivered"}],
        },
    )
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/system.db "
        "\"select json_extract(value,'$.status') from meta_planned_thread_messages where "
        "json_extract(value,'$.provider_ref')='" + sms_ref + "'\")\" = delivered",
        timeout=30,
    )

    # An intermediate status is log-only: 200, no forward, row untouched.
    code = post_event_code(
        "message.finalized",
        {
            "id": sms_ref,
            "to": [{"phone_number": "+15550002222", "status": "sending"}],
        },
    )
    if code != "200":
        raise Exception(f"expected 200 for an intermediate status, got {code}")
    status = machine.succeed(
        "sqlite3 /var/lib/webphone/system.db "
        "\"select json_extract(value,'$.status') from meta_planned_thread_messages where "
        "json_extract(value,'$.provider_ref')='" + sms_ref + "'\""
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
    # closing the "no Telnyx in this VM" gap the SMS send lane left to
    # the unit tests (before this rewrite started it above).
    #
    # The whatsapp lane is live: /gateway/health reports the from-number.
    machine.succeed(
        "curl -sf http://127.0.0.1:8069/gateway/health "
        "| grep -q '\"whatsapp_from\": \"+15550003333\"'"
    )

    # Outbound WhatsApp: the gateway posts the whatsapp:-prefixed send,
    # the stub answers with a provider ref, and the logged request must
    # carry the spec-shaped whatsapp_message object.
    out = machine.succeed(
        "curl -sf " + gateway_auth + " "
        "-F 'to=whatsapp:+15550002222' -F 'body=hello from the wa vm arm' "
        "http://127.0.0.1:8069/gateway/message"
    )
    assert '"provider_ref": "stub-' in out, out
    # The WA status arm's ref comes from a REAL webphone send too (the
    # bridge-lane send above proves the whatsapp forwarding lane; the
    # verdict arm needs a row the send owns).
    webphone_send("wa outbound probe")
    machine.wait_until_succeeds(
        "test -n \"$(sqlite3 /var/lib/webphone/system.db "
        "\"select json_extract(value,'$.provider_ref') from meta_planned_thread_messages where "
        "json_extract(value,'$.direction')='out' and "
        "json_extract(value,'$.body')='wa outbound probe'\")\"",
        timeout=30,
    )
    wa_ref = outbound_ref("wa outbound probe")
    machine.wait_until_succeeds(
        "grep -q '/messages/whatsapp' /tmp/telnyx-stub.jsonl"
    )
    stub_rows = machine.succeed("cat /tmp/telnyx-stub.jsonl")
    assert "hello from the wa vm arm" in stub_rows, stub_rows
    assert '"type": "text"' in stub_rows, stub_rows

    # Window refusal surfaces as guidance, not a bare 502: the stub's
    # 40008 answer must reach the caller with the HUMANIZED guidance
    # sentence whatsapp_rejection_guidance appends — the wording pin
    # keeps a guidance regression (a bare code or a generic 502 wall)
    # from passing as green.
    _, http_code = machine.execute(
        "curl -s -o /tmp/wa-window.json -w '%{http_code}' " + gateway_auth + " "
        "-F 'to=whatsapp:+15550002222' -F 'body=WINDOW_CLOSED probe' "
        "http://127.0.0.1:8069/gateway/message"
    )
    window_body = machine.succeed("cat /tmp/wa-window.json")
    assert http_code.strip() == "502", f"expected 502, got {http_code}: {window_body}"
    assert (
        "only accepts free-form replies within 24 hours" in window_body
        and "pre-approved template (managed in the Telnyx portal" in window_body
    ), window_body

    # Outbound MMS media: the gateway stages the attachment, hands
    # Telnyx a PUBLIC_BASE_URL/mms-media URL in media_urls, and the
    # REAL nginx -> bridge download path serves the exact bytes back.
    # One lane proves all three: stage (send), wire shape (stub row),
    # download (curl through the vhost).
    machine.succeed(
        "python3 -c \"open('/tmp/mms-payload.png','wb').write("
        "b'\\x89PNG\\r\\n\\x1a\\n' + b'0' * 64)\""
    )
    _, media_code = machine.execute(
        "curl -s -o /tmp/mms-send.json -w '%{http_code}' " + gateway_auth + " "
        "-F 'to=+15550001111' -F 'body=mms media probe' "
        "-F 'media=@/tmp/mms-payload.png;type=image/png' "
        "http://127.0.0.1:8069/gateway/message"
    )
    media_body = machine.succeed("cat /tmp/mms-send.json")
    assert media_code.strip() == "200", f"mms send got {media_code}: {media_body}"
    stub_rows = machine.succeed("cat /tmp/telnyx-stub.jsonl")
    assert '"media_urls"' in stub_rows and "https://pbx.test/mms-media/" in stub_rows, (
        stub_rows
    )
    media_path = machine.succeed(
        "grep -o 'https://pbx.test/mms-media/[^\"]*' /tmp/telnyx-stub.jsonl"
        " | head -1 | cut -d/ -f4-"
    ).strip()
    assert media_path.startswith("mms-media/"), media_path
    # The download rides the REAL vhost wire: nginx must be listening
    # first (the house wait shape — the passkey/webphone suites both
    # wait the unit and the port before any https curl).
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)
    machine.succeed(
        "curl -k -sf https://pbx.test/" + media_path + " | cmp - /tmp/mms-payload.png"
    )
    print("MMS-MEDIA-ROUNDTRIP-DONE")

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
        "test \"$(sqlite3 /var/lib/webphone/system.db "
        "\"select count(*) from meta_planned_thread_messages where json_extract(value,'$.owner')='1000' "
        "and json_extract(value,'$.remote')='whatsapp+15550004444' and json_extract(value,'$.direction')='in' "
        "and json_extract(value,'$.body')='wa inbound vm arm'\")\" = 1",
        timeout=30,
    )

    # Status verdict on the WhatsApp/Meta envelope (to as a STRING, the
    # verdicts in statuses) must ride the FULL production path: the
    # outbound row is the wa send's own (wa_ref above — a REAL row from
    # the stub-ref send, not a seed), deliver, assert the projection.
    # channel carries the message FORMAT (sms|mms — webphone's domain);
    # the whatsapp transport lives in the whatsapp+<number> remote key
    # and the bridge envelope.
    out = post_event(
        "message.finalized",
        {
            "id": wa_ref,
            "type": "WHATSAPP",
            "to": "+15550002222",
            "statuses": [{"status": "delivered"}],
        },
    )
    assert '"forwarded": true' in out, out
    machine.wait_until_succeeds(
        "test \"$(sqlite3 /var/lib/webphone/system.db "
        "\"select json_extract(value,'$.status') from meta_planned_thread_messages where "
        "json_extract(value,'$.provider_ref')='" + wa_ref + "'\")\" = delivered",
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
