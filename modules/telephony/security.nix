# SIP scanner resistance: an option-gated fail2ban jail that watches the
# FreeSWITCH journal for auth failures and bans repeat offenders at the
# firewall. The failregex matches the source-verified sofia_reg.c line
#   "SIP auth failure (REGISTER|INVITE) on sofia profile '...' for [..] from ip X"
# — the "challenge" variant is normal first-contact behaviour and must
# NOT be counted.
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
        backend = "systemd";
        journalmatch = "_SYSTEMD_UNIT=freeswitch.service";
        inherit (cfg.fail2ban) maxretry findtime bantime;
      };
    };

    environment.etc."fail2ban/filter.d/freeswitch-sip.conf".text = ''
      [Definition]
      failregex = SIP auth failure \((?:REGISTER|INVITE)\) on sofia profile '.*' for \[.*\] from ip <HOST>
      journalmatch = _SYSTEMD_UNIT=freeswitch.service
    '';
  };
}
