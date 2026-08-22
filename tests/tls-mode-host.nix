# Eval-only fixture for the three tls.mode variants, exercised by
# tests/eval.nix (ACME cannot run in a VM test; we verify wiring by
# evaluation). Carries the shared host config; the tls.mode override
# comes from the caller.
{ ... }:
{
  imports = [ ../modules/telephony ];
  services.telephony = {
    enable = true;
    domain = "acme.test";
    eventSocketPassword = "eval";
    turn.authSecret = "eval";
    tls.acmeEmail = "ops@example.com";
    extensions."1000".password = "eval";
  };
}
