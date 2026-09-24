# NAT advertisement runtime suite: the PBX sits behind a port-forwarding
# router (the classic single-public-IP deployment `natAddress` models).
# A scripted caller on the OUTER network can reach the PBX only through
# the router's forward, so:
#   * the call COMPLETING (INVITE -> 200 -> ACK -> hold -> BYE) proves
#     the advertised Contact was routable from outside — a private-IP
#     Contact strands ACK/BYE on an unreachable address
#   * the dumped 200 OK must carry natAddress in Via, Contact and the
#     SDP connection line, wiring ext-sip-ip/ext-rtp-ip to observable
#     on-the-wire behavior (promotes the FEATURES natAddress row)
#
# Topology (framework vlans, addresses auto-assigned 192.168.<vlan>.<n>):
#   vlan 1 (outer): caller + router-eth1   <- caller dials the router
#   vlan 2 (inner): router-eth2 + pbx      <- pbx default-gateway via router
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
in
{
  name = "telephony-nat";

  nodes.caller =
    { pkgs, ... }:
    {
      networking.useDHCP = false;
      networking.firewall.enable = false;
      environment.etc."sip.py".source = ./sip.py;
      environment.systemPackages = [ pkgs.python3 ];
      virtualisation.vlans = [ 1 ];
    };

  nodes.pbx =
    {
      nodes,
      lib,
      ...
    }:
    {
      imports = common.baseNode;
      networking.useDHCP = false;
      # Replies to the outer network flow back through the router (and a
      # default route is what makes sofia bind the vlan address at all —
      # without one it silently falls back to loopback).
      networking.defaultGateway =
        (lib.head nodes.router.networking.interfaces.eth2.ipv4.addresses).address;
      # The "public" address callers use is the router's OUTER interface;
      # the PBX advertises it in Via/Contact/SDP.
      services.telephony.natAddress =
        (lib.head nodes.router.networking.interfaces.eth1.ipv4.addresses).address;
      virtualisation.vlans = [ 2 ];
    };

  nodes.router =
    {
      nodes,
      lib,
      ...
    }:
    {
      networking.useDHCP = false;
      networking.firewall.enable = false;
      virtualisation.vlans = [
        1
        2
      ];
      networking.nat =
        let
          pbxIp = (lib.head nodes.pbx.networking.interfaces.eth1.ipv4.addresses).address;
        in
        {
          enable = true;
          externalInterface = "eth1";
          internalInterfaces = [ "eth2" ];
          internalIPs = [ "192.168.2.0/24" ];
          forwardPorts = [
            {
              destination = "${pbxIp}:5060";
              proto = "tcp";
              sourcePort = 5060;
            }
            {
              destination = "${pbxIp}:5060";
              proto = "udp";
              sourcePort = 5060;
            }
          ];
        };
    };

  testScript =
    { nodes, ... }:
    let
      natIp = (builtins.head nodes.router.networking.interfaces.eth1.ipv4.addresses).address;
    in
    ''
      ${common.bootWait}

      # The router's DNAT must be up before anything speaks SIP through it.
      router.wait_for_unit("nat.service")
      # Interface configuration is asynchronous on every node; wait for
      # each side's addresses before routing assertions (the first run
      # raced the caller: ping hit "Network is unreachable").
      router.wait_until_succeeds("ip -4 addr show dev eth1 | grep -q 192.168.1")
      router.wait_until_succeeds("ip -4 addr show dev eth2 | grep -q 192.168.2")
      pbx.wait_until_succeeds("ip -4 addr show dev eth1 | grep -q 192.168.2")
      caller.wait_until_succeeds("ip -4 addr show dev eth1 | grep -q 192.168.1")

      wait_for_freeswitch(pbx, "test-es-4d5e6f")

      # Sanity: the caller reaches the router's outer address at all.
      caller.wait_until_succeeds("ping -c 1 -W 2 ${natIp} >&2")

      # A real call from the OUTER network: REGISTER + INVITE to the echo
      # extension through the forward, with the 200 OK dumped for the
      # advertisement asserts.
      out = caller.succeed(
          "python3 /etc/sip.py --server ${natIp} --domain pbx.test "
          "--user 1001 --password test-1001-u6t5s4 "
          "invite --to 9196 --hold-seconds 3 --dump-dialog"
      )
      assert "CALL COMPLETE" in out, out
      assert "DIALOG-BEGIN" in out, out
      dialog = out.split("DIALOG-BEGIN", 1)[1].split("DIALOG-END", 1)[0]

      # Via/Contact/SDP all advertise the public address; the private
      # 192.168.2.x must appear in none of them.
      contact = next(
          (l for l in dialog.splitlines() if l.lower().startswith("contact:")), "")
      assert "${natIp}" in contact, f"Contact must advertise natAddress: {contact}"
      via = [l for l in dialog.splitlines() if l.lower().startswith("via:")]
      assert via and any("${natIp}" in l for l in via), f"Via must advertise natAddress: {via}"
      sdp_c = [l for l in dialog.splitlines() if l.startswith("c=IN IP4")]
      assert sdp_c and all("${natIp}" in l for l in sdp_c), (
          f"SDP connection line must advertise natAddress: {sdp_c}"
      )
      advertised = [contact] + via + sdp_c
      assert not any("192.168.2." in l for l in advertised), (
          f"private inner address leaked into the advertisement: {advertised}"
      )
    '';
}
