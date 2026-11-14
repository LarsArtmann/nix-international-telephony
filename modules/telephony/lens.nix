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
  pkgs,
  ...
}:
let
  cfg = config.services.telephony.pbx-lens;
  shared = import ./shared.nix { inherit config lib; };

  # The messaging-bridge JSONL access render: when webhookLog points at
  # the bridge's public path with the bridge on, the module owns the
  # whole three-layer read path (ro bind + telephony-fs ACL + arg
  # rewrite to the bound path) exactly like the operator's
  # smsMessageStore default — the deployment stops hand-wiring it
  # hosts-side. Any other path passes through untouched; then the
  # deployment owns its readability.
  webhookIsBridgeLog =
    config.services.telephony.messaging.enable && cfg.webhookLog == shared.messagingJsonlPath;

  # The recordings tree (recordingsDir and transcriptsDir under it) is
  # 2770 root:telephony — readable only through the telephony group.
  readsRecordingsTree =
    cfg.recordingsDir != null
    || (
      cfg.transcriptsDir != null
      && lib.hasPrefix (toString shared.recordingsDir) (toString cfg.transcriptsDir)
    );

  # Mirrors resilience.nix: alerts fire only with exactly one of
  # url/urlFile set.
  alertsActive =
    (config.services.telephony.alerts.url != null)
    != (config.services.telephony.alerts.urlFile != null);

  # Single-component systemd spans only ("<n><unit>"); anything else
  # (compound "1h30m", "2m30s") returns null and demands an explicit
  # monitoring.freshness.maxAgeSeconds.
  simpleSpanSeconds =
    span:
    let
      # Null-safe: a null pollEvery (poller off) reaches this through
      # the freshness assertion path — builtins.match on null would
      # crash before the assertion machinery can report anything.
      parts = if span == null then null else builtins.match "([0-9]+)([smhd])" span;
    in
    if parts == null then
      null
    else
      (lib.toIntBase10 (builtins.head parts))
      * {
        s = 1;
        m = 60;
        h = 3600;
        d = 86400;
      }
      .${builtins.elemAt parts 1};

  # Fail threshold for the freshness check: explicit when set,
  # otherwise 3x the poll cadence when pollEvery is a simple span.
  freshnessMaxAgeSeconds =
    if cfg.monitoring.freshness.maxAgeSeconds != null then
      cfg.monitoring.freshness.maxAgeSeconds
    else
      let
        derived = simpleSpanSeconds cfg.pollEvery;
      in
      if derived == null then null else 3 * derived;
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

    auth = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Native passkey login (pbx-lens -auth-db). The operator account is
          event-sourced in <stateDir>/identity.db (NOT disposable, unlike
          the index); the first visitor to /login becomes the operator and
          registration closes after that account. Passkeys need a secure
          context: reach the lens through the TLS-terminating reverse proxy
          and set publicOrigin accordingly.
        '';
      };

      publicOrigin = lib.mkOption {
        type = lib.types.nullOr lib.types.str;
        default = null;
        description = ''
          The browser-facing origin (scheme + host, e.g. "https://pbx.example.com")
          that must byte-match the address bar for WebAuthn ceremonies. The
          WebAuthn RPID is derived from its host part. Required when
          auth.enable is true.
        '';
      };

      # The OIDC lane rides the identity context: with auth.enable it mounts
      # the "Sign in with Pocket ID" button beside the passkey panel. All
      # options are null/off by default (passkey-only), exactly like the
      # binary's flags.
      oidc = {
        issuer = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          description = ''
            OIDC issuer base URL (e.g. "https://auth.example.com"). Setting
            this enables the Pocket ID sign-in lane: authorization code +
            PKCE-S256, lazy discovery (an IdP outage costs a login, never the
            boot), RS256 id_token verification, and the userinfo fallback for
            access tokens without profile claims. The login routes
            auto-mount at /auth/oauth/&lt;provider&gt;/begin|callback.
          '';
        };

        clientId = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          description = "OIDC client id registered in the IdP (required with issuer).";
        };

        clientSecretFile = lib.mkOption {
          type = lib.types.nullOr lib.types.path;
          default = null;
          description = ''
            OIDC client secret file, loaded as a systemd credential and read
            by the lens per login (rotation takes effect on the next
            sign-in; no trailing newline — the raw-read class).
          '';
        };

        redirectUrl = lib.mkOption {
          type = lib.types.nullOr lib.types.str;
          default = null;
          description = ''
            The callback URL registered in the IdP. Library route law pins
            the shape: https://&lt;public-host&gt;/auth/oauth/pocketid/callback.
          '';
        };

        allowedGroups = lib.mkOption {
          type = lib.types.listOf lib.types.str;
          default = [ ];
          description = ''
            IdP groups allowed to sign in (fail-closed: a token claiming
            none of them is denied before any user matching). Must be
            non-empty when issuer is set — the group gate is the security
            boundary, and an empty list would disable it in the binary.
          '';
        };
      };
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

    aiDids = lib.mkOption {
      type = lib.types.nullOr (lib.types.nonEmptyListOf lib.types.nonEmptyStr);
      default = null;
      description = ''
        AI-facing DIDs (pbx-lens docs/did-direction-design.md): polled
        Telnyx conversations touching one of these numbers index as
        inbound, overriding pollDirection. null keeps the declared
        direction.
      '';
    };

    pollMaxAge = lib.mkOption {
      type = lib.types.nullOr lib.types.nonEmptyStr;
      default = null;
      description = ''
        Ingest-side retention window (Go duration, e.g. "720h"): polled
        observations older than now-minus-window are refused at ingest
        (labeled retention:age-cutoff). null (the default, owner decision
        2026-10-12) keeps everything — retention stays opt-in.
      '';
    };

    recordingTimeout = lib.mkOption {
      type = lib.types.nullOr lib.types.nonEmptyStr;
      default = null;
      description = ''
        Upstream bound for the recording proxy (Go duration): metadata
        deadline + WAV response headers; the audio body streams unbounded.
        null keeps the binary default (30s).
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

      dryRun = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Pre-flight the retention purge: the purge verb runs with
          -dry-run and logs what it would retire without writing any
          tombstones. One timer pass with this on is the honest way to
          size a retention window before it starts deleting history.
        '';
      };
    };

    csp = {
      nonce = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Serve with a nonce-based Content-Security-Policy (renders
          CSP_NONCE=1 for the serve unit). The lens emits its assets
          inline/script-tagged; the nonce policy keeps that shape while
          giving the browser an enforcement point.
        '';
      };

      reportOnly = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Switch the nonce policy's header to
          Content-Security-Policy-Report-Only (renders CSP_REPORT_ONLY=1):
          an observe-only rollout that reports violations without
          blocking them. Meaningful only together with csp.nonce —
          report-only switches the nonce policy's header, it does not
          create one (asserted).
        '';
      };
    };

    monitoring.scrape.enable = lib.mkEnableOption ''
      the pbx-lens Prometheus scrape target. /metrics lives on the same
      address as the UI (appkit mounts it OUTSIDE the session-gate chain —
      the perimeter is the bind address; SECURITY.md in pbx-lens records
      the opt-in as deliberate). When on, the lens appends a scrape job
      to services.telephony.monitoring.scrapeJobs for a host-level
      Prometheus/Gatus to consume; no scraper is created here.
    '';

    monitoring.freshness = {
      enable = lib.mkEnableOption ''
        the poller freshness check: a timer-driven unit that reads
        last_pass_age_seconds from the lens's /api/ops JSON and fails
        loudly when the poller has never passed (-1) or its last pass is
        older than the threshold below — a dead poller otherwise fails
        silently (the UI simply stops updating). The ops API sits behind
        the identity session gate when auth.enable is on and a
        credential-less check unit cannot cross it, so this arm requires
        auth off (asserted): run the lens unauthenticated on loopback —
        the perimeter IS the bind address — and front it with the
        reverse proxy; consume /health/ready and the scrape target
        beside an authenticated lens.
      '';

      interval = lib.mkOption {
        type = lib.types.nonEmptyStr;
        default = "15m";
        description = ''
          Check cadence (systemd time span, OnUnitActiveSec). Keep it at
          or below half the fail threshold so a stale poller is caught
          within one interval, not two.
        '';
      };

      maxAgeSeconds = lib.mkOption {
        type = lib.types.nullOr lib.types.ints.positive;
        default = null;
        description = ''
          Fail threshold in seconds: the check fails when
          last_pass_age_seconds is -1 (never passed since boot) or
          above this. null derives 3x pollEvery when pollEvery is a
          simple span ("15m" -> 2700); set it explicitly for compound
          spans.
        '';
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
    assertions = [
      {
        assertion = !cfg.auth.enable || cfg.auth.publicOrigin != null;
        message = ''
          services.telephony.pbx-lens.auth.enable needs auth.publicOrigin:
          the WebAuthn origin must byte-match the browser-facing address.
        '';
      }
      {
        assertion = cfg.auth.oidc.issuer == null || cfg.auth.enable;
        message = ''
          services.telephony.pbx-lens.auth.oidc rides the identity context:
          set auth.enable = true (and auth.publicOrigin) with it.
        '';
      }
      {
        assertion = !cfg.monitoring.freshness.enable || cfg.pollEvery != null;
        message = ''
          services.telephony.pbx-lens.monitoring.freshness reads the
          poller's last-pass age: enable it only with pollEvery set (a
          poller-less lens has no freshness to check — the age stays -1
          forever and the check would page on every tick).
        '';
      }
      {
        assertion = !cfg.monitoring.freshness.enable || !cfg.auth.enable;
        message = ''
          services.telephony.pbx-lens.monitoring.freshness reads /api/ops,
          which the identity session gate fronts when auth.enable is on —
          a credential-less check unit cannot cross it (fail-closed). Run
          the lens unauthenticated on loopback (the perimeter is the bind
          address) or consume /health/ready + the scrape target instead.
        '';
      }
      {
        assertion = !cfg.monitoring.freshness.enable || freshnessMaxAgeSeconds != null;
        message = ''
          services.telephony.pbx-lens.monitoring.freshness: cannot derive
          a fail threshold from pollEvery "${toString cfg.pollEvery}"
          (only simple spans like "15m" derive, at 3x cadence) — set
          monitoring.freshness.maxAgeSeconds explicitly.
        '';
      }
      {
        assertion = !cfg.csp.reportOnly || cfg.csp.nonce;
        message = ''
          services.telephony.pbx-lens.csp.reportOnly without csp.nonce
          emits no CSP at all (report-only switches the nonce policy's
          header, it does not create one) — set csp.nonce too.
        '';
      }
      {
        assertion =
          cfg.auth.oidc.issuer == null
          || (
            cfg.auth.oidc.clientId != null
            && cfg.auth.oidc.clientSecretFile != null
            && cfg.auth.oidc.redirectUrl != null
            && builtins.length cfg.auth.oidc.allowedGroups > 0
          );
        message = ''
          services.telephony.pbx-lens.auth.oidc.issuer needs clientId,
          clientSecretFile, redirectUrl and a non-empty allowedGroups —
          the group list is the security boundary (fail-closed) and the
          redirect must match the IdP-registered callback
          https://<host>/auth/oauth/pocketid/callback.
        '';
      }
    ];

    systemd.services.pbx-lens = {
      description = "pbx-lens — unified call-history index (read-only UI)";
      after = [
        "network-online.target"
      ]
      ++ lib.optionals (cfg.cdrFile != null) [
        # The CDR file lives under FreeSWITCH's DynamicUser-private
        # state; the ACL oneshot must have granted the group read
        # before the first poll pass walks the tree.
        "freeswitch.service"
        "telephony-fs-state-acl.service"
      ]
      ++ lib.optionals webhookIsBridgeLog [
        # Cold-start ordering: the bridge's DynamicUser state dir only
        # appears when telnyx-webhooks first starts, and systemd binds
        # an EMPTY directory when the BindReadOnlyPaths source does not
        # exist yet — without this ordering a fresh host binds emptiness.
        "telnyx-webhooks.service"
        "telephony-sms-store-acl.service"
      ]
      ++ lib.optionals readsRecordingsTree [
        # The shared recordings tree is created by this oneshot before
        # FreeSWITCH starts; ReadOnlyPaths over a missing dir fails the
        # unit. (Absent when recording is off — a dangling After target
        # is a no-op.)
        "telephony-recordings-dir.service"
      ];
      wants = [
        "network-online.target"
      ]
      ++ lib.optionals webhookIsBridgeLog [
        # Pull the bridge (and its ACL oneshot) when the lens is started
        # standalone on a fresh host: the bind below needs the bridge's
        # state dir to exist, and the files need their telephony-fs ACLs.
        "telnyx-webhooks.service"
        "telephony-sms-store-acl.service"
      ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        Type = "notify";
        # appkit sends READY=1 after the listener binds and STOPPING=1 at
        # the graceful drain; the binary feeds the watchdog at half this.
        WatchdogSec = "30";
        DynamicUser = true;
        StateDirectory = "pbx-lens";
        StateDirectoryMode = "0750";
        # CDR ingest reads FreeSWITCH's DynamicUser-private state through
        # the same three-layer path as the operator API (pbx.nix): the
        # ro bind is the only non-root way in (/var/lib/private is 0700
        # root), the telephony-fs group carries the POSIX ACLs, and the
        # supplementary group makes them effective for this unit's
        # ephemeral identity. Deploy contract: point cdrFile at the
        # bound path (/var/lib/telephony/freeswitch-ro/cdr-csv/
        # Master.csv), exactly like operatorApiArgs does.
        # The bridge JSONL rides the SAME three layers through the
        # messaging bind (shared.nix paths), and the recordings tree
        # (recordings + transcripts) through the telephony group —
        # both rendered by this module since the source-access grow,
        # replacing the live host's hand-wired overrides.
        SupplementaryGroups =
          lib.optionals (cfg.cdrFile != null || webhookIsBridgeLog) [ "telephony-fs" ]
          ++ lib.optionals readsRecordingsTree [ "telephony" ];
        BindReadOnlyPaths =
          lib.optionals (cfg.cdrFile != null) [
            "/var/lib/private/freeswitch:/var/lib/telephony/freeswitch-ro"
          ]
          ++ lib.optionals webhookIsBridgeLog [
            "${shared.messagingPrivateDir}:${shared.messagingRoDir}"
          ];
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
          ++ lib.optionals cfg.auth.enable (
            [
              "-auth-db ${cfg.stateDir}/identity.db"
              "-auth-origin ${cfg.auth.publicOrigin}"
            ]
            ++ lib.optionals (cfg.auth.oidc.issuer != null) [
              "-auth-oidc-issuer ${cfg.auth.oidc.issuer}"
              "-auth-oidc-client-id ${cfg.auth.oidc.clientId}"
              "-auth-oidc-secret-file \${CREDENTIALS_DIRECTORY}/oidc-client-secret"
              "-auth-oidc-redirect ${cfg.auth.oidc.redirectUrl}"
              "-auth-oidc-group ${lib.concatStringsSep "," cfg.auth.oidc.allowedGroups}"
            ]
          )
          ++ lib.optionals (cfg.recordingsDir != null) [
            "-recordings-dir ${cfg.recordingsDir}"
          ]
          ++ lib.optionals (cfg.pollEvery != null) [ "-poll-every ${cfg.pollEvery}" ]
          ++ lib.optionals (cfg.pollSince != null) [ "-poll-since ${cfg.pollSince}" ]
          ++ lib.optionals (cfg.pollDirection != null) [ "-poll-direction ${cfg.pollDirection}" ]
          ++ lib.optionals (cfg.aiDids != null) [
            "-ai-did ${lib.concatStringsSep "," cfg.aiDids}"
          ]
          ++ lib.optionals (cfg.pollMaxAge != null) [ "-max-age ${cfg.pollMaxAge}" ]
          ++ lib.optionals (cfg.recordingTimeout != null) [
            "-recording-timeout ${cfg.recordingTimeout}"
          ]
          ++ lib.optionals (cfg.cdrFile != null) [ "-cdr-file ${cfg.cdrFile}" ]
          ++ lib.optionals (cfg.webhookLog != null) [
            "-webhook-log ${
              if webhookIsBridgeLog then "${shared.messagingRoDir}/inbound.jsonl" else cfg.webhookLog
            }"
          ]
          ++ lib.optionals (cfg.transcriptsDir != null) [
            "-transcripts-dir ${cfg.transcriptsDir}"
          ]
        );
        LoadCredential =
          lib.optional (cfg.telnyxApiKeyFile != null) "telnyx-api-key:${cfg.telnyxApiKeyFile}"
          ++ lib.optional (
            cfg.auth.enable && cfg.auth.oidc.issuer != null
          ) "oidc-client-secret:${cfg.auth.oidc.clientSecretFile}";
        # CSP knobs (csp.*): rendered as serve-unit environment, exactly
        # the env pair the binary documents (CSP_NONCE=1 enables the
        # nonce policy, CSP_REPORT_ONLY=1 flips its header). Empty list
        # when both off — no CSP emitted, the default posture.
        Environment =
          lib.optional cfg.csp.nonce "CSP_NONCE=1" ++ lib.optional cfg.csp.reportOnly "CSP_REPORT_ONLY=1";
        # Read-only ingest sources: the lens never writes back to any of them.
        ReadOnlyPaths =
          lib.optionals (cfg.recordingsDir != null) [ cfg.recordingsDir ]
          ++ lib.optionals (cfg.transcriptsDir != null) [ cfg.transcriptsDir ];
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
      # Staging only, per pbx-lens's backup-rotation opinion
      # (docs/backup-rotation-opinion.md in the lens repo): pbx-lens never
      # rotates — it produces one verified snapshot and never deletes; the
      # host backup tool owns versioned retention and off-host shipping.
      description = "pbx-lens — nightly snapshot staging (index +, with auth.enable, the NOT-disposable identity.db; never rotates; the host backup tool owns retention and shipping)";
      serviceConfig = {
        Type = "oneshot";
        DynamicUser = true;
        # Same StateDirectory as pbx-lens.service: both units share the
        # dynamic user, so this one may read index.db and stage into
        # backups/ (sqlite VACUUM INTO + integrity_check inside the binary).
        StateDirectory = "pbx-lens";
        StateDirectoryMode = "0750";
        ExecStart = [
          (lib.concatStringsSep " " [
            (lib.getExe cfg.package)
            "backup"
            "-db ${cfg.stateDir}/index.db"
            "-out ${cfg.stateDir}/backups/index.db"
          ])
        ]
        ++ lib.optionals cfg.auth.enable [
          # The identity DB is NOT disposable (accounts, passkeys, sessions
          # are event-sourced state, not re-derivable from any source), so
          # it rides the same verified-snapshot staging as the index.
          (lib.concatStringsSep " " [
            (lib.getExe cfg.package)
            "backup"
            "-db ${cfg.stateDir}/identity.db"
            "-out ${cfg.stateDir}/backups/identity.db"
          ])
        ];
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        RestrictAddressFamilies = [ "AF_UNIX" ];
        MemoryDenyWriteExecute = true;
      };
      # systemd's StateDirectory mapping creates only the top-level dir;
      # sqlite's VACUUM INTO refuses to mkdir, so the staging subdir must
      # exist before the first fire (proven by the lens VM suite:
      # [rejection:lens.backup.vacuum] "unable to open database file"
      # without it).
      preStart = "${pkgs.coreutils}/bin/mkdir -p ${cfg.stateDir}/backups";
    };

    systemd.timers.pbx-lens-backup = lib.mkIf cfg.backup.enable {
      description = "pbx-lens — nightly snapshot staging schedule (staging only; host owns retention)";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.backup.calendar;
        RandomizedDelaySec = "10m";
        Persistent = true;
      };
    };

    systemd.services.pbx-lens-purge = lib.mkIf (cfg.retention.maxAge != null) {
      # Retires INDEX rows (call.retired tombstones in the disposable
      # index); every source stays authoritative and untouched. The
      # identity DB is deliberately OUT of scope here: accounts, passkeys,
      # and sessions never age out through retention.
      description = "pbx-lens — retention purge (tombstone index rows over the age window; sources untouched)";
      serviceConfig = {
        Type = "oneshot";
        DynamicUser = true;
        StateDirectory = "pbx-lens";
        StateDirectoryMode = "0750";
        ExecStart =
          lib.concatStringsSep " " [
            (lib.getExe cfg.package)
            "purge"
            "-db ${cfg.stateDir}/index.db"
            "-max-age ${cfg.retention.maxAge}"
          ]
          + lib.optionalString cfg.retention.dryRun " -dry-run";
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

    # /metrics scrape target (plan T14 in pbx-lens's closure plan): the
    # endpoint shares the UI address (loopback) and speaks Prometheus text
    # format (appkit_build_info carries the build version). Plain attrs so
    # the pass-through list stays scraper-agnostic.
    services.telephony.monitoring.scrapeJobs = lib.mkIf cfg.monitoring.scrape.enable [
      {
        job_name = "pbx-lens";
        targets = [ cfg.address ];
        metrics_path = "/metrics";
      }
    ];

    # Freshness check (monitoring.freshness.*): timer-driven oneshot that
    # fails (and pages, through the OnFailure alert lane) when the
    # poller's last pass is -1 or older than freshnessMaxAgeSeconds.
    # Timer-triggered only: a failed run must page, not retry into
    # oblivion — the next timer tick retries naturally.
    systemd.services.pbx-lens-freshness = lib.mkIf cfg.monitoring.freshness.enable {
      description = "pbx-lens — poller freshness check (stale above ${toString freshnessMaxAgeSeconds}s; fails loudly when the index stops passing)";
      unitConfig = lib.mkIf alertsActive { OnFailure = "telephony-alert@%N.service"; };
      serviceConfig = {
        Type = "oneshot";
        # /api/ops (the only surface carrying last_pass_age_seconds;
        # auth-gated when auth.enable — the assertion above keeps that
        # combination out of the build). jq extracts the age, awk does
        # the float compare.
        ExecStart = pkgs.writeShellScript "pbx-lens-freshness" ''
          set -eu
          age="$(${pkgs.curl}/bin/curl -fsS --max-time 10 http://${cfg.address}/api/ops \
            | ${pkgs.jq}/bin/jq -r '.last_pass_age_seconds // empty')"
          if [ -z "$age" ]; then
            echo "pbx-lens freshness: last_pass_age_seconds missing from /api/ops (serve broken or the payload shape moved)" >&2
            exit 1
          fi
          if ${pkgs.gawk}/bin/awk -v v="$age" -v max=${toString freshnessMaxAgeSeconds} 'BEGIN { exit !(v == -1 || v + 0 > max) }'; then
            echo "pbx-lens freshness STALE: last_pass_age_seconds=''${age}s exceeds max ${toString freshnessMaxAgeSeconds}s (-1 = never passed since boot)" >&2
            exit 1
          fi
          echo "pbx-lens freshness OK: last_pass_age_seconds=''${age}s (max ${toString freshnessMaxAgeSeconds}s)"
        '';
        NoNewPrivileges = true;
        DynamicUser = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
        PrivateDevices = true;
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
        ];
        MemoryDenyWriteExecute = true;
      };
    };

    systemd.timers.pbx-lens-freshness = lib.mkIf cfg.monitoring.freshness.enable {
      description = "pbx-lens — poller freshness check cadence";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "5m";
        OnUnitActiveSec = cfg.monitoring.freshness.interval;
      };
    };
  };
}
