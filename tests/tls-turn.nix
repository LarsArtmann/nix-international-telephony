# NixOS VM test for TLS and ICE infrastructure:
#   * the self-signed cert bootstrap (telephony-tls oneshot) provisions
#     cert.pem/key.pem before sofia starts
#   * SIP-over-TLS (5061) completes a real TLS handshake (not just a
#     listener) and the external profile (5080, TCP + UDP) listens
#   * the event socket (8021) stays loopback-only
#   * coturn listens for STUN/TURN
#   * the runtime-rendered config.js exists and its TURN credentials equal
#     the coturn REST derivation (HMAC-SHA1 over "<expiry>:webphone" with
#     the configured secret)
#   * STUN answers, a REST credential allocates a relay, a wrong secret 401s
#   * manual tls.mode: the HTTPS vhost presents the operator-provided
#     certificate pair (validated by trusting exactly that certificate)
{
  telephonyModule,
  webphonePackage,
  pkgs,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };

  # Manual-TLS fixture: a throwaway certificate with a distinctive CN.
  # The manual-mode node serves it and the suite validates the HTTPS
  # vhost against it — proof nginx presents the operator's pair. The
  # store-baked key is fine here by construction (generated test data,
  # never a real secret).
  manualCert = pkgs.runCommand "telephony-manual-test-cert" { } ''
    mkdir -p $out
    ${pkgs.openssl}/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
      -keyout $out/key.pem -out $out/cert.pem \
      -subj "/CN=manual-tls.test" \
      -addext "subjectAltName=DNS:manual-tls.test"
  '';
in
{
  name = "telephony-tls-turn";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;
    };

  nodes.manual =
    { ... }:
    {
      imports = common.baseNode;
      environment.etc."telephony-manual-cert".source = manualCert;
      services.telephony.tls = {
        mode = "manual";
        certificate = "${manualCert}/cert.pem";
        key = "${manualCert}/key.pem";
      };
    };

  testScript = ''
    ${common.bootWait}

    # NOTE: no start_all() — machines start lazily at their first command
    # (staggered sofia startup; see tests/dialplan.nix).
    wait_for_freeswitch(machine, "test-es-4d5e6f")

    # Cert bootstrap: the telephony-tls oneshot has rendered the
    # self-signed pair (completed oneshots are asserted by artifact).
    machine.succeed("test -s /var/lib/telephony/tls/cert.pem")
    machine.succeed("test -s /var/lib/telephony/tls/key.pem")
    cert = machine.succeed("head -n 1 /var/lib/telephony/tls/cert.pem")
    assert "BEGIN CERTIFICATE" in cert, cert

    # --- SIP-over-TLS (5061) and the external profile (5080) listen ---
    machine.wait_until_succeeds("ss -ltn | grep ':5061'")
    machine.wait_until_succeeds("ss -ltn | grep ':5080'")
    machine.wait_until_succeeds("ss -lun | grep ':5080'")

    # --- 5061 speaks real TLS, not just a listener: a full handshake
    # completes and the server presents a certificate ---
    tls_ip = sip_server(machine)
    handshake = machine.succeed(
        "echo | openssl s_client -connect " + tls_ip + ":5061 2>/dev/null"
    )
    assert "BEGIN CERTIFICATE" in handshake, handshake[:400]
    assert "Cipher is" in handshake, handshake[:400]

    # --- Event socket (8021) stays loopback-only: every listener on the
    # port must be 127.0.0.1 — a regression here would expose fs_cli ---
    es_listeners = machine.succeed("ss -ltn 'sport = :8021' | grep -v State")
    assert es_listeners.strip(), "no 8021 listener at all"
    for listener in es_listeners.splitlines():
        assert "127.0.0.1:8021" in listener, listener

    machine.wait_for_unit("coturn.service")
    machine.wait_for_open_port(3478)

    # --- TURN: STUN answers, REST credentials allocate, wrong secret 401 ---
    machine.succeed("test -s /var/lib/telephony/config.js")
    turnpy = "python3 /etc/turn.py"
    machine.succeed(f"{turnpy} stun --server 127.0.0.1")
    turn_username, turn_credential = machine.succeed(
        "curl -k -f https://localhost/config.js"
        " | sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//'"
        " | python3 -c 'import json,sys; c=json.load(sys.stdin);"
        " t=[s for s in c[\"iceServers\"] if any(u.startswith(\"turn:\") for u in s[\"urls\"])][0];"
        " print(t[\"username\"], t[\"credential\"])'"
    ).split()
    # The served credential must equal the coturn REST derivation
    # (HMAC-SHA1 over "<expiry>:webphone" with the configured secret).
    machine.succeed(
        "curl -k -f https://localhost/config.js"
        " | sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//'"
        " | python3 -c 'import base64,hashlib,hmac,json,sys;"
        " c=json.load(sys.stdin);"
        " t=[s for s in c[\"iceServers\"] if any(u.startswith(\"turn:\") for u in s[\"urls\"])][0];"
        " u=t[\"username\"].encode();"
        " e=base64.b64encode(hmac.new(b\"test-turn-rest-4d5e6f\", u, hashlib.sha1).digest()).decode();"
        " assert e == t[\"credential\"], (e, t[\"credential\"])'"
    )
    machine.succeed(
        f"{turnpy} allocate --server 127.0.0.1"
        f" --username '{turn_username}' --password '{turn_credential}'"
    )
    machine.succeed(
        f"{turnpy} allocate --server 127.0.0.1"
        " --username '9999999999:evil' --password 'wrong' --expect-401"
    )

    # --- Manual TLS mode (node `manual`): the HTTPS vhost presents the
    # operator-provided certificate pair. Trusting exactly the fixture
    # certificate (CA = the cert itself, SNI/SAN match) validates the
    # full server-side path: any other cert (self-signed bootstrap,
    # stale pair) fails the handshake. ---
    manual.wait_for_unit("nginx.service")
    manual.wait_for_open_port(443)
    manual.succeed(
        "curl --cacert /etc/telephony-manual-cert/cert.pem"
        " --resolve manual-tls.test:443:127.0.0.1"
        " -f https://manual-tls.test/"
    )
  '';
}
