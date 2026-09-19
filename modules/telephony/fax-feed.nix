# telephony.fax.feed: forward rxfax TIFFs to the webphone /hooks/fax
# webhook as PDFs (the webphone Fax tab renders PDFs, not TIFFs).
#
# Shape: a oneshot service sweeps the fax directory, converts each TIFF
# with tiff2pdf and POSTs it as pdf_base64 (Bearer-secret authenticated).
# A systemd path unit picks new faxes up within seconds; a timer sweep
# is the retry policy — a file that fails conversion or posting stays in
# place and is retried on the next sweep, so nothing is ever lost to a
# transient webphone outage.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.telephony;
  faxDir = "/var/lib/telephony/recordings/fax";

  poster = pkgs.writers.writePython3 "telephony-fax-feed-post" { } ''
    import base64
    import json
    import os
    import sys
    import urllib.request

    tif_path, pdf_path = sys.argv[1], sys.argv[2]
    secret = open(
        os.path.join(os.environ["CREDENTIALS_DIRECTORY"], "webphone-hook-secret")
    ).read().strip()
    url = os.environ["FAX_FEED_URL"].rstrip("/") + "/hooks/fax"
    pdf = open(pdf_path, "rb").read()
    body = json.dumps(
        {
            "owner": os.environ["FAX_FEED_OWNER"],
            "from": os.environ["FAX_FEED_FROM"],
            "pdf_base64": base64.b64encode(pdf).decode(),
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + secret,
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status != 202:
            sys.exit(f"webphone answered {resp.status}, want 202")
    print(f"fax-feed: posted {tif_path} ({len(pdf)} bytes pdf)")
  '';

  feedScript = pkgs.writeShellScript "telephony-fax-feed" ''
    set -euo pipefail
    shopt -s nullglob
    done_dir="${faxDir}/fed"
    mkdir -p "$done_dir"
    for tif in "${faxDir}"/*.tif "${faxDir}"/*.tiff; do
      base="$(basename "$tif")"
      pdf="$(mktemp)"
      if ! ${pkgs.libtiff}/bin/tiff2pdf -o "$pdf" "$tif"; then
        rm -f "$pdf"
        echo "fax-feed: tiff2pdf failed for $base (left for retry)" >&2
        continue
      fi
      if python3 ${poster} "$tif" "$pdf"; then
        mv -- "$tif" "$done_dir/$base"
      else
        echo "fax-feed: webphone rejected $base (left for retry)" >&2
      fi
      rm -f "$pdf"
    done
  '';
in
{
  config = lib.mkIf cfg.fax.feed.enable {
    assertions = [
      {
        assertion = cfg.fax.enable;
        message = "services.telephony.fax.feed.enable requires fax.enable (there are no rxfax TIFFs otherwise)";
      }
      {
        assertion = cfg.webphone.enable;
        message = "services.telephony.fax.feed.enable requires webphone.enable (the feed exists to serve the webphone Fax tab)";
      }
      {
        assertion = cfg.fax.feed.secretFile != null;
        message = "services.telephony.fax.feed.secretFile is required when feed.enable is true (webphone hooks fail closed without the secret)";
      }
    ];

    systemd.services.telephony-fax-feed = {
      description = "Feed rxfax TIFFs to the webphone fax webhook as PDFs";
      serviceConfig = {
        Type = "oneshot";
        Group = "telephony";
        LoadCredential = "webphone-hook-secret:${cfg.fax.feed.secretFile}";
        Environment = {
          FAX_FEED_URL = cfg.fax.feed.webphoneUrl;
          FAX_FEED_OWNER = cfg.fax.feed.owner;
          FAX_FEED_FROM = cfg.fax.feed.from;
        };
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ReadWritePaths = [ faxDir ];
      };
      script = feedScript;
    };

    systemd.paths.telephony-fax-feed = {
      description = "Watch the fax receive directory for new rxfax TIFFs";
      wantedBy = [ "multi-user.target" ];
      pathConfig = {
        PathModified = faxDir;
        Unit = "telephony-fax-feed.service";
      };
    };

    systemd.timers.telephony-fax-feed = {
      description = "Periodic retry sweep for unconverted fax TIFFs";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*:0/${toString cfg.fax.feed.sweepInterval}";
        Persistent = true;
        Unit = "telephony-fax-feed.service";
      };
    };
  };
}
