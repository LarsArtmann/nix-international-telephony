# services.telephony.pbx-lens: the unified call-history index (pbx-lens).
#
# pbx-lens is a read-only index over the stack's call sources: the
# FreeSWITCH CDR CSV, the Telnyx receiver webhook JSONL, the agent
# transcripts, and (optionally) the Telnyx API for recordings/cost. The
# index database is disposable and always re-derivable from those sources;
# the lens never writes back to any of them. The binary comes from the
# github:LarsArtmann/pbx-lens flake input; this module owns the deploy
# surface (service, credentials, poll cadence, backup and retention
# timers). The unit draft lives in that repo under deploy/ for reference.
{
  config,
  lib,
  ...
}:
let
  cfg = config.services.telephony.pbx-lens;
in
{
  options.services.telephony.pbx-lens = {
    enable = lib.mkEnableOption "the pbx-lens call-history index UI";

    package = lib.mkOption {
      type = lib.types.package;
      description = ''
        The pbx-lens package. nixosModules.telephony defaults this to the
        flake's pbx-lens input.
      '';
    };

    address = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1:8300";
      description = "Listen address. Keep loopback and front it with the reverse proxy.";
    };

    stateDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/pbx-lens";
      description = "Index DB directory (disposable: always re-derivable from sources).";
    };

    telnyxApiKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Telnyx API key file for the recording proxy and the Telnyx poller.
        Loaded as a systemd credential; null disables both paths.
      '';
    };

    htpasswdFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        bcrypt htpasswd file (htpasswd -B). Loaded as a systemd credential;
        null leaves every route open — acceptable only on loopback dev.
      '';
    };

    recordingsDir = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = "/var/lib/telephony/recordings";
      description = "FreeSWITCH recordings directory served through the proxy.";
    };

    pollEvery = lib.mkOption {
      type = lib.types.nullOr lib.types.nonEmptyStr;
      default = "15m";
      description = "Poll cadence (systemd time span); null disables the poller.";
    };

    pollSince = lib.mkOption {
      type = lib.types.nullOr lib.types.nonEmptyStr;
      default = "48h";
      description = "Telnyx look-back window per poll (Go duration).";
    };

    pollDirection = lib.mkOption {
      type = lib.types.enum [
        "inbound"
        "outbound"
      ];
      default = "outbound";
      description = ''
        Caller-declared direction for polled Telnyx conversations (Telnyx
        metadata exposes none).
      '';
    };

    cdrFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "FreeSWITCH Master.csv re-ingested every poll.";
    };

    webhookLog = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Receiver webhook JSONL re-ingested every poll.";
    };

    transcriptsDir = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Agent transcripts dir re-scanned every poll.";
    };

    retention = {
      maxAge = lib.mkOption {
        type = lib.types.nullOr lib.types.nonEmptyStr;
        default = null;
        description = ''
          Retention window (Go duration, e.g. "2160h" = 90 days). Calls
          observed before now-minus-window are retired from every read
          surface on the schedule below; null keeps everything.
        '';
      };

      calendar = lib.mkOption {
        type = lib.types.str;
        default = "*-*-* 03:30:00";
        description = "OnCalendar schedule for the retention purge timer.";
      };
    };

    backup = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = ''
          Stage one verified index snapshot nightly. This is staging only:
          the host backup tool owns retention and off-host shipping and
          must include the index backups directory (registered in
          services.telephony.state.paths).
        '';
      };

      calendar = lib.mkOption {
        type = lib.types.str;
        default = "*-*-* 02:15:00";
        description = "OnCalendar schedule for the snapshot staging timer.";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.services.pbx-lens = {
      description = "pbx-lens — unified call-history index (read-only UI)";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "notify";
        # appkit sends READY=1 after the listener binds and STOPPING=1 at
        # the graceful drain; the binary feeds the watchdog at half this.
        WatchdogSec = "30";
        DynamicUser = true;
        StateDirectory = "pbx-lens";
        StateDirectoryMode = "0750";
        ExecStart = lib.concatStringsSep " " (
          [
            (lib.getExe cfg.package)
            "serve"
            "-db ${cfg.stateDir}/index.db"
            "-addr ${cfg.address}"
          ]
          ++ lib.optionals (cfg.telnyxApiKeyFile != null) [
            "-telnyx-key-file \${CREDENTIALS_DIRECTORY}/telnyx-api-key"
          ]
          ++ lib.optionals (cfg.htpasswdFile != null) [
            "-htpasswd \${CREDENTIALS_DIRECTORY}/htpasswd"
          ]
          ++ lib.optionals (cfg.recordingsDir != null) [
            "-recordings-dir ${cfg.recordingsDir}"
          ]
          ++ lib.optionals (cfg.pollEvery != null) [ "-poll-every ${cfg.pollEvery}" ]
          ++ lib.optionals (cfg.pollSince != null) [ "-poll-since ${cfg.pollSince}" ]
          ++ lib.optionals (cfg.pollDirection != null) [ "-poll-direction ${cfg.pollDirection}" ]
          ++ lib.optionals (cfg.cdrFile != null) [ "-cdr-file ${cfg.cdrFile}" ]
          ++ lib.optionals (cfg.webhookLog != null) [ "-webhook-log ${cfg.webhookLog}" ]
          ++ lib.optionals (cfg.transcriptsDir != null) [
            "-transcripts-dir ${cfg.transcriptsDir}"
          ]
        );
        LoadCredential =
          lib.optional (cfg.telnyxApiKeyFile != null) "telnyx-api-key:${cfg.telnyxApiKeyFile}"
          ++ lib.optional (cfg.htpasswdFile != null) "htpasswd:${cfg.htpasswdFile}";
        # Read-only ingest sources: the lens never writes back to any of them.
        ReadOnlyPaths = lib.optionals (cfg.recordingsDir != null) [ cfg.recordingsDir ];
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
          "AF_INET6"
        ];
        RestrictNamespaces = true;
        LockPersonality = true;
        MemoryDenyWriteExecute = true;
        SystemCallFilter = "@system-service";
        SystemCallArchitectures = "native";
        CapabilityBoundingSet = [ ];
        AmbientCapabilities = [ ];
      };
    };

    systemd.services.pbx-lens-backup = lib.mkIf cfg.backup.enable {
      description = "pbx-lens — nightly index snapshot staging";
      serviceConfig = {
        Type = "oneshot";
        DynamicUser = true;
        # Same StateDirectory as pbx-lens.service: both units share the
        # dynamic user, so this one may read index.db and stage into
        # backups/ (sqlite VACUUM INTO + integrity_check inside the binary).
        StateDirectory = "pbx-lens";
        StateDirectoryMode = "0750";
        ExecStart = lib.concatStringsSep " " [
          (lib.getExe cfg.package)
          "backup"
          "-db ${cfg.stateDir}/index.db"
          "-out ${cfg.stateDir}/backups/index.db"
        ];
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        RestrictAddressFamilies = [ "AF_UNIX" ];
        MemoryDenyWriteExecute = true;
      };
    };

    systemd.timers.pbx-lens-backup = lib.mkIf cfg.backup.enable {
      description = "pbx-lens — nightly index snapshot staging schedule";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.backup.calendar;
        RandomizedDelaySec = "10m";
        Persistent = true;
      };
    };

    systemd.services.pbx-lens-purge = lib.mkIf (cfg.retention.maxAge != null) {
      description = "pbx-lens — retention purge (retire calls over the age window)";
      serviceConfig = {
        Type = "oneshot";
        DynamicUser = true;
        StateDirectory = "pbx-lens";
        StateDirectoryMode = "0750";
        ExecStart = lib.concatStringsSep " " [
          (lib.getExe cfg.package)
          "purge"
          "-db ${cfg.stateDir}/index.db"
          "-max-age ${cfg.retention.maxAge}"
        ];
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        RestrictAddressFamilies = [ "AF_UNIX" ];
        MemoryDenyWriteExecute = true;
      };
    };

    systemd.timers.pbx-lens-purge = lib.mkIf (cfg.retention.maxAge != null) {
      description = "pbx-lens — retention purge schedule";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.retention.calendar;
        RandomizedDelaySec = "10m";
        Persistent = true;
      };
    };
  };
}
