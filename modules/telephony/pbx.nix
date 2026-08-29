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
    tlsCertDir = if cfg.tls.mode == "acme" then fsCertDir else null;
    mailerCommand = cfg.voicemail.mailerCommand;
    rtpStartPort = cfg.rtp.startPort;
    rtpEndPort = cfg.rtp.endPort;
  };

  # Concatenate the ACME certificate into FreeSWITCH's tls-cert-dir layout
  # (agent.pem = cert+key, cafile.pem = chain); when FreeSWITCH is already
  # running the internal profile is restarted so SIP TLS uses the new
  # material.
  esPasswordArg =
    if cfg.eventSocketPasswordFile != null then
      "$(${pkgs.coreutils}/bin/cat ${cfg.eventSocketPasswordFile})"
    else
      cfg.eventSocketPassword;

  renderFsCert = pkgs.writeShellScript "telephony-fs-cert" ''
    set -eu
    es_password="${esPasswordArg}"
    ${pkgs.coreutils}/bin/mkdir -p ${fsCertDir}
    ${pkgs.coreutils}/bin/cat /var/lib/acme/${cfg.domain}/fullchain.pem       /var/lib/acme/${cfg.domain}/key.pem > ${fsCertDir}/agent.pem.tmp
    ${pkgs.coreutils}/bin/cp /var/lib/acme/${cfg.domain}/fullchain.pem ${fsCertDir}/cafile.pem.tmp
    ${pkgs.coreutils}/bin/chmod 600 ${fsCertDir}/agent.pem.tmp ${fsCertDir}/cafile.pem.tmp
    ${pkgs.coreutils}/bin/mv ${fsCertDir}/agent.pem.tmp ${fsCertDir}/agent.pem
    ${pkgs.coreutils}/bin/mv ${fsCertDir}/cafile.pem.tmp ${fsCertDir}/cafile.pem
    if ${pkgs.freeswitch}/bin/fs_cli -p "$es_password" -x 'sofia status' >/dev/null 2>&1; then
      ${pkgs.freeswitch}/bin/fs_cli -p "$es_password" -x 'sofia profile internal restart'
    fi
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
      // lib.optionalAttrs cfg.recording.enable {
        # FreeSWITCH runs as a DynamicUser whose only writable state is
        # /var/lib/freeswitch; recordings go to the shared directory.
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
    # restarts the internal profile so 5061 picks up the new material).
    systemd.paths.telephony-fs-cert = lib.mkIf (cfg.tls.mode == "acme") {
      wantedBy = [ "multi-user.target" ];
      pathConfig.PathChanged = "/var/lib/acme/${cfg.domain}/cert.pem";
    };
  };
}
