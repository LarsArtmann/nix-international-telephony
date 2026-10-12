# Forward-auth mode end-to-end (2026-10-12, pbx-artmann SSO plan): the
# /recordings/ and /operator/ + /operator-api/ surfaces in
# authMode = "forwardAuth" delegate every request to an external auth
# service via nginx auth_request. A fake gate on loopback answers per
# the client's X-Test-Gate header (the auth_request subrequest INHERITS
# client request headers), so one boot covers every leg:
#   * gate 401 -> 302 to signInUrl with the original absolute URL
#     appended (no BASIC prompt ever — the satisfy-any trap)
#   * gate 403 -> 403 through (authenticated, wrong group)
#   * gate 200 -> the surface serves content
#   * loopback source (the server itself, ssh -L break-glass) bypasses
#     even a denying gate
#   * no htpasswd is rendered for forwardAuth surfaces (operator-auth
#     still writes its non-htpasswd credentials)
# The gated probes run from a CLIENT node: requests from the server's
# own loopback would hit the break-glass allow and never reach the gate.
{ telephonyModule, webphonePackage }:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  signInUrl = "https://sso.example.test/oauth2/start?rd=";
  gateUrl = "http://127.0.0.1:9090/gate";
in
{
  name = "telephony-forward-auth";

  nodes = {
    server =
      { pkgs, ... }:
      {
        imports = common.baseNode;

        services.telephony = {
          recording.serve = {
            enable = true;
            authMode = "forwardAuth";
            forwardAuth = {
              authUrl = gateUrl;
              inherit signInUrl;
            };
          };
          operator = {
            enable = true;
            authMode = "forwardAuth";
            forwardAuth = {
              authUrl = gateUrl;
              inherit signInUrl;
            };
          };
        };

        # The fake gate: decides by the inherited X-Test-Gate header.
        services.nginx.virtualHosts."fakegate" = {
          serverName = "fakegate";
          listen = [ { addr = "127.0.0.1"; port = 9090; } ];
          locations."/gate" = {
            extraConfig = ''
              if ($http_x_test_gate = deny) { return 401; }
              if ($http_x_test_gate = forbid) { return 403; }
              return 200;
            '';
          };
        };
      };

    client =
      { pkgs, ... }:
      {
        environment.systemPackages = [ pkgs.curl ];
      };
  };

  testScript = ''
    ${common.bootWait}

    server.wait_for_unit("nginx.service")
    server.wait_for_open_port(443)
    server.wait_for_unit("telephony-operator.service")
    client.wait_for_unit("multi-user.target")

    base = "https://server"
    surfaces = ["/recordings/", "/operator/", "/operator-api/health"]

    def status(path, gate):
        return client.succeed(
            "curl -k -s -o /dev/null -w '%{http_code}'"
            f" -H 'X-Test-Gate: {gate}' {base}{path}"
        ).strip()

    def redirect(path, gate):
        return client.succeed(
            "curl -k -s -o /dev/null -w '%{redirect_url}'"
            f" -H 'X-Test-Gate: {gate}' {base}{path}"
        ).strip()

    # --- 401 leg: 302 to the sign-in URL, original URL carried in rd ---
    for path in surfaces:
        with client.nested(f"unauthenticated {path} redirects to sign-in"):
            assert status(path, "deny") == "302", path
            loc = redirect(path, "deny")
            assert loc.startswith("${signInUrl}"), f"{path}: {loc}"
            assert (base + path) in loc, f"{path}: rd must carry the original URL: {loc}"

    # --- 403 leg: authenticated but not allowed -> 403 through ---
    for path in surfaces:
        with client.nested(f"forbidden {path} fails through"):
            code = status(path, "forbid")
            assert code == "403", f"{path}: expected 403, got {code}"

    # --- 200 leg: the gate allows -> the surface serves ---
    with client.nested("allowed requests are served"):
        assert status("/recordings/", "allow") == "200"
        assert status("/operator/", "allow") == "200"
        assert status("/operator-api/health", "allow") == "200"

    # --- break-glass: a LOOPBACK source bypasses even a denying gate ---
    with server.nested("loopback break-glass bypasses the gate"):
        code = server.succeed(
            "curl -k -s -o /dev/null -w '%{http_code}'"
            " -H 'X-Test-Gate: deny' https://localhost/recordings/"
        ).strip()
        assert code == "200", f"break-glass: expected 200, got {code}"

    # --- forwardAuth surfaces render no htpasswd at all; the operator
    # unit's OTHER credentials (ESL password) still land ---
    with server.nested("no htpasswd for forwardAuth surfaces"):
        server.fail("test -e /var/lib/telephony/recordings.htpasswd")
        server.succeed("test -s /var/lib/telephony/operator/esl-password")

    # --- and the basic-mode contract is untouched by this train:
    # telephony-operator-auth stays a oneshot before nginx ---
    server.succeed("systemctl is-active telephony-operator-auth.service")
  '';
}
