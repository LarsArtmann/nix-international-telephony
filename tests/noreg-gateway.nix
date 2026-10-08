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
            # BARE host, no ";transport=..." suffix — proven the hard way
            # (runs 1-8): FreeSWITCH 1.11.1's gateway-challenge anti-spoof
            # check (is_legitimate_gateway -> is_host_from_gateway in
            # sofia_reg.c) compares the 407's SOURCE IP against
            # gateway->proxy_host_cfg, which sofia_glue_get_host_from_cfg
            # builds by stripping only a "sip:" prefix and truncating at
            # the last ":". A ";transport=udp" suffix therefore LEAKS into
            # the host string ("192.168.1.1;transport=udp" is neither an
            # IP nor a domain), the challenge is judged illegitimate, the
            # 407 is ACK'd and abandoned, and the caller dies 480
            # cause=96 MANDATORY_IE_MISSING. A bare IP matches via
            # host_is_ip_address + strcmp; the stub speaks UDP, which is
            # the gateway register_transport default anyway. (Production's
            # "sip.telnyx.com;transport=tcp" carries the same latent
            # breakage against Telnyx 407s — routed to pbx-artmann's
            # TODO_LIST; the production value lives there, not here.)
            proxy = "${(lib.head nodes.itsp.networking.interfaces.eth1.ipv4.addresses).address}";
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
      # sofia resolves `$${local_ip_v4}` by UDP-connecting toward an
      # external address — it binds the DEFAULT ROUTE's egress
      # interface. The QEMU user-net eth0 (10.0.2.15) is per-VM
      # isolated: an outbound gateway INVITE sourced from it reaches
      # the stub over the VLAN, but the stub's 407 back to 10.0.2.15
      # lands on the STUB'S OWN eth0 — unrepliable (forensic run 5:
      # raw-UDP probe green, INVITE sent per siptrace, caller
      # TimeoutError). Kill eth0's DHCP lease and route the default
      # via the VLAN so FreeSWITCH binds the eth1 address; the gateway
      # address is never contacted, only route-looked-up.
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
