# Failure resilience: off-host restic backups of PBX state and webhook
# routing of unit failures (OnFailure -> telephony-alert@<unit>).
#
# Backups delegate to NixOS' own services.restic.backups (timer,
# credentials handling, pruning); this module only folds the telephony
# options into it and points failure hooks at the alert template. The
# alert unit POSTs the failed unit's name, host, time and the last
# journal lines to the configured webhook — any endpoint accepting a
# POST body works (healthchecks.io dead-man switch, Slack, ntfy.sh).
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };

  # Alerts are active when exactly one of url/urlFile is set (the
  # assertion in this file keeps the pair unambiguous).
  alertsActive = (cfg.alerts.url != null) != (cfg.alerts.urlFile != null);

  alertUrl =
    if cfg.alerts.urlFile != null then
      ''"$(cat ${lib.escapeShellArg cfg.alerts.urlFile})"''
    else
      lib.escapeShellArg cfg.alerts.url;

  # %n reaches the template instance-expanded, i.e. the FAILED unit's
  # name — that is the whole routing mechanism.
  alertOnFailure = lib.mkIf alertsActive { OnFailure = "telephony-alert@%n.service"; };
in
{
  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = !cfg.backups.enable || ((cfg.backups.repository != null) != (cfg.backups.repositoryFile != null));
        message = "services.telephony.backups: set exactly one of repository or repositoryFile when backups are enabled.";
      }
      {
        assertion = !cfg.backups.enable || cfg.backups.passwordFile != null;
        message = "services.telephony.backups.passwordFile is required when backups are enabled (restic repo password).";
      }
      {
        assertion = !cfg.backups.enable || cfg.backups.paths != [ ];
        message = "services.telephony.backups.paths must not be empty.";
      }
      {
        assertion = !alertsActive || (cfg.alerts.url != null || cfg.alerts.urlFile != null);
        message = "services.telephony.alerts: set exactly one of url or urlFile (not both).";
      }
    ];

    systemd.services."telephony-alert@" = lib.mkIf alertsActive {
      description = "Send failure alert for %i (webhook POST)";
      # Pulled in only via OnFailure=; never wanted by anything else.
      wantedBy = [ ];
      serviceConfig =
        {
          Type = "oneshot";
          ExecStart = "${pkgs.writeShellScript "telephony-alert" ''
            set -eu
            failed_unit="$1"
            payload="$(
              printf 'PBX unit failure: %%s on %%s at %%s\n' "$failed_unit" "$(hostname)" "$(date -Is)"
              echo '--- last journal lines ---'
              journalctl -u "$failed_unit" -n 15 --no-pager || true
            )"
            ${pkgs.curl}/bin/curl \
              --fail --silent --show-error --max-time 15 \
              --request POST \
              --header 'Content-Type: text/plain; charset=utf-8' \
              --data-binary "$payload" \
              ${alertUrl}
          ''} %i";
        }
        // shared.oneshotHardening
        // {
          # curl needs outbound HTTP; journal lines need journal read.
          RestrictAddressFamilies = [
            "AF_UNIX"
            "AF_INET"
            "AF_INET6"
          ];
        };
    };

    services.restic.backups.telephony = lib.mkIf cfg.backups.enable {
      inherit (cfg.backups) passwordFile paths pruneOpts;
      inherit (cfg.backups) repository repositoryFile;
      # The unit skips init when the repo already exists; a fresh
      # Storage Box path must not require a manual bootstrap step.
      initialize = true;
      timerConfig = {
        OnCalendar = cfg.backups.calendar;
        Persistent = true;
      };
    };

    systemd.services.restic-backups-telephony = lib.mkIf cfg.backups.enable {
      unitConfig = alertOnFailure;
    };

    systemd.services.telephony-health = lib.mkIf cfg.monitoring.enable {
      unitConfig = alertOnFailure;
    };

    systemd.services.fail2ban = lib.mkIf cfg.fail2ban.enable {
      unitConfig = alertOnFailure;
    };
  };
}
