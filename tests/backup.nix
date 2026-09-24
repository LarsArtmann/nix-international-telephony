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
    { pkgs, ... }:
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
        backups = {
          enable = true;
          repository = "/var/lib/telephony-backup-repo";
          passwordFile = "/run/telephony-restic-password";
          # /etc/ssh rides along like in the pbx-prod template: the
          # host-key identity must survive a disaster restore.
          paths = [
            "/var/lib/private/freeswitch"
            "/var/lib/telephony/recordings"
            "/etc/ssh"
          ];
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
    machine.succeed("systemctl start restic-backups-telephony.service")
    snapshots = json.loads(
        machine.succeed(
            "restic -r /var/lib/telephony-backup-repo"
            " -p /run/telephony-restic-password snapshots --json"))
    assert snapshots, "no restic snapshot after backup run"
    listing = machine.succeed(
        "restic -r /var/lib/telephony-backup-repo"
        " -p /run/telephony-restic-password ls latest")
    assert "backup-canary" in listing, listing[-2000:]
    # The SSH host-key identity rides in the snapshot (the prod template
    # backs up /etc/ssh for exactly this).
    assert "ssh_host_ed25519_key" in listing, listing[-2000:]
    machine.succeed("systemctl is-enabled restic-backups-telephony.timer")

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
