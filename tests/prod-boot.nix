# Boot-smoke for the production host shape (hosts/pbx-prod): proves the
# deployable template's unit graph — hardened sshd, file-based secrets,
# ACME-shaped TLS (here self-signed), CDR, nginx webphone, coturn —
# actually starts together on a VM, and that nothing template-shaped leaks
# into the runtime configuration.
#
#   * secrets are stubbed by a oneshot in the exact shape a sops-nix /
#     agenix deployment renders (root-only files under the template's
#     secretsDir, /var/lib/telephony-secrets)
#   * tls.mode is forced to self-signed: ACME cannot issue inside a VM;
#     the acme wiring itself is evaluated by checks.telephony-eval
#     (every tls.mode) and hosts/pbx-prod's toplevel eval in CI
#   * a scripted SIP REGISTER proves the spliced file secrets really
#     authenticate against sofia in the prod shape
{ sshServerModule }:
let
  common = import ./common.nix;

  esPassword = "prodboot-es-1a2b3c";
  ext1000Password = "prodboot-1000-4d5e6f";
  ext1001Password = "prodboot-1001-7g8h9i";
  turnSecret = "prodboot-turn-0j9k8l";
  gwPassword = "prodboot-gw-telnyx-2k3l4m";
in
{
  name = "telephony-prod-boot";

  nodes.machine =
    {
      lib,
      pkgs,
      ...
    }:
    {
      # The template itself plus the module and ssh wiring flake.nix adds
      # for nixosConfigurations.pbx-prod — the deployable shape, verbatim.
      imports = [
        ../modules/telephony
        sshServerModule
        ../hosts/pbx-prod
        {
          services.ssh-server = {
            enable = true;
            authorizedKeys = [ ];
          };
        }
      ];

      # --- VM adaptations, everything else stays the template ---
      # ACME cannot issue in a VM; the self-signed mode exercises the same
      # nginx/wss/sofia graph (acme eval coverage: checks.telephony-eval).
      services.telephony.tls = lib.mkForce {
        mode = "self-signed";
        acmeEmail = "";
      };
      # The template ships no manual root filesystem — the real host gets
      # one from disk.nix (disko) at install time; the VM framework
      # provides its own root device here.
      fileSystems."/" = {
        device = lib.mkForce "/dev/vda";
        fsType = lib.mkForce "ext4";
      };
      boot.loader.grub.devices = lib.mkForce [ "/dev/vda" ];
      # The template's static IPv6 + default gateway target the real
      # Hetzner NIC (ens3). The VM's NICs are eth0/eth1, and scripted
      # networking parks network-addresses-ens3.service on a device that
      # never appears, wedging network-online.target — and with it
      # freeswitch and coturn — forever. The VM brings its own networking.
      networking.interfaces.ens3 = lib.mkForce { };
      networking.defaultGateway6 = lib.mkForce null;
      systemd.services.network-addresses-ens3.enable = false;
      # curl the vhost by its template domain from inside the guest.
      networking.extraHosts = "127.0.0.1 pbx.example.com";

      # Secret-manager stand-in: renders exactly the files hosts/pbx-prod
      # references (secretsDir = "/var/lib/telephony-secrets", Option B). The
      # TURN secret is group-readable by coturn's turnserver user, mirroring
      # the sops-nix recipe in docs/secrets.md.
      systemd.services.telephony-prod-secrets = {
        description = "Provision runtime secret files (secret-manager stand-in)";
        wantedBy = [ "multi-user.target" ];
        after = [ "users-groups.service" ];
        before = [
          "freeswitch.service"
          "coturn.service"
          "telephony-web-config.service"
        ];
        serviceConfig.Type = "oneshot";
        script = ''
          install -d -m 750 -g turnserver /var/lib/telephony-secrets
          printf '%s\n' '${esPassword}'     > /var/lib/telephony-secrets/telephony_event_socket
          printf '%s\n' '${ext1000Password}' > /var/lib/telephony-secrets/telephony_ext_1000
          printf '%s\n' '${ext1001Password}' > /var/lib/telephony-secrets/telephony_ext_1001
          printf '%s\n' '${turnSecret}'     > /var/lib/telephony-secrets/telephony_turn
          printf '%s\n' '${gwPassword}'      > /var/lib/telephony-secrets/telephony_gw_itsp
          chmod 600 /var/lib/telephony-secrets/telephony_event_socket \
            /var/lib/telephony-secrets/telephony_ext_1000 /var/lib/telephony-secrets/telephony_ext_1001 \
            /var/lib/telephony-secrets/telephony_gw_itsp
          chgrp turnserver /var/lib/telephony-secrets/telephony_turn
          chmod 640 /var/lib/telephony-secrets/telephony_turn
        '';
      };

      # Scripted SIP client for the REGISTER proof (tests/sip.py).
      environment.etc."sip.py".source = ./sip.py;
      environment.systemPackages = [ pkgs.python3 ];
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "${esPassword}")

    fs_cli = "fs_cli -p ${esPassword} -x"

    # --- The whole prod unit graph came up ---
    machine.wait_for_unit("nginx.service")
    machine.wait_for_unit("coturn.service")
    machine.wait_for_unit("sshd.service")

    # --- sofia bound a real interface, not loopback-only ---
    # (the loopback-bind race the demo tests guard against, on the prod shape)
    listeners = machine.succeed("ss -ltn 'sport = :5060' | grep -v State")
    assert "127.0.0.1:5060" not in listeners, listeners

    # --- nginx serves the webphone over TLS under the template domain ---
    machine.succeed("curl -ksf https://pbx.example.com/ > /dev/null")
    machine.succeed("curl -ksf https://pbx.example.com/config.js > /dev/null")
    # ... and proxies the wss hop's upstream.
    machine.succeed("ss -ltn 'sport = :7443' | grep -q ':7443'")

    # --- File secrets were spliced into the runtime config ---
    machine.succeed("grep -q '${ext1000Password}' /var/lib/freeswitch/conf/directory/default.xml")
    machine.succeed("grep -q '${esPassword}' /var/lib/freeswitch/conf/autoload_configs/event_socket.conf.xml")
    machine.fail("grep -rq '@TELEPHONY_' /var/lib/freeswitch/conf/")

    # --- Nothing template-shaped leaked into the runtime config ---
    machine.fail("grep -ri changeme /var/lib/freeswitch/conf/")
    machine.fail("grep -ri changeme /var/lib/telephony/")

    # --- CDR is wired (the template sets cdr.enable) ---
    machine.succeed(f"{fs_cli} 'module_exists mod_cdr_csv' | grep -q true")

    # --- The spliced secrets actually authenticate (prod shape, E2E) ---
    sip_ip = sip_server(machine)
    out = machine.succeed(
        f"python3 /etc/sip.py --server {sip_ip} --domain pbx.example.com "
        f"--user 1000 --password ${ext1000Password} register"
    )
    assert "REGISTER 200" in out, out
    machine.wait_until_succeeds(
        f"{fs_cli} 'sofia status profile internal reg' | grep 1000"
    )
  '';
}
