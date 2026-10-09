# FreeSWITCH TLS certificate provisioning suite (routed gap from report
# 2026-09-18_14-47 §f.22): the telephony-fs-cert unit must render the
# ACME material into sofia's tls-cert-dir layout (agent.pem = cert+key,
# cafile.pem = chain), hand it to the FreeSWITCH DynamicUser (2026-09-16:
# a root-owned agent.pem left the internal profile dead — "Error Creating
# SIP UA"), and restart the freeswitch unit so the listeners actually
# serve the new material (in-process profile restarts are broken in this
# build). Redundant renders must be hash-guarded (2026-09-16: two path
# fires 8 min apart dropped calls for nothing), and a RENEWAL — new ACME
# files, detected by the PathChanged unit — must re-render and restart
# again. The ACME leg itself is NOT exercised: the test seeds fake
# material into /var/lib/acme/<domain> (the webphone vhost — and with it
# the only security.acme cert — is off, so no real order can interfere).
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  # Seed script: two CERT-V1/CERT-V2 generations share one body — openssl
  # makes each key fresh, so every seed's bytes differ (the renewal must
  # be detectable by content, not by mtime).
  seedScript =
    pkgs:
    pkgs.writeShellScript "acme-fake-seed" ''
      set -eu
      dir=/var/lib/acme/pbx.test
      mkdir -p "$dir"
      ${pkgs.openssl}/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
        -keyout "$dir/key.pem" -out "$dir/cert.pem" -subj "/CN=pbx.test" >/dev/null 2>&1
      cp "$dir/cert.pem" "$dir/fullchain.pem"
      chmod 600 "$dir"/*.pem
    '';
in
{
  name = "telephony-fs-cert-renewal";

  nodes.pbx =
    { pkgs, lib, ... }:
    {
      imports = common.baseNode ++ [
        {
          services.telephony = {
            webphone.enable = false;
            tls = {
              mode = "acme";
              acmeEmail = "t@pbx.test";
            };
          };
          # Seed the fake ACME dir BEFORE fs-cert renders (the unit reads
          # the files at boot; without them the boot render fails — the
          # real host gets them from the ACME order instead).
          systemd.services.acme-fake-seed = {
            description = "Seed fake ACME material for the fs-cert test";
            before = [
              "telephony-fs-cert.service"
              "freeswitch.service"
            ];
            wantedBy = [ "multi-user.target" ];
            serviceConfig = {
              Type = "oneshot";
              ExecStart = seedScript pkgs;
            };
          };
          environment.systemPackages = [ pkgs.openssl ];
        }
      ];
    };

  testScript = _: ''
    ${common.bootWait}

    wait_for_freeswitch(pbx, "test-es-4d5e6f")

    fs_cli = "fs_cli -p test-es-4d5e6f -x"
    pbx.wait_until_succeeds(
        fs_cli + " 'sofia status' | grep internal | grep -q RUNNING",
        timeout=datetime.timedelta(seconds=120),
    )

    cert_dir = "/var/lib/freeswitch/tls-certs"

    # --- Boot render: the seed ran before fs-cert, so the unit rendered
    # agent.pem (fullchain+key concat) and cafile.pem (chain) and exited
    # success; sofia's TLS listener is up on that material.
    pbx.succeed("systemctl show -p Result telephony-fs-cert.service | grep -q 'Result=success'")
    pbx.succeed(f"cmp {cert_dir}/cafile.pem /var/lib/acme/pbx.test/fullchain.pem")
    pbx.succeed(
        "cat /var/lib/acme/pbx.test/fullchain.pem /var/lib/acme/pbx.test/key.pem "
        f"> /tmp/expected-agent.pem && cmp {cert_dir}/agent.pem /tmp/expected-agent.pem"
    )
    pbx.succeed(f"test \"$(stat -c %a {cert_dir}/agent.pem)\" = 600")
    # The DynamicUser handoff: the rendered files must be owned by the
    # SAME uid/gid FreeSWITCH runs as (stat -L: /var/lib/freeswitch is a
    # symlink into /var/lib/private — a non-L stat reports root:root).
    pbx.succeed(
        f"test \"$(stat -L -c %u:%g /var/lib/freeswitch)\" = "
        f"\"$(stat -c %u:%g {cert_dir}/agent.pem)\""
    )

    # --- Hash guard: a redundant start (the path unit fires on EVERY
    # cert write during issuance — 2026-09-16 saw two fires 8 min apart)
    # must exit early WITHOUT restarting freeswitch (a restart drops
    # calls for nothing).
    t1 = pbx.succeed("systemctl show freeswitch -p ExecMainStartTimestamp --value").strip()
    pbx.succeed("systemctl start telephony-fs-cert.service")
    pbx.succeed("sleep 5")
    t_now = pbx.succeed("systemctl show freeswitch -p ExecMainStartTimestamp --value").strip()
    assert t_now == t1, f"redundant fs-cert run restarted freeswitch: {t1} -> {t_now}"

    # --- Renewal: fresh ACME material (new key => new bytes), the
    # PathChanged unit on cert.pem fires the oneshot, agent.pem picks up
    # the new concat, and freeswitch restarts to serve it — with the
    # profile back RUNNING afterward (the restart is the only verified
    # path in this build; an in-process sofia restart would leave it
    # dead or unregistered).
    pbx.succeed("systemctl start acme-fake-seed.service")
    pbx.wait_until_succeeds(
        "cat /var/lib/acme/pbx.test/fullchain.pem /var/lib/acme/pbx.test/key.pem"
        f" > /tmp/expected-agent2.pem && cmp -s {cert_dir}/agent.pem /tmp/expected-agent2.pem",
        timeout=datetime.timedelta(seconds=90),
    )
    pbx.wait_until_succeeds(
        f"test \"$(systemctl show freeswitch -p ExecMainStartTimestamp --value)\" != \"{t1}\"",
        timeout=datetime.timedelta(seconds=90),
    )
    pbx.wait_until_succeeds(
        fs_cli + " 'sofia status' | grep internal | grep -q RUNNING",
        timeout=datetime.timedelta(seconds=120),
    )
    pbx.succeed(f"cmp {cert_dir}/cafile.pem /var/lib/acme/pbx.test/fullchain.pem")
  '';
}
