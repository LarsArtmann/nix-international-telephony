# Split-trunk-profile suite (the 2026-11-18 source-port root cause,
# pbx-artmann docs/evidence/2026-11-18-trunk-source-port): with
# trunkProfilePort set, every gateway renders into a dedicated "trunk"
# sofia profile on its own port and the external profile stays
# inbound-only — so outbound INVITEs egress a socket the carrier cannot
# attribute to the inbound connection (the Telnyx FQDN-connection tuple
# match that rejected every trunk call for 57 days). The machine proof:
# the fake ITSP logs the INVITE's SOURCE PORT and the test pins it to
# the trunk profile's port, something the classic shape could never
# provide (the gateway rode external's :5080).
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-noreg-gateway-split";

  nodes.pbx =
    {
      nodes,
      lib,
      ...
    }:
    {
      imports = common.baseNode ++ [
        {
          services.telephony.trunkProfilePort = 5090;
          services.telephony.monitoring.enable = true;
          services.telephony.gateways.itsp = {
            # Same bare-host proxy rule as tests/noreg-gateway.nix: a
            # ";transport=..." suffix leaks into the gateway-challenge
            # anti-spoof host comparison and kills every 407 dance.
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
      # Same egress-interface dance as the classic suite: sofia binds
      # $${local_ip_v4} from the DEFAULT ROUTE, so the VLAN must carry it
      # or the stub's 407 cannot reach the trunk profile's socket.
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

    # Both profiles RUNNING — and the trunk profile actually BOUND its
    # dedicated port (the listener is the whole point of the split).
    pbx.wait_until_succeeds(
        fs_cli + " 'sofia status' | grep external | grep -q RUNNING",
        timeout=datetime.timedelta(seconds=120),
    )
    pbx.wait_until_succeeds(
        fs_cli + " 'sofia status' | grep trunk | grep -q RUNNING",
        timeout=datetime.timedelta(seconds=120),
    )
    pbx.succeed("ss -ltn | grep -q ':5090'")

    # Config truth: the gateway moved to trunk.xml; external.xml carries
    # no gateway block at all (it is inbound-only now).
    gw_xml = pbx.succeed(
        "grep -A12 'gateway name=\"itsp\"' /nix/store/*freeswitch-config-*/sip_profiles/trunk.xml"
    )
    assert 'param name="register" value="false"' in gw_xml, gw_xml
    pbx.succeed(
        "! grep -q 'gateway name=' /nix/store/*freeswitch-config-*/sip_profiles/external.xml"
    )

    # The health check must know the new profile: a one-shot run passes
    # with trunk RUNNING (a dead trunk profile is the blind-canary class).
    pbx.succeed("systemctl start telephony-health.service")

    # --- Outbound through the split gateway: NOREG, digest per call,
    # and the INVITE egresses the TRUNK profile's socket.
    status = pbx.wait_until_succeeds(
        fs_cli + " 'sofia status gateway itsp'",
        timeout=datetime.timedelta(seconds=60),
    )
    assert "NOREG" in status, status

    pbx.succeed("sleep 20")
    itsp.succeed("! grep -q UNEXPECTED-REGISTER /tmp/itsp.log")

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
    assert 'username="noregtest"' in stub_log, stub_log
    # THE proof this suite exists for: the outbound INVITE left the
    # trunk profile's port, not external's 5080.
    assert "SRC-PORT 5090" in stub_log, stub_log
  '';
}
