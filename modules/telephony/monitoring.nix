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

  passArg =
    if cfg.eventSocketPasswordFile != null then
      ''"$(cat ${lib.escapeShellArg cfg.eventSocketPasswordFile})"''
    else
      lib.escapeShellArg cfg.eventSocketPassword;
in
{
  config = lib.mkIf (cfg.enable && cfg.monitoring.enable) {
    systemd.services.telephony-health = {
      description = "Telephony health check: sofia profiles and gateway registrations";
      # Timer-triggered only: a failed run must be visible, not retried
      # into oblivion (the next timer tick retries naturally).
      serviceConfig = oneshotHardening // {
        Type = "oneshot";
        ExecStart = pkgs.writeShellScript "telephony-health" ''
          set -eu
          fs_cli() { ${pkgs.freeswitch}/bin/fs_cli -p ${passArg} -x "$1"; }

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
