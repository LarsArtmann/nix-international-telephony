# NixOS VM test: does a call CANCELLED while ringing leave a Master.csv
# row? (TODO row "CDR rows for calls CANCELLED while ringing": live
# evidence 2026-09-30 says answered inbound legs write rows, a leg
# cancelled mid-ring after 183 writes NONE — missed calls stay invisible
# in the phone-API History.)
#
# Scenario: `originate {originate_timeout=5}loopback/2000 &park()` places
# a call through the dialplan into the ring group; the ring group rings
# (nobody registered), the originate times out after 5s and cancels —
# the caller-gives-up-mid-ring shape (cause ORIGINATOR_CANCEL on the
# dialplan leg), driven entirely by fs_cli.
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

    # The missed call: ring group 2000 rings nobody for 5s, then the
    # originator gives up (originate timeout = caller cancelling at 183).
    out = machine.succeed(
        f"{fs_cli} 'originate {{originate_timeout=5}}loopback/2000 &park()'"
    )
    print("ORIGINATE:", out)
    assert out.startswith("-ERR"), out

    # Let the CDR machinery settle, then read the truth.
    machine.wait_until_succeeds(
        f"{fs_cli} 'show channels' | grep '^0 total'", timeout=60
    )
    machine.succeed("sleep 2")
    rows = machine.execute("cat /var/lib/freeswitch/cdr-csv/Master.csv 2>&1 || true")
    print("MASTER-CSV:", rows)
    cause = machine.execute(
        "journalctl -u freeswitch -q --no-pager | grep -i "
        "'ORIGINATOR_CANCEL\\|Hangup Cause' | tail -8 || true"
    )
    print("CAUSE-LINES:", cause)
  '';
}
