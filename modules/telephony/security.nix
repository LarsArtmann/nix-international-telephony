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
#
# With the webphone served (default), fail2ban.nginxScanner adds a second
# jail for the HTTPS surface: the vhost's access log (pinned to a
# deterministic path by web.nix) is tailed for scanner probes (wp-login,
# phpMyAdmin, .env, ...) and repeat probes are banned from port 443.
{
  config,
  lib,
  ...
}:

let
  cfg = config.services.telephony;
  shared = import ./shared.nix { inherit config lib; };
  nginxScannerActive = cfg.fail2ban.enable && cfg.fail2ban.nginxScanner.enable && cfg.webphone.enable;
  caddyScannerActive = cfg.fail2ban.enable && cfg.fail2ban.caddyScanner.enable;
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
      jails.nginx-scanner = lib.mkIf nginxScannerActive {
        settings = {
          enabled = true;
          filter = "telephony-nginx-scanner";
          backend = "auto";
          logpath = shared.nginxScannerLog;
          port = 443;
          # Same trap as the SIP jail: ignoreself skips every address
          # bound on lo — the addresses operators (and tests) probe from.
          ignoreself = false;
          inherit (cfg.fail2ban) maxretry findtime bantime;
        };
      };

      # The external-edge twin (decision D4): same scanner paths, same
      # 4xx-only strike count, caddy JSON access-log lines instead of
      # nginx combined format.
      jails.caddy-scanner = lib.mkIf caddyScannerActive {
        settings = {
          enabled = true;
          filter = "telephony-caddy-scanner";
          backend = "auto";
          logpath = cfg.fail2ban.caddyScanner.logPath;
          port = 443;
          ignoreself = false;
          inherit (cfg.fail2ban) maxretry findtime bantime;
        };
      };
    };

    environment.etc."fail2ban/filter.d/freeswitch-sip.conf".text = ''
      [Definition]
      failregex = SIP auth failure \((?:REGISTER|INVITE)\) on sofia profile '.*' for \[.*\] from ip <HOST>
    '';

    # Scanner probes against the webphone vhost (nginx "combined" format;
    # the paths internet scanners hammer first). 4xx status keeps
    # happy-path assets (200s from a stale CDN link, a renamed file) out
    # of the strike count. NOTE: fail2ban strips the matched date region
    # from the line before applying failregex, so the pattern must not
    # span the [timestamp] — use `.*` across it (verified with
    # fail2ban-regex against a real combined-format line).
    environment.etc."fail2ban/filter.d/telephony-nginx-scanner.conf".text = ''
      [Definition]
      failregex = ^<HOST> .*"(?:GET|POST|HEAD|PUT|DELETE|OPTIONS) [^"]*(?:wp-login|xmlrpc\.php|/\.env|\.git|phpmyadmin|phpMyAdmin|/\.aws/|vendor/phpunit|\.asp|\.aspx|\.sql)[^"]*" 4\d\d
    '';

    # Caddy JSON lines (the web.edge = "external" access log): the
    # remote_ip is the ban target, the uri carries the scanner path,
    # and status 4xx keeps happy-path assets out of the strike count.
    # Order-independent via lookaheads (caddy emits the request object
    # before the status); the epoch ts is fail2ban's date anchor.
    environment.etc."fail2ban/filter.d/telephony-caddy-scanner.conf".text = ''
      [Definition]
      datepattern = "ts":{epoch}
      failregex = "remote_ip":"<HOST>"(?=.*"uri":"[^"]*(?:wp-login|xmlrpc\.php|/\.env|\.git|phpmyadmin|phpMyAdmin|/\.aws/|vendor/phpunit|\.asp|\.aspx|\.sql)[^"]*")(?=.*"status":4\d\d)
    '';

    # Both jails tail log files that appear a few seconds AFTER systemd
    # marks their services started — fail2ban hard-fails when a logpath
    # is missing at config time. Order behind the producers and wait for
    # (or create) the files before letting fail2ban configure its jails.
    systemd.services.fail2ban = {
      after = [
        "freeswitch.service"
      ]
      ++ lib.optionals nginxScannerActive [ "nginx.service" ]
      ++ lib.optionals caddyScannerActive [ "caddy.service" ];
      wants = [
        "freeswitch.service"
      ]
      ++ lib.optionals nginxScannerActive [ "nginx.service" ]
      ++ lib.optionals caddyScannerActive [ "caddy.service" ];
      preStart = ''
        for i in $(seq 1 60); do
          test -f /var/lib/private/freeswitch/log/freeswitch.log && break
          sleep 1
        done
        if [ ! -f /var/lib/private/freeswitch/log/freeswitch.log ]; then
          echo "freeswitch log file never appeared" >&2
          exit 1
        fi
        ${
          # nginx's master opens the access log as root and hands the fd
          # to its workers, so a pre-created root-owned file is fine —
          # create it eagerly (idempotent) so the jail never starts with
          # a missing logpath.
          lib.optionalString nginxScannerActive ''
            test -f ${shared.nginxScannerLog} || install -m 0640 -o nginx -g nginx /dev/null ${shared.nginxScannerLog}
          ''
        }
        ${
          # caddy opens its access log itself; create the PARENT dir + an
          # empty file eagerly so fail2ban never starts against a missing
          # logpath (same class, different owner — the caddy user owns
          # this one).
          lib.optionalString caddyScannerActive ''
            mkdir -p $(dirname ${cfg.fail2ban.caddyScanner.logPath})
            test -f ${cfg.fail2ban.caddyScanner.logPath} || install -m 0640 -o caddy -g caddy /dev/null ${cfg.fail2ban.caddyScanner.logPath}
          ''
        }
      '';
    };
  };
}
