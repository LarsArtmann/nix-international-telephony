# Throwaway host for eval-only checks of the three tls.mode variants
# (ACME cannot run in a VM test; we verify wiring by evaluation).
{ ... }:
{
  imports = [ ../modules/telephony.nix ];
  services.telephony = {
    enable = true;
    domain = "acme.test";
    eventSocketPassword = "eval";
    turn.authSecret = "eval";
    tls.acmeEmail = "ops@example.com";
    extensions."1000".password = "eval";
  };
}
