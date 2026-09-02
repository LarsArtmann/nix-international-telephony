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
  inherit (pkgs.lib) concatMapStringsSep mapAttrsToList;

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
  ringGroupDidToplevel =
    builtins.unsafeDiscardStringContext ringGroupDidEval.config.system.build.toplevel.drvPath;

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

  # A runtime dial variable as it must appear in the generated XML:
  # single-dollar braces (${dialed_user}), not the doubled pre-processor
  # form. The double-quoted string keeps the escape local and obvious.
  runtimeDialVar = var: "\${${var}}";
  goodNeedle =
    "presence_id=" + runtimeDialVar "dialed_user" + "@" + runtimeDialVar "dialed_domain" + "}";
  badNeedle = "presence_id=$" + runtimeDialVar "dialed_user";
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
        inherit
          placeholderExpects
          candidateAclNeedle
          wssBindingNeedle
          internalXml
          negativeChecks
          ;
        xmls = mapAttrsToList (_: directoryXml) tlsEvals;
        inherit publicDialplanXml ringGroupDidToplevel;
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
        # A DID routed to a ring group must render the public-context transfer.
        grep -F '<action application="transfer" data="2000 XML default"/>' "$publicDialplanXml" > /dev/null || {
          echo "FAIL: public dialplan lost the DID-to-ring-group transfer action"
          exit 1
        }
        touch $out
      '';
}
