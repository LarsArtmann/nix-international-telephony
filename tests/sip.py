#!/usr/bin/env python3
"""Minimal scripted SIP user agent for the NixOS VM test.

Speaks SIP over TCP against the machine's FreeSWITCH internal profile
using only the Python standard library:

  register  — REGISTER with HTTP-Digest auth (MD5 or SHA-256 challenge),
              prints the final response code; exit 0 iff 200.
  invite    — REGISTER (as above), then INVITE to a destination, wait for
              the 200 answer, ACK, hold the call for a few seconds and
              BYE. Prints "ANSWERED" once the 200 arrives; exit 0 iff the
              call was answered and torn down cleanly.

Used by tests/pbx.nix to prove registration, authentication denial and
end-to-end call setup without a real softphone.
"""

import argparse
import hashlib
import random
import re
import socket
import sys
import time

CRLF = "\r\n"


def random_token(length: int = 12) -> str:
    return "".join(
        random.choice("0123456789abcdefghijklmnopqrstuvwxyz") for _ in range(length)
    )


class SipError(Exception):
    pass


class SipConnection:
    """One TCP connection to the SIP server; framed request/response I/O."""

    def __init__(
        self,
        server: str,
        port: int,
        domain: str,
        user: str,
        password: str,
        bind_address: str | None = None,
    ):
        self.server = server
        self.port = port
        self.domain = domain
        self.user = user
        self.password = password
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if bind_address:
            self.sock.bind((bind_address, 0))
        self.sock.settimeout(15)
        self.sock.connect((server, port))
        self.sock.settimeout(20)
        self.source_ip, self.source_port = self.sock.getsockname()
        self.buffer = b""
        self.call_id = f"{random_token()}@{self.source_ip}"
        self.from_tag = random_token(8)
        self.cseq = 0

    # -- framing -----------------------------------------------------------

    def read_response(self) -> dict:
        """Read until the next final (>= 2xx status) response.

        Provisional responses (1xx) and server-initiated requests (e.g.
        OPTIONS keepalives) are skipped. Returns a dict with status,
        headers (lowercased keys, comma-joined when repeated) and body.
        """
        deadline = time.monotonic() + 90
        while True:
            message = self._parse_one()
            if message is None:
                if time.monotonic() > deadline:
                    raise SipError("timed out waiting for a SIP response")
                chunk = self.sock.recv(65536)
                if not chunk:
                    raise SipError("connection closed by server")
                self.buffer += chunk
                continue
            first_line = message["first_line"]
            if not first_line.startswith("SIP/2.0 "):
                continue  # server-initiated request: skip
            status = int(first_line.split()[1])
            if status < 200:
                continue  # provisional: skip
            message["status"] = status
            return message

    def _parse_one(self) -> dict | None:
        separator = self.buffer.find(b"\r\n\r\n")
        if separator < 0:
            return None
        head = self.buffer[:separator].decode("utf-8", "replace")
        lines = head.split("\r\n")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip().lower()
                value = value.strip()
                headers[key] = f"{headers[key]}, {value}" if key in headers else value
        content_length = 0
        for key, value in headers.items():
            if key == "content-length":
                content_length = int(value)
                break
        if len(self.buffer) < separator + 4 + content_length:
            return None
        body = self.buffer[separator + 4 : separator + 4 + content_length]
        self.buffer = self.buffer[separator + 4 + content_length :]
        return {
            "first_line": lines[0],
            "headers": headers,
            "body": body.decode("utf-8", "replace"),
        }

    # -- message building --------------------------------------------------

    def build_request(
        self,
        method: str,
        request_uri: str,
        to_uri: str,
        extra_headers: list[str],
        body: str = "",
    ) -> str:
        self.cseq += 1
        via = (
            f"SIP/2.0/TCP {self.source_ip}:{self.source_port};"
            f"rport;branch=z9hG4bK{random_token(10)}"
        )
        headers = [
            f"{method} {request_uri} SIP/2.0",
            f"Via: {via}",
            f"From: <sip:{self.user}@{self.domain}>;tag={self.from_tag}",
            f"To: {to_uri if to_uri.startswith('<') else f'<{to_uri}>'}",
            f"Call-ID: {self.call_id}",
            f"CSeq: {self.cseq} {method}",
            "Max-Forwards: 70",
        ]
        headers += extra_headers
        if body:
            headers.append(f"Content-Length: {len(body.encode('utf-8'))}")
        else:
            headers.append("Content-Length: 0")
        message = CRLF.join(headers) + CRLF + CRLF
        if body:
            message += body
        return message

    def send(self, message: str) -> None:
        self.sock.sendall(message.encode("utf-8"))

    # -- digest auth -------------------------------------------------------

    def auth_challenge(self, response: dict) -> tuple[str, dict]:
        """Extract the digest challenge from a 401/407 response.

        Returns the header name to answer with (Authorization vs
        Proxy-Authorization) and the challenge parameters.
        """
        header_name = "Authorization"
        challenge = response["headers"].get("www-authenticate", "")
        if not challenge:
            header_name = "Proxy-Authorization"
            challenge = response["headers"].get("proxy-authenticate", "")
        if not challenge:
            raise SipError(f"no digest challenge in {response['status']} response")
        params = {}
        for key, quoted, plain in re.findall(
            r'(\w+)=(?:"([^"]*)"|([^\s,]+))', challenge
        ):
            params[key.lower()] = quoted or plain
        for required in ("realm", "nonce"):
            if required not in params:
                raise SipError(f"challenge missing {required}: {challenge}")
        params.setdefault("algorithm", "MD5")
        return header_name, params

    def digest(self, method: str, uri: str, challenge: dict) -> str:
        algorithm = challenge["algorithm"].upper()
        hash_name = {"MD5": "md5", "SHA-256": "sha256", "SHA-512": "sha512"}.get(
            algorithm
        )
        if hash_name is None:
            raise SipError(f"unsupported digest algorithm {algorithm}")

        def h(text: str) -> str:
            return hashlib.new(hash_name, text.encode("utf-8")).hexdigest()

        ha1 = h(f"{self.user}:{challenge['realm']}:{self.password}")
        ha2 = h(f"{method}:{uri}")
        qop = challenge.get("qop")
        if qop:
            cnonce = random_token(16)
            nc = "00000001"
            qop_value = qop.split(",")[0].strip()
            response = h(f"{ha1}:{challenge['nonce']}:{nc}:{cnonce}:{qop_value}:{ha2}")
            return (
                f'Digest username="{self.user}", realm="{challenge["realm"]}", '
                f'nonce="{challenge["nonce"]}", uri="{uri}", response="{response}", '
                f'algorithm={algorithm}, cnonce="{cnonce}", nc={nc}, qop={qop_value}'
            )
        response = h(f"{ha1}:{challenge['nonce']}:{ha2}")
        return (
            f'Digest username="{self.user}", realm="{challenge["realm"]}", '
            f'nonce="{challenge["nonce"]}", uri="{uri}", response="{response}", '
            f"algorithm={algorithm}"
        )


def register(connection: SipConnection, expires: int = 300) -> dict:
    """Run the REGISTER dance; returns the final response."""
    request_uri = f"sip:{connection.domain}"
    to_uri = request_uri
    contact = f"<sip:{connection.user}@{connection.source_ip}:{connection.source_port};transport=tcp>"
    common = [
        f"Contact: {contact}",
        f"Expires: {expires}",
        "Allow: INVITE, ACK, BYE, CANCEL, OPTIONS",
    ]

    connection.send(connection.build_request("REGISTER", request_uri, to_uri, common))
    response = connection.read_response()
    if response["status"] == 200:
        return response
    if response["status"] not in (401, 407):
        raise SipError(
            f"unexpected REGISTER response {response['status']} {response['first_line']}"
        )
    challenge_header, challenge = connection.auth_challenge(response)
    connection.send(
        connection.build_request(
            "REGISTER",
            request_uri,
            to_uri,
            [
                f"{challenge_header}: {connection.digest('REGISTER', request_uri, challenge)}"
            ]
            + common,
        )
    )
    return connection.read_response()


def call(
    connection: SipConnection, destination: str, hold_seconds: float, expect_status: int
) -> None:
    """INVITE -> (200: ACK -> hold -> BYE). Raises unless the final
    response status matches `expect_status`."""
    request_uri = f"sip:{destination}@{connection.domain}"
    to_uri = request_uri
    contact = f"<sip:{connection.user}@{connection.source_ip}:{connection.source_port};transport=tcp>"
    rtp_port = (connection.source_port + 100) // 2 * 2
    sdp = CRLF.join(
        [
            "v=0",
            f"o=- {random.randint(100000, 999999)} 1 IN IP4 {connection.source_ip}",
            "s=sip-helper",
            f"c=IN IP4 {connection.source_ip}",
            "t=0 0",
            f"m=audio {rtp_port} RTP/AVP 0 101",
            "a=rtpmap:0 PCMU/8000",
            "a=rtpmap:101 telephone-event/8000",
            "a=fmtp:101 0-16",
            "a=sendrecv",
        ]
    )

    def invite_headers(authorization_header: str | None) -> list[str]:
        headers = [
            f"Contact: {contact}",
            "Content-Type: application/sdp",
        ]
        if authorization_header:
            headers.append(authorization_header)
        return headers

    # INVITE attempt 1: answer a digest challenge if one comes (internal
    # profile); unauthenticated profiles (external) answer directly.
    connection.send(
        connection.build_request(
            "INVITE", request_uri, to_uri, invite_headers(None), sdp
        )
    )
    response = connection.read_response()
    if response["status"] in (401, 407):
        challenge_header, challenge = connection.auth_challenge(response)
        authorization = (
            f"{challenge_header}: {connection.digest('INVITE', request_uri, challenge)}"
        )
        connection.send(
            connection.build_request(
                "INVITE", request_uri, to_uri, invite_headers(authorization), sdp
            )
        )
        response = connection.read_response()
    print(f"INVITE {response['status']}", flush=True)
    if response["status"] != expect_status:
        raise SipError(
            f"INVITE got {response['status']}, expected {expect_status}:\n"
            f"{response['first_line']}\n{response['headers']}\n{response['body']}"
        )
    if response["status"] != 200:
        return  # denial path: no dialog to acknowledge or tear down
    print("ANSWERED", flush=True)

    to_header = response["headers"].get("to", "")
    to_tag_match = re.search(r"tag=([^;>]+)", to_header)
    to_tag = f";tag={to_tag_match.group(1)}" if to_tag_match else ""
    dialog_to = f"<{request_uri}>{to_tag}"
    remote_target = response["headers"].get("contact", "")
    contact_match = re.search(r"<([^>]+)>", remote_target)
    remote_uri = contact_match.group(1) if contact_match else request_uri

    connection.send(connection.build_request("ACK", remote_uri, dialog_to, []))
    time.sleep(hold_seconds)
    connection.send(connection.build_request("BYE", remote_uri, dialog_to, []))
    bye_response = connection.read_response()
    if bye_response["status"] != 200:
        raise SipError(f"BYE failed with {bye_response['status']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, help="SIP server IP")
    parser.add_argument(
        "--bind",
        default=None,
        help="local source IP to bind (e.g. 127.0.0.2 for ACL tests)",
    )
    parser.add_argument("--port", type=int, default=5060)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--domain", required=True, help="SIP domain/realm")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("register")
    invite_parser = sub.add_parser("invite")
    invite_parser.add_argument("--to", required=True, help="destination number")
    invite_parser.add_argument("--hold-seconds", type=float, default=4.0)
    invite_parser.add_argument(
        "--expect-status",
        type=int,
        default=200,
        help="required final INVITE status (403/503 for denial-path tests)",
    )
    invite_parser.add_argument(
        "--skip-register",
        action="store_true",
        help="send the INVITE without registering (external profile)",
    )

    args = parser.parse_args()
    connection = SipConnection(
        args.server,
        args.port,
        args.domain,
        args.user,
        args.password,
        bind_address=args.bind,
    )
    try:
        if args.command == "register":
            response = register(connection)
            print(f"REGISTER {response['status']}", flush=True)
            return 0 if response["status"] == 200 else 1
        if args.command == "invite":
            if not args.skip_register:
                register(connection)
            call(connection, args.to, args.hold_seconds, args.expect_status)
            print("CALL COMPLETE", flush=True)
            return 0
    except SipError as error:
        print(f"SIP-ERROR: {error}", file=sys.stderr, flush=True)
        return 2
    finally:
        connection.sock.close()
    return 3


if __name__ == "__main__":
    sys.exit(main())
