# services.telephony.textagent: the supervised text-message agent.
#
# A loopback stdlib-Python service (text-agent.py, this directory) that
# gives the AI a presence on SMS while keeping the human in command:
#
#   * Conversation state: the messaging bridge's webhook JSONL (both
#     directions) is tailed into per-contact state — resume-safe across
#     restarts and logrotate copytruncate, deduped by event id.
#   * Drafts: on inbound (or on demand, or on a missed call) Gemini is
#     asked for a reply in the contact's language with an English gloss
#     and a confidence self-score; every decision lands in an audit
#     JSONL. A PLACEHOLDER API key fails closed: recording continues,
#     drafting answers an honest 503, zero API calls.
#   * Review API: loopback HTTP behind a bearer shared secret (the
#     webphone reads the same file — list/approve/edit/discard drafts,
#     on-demand draft, translate, suppression, memory, presence,
#     briefing, /health).
#   * Autopilot: modes off / drafts / after-hours / full — autonomous
#     sends ride the bridge's outbound gateway with an honest identity
#     signature, gated by confidence, the STOP suppression list, the
#     loop kill-switch and VIP protection. The gates ship WITH the
#     autonomy, never after it.
#   * Presence + missed calls ride the FreeSWITCH event socket (busy
#     while channels are up; ring-out without answer becomes a
#     follow-up draft, enriched with an agent transcript when one
#     exists); ESL-less deployments degrade to schedule-only presence.
#
# Data access (the operator's three-layer pattern, module-owned because
# both endpoints are module-owned): the bridge's DynamicUser-private
# state dir is reached through a read-only bind, the telephony-fs
# group carries the ACLs (telephony-sms-store-acl), and agent
# transcripts ride the shared telephony group.
#
# Contracts are pinned by tests/test_text_agent.py (stdlib unittest)
# and tests/eval.nix (unit/secret/bind asserts).
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.telephony;
  agent = cfg.textagent;
  shared = import ./shared.nix { inherit config lib; };
  inherit (shared) recordingsDir messagingPrivateDir messagingRoDir;
  transcriptsDir = "${recordingsDir}/transcripts";
  transcriptsAvailable = cfg.agent.enable && cfg.recording.enable;
in
{
  config = lib.mkIf (cfg.enable && agent.enable) {
    assertions = [
      {
        assertion = cfg.messaging.enable;
        message = "services.telephony.textagent requires messaging.enable (the conversation reader tails the bridge's webhook JSONL and autonomous sends ride the bridge's outbound gateway).";
      }
      {
        assertion = agent.apiKeyFile != null;
        message = "services.telephony.textagent.apiKeyFile is required when textagent is enabled (a PLACEHOLDER value fails drafting closed by design, but the file must exist or the unit cannot start).";
      }
      {
        assertion = agent.systemPromptFile != null;
        message = "services.telephony.textagent.systemPromptFile is required when textagent is enabled (the prompt is the agent's brain; it is a runtime file, not an inline option).";
      }
      {
        assertion = agent.sharedSecretFile != null;
        message = "services.telephony.textagent.sharedSecretFile is required when textagent is enabled (the review API authenticates every route except /health against it).";
      }
      {
        assertion = cfg.eventSocketPasswordFile != null || cfg.eventSocketPassword != "";
        message = "services.telephony.textagent needs the event socket for presence and missed calls: set eventSocketPasswordFile (or the inline eventSocketPassword in throwaway/demo postures).";
      }
      {
        assertion = agent.briefing.mailerCommand == null || (agent.briefing.fromAddress != "" && agent.briefing.toAddress != "");
        message = "services.telephony.textagent.briefing: a mailerCommand needs fromAddress and toAddress (the sendmail-style pipe is invoked as \"mailerCommand -f <from> -t <to>\").";
      }
    ];

    warnings =
      lib.optionals (agent.autopilot.signature == "") [
        "services.telephony.textagent.autopilot.signature is empty: autonomous sends go out unsigned. Honest identity is the trust story — every recipient deserves to know a machine answered."
      ]
      ++ lib.optionals (agent.autopilot.mode == "full") [
        "services.telephony.textagent.autopilot.mode is \"full\": every confident draft sends autonomously, around the clock. after-hours keeps the human in the loop while the desk is reachable."
      ];

    # Auto-wire the webphone review surfaces (mirrors the messaging
    # gateway auto-wire): URL + the SAME secret file the review API
    # authenticates against — one secret, two consumers. mkDefault
    # keeps explicit operator overrides possible.
    services.webphone.settings.textagent = lib.mkDefault {
      url = "http://127.0.0.1:${toString agent.httpPort}";
      secret_file = agent.sharedSecretFile;
    };

    systemd.services.telephony-textagent = {
      description = "Supervised text-message agent: drafts in the contact's language, human approves, autonomy carries an honest signature";
      wants = [ "network-online.target" ];
      after = [
        "network-online.target"
        "telnyx-webhooks.service"
        # The ACL oneshot must have granted the group read before the
        # first tail pass opens the JSONL (same ordering contract as
        # the operator API's SMS store read).
        "telephony-sms-store-acl.service"
      ];
      wantedBy = [ "multi-user.target" ];
      environment = {
        HTTP_PORT = toString agent.httpPort;
        GEMINI_API_BASE = agent.geminiApiBase;
        TEXTAGENT_OWNER_NAME = agent.ownerName;
        TEXTAGENT_LANGUAGES = lib.concatStringsSep "," agent.languages;
        TEXTAGENT_HISTORY_MESSAGES = toString agent.historyMessages;
        TEXTAGENT_DRAFT_TTL = toString agent.draftTtlSeconds;
        TEXTAGENT_MODE = agent.autopilot.mode;
        TEXTAGENT_WORKING_START = agent.autopilot.workingStart;
        TEXTAGENT_WORKING_END = agent.autopilot.workingEnd;
        TEXTAGENT_CONFIDENCE_THRESHOLD = toString agent.autopilot.confidenceThreshold;
        TEXTAGENT_SIGNATURE = agent.autopilot.signature;
        TEXTAGENT_MAX_AUTO = toString agent.autopilot.maxAutoPerConversation;
        TEXTAGENT_VIP = lib.concatStringsSep "," agent.vipNumbers;
        TEXTAGENT_OPT_OUT_KEYWORDS = lib.concatStringsSep "," agent.optOutKeywords;
        TEXTAGENT_BRIEFING_HOUR = toString agent.briefing.hour;
        TEXTAGENT_MISSED_CALL = if agent.missedCall.enable then "1" else "0";
        TEXTAGENT_MISSED_CALL_GRACE = toString agent.missedCall.transcriptGraceSeconds;
        TEXTAGENT_LENS_URL = if agent.lensUrl != null then agent.lensUrl else "";
        TEXTAGENT_LENS_CONTEXT_DAYS = toString agent.lensContextDays;
        TEXTAGENT_WEBHOOK_LOG = "${messagingRoDir}/inbound.jsonl";
        TEXTAGENT_BRIDGE_URL = "http://127.0.0.1:${toString cfg.messaging.port}";
        TEXTAGENT_OWN_DID = cfg.messaging.did;
        ESL_HOST = "127.0.0.1";
        ESL_PORT = "8021";
        ESL_PASSWORD = lib.mkIf (cfg.eventSocketPasswordFile == null) cfg.eventSocketPassword;
      }
      // (lib.optionalAttrs transcriptsAvailable {
        TEXTAGENT_TRANSCRIPTS_DIR = transcriptsDir;
      })
      // lib.optionalAttrs (agent.briefing.mailerCommand != null) {
        TEXTAGENT_MAILER_COMMAND = lib.getExe agent.briefing.mailerCommand;
        TEXTAGENT_BRIEFING_FROM = agent.briefing.fromAddress;
        TEXTAGENT_BRIEFING_TO = agent.briefing.toAddress;
      };
      serviceConfig = {
        ExecStart = "${pkgs.python3}/bin/python3 ${./text-agent.py}";
        StateDirectory = "telephony-textagent";
        DynamicUser = true;
        # Secrets ride $CREDENTIALS_DIRECTORY (systemd sources the files
        # as root at start; the 2026-10-01 outage lesson: the directory
        # is CREDENTIALS_DIRECTORY, never CREDENTIALS_DIR alone). The
        # gateway secret is the SAME file the bridge authenticates —
        # one value, two consumers, like the webphone gateway story.
        LoadCredential = [
          "gemini_key:${agent.apiKeyFile}"
          "system_prompt:${agent.systemPromptFile}"
          "shared_secret:${agent.sharedSecretFile}"
          "gateway_secret:${cfg.messaging.gatewaySecretFile}"
        ]
        ++ lib.optionals (cfg.eventSocketPasswordFile != null) [
          "esl_pass:${cfg.eventSocketPasswordFile}"
        ];
        # The bridge's DynamicUser-private JSONL is readable through
        # the ro bind + the telephony-fs ACLs (the operator pattern);
        # agent transcripts ride the shared telephony group.
        SupplementaryGroups = [ "telephony-fs" ]
        ++ lib.optionals transcriptsAvailable [ "telephony" ];
        BindReadOnlyPaths = [
          "${messagingPrivateDir}:${messagingRoDir}"
        ];
        Restart = "on-failure";
        RestartSec = 5;
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectHome = true;
        ProtectSystem = "strict";
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
          "AF_INET6"
        ];
      };
    };
  };
}
