# FreeSWITCH wiring: generated XML config, the hardened service unit,
# call recordings (shared dir, basic-auth rendering, retention) and the
# SIP TLS certificate provisioning from ACME.
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };
  inherit (shared)
    recordingsDir
    recordingsHtpasswd
    oneshotHardening
    gatewaysForFs
    fsSecrets
    useFsSecrets
    faxDir
    operatorPort
    operatorDir
    ;

  # Fill option defaults that depend on their own key (extension number
  # etc.); passwordFile entries become placeholder tokens (shared.nix).
  extensionsForFs = lib.mapAttrs (number: ext: {
    password = if ext.passwordFile != null then "@TELEPHONY_EXT_${number}_PASSWORD@" else ext.password;
    inherit (ext) allowInternational;
    displayName = if ext.displayName == "" then "Extension ${number}" else ext.displayName;
    vmPassword = if ext.vmPassword == null then number else ext.vmPassword;
    inherit (ext) vmEmail callerIdNumber;
  }) cfg.extensions;

  ringGroupsForFs = lib.mapAttrs (_: group: {
    inherit (group) members timeoutSec;
    voicemailMember =
      if group.voicemailMember == null then builtins.head group.members else group.voicemailMember;
    inherit (group) timeWindow;
  }) cfg.ringGroups;

  # FreeSWITCH TLS cert directory (agent.pem = cert+key, cafile.pem = chain)
  # provisioned from the ACME certificate for the internal profile's 5061.
  fsCertDir = "/var/lib/freeswitch/tls-certs";

  # Event-socket password as seen by the generated XML: a placeholder
  # when the file variant is used (spliced in at service start).
  eventSocketPasswordForXml =
    if cfg.eventSocketPasswordFile != null then
      "@TELEPHONY_EVENT_SOCKET_PASSWORD@"
    else
      cfg.eventSocketPassword;

  freeswitchConfig = import ../freeswitch.nix { inherit lib pkgs; } {
    inherit (cfg) domain;
    soundsDir = if cfg.sounds.package == null then null else "${cfg.sounds.package}/sounds";
    extensions = extensionsForFs;
    ringGroups = ringGroupsForFs;
    gateways = gatewaysForFs;
    inherit (cfg) ivrs conferences;
    inherit recordingsDir;
    eventSocketPassword = eventSocketPasswordForXml;
    natSipAddress = if cfg.natSipAddress != null then cfg.natSipAddress else cfg.natAddress;
    natRtpAddress = if cfg.natRtpAddress != null then cfg.natRtpAddress else cfg.natAddress;
    enableRecording = cfg.recording.enable;
    enableCdr = cfg.cdr.enable;
    faxExtension = if cfg.fax.enable then cfg.fax.extension else null;
    inherit faxDir;
    tlsCertDir = if cfg.tls.mode == "acme" then fsCertDir else null;
    mailerCommand = cfg.voicemail.mailerCommand;
    rtpStartPort = cfg.rtp.startPort;
    rtpEndPort = cfg.rtp.endPort;
    conferenceTemplate =
      "${config.services.freeswitch.configTemplate}/autoload_configs/conference.conf.xml";
  };

  # The operator read-model API runs when either of its consumers is on.
  operatorApiEnabled = cfg.operator.enable || cfg.webphone.phoneApi.enable;

  # ESL password source, mirroring the monitoring unit's passArg split.
  operatorEslPass =
    if cfg.eventSocketPasswordFile != null then
      ''"$(cat ${lib.escapeShellArg cfg.eventSocketPasswordFile})"''
    else
      lib.escapeShellArg cfg.eventSocketPassword;

  # Health view: units worth watching, beyond the always-on pair.
  operatorWatchedUnits = [
    "freeswitch.service"
    "nginx.service"
  ]
  ++ lib.optional cfg.turn.enable "turnserver.service"
  ++ lib.optionals cfg.monitoring.enable [
    "telephony-health.service"
    "telephony-health.timer"
  ]
  ++ lib.optionals cfg.backups.enable [ "restic-backups-telephony.service" ];

  # Certificate shown in the health view (best-effort; ACME dirs are
  # root-only, the API reports "unavailable" there).
  operatorTlsCert =
    if cfg.tls.mode == "self-signed" then
      "/var/lib/telephony/tls/cert.pem"
    else if cfg.tls.mode == "manual" then
      cfg.tls.certificate
    else
      null;

  operatorApiArgs = [
    "--domain ${lib.escapeShellArg cfg.domain}"
    "--esl-password-file ${operatorDir}/esl-password"
    "--cdr-file /var/lib/telephony/freeswitch-ro/cdr-csv/Master.csv"
    "--fs-root /var/lib/telephony/freeswitch-ro"
    "--voicemail-db /var/lib/telephony/freeswitch-ro/db/voicemail_default.db"
    "--dialplan-dir ${freeswitchConfDir}/dialplan"
    "--port ${toString operatorPort}"
    "--unit ${lib.concatStringsSep "," operatorWatchedUnits}"
  ]
  ++ lib.optionals (cfg.operator.smsMessageStore != null) [
    "--sms-store ${lib.escapeShellArg cfg.operator.smsMessageStore}"
  ]
  ++ lib.optionals (operatorTlsCert != null) [
    "--tls-cert-file ${lib.escapeShellArg operatorTlsCert}"
  ];

  # Concatenate the ACME certificate into FreeSWITCH's tls-cert-dir layout
  # (agent.pem = cert+key, cafile.pem = chain); the unit then enqueues a
  # freeswitch restart so the new material is actually in use.

  renderFsCert = pkgs.writeShellScript "telephony-fs-cert" ''
    set -eu
    ${pkgs.coreutils}/bin/mkdir -p ${fsCertDir}
    # Render to temp files and hash-guard the install: the path unit fires
    # on every cert-file write during issuance/renewal, and a redundant
    # restart drops calls for nothing (2026-09-16: two fires 8 min apart).
    new_agent="$(${pkgs.coreutils}/bin/mktemp ${fsCertDir}/agent.pem.XXXXXX)"
    new_cafile="$(${pkgs.coreutils}/bin/mktemp ${fsCertDir}/cafile.pem.XXXXXX)"
    trap '${pkgs.coreutils}/bin/rm -f "$new_agent" "$new_cafile"' EXIT
    ${pkgs.coreutils}/bin/cat /var/lib/acme/${cfg.domain}/fullchain.pem       /var/lib/acme/${cfg.domain}/key.pem > "$new_agent"
    ${pkgs.coreutils}/bin/cp /var/lib/acme/${cfg.domain}/fullchain.pem "$new_cafile"
    if ${pkgs.diffutils}/bin/cmp -s "$new_agent" ${fsCertDir}/agent.pem \
      && ${pkgs.diffutils}/bin/cmp -s "$new_cafile" ${fsCertDir}/cafile.pem; then
      exit 0
    fi
    # freeswitch runs as a DynamicUser over this StateDirectory: while it is
    # running, files written here by root (0600) are UNREADABLE to it and the
    # internal profile dies with "Error Creating SIP UA" on the next
    # start/restart (2026-09-16 deploy: renewal wrote root-owned agent.pem,
    # profile dead until manual chown). Hand the files to the StateDirectory
    # owner — stat -L: /var/lib/freeswitch is a symlink into /var/lib/private
    # and a non-L stat reports the link (root:root). Pre-first-start the tree
    # is root-owned and systemd chowns it when the unit starts.
    fs_owner="$(${pkgs.coreutils}/bin/stat -L -c %u:%g /var/lib/freeswitch 2>/dev/null || true)"
    if [ -n "$fs_owner" ] && [ "$fs_owner" != "root:root" ]; then
      ${pkgs.coreutils}/bin/chown "$fs_owner" "$new_agent" "$new_cafile"
    fi
    ${pkgs.coreutils}/bin/chmod 600 "$new_agent" "$new_cafile"
    ${pkgs.coreutils}/bin/mv "$new_agent" ${fsCertDir}/agent.pem
    ${pkgs.coreutils}/bin/mv "$new_cafile" ${fsCertDir}/cafile.pem
    # Reload requires tearing down sofia's TLS context. In this FreeSWITCH
    # build (1.11.1) BOTH in-process paths are broken, verified live on the
    # 2026-09-16 deploy: `sofia profile internal restart` races its own
    # port release ("Error Creating SIP UA" x3 leaves the profile DEAD),
    # and a stop+start rebinds the listeners but never re-registers the
    # profile in `sofia status`, breaking every future profile command
    # with "Invalid Profile". A unit restart is the only path verified to
    # bring the profile back RUNNING, registered, and serving the new
    # cert. It drops active calls; certificate renewals are ~60-day
    # events.
    #
    # Enqueue it with --no-block and WITHOUT any sofia/fs_cli probe: this
    # unit is ordered Before=freeswitch.service, so a blocking restart
    # self-deadlocks (its start job waits for this unit to finish while
    # this script blocks inside `systemctl restart`; 2026-09-16: job sat
    # queued >1h, PBX dark), and an fs_cli probe can hang on a wedged
    # event socket, holding this job — and with it the queued restart —
    # hostage (2026-09-16: second deploy, same blackout shape). `restart`
    # also STARTS a stopped unit, so the boot path (FreeSWITCH down) still
    # brings it up, merged into the boot transaction's own start job.
    ${pkgs.systemd}/bin/systemctl restart --no-block freeswitch.service
  '';

  # Assembled FreeSWITCH config directory, mirroring how the upstream
  # services.freeswitch module builds its store configDirectory (vanilla
  # template + configDir overlay). Only assembled when file-based secrets
  # are in play: the freeswitch unit then renders a private copy at
  # /var/lib/freeswitch/conf and runs against that instead of the store.
  # Named distinctly from the upstream module's own "freeswitch-config-d"
  # derivation: ours carries @TELEPHONY_*@ placeholders (meta says so) and
  # the secrets test greps for it by name.
  freeswitchConfDir =
    pkgs.runCommand "telephony-freeswitch-config-d"
      {
        # Self-documenting: anyone grepping the store for their secret finds
        # the placeholder instead.
        meta = {
          description = "Assembled FreeSWITCH config (secrets as placeholders)";
        };
      }
      ''
        mkdir -p $out
        cp -rT ${config.services.freeswitch.configTemplate} $out
        chmod -R +w $out
        ${lib.concatStringsSep "\n" (
          lib.mapAttrsToList (fileName: filePath: ''
            mkdir -p $out/$(dirname ${fileName})
            cp ${filePath} $out/${fileName}
          '') config.services.freeswitch.configDir
        )}
      '';

  # Copy the assembled store config to the runtime dir and splice the
  # real secrets in from the unit's LoadCredential files.
  renderFsConf = pkgs.writeShellScript "telephony-render-fs-conf" ''
    set -eu
    dst=/var/lib/freeswitch/conf
    ${pkgs.coreutils}/bin/rm -rf "$dst"
    ${pkgs.coreutils}/bin/cp -r ${freeswitchConfDir} "$dst"
    # Store files are read-only and world-readable; the runtime copy holds
    # real secrets, so make it private to the unit's (dynamic) user.
    ${pkgs.coreutils}/bin/chmod -R u+rwX,go-rwx "$dst"
    ${lib.concatStringsSep "\n" (
      lib.mapAttrsToList (id: secret: ''
        ${pkgs.replace-secret}/bin/replace-secret '${secret.token}' "$CREDENTIALS_DIRECTORY/${id}" "$dst/${secret.target}"
      '') fsSecrets
    )}
  '';
in
{
  config = lib.mkIf cfg.enable {
    services.freeswitch = {
      enable = true;
      # Generated config first, operator-provided extras win on collision.
      configDir = freeswitchConfig // cfg.extraConfigFiles;
    };

    # Group shared by FreeSWITCH (writes recordings) and nginx (serves them).
    users.groups.telephony = { };

    # Parent for all telephony runtime state; created during sysinit so the
    # hardened oneshots can bind-mount it writable without creating parents.
    systemd.tmpfiles.rules = [
      "d /var/lib/telephony 0755 root root -"
    ]
    # Fax TIFFs land next to the recordings (same group story); created
    # by tmpfiles so it exists regardless of recording.enable.
    ++ lib.optionals cfg.fax.enable [
      "d ${faxDir} 0770 root telephony -"
    ]
    # FreeSWITCH's outgoing-email pipeline hardcodes /bin/cat
    # (switch_utils.c: "/bin/cat <msg> | <mailer-app> ..."), which stock
    # NixOS does not provide — without the symlink the mailer silently
    # receives an empty message. Only needed when a mailer is wired.
    ++ lib.optionals (cfg.voicemail.mailerCommand != null) [
      "L+ /bin/cat - - - - ${pkgs.coreutils}/bin/cat"
    ];

    # Shared recordings directory, created before FreeSWITCH starts so the
    # unit's ReadWritePaths bind-mount has an existing path to mount.
    systemd.services.telephony-recordings-dir = lib.mkIf cfg.recording.enable {
      description = "Create the shared call-recordings directory";
      wantedBy = [ "multi-user.target" ];
      after = [ "users-groups.service" ];
      before = [ "freeswitch.service" ];
      serviceConfig = oneshotHardening // {
        Type = "oneshot";
        ReadWritePaths = [ "/var/lib/telephony" ];
        # setgid keeps files group-owned by telephony regardless of umask.
        ExecStart = pkgs.writeShellScript "telephony-recordings-dir" ''
          ${pkgs.coreutils}/bin/install -d -o root -g telephony -m 2770 ${recordingsDir}
        '';
      };
    };

    systemd.services.freeswitch = {
      # sofia resolves `$${local_ip_v4}` by UDP-connecting toward an
      # external address; without a default route it silently falls back
      # to 127.0.0.1 and the PBX stays unreachable from the network
      # until a manual restart. Wait for the network before binding.
      after = [
        "network-online.target"
        "telephony-tls.service"
      ]
      ++ lib.optionals cfg.recording.enable [ "telephony-recordings-dir.service" ];
      wants = [
        "network-online.target"
        "telephony-tls.service"
      ]
      ++ lib.optionals cfg.recording.enable [ "telephony-recordings-dir.service" ];
      serviceConfig = {
        # With DynamicUser, Group= pins a STATIC primary group for the
        # ephemeral user: everything FreeSWITCH creates (db/, storage/, log/
        # are 0750) becomes group-readable/traversable for the telephony
        # group. That is what makes the operator API's read-only bind of
        # this tree actually readable — the API runs as a DIFFERENT
        # ephemeral user and previously got EACCES on db/ (os.path.exists
        # -> False). Read-only exposure of FS state to the telephony group
        # (nginx, operator API) is the intended trust circle; the API
        # deliberately keeps its own uid so it still cannot WRITE here.
        Group = "telephony";
        ExecStartPre = [
          "${pkgs.coreutils}/bin/mkdir -p /var/lib/freeswitch/empty-moh"
        ]
        ++ lib.optionals cfg.cdr.enable [
          "${pkgs.coreutils}/bin/mkdir -p /var/lib/freeswitch/cdr-csv"
        ]
        ++ lib.optionals useFsSecrets [ renderFsConf ];
        # DynamicUser already implies ProtectSystem=strict + PrivateTmp;
        # these close the remaining gaps for a SIP/RTP daemon.
        NoNewPrivileges = true;
        ProtectHome = true;
        # Hardening, not a bug fix: the upstream nixpkgs unit grants
        # FreeSWITCH SCHED_FIFO with no RT time budget, so a runaway
        # realtime task could starve the whole host. This stack needs no
        # realtime guarantees, so run the default CFS policy; operators
        # who need RT can re-enable it knowingly.
        CPUSchedulingPolicy = lib.mkForce "other";
        # AF_NETLINK: getifaddrs for NAT/interface detection (sofia stalls
        # on the first INVITE without it).
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
          "AF_INET6"
          "AF_NETLINK"
        ];
      }
      // lib.optionalAttrs (cfg.recording.enable || cfg.fax.enable) {
        # FreeSWITCH runs as a DynamicUser whose only writable state is
        # /var/lib/freeswitch; recordings and fax TIFFs go to the shared
        # directory (written via the telephony group).
        SupplementaryGroups = [ "telephony" ];
        ReadWritePaths = [ recordingsDir ];
      }
      // lib.optionalAttrs useFsSecrets {
        # Secret-file mode: render the private config copy (ExecStartPre
        # above) and run against it. Mirrors the upstream ExecStart with
        # only -conf redirected; systemd hands the LoadCredential files
        # to the DynamicUser via $CREDENTIALS_DIRECTORY.
        LoadCredential = lib.mapAttrsToList (id: secret: "${id}:${secret.file}") fsSecrets;
        ExecStart = lib.mkForce (
          "${config.services.freeswitch.package}/bin/freeswitch -nf"
          + " -mod ${config.services.freeswitch.package}/lib/freeswitch/mod"
          + " -conf /var/lib/freeswitch/conf"
          + " -base /var/lib/freeswitch"
        );
      };
    };

    # Render the /recordings/ basic-auth file from the operator-supplied
    # password; nginx reads it at request time via the telephony group.
    systemd.services.telephony-recordings-auth = lib.mkIf cfg.recording.serve.enable {
      description = "Render basic-auth credentials for the recordings endpoint";
      wantedBy = [ "multi-user.target" ];
      after = [ "users-groups.service" ];
      before = [ "nginx.service" ];
      serviceConfig = oneshotHardening // {
        Type = "oneshot";
        ReadWritePaths = [ "/var/lib/telephony" ];
        ExecStart = pkgs.writeShellScript "telephony-recordings-auth" ''
          set -eu
          password=$(cat ${cfg.recording.serve.basicAuthPasswordFile})
          umask 027
          printf '%s:{PLAIN}%s\n' ${lib.escapeShellArg cfg.recording.serve.basicAuthUser} "$password" \
            > ${recordingsHtpasswd}
          ${pkgs.coreutils}/bin/chgrp telephony ${recordingsHtpasswd}
        '';
      };
    };

    # Operator window provisioning: the ESL password (the read-model API
    # drives fs_cli for credential checks and health) and, when the
    # operator window is on, the shared basic-auth htpasswd.
    systemd.services.telephony-operator-auth = lib.mkIf operatorApiEnabled {
      description = "Render credentials for the telephony operator API";
      wantedBy = [ "multi-user.target" ];
      after = [ "users-groups.service" ];
      before = [ "nginx.service" ];
      serviceConfig = oneshotHardening // {
        Type = "oneshot";
        ReadWritePaths = [ "/var/lib/telephony" ];
        ExecStart = pkgs.writeShellScript "telephony-operator-auth" ''
          set -eu
          ${pkgs.coreutils}/bin/install -d -o root -g telephony -m 0750 ${operatorDir}
          umask 027
          printf '%s\n' ${operatorEslPass} > ${operatorDir}/esl-password
          ${pkgs.coreutils}/bin/chgrp telephony ${operatorDir}/esl-password
          ${lib.optionalString cfg.operator.enable ''
            password=$(cat ${cfg.operator.apiPasswordFile})
            printf '%s:{PLAIN}%s\n' ${lib.escapeShellArg cfg.operator.apiUser} "$password" \
              > ${recordingsHtpasswd}
            ${pkgs.coreutils}/bin/chgrp telephony ${recordingsHtpasswd}
          ''}
        '';
      };
    };

    # The read-model API: a stdlib-only service rendering PBX state for
    # the webphone panels and the operator window. It reads FreeSWITCH's
    # DynamicUser-private state through a read-only bind (the
    # /var/lib/freeswitch symlink targets /var/lib/private, which is
    # 0700 root — the bind is the only non-root path in) and talks to
    # fs_cli over the loopback event socket. Window, never editor: the
    # only state change it can make is a voicemail delete via
    # mod_voicemail's own vm_delete API.
    systemd.services.telephony-operator = lib.mkIf operatorApiEnabled {
      description = "Telephony read-model API (webphone voicemail/history, operator window)";
      wantedBy = [ "multi-user.target" ];
      after = [
        "freeswitch.service"
        "telephony-operator-auth.service"
      ];
      wants = [ "freeswitch.service" ];
      serviceConfig = {
        Type = "simple";
        DynamicUser = true;
        SupplementaryGroups = [ "telephony" ];
        # The read model needs FreeSWITCH's state tree (CDR CSV, voicemail
        # DB, message WAVs). The files physically live under
        # /var/lib/private/freeswitch (DynamicUser StateDirectory);
        # /var/lib/private is 0700 root:root, so the operator's dynamic
        # user cannot WALK to any mountpoint below it (os.path.exists
        # then reports False on EACCES — paid for twice in the operator
        # suite). Mounting onto /var/lib/freeswitch does not help either:
        # that name is a host SYMLINK into /var/lib/private, and the
        # bind destination follows it straight back into the trap.
        # Mount onto a fresh, collision-free path instead; the API args
        # use it (systemd creates the destination dir if missing).
        # Layer 3 (paid for in the same suite): the bind alone still
        # fails — FS-created subdirs (db/, storage/) are 0750 owned by
        # FreeSWITCH's ephemeral user, unreadable for a second dynamic
        # user. freeswitch.service therefore pins Group=telephony (see
        # there), and this unit's SupplementaryGroups above completes it.
        BindReadOnlyPaths = [
          "/var/lib/private/freeswitch:/var/lib/telephony/freeswitch-ro"
        ];
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
        ];
        IPAddressAllow = [ "localhost" ];
        IPAddressDeny = [ "any" ];
        Restart = "on-failure";
        Environment = "PYTHONDONTWRITEBYTECODE=1";
        ExecStart = "${
          pkgs.callPackage ../../packages/telephony-operator { }
        }/bin/telephony-operator-api ${lib.concatStringsSep " " operatorApiArgs}";
      };
      # fs_cli, systemctl (unit states) and openssl (cert expiry) on PATH.
      path = with pkgs; [
        freeswitch
        systemd
        openssl
      ];
    };

    # Retention: prune recordings past their window (find -mtime +N means
    # "older than roughly N days"; the timer makes the guarantee "at least").
    systemd.services.telephony-recording-retention = lib.mkIf (cfg.recording.retentionDays != null) {
      description = "Delete call recordings past their retention window";
      serviceConfig = oneshotHardening // {
        Type = "oneshot";
        ReadWritePaths = [ "/var/lib/telephony" ];
        ExecStart = pkgs.writeShellScript "telephony-recording-retention" ''
          exec ${pkgs.findutils}/bin/find ${recordingsDir} -type f -name '*.wav' \
            -mtime +${toString cfg.recording.retentionDays} -delete
        '';
      };
    };

    systemd.timers.telephony-recording-retention = lib.mkIf (cfg.recording.retentionDays != null) {
      description = "Prune old call recordings daily";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
      };
    };

    # Provision the ACME certificate to FreeSWITCH's SIP-over-TLS listener:
    # sofia reads agent.pem (cert+key) and cafile.pem from tls-cert-dir.
    systemd.services.telephony-fs-cert = lib.mkIf (cfg.tls.mode == "acme") {
      description = "Provision ACME certificate to FreeSWITCH SIP TLS";
      wantedBy = [ "multi-user.target" ];
      after = [ "acme-finished-${cfg.domain}.service" ];
      wants = [ "acme-finished-${cfg.domain}.service" ];
      before = [ "freeswitch.service" ];
      serviceConfig = {
        Type = "oneshot";
        # A hung script here holds the ordered freeswitch start job — and
        # through it multi-user.target — hostage; bound the whole thing.
        timeoutStartSec = 120;
        # No ProtectSystem here: the unit creates /var/lib/freeswitch/tls-certs
        # before FreeSWITCH's DynamicUser StateDirectory exists.
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectHome = true;
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
        ];
        ExecStart = renderFsCert;
      };
    };

    # Renewal: when ACME rotates the certificate, re-provision (the service
    # restarts the freeswitch unit so the TLS listeners pick up the new
    # material; see the script for why in-process profile restarts do not
    # work in this build).
    systemd.paths.telephony-fs-cert = lib.mkIf (cfg.tls.mode == "acme") {
      wantedBy = [ "multi-user.target" ];
      pathConfig.PathChanged = "/var/lib/acme/${cfg.domain}/cert.pem";
    };
  };
}
