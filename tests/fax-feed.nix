# NixOS VM test for the inbound fax feed (modules/telephony/fax-feed.nix):
#   * a rxfax TIFF seeded into the fax receive directory is converted with
#     tiff2pdf and POSTed to the REAL webphone /hooks/fax webhook (Bearer
#     secret over loopback): the original moves into fed/ and a received
#     fax row lands in webphone's SQLite database for the owner extension
#   * a file that is not a TIFF stays in place for the next sweep and the
#     journal says so — nothing is ever silently dropped
#
# The suite runs the feed against the real webphone service (not a stub
# sink): the 202 answer, the secret check and the database row are all
# production behavior.
{
  telephonyModule,
  webphonePackage,
  kvm ? true,
  slowBoot ? false,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  # 8x8 white TIFF, depth 8 (322 bytes) — small enough to inline, real
  # enough that tiff2pdf accepts it (depth 16 from stock ImageMagick
  # defaults is the conversion failure this fixture class guards against).
  goodTiffB64 = "SUkqAEgAAAD/////////////////////////////////////////////////////////////////////////////////////DwAAAQMAAQAAAAgAAAABAQMAAQAAAAgAAAACAQMAAQAAAAgAAAADAQMAAQAAAAEAAAAGAQMAAQAAAAEAAAAKAQMAAQAAAAEAAAARAQQAAQAAAAgAAAASAQMAAQAAAAEAAAAVAQMAAQAAAAEAAAAWAQMAAQAAAAgAAAAXAQQAAQAAAEAAAAAcAQMAAQAAAAEAAAApAQMAAgAAAAAAAQA+AQUAAgAAADIBAAA/AQUABgAAAAIBAAAAAAAAhetRAAAAgADD9agAAAAAAs3MTAAAAAABzcxMAAAAgADNzEwAAAAAAo/C9QAAAAAQNxqgAAAAAAIrhwoAAAAgAA==";

  bootTimeouts = if slowBoot then ", port_timeout=900, unit_timeout=900" else "";
in
{
  name = if kvm then "telephony-fax-feed" else "telephony-fax-feed-tcg";

  requiredFeatures.kvm = kvm;

  nodes.machine =
    { pkgs, ... }:
    {
      imports = common.baseNode;
      environment.systemPackages = [ pkgs.sqlite ];
      environment.etc."webphone-hook-secret".text = "test-hook-secret-4d5e6f\n";
      services.telephony.fax = {
        enable = true;
        feed = {
          enable = true;
          # The rxfax receiver stays at its default (6000, colliding with
          # nothing); the fed faxes are owned by the REAL extension 1000,
          # whose Fax tab is what this pipeline exists to serve.
          owner = "1000";
          from = "15550001111";
          secretFile = "/etc/webphone-hook-secret";
        };
      };
      # The same secret webphone's hook gate expects: the feed posts with
      # it, and a mismatch would fail the run at the 401, not silently.
      services.webphone.settings.gateway.webhook_secret = "test-hook-secret-4d5e6f";
    };

  testScript = ''
    ${common.bootWait}

    # Only the web half matters here: no sofia wait, no calls — the feed
    # is an HTTP producer and webphone is the consumer.
    machine.wait_for_unit("webphone.service"${bootTimeouts})
    machine.wait_for_open_port(8080)

    # Seed one real TIFF and one malformed file into the receive
    # directory (created by fax.enable's tmpfiles rule, 0770
    # root:telephony).
    machine.succeed(
        "printf %s '${goodTiffB64}' | base64 -d > /var/lib/telephony/recordings/fax/good.tif"
    )
    machine.succeed(
        "echo 'definitely not a tiff' > /var/lib/telephony/recordings/fax/bad.tif"
    )

    # Deterministic sweep: start the oneshot directly (the path unit and
    # retry timer exist too, but the test asserts outcomes, not scheduler
    # timing).
    machine.succeed("systemctl start telephony-fax-feed.service")

    # The good TIFF is converted, posted and archived.
    machine.wait_until_succeeds(
        "test -f /var/lib/telephony/recordings/fax/fed/good.tif",
        timeout=60,
    )
    machine.succeed(
        "journalctl -u telephony-fax-feed | grep -q 'fax-feed: posted'"
    )

    # The malformed file stays in place for the next sweep, with the
    # conversion failure journaled.
    machine.succeed("test -f /var/lib/telephony/recordings/fax/bad.tif")
    machine.succeed(
        "journalctl -u telephony-fax-feed | grep -q 'tiff2pdf failed for bad.tif'"
    )

    # End to end: the webhook accepted the PDF — webphone holds a
    # received fax row for the owner extension (default = fax.extension).
    machine.wait_until_succeeds(
        "sqlite3 /var/lib/webphone/webphone.db \"select count(*) from fax_jobs where owner='1000' and status='received'\" | grep -q '^1$'",
        timeout=30,
    )
  '';
}
