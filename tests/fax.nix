# Inbound-fax VM test (P16): with fax.enable, mod_spandsp is loaded and
# the fax extension answers as a G.711 receiver — a plain voice-shaped
# call (noise RTP, like a calling fax machine) reaches the rxfax app,
# ends cleanly on the caller's BYE, and never offers T.38.
let
  common = import ./common.nix;
in
{
  name = "telephony-fax";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;

      environment.etc."vmclient.py".source = ./vmclient.py;

      services.telephony.fax.enable = true;
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    fs_cli = "fs_cli -p test-es-4d5e6f -x"

    # The fax receiver stack is actually running.
    machine.succeed(f"{fs_cli} 'show modules' | grep -q mod_spandsp")

    # The receive directory exists before the first fax (tmpfiles rule).
    machine.succeed("test -d /var/lib/telephony/recordings/fax")

    # A calling fax machine looks like a voice call: G.711 noise until
    # the page transmission starts. Deposit exercises exactly that
    # shape; the fax extension must ANSWER (catch_all would refuse with
    # unallocated_number) and run the receiver.
    machine.succeed(
        "python3 /etc/vmclient.py --server "
        + sip_server(machine)
        + " --domain pbx.test --user 1000 --password test-1000-x9y8z7 "
        + "deposit --to 6000 --seconds 12 > /tmp/faxcall.log 2>&1"
    )
    machine.wait_until_succeeds("grep -q 'VM-DEPOSIT-ANSWERED' /tmp/faxcall.log", timeout=30)

    # The dialplan reached the receiver with T.38 disabled (G.711
    # posture), and the call ended on the caller's BYE, not a crash.
    machine.wait_until_succeeds("grep -q 'VM-DEPOSIT-BYE' /tmp/faxcall.log", timeout=30)
    log = machine.succeed(
        "grep -a 'fax' /var/lib/freeswitch/log/freeswitch.log | tail -n 40"
    )
    assert "set(fax_use_t38=false)" in log, f"t38 disable action missing:\n{log}"
    assert "rxfax(" in log, f"rxfax never executed:\n{log}"
    hangup = machine.succeed(
        "grep -a 'Hangup sofia/internal/1000@pbx.test' "
        "/var/lib/freeswitch/log/freeswitch.log | tail -n 3"
    )
    assert "NORMAL_CLEARING" in hangup, f"fax call did not end cleanly:\n{hangup}"
  '';
}
