# SSO-only identity resolution, end-to-end through the stack front
# (2026-11-21, webphone pareto T21): an oauth2-only deployment —
# passkey OFF, the shared users map carrying the email→extension
# mapping — must BOOT and resolve a login's identity ALL the way to
# the whoami surface. The app-level pin (webphone's
# TestSSOOnlySessionResolvesIdentity, ssoStub) proves the handler
# against a fake injected at the seam; this suite proves the SAME
# contract through the shapes that actually ship: the stack's typed
# oauth2 options, the nginx TLS front, a REAL discovery+authorize+
# token+JWKS IdP over https, and the FreeSWITCH directory verify the
# callback performs before minting.
#
# The suite's first run (2026-11-21 03:10) found the lane UNBOOTABLE:
# the app folds the shared auth.users map into its passkey shape,
# which switches passkey mode ON, and passkey mode refuses the boot
# without rp_id/rp_origins ("auth.passkey: rp_id is required when the
# passkey mode is configured") — which the module rendered only under
# passkey.enable. The module now derives the relying party from the
# stack domain whenever the identity layer is on (shared.nix
# webphoneIdentityOn); the rendered-config block below pins it.
#
# The stub IdP is a loopback https server on :8443 (443 belongs to
# nginx) whose leaf the guest trust store adopts, so webphone's Go
# client verifies it with the system pool — no app-side knobs. It
# mints RS256 ID tokens with a key it publishes at jwks_uri: webphone
# verifies signature+issuer+audience+expiry+nonce (the nonce is
# stashed per authorization code and replayed into the token), reads
# the email claim, and resolves the mapping.
#
# The dance is driven with curl exactly like a browser session:
#   begin (302 → discovered authorize, attempt cookies set)
#   → stub authorize (302 → callback?code&state)
#   → callback (303 → /, session cookie minted)
#   → GET /api/session resolves extension 1000 / "Lars" / lines[]
#   → an anonymous probe stays 401 (the mint is the only door)
{
  telephonyModule,
  webphonePackage,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  issuer = "https://idp.pbx.test:8443";

  idpCert =
    pkgs:
    pkgs.runCommand "sso-idp-cert" { } ''
      mkdir $out
      ${pkgs.openssl}/bin/openssl req -x509 -newkey rsa:2048 -nodes \
        -keyout $out/key.pem -out $out/cert.pem -days 3 \
        -subj "/CN=idp.pbx.test" \
        -addext "subjectAltName=DNS:idp.pbx.test"
    '';

  idpStub =
    pkgs:
    pkgs.writeText "sso-idp-stub.py" ''
      import base64
      import json
      import ssl
      import time
      import urllib.parse
      from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

      from cryptography.hazmat.primitives import hashes
      from cryptography.hazmat.primitives.asymmetric import padding, rsa

      KID = "vm-sso-kid"
      ISSUER = "${issuer}"
      CLIENT_ID = "webphone"
      EMAIL = "lars@pbx.test"

      KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
      ATTEMPTS = {}

      def b64url(raw):
          return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

      def jwks():
          pub = KEY.public_key().public_numbers()
          n_bytes = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")
          e_bytes = pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")
          return {
              "keys": [
                  {
                      "kty": "RSA",
                      "kid": KID,
                      "use": "sig",
                      "alg": "RS256",
                      "n": b64url(n_bytes),
                      "e": b64url(e_bytes),
                  }
              ]
          }

      def mint_id_token(nonce):
          now = int(time.time())
          header = {"alg": "RS256", "kid": KID, "typ": "JWT"}
          payload = {
              "iss": ISSUER,
              "aud": CLIENT_ID,
              "sub": "usr-sso-vm-1",
              "iat": now,
              "exp": now + 600,
              "nonce": nonce,
              "email": EMAIL,
              "email_verified": True,
              "preferred_username": "lars",
              "groups": ["phone"],
          }
          head = b64url(json.dumps(header, separators=(",", ":")).encode())
          body = b64url(json.dumps(payload, separators=(",", ":")).encode())
          signing_input = head + "." + body
          sig = KEY.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
          return signing_input + "." + b64url(sig)

      DISCOVERY = json.dumps(
          {
              "issuer": ISSUER,
              "authorization_endpoint": ISSUER + "/authorize",
              "token_endpoint": ISSUER + "/token",
              "userinfo_endpoint": ISSUER + "/userinfo",
              "jwks_uri": ISSUER + "/jwks.json",
              "response_types_supported": ["code"],
              "subject_types_supported": ["public"],
              "id_token_signing_alg_values_supported": ["RS256"],
              "scopes_supported": ["openid", "email", "profile"],
          }
      ).encode()

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

          def do_GET(self):
              parsed = urllib.parse.urlsplit(self.path)
              query = urllib.parse.parse_qs(parsed.query)
              if parsed.path == "/.well-known/openid-configuration":
                  self._json(json.loads(DISCOVERY))
              elif parsed.path == "/jwks.json":
                  self._json(jwks())
              elif parsed.path == "/authorize":
                  code = "vm-code-" + str(len(ATTEMPTS) + 1)
                  ATTEMPTS[code] = query.get("nonce", [""])[0]
                  redirect = query.get("redirect_uri", [""])[0]
                  if not redirect:
                      self.send_response(400)
                      self.end_headers()
                      return
                  sep = "&" if "?" in redirect else "?"
                  self.send_response(302)
                  self.send_header(
                      "Location",
                      redirect + sep + "code=" + code + "&state=" + query.get("state", [""])[0],
                  )
                  self.end_headers()
              else:
                  self.send_response(404)
                  self.end_headers()

          def do_POST(self):
              parsed = urllib.parse.urlsplit(self.path)
              if parsed.path == "/token":
                  length = int(self.headers.get("Content-Length", "0"))
                  form = urllib.parse.parse_qs(self.rfile.read(length).decode())
                  code = form.get("code", [""])[0]
                  nonce = ATTEMPTS.pop(code, "")
                  self._json(
                      {
                          "access_token": "vm-access-token",
                          "token_type": "Bearer",
                          "expires_in": 3600,
                          "id_token": mint_id_token(nonce),
                      }
                  )
              else:
                  self.send_response(404)
                  self.end_headers()

      server = ThreadingHTTPServer(("127.0.0.1", 8443), Handler)
      context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
      context.load_cert_chain("/etc/sso-idp/cert.pem", "/etc/sso-idp/key.pem")
      server.socket = context.wrap_socket(server.socket, server_side=True)
      server.serve_forever()
    '';
in
{
  name = "telephony-webphone-sso-only";

  nodes.machine =
    { pkgs, ... }:
    let
      cert = idpCert pkgs;
      idpPython = pkgs.python3.withPackages (ps: [ ps.cryptography ]);
    in
    {
      imports = common.baseNode;

      networking.extraHosts = "127.0.0.1 pbx.test idp.pbx.test";
      virtualisation.memorySize = 2048;

      # The stub IdP is a boot-started unit. A bare `nohup` of the
      # shebang-less script died silently and cost a full 15-minute
      # port wait to notice; a failed start now fails the suite on the
      # unit itself, with its journal in the driver log.
      systemd.services.sso-idp-stub = {
        description = "Loopback stub OIDC provider (telephony-webphone-sso-only)";
        after = [ "network.target" ];
        wantedBy = [ "multi-user.target" ];
        serviceConfig.ExecStart = "${idpPython}/bin/python3 /etc/sso-idp/stub.py";
      };

      # The SSO-only shape: oauth2 on, passkey absent, the shared
      # users map carrying the mapping both passwordless modes read.
      services.telephony.webphone.oauth2 = {
        enable = true;
        inherit issuer;
        clientSecretFile = "/etc/telephony/oidc-client-secret";
      };
      services.telephony.webphone.users."lars@pbx.test" = {
        extensions = [ "1000" ];
        displayName = "Lars";
      };
      # The SSO finish reads the SIP directory password from the
      # password FILE and directory-verifies it before minting — the
      # content must match the fixture's real extension password.
      services.telephony.webphone.extensionPasswordFiles."1000" = "/etc/telephony/sso-ext-1000";

      security.pki.certificateFiles = [ "${cert}/cert.pem" ];

      environment.etc = {
        "telephony/oidc-client-secret" = {
          text = "oidc-vm-sso-secret";
          mode = "0600";
        };
        "telephony/sso-ext-1000" = {
          text = "test-1000-x9y8z7";
          user = "webphone";
          mode = "0600";
        };
        "sso-idp/cert.pem" = {
          source = "${cert}/cert.pem";
          mode = "0644";
        };
        "sso-idp/key.pem" = {
          source = "${cert}/key.pem";
          mode = "0600";
        };
        "sso-idp/stub.py" = {
          source = idpStub pkgs;
          mode = "0755";
        };
      };

      environment.systemPackages = [
        idpPython
        pkgs.curl
      ];
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f")
    machine.wait_for_unit("webphone.service")
    machine.wait_for_unit("nginx.service")
    machine.wait_for_open_port(443)
    machine.wait_until_succeeds(
        "curl -k -s -o /dev/null -w '%{http_code}' https://pbx.test/healthz | grep -q 200",
        timeout=datetime.timedelta(seconds=60),
    )

    with machine.nested("SSO-only shape boots with the derived relying party"):
        # The module derives auth.passkey.{rp_id,rp_origins} from the
        # stack domain whenever the identity layer is on — without them
        # the app refuses the boot (its loader folds the shared users
        # map into the passkey shape). Nothing else rides under
        # passkey here: users + password files are the shared auth.*
        # keys the oauth2 lane reads.
        cfg_path = machine.execute(
            "tr '\\0' '\\n' < /proc/$(systemctl show -p MainPID --value webphone)/environ"
            " | sed -n 's/^WEBPHONE_CONFIG=//p'"
        )[1].strip()
        assert cfg_path.startswith("/nix/store/"), f"WEBPHONE_CONFIG not found: {cfg_path!r}"
        import json

        rendered = json.loads(machine.succeed(f"cat {cfg_path}"))
        auth = rendered["auth"]
        assert auth["passkey"] == {
            "rp_id": "pbx.test",
            "rp_origins": [ "https://pbx.test" ],
        }, auth.get("passkey")
        assert auth["users"]["lars@pbx.test"]["extensions"] == [ "1000" ], auth.get("users")
        assert auth["oauth2"]["issuer"] == "${issuer}", auth.get("oauth2")

        # The front door offers the SSO door (the identity layer's
        # passkey ceremony renders beside it: the app wires both login
        # lanes from the one layer the shared map arms).
        login = machine.succeed("curl -k -s https://pbx.test/login")
        assert 'id="sso-login"' in login, "the login page does not offer the SSO door"

    # The stub IdP is a boot-started unit: discovery is begin-eager,
    # so the issuer must already answer before the first begin. The
    # explicit address + timeout turn a dead helper into a one-minute
    # failure instead of a silent 15-minute one.
    machine.wait_for_unit("sso-idp-stub.service")
    machine.wait_for_open_port(8443, "127.0.0.1", timeout=60)

    with machine.nested("SSO-only dance: begin → authorize → callback → whoami"):
        # curl's %{redirect_url} write-out stays EMPTY on curl 8.x (the
        # 302 carries its Location header; the variable is not filled
        # without a followed redirect), so both hops read the header
        # from a dump. The second sed strips the trailing CR.
        begin_location = machine.succeed(
            "curl -k -s -o /dev/null -D /tmp/begin.hdr -c /tmp/sso-jar"
            " 'https://pbx.test/api/auth/oauth2/begin'"
            " && sed -n 's/^[Ll]ocation: //p' /tmp/begin.hdr | sed 's/[^[:print:]].*//'"
        ).strip()
        assert begin_location.startswith("${issuer}/authorize"), (
            "begin did not redirect to the discovered issuer endpoint: " + begin_location
        )
        assert "code_challenge_method=S256" in begin_location, (
            "begin lost the PKCE method: " + begin_location
        )
        assert "nonce=" in begin_location, "begin lost the nonce: " + begin_location

        callback_url = machine.succeed(
            "curl -k -s -o /dev/null -D /tmp/authorize.hdr '" + begin_location + "'"
            " && sed -n 's/^[Ll]ocation: //p' /tmp/authorize.hdr | sed 's/[^[:print:]].*//'"
        ).strip()
        assert callback_url.startswith("https://pbx.test/api/auth/oauth2/callback?code="), (
            "the stub IdP did not redirect back to the registered callback: " + callback_url
        )

        callback_status = machine.succeed(
            "curl -k -s -o /dev/null -w '%{http_code}' -b /tmp/sso-jar -c /tmp/sso-jar"
            " '" + callback_url + "'"
        ).strip()
        assert callback_status == "303", (
            "callback answered " + callback_status + ", want 303 to the shell"
        )

        identity = machine.succeed(
            "curl -k -s -b /tmp/sso-jar 'https://pbx.test/api/session'"
        )
        assert '"extension":"1000"' in identity, "whoami did not resolve the mapped extension: " + identity
        assert '"display_name":"Lars"' in identity, "whoami did not resolve the mapped display name: " + identity
        assert '"lines"' in identity, "the typed lines wire is absent from the session identity: " + identity
        print("SSO-ONLY-IDENTITY-RESOLVED: " + identity.strip())

        anonymous = machine.succeed(
            "curl -k -s -o /dev/null -w '%{http_code}' 'https://pbx.test/api/session'"
        ).strip()
        assert anonymous == "401", (
            "an anonymous session probe answered " + anonymous + ", want 401"
        )
  '';
}
