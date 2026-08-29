# SIP scanner resistance: an option-gated fail2ban jail that watches the
# FreeSWITCH LOG FILE for auth failures and bans repeat offenders at the
# firewall. The failregex matches the source-verified sofia_reg.c line
#   "SIP auth failure (REGISTER|INVITE) on sofia profile '...' for [..] from ip X"
# — the "challenge" variant is normal first-contact behaviour and must
# NOT be counted.
#
# The jail reads the FILE, not the journal: after startup FreeSWITCH's
# console logger detaches ("We've become an orphan, no more console for
# us") and post-startup lines like the auth failures NEVER reach the
# journal — only /var/lib/freeswitch/log/freeswitch.log (observed live;
# the journal-based design could never work). The generator's internal
# profile sets log-auth-failures=true so sofia emits the line at all.
{
  config,
  lib,
  ...
}:

let
  cfg = config.services.telephony;
in
{
  config = lib.mkIf (cfg.enable && cfg.fail2ban.enable) {
    services.fail2ban = {
      enable = true;
      jails.freeswitch-sip.settings = {
        enabled = true;
        filter = "freeswitch-sip";
        backend = "auto";
        logpath = "/var/lib/private/freeswitch/log/freeswitch.log";
        # The PBX never REGISTERs against itself, and ignoreself would
        # ALSO skip every address bound on lo — exactly what the VM test
        # (and any operator probing from the host) uses as a source.
        ignoreself = false;
        inherit (cfg.fail2ban) maxretry findtime bantime;
      };
    };

    environment.etc."fail2ban/filter.d/freeswitch-sip.conf".text = ''
      [Definition]
      failregex = SIP auth failure \((?:REGISTER|INVITE)\) on sofia profile '.*' for \[.*\] from ip <HOST>
    '';

    # The jail tails FreeSWITCH's log file, which the daemon opens a few
    # seconds AFTER systemd marks it started — fail2ban hard-fails when
    # the file is missing at config time. Order behind freeswitch and
    # wait for the file before letting fail2ban configure its jails.
    systemd.services.fail2ban = {
      after = [ "freeswitch.service" ];
      wants = [ "freeswitch.service" ];
      preStart = ''
        for i in $(seq 1 60); do
          test -f /var/lib/private/freeswitch/log/freeswitch.log && exit 0
          sleep 1
        done
        echo "freeswitch log file never appeared" >&2
        exit 1
      '';
    };
  };
}
