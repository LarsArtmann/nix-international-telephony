# Eval-only fixture exercising every *File option at once (and one plain
# password for mixed mode), used by tests/eval.nix to assert the generated
# XML carries exactly one @TELEPHONY_*@ placeholder per configured file.
{ ... }:
{
  imports = [ ../modules/telephony ];

  # Boot fixtures mirror tests/tls-mode-host.nix: this host never boots, it
  # exists to force a full toplevel evaluation.
  fileSystems."/" = {
    device = "/dev/vda";
    fsType = "ext4";
  };
  boot.loader.grub.devices = [ "/dev/vda" ];
  system.stateVersion = "26.05";

  services.telephony = {
    enable = true;
    domain = "files.test";
    eventSocketPasswordFile = "/run/secrets/event-socket";
    turn.authSecretFile = "/run/secrets/turn";
    extensions = {
      "1000".passwordFile = "/run/secrets/ext-1000";
      "1001".password = "plain";
    };
    gateways.itsp = {
      proxy = "sip.provider.example";
      username = "acct";
      passwordFile = "/run/secrets/gw-itsp";
      did = "441632960961";
      didDestination = "1000";
    };
  };
}
