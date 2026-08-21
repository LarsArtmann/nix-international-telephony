# Shared fixtures for the telephony VM tests (tests/dialplan.nix,
# tests/webphone.nix, tests/tls-turn.nix, tests/pbx.nix).
#
# Every test node imports `baseNode`: the module under test, the scripted
# protocol clients and the shared PBX config (two extensions, one ring
# group, no gateway). Tests then add their scenario-specific config on top.
let
  # Scripted SIP client for SIP-level assertions (tests/sip.py), plus the
  # TURN client (tests/turn.py).
  sipClientModule =
    { pkgs, ... }:
    {
      environment.etc."sip.py".source = ./sip.py;
      environment.etc."turn.py".source = ./turn.py;
      environment.systemPackages = [ pkgs.python3 ];
    };

  # Shared PBX under test: two extensions and one ring group, no gateway.
  baseTelephony = {
    services.telephony = {
      enable = true;
      domain = "pbx.test";
      eventSocketPassword = "test-es-4d5e6f";
      turn.authSecret = "test-turn-rest-4d5e6f";
      extensions = {
        "1000" = {
          password = "test-1000-x9y8z7";
          displayName = "Alice";
        };
        "1001" = {
          password = "test-1001-u6t5s4";
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
    };
  };

  # Node boilerplate shared by every machine in every test.
  nodeSettings = {
    networking.firewall.enable = true;
    system.stateVersion = "26.05";
  };

  # Everything every test node imports.
  baseNode = [
    ../modules/telephony.nix
    sipClientModule
    baseTelephony
    nodeSettings
  ];
in
{
  inherit baseNode;
}
