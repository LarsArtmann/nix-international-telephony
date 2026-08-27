# Declarative IVR VM test (M21 of the live-PBX plan): dial the menu,
# press a key, land at the mapped destination — the echo test streams
# real audio back through the transfer, proving the routing end to end.
# The no-match path exhausts play_and_get_digits retries and lands on
# the fallback (hangup).
let
  common = import ./common.nix;
in
{
  name = "telephony-ivr";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;

      environment.etc."vmclient.py".source = ./vmclient.py;

      services.telephony.ivrs.main = {
        extension = "4000";
        timeoutSec = 3;
        maxTries = 2;
        entries = {
          "1".destination = "9196"; # echo: audio streams back
          "2".destination = "1000"; # unregistered -> voicemail fallback
        };
        # null fallback -> hangup after wrong input
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")


    sip_ip = sip_server(machine)
    vmclient = "python3 /etc/vmclient.py --server " + sip_ip + " --domain pbx.test "

    # --- Mapped key 1 -> echo test: the transfer lands and audio returns ---
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "menu --to 4000 --key 1 --listen-seconds 6"
    )
    assert "VM-MENU-ANSWERED" in out, out
    menu_bytes = 0
    for line in out.splitlines():
        if line.startswith("VM-MENU-RTP"):
            menu_bytes = int(line.split("bytes=")[1].split()[0])
    # Echo streams our own noise back: an idle menu leg gets a few
    # hundred bytes, an established echo gets thousands.
    assert menu_bytes > 20000, f"echo after IVR transfer streamed only {menu_bytes} bytes:\n{out}"
    machine.succeed(
        "journalctl -u freeswitch --no-pager | grep -q 'Processing 1000.*->9196'"
    )

    # --- Mapped key 2 -> extension dialplan (voicemail fallback answers) ---
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "menu --to 4000 --key 2 --listen-seconds 8"
    )
    assert "VM-MENU-ANSWERED" in out, out
    machine.wait_until_succeeds(
        "journalctl -u freeswitch --no-pager | grep -q 'voicemail(default pbx.test 1000)'",
        timeout=30,
    )

    # --- No-match key: retries exhaust, fallback hangs up ---
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "menu --to 4000 --key 9 --listen-seconds 10"
    )
    assert "VM-MENU-ANSWERED" in out, out
    assert "VM-SERVER-HANGUP yes" in out, out
  '';
}
