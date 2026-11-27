# Dashboard-on VM leg (the 2026-10-23 404-health stack residue, closed
# 2026-11-27): boots the stack with `webphone.dashboard.enable = true` and
# asserts the operator window end to end — the page renders through the
# vhost FENCE (loopback-only: nginx `allow 127.0.0.1; allow ::1; deny all`
# in modules/telephony/web.nix dashboardLocation), the probe aliases ride
# the same probe instance, and a non-loopback source is denied. The OFF
# state (styled 404 at /health) stays webphone-side (its TestDashboard*
# suite + the boot smoke).
{
  telephonyModule,
  webphonePackage,
  kvm ? true,
  slowBoot ? false,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  # Under TCG the guest boots and starts sofia far slower than under KVM.
  bootTimeouts = if slowBoot then ", port_timeout=900, unit_timeout=900" else "";
in
{
  name = if kvm then "telephony-webphone-dashboard" else "telephony-webphone-dashboard-tcg";

  requiredFeatures.kvm = kvm;

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;
      services.telephony.webphone.dashboard.enable = true;
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f"${bootTimeouts})
    machine.wait_for_unit("webphone.service")
    machine.wait_for_open_port(8080)
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)

    # The page renders through the vhost fence from loopback: the
    # dashboard's own connection-state marker, NOT the styled 404 the
    # OFF state answers with.
    page = machine.succeed("curl -k -sf https://localhost/health")
    assert "conn-state-live" in page, page[:300]
    assert "wp-notfound" not in page, page[:300]

    # The probe aliases ride the SAME probe instance.
    machine.succeed("curl -k -sf https://localhost/health/livez")
    machine.succeed("curl -k -sf https://localhost/health/readyz")

    # The fence denies non-loopback sources (nginx deny all → 403).
    import re

    route = machine.succeed("ip -4 route get 1.1.1.1")
    match = re.search(r"src ([0-9.]+)", route)
    assert match is not None, route
    egress_ip = match.group(1)
    code = machine.succeed(
        "curl -k -s -o /dev/null -w '%{http_code}' https://" + egress_ip + "/health"
    ).strip()
    assert code == "403", f"non-loopback /health must be 403, got {code}"

    # The direct app port serves the same page (the fence is the vhost's
    # job; the app-side gate is dashboard.enable itself).
    direct = machine.succeed("curl -sf http://127.0.0.1:8080/health")
    assert "conn-state-live" in direct, direct[:300]
  '';
}
