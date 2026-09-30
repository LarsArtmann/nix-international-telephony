# NixOS VM test: does a call CANCELLED while ringing leave a Master.csv
# row? (TODO row "CDR rows for calls CANCELLED while ringing": live
# evidence 2026-09-30 says answered inbound legs write rows, a leg
# cancelled mid-ring after 183 writes NONE — missed calls stay invisible
# in the phone-API History.)
#
# Scenario: a scripted callee (tests/sip.py missed-call) registers with a
# Contact pointing at a listening socket; a caller INVITEs the ring group
# (2000), the callee leg rings (180) and never answers; after
# ring-seconds the caller CANCELs — the ORIGINATOR_CANCEL shape of a
# caller giving up mid-ring.
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  cdrTestConfig = {
    services.telephony.cdr.enable = true;
  };
in
{
  name = "telephony-cdr-cancel";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode ++ [ cdrTestConfig ];
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")

    es_password = "test-es-4d5e6f"
    fs_cli = f"fs_cli -p {es_password} -x"

    sip_ip = sip_server(machine)
    machine.succeed(
        f"{fs_cli} 'sofia global siptrace on' || true"
    )

    def run_missed(destination):
        return machine.execute(
            "python3 /etc/sip.py --server " + sip_ip + " --domain pbx.test "
            "--user 1000 --password test-1000-x9y8z7 "
            "--caller-user 1001 --caller-password test-1001-u6t5s4 "
            f"missed-call --to {destination} --ring-seconds 3 2>&1"
        )

    # Arm 1: direct extension call (1001 -> 1000) cancelled mid-ring.
    print(
        "REGS-BEFORE:",
        machine.execute(f"{fs_cli} 'sofia status profile internal reg' || true"),
    )
    status, out = run_missed("1000")
    print("MISSED-CALL-1000 OUTPUT:", out)
    regs = machine.execute(
        f"{fs_cli} 'sofia status profile internal reg' || true"
    )
    print("REGS-BEFORE-FLUSH:", regs)
    trace = machine.execute(
        "journalctl -u freeswitch -q --no-pager | grep -E 'send|recv|INVITE|CANCEL' | tail -40 || true"
    )
    print("SIP-TRACE-TAIL:", trace)
    assert status == 0, out
    assert "CANCELLED 487" in out, out
  '';
}
