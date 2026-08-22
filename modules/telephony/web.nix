# Web wiring: the nginx webphone vhost (TLS modes, SIP WebSocket proxy,
# recordings browsing) and the runtime-rendered config.js carrying
# short-lived TURN credentials.
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };
  inherit (shared) recordingsDir recordingsHtpasswd oneshotHardening;

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

  turnServer = "${cfg.domain}:3478";

  # TURN REST credentials are valid for this long; the renewal timer runs
  # at half the validity so a rendered config.js never carries stale creds.
  turnCredentialValiditySec = 48 * 3600;

  escapeJs = lib.replaceStrings [ "\\" "\"" ] [ "\\\\" "\\\"" ];

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
in
{
  config = lib.mkIf cfg.enable {
    security.acme = lib.mkIf (cfg.tls.mode == "acme") {
      acceptTerms = true;
      defaults.email = cfg.tls.acmeEmail;
      certs.${cfg.domain}.group = "nginx";
    };

    # nginx workers call initgroups(), so membership comes from the user,
    # not the unit (systemd SupplementaryGroups is not enough).
    users.users.nginx.extraGroups = lib.optional cfg.recording.serve.enable "telephony";

    systemd.services.telephony-tls = lib.mkIf (cfg.tls.mode == "self-signed") {
      description = "Self-signed TLS certificate for the telephony web endpoints";
      wantedBy = [ "multi-user.target" ];
      after = [ "users-groups.service" ];
      before = [
        "nginx.service"
        "freeswitch.service"
      ];
      serviceConfig = oneshotHardening // {
        Type = "oneshot";
        ReadWritePaths = [ "/var/lib/telephony" ];
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
        # Everything the webphone needs is same-origin (bundled sip.js,
        # local assets) plus the wss SIP proxy; deny the rest.
        extraConfig = ''
          add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' wss:; img-src 'self'; media-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" always;
        '';
        # Runtime-rendered (TURN credentials are short-lived).
        locations."= /config.js".root = "/var/lib/telephony";
        # Recorded-call browsing, gated by basic auth (rendered at runtime).
        locations."/recordings/" = lib.mkIf cfg.recording.serve.enable {
          alias = "${recordingsDir}/";
          extraConfig = ''
            autoindex on;
            auth_basic "Call recordings";
            auth_basic_user_file ${recordingsHtpasswd};
          '';
        };
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
      serviceConfig = oneshotHardening // {
        Type = "oneshot";
        ReadWritePaths = [ "/var/lib/telephony" ];
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
  };
}
