# Health monitoring: a timer-driven check unit that fails loudly when the
# stack is sick — sofia profiles down or gateway registrations lost. A
# failed systemd unit is the alert: point your favourite notifier at
# `OnFailure=` of `telephony-health.service`, or watch the journal.
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };
  inherit (shared) oneshotHardening;

  # Gateways whose REG state must be REGED (register = true only; NOREG is
  # the expected state for peer-to-peer trunks).
  registeredGateways = lib.filterAttrs (_: g: g.register) cfg.gateways;

  passArg = shared.eventSocketPasswordShellArg;

  # The webphone app's loopback port (one derivation, shared.nix: the
  # nginx vhost and the metrics scrape target read the same value).
  webphonePort = shared.webphonePort;
in
{
  config = lib.mkIf (cfg.enable && cfg.monitoring.enable) {
    systemd.services.telephony-health = {
      description = "Telephony health check: sofia profiles and gateway registrations";
      # Timer-triggered only: a failed run must be visible, not retried
      # into oblivion (the next timer tick retries naturally). Unlike the
      # file-writing oneshots, this unit opens a TCP connection to the
      # event socket — allow AF_INET, scoped to loopback.
      serviceConfig = oneshotHardening // {
        Type = "oneshot";
        RestrictAddressFamilies = [
          "AF_UNIX"
          "AF_INET"
        ];
        IPAddressAllow = [ "localhost" ];
        IPAddressDeny = [ "any" ];
        ExecStart = pkgs.writeShellScript "telephony-health" ''
          set -eu
          # -H is REQUIRED: fs_cli's builtin profile carries an EMPTY host,
          # so a bare call dies "Error Connecting []" against a perfectly
          # healthy socket (proven against the 1.11.1 binary, 2026-10-08) —
          # without it this unit reported "event socket unresponsive"
          # unconditionally.
          fs_cli() { ${config.services.freeswitch.package}/bin/fs_cli -H 127.0.0.1 -p ${passArg} -x "$1"; }

          # The event socket answering at all is the first health signal.
          # Bounded retries: mod_event_socket accepts connections slightly
          # after its listener appears on cold boots — that race must not
          # raise a false alarm, while a genuinely dead socket still fails.
          status=""
          connected=0
          for attempt in 1 2 3 4 5; do
            if status=$(fs_cli 'sofia status'); then
              connected=1
              break
            fi
            sleep 2
          done
          if [ "$connected" != 1 ]; then
            echo "telephony-health: event socket unresponsive (fs_cli failed)" >&2
            exit 1
          fi

          echo "$status" | grep -q 'internal.*RUNNING' || {
            echo "telephony-health: sofia profile internal is not RUNNING" >&2
            exit 1
          }
          echo "$status" | grep -q 'external.*RUNNING' || {
            echo "telephony-health: sofia profile external is not RUNNING" >&2
            exit 1
          }
          ${lib.optionalString (cfg.trunkProfilePort != null) ''
            # The dedicated outbound profile is invisible to every other
            # gate: a dead trunk profile keeps internal/external green
            # while every outbound call dies 502/GATEWAY_DOWN.
            echo "$status" | grep -q 'trunk.*RUNNING' || {
              echo "telephony-health: sofia profile trunk is not RUNNING" >&2
              exit 1
            }
          ''}
          ${lib.optionalString cfg.webphone.enable ''
            # The webphone UI is a service that can die quietly since the v2
            # switchover; /healthz is the app's own readiness probe (open GET,
            # pings its SQLite — a 200 proves both unit-up and ready). The
            # curl targets the same loopback address nginx proxies to.
            ${pkgs.curl}/bin/curl -fsS --max-time 5 -o /dev/null \
            "http://127.0.0.1:${webphonePort}/healthz" || {
            echo "telephony-health: webphone /healthz probe failed (service down or not ready)" >&2
            exit 1
            }
          ''}
          ${lib.optionalString cfg.ringhook.enable ''
            # The ring-while-closed shim is the one stack service whose death
            # is SILENT by contract: webphone answers nothing (push may just
            # have no devices) and the dialplan never depends on it, so a dead
            # shim quietly stops every closed-app ring until someone notices.
            # The shim's own /ringhook/health answers 200 while the listener
            # lives — exactly the /healthz pattern above.
            ${pkgs.curl}/bin/curl -fsS --max-time 5 -o /dev/null \
            "http://127.0.0.1:${toString cfg.ringhook.port}/ringhook/health" || {
            echo "telephony-health: ringhook shim /ringhook/health probe failed (ring-while-closed is down)" >&2
            exit 1
            }
          ''}
          ${lib.optionalString cfg.agent.enable ''
            # The voice agent's endpoint is LOOPBACK-ONLY: a dead agent is
            # invisible to every external probe, so this timer is its only
            # watchdog. The esl flag matters as much as the 200 — an agent
            # that is up but ESL-disconnected answers nothing (the 2026-10-05
            # outage class: the ESL leg died and no gate noticed). Bounded
            # retries absorb the reconnect race after a FreeSWITCH restart
            # (the agent reconnects with a short backoff).
            agent_esl=0
            for attempt in 1 2 3; do
              agent_health=$(${pkgs.curl}/bin/curl -fsS --max-time 5 \
                "http://127.0.0.1:${toString cfg.agent.httpPort}/health") || {
                echo "telephony-health: agent /health probe failed (attempt $attempt)" >&2
                sleep 3
                continue
              }
              if echo "$agent_health" | grep -q '"esl": *true'; then
                agent_esl=1
                break
              fi
              echo "telephony-health: agent ESL leg down (attempt $attempt): $agent_health" >&2
              sleep 3
            done
            if [ "$agent_esl" != 1 ]; then
              echo "telephony-health: agent is down or ESL-disconnected" >&2
              exit 1
            fi
          ''}
          ${lib.optionalString (cfg.monitoring.requireGatewayReg && registeredGateways != { }) ''
            # A losing registration means no PSTN calls in or out.
            ${lib.concatMapStrings (name: ''
              gw_status=$(fs_cli 'sofia status gateway ${name}') || {
                echo "telephony-health: gateway ${name} status query failed" >&2
                exit 1
              }
              echo "$gw_status" | grep -q 'State:[[:space:]]*REGED' || {
                echo "telephony-health: gateway ${name} is not REGED:" >&2
                echo "$gw_status" | grep 'State:' >&2
                exit 1
              }
            '') (builtins.attrNames registeredGateways)}
          ''}
          echo "telephony-health: ok"
        '';
      };
    };

    systemd.timers.telephony-health = {
      description = "Run the telephony health check periodically";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnBootSec = "2min";
        OnUnitActiveSec = "${toString cfg.monitoring.intervalSec}s";
        AccuracySec = "10s";
      };
    };
  };
}
