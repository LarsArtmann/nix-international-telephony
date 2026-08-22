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

  # Merge the deprecated singular gateway into the attrsOf form, fill
  # the realm default (proxy host when unset) and swap passwordFile
  # entries for their placeholder token (see fsSecrets).
  gatewaysForFs =
    lib.mapAttrs
      (
        _name: gateway:
        gateway
        // {
          realm = if gateway.realm == "" then gateway.proxy else gateway.realm;
          password =
            if gateway.passwordFile != null then
              "@TELEPHONY_GW_${lib.toUpper (lib.replaceStrings [ "-" ] [ "_" ] gateway.name)}_PASSWORD@"
            else
              gateway.password;
        }
      )
      (cfg.gateways // (lib.optionalAttrs (cfg.gateway != null) { ${cfg.gateway.name} = cfg.gateway; }));

  # Activation-time secret rendering: options carrying a *File variant
  # emit a @TELEPHONY_*@ placeholder into the (world-readable) generated
  # FreeSWITCH config instead of the secret; the freeswitch unit's
  # ExecStartPre copies the assembled config to a runtime dir and splices
  # the real values in from LoadCredential files (pkgs.replace-secret).
  # Keys are systemd credential ids; each names the file, the placeholder
  # token and the config-relative target file carrying that token.
  fsSecrets =
    (lib.optionalAttrs (cfg.eventSocketPasswordFile != null) {
      event-socket-password = {
        file = cfg.eventSocketPasswordFile;
        token = "@TELEPHONY_EVENT_SOCKET_PASSWORD@";
        target = "autoload_configs/event_socket.conf.xml";
      };
    })
    // (lib.mapAttrs' (
      num: ext:
      lib.nameValuePair "ext-${num}-password" {
        file = ext.passwordFile;
        token = "@TELEPHONY_EXT_${num}_PASSWORD@";
        target = "directory/default.xml";
      }
    ) (lib.filterAttrs (_: ext: ext.passwordFile != null) cfg.extensions))
    // (lib.mapAttrs' (
      name: gateway:
      lib.nameValuePair "gw-${name}-password" {
        file = gateway.passwordFile;
        token = "@TELEPHONY_GW_${lib.toUpper (lib.replaceStrings [ "-" ] [ "_" ] name)}_PASSWORD@";
        target = "sip_profiles/external.xml";
      }
    ) (lib.filterAttrs (_: gateway: gateway.passwordFile != null) gatewaysForFs));

  useFsSecrets = fsSecrets != { };
in
{
  inherit cfg;

  inherit fsSecrets useFsSecrets gatewaysForFs;

  allNumbers = (builtins.attrNames cfg.extensions) ++ (builtins.attrNames cfg.ringGroups);

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
