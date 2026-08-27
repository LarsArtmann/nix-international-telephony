# Example deployment: a small two-extension PBX with one ring group.
# DEMO HOST — QEMU-shaped (tmpfs root, autologin, demo secrets in the store).
# Run an ephemeral demo VM:
#   nix run .#vm
# For a real server use the production template instead (docs/deploy.md):
#   nixos-rebuild switch --flake .#pbx-prod --target-host root@pbx.example.com
{
  config,
  modulesPath,
  ...
}:

{
  imports = [
    # Makes `config.system.build.vm` available for local testing.
    (modulesPath + "/virtualisation/qemu-vm.nix")
  ];

  # Demo-only settings; replace for real deployments.
  networking.hostName = "pbx";
  networking.domain = "example.com";

  fileSystems."/" = {
    device = "tmpfs";
    fsType = "tmpfs"; # demo VM: ephemeral root, config baked in from the store
  };

  services.telephony = {
    enable = true;
    domain = "pbx.example.com";

    # CHANGE ALL SECRETS BEFORE EXPOSING PORTS.
    eventSocketPassword = "demo-es-9f1e2c";
    turn.authSecret = "demo-turn-secret-7b3a4d-change-me";

    extensions = {
      "1000" = {
        password = "demo-1000-a1b2c3";
        displayName = "Alice";
      };
      "1001" = {
        password = "demo-1001-d4e5f6";
        displayName = "Bob";
      };
    };

    ringGroups."2000" = {
      members = [
        "1000"
        "1001"
      ];
      timeoutSec = 25;
    };

    # Example ITSP trunk (fictional values, dialling PSTN answers 503 while null):
    # gateway = {
    #   proxy = "sip.provider.example";
    #   username = "acme-account";
    #   password = "provider-secret";
    #   callerIdNumber = "441632960961";
    #   did = "441632960961";
    #   didDestination = "2000";
    # };
  };

  # Demo convenience: no need to log in at the VM console.
  services.getty.autologinUser = "root";
  users.users.root.initialPassword = "root";

  # Reach the webphone from the host browser: https://localhost/.
  # Ops shell over hardened SSH (key-only): ssh -p 2222 root@localhost.
  virtualisation.forwardPorts = [
    {
      from = "host";
      host.port = 443;
      guest.port = 443;
    }
    {
      from = "host";
      host.port = 2222;
      guest.port = 22;
    }
  ];

  # Printed by every root login shell (the autologin getty shows it).
  environment.etc."profile.d/telephony-demo-banner.sh".text = ''
    cat <<'BANNER'

      Telephony demo VM
      Webphone      https://${config.services.telephony.domain}/
                    (self-signed certificate — accept the browser warning)
      Extensions    1000 Alice / demo-1000-a1b2c3
                    1001 Bob   / demo-1001-d4e5f6
                    2000 ring group (Alice + Bob)
      Echo test     dial 9196 from the webphone
      Recordings    https://${config.services.telephony.domain}/recordings/ (serving disabled by default)
      SSH           ssh -p 2222 root@localhost (hardened, key-only, tracked keys)
      fs_cli        fs_cli -p ${config.services.telephony.eventSocketPassword}

      CHANGE ALL SECRETS BEFORE EXPOSING PORTS.

    BANNER
  '';

  system.stateVersion = "26.05";
}
