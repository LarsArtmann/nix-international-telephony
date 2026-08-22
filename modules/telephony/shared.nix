# Derived values shared by the services.telephony wiring parts
# (pbx.nix, web.nix) and the assertions in default.nix.
#
# This file is a plain function, not a NixOS module: it folds the
# option-level config into the shapes the wiring consumes and owns the
# runtime paths shared across concerns (recordings are written by
# FreeSWITCH and served by nginx).
{
  config,
  lib,
  ...
}:
let
  cfg = config.services.telephony;
in
{
  inherit cfg;

  allNumbers = (builtins.attrNames cfg.extensions) ++ (builtins.attrNames cfg.ringGroups);

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

  # Recordings live outside FreeSWITCH's DynamicUser-private
  # /var/lib/freeswitch state so nginx can serve them and root-owned
  # timers can prune them; access is shared through the telephony group.
  recordingsDir = "/var/lib/telephony/recordings";
  recordingsHtpasswd = "/var/lib/telephony/recordings.htpasswd";

  # Shared sandbox profile for the root oneshot provisioning units. They
  # write only under /var/lib/telephony (pre-created by a tmpfiles rule:
  # ReadWritePaths targets must already exist when the unit starts).
  oneshotHardening = {
    NoNewPrivileges = true;
    PrivateTmp = true;
    ProtectSystem = "strict";
    ProtectHome = true;
    ProtectKernelTunables = true;
    ProtectKernelModules = true;
    ProtectControlGroups = true;
    RestrictAddressFamilies = [ "AF_UNIX" ];
  };
}
