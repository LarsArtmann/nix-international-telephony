# NixOS VM test for TLS and ICE infrastructure:
#   * the self-signed cert bootstrap (telephony-tls oneshot) provisions
#     cert.pem/key.pem before sofia starts
#   * SIP-over-TLS (5061) and the external profile (5080, TCP + UDP) listen
#   * coturn listens for STUN/TURN
#   * the runtime-rendered config.js exists and its TURN credentials equal
#     the coturn REST derivation (HMAC-SHA1 over "<expiry>:webphone" with
#     the configured secret)
#   * STUN answers, a REST credential allocates a relay, a wrong secret 401s
let
  common = import ./common.nix;
in
{
  name = "telephony-tls-turn";

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;
    };

  testScript = ''
    ${common.bootWait}

    # NOTE: no start_all() — machines start lazily at their first command
    # (staggering sofia's heavy startup phase; see tests/dialplan.nix).
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
  '';
}
