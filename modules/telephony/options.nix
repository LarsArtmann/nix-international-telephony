# Interface of services.telephony: every option plus the submodule types
# they are built from. Wiring lives in the sibling files (see default.nix).
{
  lib,
  pkgs,
  ...
}:

let
  webphonePkg = pkgs.callPackage ../../packages/webphone { };
  soundsPkg = pkgs.callPackage ../../packages/sounds.nix { };

  digitString = lib.types.strMatching "^[0-9]+$";

  extensionType = lib.types.submodule {
    options = {
      password = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "SIP secret for this extension. Set exactly one of password/passwordFile.";
      };
      passwordFile = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "/run/secrets/telephony-ext-1000";
        description = ''
          Absolute path to a runtime file (e.g. rendered by sops-nix or
          agenix at activation) containing this extension's SIP secret
          (single line). When set it replaces password and the secret
          never lands in the world-readable Nix store: the generated
          directory XML carries a placeholder that the freeswitch unit
          substitutes from the file at service start.
        '';
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
        default = "";
        description = "SIP secret assigned by the provider. Set exactly one of password/passwordFile.";
      };
      passwordFile = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "/run/secrets/telephony-gateway-itsp";
        description = ''
          Absolute path to a runtime file (sops-nix/agenix-rendered)
          containing the provider SIP secret (single line). When set it
          replaces password and the secret never lands in the store; the
          generated gateway XML carries a placeholder substituted at
          service start.
        '';
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
        only listens on 127.0.0.1. Must be set explicitly (or use
        eventSocketPasswordFile).
      '';
    };

    eventSocketPasswordFile = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "/run/secrets/telephony-event-socket";
      description = ''
        Absolute path to a runtime file (sops-nix/agenix-rendered)
        containing the event-socket password (single line). Replaces
        eventSocketPassword; set exactly one of the two. The password is
        substituted into the FreeSWITCH config at service start and never
        lands in the Nix store.
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

    natSipAddress = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "sip.example.com";
      description = ''
        Public address advertised in SIP (Via/Contact) when it differs from
        the RTP address — e.g. asymmetric NAT or a separate SIP edge proxy.
        Defaults to natAddress (or the local address when that is null).
      '';
    };

    natRtpAddress = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "203.0.113.10";
      description = ''
        Public address advertised in SDP (media) when it differs from the
        SIP address — e.g. a media relay in front of the PBX. Defaults to
        natAddress (or the local address when that is null).
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

    extraConfigFiles = lib.mkOption {
      type = lib.types.attrsOf lib.types.path;
      default = { };
      example = {
        "sip_profiles/custom.xml" = ./custom-profile.xml;
      };
      description = ''
        Escape hatch for FreeSWITCH configuration this module does not
        model: extra files merged into the generated config directory.
        Keys are paths relative to the FreeSWITCH conf directory (e.g.
        "autoload_configs/my.conf.xml", "dialplan/extra.xml"); values are
        files. A key that collides with a generated file REPLACES it —
        overriding e.g. "dialplan/default.xml" silently discards the
        generated dialplan, so prefer additive keys. Keys must be relative
        paths without ".." components.
      '';
    };

    recording = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Record dialled calls (extensions and PSTN) as WAV under
          /var/lib/telephony/recordings. Both parties hear no announcement;
          check your local recording-consent law before enabling.
        '';
      };
      retentionDays = lib.mkOption {
        type = lib.types.nullOr lib.types.ints.positive;
        default = null;
        example = 90;
        description = ''
          Days to keep recorded calls; a daily timer deletes WAV files
          older than this. null (default) keeps recordings forever.
          Requires recording.enable.
        '';
      };
      serve = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = false;
          description = ''
            Serve recorded calls over HTTPS at https://<domain>/recordings/
            with an nginx directory listing, protected by HTTP basic auth.
            Recordings are personal data — basicAuthPasswordFile is
            required, and you should put TLS (see tls.mode = "acme") in
            front before exposing this beyond trusted networks.
          '';
        };
        basicAuthUser = lib.mkOption {
          type = lib.types.str;
          default = "admin";
          description = "Username for the /recordings/ basic-auth prompt.";
        };
        basicAuthPasswordFile = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "/run/keys/recordings-password";
          description = ''
            Path to a file containing the basic-auth password (single
            line, no colon or newline). Read at boot by a oneshot unit
            that renders an htpasswd file nginx checks; point this at a
            runtime secret (e.g. sops/agenix-rendered), not a store path,
            to keep the password out of the world-readable store.
            Required when serve.enable is true.
          '';
        };
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
      defaultText = lib.literalExpression "pkgs.callPackage ../../packages/sounds.nix { }";
      description = ''
        FreeSWITCH prompt and music-on-hold package. Without it voicemail
        prompts are silent; the null default keeps the store closure small.
      '';
    };

    webphone = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Serve the static SIP.js WebRTC softphone at https://<domain>/.
          When the webphone misbehaves in the browser, the failure
          playbook and the raw wss probe live in docs/ops-runbook.md.
        '';
      };
      package = lib.mkOption {
        type = lib.types.package;
        default = webphonePkg;
        defaultText = lib.literalExpression "pkgs.callPackage ../../packages/webphone { }";
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
          Set exactly one of authSecret/authSecretFile.
        '';
      };
      authSecretFile = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "/run/secrets/telephony-turn";
        description = ''
          Absolute path to a runtime file (sops-nix/agenix-rendered)
          containing the TURN REST shared secret (single line). Replaces
          authSecret and feeds coturn via its native
          static-auth-secret-file, so the secret never lands in the Nix
          store. Required (in one of the two forms) when turn is enabled.
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
}
