# Eval-only fixture for the three tls.mode variants, exercised by
# tests/eval.nix (ACME cannot run in a VM test; we verify wiring by
# evaluation). Carries the shared host config; the tls.mode override
# comes from the caller. The telephony MODULE comes from the caller
# too (eval.nix passes nixosModules.telephony) — importing it here as
# well double-defines every readOnly option (services.telephony.state.*
# failed telephony-eval exactly that way once an arm first read it).
_: {
  # Minimal boot fixtures so a FULL toplevel evaluation succeeds — this
  # host never boots; it exists to prove the telephony module evaluates
  # in every tls.mode (tests/eval.nix forces system.build.toplevel,
  # which runs NixOS's own assertions, e.g. security.acme's).
  fileSystems."/" = {
    device = "/dev/vda";
    fsType = "ext4";
  };
  boot.loader.grub.devices = [ "/dev/vda" ];
  system.stateVersion = "26.05";

  services.telephony = {
    enable = true;
    domain = "acme.test";
    eventSocketPassword = "eval";
    turn.authSecret = "eval";
    tls.acmeEmail = "ops@example.com";
    extensions."1000".password = "eval";
  };
}
