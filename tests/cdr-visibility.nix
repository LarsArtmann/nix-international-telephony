# NixOS VM test: CDR visibility for the missed-call failover shape.
#
# History: this suite began as `cdr-cancel`, asserting that an fs_cli
# `originate ... loopback/2000` returns -ERR after 5s of ringing nobody
# (the caller-gives-up-mid-ring shape). That premise was never green —
# the file landed as sibling WIP via an auto-commit (2026-10-01 10:41)
# and the identical +OK failure reproduces at the pre-relock base too
# (2026-10-01 collision report: relock exonerated, suite never green).
# What actually happens: bridge(user/1000,user/1001) with no registered
# members fails INSTANTLY with USER_NOT_REGISTERED, continue_on_fail
# falls through to answer+voicemail, and the originate returns +OK in
# well under a second — the product's missed-call shape is voicemail
# failover, not 25s of ring. And the loopback harness was structurally
# CDR-blind on top: loopback channels never reach mod_cdr_csv at all
# (probe 2026-10-03: a loopback originate writes ZERO Master.csv rows;
# the same call driven through a real sofia leg writes rows instantly).
# The mid-ring ORIGINATOR_CANCEL question stays on the live-host track
# (TODO row "CDR rows for calls CANCELLED while ringing": scripted SIP
# listeners never receive the B-leg INVITE in a VM — ten runs,
# 2026-09-30).
#
# Asserted here, deterministically: driving the caller leg through a
# real sofia self-INVITE, the voicemail-failover leg leaves Master.csv
# rows — missed-call visibility in the phone-API History rides on them.
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
  name = "telephony-cdr-visibility";

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

    # Nobody is registered: the dialplan's bridge(user/1000,user/1001)
    # fails instantly (USER_NOT_REGISTERED) and continue_on_fail hands
    # the caller to answer+voicemail — the missed-call failover shape.
    # The caller leg MUST be a real sofia leg (a self-INVITE through the
    # internal profile): loopback channels never reach mod_cdr_csv.
    sip_ip = sip_server(machine)
    out = machine.succeed(
        f"{fs_cli} 'originate {{originate_timeout=5}}sofia/internal/2000@{sip_ip}:5060 &park()'"
    )
    print("ORIGINATE:", out)

    # Let the failover leg and the parked channel wrap up, then read the
    # truth. (Evidence prints come BEFORE the row assert so a failure
    # leaves the CDR state in the log.)
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

    # The missed-call failover must be visible in the CDR: phone-API
    # History rows ride on Master.csv.
    assert rows[1] != "" and '"2000"' in rows[1], rows
  '';
}
