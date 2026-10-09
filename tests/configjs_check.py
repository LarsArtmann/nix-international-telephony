#!/usr/bin/env python3
"""Assert the webphone /config.js wire contract (shared test fixture).

Reads the config.js BODY on stdin — the caller strips the JS wrapper
(`sed -e 's/^ *window.PBX_CONFIG = //' -e 's/;[[:space:]]*$//') — and
checks the cross-repo contract with the webphone app's render
(internal/server/configjs.go):

  * strict JSON with the exact key set (a new key is a contract change:
    update the island readers, this fixture and upstream's
    internal/server/configjs_test.go together)
  * phoneApi/crm are booleans mirroring the stack options
  * contacts keys are LOWERCASE name/number on the wire — the island's
    readers and the UI's personal-contact round-trip depend on them;
    the 2026-09-24 capitalized-keys breakage crossed exactly this seam
  * TURN REST pairs are derived per response: username is the bare unix
    expiry (digits), credential base64(HMAC-SHA1(secret, username)) —
    re-verified when --turn-rest-secret is given

The producer side of the same contract is asserted upstream in the
webphone repo (internal/server/configjs_test.go); this fixture plus
tests/webphone.nix and tests/browser-e2e.py assert the consumer side.

Exit status: 0 = contract holds, 1 = violation (assertion text on
stderr). Stdlib only — runs inside the VM test image.
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sip-domain", required=True)
    parser.add_argument(
        "--turn-rest-secret",
        default=None,
        help="fixture secret; when given, TURN credentials are re-derived "
        "and compared byte-for-byte",
    )
    parser.add_argument(
        "--phone-api",
        action="store_true",
        help="expect phoneApi true (default: false)",
    )
    parser.add_argument(
        "--crm",
        action="store_true",
        help="expect crm true (default: false)",
    )
    parser.add_argument(
        "--contact",
        action="append",
        default=[],
        metavar="NAME=NUMBER",
        help="expected contacts in order (repeatable)",
    )
    args = parser.parse_args()

    config = json.load(sys.stdin)
    # asr joined the wire contract upstream in the webphone repo
    # (surfaced 2026-10-09: this consumer check had not RUN on main for
    # days — the pre-commit gate was red above it — so the float moved
    # past the expected key set first). The module does not wire asr
    # yet, so the key is type-checked only, not value-pinned.
    assert set(config) == {
        "sipDomain",
        "websocketPath",
        "iceServers",
        "phoneApi",
        "crm",
        "asr",
        "contacts",
    }, config
    assert isinstance(config["asr"], bool), config
    assert config["sipDomain"] == args.sip_domain, config
    assert config["websocketPath"] == "/sip", config
    assert isinstance(config["phoneApi"], bool), config
    assert config["phoneApi"] == args.phone_api, config
    assert isinstance(config["crm"], bool), config
    assert config["crm"] == args.crm, config

    contacts = config["contacts"]
    assert all(set(c) == {"name", "number"} for c in contacts), (
        f"contact keys must be lowercase name/number on the wire: {contacts}"
    )
    expected = [tuple(c.split("=", 1)) for c in args.contact]
    assert [(c["name"], c["number"]) for c in contacts] == expected, contacts

    turn = [
        s for s in config["iceServers"] if any(u.startswith("turn:") for u in s["urls"])
    ]
    assert turn, config
    username = turn[0]["username"]
    assert username.isdigit() and int(username) > time.time(), config
    if args.turn_rest_secret is not None:
        mac = hmac.new(
            args.turn_rest_secret.encode(), username.encode(), hashlib.sha1
        ).digest()
        expected_cred = base64.b64encode(mac).decode()
        assert turn[0]["credential"] == expected_cred, config


if __name__ == "__main__":
    main()
