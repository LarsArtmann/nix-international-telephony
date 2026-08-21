# services.telephony: a batteries-included open-source PBX stack.
#
# Wires together:
#   * FreeSWITCH (upstream services.freeswitch + generated XML config)
#   * nginx serving a static SIP.js WebRTC webphone and proxying
#     wss://<host>/sip to FreeSWITCH's loopback WebSocket listener
#   * coturn (STUN/TURN) for WebRTC media traversal behind NAT
#   * call recording, voicemail, ring groups and an ITSP gateway for
#     international calling, all declared as Nix options
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.telephony;

  digitString = lib.types.strMatching "^[0-9]+$";

  extensionType = lib.types.submodule {
    options = {
      password = lib.mkOption {
        type = lib.types.str;
        description = "SIP secret for this extension.";
      };
      displayName = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Caller-id name presented by this extension. Defaults to \"Extension <number>\“.";
      };
      allowInternational = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Whether this extension may dial international/PSTN numbers via the gateway.";
      };
      vmPassword = lib.mkOption {
        type = lib.types.nullOr digitString;
        default = null;
        description = "Voicemail PIN. Defaults to the extension number.";
      };
    };
  };

  ringGroupType = lib.types.submodule {
    options = {
      members = lib.mkOption {
        type = lib.types.nonEmptyListOf digitString;
        description = "Extensions rung simultaneously when this group is dialled.";
      };
      timeoutSec = lib.mkOption {
        type = lib.types.ints.positive;
        default = 30;
        description = "Seconds to ring before falling through to voicemail.";
      };
      voicemailMember = lib.mkOption {
        type = lib.types.nullOr digitString;
        default = null;
        description = "Member whose voicemail answers unanswered group calls. Defaults to the first member.";
      };
    };
  };

  gatewayType = lib.types.submodule {
    options = {
      name = lib.mkOption {
        type = lib.types.strMatching "^[A-Za-z0-9_-]+$";
        default = "itsp";
        description = "FreeSWITCH gateway name used in the dialplan.";
      };
      proxy = lib.mkOption {
        type = lib.types.str;
        description = "ITSP SIP proxy, e.g. sip.provider.example or sip.provider.example:5060.";
      };
      realm = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Authentication realm. Defaults to the proxy host.";
      };
      username = lib.mkOption {
        type = lib.types.str;
        description = "SIP username assigned by the provider.";
      };
      password = lib.mkOption {
        type = lib.types.str;
        description = "SIP secret assigned by the provider.";
      };
      register = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Register with the provider (most ITSPs require this).";
      };
      callerIdNumber = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Outbound caller-id number (usually your DID).";
      };
      dialPrefix = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Prefix added to dialled PSTN numbers, e.g. \"+\" or \"00\" depending on the provider.";
      };
      did = lib.mkOption {
        type = digitString;
        description = "Inbound number (DID) the provider sends.";
      };
      didDestination = lib.mkOption {
        type = digitString;
        description = "Extension or ring group that answers calls to the DID.";
      };
      fromUser = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Optional From-user override for outbound calls.";
      };
      fromDomain = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Optional From-domain override for outbound calls.";
      };
    };
  };

  webphonePkg = pkgs.callPackage ../packages/webphone { };
  soundsPkg = pkgs.callPackage ../packages/sounds.nix { };

  escapeJs = lib.replaceStrings [ "\\" "\"" ] [ "\\\\" "\\\"" ];

  # Fill option defaults that depend on their own key (extension number etc.).
  extensionsForFs = lib.mapAttrs (number: ext: {
    inherit (ext) password allowInternational;
    displayName = if ext.displayName == "" then "Extension ${number}" else ext.displayName;
    vmPassword = if ext.vmPassword == null then number else ext.vmPassword;
  }) cfg.extensions;

  ringGroupsForFs = lib.mapAttrs (_: group: {
    inherit (group) members timeoutSec;
    voicemailMember =
      if group.voicemailMember == null then builtins.head group.members else group.voicemailMember;
  }) cfg.ringGroups;

  gatewayForFs =
    if cfg.gateway == null then
      null
    else
      cfg.gateway
      // {
        realm = if cfg.gateway.realm == "" then cfg.gateway.proxy else cfg.gateway.realm;
      };

  freeswitchConfig = import ./freeswitch.nix { inherit lib pkgs; } {
    inherit (cfg) domain;
    soundsDir = if cfg.sounds.package == null then null else "${cfg.sounds.package}/sounds";
    extensions = extensionsForFs;
    ringGroups = ringGroupsForFs;
    gateway = gatewayForFs;
    inherit (cfg) eventSocketPassword natAddress;
    enableRecording = cfg.recording.enable;
    rtpStartPort = cfg.rtp.startPort;
    rtpEndPort = cfg.rtp.endPort;
  };

  tlsDir = "/var/lib/telephony/tls";
  tlsCert = if cfg.tls.mode == "manual" then cfg.tls.certificate else "${tlsDir}/cert.pem";
  tlsKey = if cfg.tls.mode == "manual" then cfg.tls.key else "${tlsDir}/key.pem";

  turnServer = "${cfg.domain}:3478";

  webRoot = pkgs.runCommand "webphone-root" { } ''
    mkdir -p $out
    cp -r ${cfg.webphone.package}/share/webphone/. $out/
    cat > $out/config.js <<EOF
    window.PBX_CONFIG = {
      sipDomain: "${escapeJs cfg.domain}",
      websocketPath: "/sip",
      iceServers: [
        { urls: ["stun:${turnServer}"] },
        { urls: ["turn:${turnServer}"], username: "${escapeJs cfg.turn.username}", credential: "${escapeJs cfg.turn.password}" }
      ]
    };
    EOF
  '';

  allNumbers = (builtins.attrNames cfg.extensions) ++ (builtins.attrNames cfg.ringGroups);
in
{
  options.services.telephony = {
    enable = lib.mkEnableOption "the telephony stack (FreeSWITCH PBX, WebRTC webphone, STUN/TURN)";

    domain = lib.mkOption {
      type = lib.types.str;
      default = "pbx.example.com";
      description = ''
        SIP domain and HTTPS server name. Phones and browsers connect to this
        name; it must resolve to this host.
      '';
    };

    eventSocketPassword = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = ''
        Password for the FreeSWITCH event socket (used by fs_cli). The socket
        only listens on 127.0.0.1. Must be set explicitly.
      '';
    };

    natAddress = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "203.0.113.10";
      description = ''
        Public IP address to advertise in SDP and SIP when running behind NAT.
        Leave null when the host itself has the public address.
      '';
    };

    openFirewall = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Open firewall ports for SIP, RTP, HTTPS and STUN/TURN.";
    };

    extensions = lib.mkOption {
      type = lib.types.attrsOf extensionType;
      default = { };
      example = {
        "1000" = {
          password = "s3cret";
          displayName = "Alice";
        };
      };
      description = "SIP extensions (directory users), keyed by number.";
    };

    ringGroups = lib.mkOption {
      type = lib.types.attrsOf ringGroupType;
      default = { };
      example = {
        "2000" = {
          members = [
            "1000"
            "1001"
          ];
          timeoutSec = 25;
        };
      };
      description = "Virtual numbers that ring several extensions simultaneously.";
    };

    gateway = lib.mkOption {
      type = lib.types.nullOr gatewayType;
      default = null;
      description = ''
        SIP trunk to an ITSP for inbound and outbound international/PSTN calls.
        When null, dialling PSTN numbers answers 503.
      '';
    };

    recording = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Record dialled calls (extensions and PSTN) as WAV under
          /var/lib/freeswitch/recordings. Both parties hear no announcement;
          check your local recording-consent law before enabling.
        '';
      };
    };

    rtp = {
      startPort = lib.mkOption {
        type = lib.types.port;
        default = 16384;
        description = "First UDP port used for RTP media.";
      };
      endPort = lib.mkOption {
        type = lib.types.port;
        default = 16584;
        description = "Last UDP port used for RTP media (~2 ports per call leg).";
      };
    };

    sounds.package = lib.mkOption {
      type = lib.types.nullOr lib.types.package;
      default = soundsPkg;
      defaultText = lib.literalExpression "pkgs.callPackage ../packages/sounds.nix { }";
      description = ''
        FreeSWITCH prompt and music-on-hold package. Without it voicemail
        prompts are silent; the null default keeps the store closure small.
      '';
    };

    webphone = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Serve the static SIP.js WebRTC softphone at https://<domain>/.";
      };
      package = lib.mkOption {
        type = lib.types.package;
        default = webphonePkg;
        defaultText = lib.literalExpression "pkgs.callPackage ../packages/webphone { }";
        description = "Webphone static-site derivation to serve.";
      };
    };

    turn = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Run coturn for STUN/TURN and hand its servers to the webphone via config.js.";
      };
      username = lib.mkOption {
        type = lib.types.str;
        default = "webphone";
        description = "Static TURN username shared by webphone clients.";
      };
      password = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Static TURN secret shared by webphone clients; required when turn is enabled.";
      };
    };

    tls = {
      mode = lib.mkOption {
        type = lib.types.enum [
          "self-signed"
          "manual"
        ];
        default = "self-signed";
        description = ''
          self-signed: generate a per-host throwaway certificate at runtime
          (browsers show a warning; fine for testing and LANs).
          manual: provide certificate and key paths, e.g. from security.acme.
        '';
      };
      certificate = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Path to the TLS certificate when mode is manual.";
      };
      key = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = "Path to the TLS key when mode is manual.";
      };
    };
  };

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
        assertion = !cfg.turn.enable || cfg.turn.password != "";
        message = "services.telephony.turn.password must be set when turn is enabled.";
      }
      {
        assertion = cfg.tls.mode != "manual" || (cfg.tls.certificate != null && cfg.tls.key != null);
        message = "services.telephony.tls.certificate and .key are required when mode is manual.";
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
              ++ lib.optional (cfg.gateway != null) cfg.gateway.didDestination;
            missing = builtins.filter (r: !(builtins.elem r numbers)) (lib.unique refs);
          in
          missing == [ ];
        message = "ring group members and gateway.didDestination must reference defined extensions.";
      }
      {
        assertion = (builtins.intersectAttrs cfg.extensions cfg.ringGroups) == { };
        message = "extension and ring-group numbers must not overlap.";
      }
    ];

    services.freeswitch = {
      enable = true;
      configDir = freeswitchConfig;
    };

    systemd.services.freeswitch = {
      after = [ "telephony-tls.service" ];
      wants = [ "telephony-tls.service" ];
      serviceConfig.ExecStartPre = [
        "${pkgs.coreutils}/bin/mkdir -p /var/lib/freeswitch/recordings /var/lib/freeswitch/empty-moh"
      ];
    };

    systemd.services.telephony-tls = lib.mkIf (cfg.tls.mode == "self-signed") {
      description = "Self-signed TLS certificate for the telephony web endpoints";
      wantedBy = [ "multi-user.target" ];
      after = [ "users-groups.service" ];
      before = [
        "nginx.service"
        "freeswitch.service"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = pkgs.writeShellScript "telephony-tls" ''
          set -eu
          ${pkgs.coreutils}/bin/mkdir -p ${tlsDir}
          if [ ! -s ${tlsDir}/cert.pem ]; then
            ${pkgs.openssl}/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
              -keyout ${tlsDir}/key.pem -out ${tlsDir}/cert.pem \
              -subj "/CN=${cfg.domain}" \
              -addext "subjectAltName=DNS:${cfg.domain}"
          fi
          # nginx runs unprivileged and reads both files; keep the key
          # group-readable only when the nginx group exists.
          ${pkgs.coreutils}/bin/chmod 755 ${tlsDir}
          ${pkgs.coreutils}/bin/chmod 644 ${tlsDir}/cert.pem
          if ${pkgs.coreutils}/bin/chown root:nginx ${tlsDir}/key.pem 2>/dev/null; then
            ${pkgs.coreutils}/bin/chmod 640 ${tlsDir}/key.pem
          else
            ${pkgs.coreutils}/bin/chmod 600 ${tlsDir}/key.pem
          fi
        '';
      };
    };

    services.nginx = lib.mkIf cfg.webphone.enable {
      enable = true;
      virtualHosts.${cfg.domain} = {
        forceSSL = true;
        sslCertificate = tlsCert;
        sslCertificateKey = tlsKey;
        root = webRoot;
        locations."/sip" = {
          proxyPass = "http://127.0.0.1:5066";
          proxyWebsockets = true;
          extraConfig = ''
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
          '';
        };
      };
    };

    services.coturn = lib.mkIf cfg.turn.enable {
      enable = true;
      realm = cfg.domain;
      lt-cred-mech = true;
      no-cli = true;
      min-port = 49160;
      max-port = 49260;
      extraConfig = ''
        user=${cfg.turn.username}:${cfg.turn.password}
      '';
    };

    networking.firewall = lib.mkIf cfg.openFirewall {
      allowedTCPPorts = [
        443
        5060
        5061
        5080
      ]
      ++ lib.optionals cfg.turn.enable [ 3478 ];
      allowedUDPPorts = [
        5060
        5080
      ]
      ++ lib.optionals cfg.turn.enable ([ 3478 ] ++ (lib.range 49160 49260))
      ++ (lib.range cfg.rtp.startPort cfg.rtp.endPort);
    };
  };
}
