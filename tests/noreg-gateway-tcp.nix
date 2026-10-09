# TCP trunk-shape suite (pbx-artmann TODO §3 lab proof): the production
# gateway proxy `sip.telnyx.com;transport=tcp` cannot pass sofia's
# gateway-challenge anti-spoof check — `sofia_glue_get_host_from_cfg`
# truncates at the LAST ":" without stripping URI params, so the
# ";transport=tcp" suffix leaks into `proxy_host_cfg`,
# `is_legitimate_gateway` rejects the 407, and the caller dies 480
# cause=96 MANDATORY_IE_MISSING (docs/lessons/freeswitch.md,
# 2026-10-08). Candidate fix shape (b): `host:5060;transport=tcp` — the
# port's colon makes the truncation yield the clean host while the
# routed URI keeps TCP. This suite pins that shape end to end against a
# TCP-speaking fake ITSP: NOREG state, no REGISTER, the 407 is answered
# with a digest retry (the anti-spoof check PASSED), and the call
# ANSWERS — all with ";transport=tcp" still in the proxy value.
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-noreg-gateway-tcp";

  nodes.pbx =
    {
      nodes,
      lib,
      ...
    }:
    {
      imports = common.baseNode ++ [
        {
          services.telephony.gateways.itsp = {
            # The candidate production shape: URI params present, but a
            # ":port" BEFORE them so the last-":" truncation keeps the
            # host clean. The name resolves to the stub's VLAN IP via
            # /etc/hosts — the same resolution path production's
            # sip.telnyx.com takes.
            proxy = "sip.telnyx.test:5060;transport=tcp";
            username = "noregtest";
            password = "test-gw-noreg";
            register = false;
            did = "15551230000";
            didDestination = "2000";
            allowedCidrs = [ "127.0.0.1/32" ];
          };
          networking.hosts."${(lib.head nodes.itsp.networking.interfaces.eth1.ipv4.addresses).address}" =
            [ "sip.telnyx.test" ];
        }
      ];
      virtualisation.vlans = [ 1 ];
      # Same default-route lesson as the UDP suite: sofia must bind and
      # source from eth1, not the per-VM user-net eth0.
      networking = {
        useDHCP = false;
        defaultGateway = (lib.head nodes.itsp.networking.interfaces.eth1.ipv4.addresses).address;
      };
    };

  nodes.itsp =
    { pkgs, ... }:
    {
      networking.firewall.enable = false;
      environment.etc."itsp-stub.py".source = ./itsp_stub.py;
      systemd.services.itsp-stub = {
        description = "Scripted ITSP (TCP): 407-challenge once, accept digest INVITEs";
        wantedBy = [ "multi-user.target" ];
        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.python3}/bin/python3 /etc/itsp-stub.py --tcp /tmp/itsp.log";
          Restart = "on-failure";
        };
      };
      virtualisation.vlans = [ 1 ];
    };

  testScript = _: ''
    ${common.bootWait}

    itsp.wait_for_unit("itsp-stub.service")
    # The TCP variant of the stub must actually be listening in TCP mode
    # before any assertion about the transport is meaningful.
    itsp.wait_until_succeeds("grep -q 'LISTEN tcp' /tmp/itsp.log",
                             timeout=datetime.timedelta(seconds=30))
    wait_for_freeswitch(pbx, "test-es-4d5e6f")

    fs_cli = "fs_cli -p test-es-4d5e6f -x"

    pbx.wait_until_succeeds(
        fs_cli + " 'sofia status' | grep external | grep -q RUNNING",
        timeout=datetime.timedelta(seconds=120),
    )

    # NOREG like the UDP suite: register=false never enters a REG state
    # machine even with the param-bearing proxy.
    status = pbx.wait_until_succeeds(
        fs_cli + " 'sofia status gateway itsp'",
        timeout=datetime.timedelta(seconds=60),
    )
    assert "NOREG" in status, status
    for bad_state in ("TRYING", "FAILED", "FAIL_WAIT", "REGED"):
        assert bad_state not in status, f"register=false gateway shows {bad_state}: {status}"

    # Config truth: the generated XML carries the FULL param-bearing
    # value verbatim (this is the string whose last-":" truncation must
    # yield the clean host for the anti-spoof check).
    gw_xml = pbx.succeed(
      "grep -A12 'gateway name=\"itsp\"' /nix/store/*freeswitch-config-*/sip_profiles/external.xml"
    )
    assert 'param name="proxy" value="sip.telnyx.test:5060;transport=tcp"' in gw_xml, gw_xml

    pbx.succeed("sleep 20")
    itsp.succeed("! grep -q UNEXPECTED-REGISTER /tmp/itsp.log")

    # Outbound over the TCP gateway: INVITE rides a TCP connection to
    # the stub, the 407 challenge is answered with a digest retry (the
    # anti-spoof check accepted the challenge source — THE regression
    # this suite pins; the bare ";transport=tcp" shape dies here with
    # zero journal explanation), and the caller sees 200. Evidence dump
    # on failure: a silent caller timeout must be diagnosable from the
    # log alone.
    gw_status = pbx.succeed(fs_cli + " 'sofia status gateway itsp'");
    print("GATEWAY-STATUS-BEGIN\\n" + gw_status + "GATEWAY-STATUS-END\\n")
    try:
        out = pbx.succeed(
            "python3 /etc/sip.py --server " + sip_server(pbx) + " --domain pbx.test "
            "--user 1001 --password test-1001-u6t5s4 invite --to 12345678901 "
            "--hold-seconds 3"
        )
        assert "INVITE 200" in out, out
    except Exception:
        print("STUB-LOG-BEGIN\\n" + itsp.succeed("cat /tmp/itsp.log") + "STUB-LOG-END\\n")
        print(
            "FS-JOURNAL-BEGIN\\n"
            + pbx.succeed(
                "journalctl -u freeswitch -n 200 --no-pager | grep -iE 'tport|gateway|tcp|sip' | tail -40"
            )
            + "FS-JOURNAL-END\\n"
        )
        raise

    itsp.wait_until_succeeds(
        "grep -q CHALLENGE /tmp/itsp.log", timeout=datetime.timedelta(seconds=10)
    )
    itsp.wait_until_succeeds(
        "grep -q DIGEST-INVITE /tmp/itsp.log", timeout=datetime.timedelta(seconds=10)
    )
    stub_log = itsp.succeed("cat /tmp/itsp.log")
    assert 'username="noregtest"' in stub_log, stub_log
  '';
}
