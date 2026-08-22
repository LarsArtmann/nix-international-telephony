# Network-edge wiring: coturn (STUN/TURN relay for WebRTC media behind
# NAT) and the firewall exposure of SIP/RTP/HTTPS/TURN ports.
{
  config,
  lib,
  ...
}:

let
  cfg = config.services.telephony;
in
{
  config = lib.mkIf cfg.enable {
    services.coturn = lib.mkIf cfg.turn.enable {
      enable = true;
      realm = cfg.domain;
      use-auth-secret = true;
      # File mode feeds coturn's native static-auth-secret-file (spliced
      # into its runtime config by the upstream unit's preStart), so the
      # secret never lands in the store. The two options are mutually
      # exclusive upstream.
      static-auth-secret = if cfg.turn.authSecretFile == null then cfg.turn.authSecret else null;
      static-auth-secret-file = cfg.turn.authSecretFile;
      no-cli = true;
      min-port = 49160;
      max-port = 49260;
    };

    networking.firewall = lib.mkIf cfg.openFirewall {
      allowedTCPPorts = [
        443
        5060
        5061
      ]
      ++ lib.optionals (cfg.firewall.restrictExternalTo == [ ]) [ 5080 ]
      ++ lib.optionals cfg.turn.enable [ 3478 ];
      allowedUDPPorts = [
        5060
      ]
      ++ lib.optionals (cfg.firewall.restrictExternalTo == [ ]) [ 5080 ]
      ++ lib.optionals cfg.turn.enable ([ 3478 ] ++ (lib.range 49160 49260))
      ++ (lib.range cfg.rtp.startPort cfg.rtp.endPort);
      extraInputRules = lib.concatMapStrings (cidr: ''
        ip saddr ${cidr} tcp dport 5080 accept
        ip saddr ${cidr} udp dport 5080 accept
      '') cfg.firewall.restrictExternalTo;
    };
  };
}
