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

      services.telephony = {
        # The fallback group's member is an UNREGISTERED-but-existing
        # extension: bridging user/1002 fails instantly (no contact)
        # instead of ringing the caller's own registration forever
        # (originate_timeout does not cap a bridge to a registered
        # endpoint that never answers).
        extensions."1002".password = "test-1002-i6j7k8";
        ringGroups."2100" = {
          members = [ "1002" ];
          timeoutSec = 4;
          voicemailMember = "1000";
        };
        ivrs.main = {
          extension = "4000";
          timeoutSec = 3;
          maxTries = 2;
          entries = {
            "1".destination = "9196"; # echo: audio streams back
            "2".destination = "2100"; # ring group -> voicemail fallback
            "*".destination = "9196"; # star is a valid menu key
            "42".destination = "2100"; # multi-digit key
          };
          # null fallback -> hangup after wrong input
        };
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")


    sip_ip = sip_server(machine)
    vmclient = "python3 /etc/vmclient.py --server " + sip_ip + " --domain pbx.test "

    # --- Mapped key 1 -> echo test: the transfer lands and audio returns ---
    # Listen window must clear the digit-collection timeout (3 s) plus
    # greeting and transfer latency with room for several seconds of
    # echo — 6 s left the assert at the flaky edge.
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "menu --to 4000 --key 1 --listen-seconds 10"
    )
    assert "VM-MENU-ANSWERED" in out, out
    menu_bytes = 0
    for line in out.splitlines():
        if line.startswith("VM-MENU-RTP"):
            menu_bytes = int(line.split("bytes=")[1].split()[0])
    # Echo streams our own noise back: an idle menu leg gets a few
    # hundred bytes, an established echo gets thousands.
    assert menu_bytes > 20000, f"echo after IVR transfer streamed only {menu_bytes} bytes:\n{out}"
    # NOTE: sofia-channel EXECUTE/Processing lines never reach the VM
    # journal (known trap) — the freeswitch.log FILE has them.
    machine.succeed(
        "grep -q 'Processing 1000.*->9196' /var/lib/freeswitch/log/freeswitch.log"
    )

    # --- Mapped key 2 -> extension dialplan (voicemail fallback answers) ---
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "menu --to 4000 --key 2 --listen-seconds 18"
    )
    assert "VM-MENU-ANSWERED" in out, out
    machine.wait_until_succeeds(
        "grep -q 'voicemail(default pbx.test 1000)'"
        " /var/lib/freeswitch/log/freeswitch.log",
        timeout=datetime.timedelta(seconds=30),
    )

    # --- No-match key: retries exhaust, fallback hangs up ---
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "menu --to 4000 --key 9 --listen-seconds 10"
    )
    assert "VM-MENU-ANSWERED" in out, out
    assert "VM-SERVER-HANGUP yes" in out, out

    # --- Star key: '*' collects as a menu key and routes to echo ---
    # (the digit-collection mask must accept [0-9*]; '#' stays the
    # input terminator and cannot be an entry)
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "menu --to 4000 --key '*' --listen-seconds 10"
    )
    assert "VM-MENU-ANSWERED" in out, out
    star_bytes = 0
    for line in out.splitlines():
        if line.startswith("VM-MENU-RTP"):
            star_bytes = int(line.split("bytes=")[1].split()[0])
    assert star_bytes > 20000, f"echo after '*' transfer streamed only {star_bytes} bytes:\n{out}"

    # --- Multi-digit key: '42' collects as ONE input and routes whole ---
    # Proven by a NEW voicemail fallback for 1000 after the transfer —
    # counting occurrences distinguishes this leg from the key-2 leg.
    def vm_fallback_count():
        return int(
            machine.succeed(
                "grep -c 'voicemail(default pbx.test 1000)'"
                " /var/lib/freeswitch/log/freeswitch.log"
            ).strip()
        )

    fallbacks_before = vm_fallback_count()
    out = machine.succeed(
        vmclient
        + "--user 1000 --password test-1000-x9y8z7 "
        + "menu --to 4000 --key 42 --listen-seconds 18"
    )
    assert "VM-MENU-ANSWERED" in out, out
    machine.wait_until_succeeds(
        "test $(grep -c 'voicemail(default pbx.test 1000)'"
        " /var/lib/freeswitch/log/freeswitch.log) -gt "
        + str(fallbacks_before),
        timeout=datetime.timedelta(seconds=30),
    )
  '';
}
