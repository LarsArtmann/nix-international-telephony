# Agent VM E2E (plan T17): the REAL systemd wiring end to end — FreeSWITCH
# parks the 9100 dialplan leg, the telephony-agent unit picks it up over the
# event socket, greets, records one caller turn against the loopback Gemini
# stub (tests/gemini_stub.py), replies, and hangs the call up on the
# [ACTION: end] directive. Asserts the caller-visible outcomes (answer,
# streamed audio, server BYE) plus the on-host evidence (health esl:true,
# transcript reason agent_end, the recorded call WAV).
{ telephonyModule, webphonePackage }:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-agent";

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;

      environment.etc."vmclient.py".source = ./vmclient.py;
      environment.etc."gemini-stub.py".source = ./gemini_stub.py;

      services.telephony = {
        recording.enable = true;
        agent = {
          enable = true;
          extension = "9100";
          systemPromptFile = "/run/telephony-test/system-prompt";
          apiKeyFile = "/run/telephony-test/gemini-key";
          transferDestination = "2000";
          geminiApiBase = "http://127.0.0.1:8443";
          # Keep the loop tight: the caller turn ends at the cap while
          # the vmclient streams continuous noise (the VAD never sees
          # trailing silence), so turnMaxSeconds IS the turn length here.
          turnMaxSeconds = 6;
          silenceHits = 40;
        };
      };

      # The agent's LoadCredential sources must exist before its unit
      # starts (a missing source fails the unit 243/CREDENTIALS — the
      # documented failure signature).
      systemd.services.vm-agent-secrets = {
        description = "Seed telephony-agent credential files (VM test)";
        wantedBy = [ "multi-user.target" ];
        before = [ "telephony-agent.service" ];
        serviceConfig.Type = "oneshot";
        script = ''
          install -Dm600 /dev/null /run/telephony-test/gemini-key
          printf '%s' 'vm-test-key-not-a-placehol' > /run/telephony-test/gemini-key
          install -Dm600 /dev/null /run/telephony-test/system-prompt
          printf '%s' 'You are the VM-test agent.' > /run/telephony-test/system-prompt
        '';
      };

      systemd.services.gemini-stub = {
        description = "Loopback Gemini API stub for the agent VM test";
        wantedBy = [ "multi-user.target" ];
        before = [ "telephony-agent.service" ];
        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.python3}/bin/python3 /etc/gemini-stub.py 8443";
          Restart = "on-failure";
        };
      };
    };

  testScript = _: ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    machine.wait_for_unit("gemini-stub.service")
    machine.wait_for_unit("telephony-agent.service")

    # The health endpoint is the agent's only loopback-visible liveness:
    # esl:true proves the event-socket leg came up.
    machine.wait_until_succeeds(
        "curl -fsS http://127.0.0.1:8070/health | grep -q '\"esl\": true'",
        timeout=datetime.timedelta(seconds=60),
    )

    sip_ip = sip_server(machine)
    vmclient = "python3 /etc/vmclient.py --server " + sip_ip + " --domain pbx.test "

    # Dial the agent: answered, greeting + reply stream back as RTP,
    # the stub's [ACTION: end] hangs the call up server-side.
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "join --to 9100 --seconds 20"
    )
    assert "VM-JOIN-ANSWERED" in out, out
    join_bytes = 0
    for line in out.splitlines():
        if line.startswith("VM-JOIN-RTP"):
            join_bytes = int(line.split("bytes=")[1].split()[0])
    # Greeting + the spoken reply are the stub's two 0.4 s WAV bursts
    # (~40 RTP packets, ~6.9 kB measured); a dead (silent) agent leg
    # lands in the hundreds. The parked channel sends no filler RTP
    # while the turn records (uuid_record + agent-side VAD), so the
    # received bytes are exactly what was spoken.
    assert join_bytes > 4000, f"agent leg streamed only {join_bytes} bytes:\n{out}"
    assert "VM-JOIN-BYE" in out, f"agent did not hang the call up (stub end action):\n{out}"

    # On-host evidence: the transcript ended via the model's directive
    # and the call recording landed in the shared recordings dir.
    machine.wait_until_succeeds(
        "grep -q '\"reason\": \"agent_end\"' /var/lib/telephony/recordings/transcripts/*.jsonl",
        timeout=datetime.timedelta(seconds=30),
    )

    # vm-speech-then-stop (2026-10-29): stream noise (the caller speaks),
    # then go SILENT mid-call — the agent-side VAD must close the turn on
    # trailing silence (the recorder + GrowingWav are REAL FreeSWITCH
    # uuid_record; only STT/LLM/TTS are the stub), the stub replies and
    # ends, and the server hangs up INSIDE the listening window. A broken
    # VAD keeps recording until the no-speech cap instead — the hangup
    # marker distinguishes the two.
    sts = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "speech-then-stop --to 9100 --speak-seconds 6 --listen-seconds 30"
    )
    assert "VM-STS-ANSWERED" in sts, sts
    assert "VM-STS-SPEECH-DONE" in sts, sts
    assert "VM-SERVER-HANGUP yes" in sts, (
        "agent never hung up after the caller went silent — the VAD "
        f"trailing-silence close did not fire:\n{sts}"
    )
    machine.succeed("ls /var/lib/telephony/recordings/*.wav >/dev/null")

    machine.succeed(
        "curl -fsS http://127.0.0.1:8070/health | grep -q '\"calls_total\": 1'"
    )
  '';
}
