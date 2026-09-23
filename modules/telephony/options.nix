# Interface of services.telephony: every option plus the submodule types
# they are built from. Wiring lives in the sibling files (see default.nix).
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.telephony;

  soundsPkg = pkgs.callPackage ../../packages/sounds.nix { };

  digitString = lib.types.strMatching "^[0-9]+$";

  conferenceType = lib.types.submodule {
    options = {
      extension = lib.mkOption {
        type = digitString;
        description = "Number callers dial to join this room.";
      };
      profile = lib.mkOption {
        type = lib.types.str;
        default = "default";
        description = ''
          mod_conference profile from conference.conf.xml (the vanilla
          "default" ships music-on-hold while alone and a sane mix).
        '';
      };
      pin = lib.mkOption {
        type = lib.types.nullOr digitString;
        default = null;
        description = "PIN callers must enter to join (null = open room).";
      };
    };
  };

  ivrEntryType = lib.types.submodule {
    options = {
      destination = lib.mkOption {
        type = lib.types.str;
        description = ''
          Where this key routes: an extension number, a ring group, the
          echo test (9196), or any PSTN number the dialplan can handle.
        '';
      };
    };
  };

  ivrType = lib.types.submodule {
    options = {
      extension = lib.mkOption {
        type = digitString;
        description = "Number callers dial to reach this menu.";
      };
      greetingSound = lib.mkOption {
        type = lib.types.str;
        default = "tone_stream://%(1000,0,640)";
        description = ''
          Sound played before digit collection: a tone_stream pattern
          (default beep) or a sound file path under the configured
          sounds package, e.g. "en/us/callie/ivr/8000/ivr-menu.wav"
          (see services.telephony.sounds.package).
        '';
      };
      invalidSound = lib.mkOption {
        type = lib.types.str;
        default = "tone_stream://%(400,0,480)";
        description = "Sound played for an unmatched key before re-collecting.";
      };
      timeoutSec = lib.mkOption {
        type = lib.types.ints.positive;
        default = 6;
        description = "Seconds to wait for each keypress before re-prompting.";
      };
      maxTries = lib.mkOption {
        type = lib.types.ints.between 1 9;
        default = 3;
        description = "Collection attempts (initial + re-prompts) before the fallback.";
      };
      entries = lib.mkOption {
        type = lib.types.attrsOf ivrEntryType;
        description = ''
          Key-to-destination mapping. Keys are digit strings, optionally
          with `*` (e.g. "1", "42", "*1"); callers finish multi-digit
          keys with # or the collect timeout. `#` itself terminates
          input and cannot be a menu key.
        '';
      };
      fallbackDestination = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = ''
          Destination for wrong/absent input after maxTries. null hangs
          up (operator-friendly menus usually point this at a ring
          group).
        '';
      };
    };
  };

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
      vmEmail = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "alice@example.com";
        description = ''
          Email address new voicemails are sent to (mod_voicemail's
          vm-mailto). Requires a working mailer: set
          voicemail.mailerCommand (e.g. msmtp) or wire mailer-app in
          switch.conf.xml yourself.
        '';
      };
      callerIdNumber = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "+441632960961";
        description = ''
          Outbound caller-id number for PSTN calls from this extension,
          overriding the gateway's DID (some providers allow per-account
          numbers; check yours).
        '';
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
      timeWindow = {
        days = lib.mkOption {
          type = lib.types.listOf (
            lib.types.enum [
              "sun"
              "mon"
              "tue"
              "wed"
              "thu"
              "fri"
              "sat"
            ]
          );
          default = [
            "mon"
            "tue"
            "wed"
            "thu"
            "fri"
          ];
          description = "Days of the week the group rings (server local time).";
        };
        startHour = lib.mkOption {
          type = lib.types.ints.between 0 23;
          default = 9;
          description = "First hour (inclusive) of the ringing window.";
        };
        endHour = lib.mkOption {
          type = lib.types.ints.between 0 23;
          default = 17;
          description = "Last hour (inclusive) of the ringing window.";
        };
        afterHoursDestination = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          description = ''
            Where calls go outside the window (evenings/weekends): an
            extension, ring group, or any dialplan destination (e.g. an
            IVR announcing "we are closed"). null (default) disables
            time routing — the group rings around the clock.
          '';
        };
      };
    };
  };

  contactType = lib.types.submodule {
    options = {
      name = lib.mkOption {
        type = lib.types.str;
        description = "Display name shown in the webphone contacts list.";
      };
      number = lib.mkOption {
        type = lib.types.str;
        description = "Dialable number: an extension, ring group, or full PSTN number (E.164 with +).";
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
      retrySeconds = lib.mkOption {
        type = lib.types.nullOr (lib.types.ints.between 1 3600);
        default = null;
        example = 15;
        description = ''
          Base seconds between REGISTER retries, wired as the gateway
          param retry-seconds. FreeSWITCH's default is 30 and it grows
          linearly per consecutive failure (retry-seconds x failures):
          a provider whose load-balancer intermittently re-challenges
          REGISTERs (Telnyx observed doing so 2026-09-18) then stays
          "down" for minutes between attempts. A low value keeps the
          retry cadence tight through bad streaks. Null omits the param
          (FreeSWITCH default).
        '';
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
      gwAuthAcl = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "trusted-itsp";
        description = ''
          Network-list name (acl.conf.xml) that digest-challenge sources
          for this gateway must match, wired as the gateway param
          gw-auth-acl. FreeSWITCH gates a gateway's challenge credentials
          on the challenge arriving from an address the proxy hostname
          resolves to AT CHALLENGE TIME (is_legitimate_gateway); providers
          whose proxy DNS rotates between edges (Telnyx round-robins
          sip.telnyx.com between at least two anycast edges) fail that
          comparison and every outbound call dies with "Cannot locate any
          authentication credentials" -> MANDATORY_IE_MISSING. Setting
          gw-auth-acl replaces the DNS comparison with an ACL match.
          Currently the only emitted list is trusted-itsp, built from
          allowedCidrs, so set those too.
        '';
      };
      faxDid = lib.mkOption {
        type = lib.types.nullOr digitString;
        default = null;
        description = ''
          DID dedicated to inbound fax for this trunk (requires
          services.telephony.fax.enable). The provider must route this
          number to the PBX; inbound calls to it run mod_spandsp's rxfax
          and land as TIFF files under the recordings fax directory.
        '';
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

    conferences = lib.mkOption {
      type = lib.types.attrsOf conferenceType;
      default = { };
      example = {
        sales = {
          extension = "5000";
          pin = "3141";
        };
      };
      description = ''
        Conference rooms (mod_conference): dial the extension to join;
        with a pin set, callers are prompted for it before joining.
      '';
    };

    ivrs = lib.mkOption {
      type = lib.types.attrsOf ivrType;
      default = { };
      example = {
        main = {
          extension = "4000";
          greetingSound = "en/us/callie/ivr/8000/ivr-menu.wav";
          entries = {
            "1".destination = "1000";
            "2".destination = "2000";
          };
          fallbackDestination = "2000";
        };
      };
      description = ''
        Declarative IVR menus: dial the extension, hear the greeting,
        press a key (terminated by #) and land at the mapped
        destination. Implemented with play_and_get_digits + dialplan
        routing — no extra FreeSWITCH modules.
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

    voicemail = {
      mailerCommand = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        example = lib.literalExpression "pkgs.msmtp";
        description = ''
          Program FreeSWITCH pipes outgoing voicemail emails (per-extension
          vmEmail) through — the core "mailer-app" setting. It receives the
          full RFC 5322 message on stdin, invoked sendmail-style as
          "mailerCommand -f <from> -t <to>"; msmtp works out of the box.
          null keeps the compiled-in default ("sendmail"), which stock
          NixOS hosts do not have — without a mailer, vmEmail messages
          silently go nowhere.
        '';
      };
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
        Master.csv) under /var/lib/freeswitch/cdr-csv.
      '';
    };

    fax.enable = lib.mkEnableOption "inbound fax receive (mod_spandsp rxfax): calls to fax.extension render the caller's fax to a TIFF file under the recordings fax directory";

    fax.extension = lib.mkOption {
      type = digitString;
      default = "6000";
      description = ''
        Number that answers with rxfax when fax is enabled. Route calls
        here from a DID (gateway.<name>.faxDid) or any dialplan target.
      '';
    };

    fax.feed.enable = lib.mkEnableOption "inbound fax feed to webphone: convert rxfax TIFFs to PDF and POST them to the webphone /hooks/fax webhook so they appear in the Fax tab";

    fax.feed.owner = lib.mkOption {
      type = digitString;
      default = cfg.fax.extension;
      defaultText = lib.literalExpression "config.services.telephony.fax.extension";
      description = ''
        Webphone extension that owns the fed faxes (the Fax tab scopes by
        extension). Defaults to the fax extension itself.
      '';
    };

    fax.feed.from = lib.mkOption {
      type = digitString;
      default = "0000";
      description = ''
        Sender identity recorded for fed faxes (webphone validates it as
        a dialable number). Set it to the trunk's faxDid so the Fax tab
        shows the real sender instead of the 0000 placeholder.
      '';
    };

    fax.feed.webphoneUrl = lib.mkOption {
      type = lib.types.str;
      default = "http://127.0.0.1:8080";
      description = "Base URL of the webphone service receiving the hooks.";
    };

    fax.feed.secretFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      example = "/run/secrets/telephony-webphone-hook-secret";
      description = ''
        Runtime file containing the webphone gateway webhook secret
        (single line) — the same value as
        services.webphone.settings.gateway.webhook_secret. Required when
        feed.enable is true; mounted via LoadCredential.
      '';
    };

    fax.feed.sweepInterval = lib.mkOption {
      type = lib.types.ints.positive;
      default = 5;
      description = "Minutes between retry sweeps of unconverted fax TIFFs.";
    };

    operator.enable = lib.mkEnableOption "the operator web window: a read-only dashboard (CDR viewer, live health, dialplan simulator) served at /operator/ — it renders runtime state, it never mutates it";

    operator.apiUser = lib.mkOption {
      type = lib.types.str;
      default = "admin";
      description = "Username for the /operator/ basic-auth prompt (shared realm with /recordings/).";
    };

    operator.apiPasswordFile = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "/run/secrets/telephony-operator-password";
      description = ''
        Path to a runtime file containing the operator basic-auth password
        (single line). Required when operator.enable is true; rendered
        into the same htpasswd file /recordings/ uses, so both surfaces
        share one operator credential.
      '';
    };

    operator.smsMessageStore = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      example = "/var/lib/telnyx-webhooks/inbound.jsonl";
      description = ''
        Optional append-only JSONL file of SMS messages (one JSON object
        per line: received_at, from, to, body) shown in the operator
        window's SMS tab. The PBX never writes to it — point this at the
        store your SMS webhook receiver keeps (Telnyx delivers SMS via
        HTTP API, not the SIP trunk; see docs/decisions for the SMS lane
        rationale). The file must be readable by the telephony group.
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

    fail2ban = {
      enable = lib.mkEnableOption "a fail2ban jail that bans sources of repeated SIP auth failures (scanner resistance for 5060/5080; digest auth stays the real gate — see the runbook's security notes)";

      maxretry = lib.mkOption {
        type = lib.types.ints.positive;
        default = 5;
        description = "SIP auth failures within findtime before the source IP is banned.";
      };

      findtime = lib.mkOption {
        type = lib.types.ints.positive;
        default = 600;
        description = "Seconds within which maxretry failures must occur.";
      };

      bantime = lib.mkOption {
        type = lib.types.ints.positive;
        default = 600;
        description = "Seconds a banned source IP is blocked.";
      };

      nginxScanner = {
        enable = lib.mkOption {
          type = lib.types.bool;
          default = true;
          description = ''
            Also guard the HTTPS surface: an nginx jail bans source IPs
            that repeatedly probe scanner paths (wp-login/phpMyAdmin/.env/
            .git/...) against the webphone vhost. Effective only while
            fail2ban.enable and webphone.enable are both set; shares
            maxretry/findtime/bantime with the SIP jail. Like the SIP
            jail this cuts noise, it is not an access gate — TLS plus
            (where configured) basic auth remain the real doors.
          '';
        };
      };
    };

    monitoring = {
      enable = lib.mkEnableOption "the telephony health-check timer (a failing unit means the PBX is sick: sofia profiles down or gateway registrations lost)";

      intervalSec = lib.mkOption {
        type = lib.types.ints.positive;
        default = 60;
        description = ''
          Seconds between health-check runs (OnUnitActiveSec of the
          telephony-health timer).
        '';
      };

      requireGatewayReg = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Fail the health check when a gateway with register = true is not
          in state REGED. Disable while bringing a new ITSP trunk up.
        '';
      };
    };

    opsTools.enable = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Put the operator tooling baseline on the host shell: system
        monitors (btop, htop), network and SIP diagnostics (dig,
        tcpdump, lsof), JSON and database inspection (jq, sqlite), an
        editor (vim), tmux and openssl. Also enables the flake nix CLI
        (nix-command + flakes) and pins the nixpkgs registry entry to
        the exact nixpkgs source this system was built from, so
        `nix run nixpkgs#<tool>` works on the host for ad-hoc tools.
        Disable for a truly minimal appliance image.
      '';
    };

    backups = {
      enable = lib.mkEnableOption "restic backups of PBX state (voicemail, CDR, recordings) so it is not single-copy on-host";

      repository = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "sftp:u123456@u123456.your-storagebox.de:/backups/pbx";
        description = ''
          restic repository URL (sftp:, rest:, s3:, or a local path for
          tests). Exactly one of repository or repositoryFile when
          backups are enabled. Hetzner Storage Box via sftp is the
          reference off-host target.
        '';
      };

      repositoryFile = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        description = ''
          File containing the repository URL (the *File pair of
          repository, for when even the endpoint should stay out of the
          store).
        '';
      };

      passwordFile = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        description = "File containing the restic repository password (required when backups are enabled).";
      };

      paths = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ "/var/lib/private/freeswitch" ];
        description = ''
          Paths to back up. The default is the real DynamicUser state
          directory — /var/lib/freeswitch is only a symlink there and
          restic archives symlinks as links, not their contents (the
          VM test caught exactly that). The default covers voicemail,
          CDR and call recordings; add your secrets directory (e.g.
          /var/lib/telephony-secrets) in the host config. Hot-copy
          caveat: FreeSWITCH keeps running during the snapshot, so a
          mid-write voicemail DB row is possible; messages are inserted
          atomically (insert_db), so a restore loses at most the last
          moments of one message.
        '';
      };

      calendar = lib.mkOption {
        type = lib.types.str;
        default = "daily";
        description = "systemd calendar expression for the backup timer (OnCalendar).";
      };

      pruneOpts = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
        example = [
          "--keep-daily 7"
          "--keep-weekly 4"
        ];
        description = "restic forget options applied after each backup (empty = keep everything).";
      };
    };

    alerts = {
      url = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        example = "https://hc-ping.com/<uuid>/fail";
        description = ''
          Webhook URL that receives an HTTP POST whenever a supervised
          unit fails (telephony-health, fail2ban, restic-backup-*).
          Any endpoint that accepts a POST body works (healthchecks.io,
          a Slack webhook, ntfy.sh). Set exactly one of url or urlFile.
        '';
      };

      urlFile = lib.mkOption {
        type = lib.types.nullOr lib.types.path;
        default = null;
        description = "File containing the webhook URL (the *File pair of url, for tokens that must stay out of the store).";
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
          Run the webphone (v2 Go service from github:LarsArtmann/webphone,
          wired through its own services.webphone NixOS module) and serve it
          at https://<domain>/ behind the stack's nginx vhost. When the
          webphone misbehaves in the browser, the failure playbook and the
          raw wss probe live in docs/ops-runbook.md.
        '';
      };
      package = lib.mkOption {
        type = lib.types.package;
        description = ''
          Webphone package (the Go binary). The flake's
          nixosModules.telephony defaults this to its webphone input
          (github:LarsArtmann/webphone, the UI's dedicated repo);
          consumers importing the module directly must set it (and import
          the webphone repo's services.webphone module alongside — the
          stack's vhost proxies to that service).
        '';
      };
      phoneApi.enable = lib.mkEnableOption "the per-extension phone API (/phone-api: voicemail list/play/delete, call-detail history); the webphone service proxies the browser island's /phone-api calls to it with the signed-in extension's SIP credentials as Basic auth";

      contacts = lib.mkOption {
        type = lib.types.listOf contactType;
        default = [ ];
        example = [
          {
            name = "Support";
            number = "2000";
          }
        ];
        description = ''
          Shared contacts handed to the webphone (server config plus the
          runtime config.js) with click-to-dial. Personal contacts are
          kept per extension in the webphone's own store alongside these.
        '';
      };

      crm = {
        enable = lib.mkEnableOption "the Ledger CRM integration (panels resolve contact names from the CRM's machine API and the island logs finished calls there); read-only display enrichment — a dead CRM never breaks a page";

        url = lib.mkOption {
          type = lib.types.str;
          default = "";
          example = "http://127.0.0.1:8080";
          description = ''
            Base URL of the CRM machine API (absolute http(s) URL; the
            CRM mounts /api/* behind its API token). Required when
            crm.enable is set.
          '';
        };

        tokenFile = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          example = "/run/secrets/telephony-crm-token";
          description = ''
            Absolute path to a runtime file (sops-nix/agenix-rendered)
            containing the CRM bearer token (single line). Injected as
            WEBPHONE_CRM__TOKEN via the runtime-rendered webphone
            environment file, so the token never lands in the Nix store.
            Required when crm.enable is set.
          '';
        };
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
      tls = {
        enable = lib.mkEnableOption "the TURN-over-TLS/DTLS listener (turns:)";
        port = lib.mkOption {
          type = lib.types.port;
          default = 5349;
          description = "TLS/DTLS listening port (opened in the firewall with openFirewall).";
        };
        certificate = lib.mkOption {
          type = lib.types.str;
          description = ''
            Path to the PEM certificate chain for the turns: listener.
            The file must be readable by the turnserver user (render
            ownership accordingly, like the coturn secret).
          '';
        };
        key = lib.mkOption {
          type = lib.types.str;
          description = "Path to the PEM private key for the turns: listener (turnserver-readable).";
        };
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
