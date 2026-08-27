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
          ;
        xmls = mapAttrsToList (_: directoryXml) tlsEvals;
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
        touch $out
      '';
}
