# NixOS VM test for the Telnyx webhook signature gate
# (modules/telephony/messaging.nix + telnyx-webhooks.py): with
# messaging.webhookPublicKeyFile set, systemd mounts the public key as
# the unit's fourth credential, the bridge reports
# "webhook_signature": "required", an unsigned delivery answers 403 on
# loopback and through the nginx edge and leaves no line in
# inbound.jsonl, a signed one passes through the edge with its two
# headers intact, a body changed after signing is refused, and the edge
# overwrites a client-sent X-Real-IP while the direct loopback path
# honours it.
#
# The signer (tests/sign_webhook.py) builds the signature the way
# Telnyx documents it, on the curve arithmetic of the bridge module
# under test with an independent point encoder; the unit tests
# (tests/test_telnyx_bridge.py) pin that arithmetic to the RFC 8032
# vectors. The key pair is the VM's own, fictional and used nowhere
# else.
{
  telephonyModule,
  webphonePackage,
  kvm ? true,
  slowBoot ? false,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  bootTimeouts = if slowBoot then ", port_timeout=900, unit_timeout=900" else "";

  # The VM's Ed25519 key pair: the seed (private) hex and the public
  # key in the base64 spelling the Telnyx portal shows.
  seed = "83faafe6cd783e2a6c7ec39800a313590529c2325fe59704bd094f7ffb3a9d10";
  publicKey = "IUKuesXb7CyMGC7lA9YCjw5+ekikfe14OFHp7196gW4=";
in
{
  name = if kvm then "telephony-messaging-signature" else "telephony-messaging-signature-tcg";

  requiredFeatures.kvm = kvm;

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;
      environment.systemPackages = [ pkgs.python3 ];
      # The edge leg curls the public hostname shape; map it like the
      # messaging suite does.
      networking.extraHosts = "127.0.0.1 pbx.test";
      environment.etc."bridge-secrets/webphone_gateway_secret".text = "test-gw-secret-4d5e6f\n";
      environment.etc."bridge-secrets/telnyx_api_key".text = "KEYtest-not-real\n";
      environment.etc."bridge-secrets/telephony_webhook_token".text = "test-receiver-token-4d5e6f\n";
      environment.etc."bridge-secrets/telnyx_public_key".text = publicKey + "\n";
      # The bridge module and the signer, at fixed paths for the driver.
      # The module copy is the same store file the unit runs.
      environment.etc."telnyx-webhooks.py".source = ../modules/telephony/telnyx-webhooks.py;
      environment.etc."sign_webhook.py".source = ./sign_webhook.py;
      services.telephony.messaging = {
        enable = true;
        ownerExtension = "1000";
        did = "+15550001111";
        gatewaySecretFile = "/etc/bridge-secrets/webphone_gateway_secret";
        telnyxApiKeyFile = "/etc/bridge-secrets/telnyx_api_key";
        webhookTokenFile = "/etc/bridge-secrets/telephony_webhook_token";
        webhookPublicKeyFile = "/etc/bridge-secrets/telnyx_public_key";
      };
    };

  testScript = ''
    ${common.bootWait}
    ${common.helpers}

    # Only the web half matters here: no sofia wait, no calls.
    wait_webphone(machine${bootTimeouts})
    machine.wait_for_unit("telnyx-webhooks.service")
    machine.wait_for_open_port(8069)

    import json

    bridge = "http://127.0.0.1:8069"
    edge = "https://pbx.test"
    token = "Authorization: Bearer test-receiver-token-4d5e6f"

    def signed(url, *headers, tamper=False):
        prefix = "SIGN_WEBHOOK_TAMPER=1 " if tamper else ""
        quoted = " ".join(f"'{header}'" for header in headers)
        out = machine.succeed(
            f"{prefix}python3 /etc/sign_webhook.py /etc/telnyx-webhooks.py ${seed} '{url}/telnyx/webhooks' {quoted}"
        )
        return out.strip().splitlines()[-1]

    def unsigned(url, *headers):
        event = {"id": "vm-unsigned", "event_type": "message.sent", "payload": {"id": "vm-out-1"}}
        body = json.dumps({"data": event})
        quoted = " ".join(f"-H '{header}'" for header in headers)
        return machine.succeed(
            "curl -sk -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json'"
            f" --data-binary '{body}' {quoted} '{url}/telnyx/webhooks'"
        ).strip()

    def remotes():
        rows = machine.succeed(f"curl -sf -H '{token}' '{bridge}/telnyx/webhooks/recent?limit=20'")
        return [entry["remote"] for entry in json.loads(rows)["entries"]]

    # systemd wiring: the public key is mounted as the unit's fourth
    # credential, holding exactly the configured key.
    mounted = "/run/credentials/telnyx-webhooks.service/telnyx_public_key"
    machine.succeed(f"test -s '{mounted}' && grep -qF '${publicKey}' '{mounted}'")

    # The bridge reports the gate as on.
    health = machine.succeed(f"curl -sf '{bridge}/gateway/health'")
    assert '"webhook_signature": "required"' in health, health

    # Unsigned deliveries: 403 on loopback and through the edge, and
    # nothing in the event log.
    assert unsigned(bridge) == "403", "an unsigned loopback delivery must be 403"
    assert unsigned(edge) == "403", "an unsigned edge delivery must be 403"
    assert remotes() == [], f"unsigned deliveries were logged: {remotes()}"

    # Signed deliveries: 200 on both paths (the two headers survive the
    # edge), each logged once.
    assert signed(bridge).startswith("STATUS 200"), signed(bridge)
    assert signed(edge).startswith("STATUS 200"), signed(edge)
    assert remotes() == ["127.0.0.1", "127.0.0.1"], remotes()

    # A body changed after signing is refused on both paths and never
    # logged.
    assert signed(bridge, tamper=True).startswith("STATUS 403"), signed(bridge, tamper=True)
    assert signed(edge, tamper=True).startswith("STATUS 403"), signed(edge, tamper=True)
    assert len(remotes()) == 2, remotes()

    # The public client address: on the direct loopback path the bridge
    # honours a valid X-Real-IP (there is no edge to overwrite it);
    # through the edge nginx replaces the client's header with the
    # address it saw.
    assert signed(bridge, "X-Real-IP: 203.0.113.9").startswith("STATUS 200")
    assert remotes()[-1] == "203.0.113.9", remotes()
    assert signed(edge, "X-Real-IP: 203.0.113.9").startswith("STATUS 200")
    assert remotes()[-1] == "127.0.0.1", remotes()
  '';
}
