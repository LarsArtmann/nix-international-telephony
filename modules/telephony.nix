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
      priority = lib.mkOption {
        type = lib.types.ints.unsigned;
        default = 100;
        description = ''
          Outbound routing priority: lower numbers are tried first
          (least-cost routing across gateways).
        '';
      };
      allowedCidrs = lib.mkOption {
        type = lib.types.listOf (lib.types.strMatching "^[0-9]{1,3}(\\.[0-9]{1,3}){3}(/[0-9]{1,2})?$");
        default = [ ];
        example = [ "203.0.113.0/24" ];
        description = ''
          Source addresses of the provider, as IPv4 CIDRs (host addresses
          allowed). When non-empty, inbound calls on the external profile
          are checked against an ACL restricted to these addresses:
          INVITEs from anywhere else are rejected before the dialplan.
          Empty disables the ACL; restrict reachability with the firewall
          (services.telephony.firewall.restrictExternalTo) instead.
        '';
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

  # Merge the deprecated singular gateway into the attrsOf form and fill
  # the realm default (proxy host when unset).
  gatewaysForFs =
    lib.mapAttrs
      (
        _name: gateway:
        gateway
        // {
          realm = if gateway.realm == "" then gateway.proxy else gateway.realm;
        }
      )
      (cfg.gateways // (lib.optionalAttrs (cfg.gateway != null) { ${cfg.gateway.name} = cfg.gateway; }));

  freeswitchConfig = import ./freeswitch.nix { inherit lib pkgs; } {
    inherit (cfg) domain;
    soundsDir = if cfg.sounds.package == null then null else "${cfg.sounds.package}/sounds";
    extensions = extensionsForFs;
    ringGroups = ringGroupsForFs;
    gateways = gatewaysForFs;
    inherit (cfg) eventSocketPassword natAddress;
    enableRecording = cfg.recording.enable;
    enableCdr = cfg.cdr.enable;
    tlsCertDir = if cfg.tls.mode == "acme" then fsCertDir else null;
    rtpStartPort = cfg.rtp.startPort;
    rtpEndPort = cfg.rtp.endPort;
  };

  tlsDir = "/var/lib/telephony/tls";
  tlsCert =
    if cfg.tls.mode == "manual" then
      cfg.tls.certificate
    else if cfg.tls.mode == "acme" then
      "/var/lib/acme/${cfg.domain}/cert.pem"
    else
      "${tlsDir}/cert.pem";
  tlsKey =
    if cfg.tls.mode == "manual" then
      cfg.tls.key
    else if cfg.tls.mode == "acme" then
      "/var/lib/acme/${cfg.domain}/key.pem"
    else
      "${tlsDir}/key.pem";

  # FreeSWITCH TLS cert directory (agent.pem = cert+key, cafile.pem = chain)
  # provisioned from the ACME certificate for the internal profile's 5061.
  fsCertDir = "/var/lib/freeswitch/tls-certs";

  turnServer = "${cfg.domain}:3478";

  # TURN REST credentials are valid for this long; the renewal timer runs
  # at half the validity so a rendered config.js never carries stale creds.
  turnCredentialValiditySec = 48 * 3600;

  # Concatenate the ACME certificate into FreeSWITCH's tls-cert-dir layout
  # (agent.pem = cert+key, cafile.pem = chain); when FreeSWITCH is already
  # running the internal profile is restarted so SIP TLS uses the new
  # material.
  renderFsCert = pkgs.writeShellScript "telephony-fs-cert" ''
    set -eu
    ${pkgs.coreutils}/bin/mkdir -p ${fsCertDir}
    ${pkgs.coreutils}/bin/cat /var/lib/acme/${cfg.domain}/fullchain.pem       /var/lib/acme/${cfg.domain}/key.pem > ${fsCertDir}/agent.pem.tmp
    ${pkgs.coreutils}/bin/cp /var/lib/acme/${cfg.domain}/fullchain.pem ${fsCertDir}/cafile.pem.tmp
    ${pkgs.coreutils}/bin/chmod 600 ${fsCertDir}/agent.pem.tmp ${fsCertDir}/cafile.pem.tmp
    ${pkgs.coreutils}/bin/mv ${fsCertDir}/agent.pem.tmp ${fsCertDir}/agent.pem
    ${pkgs.coreutils}/bin/mv ${fsCertDir}/cafile.pem.tmp ${fsCertDir}/cafile.pem
    if ${pkgs.freeswitch}/bin/fs_cli -p ${cfg.eventSocketPassword} -x 'sofia status' >/dev/null 2>&1; then
      ${pkgs.freeswitch}/bin/fs_cli -p ${cfg.eventSocketPassword} -x 'sofia profile internal restart'
    fi
  '';

  # Runtime-rendered webphone config (contains short-lived TURN
  # credentials, so it cannot be baked into the store).
  webConfigFile = "/var/lib/telephony/config.js";

  renderWebConfig = pkgs.writeShellScript "telephony-web-config" ''
    set -eu
    ${pkgs.coreutils}/bin/mkdir -p /var/lib/telephony
    expiry=$(( $(${pkgs.coreutils}/bin/date +%s) + ${toString turnCredentialValiditySec} ))
    ice_servers="[]"
    ${
      if cfg.turn.enable then
        ''
          username="''${expiry}:webphone"
          password=$(printf '%s' "$username" \
            | ${pkgs.openssl}/bin/openssl dgst -sha1 -hmac "${cfg.turn.authSecret}" -binary \
            | ${pkgs.coreutils}/bin/base64 -w0)
          ice_servers="[{ \"urls\": [\"stun:${turnServer}\"] }, { \"urls\": [\"turn:${turnServer}\"], \"username\": \"$username\", \"credential\": \"$password\" }]"
        ''
      else
        ""
    }
    cat > ${webConfigFile}.tmp <<EOF
    window.PBX_CONFIG = {
      "sipDomain": "${escapeJs cfg.domain}",
      "websocketPath": "/sip",
      "iceServers": $ice_servers
    };
    EOF
    ${pkgs.coreutils}/bin/chmod 644 ${webConfigFile}.tmp
    ${pkgs.coreutils}/bin/mv ${webConfigFile}.tmp ${webConfigFile}
  '';

  webRoot = pkgs.runCommand "webphone-root" { } ''
    mkdir -p $out
    cp -r ${cfg.webphone.package}/share/webphone/. $out/
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

    firewall.restrictExternalTo = lib.mkOption {
      type = lib.types.listOf (lib.types.strMatching "^[0-9]{1,3}(\\.[0-9]{1,3}){3}(/[0-9]{1,2})?$");
      default = [ ];
      example = [ "203.0.113.0/24" ];
      description = ''
        Restrict the external SIP profile's port 5080 (TCP and UDP) to these
        source IPv4 CIDRs — your ITSP's addresses. With an empty list 5080
        stays open to all sources; pair this with gateway.allowedCidrs so
        non-listed sources are also rejected at the SIP layer.
      '';
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

    gateways = lib.mkOption {
      type = lib.types.attrsOf gatewayType;
      default = { };
      description = ''
        SIP trunks to ITSPs for inbound and outbound international/PSTN
        calls, keyed by gateway name. Outbound calls fail over across
        gateways in ascending priority; inbound calls route per-gateway
        DID. With no gateways, dialling PSTN numbers answers 503.
      '';
    };

    gateway = lib.mkOption {
      type = lib.types.nullOr gatewayType;
      default = null;
      description = ''
        Deprecated single-trunk form; equivalent to
        gateways.''${name}. Prefer services.telephony.gateways.
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

    cdr.enable = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Write CSV call detail records (one row per call leg, appended to
        Master.csv) under /var/lib/freeswitch/cdr.
      '';
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
      authSecret = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = ''
          Shared secret for TURN REST-style credentials (coturn
          use-auth-secret). The webphone is served short-lived
          username/password pairs derived from this secret instead of a
          static credential; the secret itself never leaves the server.
          Required when turn is enabled. Replaces the former static
          turn.username/turn.password pair.
        '';
      };
    };

    tls = {
      mode = lib.mkOption {
        type = lib.types.enum [
          "self-signed"
          "manual"
          "acme"
        ];
        default = "self-signed";
        description = ''
          self-signed: generate a per-host throwaway certificate at runtime
          (browsers show a warning; fine for testing and LANs).
          manual: provide certificate and key paths, e.g. from security.acme.
          acme: obtain a real certificate via security.acme for the domain
          (requires tls.acmeEmail and a publicly reachable host); the same
          certificate is also provisioned to FreeSWITCH's SIP-over-TLS
          listener on 5061.
        '';
      };
      acmeEmail = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "Account email for Let's Encrypt (required when tls.mode is acme).";
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
        assertion = !cfg.turn.enable || cfg.turn.authSecret != "";
        message = "services.telephony.turn.authSecret must be set when turn is enabled.";
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
      ]
      ++ lib.optionals cfg.cdr.enable [
        "${pkgs.coreutils}/bin/mkdir -p /var/lib/freeswitch/cdr-csv"
      ];
    };

    security.acme = lib.mkIf (cfg.tls.mode == "acme") {
      acceptTerms = true;
      defaults.email = cfg.tls.acmeEmail;
      certs.${cfg.domain}.group = "nginx";
    };

    # Provision the ACME certificate to FreeSWITCH's SIP-over-TLS listener:
    # sofia reads agent.pem (cert+key) and cafile.pem from tls-cert-dir.
    systemd.services.telephony-fs-cert = lib.mkIf (cfg.tls.mode == "acme") {
      description = "Provision ACME certificate to FreeSWITCH SIP TLS";
      wantedBy = [ "multi-user.target" ];
      after = [ "acme-finished-${cfg.domain}.service" ];
      wants = [ "acme-finished-${cfg.domain}.service" ];
      before = [ "freeswitch.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = renderFsCert;
      };
    };

    # Renewal: when ACME rotates the certificate, re-provision (the service
    # restarts the internal profile so 5061 picks up the new material).
    systemd.paths.telephony-fs-cert = lib.mkIf (cfg.tls.mode == "acme") {
      wantedBy = [ "multi-user.target" ];
      pathConfig.PathChanged = "/var/lib/acme/${cfg.domain}/cert.pem";
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
        # Runtime-rendered (TURN credentials are short-lived).
        locations."= /config.js".root = "/var/lib/telephony";
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

    # Render config.js with fresh TURN REST credentials at boot and renew it
    # daily (credentials stay valid for 48h, so an unrenewed file still works
    # for a day).
    systemd.services.telephony-web-config = lib.mkIf cfg.webphone.enable {
      description = "Render webphone config.js with ephemeral TURN credentials";
      wantedBy = [ "multi-user.target" ];
      before = [ "nginx.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = renderWebConfig;
      };
    };

    systemd.timers.telephony-web-config = lib.mkIf cfg.webphone.enable {
      description = "Renew webphone TURN credentials daily";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
      };
    };

    services.coturn = lib.mkIf cfg.turn.enable {
      enable = true;
      realm = cfg.domain;
      use-auth-secret = true;
      static-auth-secret = cfg.turn.authSecret;
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
