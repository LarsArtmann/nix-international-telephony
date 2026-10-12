# NixOS VM test for the dynamic SIP directory (credential brokering):
#   * directory.mode = "xml_curl" boots the fs-directory bridge and
#     FreeSWITCH loads mod_xml_curl with the Bearer binding (the same
#     derivation secret webphone runs under — the module wires
#     services.webphone.settings.sip.credential_secret_file from
#     bridge.secretFile)
#   * a webphone login mints a session whose DERIVED credential
#     REGISTERs against FreeSWITCH (the full seam: island-equivalent
#     login → internal directory endpoint → bridge → sofia digest check)
#   * a wrong credential is denied; after logout the SAME credential is
#     denied at the next REGISTER (revocation is inherent)
#   * a static-fallback extension still registers with its file password
#     while xml_curl mode is on (the operator's lifeline)
#
# Rollback drill (mode back to static): covered at eval level — the
# golden rule is that mode=static renders byte-identical config (all
# new rendering is gated on xml_curl), so the rollback is a config flip
# plus a rebuild; this suite proves the xml_curl side end to end.
{
  telephonyModule,
  webphonePackage,
  kvm ? true,
  slowBoot ? false,
}:
let
  common = import ./common.nix { inherit telephonyModule webphonePackage; };
  bootTimeouts = if slowBoot then ", port_timeout=900, unit_timeout=900" else "";
in
{
  name =
    if kvm then "telephony-webphone-dynamic-directory" else "telephony-webphone-dynamic-directory-tcg";

  requiredFeatures.kvm = kvm;

  nodes.machine =
    { ... }:
    {
      imports = common.baseNode;
      environment.etc."wsprobe.py".source = ./wsprobe.py;
      # The derivation secret: ONE file on both sides of the seam (the
      # module default-wires it into webphone's credential_secret_file).
      environment.etc."telephony/webphone-directory-secret" = {
        text = "dynamic-directory-secret-4d5e6f\n";
        user = "webphone";
        mode = "0600";
      };
      services.telephony.directory = {
        mode = "xml_curl";
        bridge = {
          webphoneUrl = "http://127.0.0.1:8080";
          secretFile = "/etc/telephony/webphone-directory-secret";
        };
        # 1001 keeps its static entry (the operator lifeline); 1000
        # exists only as live webphone sessions.
        staticFallbackExtensions = [ "1001" ];
      };
    };

  testScript = ''
    ${common.bootWait}

    wait_for_freeswitch(machine, "test-es-4d5e6f"${bootTimeouts})
    machine.wait_for_unit("webphone.service")
    machine.wait_for_open_port(8080)
    machine.wait_for_unit("fs-directory.service")
    machine.wait_for_open_port(8071)

    # The bridge answers the health probe; FreeSWITCH's generated config
    # carries the xml_curl binding (module loaded, spliced secret).
    machine.succeed("curl -sf http://127.0.0.1:8071/health | grep -q ok")
    machine.succeed(
        "grep -q 'mod_xml_curl' /var/lib/freeswitch/conf/autoload_configs/modules.conf.xml"
    )
    machine.succeed(
        "grep -q 'gateway-url' /var/lib/freeswitch/conf/autoload_configs/xml_curl.conf.xml"
    )
    machine.succeed(
        "! grep -q '@TELEPHONY_DIRECTORY_SECRET@' /var/lib/freeswitch/conf/autoload_configs/xml_curl.conf.xml"
    )
    # The static directory is SCOPED: 1000 must NOT be in it (only a
    # live webphone session may register), 1001 must be (the fallback).
    machine.succeed("! grep -q 'id=\"1000\"' /var/lib/freeswitch/conf/directory/default.xml")
    machine.succeed("grep -q 'id=\"1001\"' /var/lib/freeswitch/conf/directory/default.xml")

    # Webphone-side login: CSRF dance (cookie jar + masked token), then
    # the 201 answer carries the derived REGISTER credential. The phone
    # API is off in this fixture (no directory verification — the same
    # loopback-dev trust model), so any password mints the session; the
    # DERIVED credential is what FreeSWITCH will accept.
    import json
    import re

    machine.succeed("curl -sf -c /tmp/jar http://127.0.0.1:8080/api/csrf > /tmp/csrf.json")
    csrf_match = re.search(r'"token":"([^"]+)"', machine.succeed("cat /tmp/csrf.json"))
    assert csrf_match is not None, "csrf answer must carry a token"
    csrf = csrf_match.group(1)
    login = machine.succeed(
        "curl -sf -b /tmp/jar -c /tmp/jar -H 'X-CSRF-Token: "
        + csrf
        + "' -H 'Content-Type: application/json' -d '{\"extension\":\"1000\",\"password\":\"typed-pw\"}'"
        " http://127.0.0.1:8080/api/session"
    )
    credential = json.loads(login).get("sip_credential")
    assert credential, f"login answer must carry sip_credential: {login!r}"
    assert "password" not in json.loads(login), "legacy wire must stay silent under brokering"

    # Login ROTATES the CSRF pair (session-api contract) — re-adopt the
    # fresh token the island itself fetches after login, or every later
    # POST/DELETE 403s.
    csrf = json.loads(
        machine.succeed(
            "curl -sf -b /tmp/jar -c /tmp/jar http://127.0.0.1:8080/api/csrf"
        )
    )["token"]

    # The internal directory endpoint holds it (Bearer = the same secret).
    directory = machine.succeed(
        "curl -sf -H 'Authorization: Bearer dynamic-directory-secret-4d5e6f'"
        " http://127.0.0.1:8080/internal/directory/1000"
    )
    assert credential in directory, f"directory endpoint must list the derived credential: {directory!r}"

    # F46: the derived credential REGISTERs (the seam end to end).
    machine.succeed(
        f"python3 /etc/wsprobe.py --auth-register 1000 '{credential}' ok direct"
    )
    # F47 negative: a wrong credential is denied.
    machine.fail(
        "python3 /etc/wsprobe.py --auth-register 1000 'wrong-password' ok direct"
    )

    # F47 revocation: logout kills the session; the SAME credential is
    # denied at the next REGISTER (the directory endpoint no longer
    # lists it, sofia's digest check fails).
    machine.succeed(
        "curl -sf -b /tmp/jar -H 'X-CSRF-Token: "
        + csrf
        + "' -X DELETE http://127.0.0.1:8080/api/session"
    )
    # Revocation must be VISIBLE at the seam first: no live session, no
    # credential. If this holds but the register below still succeeds,
    # the hole is sofia-side (blind accept / cache), never webphone's.
    post_logout_directory = machine.succeed(
        "curl -sf -H 'Authorization: Bearer dynamic-directory-secret-4d5e6f'"
        " http://127.0.0.1:8080/internal/directory/1000"
    )
    post = json.loads(post_logout_directory)
    assert post.get("credentials") == [], (
        f"post-logout directory must answer an empty list: {post_logout_directory!r}"
    )
    # The blind-registration guard must actually be rendered (an unknown
    # user is a DENIAL under xml_curl, never sofia's permissive default).
    machine.succeed(
        "grep -q 'accept-blind-reg\" value=\"false\"'"
        " /var/lib/freeswitch/conf/sip_profiles/internal.xml"
    )
    machine.fail(
        f"python3 /etc/wsprobe.py --auth-register 1000 '{credential}' ok direct"
    )

    # F48 static fallback: 1001 keeps its file password and registers
    # while xml_curl mode is on.
    machine.succeed(
        "python3 /etc/wsprobe.py --auth-register 1001 'test-1001-u6t5s4' ok direct"
    )
  '';
}
