# NixOS VM test for the generated FreeSWITCH core:
#   * FreeSWITCH loads the generated config and opens the SIP listeners
#   * the generated directory (extensions) is queryable
#   * the generated dialplan actually executes (loopback call through echo
#     test; CSV call detail records for the finished call)
#   * a scripted SIP client (tests/sip.py) registers over TCP with digest
#     auth, gets rejected on bad credentials and holds two registrations
#     at once (multi-device)
#   * a dialled echo call is answered with media (PCMU) and completes
#   * denial paths: E.164 without a gateway answers 503, unknown numbers
#     answer 404
#   * an unanswered ring group times out into the voicemail fallback
#   * *98 reaches the voicemail-check application
let
  common = import ./common.nix;

  # machine only: CSV call detail records enabled.
  cdrTestConfig = {
    services.telephony.cdr.enable = true;
  };
in
{
  name = "telephony-dialplan";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode ++ [ cdrTestConfig ];
    };

  testScript = ''
    # NOTE: no start_all() — machines start lazily at their first command.
    # Booting several QEMU VMs at once stalled one node's sofia mid-start
    # on shared CI runners (nested KVM, 100% reproducible there, never
    # locally even pinned to a single core); staggering the heavy sofia
    # startup phase recreates the known-green one-VM-at-a-time condition.
    machine.wait_for_unit("freeswitch.service")
    machine.wait_for_open_port(5060)

    es_password = "test-es-4d5e6f"
    fs_cli = f"fs_cli -p {es_password} -x"

    # FreeSWITCH must have loaded the generated sofia profiles.
    machine.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep internal")
    machine.wait_until_succeeds(f"{fs_cli} 'sofia status' | grep external")
    internal = machine.succeed(f"{fs_cli} 'sofia status profile internal'")
    assert "Context" in internal and "default" in internal, internal

    # The WebSocket transport for the nginx TLS proxy must be bound to loopback.
    assert "127.0.0.1:5066" in internal, internal

    # Directory: generated users exist with the configured password.
    password = machine.succeed(f"{fs_cli} 'user_data 1000@pbx.test param password'")
    assert password.strip() == "test-1000-x9y8z7", password

    # Dialplan executes end to end: a loopback call into the echo-test
    # extension must be answered by the echo application.
    originate = machine.succeed(f"{fs_cli} 'originate loopback/9196 &park()'")
    assert originate.startswith("+OK"), originate
    # Tear the parked loopback call down so later `show channels` greps
    # only see calls placed by the scripted SIP client.
    machine.succeed(f"{fs_cli} 'hupall'")
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'")

    # CDR: the finished call leaves a row in Master.csv.
    machine.wait_until_succeeds(
        "grep 9196 /var/lib/freeswitch/cdr-csv/Master.csv", timeout=30
    )

    # --- SIP-level checks with the scripted client (tests/sip.py) ---
    def sip_server(node):
        listener = node.succeed("ss -ltn 'sport = :5060' | grep -v State").strip()
        ip = listener.split()[3].rsplit(":", 1)[0]
        return "::1" if ip.startswith("[") else ip

    sip_ip = sip_server(machine)
    sip = (
        f"python3 /etc/sip.py --server {sip_ip} --domain pbx.test "
        "--user 1000 --password test-1000-x9y8z7"
    )

    # REGISTER with correct credentials is accepted and listed by sofia.
    out = machine.succeed(f"{sip} register")
    assert "REGISTER 200" in out, out
    machine.wait_until_succeeds(
        f"{fs_cli} 'sofia status profile internal reg' | grep 1000"
    )

    # REGISTER with a wrong password must be rejected after the challenge.
    status, wrong = machine.execute(
        f"python3 /etc/sip.py --server {sip_ip} --domain pbx.test "
        "--user 1000 --password definitely-wrong register"
    )
    assert status != 0, wrong
    assert "REGISTER 401" in wrong or "REGISTER 403" in wrong, wrong

    # A second registration from another client (different source port)
    # must coexist: multiple-registrations is on.
    machine.succeed(f"{sip} register")
    regs = machine.succeed(f"{fs_cli} 'sofia status profile internal reg'")
    assert regs.count("Call-ID:") == 2, regs

    # INVITE through the dialplan: the echo test must answer (200 with
    # SDP), stay up while we check channel state, then hang up cleanly.
    machine.succeed(
        f"nohup {sip} invite --to 9196 --hold-seconds 6 >/tmp/invite.log 2>&1 &"
    )
    machine.wait_until_succeeds(
        f"{fs_cli} 'show channels' | grep 'sofia/internal/1000@pbx.test'", timeout=60
    )
    media = machine.succeed(f"{fs_cli} 'show detailed_calls'")
    assert "9196" in media and "PCMU" in media, media
    machine.wait_until_succeeds("grep -q 'CALL COMPLETE' /tmp/invite.log", timeout=60)
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'")
    # Drop the helper's registrations so later bridge tests hit clean
    # USER_NOT_REGISTERED failures instead of dead TCP contacts.
    machine.succeed(f"{fs_cli} 'sofia profile internal flush_inbound_reg'")

    # Denial: with no gateway configured, E.164 calls answer 503.
    machine.succeed(
        f"{fs_cli} 'console loglevel debug' && {fs_cli} 'sofia global siptrace on'"
    )
    status503, unavailable = machine.execute(
        f"{sip} invite --to 12345678901 --expect-status 503"
    )
    status404, unknown = machine.execute(
        f"{sip} invite --to 555 --expect-status 404"
    )
    if status503 != 0 or status404 != 0:
        print(machine.succeed("journalctl -u freeswitch -q --no-pager | tail -n 150"))
    machine.succeed(
        f"{fs_cli} 'sofia global siptrace off' && {fs_cli} 'console loglevel info'"
    )
    assert status503 == 0, unavailable
    assert "INVITE 503" in unavailable, unavailable
    assert status404 == 0, unknown
    assert "INVITE 404" in unknown, unknown

    # --- Ring-group fallback: an unanswered 2000 rings (early media),
    # times out after the group's 25s and is answered by the voicemail
    # fallback — the only possible 200 for this call. ---
    machine.succeed(
        f"nohup {sip} invite --to 2000 --hold-seconds 3 >/tmp/ringgroup.log 2>&1 &"
    )
    machine.wait_until_succeeds("grep -q 'CALL COMPLETE' /tmp/ringgroup.log", timeout=120)
    ringgroup_log = machine.succeed("cat /tmp/ringgroup.log")
    assert "ANSWERED" in ringgroup_log, ringgroup_log
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'", timeout=60)

    # --- *98 reaches the voicemail-check application (answered by it) ---
    machine.succeed(
        f"nohup {sip} invite --to '*98' --hold-seconds 3 >/tmp/vmcheck.log 2>&1 &"
    )
    machine.wait_until_succeeds("grep -q 'CALL COMPLETE' /tmp/vmcheck.log", timeout=60)
    vmcheck_log = machine.succeed("cat /tmp/vmcheck.log")
    assert "ANSWERED" in vmcheck_log, vmcheck_log
    machine.wait_until_succeeds(f"{fs_cli} 'show channels' | grep '^0 total'", timeout=60)
  '';
}
