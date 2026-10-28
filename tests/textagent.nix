# NixOS VM test for the supervised text-message agent (modules/telephony/
# textagent.nix + text-agent.py): the REAL three-service wiring end to
# end — receiver logs a synthetic Telnyx webhook into inbound.jsonl, the
# textagent's tailer reads it THROUGH the ro-bind + telephony-fs ACL
# path (the production data route, not a test shortcut), drafts via the
# loopback Gemini text stub (tests/textagent_gemini_stub.py), and the
# human approve in the review API rides the REAL outbound gateway into
# the stub Telnyx (tests/telnyx_stub.py). Also asserts the bearer gate,
# the STOP suppression gate, and honest /health.
{
  telephonyModule,
  webphonePackage,
  kvm ? true,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = if kvm then "telephony-textagent" else "telephony-textagent-tcg";

  requiredFeatures.kvm = kvm;

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;

      environment.etc."bridge-secrets/webphone_gateway_secret".text = "test-gw-secret-4d5e6f\n";
      environment.etc."bridge-secrets/telnyx_api_key".text = "KEYtest-not-real\n";
      environment.etc."bridge-secrets/telephony_webhook_token".text = "test-receiver-token-4d5e6f\n";
      environment.etc."telnyx_stub.py".source = ./telnyx_stub.py;
      environment.etc."textagent_gemini_stub.py".source = ./textagent_gemini_stub.py;

      systemd.services.telnyx-webhooks.environment.TELNYX_API_BASE = "http://127.0.0.1:4545/v2";

      systemd.services.vm-telnyx-stub = {
        description = "Loopback stub Telnyx API for the textagent VM test";
        wantedBy = [ "multi-user.target" ];
        before = [ "telnyx-webhooks.service" ];
        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.python3}/bin/python3 /etc/telnyx_stub.py --port 4545 --log /tmp/telnyx-stub.jsonl";
          Restart = "on-failure";
        };
      };

      systemd.services.vm-textagent-stub = {
        description = "Loopback stub Gemini text API for the textagent VM test";
        wantedBy = [ "multi-user.target" ];
        before = [ "telephony-textagent.service" ];
        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.python3}/bin/python3 /etc/textagent_gemini_stub.py 8444 --log /tmp/textagent-gemini-stub.jsonl";
          Restart = "on-failure";
        };
      };

      # Credential seeds: every LoadCredential source must exist before
      # the units start (a missing source fails the unit 243/CREDENTIALS).
      systemd.services.vm-textagent-secrets = {
        description = "Seed textagent credential files (VM test)";
        wantedBy = [ "multi-user.target" ];
        before = [
          "telephony-textagent.service"
          # webphone opens the shared secret at config load (the
          # gateway-secret class): seed before it ever starts.
          "webphone.service"
        ];
        serviceConfig.Type = "oneshot";
        script = ''
          install -Dm600 /dev/null /run/telephony-test/gemini-key
          printf '%s' 'vm-test-key-not-a-placehol' > /run/telephony-test/gemini-key
          install -Dm600 /dev/null /run/telephony-test/textagent-prompt
          printf '%s' 'You draft replies for the VM test.' > /run/telephony-test/textagent-prompt
          # The shared secret has TWO consumers: the review API (via
          # LoadCredential, root-sourced) and webphone as its own user.
          # 0640 root:webphone is the production heal-unit shape; a
          # root-only file makes webphone exit 1 at config load.
          install -D -m 0640 -o root -g webphone /dev/null /run/telephony-test/textagent-secret
          printf '%s' 'test-review-secret-4d5e6f' > /run/telephony-test/textagent-secret
        '';
      };

      services.telephony.messaging = {
        enable = true;
        ownerExtension = "1000";
        did = "+15550001111";
        gatewaySecretFile = "/etc/bridge-secrets/webphone_gateway_secret";
        telnyxApiKeyFile = "/etc/bridge-secrets/telnyx_api_key";
        webhookTokenFile = "/etc/bridge-secrets/telephony_webhook_token";
      };

      services.telephony.textagent = {
        enable = true;
        apiKeyFile = "/run/telephony-test/gemini-key";
        systemPromptFile = "/run/telephony-test/textagent-prompt";
        sharedSecretFile = "/run/telephony-test/textagent-secret";
        geminiApiBase = "http://127.0.0.1:8444";
      };
    };

  testScript = ''
    ${common.bootWait}

    machine.wait_for_unit("webphone.service")
    # The bridge forwards inbound messages into webphone's /hooks/message:
    # the HTTP listener binds only AFTER the read-model boot work, so a
    # unit-wait alone races the first webhook POST into a 503 (seen once
    # under a loaded full `nix flake check`; the messaging suite already
    # waits for the port for the same reason).
    machine.wait_for_open_port(8080)
    machine.wait_for_unit("telnyx-webhooks.service")
    machine.wait_for_open_port(8069)
    machine.wait_for_unit("telephony-textagent.service")
    machine.wait_for_open_port(8072)

    import json

    reviews = "curl -sf -H 'Authorization: Bearer test-review-secret-4d5e6f' http://127.0.0.1:8072/reviews"

    # Honest health: key configured, loopback presence, drafts mode.
    machine.succeed(
        "curl -sf http://127.0.0.1:8072/health | grep -q '\"api_key_configured\": true'"
    )
    machine.succeed(
        "curl -sf http://127.0.0.1:8072/health | grep -q '\"gateway_secret_configured\": true'"
    )

    # The bearer gate: /reviews is closed without the shared secret.
    machine.fail("curl -sf http://127.0.0.1:8072/reviews")

    def post_event(event_type, payload):
        body = json.dumps({"data": {"event_type": event_type, "payload": payload}})
        return machine.succeed(
            "curl -sf -X POST -H 'Content-Type: application/json' --data-binary '"
            + body
            + "' http://127.0.0.1:8069/telnyx/webhooks"
        )

    # The keystone loop end to end: receiver -> inbound.jsonl -> tailer
    # (through the ro bind + ACL path) -> Gemini stub draft -> review
    # list. The receiver writes the FULL envelope; the tailer normalizes.
    post_event("message.received", {
        "id": "msg-vm-1",
        "from": {"phone_number": "+15550002222"},
        "to": [{"phone_number": "+15550001111"}],
        "text": "Wann kommt der Techniker?",
    })
    machine.wait_until_succeeds(
        "curl -sf -H 'Authorization: Bearer test-review-secret-4d5e6f' "
        "http://127.0.0.1:8072/reviews | grep -q 'VM-Test-Antwort'",
        timeout=60,
    )

    # The draft carries the bilingual story: German reply + EN gloss +
    # language + confidence, and the prompt asked in the stub really
    # saw the conversation history.
    listing = json.loads(machine.succeed(reviews))
    assert len(listing["drafts"]) == 1, listing
    draft = listing["drafts"][0]
    assert draft["contact"] == "15550002222", draft
    assert draft["language"] == "de", draft
    assert draft["confidence"] == 93, draft
    assert draft["en_gloss"].startswith("Good morning"), draft
    stub_prompt = json.loads(
        machine.succeed("tail -n 1 /tmp/textagent-gemini-stub.jsonl")
    )
    assert "Wann kommt der Techniker?" in stub_prompt["prompt"], stub_prompt

    # Approve: the review API rides the REAL outbound gateway into the
    # stub Telnyx — provider_ref comes back, the stub saw the text.
    approved = json.loads(machine.succeed(
        "curl -sf -X POST -H 'Authorization: Bearer test-review-secret-4d5e6f' "
        "-H 'Content-Type: application/json' --data '{}' "
        "http://127.0.0.1:8072/reviews/" + draft["id"] + "/approve"
    ))
    assert approved["status"] == "sent", approved
    assert approved["sent_by"] == "human", approved
    assert approved["provider_ref"].startswith("stub-"), approved
    sent = json.loads(machine.succeed("tail -n 1 /tmp/telnyx-stub.jsonl"))
    assert "VM-Test-Antwort" in json.dumps(sent), sent

    # Conversation state landed under the service's own state dir.
    machine.succeed(
        "test -f /var/lib/telephony-textagent/conversations/15550002222.json"
    )

    # The suppression gate: a STOP inbound suppresses the contact, no
    # draft appears, and the reset surface clears it again.
    post_event("message.received", {
        "id": "msg-vm-2",
        "from": {"phone_number": "+15550002222"},
        "to": [{"phone_number": "+15550001111"}],
        "text": "STOP",
    })
    machine.wait_until_succeeds(
        "curl -sf -H 'Authorization: Bearer test-review-secret-4d5e6f' "
        "http://127.0.0.1:8072/suppression | grep -q 15550002222",
        timeout=60,
    )
    listing = json.loads(machine.succeed(reviews))
    assert len(listing["drafts"]) == 0, listing
    machine.succeed(
        "curl -sf -X POST -H 'Authorization: Bearer test-review-secret-4d5e6f' "
        "http://127.0.0.1:8072/suppression/15550002222/reset | grep -q '\"reset\": true'"
    )

    # On-demand draft from the compose surface (the webphone button's
    # backend call), then discard keeps it out of the list.
    ondemand = json.loads(machine.succeed(
        "curl -sf -X POST -H 'Authorization: Bearer test-review-secret-4d5e6f' "
        "-H 'Content-Type: application/json' "
        "--data '{\"to\": \"+15550002222\"}' http://127.0.0.1:8072/draft"
    ))
    assert ondemand["status"] == "pending", ondemand
    machine.succeed(
        "curl -sf -X POST -H 'Authorization: Bearer test-review-secret-4d5e6f' "
        "http://127.0.0.1:8072/reviews/" + ondemand["id"] + "/discard"
    )
    listing = json.loads(machine.succeed(reviews))
    assert len(listing["drafts"]) == 0, listing
  '';
}
