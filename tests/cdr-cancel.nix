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
    missed = (
        "python3 /etc/sip.py --server " + sip_ip + " --domain pbx.test "
        "--user 1000 --password test-1000-x9y8z7 "
        "--caller-user 1001 --caller-password test-1001-u6t5s4 "
        "missed-call --to 2000 --ring-seconds 3"
    )

    status, out = machine.execute(missed)
    print("MISSED-CALL OUTPUT:", out)
    assert status == 0, out
    assert "CANCELLED 487" in out, out

    # Let the CDR machinery settle, then dump the truth.
    import time as _time
    _time.sleep(3)
    machine.succeed(f"{fs_cli} 'show channels'")
    rows = machine.execute("cat /var/lib/freeswitch/cdr-csv/Master.csv 2>&1 || true")
    print("MASTER-CSV:", rows)
    cause = machine.execute(
        "journalctl -u freeswitch -q --no-pager | grep -i "
        "'ORIGINATOR_CANCEL\\|Hangup Cause' | tail -5 || true"
    )
    print("CAUSE-LINES:", cause)
  '';
}
