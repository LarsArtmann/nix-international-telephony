# Eval-only checks: cheap regression guards that need no VM boot.
#
#   * every tls.mode variant (self-signed/manual/acme) evaluates to a full
#     NixOS configuration — ACME cannot run inside a VM test and manual
#     needs real certificate paths, so wiring is proven by evaluation
#     (fixture: tests/tls-mode-host.nix)
#   * the generated directory dial-string uses single-dollar RUNTIME dial
#     variables exactly like vanilla FreeSWITCH. The over-escaped
#     pre-processor form ($${dialed_user}) breaks every user/N bridge with
#     "No origination URL specified" and, before this check, was only
#     catchable by the browser E2E suite (status report 2026-08-22 §E.4).
#   * the internal profile keeps the WebRTC lifelines: the wss-binding the
#     nginx /sip proxy targets and apply-candidate-acl (without it LAN
#     browsers get 488 INCOMPATIBLE_DESTINATION).
#   * the firewall opens TCP 80 in acme mode (HTTP-01) and no other mode.
#   * the acme-mode order-renew unit carries Restart=on-failure: nixpkgs
#     ships RestartSec=15min without Restart= (dead config), so a failed
#     first-boot order was never retried and the vhost served the minica
#     placeholder for up to a day (deploy 2026-09-16, pbx.artmann.tech).
#   * every *File option yields exactly one @TELEPHONY_*@ placeholder in the
#     generated XML (fixture: tests/file-secrets-host.nix) — the runtime
#     splice depends on the 1:1 token/credential mapping.
#   * setting both sides of a plain/File secret pair (event socket,
#     extension, gateway, TURN) trips the exactly-one-of assertion and
#     blocks the build — the rejection paths, not just the happy paths.
#   * a gateway didDestination may target a ring group: the public-context
#     transfer lands in the default context, where the group answers (the
#     reference assertion used to reject ring-group targets).
{
  nixpkgs,
  pkgs,
  telephonyModule,
}:
let
  inherit (pkgs.lib) concatMapStringsSep mapAttrsToList hasInfix;

  # tests/tls-mode-host.nix carries the shared host (domain, passwords,
  # acmeEmail); each variant only overrides services.telephony.tls.
  evalWith =
    tlsOverride:
    nixpkgs.lib.nixosSystem {
      system = pkgs.stdenv.hostPlatform.system;
      modules = [
        telephonyModule
        (import ./tls-mode-host.nix)
        tlsOverride
      ];
    };

  tlsEvals = {
    self-signed = evalWith { };
    manual = evalWith {
      services.telephony.tls = {
        mode = "manual";
        certificate = "/var/lib/acme/eval.test/fullchain.pem";
        key = "/var/lib/acme/eval.test/key.pem";
      };
    };
    acme = evalWith { services.telephony.tls.mode = "acme"; };
  };

  directoryXml = eval: eval.config.services.freeswitch.configDir."directory/default.xml";

  # All-*File host (plus one plain password for mixed mode) whose generated
  # XML must carry exactly one placeholder per configured file.
  secretsEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./file-secrets-host.nix)
    ];
  };

  secretsXmls = secretsEval.config.services.freeswitch.configDir;

  # Gateway DID routed to a RING GROUP (the shape real deployments want:
  # inbound trunk call rings every desk phone). Must evaluate to a full
  # toplevel and render the transfer action in the public dialplan.
  ringGroupDidEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          extensions."1001".password = "eval";
          ringGroups."2000".members = [
            "1000"
            "1001"
          ];
          gateways.itsp = {
            proxy = "sip.provider.example";
            username = "acct";
            password = "eval";
            did = "441632960961";
            didDestination = "2000";
          };
        };
      }
    ];
  };

  publicDialplanXml = ringGroupDidEval.config.services.freeswitch.configDir."dialplan/public.xml";
  ringGroupDidToplevel = builtins.unsafeDiscardStringContext ringGroupDidEval.config.system.build.toplevel.drvPath;

  # settings.identities derivation: the gateway DID presents for its
  # ring-group destination's every member; with no gateway configured
  # (the plain tls-mode fixtures) the key must be absent entirely.
  identitiesCheck =
    let
      ids = ringGroupDidEval.config.services.webphone.settings.identities or { };
    in
    if
      ids == {
        "1000" = "441632960961";
        "1001" = "441632960961";
      }
    then
      "PASS: identities derive extension -> gateway DID (ring-group members included)"
    else
      "FAIL: identities derivation wrong: ${builtins.toJSON ids}";

  identitiesAbsentCheck =
    if !(tlsEvals.self-signed.config.services.webphone.settings ? identities) then
      "PASS: no gateway configured — identities key absent, app shows no presented number"
    else
      "FAIL: identities leaked into a gateway-less config";

  # CRM happy path (inline TURN secret): settings.crm.url plus the
  # turn_rest/ice_servers wiring must land in services.webphone, the
  # token must ride the env-file seam, and the legacy config.js render
  # unit/timer must be gone.
  crmEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony.webphone.crm = {
          enable = true;
          url = "http://127.0.0.1:8080";
          tokenFile = "/run/secrets/crm-token";
        };
      }
    ];
  };

  crmSettings = crmEval.config.services.webphone.settings;

  crmCheck =
    if
      (crmSettings.crm.url or null) == "http://127.0.0.1:8080"
      && (crmSettings.turn_rest.secret or null) == "eval"
      && builtins.length (crmSettings.ice_servers or [ ]) == 2
      && crmEval.config.services.webphone.environmentFiles == [ "/var/lib/telephony/webphone-env" ]
      && crmEval.config.systemd.services ? telephony-webphone-env
      && !(crmEval.config.systemd.services ? telephony-web-config)
      && !(crmEval.config.systemd.timers ? telephony-web-config)
    then
      "PASS: crm + inline TURN wiring (settings, env file, render unit; legacy shadow gone)"
    else
      "FAIL: crm/TURN wiring incomplete in services.webphone";

  # File-sourced TURN secret: nothing may leak into the store config;
  # the env render unit + environmentFiles carry it instead.
  turnFileEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony.turn = {
          authSecret = nixpkgs.lib.mkForce "";
          authSecretFile = "/run/secrets/turn";
        };
      }
    ];
  };

  turnFileCheck =
    if
      !(turnFileEval.config.services.webphone.settings ? turn_rest)
      && turnFileEval.config.services.webphone.environmentFiles == [ "/var/lib/telephony/webphone-env" ]
      && turnFileEval.config.systemd.services ? telephony-webphone-env
    then
      "PASS: file-sourced TURN secret rides the env file, never settings"
    else
      "FAIL: authSecretFile path leaked into settings or lost the env file";

  # Messaging bridge happy path: the module must render the loopback
  # service with all three credentials mounted, the four nginx locations
  # on the stack vhost, and the JSONL logrotate — from options alone.
  messagingEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony.messaging = {
          enable = true;
          did = "+15550100000";
          gatewaySecretFile = "/run/secrets/gw-secret";
          telnyxApiKeyFile = "/run/secrets/telnyx-key";
          webhookTokenFile = "/run/secrets/webhook-token";
        };
      }
    ];
  };

  messagingUnit = messagingEval.config.systemd.services.telnyx-webhooks;
  messagingLocations =
    builtins.attrNames
      messagingEval.config.services.nginx.virtualHosts."acme.test".locations;

  messagingCheck =
    if
      messagingUnit.environment.FROM_NUMBER == "+15550100000"
      && messagingUnit.environment.WHATSAPP_FROM == ""
      && messagingUnit.environment.PUBLIC_BASE_URL == "https://acme.test"
      && messagingUnit.environment.PORT == "8069"
      && builtins.length messagingUnit.serviceConfig.LoadCredential == 3
      && messagingEval.config.services.logrotate.settings ? telnyx-webhooks
      && builtins.all (location: builtins.elem location messagingLocations) [
        "= /telnyx/webhooks"
        "= /telnyx/webhooks/health"
        "= /telnyx/webhooks/recent"
        "/mms-media/"
      ]
      # Gateway auto-wire: webhook mode, loopback bridge URL and the
      # shared secret FILE derive from messaging options alone.
      && messagingEval.config.services.webphone.settings.gateway ? webhook_secret_file
      && messagingEval.config.services.webphone.settings.gateway.mode == "webhook"
      &&
        messagingEval.config.services.webphone.settings.gateway.webhook_url
        == "http://127.0.0.1:8069/gateway"
      &&
        messagingEval.config.services.webphone.settings.gateway.webhook_secret_file
        == "/run/secrets/gw-secret"
    then
      "PASS: messaging bridge renders service + credentials + vhost locations + logrotate + gateway auto-wire"
    else
      "FAIL: messaging bridge wiring incomplete";

  # WhatsApp lane happy path: enabling it plants the dedicated WhatsApp
  # from-number in the bridge environment. An unverified number is never
  # defaulted from messaging.did — the operator names it explicitly.
  whatsappEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony.messaging = {
          enable = true;
          did = "+15550100000";
          gatewaySecretFile = "/run/secrets/gw-secret";
          telnyxApiKeyFile = "/run/secrets/telnyx-key";
          webhookTokenFile = "/run/secrets/webhook-token";
          whatsapp = {
            enable = true;
            did = "+15550100001";
          };
        };
      }
    ];
  };

  whatsappCheck =
    if
      whatsappEval.config.systemd.services.telnyx-webhooks.environment.WHATSAPP_FROM == "+15550100001"
    then
      "PASS: whatsapp lane plants WHATSAPP_FROM from whatsapp.did (never defaulted)"
    else
      "FAIL: whatsapp.enable did not wire WHATSAPP_FROM";

  # whatsapp.enable without messaging.enable used to be a silent no-op
  # (the whole module sits behind mkIf messaging.enable) — it must warn.
  whatsappNoopEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony.messaging.whatsapp = {
          enable = true;
          did = "+15550100001";
        };
      }
    ];
  };

  whatsappNoopWarnings = builtins.filter (
    warning: builtins.match ".*whatsapp.enable is true but messaging.enable is false.*" warning != null
  ) whatsappNoopEval.config.warnings;

  whatsappNoopCheck =
    if builtins.length whatsappNoopWarnings == 1 then
      "PASS: whatsapp.enable without messaging.enable warns (no silent no-op)"
    else
      "FAIL: whatsapp-without-messaging warning missing or duplicated";

  # Operator SMS store derived default: with messaging enabled and the
  # option left unset, the operator must read the bridge's JSONL through
  # the collision-free ro bind (never the unwalkable private path —
  # os.path.exists reports False on EACCES), carry the group-ACL heal
  # unit, and order after the bridge. Guards the three-layer access
  # pattern the same way the VM operator suite guards freeswitch-ro.
  smsStoreEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          messaging = {
            enable = true;
            did = "+15550100000";
            gatewaySecretFile = "/run/secrets/gw-secret";
            telnyxApiKeyFile = "/run/secrets/telnyx-key";
            webhookTokenFile = "/run/secrets/webhook-token";
          };
          operator = {
            enable = true;
            apiPasswordFile = "/run/secrets/operator-password";
          };
        };
      }
    ];
  };

  smsStoreCfg = smsStoreEval.config.services.telephony;
  smsOperatorUnit = smsStoreEval.config.systemd.services.telephony-operator;
  smsStoreExecStart = toString smsOperatorUnit.serviceConfig.ExecStart;

  smsStoreCheck =
    if
      smsStoreCfg.operator.smsMessageStore == "/var/lib/telnyx-webhooks/inbound.jsonl"
      &&
        builtins.match ".*--sms-store '?/var/lib/telephony/telnyx-webhooks-ro/inbound.jsonl'?.*" smsStoreExecStart
        != null
      && builtins.elem "/var/lib/private/telnyx-webhooks:/var/lib/telephony/telnyx-webhooks-ro" (
        smsOperatorUnit.serviceConfig.BindReadOnlyPaths or [ ]
      )
      && builtins.elem "telnyx-webhooks.service" smsOperatorUnit.after
      && smsStoreEval.config.systemd.services ? telephony-sms-store-acl
    then
      "PASS: derived smsMessageStore reads the bridge JSONL via ro bind + ACL unit + ordering"
    else
      "FAIL: derived operator.smsMessageStore access wiring incomplete";

  # Shared htpasswd single-writer invariant (2026-10-07 race fix): when
  # the operator API runs (operator.enable OR webphone.phoneApi.enable)
  # telephony-operator-auth is the ONLY unit that may write the shared
  # recordings.htpasswd; telephony-recordings-auth exists only when the
  # API is off entirely. Two un-ordered oneshots truncate-writing the
  # same file let boot order decide which basic-auth surface loses its
  # login.
  htpasswdRaceEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          recording = {
            enable = true;
            serve = {
              enable = true;
              basicAuthPasswordFile = "/run/secrets/recordings-password";
            };
          };
          operator = {
            enable = true;
            apiPasswordFile = "/run/secrets/operator-password";
          };
        };
      }
    ];
  };

  htpasswdRaceServices = htpasswdRaceEval.config.systemd.services;

  htpasswdSoloEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          recording = {
            enable = true;
            serve = {
              enable = true;
              basicAuthPasswordFile = "/run/secrets/recordings-password";
            };
          };
          webphone.phoneApi.enable = false;
        };
      }
    ];
  };

  htpasswdSoloServices = htpasswdSoloEval.config.systemd.services;

  htpasswdWriterCheck =
    if
      htpasswdRaceServices ? telephony-operator-auth
      && !(htpasswdRaceServices ? telephony-recordings-auth)
      && htpasswdSoloServices ? telephony-recordings-auth
      && !(htpasswdSoloServices ? telephony-operator-auth)
    then
      "PASS: shared htpasswd has exactly one writer in both API modes"
    else
      "FAIL: recordings/operator auth units violate the single-writer rule";

  # Forward-auth mode (2026-10-12): surfaces with authMode = "forwardAuth"
  # render no htpasswd line — with BOTH surfaces forwarded the recordings
  # unit is absent entirely and the operator unit (still required for the
  # ESL password + stream-token secrets) exists without being a htpasswd
  # writer. Runtime proof (302/403/200 + loopback break-glass + no
  # htpasswd on disk) lives in tests/forward-auth.nix; this is the
  # unit-shape matrix.
  forwardAuthEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          recording.serve = {
            enable = true;
            authMode = "forwardAuth";
            forwardAuth = {
              authUrl = "http://127.0.0.1:4181/gate/recordings/oauth2/auth";
              signInUrl = "https://sso.example.test/gate/recordings/oauth2/start?rd=";
            };
          };
          operator = {
            enable = true;
            authMode = "forwardAuth";
            forwardAuth = {
              authUrl = "http://127.0.0.1:4182/gate/operator/oauth2/auth";
              signInUrl = "https://sso.example.test/gate/operator/oauth2/start?rd=";
            };
          };
        };
      }
    ];
  };

  forwardAuthServices = forwardAuthEval.config.systemd.services;

  forwardAuthCheck =
    if
      !(forwardAuthServices ? telephony-recordings-auth) && forwardAuthServices ? telephony-operator-auth
    then
      "PASS: forwardAuth surfaces keep the single-writer rule with zero htpasswd writers"
    else
      "FAIL: forwardAuth surfaces must drop recordings-auth and keep operator-auth (ESL/stream secrets)";

  # Mixed mode (recordings basic + operator forwardAuth): operator-auth
  # stays the single writer and now renders ONLY the recordings line.
  forwardAuthMixedEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          recording.serve = {
            enable = true;
            basicAuthPasswordFile = "/run/secrets/recordings-password";
          };
          operator = {
            enable = true;
            authMode = "forwardAuth";
            forwardAuth = {
              authUrl = "http://127.0.0.1:4182/gate/operator/oauth2/auth";
              signInUrl = "https://sso.example.test/gate/operator/oauth2/start?rd=";
            };
          };
        };
      }
    ];
  };

  forwardAuthMixedServices = forwardAuthMixedEval.config.systemd.services;

  forwardAuthMixedCheck =
    if
      !(forwardAuthMixedServices ? telephony-recordings-auth)
      && forwardAuthMixedServices ? telephony-operator-auth
    then
      "PASS: mixed mode (recordings basic + operator forwardAuth) keeps telephony-operator-auth as the single writer"
    else
      "FAIL: mixed mode lost the single-writer rule";

  # file<TAB>needle<TAB>expectedCount — one line per *File option.
  placeholderExpects = concatMapStringsSep "\n" (e: "${e.file}\t${e.needle}\t${toString e.count}") [
    {
      file = "directory/default.xml";
      needle = "@TELEPHONY_EXT_1000_PASSWORD@";
      count = 1;
    }
    {
      file = "directory/default.xml";
      needle = "@TELEPHONY_EXT_1001_PASSWORD@";
      count = 0;
    }
    {
      file = "autoload_configs/event_socket.conf.xml";
      needle = "@TELEPHONY_EVENT_SOCKET_PASSWORD@";
      count = 1;
    }
    {
      file = "sip_profiles/external.xml";
      needle = "@TELEPHONY_GW_ITSP_PASSWORD@";
      count = 1;
    }
  ];

  # WebRTC lifelines of the internal profile (regressions of either were
  # VM/browser-debugging sessions; see AGENTS.md).
  candidateAclNeedle = ''<param name="apply-candidate-acl" value="localnet.auto"/>'';
  wssBindingNeedle = ''<param name="wss-binding" value="127.0.0.1:7443"/>'';
  internalXml = tlsEvals.self-signed.config.services.freeswitch.configDir."sip_profiles/internal.xml";

  # Negative evals: setting BOTH sides of a plain/File secret pair must
  # produce the module's exactly-one-of assertion AND block the toplevel
  # build. `fires` inspects config.assertions directly (so a broken eval
  # cannot masquerade as a fired assertion); `blocks` proves NixOS refuses
  # to build the configuration.
  negativeHost =
    extra:
    nixpkgs.lib.nixosSystem {
      system = pkgs.stdenv.hostPlatform.system;
      modules = [
        telephonyModule
        (import ./tls-mode-host.nix)
        extra
      ];
    };

  bothSet =
    {
      name,
      extra,
      message,
    }:
    let
      ev = negativeHost extra;
      fires = builtins.any (
        a: !a.assertion && builtins.match ".*${message}.*" a.message != null
      ) ev.config.assertions;
      blocks = !(builtins.tryEval ev.config.system.build.toplevel.drvPath).success;
    in
    "${name}: ${
      if fires && blocks then "PASS" else "FAIL (fires=${toString fires} blocks=${toString blocks})"
    }";

  negativeChecks = concatMapStringsSep "\n" bothSet [
    {
      name = "eventSocket";
      extra = {
        services.telephony.eventSocketPasswordFile = "/run/secrets/es";
      };
      message = "set exactly one of eventSocketPassword or eventSocketPasswordFile";
    }
    {
      name = "extension";
      extra = {
        services.telephony.extensions."1000".passwordFile = "/run/secrets/ext";
      };
      message = "each extension must set exactly one of password or passwordFile";
    }
    {
      name = "gateway";
      extra = {
        services.telephony.gateways.itsp = {
          proxy = "sip.provider.example";
          username = "acct";
          password = "plain";
          passwordFile = "/run/secrets/gw";
          did = "441632960961";
          didDestination = "1000";
        };
      };
      message = "each gateway must set exactly one of password or passwordFile";
    }
    {
      name = "turn";
      extra = {
        services.telephony.turn.authSecretFile = "/run/secrets/turn";
      };
      message = "set exactly one of authSecret or authSecretFile when turn is enabled";
    }
    {
      name = "crm";
      extra = {
        services.telephony.webphone.crm.enable = true;
      };
      message = "set both url and tokenFile when crm is enabled";
    }
    {
      name = "messaging";
      extra = {
        services.telephony.messaging = {
          enable = true;
          did = "+15550100000";
        };
      };
      message = "gatewaySecretFile is required when messaging is enabled";
    }
    {
      name = "messaging-gateway-inline-secret";
      extra = {
        services.telephony.messaging = {
          enable = true;
          did = "+15550100000";
          gatewaySecretFile = "/run/secrets/gw-secret";
          telnyxApiKeyFile = "/run/secrets/telnyx-key";
          webhookTokenFile = "/run/secrets/webhook-token";
        };
        services.webphone.settings.gateway.webhook_secret = "inline-secret";
      };
      message = "the messaging bridge wires webhook_secret_file from services.telephony.messaging.gatewaySecretFile";
    }
    {
      name = "whatsapp";
      extra = {
        services.telephony.messaging = {
          enable = true;
          did = "+15550100000";
          gatewaySecretFile = "/run/secrets/gw-secret";
          telnyxApiKeyFile = "/run/secrets/telnyx-key";
          webhookTokenFile = "/run/secrets/webhook-token";
          whatsapp.enable = true;
        };
      };
      message = "whatsapp.did must be set when messaging.whatsapp.enable is true";
    }
    {
      name = "agent-prompt";
      extra = {
        services.telephony.agent = {
          enable = true;
          apiKeyFile = "/run/secrets/gemini-key";
        };
      };
      message = "systemPromptFile is required when agent is enabled";
    }
    {
      name = "agent-key";
      extra = {
        services.telephony.agent = {
          enable = true;
          systemPromptFile = "/run/secrets/agent-prompt";
        };
      };
      message = "apiKeyFile is required when agent is enabled";
    }
    {
      name = "agent-recording";
      extra = {
        services.telephony.agent = {
          enable = true;
          systemPromptFile = "/run/secrets/agent-prompt";
          apiKeyFile = "/run/secrets/gemini-key";
        };
        services.telephony.recording.enable = false;
      };
      message = "agent requires recording.enable";
    }
    {
      name = "agent-answerdid";
      extra = {
        services.telephony.agent = {
          enable = true;
          systemPromptFile = "/run/secrets/agent-prompt";
          apiKeyFile = "/run/secrets/gemini-key";
          answerDids = [ "440000000000" ];
        };
      };
      message = "every DID must be the did of a configured gateway";
    }
    {
      name = "textagent-without-messaging";
      extra = {
        services.telephony.textagent = {
          enable = true;
          apiKeyFile = "/run/secrets/gemini-key";
          systemPromptFile = "/run/secrets/textagent-prompt";
          sharedSecretFile = "/run/secrets/textagent-secret";
        };
      };
      message = "services.telephony.textagent requires messaging.enable";
    }
    {
      name = "textagent-prompt";
      extra = {
        services.telephony = {
          messaging.enable = true;
          textagent = {
            enable = true;
            apiKeyFile = "/run/secrets/gemini-key";
            sharedSecretFile = "/run/secrets/textagent-secret";
          };
        };
      };
      message = "systemPromptFile is required when textagent is enabled";
    }
    {
      name = "textagent-key";
      extra = {
        services.telephony = {
          messaging.enable = true;
          textagent = {
            enable = true;
            systemPromptFile = "/run/secrets/textagent-prompt";
            sharedSecretFile = "/run/secrets/textagent-secret";
          };
        };
      };
      message = "apiKeyFile is required when textagent is enabled";
    }
    {
      name = "textagent-secret";
      extra = {
        services.telephony = {
          messaging.enable = true;
          textagent = {
            enable = true;
            apiKeyFile = "/run/secrets/gemini-key";
            systemPromptFile = "/run/secrets/textagent-prompt";
          };
        };
      };
      message = "sharedSecretFile is required when textagent is enabled";
    }
    {
      name = "textagent-briefing-mailer";
      extra = {
        services.telephony = {
          messaging.enable = true;
          textagent = {
            enable = true;
            apiKeyFile = "/run/secrets/gemini-key";
            systemPromptFile = "/run/secrets/textagent-prompt";
            sharedSecretFile = "/run/secrets/textagent-secret";
            briefing.mailerCommand = pkgs.msmtp;
          };
        };
      };
      message = "a mailerCommand needs fromAddress and toAddress";
    }
  ];

  # Firewall port policy per tls.mode: ACME's HTTP-01 challenge needs
  # TCP 80 open; other modes must not open it (smallest surface).
  tcpPorts = builtins.map (mode: {
    inherit mode;
    ports = tlsEvals.${mode}.config.networking.firewall.allowedTCPPorts;
  }) (builtins.attrNames tlsEvals);

  portCheck =
    if
      (builtins.elem 80 (builtins.head (builtins.filter (p: p.mode == "acme") tcpPorts)).ports)
      && !(builtins.any (p: p.mode != "acme" && builtins.elem 80 p.ports) tcpPorts)
    then
      "PASS: tcp/80 open only in acme mode"
    else
      "FAIL: tcp/80 must be open in acme mode and closed in every other tls.mode";

  # Our Restart=on-failure override must survive module refactors: without
  # it one failed order means a day of self-signed placeholder.
  acmeRestart =
    tlsEvals.acme.config.systemd.services."acme-order-renew-acme.test".serviceConfig.Restart
      or "MISSING";

  # A runtime dial variable as it must appear in the generated XML:
  # single-dollar braces (${dialed_user}), not the doubled pre-processor
  # form. The double-quoted string keeps the escape local and obvious.
  runtimeDialVar = var: "\${${var}}";
  goodNeedle =
    "presence_id=" + runtimeDialVar "dialed_user" + "@" + runtimeDialVar "dialed_domain" + "}";
  badNeedle = "presence_id=$" + runtimeDialVar "dialed_user";

  # fail2ban filter texts, straight from a full module eval (single
  # source of truth: the check fails if the module ever stops emitting
  # the filters or a regex edit stops matching the canned attack lines).
  fail2banEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony.fail2ban = {
          enable = true;
          nginxScanner.enable = true;
        };
        services.telephony.webphone.enable = true;
      }
    ];
  };

  sipFilterText = fail2banEval.config.environment.etc."fail2ban/filter.d/freeswitch-sip.conf".text;
  nginxScannerFilterText =
    fail2banEval.config.environment.etc."fail2ban/filter.d/telephony-nginx-scanner.conf".text;

  # AI voice agent happy path: the loopback service must render the
  # Gemini seam (credential mounts, model env, recordings-dir access),
  # the dialplan must answer + record + park the agent extension, and
  # the DID interception must beat the gateway didDestination (with the
  # accountcode stamp so the call stays visible in the webphone History).
  agentEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          extensions."1001".password = "eval";
          ringGroups."2000".members = [ "1001" ];
          gateways.itsp = {
            proxy = "sip.provider.example";
            username = "acct";
            password = "eval";
            did = "441632960961";
            didDestination = "2000";
          };
          agent = {
            enable = true;
            answerDids = [ "441632960961" ];
            extension = "9100";
            accountcode = "1001";
            systemPromptFile = "/run/secrets/agent-prompt";
            apiKeyFile = "/run/secrets/gemini-key";
            transferDestination = "2000";
            languageByDid."441632960961" = "de-DE";
            greetingByDid."441632960961" = "Guten Tag";
          };
        };
      }
    ];
  };

  agentUnit = agentEval.config.systemd.services.telephony-agent;
  agentDefaultXml = agentEval.config.services.freeswitch.configDir."dialplan/default.xml";
  agentPublicXml = agentEval.config.services.freeswitch.configDir."dialplan/public.xml";
  # Eval-pure content (the configDir value is a coerced store path whose
  # text is only readable after a build; readFile here broke every
  # --no-build check run with an IFD demand).
  agentPublicText = agentEval.config.services.telephony.generatedPublicDialplan;

  agentCheck =
    if
      agentUnit.environment.GEMINI_LLM_MODEL == "gemini-3.8-flash"
      && agentUnit.environment.GEMINI_TTS_MODEL == "gemini-3.8-flash-lite-tts"
      && agentUnit.environment.GEMINI_VOICE == "Kore"
      && agentUnit.environment.AGENT_TRANSFER_DESTINATION == "2000"
      && agentUnit.environment.AGENT_TURNS_DIR == "/var/lib/telephony/recordings/ai-turns"
      && agentUnit.environment.HTTP_PORT == "8070"
      && agentUnit.environment.AGENT_LANGUAGES_BY_DID == "{\"441632960961\":\"de-DE\"}"
      && agentUnit.environment.AGENT_GREETINGS_BY_DID == "{\"441632960961\":\"Guten Tag\"}"
      && hasInfix "ai_agent_did=441632960961" agentPublicText
      && hasInfix "ai_agent_lang=de-DE" agentPublicText
      && builtins.any (c: builtins.match "gemini_key:.*" c != null) agentUnit.serviceConfig.LoadCredential
      && builtins.any (
        c: builtins.match "system_prompt:.*" c != null
      ) agentUnit.serviceConfig.LoadCredential
      && builtins.elem "telephony" agentUnit.serviceConfig.SupplementaryGroups
      && builtins.elem "/var/lib/telephony/recordings" agentUnit.serviceConfig.ReadWritePaths
      && builtins.any (
        rule: builtins.match ".*recordings/ai-turns.*" rule != null
      ) agentEval.config.systemd.tmpfiles.rules
      && builtins.any (
        rule: builtins.match ".*recordings/transcripts.*" rule != null
      ) agentEval.config.systemd.tmpfiles.rules
    then
      "PASS: agent service wiring (Gemini credentials + env, recordings access, turn/transcript dirs)"
    else
      "FAIL: agent service wiring incomplete";

  # pbx-lens happy path: CDR ingest rides the operator's three-layer
  # FS-state read path (ro bind + telephony-fs group + ACL ordering),
  # and the module registers its state for the stack backups; with no
  # cdrFile none of the FS access wiring may appear (smallest surface).
  lensEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          cdr.enable = true;
          pbx-lens = {
            enable = true;
            cdrFile = "/var/lib/telephony/freeswitch-ro/cdr-csv/Master.csv";
          };
        };
      }
    ];
  };

  lensUnit = lensEval.config.systemd.services.pbx-lens;
  lensCheck =
    let
      noCdrEval = nixpkgs.lib.nixosSystem {
        system = pkgs.stdenv.hostPlatform.system;
        modules = [
          telephonyModule
          (import ./tls-mode-host.nix)
          { services.telephony.pbx-lens.enable = true; }
        ];
      };
      noCdrSvc = noCdrEval.config.systemd.services.pbx-lens.serviceConfig;
    in
    if
      builtins.elem "telephony-fs" lensUnit.serviceConfig.SupplementaryGroups
      && builtins.elem "/var/lib/private/freeswitch:/var/lib/telephony/freeswitch-ro" (
        lensUnit.serviceConfig.BindReadOnlyPaths or [ ]
      )
      && builtins.elem "telephony-fs-state-acl.service" lensUnit.after
      && lensEval.config.systemd.services ? telephony-fs-state-acl
      && builtins.elem "/var/lib/pbx-lens/backups" lensEval.config.services.telephony.state.paths
      && builtins.elem "/var/lib/pbx-lens/index.db" lensEval.config.services.telephony.state.sqliteDatabases
      # Bare lens (no cdrFile): the FS-specific access wiring must be
      # absent — other groups (webphone's `telephony`) may legitimately
      # remain.
      && !builtins.elem "telephony-fs" (noCdrSvc.SupplementaryGroups or [ ])
      && !builtins.elem "/var/lib/private/freeswitch:/var/lib/telephony/freeswitch-ro" (
        noCdrSvc.BindReadOnlyPaths or [ ]
      )
    then
      "PASS: lens CDR read path (bind+group+ACL ordering) and state.* registration; bare lens stays surface-minimal"
    else
      "FAIL: lens access wiring or state registration incomplete";

  # Text agent happy path: the loopback service renders all five
  # credentials (Gemini + prompt + shared secret + the bridge's gateway
  # secret + ESL), reaches the bridge JSONL through the module-owned
  # three-layer path (ro bind + telephony-fs + ACL ordering), keeps the
  # review API loopback-derived for the webphone auto-wire, and
  # registers its state for the stack backups. Bare textagent (without
  # the voice agent) must NOT claim the transcripts group.
  textagentEval = nixpkgs.lib.nixosSystem {
    system = pkgs.stdenv.hostPlatform.system;
    modules = [
      telephonyModule
      (import ./tls-mode-host.nix)
      {
        services.telephony = {
          messaging = {
            enable = true;
            did = "+15550100000";
            gatewaySecretFile = "/run/secrets/gw-secret";
            telnyxApiKeyFile = "/run/secrets/telnyx-key";
            webhookTokenFile = "/run/secrets/webhook-token";
          };
          textagent = {
            enable = true;
            apiKeyFile = "/run/secrets/gemini-key";
            systemPromptFile = "/run/secrets/textagent-prompt";
            sharedSecretFile = "/run/secrets/textagent-secret";
            ownerName = "Eval Owner";
            missedCall.enable = true;
            autopilot = {
              mode = "after-hours";
              confidenceThreshold = 75;
            };
            vipNumbers = [ "+15550109999" ];
          };
        };
      }
    ];
  };

  textagentUnit = textagentEval.config.systemd.services.telephony-textagent;

  textagentCheck =
    let
      creds = textagentUnit.serviceConfig.LoadCredential;
    in
    if
      textagentUnit.environment.HTTP_PORT == "8071"
      && textagentUnit.environment.TEXTAGENT_MODE == "after-hours"
      && textagentUnit.environment.TEXTAGENT_CONFIDENCE_THRESHOLD == "75"
      && textagentUnit.environment.TEXTAGENT_OWNER_NAME == "Eval Owner"
      && textagentUnit.environment.TEXTAGENT_VIP == "+15550109999"
      && textagentUnit.environment.TEXTAGENT_MISSED_CALL == "1"
      && textagentUnit.environment.TEXTAGENT_WEBHOOK_LOG
        == "/var/lib/telephony/telnyx-webhooks-ro/inbound.jsonl"
      && textagentUnit.environment.TEXTAGENT_BRIDGE_URL == "http://127.0.0.1:8069/gateway"
      && textagentUnit.environment.TEXTAGENT_OWN_DID == "+15550100000"
      # The tls-mode-host fixture uses the inline event-socket password,
      # so the ESL secret rides ESL_PASSWORD, not a fifth credential —
      # the four file-backed secrets are the deploy posture.
      && builtins.length creds == 4
      && builtins.any (c: builtins.match "shared_secret:.*" c != null) creds
      && builtins.any (c: builtins.match "gateway_secret:.*" c != null) creds
      && textagentUnit.environment.ESL_PASSWORD == "eval"
      && builtins.elem "telephony-fs" textagentUnit.serviceConfig.SupplementaryGroups
      && builtins.elem "/var/lib/private/telnyx-webhooks:/var/lib/telephony/telnyx-webhooks-ro" (
        textagentUnit.serviceConfig.BindReadOnlyPaths or [ ]
      )
      && builtins.elem "telephony-sms-store-acl.service" textagentUnit.after
      && textagentEval.config.systemd.services ? telephony-sms-store-acl
      && !builtins.elem "telephony" textagentUnit.serviceConfig.SupplementaryGroups
      && builtins.elem "/var/lib/telephony-textagent" textagentEval.config.services.telephony.state.paths
      # Webphone review surfaces auto-wire from the module (URL + the
      # SAME secret file the review API authenticates).
      && textagentEval.config.services.webphone.settings.textagent.url
        == "http://127.0.0.1:8071"
      && textagentEval.config.services.webphone.settings.textagent.secret_file
        == "/run/secrets/textagent-secret"
    then
      "PASS: textagent service wiring (credentials, JSONL read path, webphone auto-wire, state registration)"
    else
      "FAIL: textagent service wiring incomplete";

  # FreeSWITCH module-mirror drift: forcing this string resolves every
  # entry of modules/telephony/freeswitch-modules.nix (the ONE home
  # pbx.nix's override consumes) against nixpkgs' module universe. The
  # `modules` override replaces nixpkgs' default set wholesale, so an
  # upstream rename/removal would otherwise fail a freeswitch BUILD deep
  # inside a VM suite; here the stale entry fails the whole check at EVAL
  # in seconds as "attribute '<name>' missing at freeswitch-modules.nix:
  # <line>" — precise by construction, because Nix 2.34 routes
  # attribute-missing OUTSIDE tryEval (verified 2026-10-12: tryEval catches
  # throw, not attr-missing), so the error always names the file and line.
  # Forcing stays WHNF-level: map (m: m.path) touches the plain `path`
  # string of each module record and nothing deeper (`.inputs` would pull
  # package derivations and their stdenv bootstrap — a pure-eval stack
  # overflow, not a verdict).
  fsModuleMirrorNeedle =
    let
      # The PRISTINE nixpkgs set, not the flake's overlaid perSystem pkgs:
      # the universe is exactly what nixpkgs' own callPackage sees, and
      # the overlay chain can recurse under these fixed-point lookups.
      pristine = nixpkgs.legacyPackages.${pkgs.system};
      # Supply whatever the pinned modules.nix requires — the same
      # auto-fill callPackage performs inside nixpkgs — instead of
      # hand-listing its argument names (they drift across nixpkgs
      # bumps; an unknown name fails loudly right here).
      modulesExpr = import (pristine.path + "/pkgs/by-name/fr/freeswitch/modules.nix");
      universe = modulesExpr (
        builtins.mapAttrs (name: _: pristine.${name}) (builtins.functionArgs modulesExpr)
      );
    in
    builtins.concatStringsSep "," (
      map (m: m.path) (
        import ../modules/telephony/freeswitch-modules.nix {
          inherit (nixpkgs) lib;
          isLinux = true;
          mods = universe;
        }
      )
    );
in
{
  telephony-eval =
    pkgs.runCommand "telephony-eval"
      {
        meta.description = "Eval-only regressions: TLS modes evaluate; dial-string keeps runtime dial variables";
        # Forcing these derivation paths at flake-evaluation time is the
        # actual TLS-mode check: a module change that breaks any mode fails
        # here. They are plain strings, so nothing builds the full systems;
        # the context is discarded so `nix flake check --no-build` (and
        # --all-systems) does not demand the foreign-arch drvs be valid.
        toplevels = concatMapStringsSep " " (
          mode: builtins.unsafeDiscardStringContext tlsEvals.${mode}.config.system.build.toplevel.drvPath
        ) (builtins.attrNames tlsEvals);
        inherit goodNeedle badNeedle portCheck;
        inherit acmeRestart;
        inherit
          placeholderExpects
          candidateAclNeedle
          wssBindingNeedle
          internalXml
          negativeChecks
          crmCheck
          turnFileCheck
          messagingCheck
          whatsappCheck
          whatsappNoopCheck
          identitiesCheck
          identitiesAbsentCheck
          smsStoreCheck
          htpasswdWriterCheck
          forwardAuthCheck
          forwardAuthMixedCheck
          agentCheck
          lensCheck
          textagentCheck
          fsModuleMirrorNeedle
          ;
        xmls = mapAttrsToList (_: directoryXml) tlsEvals;
        inherit publicDialplanXml ringGroupDidToplevel;
        inherit agentDefaultXml agentPublicXml;
        secretsDirXml = secretsXmls."directory/default.xml";
        secretsEsXml = secretsXmls."autoload_configs/event_socket.conf.xml";
        secretsExtXml = secretsXmls."sip_profiles/external.xml";
      }
      ''
        for xml in $xmls; do
          grep -F "$goodNeedle" "$xml" > /dev/null || {
            echo "FAIL: $xml: dial-string lost its single-dollar runtime dial variables"
            exit 1
          }
          if grep -F "$badNeedle" "$xml" > /dev/null; then
            echo "FAIL: $xml: dial-string uses the over-escaped pre-processor form"
            exit 1
          fi
        done
        case "$portCheck" in
          PASS*) ;;
          *) echo "$portCheck"; exit 1 ;;
        esac
        if [ "$acmeRestart" != "on-failure" ]; then
          echo "FAIL: acme order-renew unit lost Restart=on-failure (got: $acmeRestart)"
          exit 1
        fi
        # WebRTC lifelines: wss proxy hop + ICE candidate screening.
        for needle in "$wssBindingNeedle" "$candidateAclNeedle"; do
          grep -F "$needle" "$internalXml" > /dev/null || {
            echo "FAIL: internal profile lost: $needle"
            exit 1
          }
        done
        # One placeholder per configured *File option, substituted at start.
        while IFS=$'\t' read -r file needle count; do
          case "$file" in
            directory*) xml="$secretsDirXml" ;;
            *event_socket*) xml="$secretsEsXml" ;;
            *external*) xml="$secretsExtXml" ;;
          esac
          actual=$(grep -c -F "$needle" "$xml" || true)
          if [ "$actual" != "$count" ]; then
            echo "FAIL: $file: expected $count occurrence(s) of $needle, found $actual"
            exit 1
          fi
        done <<< "$placeholderExpects"
        # Both-set secret pairs must be rejected (assertion fires + build blocks).
        if grep -q 'FAIL' <<< "$negativeChecks"; then
          echo "$negativeChecks"
          exit 1
        fi
        # CRM + file-sourced TURN + messaging + whatsapp + identities + agent + lens wiring must land in the config.
        for check in "$crmCheck" "$turnFileCheck" "$messagingCheck" "$whatsappCheck" "$whatsappNoopCheck" "$identitiesCheck" "$identitiesAbsentCheck" "$smsStoreCheck" "$htpasswdWriterCheck" "$forwardAuthCheck" "$forwardAuthMixedCheck" "$agentCheck" "$lensCheck" "$textagentCheck"; do
          case "$check" in
            PASS*) ;;
            *) echo "$check"; exit 1 ;;
          esac
        done
        # Module-mirror drift: the resolved path list (eval fails entirely
        # on a stale entry) must still carry mod_xml_curl — the module the
        # dynamic directory bridge is FOR.
        case "$fsModuleMirrorNeedle" in
          *xml_int/mod_xml_curl*) ;;
          *)
            echo "FAIL: freeswitch module mirror lost xml_int.curl (mod_xml_curl)"
            exit 1
            ;;
        esac
        # A DID routed to a ring group must render the public-context transfer.
        grep -F '<action application="transfer" data="2000 XML default"/>' "$publicDialplanXml" > /dev/null || {
          echo "FAIL: public dialplan lost the DID-to-ring-group transfer action"
          exit 1
        }
        # Agent dialplan: answer + record + park on the agent extension.
        for needle in 'expression="^9100$"' 'data="ai_agent=1"' 'application="park"' '_ai_agent.wav'; do
          grep -F "$needle" "$agentDefaultXml" > /dev/null || {
            echo "FAIL: default dialplan lost an agent needle: $needle"
            exit 1
          }
        done
        # DID interception (the agent answers the DID, not the ring
        # group) plus the accountcode stamp that keeps the call visible
        # in the per-extension phone API.
        grep -F '<action application="transfer" data="9100 XML default"/>' "$agentPublicXml" > /dev/null || {
          echo "FAIL: public dialplan did not intercept the agent DID"
          exit 1
        }
        grep -F '<action application="set" data="accountcode=1001"/>' "$agentPublicXml" > /dev/null || {
          echo "FAIL: agent DID lost its accountcode stamp"
          exit 1
        }
        touch $out
      '';

  # Eval-time fail2ban-regex check: runs the REAL fail2ban-regex binary
  # over canned attack/benign log lines against the filters the module
  # ships. Guards the date-strip trap (nginx filter must not span the
  # [timestamp]) and the sofia line shape in seconds instead of a full
  # VM suite (tests/fail2ban.nix stays the end-to-end proof).
  telephony-failregex =
    pkgs.runCommand "telephony-failregex"
      {
        nativeBuildInputs = [ pkgs.fail2ban ];
        meta.description = "fail2ban-regex over canned lines: module filters still match attacks and spare benign lines";
        sipFilter = sipFilterText;
        nginxScannerFilter = nginxScannerFilterText;
      }
      ''
        set -eu
        dir="$(mktemp -d)"
        printf '%s\n' "$sipFilter" > "$dir/sip.conf"
        printf '%s\n' "$nginxScannerFilter" > "$dir/nginx-scanner.conf"

        # FreeSWITCH journal lines (source-verified sofia_reg.c shape):
        # two attacks (REGISTER + INVITE), one benign registration.
        cat > "$dir/sip.log" <<'LOGS'
        2026-09-29T12:00:00.000000 [WARNING] sofia_reg.c:1792 SIP auth failure (REGISTER) on sofia profile 'internal' for [1000@test] from ip 198.51.100.7
        2026-09-29T12:00:00.500000 [WARNING] sofia_reg.c:1792 SIP auth failure (INVITE) on sofia profile 'external' for [1001@test] from ip 198.51.100.7
        2026-09-29T12:00:01.000000 [NOTICE] sofia_reg.c:1757 Registering 1000@test from ip 198.51.100.7
        LOGS

        # nginx combined-format lines: two scanner probes, one 200 on a
        # scanner path (must NOT count), one benign 404 (must NOT count).
        cat > "$dir/nginx.log" <<'LOGS'
        198.51.100.8 - - [29/Sep/2026:12:00:00 +0000] "GET /wp-login.php HTTP/1.1" 404 153 "-" "curl/8.0"
        198.51.100.8 - - [29/Sep/2026:12:00:01 +0000] "POST /xmlrpc.php HTTP/1.1" 405 157 "-" "curl/8.0"
        198.51.100.8 - - [29/Sep/2026:12:00:02 +0000] "GET /wp-login.php HTTP/1.1" 200 153 "-" "curl/8.0"
        198.51.100.9 - - [29/Sep/2026:12:00:03 +0000] "GET /assets/app.js HTTP/1.1" 404 153 "-" "Mozilla/5.0"
        LOGS

        expect_lines() {
          log="$1"; filter="$2"; want="$3"
          got="$(fail2ban-regex "$dir/$log" "$dir/$filter" 2>&1 | grep -E '^Lines:' || true)"
          case "$got" in
            "Lines: $want") ;;
            *)
              echo "FAIL: $filter no longer matches the canned lines exactly."
              echo "  expected summary: Lines: $want"
              echo "  got: $got"
              fail2ban-regex "$dir/$log" "$dir/$filter" 2>&1 | sed 's/^/  /'
              exit 1
              ;;
          esac
        }

        expect_lines sip.log sip.conf "3 lines, 0 ignored, 2 matched, 1 missed"
        expect_lines nginx.log nginx-scanner.conf "4 lines, 0 ignored, 2 matched, 2 missed"
        touch "$out"
      '';
}
