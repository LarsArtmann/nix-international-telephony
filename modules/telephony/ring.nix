# The ring-while-closed hook shim: FreeSWITCH dialplan -> webphone /hooks/ring.
#
# FreeSWITCH's mod_curl application cannot hold a secret: the dialplan XML is
# store-rendered and world-readable by construction, so the ring fact travels
# UNsigned from the dialplan to this loopback shim, which attaches the Bearer
# (the shared webhook secret, read per request via LoadCredential) and forwards
# to webphone. Fire-and-forget by contract (webphone AGENTS: the dialplan must
# never depend on push health): a failed forward is logged, never retried.
#
# OFF (ringhook.enable = false) renders a byte-identical dialplan — the hook
# arms exist only when the shim is enabled.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.telephony;
in
{
  config = lib.mkMerge [
    {
      # One secret, one home: the shim signs with the SAME webhook secret the
      # messaging bridge's gateway lane uses, so derive from it when that lane
      # is configured. mkDefault keeps an explicit override possible (and the
      # assertion below still fires when neither lane provides a file).
      services.telephony.ringhook.webhookSecretFile = lib.mkIf (
        cfg.messaging.enable && cfg.messaging.gatewaySecretFile != null
      ) (lib.mkDefault cfg.messaging.gatewaySecretFile);
    }
    (lib.mkIf cfg.ringhook.enable {
      assertions = [
        {
          assertion = cfg.webphone.enable;
          message = "services.telephony.ringhook.enable requires webphone.enable (the shim exists to forward ring facts to webphone's /hooks/ring lane).";
        }
        {
          assertion = cfg.ringhook.webhookSecretFile != null;
          message = "services.telephony.ringhook.webhookSecretFile must be set (the shim signs forwarded facts with it — the same secret webphone's gateway webhook_secret_file verifies; it defaults to messaging.gatewaySecretFile when the messaging bridge is on).";
        }
      ];

      systemd.services.ringhook = {
        description = "Ring-while-closed hook shim: FreeSWITCH ring facts -> webphone /hooks/ring (Bearer-signed forward)";
        after = [
          "network.target"
          "webphone.service"
        ];
        wantedBy = [ "multi-user.target" ];
        # The shim reads the secret via $CREDENTIALS_DIRECTORY (systemd reads
        # the source file as root at start) and re-reads it PER REQUEST, so a
        # rotated secret bites on the next ring without a unit restart.
        environment = {
          PORT = toString cfg.ringhook.port;
          WEBPHONE_URL = cfg.ringhook.webphoneUrl;
        };
        serviceConfig = {
          ExecStart = "${pkgs.python3}/bin/python3 ${./ringhook.py}";
          DynamicUser = true;
          LoadCredential = [ "webphone_secret:${cfg.ringhook.webhookSecretFile}" ];
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
    })
  ];
}
