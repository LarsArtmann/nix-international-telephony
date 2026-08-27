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
        xmls = mapAttrsToList (_: directoryXml) tlsEvals;
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
        touch $out
      '';
}
