# Native-OAuth recordings mode end-to-end (2026-10-28, the owner's
# "apps do OAuth natively" directive): the /recordings/ surface in
# authMode = "oidc" is served by the telephony-recordings-view app, and
# nginx is a dumb prefix-stripping proxy — NO auth_request, NO
# oauth2-proxy, NO htpasswd. A loopback stub IdP (real discovery,
# authorize, token, userinfo endpoints) rides on the server at a
# hostname BOTH nodes resolve, so the client node drives the WHOLE
# dance like a browser would:
#   * unauthenticated /recordings/ -> 302 into the login route
#   * login -> 302 to the IdP authorize URL with PKCE S256 + state
#   * stub authorize -> 302 back with code+state; callback exchanges it
#     and mints the session
#   * the session unlocks the listing and the file stream
#   * an identity WITHOUT the required group answers the typed
#     sso_error=group page (fail-closed)
{ telephonyModule, webphonePackage }:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  issuer = "http://server:8901";

  stubIdp =
    pkgs:
    pkgs.writeText "stub-idp.py" ''
      """Minimal OIDC stub: discovery + authorize + token + userinfo.

      Userinfo comes from STUB_USERINFO_FILE, read PER REQUEST so the test
      can flip the identity between the group-ok and group-missing legs.
      """
      import json
      import os
      import urllib.parse
      from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

      USERINFO_FILE = os.environ.get("STUB_USERINFO_FILE", "/tmp/stub-userinfo.json")
      ISSUER = os.environ.get("STUB_ISSUER", "${issuer}")

      class Handler(BaseHTTPRequestHandler):
          def log_message(self, fmt, *args):
              pass

          def _json(self, payload, status=200):
              body = json.dumps(payload).encode()
              self.send_response(status)
              self.send_header("Content-Type", "application/json")
              self.send_header("Content-Length", str(len(body)))
              self.end_headers()
              self.wfile.write(body)

          def _redirect(self, location):
              self.send_response(302)
              self.send_header("Location", location)
              self.end_headers()

          def do_GET(self):
              parsed = urllib.parse.urlsplit(self.path)
              q = urllib.parse.parse_qs(parsed.query)
              if parsed.path == "/.well-known/openid-configuration":
                  self._json({
                      "issuer": ISSUER,
                      "authorization_endpoint": f"{ISSUER}/authorize",
                      "token_endpoint": f"{ISSUER}/token",
                      "userinfo_endpoint": f"{ISSUER}/userinfo",
                  })
              elif parsed.path == "/authorize":
                  rd = (q.get("redirect_uri") or [""])[0]
                  state = (q.get("state") or [""])[0]
                  sep = "&" if "?" in rd else "?"
                  self._redirect(f"{rd}{sep}code=stub-code&state={urllib.parse.quote(state)}")
              elif parsed.path == "/userinfo":
                  with open(USERINFO_FILE) as fh:
                      self._json(json.load(fh))
              else:
                  self._json({"error": "not found"}, 404)

          def do_POST(self):
              self._json({"access_token": "stub-access-token", "token_type": "Bearer"})

      ThreadingHTTPServer(("0.0.0.0", 8901), Handler).serve_forever()
    '';

  userinfoOk = builtins.toJSON {
    sub = "usr_1";
    preferred_username = "lars";
    email = "lars@example.test";
    groups = [
      "pbx-recordings"
      "pbx-operator"
    ];
  };
in
{
  name = "telephony-native-oidc-recordings";

  nodes = {
    server =
      { pkgs, ... }:
      {
        imports = common.baseNode;

        # The client node drives the browser legs, including the IdP leg:
        # the stub IdP must be reachable cross-node (the module's strict
        # firewall would otherwise eat the /authorize hop).
        networking.firewall.allowedTCPPorts = [ 8901 ];

        services.telephony = {
          recording.serve = {
            enable = true;
            authMode = "oidc";
            oidc = {
              inherit issuer;
              clientSecretFile = "/etc/oidc-client-secret";
              sessionSecretFile = "/etc/oidc-session-secret";
            };
          };
          operator = {
            enable = true;
            authMode = "oidc";
            oidc = {
              inherit issuer;
              clientSecretFile = "/etc/oidc-client-secret";
              sessionSecretFile = "/etc/oidc-session-secret";
            };
          };
        };

        environment.etc = {
          "oidc-client-secret".text = "stub-client-secret";
          "oidc-session-secret".text = "stub-session-secret";
        };

        systemd.services.stub-idp = {
          description = "Stub OIDC IdP for VM tests";
          wantedBy = [ "multi-user.target" ];
          before = [ "telephony-recordings-view.service" ];
          environment = {
            STUB_ISSUER = issuer;
            STUB_USERINFO_FILE = "/var/lib/stub-idp/userinfo.json";
          };
          serviceConfig = {
            ExecStart = "${pkgs.python3}/bin/python3 ${stubIdp pkgs}";
            ExecStartPre = pkgs.writeShellScript "seed-userinfo" ''
              echo '${userinfoOk}' > /var/lib/stub-idp/userinfo.json
            '';
            DynamicUser = true;
            StateDirectory = "stub-idp";
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
    server.wait_for_unit("stub-idp.service")
    server.wait_for_unit("telephony-recordings-view.service")
    server.wait_for_unit("telephony-operator.service")
    client.wait_for_unit("multi-user.target")

    # Plant one recording the listing must surface after login.
    server.succeed(
      "mkdir -p /var/lib/telephony/recordings/2026"
      " && printf 'RIFF-vm-test' > /var/lib/telephony/recordings/2026/call-1.wav"
    )

    # One host for the WHOLE dance: cookies (state + session) must ride
    # the same host as the OIDC redirect URLs, which derive from the
    # telephony domain (pbx.test). /etc/hosts is read-only in the VM, so
    # curl resolves the domain per-request instead.
    ip = client.succeed("getent hosts server").split()[0]
    resolve = f"--resolve pbx.test:443:{ip}"
    base = "https://pbx.test"
    jar = "/tmp/jar.txt"

    def curl(*args):
        return client.succeed(" ".join(["curl -k -s", resolve] + list(args))).strip()

    def code(path):
        return curl("-o /dev/null -w '%{http_code}'", f"'{base}{path}'")

    with client.nested("wiring: healthz through nginx without auth"):
        assert code("/recordings/healthz") == "200", "healthz must proxy to the app"

    with client.nested("unauthenticated /recordings/ redirects into the dance"):
        assert code("/recordings/") == "302", code("/recordings/")
        loc = curl("-o /dev/null -w '%{redirect_url}'", f"'{base}/recordings/'")
        assert loc.endswith("/recordings/oidc/login"), loc

    with client.nested("login redirects to the IdP with PKCE + state"):
        client.execute(f"rm -f {jar}")
        headers = curl("-D - -o /dev/null -c /tmp/jar.txt", f"'{base}/recordings/oidc/login'")
        assert " 302" in headers.splitlines()[0], headers[:200]
        auth_line = [l for l in headers.splitlines() if l.lower().startswith("location:")][0]
        authorize = auth_line.split(" ", 1)[1].strip()
        assert authorize.startswith("${issuer}/authorize?"), authorize
        assert "code_challenge_method=S256" in authorize, authorize
        assert "state=" in authorize and "nonce=" in authorize, authorize

    with client.nested("stub IdP sends the code; callback mints the session"):
        # The IdP leg rides the same cookie jar (state cookie).
        step2 = curl("-D - -o /dev/null -b /tmp/jar.txt -c /tmp/jar.txt", f"'{authorize}'")
        cb_line = [l for l in step2.splitlines() if l.lower().startswith("location:")][0]
        callback = cb_line.split(" ", 1)[1].strip()
        assert "/recordings/oidc/callback?" in callback, callback
        step3 = curl("-D - -o /dev/null -b /tmp/jar.txt -c /tmp/jar.txt", f"'{callback}'")
        assert "302" in step3.splitlines()[0], step3[:200]
        home_line = [l for l in step3.splitlines() if l.lower().startswith("location:")][0]
        assert home_line.strip().endswith("/recordings/"), home_line

    with client.nested("the session unlocks listing and streaming"):
        listing = curl("-b /tmp/jar.txt", f"'{base}/recordings/'")
        assert "call-1.wav" in listing, listing[:300]
        stream = client.succeed(
            f"curl -k -s -b /tmp/jar.txt '{base}/recordings/file/2026/call-1.wav'"
        )
        assert stream == "RIFF-vm-test", stream[:60]

    with client.nested("an identity without the group fails closed"):
        server.execute("python3 -c 'import json; d=json.load(open(\"/var/lib/stub-idp/userinfo.json\")); d[\"groups\"]=[\"phone\"]; json.dump(d, open(\"/var/lib/stub-idp/userinfo.json\",\"w\"))'")
        server.succeed("cp /var/lib/stub-idp/userinfo.json /var/lib/stub-idp/userinfo-nogroup.json")
        try:
            client.execute(f"rm -f {jar}")
            headers = curl("-D - -o /dev/null -c /tmp/jar.txt", f"'{base}/recordings/oidc/login'")
            auth_line = [l for l in headers.splitlines() if l.lower().startswith("location:")][0]
            authorize = auth_line.split(" ", 1)[1].strip()
            step2 = curl("-D - -o /dev/null -b /tmp/jar.txt -c /tmp/jar.txt", f"'{authorize}'")
            cb_line = [l for l in step2.splitlines() if l.lower().startswith("location:")][0]
            callback = cb_line.split(" ", 1)[1].strip()
            body = curl("-b /tmp/jar.txt", f"'{callback}'")
            assert "sso_error=group" in body, body[:300]
        finally:
            server.execute("python3 -c 'import json; d=json.load(open(\"/var/lib/stub-idp/userinfo.json\")); d[\"groups\"]=[\"pbx-recordings\",\"pbx-operator\"]; json.dump(d, open(\"/var/lib/stub-idp/userinfo.json\",\"w\"))'")

    with server.nested("no htpasswd and no auth_request for the oidc surfaces"):
        server.fail("test -e /var/lib/telephony/recordings.htpasswd")
        conf = server.succeed("cat /etc/nginx/nginx.conf")
        assert "_telephony_auth_recordings" not in conf, "oidc mode must render no auth_request"
        assert "_telephony_auth_operator" not in conf, "oidc mode must render no auth_request"
        rec_block = conf.split("location /recordings/")[1].split("}")[0]
        assert "alias" not in rec_block, "oidc recordings must not alias the dir"
        op_block = conf.split("location /operator/")[1].split("}")[0]
        assert "alias" not in op_block, "oidc operator must not alias the webroot"

    with client.nested("operator surface: unauthenticated legs"):
        assert code("/operator/") == "302", code("/operator/")
        loc = curl("-o /dev/null -w '%{redirect_url}'", f"'{base}/operator/'")
        assert loc.endswith("/operator/oidc/login"), loc
        api_code = curl("-o /dev/null -w '%{http_code}'", f"'{base}/operator-api/health'")
        assert api_code == "401", f"api without session must 401, got {api_code}"

    with client.nested("operator surface: the dance unlocks UI and API"):
        client.execute(f"rm -f {jar}")
        headers = curl("-D - -o /dev/null -c /tmp/jar.txt", f"'{base}/operator/oidc/login'")
        auth_line = [l for l in headers.splitlines() if l.lower().startswith("location:")][0]
        authorize = auth_line.split(" ", 1)[1].strip()
        assert authorize.startswith("${issuer}/authorize?"), authorize
        step2 = curl("-D - -o /dev/null -b /tmp/jar.txt -c /tmp/jar.txt", f"'{authorize}'")
        cb_line = [l for l in step2.splitlines() if l.lower().startswith("location:")][0]
        callback = cb_line.split(" ", 1)[1].strip()
        assert "/operator/oidc/callback?" in callback, callback
        step3 = curl("-D - -o /dev/null -b /tmp/jar.txt -c /tmp/jar.txt", f"'{callback}'")
        assert "302" in step3.splitlines()[0], step3[:200]
        page = curl("-b /tmp/jar.txt", f"'{base}/operator/'")
        assert "operator" in page.lower() and "<" in page, page[:200]
        health = curl("-b /tmp/jar.txt", f"'{base}/operator-api/health'")
        assert '"ok"' in health or "profiles" in health, health[:200]
  '';
}
