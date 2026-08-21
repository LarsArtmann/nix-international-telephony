# Example deployment: a small two-extension PBX with one ring group.
#
# Run an ephemeral demo VM:
#   nix run .#vm
# Deploy to a real host (adjust domain + secrets first!):
#   nixos-rebuild switch --flake .#pbx --target-host root@pbx.example.com
{
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

  system.stateVersion = "26.05";
}
