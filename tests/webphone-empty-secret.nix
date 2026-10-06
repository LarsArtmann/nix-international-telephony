# VM test pinning the webphone EMPTY-secret-file honest rejection: a
# `webhook_secret_file` pointing at a zero-byte file must crash-loop the
# service at config load with the journal signature
# `[rejection:config.webhook_secret_file]` … "is empty", and the port must
# never open. This is the contract that would have caught the 2026-10-01
# production outage class: the file existed, the content did not, webphone
# exited 1 at ~40 ms in a restart loop, and every external health surface
# stayed green because the app was never up to answer them.
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-webphone-empty-secret";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;
      # Wired DIRECTLY on services.webphone (messaging stays off — no
      # bridge, no FreeSWITCH dependency in the assertion path): the
      # rejection lives in webphone's config load, before any SIP or
      # messaging dependency could matter.
      services.webphone.settings.gateway.webhook_secret_file =
        "/etc/telephony/empty-gateway-secret";
      environment.etc."telephony/empty-gateway-secret".text = "";
    };

  testScript = ''
    # No start_all() — lazy start (see tests/dialplan.nix). FreeSWITCH is
    # deliberately NOT awaited: the config rejection is independent of it.
    machine.start()

    # The crash-loop journal signature, byte-exact on the two decisive
    # fragments: the rejection namespace names the field, the errno-family
    # tail distinguishes EMPTY from the unreadable/missing siblings.
    machine.wait_until_succeeds(
      "journalctl -u webphone -n 200 --no-pager"
      " | grep -F '[rejection:config.webhook_secret_file]'"
    )
    machine.succeed(
      "journalctl -u webphone -n 200 --no-pager"
      " | grep -F '[rejection:config.webhook_secret_file]'"
      " | grep -F 'is empty'"
    )

    # The service is down and STAYS down (the rejection is deterministic,
    # not a flaky start): no active spell survives a restart cycle, and
    # the app port never opens.
    machine.wait_until_fails("systemctl is-active --quiet webphone.service")
    machine.sleep(3)
    machine.fail("systemctl is-active --quiet webphone.service")
    machine.fail("ss -ltn 'sport = :8080' | grep -q ':8080'")
  '';
}
