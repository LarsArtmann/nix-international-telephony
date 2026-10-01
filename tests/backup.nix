# Resilience VM test: restic backups round-trip PBX state, and a
# failing supervised unit routes a webhook alert through
# telephony-alert@<unit> (real HTTP sink, real failure).
{ telephonyModule, webphonePackage }:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-backup";

  nodes.machine =
    { config, pkgs, ... }:
    {
      imports = common.baseNode;

      environment.systemPackages = [ pkgs.restic ];

      # Minimal HTTP sink accepting POSTs; bodies land in /tmp/alert-sink.log.
      environment.etc."alert-sink.py".text = ''
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8", "replace")
                with open("/tmp/alert-sink.log", "a") as log:
                    log.write(body + "\n--\n")
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        HTTPServer(("127.0.0.1", 18080), Handler).serve_forever()
      '';

      services.telephony = {
        monitoring.enable = true;
        fail2ban.enable = true;
        # Master.csv rides in the snapshot like on the prod template
        # (pbx-prod sets this too).
        cdr.enable = true;
        backups = {
          enable = true;
          repository = "/var/lib/telephony-backup-repo";
          passwordFile = "/run/telephony-restic-password";
          # /etc/ssh rides along like in the pbx-prod template: the
          # host-key identity must survive a disaster restore. The
          # module-owned state.paths (recordings, cdr-csv, the webphone
          # snapshot dir) join the same way the prod template consumes
          # them — this suite therefore proves the mechanism prod uses.
          paths = [
            "/var/lib/private/freeswitch"
            "/etc/ssh"
          ]
          ++ config.services.telephony.state.paths;
        };
        alerts.url = "http://127.0.0.1:18080/alert";
      };

      # Generates the /etc/ssh host keys the backup path expects.
      services.openssh.enable = true;

      system.activationScripts.telephonyTestSecrets.text = ''
        echo "test-restic-password" > /run/telephony-restic-password
        chmod 600 /run/telephony-restic-password
      '';
    };

  testScript = ''
    import json

    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")

    # --- Backups: a real restic round-trip (backup, listing, RESTORE) ---
    # Written through the DynamicUser state dir (/var/lib/freeswitch is
    # a symlink to /var/lib/private/freeswitch; restic archives links
    # as links — the backup path must be the real directory).
    machine.succeed(
        "echo backup-canary-7812 > /var/lib/private/freeswitch/backup-canary")

    # Webphone data reaches restic ONLY as upstream's online snapshot:
    # the Wants/After wiring must pull webphone-backup (sqlite .backup
    # + blob rsync) in ahead of the restic run, fresh, every time.
    wants = machine.succeed(
        "systemctl show -p Wants restic-backups-telephony.service")
    assert "webphone-backup.service" in wants, wants
    machine.wait_for_unit("webphone.service")
    machine.wait_until_succeeds("test -f /var/lib/webphone/webphone.db")
    machine.succeed(
        "mkdir -p /var/lib/webphone/files"
        " && echo webphone-blob-canary-4d5e > /var/lib/webphone/files/blob-canary")

    # Recordings and CDR canaries: the state.paths entries prod rides on.
    machine.succeed(
        "echo recording-canary-8f21 > /var/lib/telephony/recordings/rec-canary.wav")
    machine.succeed(
        "mkdir -p /var/lib/private/freeswitch/cdr-csv"
        " && echo '\"cdr-canary\",\"row\",\"2026-10-01\"' "
        " > /var/lib/private/freeswitch/cdr-csv/Master.csv")

    machine.succeed("systemctl start restic-backups-telephony.service")
    # The pulled-in snapshot must exist and carry the blob (fresh, not
    # a leftover from some earlier run: this is its first run).
    machine.succeed("test -f /var/lib/webphone-backup/webphone.db")
    snapshots = json.loads(
        machine.succeed(
            "restic -r /var/lib/telephony-backup-repo"
            " -p /run/telephony-restic-password snapshots --json"))
    assert snapshots, "no restic snapshot after backup run"
    listing = machine.succeed(
        "restic -r /var/lib/telephony-backup-repo"
        " -p /run/telephony-restic-password ls latest")
    assert "backup-canary" in listing, listing[-2000:]
    assert "webphone-backup/webphone.db" in listing, listing[-2000:]
    assert "webphone-backup/files/blob-canary" in listing, listing[-2000:]
    assert "recordings/rec-canary.wav" in listing, listing[-2000:]
    assert "cdr-csv/Master.csv" in listing, listing[-2000:]
    # The SSH host-key identity rides in the snapshot (the prod template
    # backs up /etc/ssh for exactly this).
    assert "ssh_host_ed25519_key" in listing, listing[-2000:]
    machine.succeed("systemctl is-enabled restic-backups-telephony.timer")
    machine.succeed("systemctl is-enabled webphone-backup.timer")

    # --- Restore drill, asserted: lose the canary, restore the snapshot,
    # get the exact bytes back (recovery proven, not just the backup) ---
    machine.succeed("rm /var/lib/private/freeswitch/backup-canary")
    machine.succeed(
        "restic -r /var/lib/telephony-backup-repo"
        " -p /run/telephony-restic-password restore latest --target /tmp/restore")
    restored = machine.succeed(
        "cat /tmp/restore/var/lib/private/freeswitch/backup-canary")
    assert restored.strip() == "backup-canary-7812", restored
    host_key = machine.succeed(
        "head -1 /tmp/restore/etc/ssh/ssh_host_ed25519_key")
    assert "OPENSSH PRIVATE KEY" in host_key, host_key

    # The three new canaries restore byte-exact: recordings (state.paths
    # entry), CDR rows and the webphone snapshot (blob + db).
    rec = machine.succeed(
        "cat /tmp/restore/var/lib/telephony/recordings/rec-canary.wav")
    assert rec.strip() == "recording-canary-8f21", rec
    cdr = machine.succeed(
        "cat /tmp/restore/var/lib/private/freeswitch/cdr-csv/Master.csv")
    assert cdr.strip() == '"cdr-canary","row","2026-10-01"', cdr
    blob = machine.succeed(
        "cat /tmp/restore/var/lib/webphone-backup/files/blob-canary")
    assert blob.strip() == "webphone-blob-canary-4d5e", blob
    machine.succeed(
        "test -s /tmp/restore/var/lib/webphone-backup/webphone.db")
    # A restored webphone.db must be a REAL sqlite file (the online
    # snapshot used sqlite's backup API, not a torn hot copy).
    db_magic = machine.succeed(
        "head -c 15 /tmp/restore/var/lib/webphone-backup/webphone.db")
    assert "SQLite format 3" in db_magic, db_magic

    # --- Alert routing: OnFailure hooks are wired (%N = bare unit name) ---
    # `systemctl show` reports the specifier EXPANDED (systemd resolves %N
    # at load), so assert the per-unit expanded form, not the %N literal.
    for unit in ["restic-backups-telephony", "telephony-health", "fail2ban"]:
        on_failure = machine.succeed("systemctl show -p OnFailure " + unit)
        assert f"telephony-alert@{unit}.service" in on_failure, (unit, on_failure)

    # --- Alert delivery: a REAL failure POSTs to the sink ---
    machine.succeed(
        "systemd-run --unit=alert-sink --collect"
        " python3 /etc/alert-sink.py")
    machine.wait_for_unit("alert-sink.service")

    machine.succeed("systemctl stop freeswitch.service")
    machine.wait_until_fails("systemctl start telephony-health.service")
    machine.wait_until_succeeds("grep -q telephony-health /tmp/alert-sink.log")
    alert = machine.succeed("cat /tmp/alert-sink.log")
    assert "telephony-health" in alert, alert
    assert "PBX unit failure" in alert, alert
  '';
}
