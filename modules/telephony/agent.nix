# services.telephony.agent: the Gemini AI voice agent.
#
# A loopback stdlib-Python service (voice-agent.py, this directory) that
# drives answered calls over the FreeSWITCH event socket: play a
# TTS-rendered greeting, then loop "record utterance -> transcribe ->
# chat -> speak" against Google's Gemini API until the model asks for a
# transfer ([ACTION: transfer] to agent.transferDestination) or an end
# ([ACTION: end]), the caller dials 0, or a turn/time cap trips.
#
#   * Inbound reach: agent.answerDids (intercepted in the public
#     dialplan before the gateway didDestination) and the internal
#     agent.extension.
#   * Full-call recording is the dialplan's job (the agent extension
#     carries the same recordingActions as every other path) and
#     therefore requires recording.enable; this service only writes
#     per-turn WAVs (deleted after transcription) and the JSONL
#     transcript next to the call recording.
#   * Secrets ride $CREDENTIALS_DIRECTORY (LoadCredential): the Gemini API
#     key, the event-socket password and the system prompt (the
#     agent's brain, read per call so an edit plus a unit restart
#     reprograms it).
#   * GET /health on the loopback httpPort reports liveness and the
#     credential state (a PLACEHOLDER* API key fails closed honestly:
#     callers get a farewell and a transfer to the human destination
#     when one is configured).
#
# Honest limits (v1): turn-based conversation, no barge-in; endpointing
# is the record app's silence detector; DTMF-0 transfers land at the
# next step boundary (worst case one turn later).
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };
  inherit (shared) recordingsDir gatewaysForFs;
in
{
  config = lib.mkIf (cfg.enable && cfg.agent.enable) {
    assertions = [
      {
        assertion = cfg.recording.enable;
        message = "services.telephony.agent requires recording.enable (agent calls are calls; the agent extension records through the same path as every other dialplan destination).";
      }
      {
        assertion = cfg.agent.systemPromptFile != null;
        message = "services.telephony.agent.systemPromptFile is required when agent is enabled (the system prompt is the agent's brain; it is a runtime file, not an inline option, so prompts with personal data stay out of the store).";
      }
      {
        assertion = cfg.agent.apiKeyFile != null;
        message = "services.telephony.agent.apiKeyFile is required when agent is enabled (a PLACEHOLDER value fails closed by design, but the file must exist or the unit cannot start).";
      }
      {
        assertion = cfg.eventSocketPasswordFile != null || cfg.eventSocketPassword != "";
        message = "services.telephony.agent needs the event socket: set eventSocketPasswordFile (or the inline eventSocketPassword in throwaway/demo postures) — the agent authenticates with the same secret.";
      }
      {
        assertion = lib.all (
          did: lib.any (gateway: gateway.did == did) (lib.attrValues gatewaysForFs)
        ) cfg.agent.answerDids;
        message = "services.telephony.agent.answerDids: every DID must be the did of a configured gateway (the interception happens in the public dialplan's DID handling).";
      }
    ];

    warnings = lib.mkIf (cfg.agent.transferDestination == null) [
      "services.telephony.agent.transferDestination is null: transfer requests ([ACTION: transfer], caller DTMF 0) end the call with a farewell instead of reaching a human."
    ];

    systemd.services.telephony-agent = {
      description = "Gemini AI voice agent: drives answered calls over the FreeSWITCH event socket";
      after = [
        "network-online.target"
        "freeswitch.service"
      ]
      ++ lib.optionals cfg.recording.enable [ "telephony-recordings-dir.service" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];
      environment = {
        ESL_HOST = "127.0.0.1";
        ESL_PORT = "8021";
        ESL_PASSWORD = lib.mkIf (cfg.eventSocketPasswordFile == null) cfg.eventSocketPassword;
        GEMINI_API_BASE = cfg.agent.geminiApiBase;
        GEMINI_LLM_MODEL = cfg.agent.llmModel;
        GEMINI_TTS_MODEL = cfg.agent.ttsModel;
        GEMINI_VOICE = cfg.agent.voice;
        GEMINI_LANGUAGE = cfg.agent.language;
        AGENT_GREETING = cfg.agent.greeting;
        AGENT_TRANSFER_DESTINATION =
          if cfg.agent.transferDestination != null then cfg.agent.transferDestination else "";
        AGENT_MAX_TURNS = toString cfg.agent.maxTurns;
        AGENT_TURN_MAX_SECONDS = toString cfg.agent.turnMaxSeconds;
        AGENT_MAX_CALL_SECONDS = toString cfg.agent.maxCallSeconds;
        AGENT_SILENCE_THRESHOLD = toString cfg.agent.silenceThreshold;
        AGENT_SILENCE_HITS = toString cfg.agent.silenceHits;
        AGENT_TURNS_DIR = "${recordingsDir}/ai-turns";
        AGENT_TRANSCRIPTS_DIR = "${recordingsDir}/transcripts";
        HTTP_PORT = toString cfg.agent.httpPort;
      };
      serviceConfig = {
        ExecStart = "${pkgs.python3}/bin/python3 ${./voice-agent.py}";
        StateDirectory = "telephony-agent";
        DynamicUser = true;
        # The event-socket password, the API key and the system prompt are
        # read once at start (LoadCredential files are start-time copies;
        # a prompt edit plus `systemctl restart telephony-agent`
        # reprograms the agent); systemd sources the files as root, so no
        # supplementary path access is needed. The inline-password demo
        # posture rides the environment instead (that secret is already
        # store-plaintext by demo convention).
        LoadCredential = [
          "gemini_key:${cfg.agent.apiKeyFile}"
          "system_prompt:${cfg.agent.systemPromptFile}"
        ]
        ++ lib.optionals (cfg.eventSocketPasswordFile != null) [
          "esl_pass:${cfg.eventSocketPasswordFile}"
        ];
        # Writes only under the shared recordings dir (turn WAVs +
        # transcripts); the group is the recordings story shared with
        # FreeSWITCH (writer) and nginx (serves them when
        # recording.serve is on).
        SupplementaryGroups = [ "telephony" ];
        ReadWritePaths = [ recordingsDir ];
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

    # Turn + transcript directories under the shared recordings dir: the
    # setgid bit keeps new files group-owned by telephony (the nginx
    # serving story), tmpfiles creates the parents if needed so the unit
    # does not depend on recording.enable's oneshot having run first.
    systemd.tmpfiles.rules = [
      "d ${recordingsDir}/ai-turns 2770 root telephony - -"
      "d ${recordingsDir}/transcripts 2770 root telephony - -"
    ];
  };
}
