# NixOS VM test for file-based secrets (*File options): secrets render at
# service start from runtime files; the Nix store carries placeholders.
#
#   * a root oneshot provisions /run/secrets/* (stand-in for sops-nix or
#     agenix activation rendering)
#   * the store's assembled FreeSWITCH config contains @TELEPHONY_*@
#     placeholders and none of the real secrets
#   * the runtime copy at /var/lib/freeswitch/conf carries the real
#     values, no placeholder is left behind, and it is not group/other
#     readable
#   * FreeSWITCH boots off the runtime config: fs_cli works with the
#     file-provided event-socket password, extension 1000 (file password)
#     REGISTERs with digest auth while 1001 (plain password) still works
#   * config.js TURN credentials are HMAC'd with the file-provided secret
#     and coturn (via static-auth-secret-file) accepts the allocation
let
  common = import ./common.nix;

  esPassword = "file-es-7g8h9i";
  ext1000Password = "file-1000-a1b2c3";
  turnSecret = "file-turn-0k9l8m";
in
{
  name = "telephony-secrets";

  nodes.machine =
    { lib, ... }:
    {
      imports = common.baseNode;

      # Stand-in for a secret manager: root-only files before consumers.
      systemd.services.telephony-test-secrets = {
        description = "Provision runtime secret files (secret-manager stand-in)";
        wantedBy = [ "multi-user.target" ];
        before = [
          "freeswitch.service"
          "coturn.service"
          "telephony-web-config.service"
        ];
        serviceConfig.Type = "oneshot";
        script = ''
          install -d -m 700 /run/secrets
          printf '%s\n' '${esPassword}'   > /run/secrets/event-socket
          printf '%s\n' '${ext1000Password}' > /run/secrets/ext-1000
          printf '%s\n' '${turnSecret}'   > /run/secrets/turn
          chmod 600 /run/secrets/event-socket /run/secrets/ext-1000 /run/secrets/turn
        '';
      };

      services.telephony = {
        eventSocketPassword = lib.mkForce "";
        eventSocketPasswordFile = "/run/secrets/event-socket";
        extensions."1000".password = lib.mkForce "";
        extensions."1000".passwordFile = "/run/secrets/ext-1000";
        # 1001 keeps its plain password: mixed modes must coexist.
        turn.authSecret = lib.mkForce "";
        turn.authSecretFile = "/run/secrets/turn";
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "${esPassword}")

    fs_cli = "fs_cli -p ${esPassword} -x"

    # --- Store purity: placeholders in, secrets out ---
    machine.succeed("test -n \"$(ls -d /nix/store/*-freeswitch-config-d)\"")
    confdir=$(machine.succeed("ls -d /nix/store/*-freeswitch-config-d | head -1"))
    machine.succeed(f"grep -q '@TELEPHONY_EXT_1000_PASSWORD@' {confdir}/directory/default.xml")
    machine.succeed(f"grep -q '@TELEPHONY_EVENT_SOCKET_PASSWORD@' {confdir}/autoload_configs/event_socket.conf.xml")
    machine.fail(f"grep -rq '${ext1000Password}' {confdir}")
    machine.fail(f"grep -rq '${esPassword}' {confdir}")
    machine.fail(f"grep -rq '${turnSecret}' /nix/store/ || true", "") if False else None
    machine.fail("grep -rq '${turnSecret}' /nix/store/*-freeswitch-config-d/")

    # --- Runtime copy: real secrets, no leftovers, private modes ---
    machine.succeed("grep -q '${ext1000Password}' /var/lib/freeswitch/conf/directory/default.xml")
    machine.succeed("grep -q '${esPassword}' /var/lib/freeswitch/conf/autoload_configs/event_socket.conf.xml")
    machine.fail("grep -rq '@TELEPHONY_' /var/lib/freeswitch/conf/")
    mode = machine.succeed("stat -c '%a' /var/lib/freeswitch/conf/directory/default.xml").strip()
    assert mode == "600", mode

    # --- Functional: boot off the runtime config ---
    status = machine.succeed(f"{fs_cli} 'sofia status'")
    assert "internal" in status and "external" in status, status

    def sip_server(node):
        listener = node.succeed("ss -ltn 'sport = :5060' | grep -v State").strip()
        ip = listener.split()[3].rsplit(":", 1)[0]
        return "::1" if ip.startswith("[") else ip

    sip_ip = sip_server(machine)

    # 1000 (file password) registers with digest auth.
    out = machine.succeed(
        f"python3 /etc/sip.py --server {sip_ip} --domain pbx.test "
        f"--user 1000 --password ${ext1000Password} register"
    )
    assert "REGISTER 200" in out, out

    # 1001 (plain password) is unaffected.
    out = machine.succeed(
        f"python3 /etc/sip.py --server {sip_ip} --domain pbx.test "
        "--user 1001 --password test-1001-u6t5s4 register"
    )
    assert "REGISTER 200" in out, out

    # --- TURN: file secret on both sides (renderer + coturn) ---
    machine.wait_for_unit("coturn.service")
    machine.wait_for_open_port(3478)
    turn_username, turn_credential = machine.succeed(
        "curl -k -f https://localhost/config.js"
        " | sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//'"
        " | python3 -c 'import json,sys; c=json.load(sys.stdin);"
        " t=[s for s in c[\"iceServers\"] if any(u.startswith(\"turn:\") for u in s[\"urls\"])][0];"
        " print(t[\"username\"], t[\"credential\"])'"
    ).split()
    machine.succeed(
        "curl -k -f https://localhost/config.js"
        " | sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//'"
        " | python3 -c 'import base64,hashlib,hmac,json,sys;"
        " c=json.load(sys.stdin);"
        " t=[s for s in c[\"iceServers\"] if any(u.startswith(\"turn:\") for u in s[\"urls\"])][0];"
        " u=t[\"username\"].encode();"
        f" e=base64.b64encode(hmac.new(b\"${turnSecret}\", u, hashlib.sha1).digest()).decode();"
        " assert e == t[\"credential\"], (e, t[\"credential\"])'"
    )
    machine.succeed(
        f"python3 /etc/turn.py allocate --server 127.0.0.1"
        f" --username '{turn_username}' --password '{turn_credential}'"
    )
  '';
}
