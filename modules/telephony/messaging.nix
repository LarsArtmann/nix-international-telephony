# services.telephony.messaging: the Telnyx messaging bridge.
#
# A loopback stdlib-Python service (telnyx-webhooks.py, this directory)
# with three hats on one port:
#
#   1. Receiver: POST /telnyx/webhooks logs every Telnyx messaging event
#      as JSON lines (point operator.smsMessageStore at the JSONL to light
#      the operator SMS tab); GET /telnyx/webhooks/health and the
#      token-gated GET /telnyx/webhooks/recent expose liveness and a
#      no-SSH log reader.
#   2. Inbound bridge: message.received is normalized and forwarded to
#      the webphone POST /hooks/message (MMS media fetched, capped,
#      base64); the final delivery verdicts become POST
#      /hooks/message/status. A forwarding failure answers Telnyx 503 so
#      it retries; the event is logged either way.
#   3. Outbound gateway: webphone's webhook gateway mode (settings.
#      gateway.mode = "webhook") posts multipart to /gateway/message,
#      which rides the Telnyx Messages API. Attachments are MMS: staged
#      under /mms-media/<token> (unguessable token + TLS is the access
#      control; nginx on this vhost serves them to Telnyx at send time)
#      and sent as Telnyx media_urls.
#
#      WhatsApp lane (messaging.whatsapp.enable): destinations typed as
#      whatsapp:+<E164> ride Telnyx's WhatsApp API instead — inbound
#      WhatsApp senders are tagged with the same prefix so webphone
#      threads key identically in both directions. Fails closed (502
#      with setup guidance) until whatsapp.did names a number that
#      completed the portal's embedded signup.
#
# Contracts are pinned by tests/test_telnyx_bridge.py (stdlib unittest).
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };
  port = toString cfg.messaging.port;
  publicBaseUrl =
    if cfg.messaging.publicBaseUrl != "" then cfg.messaging.publicBaseUrl else "https://${cfg.domain}";
in
{
  config = lib.mkMerge [
    {
      warnings = lib.mkIf (cfg.messaging.whatsapp.enable && !cfg.messaging.enable) [
        "services.telephony.messaging.whatsapp.enable is true but messaging.enable is false — the WhatsApp lane is a silent no-op until messaging.enable is true."
      ];
    }
    (lib.mkIf cfg.messaging.enable {
      assertions = [
        {
          assertion = cfg.webphone.enable;
          message = "services.telephony.messaging.enable requires webphone.enable (the bridge exists to serve webphone messaging).";
        }
        {
          assertion = cfg.messaging.did != "";
          message = "services.telephony.messaging.did must be set (defaults to the sole gateway's did only when exactly one gateway is configured).";
        }
        {
          assertion = cfg.messaging.gatewaySecretFile != null;
          message = "services.telephony.messaging.gatewaySecretFile is required when messaging is enabled (webphone hooks fail closed without the secret).";
        }
        {
          assertion = cfg.messaging.telnyxApiKeyFile != null;
          message = "services.telephony.messaging.telnyxApiKeyFile is required when messaging is enabled (a PLACEHOLDER value fails outbound closed by design, but the file must exist or the unit cannot start).";
        }
        {
          assertion = cfg.messaging.webhookTokenFile != null;
          message = "services.telephony.messaging.webhookTokenFile is required when messaging is enabled (the /recent reader is token-gated).";
        }
        {
          assertion = !(cfg.messaging.whatsapp.enable && cfg.messaging.whatsapp.did == null);
          message = "services.telephony.messaging.whatsapp.did must be set when messaging.whatsapp.enable is true (a number that completed Telnyx's WhatsApp embedded signup — portal: Messaging → WhatsApp).";
        }
        {
          # Parity with the app's own exactly-one-of secret-source
          # rejection (config.gateway_secret_sources): the bridge wires
          # webhook_secret_file below, so an inline webhook_secret must
          # fail at EVAL time, not at webphone boot.
          assertion = (config.services.webphone.settings.gateway.webhook_secret or "") == "";
          message = "services.webphone.settings.gateway.webhook_secret: the messaging bridge wires webhook_secret_file from services.telephony.messaging.gatewaySecretFile (one file, one secret — both sides read it). Set that option instead of an inline secret.";
        }
      ];

      # Outbound gateway auto-wire: with the bridge running, webphone's
      # webhook gateway mode needs no operator seam — mode, the loopback
      # URL (the app posts webhook_url + /message and + /fax) and the
      # SHARED secret file (the exact file the bridge authenticates
      # against) all derive from this module. mkDefault keeps explicit
      # operator overrides possible.
      services.webphone.settings.gateway = {
        mode = lib.mkDefault "webhook";
        webhook_url = lib.mkDefault "http://127.0.0.1:${port}/gateway";
        webhook_secret_file = lib.mkDefault cfg.messaging.gatewaySecretFile;
      };

      systemd.services.telnyx-webhooks = {
        description = "Telnyx messaging bridge: webhook receiver, webphone message bridge, outbound gateway";
        after = [
          "network.target"
          "webphone.service"
        ];
        wantedBy = [ "multi-user.target" ];
        # The bridge reads everything secret via $CREDENTIALS_DIR (systemd
        # reads the source files as root at start), so unlike services that
        # read the secrets directory directly it needs no supplementary
        # group. A missing source file fails the unit start — the placeholder
        # convention (file exists, PLACEHOLDER* content) keeps that honest.
        environment = {
          WEBPHONE_URL = cfg.messaging.webphoneUrl;
          SMS_TO_EXTENSION = cfg.messaging.ownerExtension;
          FROM_NUMBER = cfg.messaging.did;
          WHATSAPP_FROM =
            if cfg.messaging.whatsapp.enable && cfg.messaging.whatsapp.did != null then
              cfg.messaging.whatsapp.did
            else
              "";
          PUBLIC_BASE_URL = publicBaseUrl;
          PORT = port;
        };
        serviceConfig = {
          ExecStart = "${pkgs.python3}/bin/python3 ${./telnyx-webhooks.py}";
          StateDirectory = "telnyx-webhooks";
          DynamicUser = true;
          LoadCredential = [
            "webphone_secret:${cfg.messaging.gatewaySecretFile}"
            "telnyx_key:${cfg.messaging.telnyxApiKeyFile}"
            "webhook_token:${cfg.messaging.webhookTokenFile}"
          ];
          Restart = "on-failure";
          RestartSec = 5;
          NoNewPrivileges = true;
          PrivateTmp = true;
          ProtectHome = true;
          ProtectSystem = "strict";
          RestrictAddressFamilies = [
            "AF_UNIX"
            "AF_INET"
            "AF_INET6"
          ];
        };
      };

      # The receiver appends to inbound.jsonl forever (stdlib open, no
      # reopen logic), so rotation must use copytruncate: the writer's fd
      # keeps working across rotation (tiny loss window accepted; the
      # alternative is teaching the receiver inode-reopen). maxsize also
      # rotates early under webhook bursts so the JSONL cannot grow
      # unbounded between daily runs.
      services.logrotate = {
        enable = true;
        settings.telnyx-webhooks = {
          files = [ shared.messagingJsonlPath ];
          frequency = "daily";
          rotate = 14;
          compress = true;
          delaycompress = true;
          extraConfig = ''
            maxsize 50M
            copytruncate
            missingok
            notifempty
          '';
        };
      };
    })
  ];
}
