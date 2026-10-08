# Register=false gateway suite (routed gap from reports 2026-09-18_14-47
# §f.11/§f.22): the production trunk shape — a gateway that NEVER
# registers must sit NOREG (sofia's permanently-UP-for-outbound state,
# never a REG state machine), must not send a single REGISTER, and an
# outbound INVITE must digest-auth PER CALL (407 challenge ->
# Proxy-Authorization retry -> 200) against a scripted fake ITSP. Until
# this suite all of that was pinned by prose only ("register = false
# makes the gateway NOREG = permanently UP; outbound INVITEs still
# digest-auth fine per call", AGENTS pbx-artmann trunk gotcha).
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-noreg-gateway";

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
            # The stub speaks UDP; the proxy uses the module's canonical
            # form — bare host + transport param, NO "sip:" scheme
            # prefix and no port (production: "sip.telnyx.com;transport=tcp",
            # where "sip." is the hostname, not a scheme). The earlier
            # scheme-prefixed shape ("sip:IP:5060;transport=udp") died
            # 502 DESTINATION_OUT_OF_ORDER with zero packets reaching
            # the stub (two driver runs, empty stub log) — matching the
            # proven production shape is the probe.
            proxy = "${(lib.head nodes.itsp.networking.interfaces.eth1.ipv4.addresses).address};transport=udp";
            username = "noregtest";
            password = "test-gw-noreg";
            register = false;
            did = "15551230000";
            didDestination = "2000";
            allowedCidrs = [ "127.0.0.1/32" ];
          };
        }
      ];
      virtualisation.vlans = [ 1 ];
    };

  nodes.itsp =
    { pkgs, ... }:
    {
      networking.firewall.enable = false;
      environment.etc."itsp-stub.py".source = ./itsp_stub.py;
      systemd.services.itsp-stub = {
        description = "Scripted ITSP: 407-challenge once, accept digest INVITEs";
        wantedBy = [ "multi-user.target" ];
        serviceConfig = {
          Type = "simple";
          ExecStart = "${pkgs.python3}/bin/python3 /etc/itsp-stub.py /tmp/itsp.log";
          Restart = "on-failure";
        };
      };
      virtualisation.vlans = [ 1 ];
    };

  testScript = _: ''
    ${common.bootWait}

    itsp.wait_for_unit("itsp-stub.service")
    wait_for_freeswitch(pbx, "test-es-4d5e6f")

    fs_cli = "fs_cli -p test-es-4d5e6f -x"

    # The external profile (which owns the gateway) loads AFTER the
    # internal one; an INVITE racing its startup dies 502
    # DESTINATION_OUT_OF_ORDER before any packet leaves the host (the
    # first driver run's lesson — the gateway object exists before the
    # profile can carry its calls).
    pbx.wait_until_succeeds(
        fs_cli + " 'sofia status' | grep external | grep -q RUNNING",
        timeout=datetime.timedelta(seconds=120),
    )

    # --- NOREG: the register=false gateway is live WITHOUT a REG state
    # machine (NOREG is sofia's "no registration, usable for outbound"
    # state — the whole point of the production setting).
    status = pbx.wait_until_succeeds(
        fs_cli + " 'sofia status gateway itsp'",
        timeout=datetime.timedelta(seconds=60),
    )
    assert "NOREG" in status, status
    for bad_state in ("TRYING", "FAILED", "FAIL_WAIT", "REGED"):
        assert bad_state not in status, f"register=false gateway shows {bad_state}: {status}"

    # Config truth, not runtime luck: the generated XML pins it.
    gw_xml = pbx.succeed(
        "grep -A12 'gateway name=\"itsp\"' /nix/store/*freeswitch-config-*/sip_profiles/external.xml"
    )
    assert 'param name="register" value="false"' in gw_xml, gw_xml

    # A register=true twin would have fired REGISTERs long before this
    # (FreeSWITCH's first attempt is immediate; the state machine above
    # already proves none ran). Belt and braces: the stub never saw one.
    pbx.succeed("sleep 20")
    itsp.succeed("! grep -q UNEXPECTED-REGISTER /tmp/itsp.log")

    # --- Forensics (2026-10-08 run 4): the bridge DID engage the
    # gateway (New Channel sofia/external/...) yet the outbound leg
    # died 503 NORMAL_TEMPORARY_FAILURE with ZERO packets at the stub.
    # Before any theory: dump the live bindings, prove raw UDP
    # reachability with a hand-rolled INVITE, and trace the real one.
    pbx.succeed(fs_cli + " 'console loglevel debug'")
    pbx.succeed(fs_cli + " 'sofia global siptrace on'")
    print("=== sofia status profile external ===")
    print(pbx.succeed(fs_cli + " 'sofia status profile external'"))
    print("=== sofia status gateway itsp ===")
    print(pbx.succeed(fs_cli + " 'sofia status gateway itsp'"))
    itsp_ip = itsp.succeed("ip -4 -o addr show dev eth1").split()[3].split("/")[0]
    print("=== itsp eth1 runtime address: " + itsp_ip)
    pbx.succeed(
        "python3 -c 'import socket,base64;"
        "socket.socket(socket.AF_INET,socket.SOCK_DGRAM)"
        ".sendto(base64.b64decode(\"SU5WSVRFIHNpcDp4QHkgU0lQLzIuMA0KQ2FsbC1JRDogcmF3dWRwLXByb2JlDQoNCg==\")"
        ",(\""
        + itsp_ip
        + "\", 5060))'"
    )
    itsp.wait_until_succeeds(
        "grep -q 'CHALLENGE rawudp-probe' /tmp/itsp.log",
        timeout=datetime.timedelta(seconds=10),
    )

    # --- Outbound through the NOREG gateway digest-auths PER CALL:
    # extension 1001 (toll_allow granted) dials E.164, the dialplan's
    # international arm bridges sofia/gateway/itsp, the stub 407-
    # challenges once, sofia retries with Proxy-Authorization and the
    # call ANSWERS (caller sees 200).
    out = pbx.succeed(
        "python3 /etc/sip.py --server " + sip_server(pbx) + " --domain pbx.test "
        "--user 1001 --password test-1001-u6t5s4 invite --to 12345678901 "
        "--hold-seconds 3"
    )
    assert "INVITE 200" in out, out

    itsp.wait_until_succeeds(
        "grep -q CHALLENGE /tmp/itsp.log", timeout=datetime.timedelta(seconds=10)
    )
    itsp.wait_until_succeeds(
        "grep -q DIGEST-INVITE /tmp/itsp.log", timeout=datetime.timedelta(seconds=10)
    )
    stub_log = itsp.succeed("cat /tmp/itsp.log")
    # The digest carried the gateway's username — the wiring, not just
    # any Authorization header.
    assert 'username="noregtest"' in stub_log, stub_log
  '';
}
