#!/usr/bin/env python3
"""Minimal scripted STUN/TURN client for the NixOS VM test.

Stdlib only. Proves coturn answers STUN binding requests on 3478 and that
TURN allocations work with REST-style ephemeral credentials (and fail
with the wrong secret):

  stun      — STUN binding request; exit 0 iff a response arrives.
  allocate  — TURN allocate with long-term credentials
              (username/password given explicitly, e.g. read from the
              served config.js); exit 0 iff allocation succeeds.
              --expect-401 flips the assertion: exit 0 iff coturn
              rejects the credentials with 401.
"""

import argparse
import hashlib
import hmac
import secrets
import socket
import struct
import sys

MAGIC_COOKIE = 0x2112A442

BINDING_REQUEST = 0x0001
BINDING_SUCCESS = 0x0101
ALLOCATE = 0x0003
ALLOCATE_SUCCESS = 0x0103
ALLOCATE_ERROR = 0x0113

ATTR_USERNAME = 0x0006
ATTR_MESSAGE_INTEGRITY = 0x0008
ATTR_ERROR_CODE = 0x0009
ATTR_REALM = 0x0014
ATTR_NONCE = 0x0015
ATTR_REQUESTED_TRANSPORT = 0x0019


class TurnError(Exception):
    pass


def pad(value: bytes) -> bytes:
    return value + b"\x00" * ((4 - len(value) % 4) % 4)


def attribute(attr_type: int, value: bytes) -> bytes:
    return struct.pack("!HH", attr_type, len(value)) + pad(value)


def parse_attributes(data: bytes) -> dict[int, bytes]:
    attrs: dict[int, bytes] = {}
    offset = 20
    while offset + 4 <= len(data):
        attr_type, length = struct.unpack("!HH", data[offset : offset + 4])
        attrs[attr_type] = data[offset + 4 : offset + 4 + length]
        offset += 4 + length + ((4 - length % 4) % 4)
    return attrs


def build_message(
    message_type: int, transaction: bytes, attributes: list[bytes], key: bytes | None
) -> bytes:
    body = b"".join(attributes)
    if key is None:
        return (
            struct.pack("!HHI", message_type, len(body), MAGIC_COOKIE)
            + transaction
            + body
        )
    # MESSAGE-INTEGRITY is computed over the message truncated BEFORE the
    # MI attribute, with the header length already counting MI (coturn's
    # reading of RFC 5389 15.4).
    length_with_mi = len(body) + 24
    message = (
        struct.pack("!HHI", message_type, length_with_mi, MAGIC_COOKIE)
        + transaction
        + body
    )
    mac = hmac.new(key, message, hashlib.sha1).digest()
    return message + attribute(ATTR_MESSAGE_INTEGRITY, mac)


def error_code(attrs: dict[int, bytes]) -> int:
    error = attrs.get(ATTR_ERROR_CODE, b"")
    if len(error) < 4:
        return 0
    return error[2] * 100 + error[3]


def transact(sock: socket.socket, server: tuple, message: bytes) -> bytes:
    sock.sendto(message, server)
    sock.settimeout(10)
    data, _ = sock.recvfrom(2048)
    return data


def stun(server: tuple) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        transaction = secrets.token_bytes(12)
        request = build_message(BINDING_REQUEST, transaction, [], None)
        data = transact(sock, server, request)
        message_type = struct.unpack("!H", data[:2])[0]
        if message_type != BINDING_SUCCESS:
            raise TurnError(f"unexpected STUN response type 0x{message_type:04x}")
        print("STUN OK", flush=True)
    finally:
        sock.close()


def allocate(server: tuple, username: str, password: str, expect_401: bool) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        transaction = secrets.token_bytes(12)
        requested = attribute(ATTR_REQUESTED_TRANSPORT, bytes([17, 0, 0, 0]))
        first = build_message(ALLOCATE, transaction, [requested], None)
        data = transact(sock, server, first)
        attrs = parse_attributes(data)
        message_type = struct.unpack("!H", data[:2])[0]
        if message_type != ALLOCATE_ERROR:
            raise TurnError(f"first allocate not challenged: 0x{message_type:04x}")
        nonce = attrs.get(ATTR_NONCE)
        realm = attrs.get(ATTR_REALM)
        if not nonce or not realm:
            raise TurnError("401 response missing NONCE/REALM")

        key = hashlib.md5(f"{username}:{realm.decode()}:{password}".encode()).digest()
        authenticated = build_message(
            ALLOCATE,
            transaction,
            [
                requested,
                attribute(ATTR_USERNAME, username.encode()),
                attribute(ATTR_REALM, realm),
                attribute(ATTR_NONCE, nonce),
            ],
            key,
        )
        data = transact(sock, server, authenticated)
        message_type = struct.unpack("!H", data[:2])[0]
        if expect_401:
            if message_type != ALLOCATE_ERROR:
                raise TurnError(f"bad credentials were accepted: 0x{message_type:04x}")
            error = parse_attributes(data).get(ATTR_ERROR_CODE, b"")
            code = error_code(attrs)
            if code != 401:
                raise TurnError(f"expected 401, got {code}")
            print("ALLOCATE REJECTED 401", flush=True)
            return
        if message_type != ALLOCATE_SUCCESS:
            error = parse_attributes(data).get(ATTR_ERROR_CODE, b"")
            code = error_code(attrs)
            raise TurnError(f"allocate failed: 0x{message_type:04x} code {code}")
        print("ALLOCATE OK", flush=True)
    finally:
        sock.close()


def main() -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--server", default="127.0.0.1")
    common.add_argument("--port", type=int, default=3478)
    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("stun", parents=[common])
    allocate_parser = sub.add_parser("allocate", parents=[common])
    allocate_parser.add_argument("--username", required=True)
    allocate_parser.add_argument("--password", required=True)
    allocate_parser.add_argument("--expect-401", action="store_true")

    args = parser.parse_args()
    server = (args.server, args.port)
    try:
        if args.command == "stun":
            stun(server)
        else:
            allocate(server, args.username, args.password, args.expect_401)
        return 0
    except TurnError as error:
        print(f"TURN-ERROR: {error}", file=sys.stderr, flush=True)
        return 2
    except OSError as error:
        print(f"TURN-ERROR: {error}", file=sys.stderr, flush=True)
        return 3


if __name__ == "__main__":
    sys.exit(main())
