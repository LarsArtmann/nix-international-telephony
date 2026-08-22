# Minimal boot proof for the FreeSWITCH stack: the smallest telephony
# node that still exercises kernel -> systemd -> freeswitch -> sofia.
#
# Built for KVM-less runners (GitHub arm64 hosts expose no /dev/kvm):
# kvm = false drops the derivation's kvm system-feature requirement so
# the suite runs under same-arch TCG, and the guest is slimmed (no
# sounds package, webphone, TURN or recordings) so it reaches the test
# driver's fixed 300s serial-shell connect window despite TCG slowness.
{
  kvm ? true,
  slowBoot ? false,
}:
let
  common = import ./common.nix;

  bootTimeouts = if slowBoot then ", port_timeout=900, unit_timeout=600" else "";
in
{
  name = if kvm then "telephony-boot" else "telephony-boot-tcg";

  requiredFeatures.kvm = kvm;

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;

      services.telephony = {
        # Keep the guest minimal: every dropped component shrinks the
        # closure and the boot-time store registration (TCG is slow).
        sounds.package = null;
        recording.enable = false;
        webphone.enable = false;
        turn.enable = false;
      };

      # MTTCG: more guest vCPUs -> more host threads under TCG.
      virtualisation.cores = 4;
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f"${bootTimeouts})

    # sofia bound its SIP listeners on a real interface.
    machine.succeed("ss -ltn 'sport = :5060' | grep -q ':5060'")
    machine.succeed("ss -lun 'sport = :5060' | grep -q ':5060'")

    # Both generated profiles came up and answer fs_cli.
    status = machine.succeed("fs_cli -p test-es-4d5e6f -x 'sofia status'")
    assert "internal" in status and "external" in status, status

    # The loopback secure-WebSocket transport (for the nginx wss proxy) is
    # bound: sofia's wss listener on 7443.
    machine.succeed("ss -ltn 'sport = :7443' | grep -q ':7443'")
  '';
}
