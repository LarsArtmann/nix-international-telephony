# Web wiring: the nginx vhost (TLS modes, SIP WebSocket proxy, recordings
# browsing) fronting the webphone service — the v2 Go binary from the
# webphone input's services.webphone module. TURN REST credentials are
# derived PER RESPONSE by the app itself (/config.js) from the shared
# secret injected via the runtime-rendered environment file — the old
# daily-renewed config.js shadow (and its timer) is gone.
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };
  inherit (shared)
    recordingsDir
    recordingsHtpasswd
    oneshotHardening
    operatorPort
    nginxScannerLog
    ;

  # The fail2ban nginx scanner jail (security.nix) tails the vhost's
  # access log, so web.nix pins it to a deterministic path when active.
  nginxScannerActive = cfg.fail2ban.enable && cfg.fail2ban.nginxScanner.enable && cfg.webphone.enable;

  # The operator window: read-model API + dashboard (packaged separately;
  # nginx locations below are gated on operator/phoneApi enablement).
  operatorPkg = pkgs.callPackage ../../packages/telephony-operator { };

  tlsDir = "/var/lib/telephony/tls";

  # Only used by the self-signed and manual modes; acme delegates to
  # the nginx vhost's enableACME (challenge location, group, reloads).
  tlsCert = if cfg.tls.mode == "manual" then cfg.tls.certificate else "${tlsDir}/cert.pem";
  tlsKey = if cfg.tls.mode == "manual" then cfg.tls.key else "${tlsDir}/key.pem";

  turnServer = "${cfg.domain}:3478";

  escapeJs = lib.replaceStrings [ "\\" "\"" ] [ "\\\\" "\\\"" ];

  # Shared contacts are static config; toJSON alone escapes the strings
  # for the JS wrapper (pre-escaping with escapeJs produced double-escaped
  # `\\\"` sequences once toJSON escaped the backslashes again).
  contactsJson = builtins.toJSON (
    map (contact: {
      inherit (contact)
        name
        number
        ;
    }) cfg.webphone.contacts
  );

  # nginx proxies the vhost to the webphone service; the port follows
  # services.webphone.settings.addr so operator overrides keep working.
  webphoneUpstream = "http://127.0.0.1:${lib.last (lib.splitString ":" config.services.webphone.settings.addr)}";

  # The CSP the v2 app sends itself (server.go) allows img-src data:;
  # for OUR static locations (recordings, operator) keep the strict
  # static-site posture the vhost always shipped.
  staticCsp = ''
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' wss:; img-src 'self'; media-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'" always;
  '';

  # Runtime-rendered webphone SECRETS environment (loaded by the webphone
  # module via services.webphone.environmentFiles): file-sourced secrets
  # must not land in the world-readable store config. The TURN REST
  # secret and the CRM token ride here; both are stable values, so the
  # file renders once at boot — no timer, no rotation (the app derives
  # short-lived TURN credentials per /config.js response itself).
  webphoneEnvFile = "/var/lib/telephony/webphone-env";

  # The env file carries content only when at least one file-sourced
  # secret exists — an empty EnvironmentFile is pointless (and would
  # fail the render's umask dance for nothing).
  webphoneEnvNeeded =
    (cfg.turn.enable && cfg.turn.authSecretFile != null)
    || (cfg.webphone.crm.enable && cfg.webphone.crm.tokenFile != null);

  renderWebphoneEnv = pkgs.writeShellScript "telephony-webphone-env" ''
    set -eu
    ${pkgs.coreutils}/bin/mkdir -p /var/lib/telephony
    umask 077
    : > ${webphoneEnvFile}.tmp
    ${lib.optionalString (cfg.turn.enable && cfg.turn.authSecretFile != null) ''
      printf 'WEBPHONE_TURN_REST__SECRET=%s\n' \
        "$(${pkgs.coreutils}/bin/cat ${lib.escapeShellArg cfg.turn.authSecretFile})" \
        >> ${webphoneEnvFile}.tmp
    ''}
    ${lib.optionalString (cfg.webphone.crm.enable && cfg.webphone.crm.tokenFile != null) ''
      printf 'WEBPHONE_CRM__TOKEN=%s\n' \
        "$(${pkgs.coreutils}/bin/cat ${lib.escapeShellArg cfg.webphone.crm.tokenFile})" \
        >> ${webphoneEnvFile}.tmp
    ''}
    ${pkgs.coreutils}/bin/mv ${webphoneEnvFile}.tmp ${webphoneEnvFile}
  '';
in
{
  config = lib.mkIf cfg.enable {
    security.acme = lib.mkIf (cfg.tls.mode == "acme") {
      acceptTerms = true;
      defaults.email = cfg.tls.acmeEmail;
    };

    # nginx workers call initgroups(), so membership comes from the user,
    # not the unit (systemd SupplementaryGroups is not enough). Only touch
    # the nginx user when an authenticated location actually exists —
    # defining a sub-attribute alone would create an empty user and fail
    # NixOS's user assertions (the boot suite runs without the webphone).
    users.users.nginx = lib.mkIf (cfg.recording.serve.enable || cfg.operator.enable) {
      extraGroups = [ "telephony" ];
    };

    systemd.services = {
      # nixpkgs' acme-order-renew-<cert> unit ships RestartSec=15min (chosen
      # against Let's Encrypt's 5-failed-validations-per-hour limit) but no
      # Restart=, so the RestartSec is dead config: a failed order — e.g. a
      # transient network blip in the first minute after first boot — is
      # never retried, and the vhost serves the minica self-signed
      # placeholder until the daily renewal timer happens to fire
      # (RandomizedDelaySec up to a full day later). Retry failed orders on
      # the cadence nixpkgs chose.
      "acme-order-renew-${cfg.domain}" = lib.mkIf (cfg.tls.mode == "acme") {
        unitConfig.StartLimitIntervalSec = 0;
        serviceConfig.Restart = "on-failure";
      };

      telephony-tls = lib.mkIf (cfg.tls.mode == "self-signed") {
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
    };

    # The webphone v2 service. The unit, user, hardening and the JSON
    # config rendering come from the webphone input's services.webphone
    # module (imported by this flake's nixosModules.telephony) so the
    # binary and its deployment shape stay in sync upstream.
    #
    # ICE/TURN is deliberately NOT wired into settings.ice_servers: the
    # runtime-rendered /var/lib/telephony/config.js (the nginx location
    # below shadows the app's own /config.js) carries short-lived REST
    # credentials renewed daily by the timer — a settings list baked at
    # eval time cannot rotate, and restarting the app to refresh it would
    # drop its in-memory sessions every day.
    #
    # Outbound SMS/MMS/fax gateway: defaults to loopback; point
    # services.webphone.settings.gateway at a webhook provider (secret via
    # services.webphone.environmentFile) for real delivery.
    services.webphone = lib.mkIf cfg.webphone.enable {
      enable = true;
      package = cfg.webphone.package;
      settings = {
        addr = lib.mkDefault "127.0.0.1:8080";
        sip_domain = cfg.domain;
        contacts = map (contact: {
          inherit (contact)
            name
            number
            ;
        }) cfg.webphone.contacts;
        # The vhost below terminates TLS, so the browser's Origin is
        # https://<domain> while the webphone listener sees plain HTTP
        # from the local nginx. Without these the CSRF middleware reads
        # the truthful Origin as a forged same-origin attestation and
        # 403s every POST (logins included).
        csrf = {
          trusted_proxies = [ "127.0.0.1" ];
          trusted_origins = [ "https://${cfg.domain}" ];
        };
      }
      // lib.optionalAttrs cfg.webphone.phoneApi.enable {
        # The app proxies the island's /phone-api/* calls here itself,
        # injecting Basic auth from the signed-in extension's session.
        phone_api_url = "http://127.0.0.1:${toString operatorPort}";
      };
    };

    services.nginx = lib.mkIf cfg.webphone.enable {
      enable = true;
      virtualHosts.${cfg.domain} = {
        forceSSL = true;
        # acme mode delegates cert wiring to nixpkgs' nginx-ACME
        # integration: it provisions the HTTP-01 challenge location, the
        # nginx group and reloads. A hand-rolled security.acme.certs
        # entry without a challenge provider fails security.acme's
        # assertion (caught by checks.telephony-eval).
        sslCertificate = lib.mkIf (cfg.tls.mode != "acme") tlsCert;
        sslCertificateKey = lib.mkIf (cfg.tls.mode != "acme") tlsKey;
        enableACME = cfg.tls.mode == "acme";
        # The v2 app (pages, assets, session API, SSE, its server-side
        # /phone-api proxy) rides this catch-all; the app sends its own
        # CSP on every response, so the vhost adds none.
        locations."/" = {
          recommendedProxySettings = true;
          proxyPass = webphoneUpstream;
        };
        # SSE feed (session-gated, HTMX): stream unbuffered and without a
        # read timeout worth having — events outlive any default.
        locations."/events" = {
          recommendedProxySettings = true;
          proxyPass = webphoneUpstream;
          extraConfig = ''
            proxy_http_version 1.1;
            proxy_buffering off;
            proxy_read_timeout 3600s;
          '';
        };
        extraConfig = lib.optionalString nginxScannerActive "access_log ${nginxScannerLog};";
        # Runtime-rendered (TURN credentials are short-lived). Served by
        # nginx instead of the app so the daily renewal never needs a
        # service restart (the shadowed app-side /config.js would freeze
        # the credentials at process start).
        locations."= /config.js".root = "/var/lib/telephony";
        # Recorded-call browsing, gated by basic auth (rendered at runtime).
        locations."/recordings/" = lib.mkIf cfg.recording.serve.enable {
          alias = "${recordingsDir}/";
          extraConfig = ''
            autoindex on;
            auth_basic "Call recordings";
            auth_basic_user_file ${recordingsHtpasswd};
            ${staticCsp}
          '';
        };
        # Operator window: static dashboard + read-model JSON API. Both sit
        # behind the same basic-auth realm as /recordings/ (one operator
        # credential); the API itself binds loopback only and never mutates
        # PBX state (a window, not an editor).
        locations."= /operator" = lib.mkIf cfg.operator.enable {
          return = "301 /operator/";
        };
        locations."/operator/" = lib.mkIf cfg.operator.enable {
          alias = "${operatorPkg}/share/telephony-operator/webroot/";
          extraConfig = ''
            auth_basic "PBX operator";
            auth_basic_user_file ${recordingsHtpasswd};
            ${staticCsp}
          '';
        };
        locations."/operator-api/" = lib.mkIf cfg.operator.enable {
          proxyPass = "http://127.0.0.1:${toString operatorPort}/api/";
          extraConfig = ''
            auth_basic "PBX operator";
            auth_basic_user_file ${recordingsHtpasswd};
            proxy_read_timeout 30s;
            ${staticCsp}
          '';
        };
        # Exact match: this is also a prefix trap — `location /sip` would
        # capture /sip.min.js (the SIP.js bundle) and proxy it to sofia,
        # which answers 400 to the plain GET and leaves the webphone dead.
        # TLS upstream to sofia's wss-binding: browsers only speak wss from
        # https pages (Via/WSS), and FreeSWITCH drops REGISTERs whose Via
        # transport mismatches the connection — a plain-ws hop would eat
        # every browser REGISTER (nginx does not verify the upstream cert).
        locations."= /sip" = {
          proxyPass = "https://127.0.0.1:7443";
          proxyWebsockets = true;
          extraConfig = ''
            proxy_ssl_protocols TLSv1.2 TLSv1.3;
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
