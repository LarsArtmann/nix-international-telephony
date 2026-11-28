#!/usr/bin/env python3
"""Sign and send one Telnyx webhook the way Telnyx does (tests/messaging-signature.nix).

    sign_webhook.py <bridge module> <seed hex> <url> [<Header: value> ...]

Prints "STATUS <http status>" as its last line. SIGN_WEBHOOK_TAMPER=1
signs the body and then changes one byte of it: the signed text is no
longer what goes on the wire.

The curve arithmetic is loaded from the bridge module under test
(tests/test_telnyx_bridge.py pins it to the RFC 8032 vectors); the point
ENCODER here is the tests' independent one, so a signature never depends
on the bridge's decoder. The body is a log-only message.sent event: this
suite asserts the signature gate, not the webphone forward
(tests/messaging.nix owns that one).
"""

import base64
import hashlib
import importlib.util
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request


def encode_point(point, prime):
    """The 32-byte little-endian Edwards encoding: y, plus the low bit of x."""
    x, y, z, _ = point
    z_inverse = pow(z, prime - 2, prime)
    x, y = x * z_inverse % prime, y * z_inverse % prime
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def sign(module, seed, message):
    """RFC 8032 section 5.1.6, on the bridge's scalar multiplication."""
    digest = hashlib.sha512(seed).digest()
    scalar = (int.from_bytes(digest[:32], "little") & ((1 << 254) - 8)) | (1 << 254)
    nonce = int.from_bytes(hashlib.sha512(digest[32:] + message).digest(), "little") % module._ED_L
    nonce_encoded = encode_point(module._ed_mul(module._ED_BASE_POINT, nonce), module._ED_P)
    public = encode_point(module._ed_mul(module._ED_BASE_POINT, scalar), module._ED_P)
    challenge = int.from_bytes(hashlib.sha512(nonce_encoded + public + message).digest(), "little") % module._ED_L
    return nonce_encoded + ((nonce + challenge * scalar) % module._ED_L).to_bytes(32, "little")


def main(argv):
    module_path, seed_hex, url, *headers = argv[1:]
    spec = importlib.util.spec_from_file_location("telnyx_bridge", module_path)
    assert spec is not None and spec.loader is not None, module_path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # A fresh event id per call: a repeated one would be a redelivery.
    event = {
        "id": f"vm-signed-{time.time_ns()}",
        "event_type": "message.sent",
        "payload": {"id": "vm-out-1"},
    }
    body = json.dumps({"data": event}).encode()
    timestamp = str(int(time.time()))
    signature = sign(module, bytes.fromhex(seed_hex), timestamp.encode() + b"|" + body)
    if os.environ.get("SIGN_WEBHOOK_TAMPER") == "1":
        body = body.replace(b"message.sent", b"message.xent")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header(module.TIMESTAMP_HEADER, timestamp)
    request.add_header(module.SIGNATURE_HEADER, base64.b64encode(signature).decode())
    for header in headers:
        name, _, value = header.partition(":")
        request.add_header(name.strip(), value.strip())
    context = ssl.create_default_context()
    # The VM's vhost certificate is self-signed by design.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # nosec B501 - the suite's own loopback bridge, self-signed by design
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:  # nosec B310 - the suite's own bridge
            print("STATUS", response.status)
    except urllib.error.HTTPError as error:
        try:
            print("STATUS", error.code, error.read().decode("utf-8", "replace").strip())
        finally:
            error.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
