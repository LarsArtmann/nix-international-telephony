# services.telephony: a batteries-included open-source PBX stack.
#
# Wires together:
#   * FreeSWITCH (upstream services.freeswitch + generated XML config)
#   * nginx serving a static SIP.js WebRTC webphone and proxying
#     wss://<host>/sip to FreeSWITCH's loopback WebSocket listener
#   * coturn (STUN/TURN) for WebRTC media traversal behind NAT
#   * call recording, voicemail, ring groups and an ITSP gateway for
#     international calling, all declared as Nix options
#
# Layout:
#   options.nix  — the option interface (types + services.telephony options)
#   pbx.nix      — FreeSWITCH service wiring, recordings, SIP TLS
#   web.nix      — nginx webphone vhost, web TLS, config.js rendering
#   edge.nix     — coturn and firewall exposure
#   shared.nix   — derived values shared across the wiring parts
{
  config,
  lib,
  ...
}:

let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };
  inherit (shared) allNumbers gatewaysForFs;
in
{
  imports = [
    ./options.nix
    ./pbx.nix
    ./web.nix
    ./edge.nix
  ];

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = cfg.eventSocketPassword != "";
        message = "services.telephony.eventSocketPassword must be set (fs_cli access).";
      }
      {
        assertion = cfg.extensions != { };
        message = "services.telephony.extensions must define at least one extension.";
      }
      {
        assertion = !cfg.turn.enable || cfg.turn.authSecret != "";
        message = "services.telephony.turn.authSecret must be set when turn is enabled.";
      }
      {
        assertion = !cfg.recording.serve.enable || cfg.recording.serve.basicAuthPasswordFile != null;
        message = "services.telephony.recording.serve.basicAuthPasswordFile must be set when serving recordings (call audio is personal data).";
      }
      {
        assertion = !cfg.recording.serve.enable || cfg.webphone.enable;
        message = "services.telephony.recording.serve requires the webphone HTTPS vhost (services.telephony.webphone.enable).";
      }
      {
        assertion = cfg.recording.retentionDays == null || cfg.recording.enable;
        message = "services.telephony.recording.retentionDays requires recording.enable.";
      }
      {
        assertion = cfg.tls.mode != "manual" || (cfg.tls.certificate != null && cfg.tls.key != null);
        message = "services.telephony.tls.certificate and .key are required when mode is manual.";
      }
      {
        assertion = cfg.tls.mode != "acme" || cfg.tls.acmeEmail != "";
        message = "services.telephony.tls.acmeEmail must be set when tls.mode is acme.";
      }
      {
        assertion = cfg.rtp.startPort < cfg.rtp.endPort;
        message = "services.telephony.rtp.startPort must be below endPort.";
      }
      {
        assertion = lib.all (n: lib.match "^[0-9]{2,7}$" n != null) allNumbers;
        message = "extension and ring-group numbers must be 2-7 digits.";
      }
      {
        assertion =
          let
            numbers = builtins.attrNames cfg.extensions;
            refs =
              (lib.concatLists (
                lib.mapAttrsToList (
                  _: g: g.members ++ lib.optional (g.voicemailMember != null) g.voicemailMember
                ) cfg.ringGroups
              ))
              ++ lib.mapAttrsToList (_: g: g.didDestination) gatewaysForFs;
            missing = builtins.filter (r: !(builtins.elem r numbers)) (lib.unique refs);
          in
          missing == [ ];
        message = "ring group members and gateway didDestinations must reference defined extensions.";
      }
      {
        assertion =
          let
            dids = lib.mapAttrsToList (_: g: g.did) gatewaysForFs;
          in
          lib.unique dids == dids;
        message = "gateways must not share inbound DIDs.";
      }
      {
        assertion = lib.all (
          name:
          !(lib.hasPrefix "/" name)
          && !(lib.any (part: part == "..") (lib.splitString "/" name))
          && lib.match ".*[[:space:]].*" name == null
        ) (builtins.attrNames cfg.extraConfigFiles);
        message = "services.telephony.extraConfigFiles keys must be relative paths without '..' or whitespace components.";
      }
      {
        assertion = (builtins.intersectAttrs cfg.extensions cfg.ringGroups) == { };
        message = "extension and ring-group numbers must not overlap.";
      }
    ];
  };
}
