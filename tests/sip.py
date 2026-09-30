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
from time import monotonic as _time_monotonic

CRLF = "\r\n"


def random_token(length: int = 12) -> str:
    return "".join(
        # test token randomness, no security
        random.choice("0123456789abcdefghijklmnopqrstuvwxyz")  # nosec B311
        for _ in range(length)
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


def register(connection: SipConnection, expires: int = 300, contact_override: str | None = None) -> dict:
    """Run the REGISTER dance; returns the final response.

    contact_override advertises a different Contact address (the
    missed-call harness points it at a listening socket that rings but
    never answers)."""
    request_uri = f"sip:{connection.domain}"
    to_uri = request_uri
    contact = contact_override or f"<sip:{connection.user}@{connection.source_ip}:{connection.source_port};transport=tcp>"
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


def _raw_response(status_line: str, request: dict, to_tag: str, body: str = "") -> str:
    """One UAS response mirroring the received request's dialog headers."""
    to = request["headers"].get("to", "")
    if to_tag and "tag=" not in to:
        to = to.rstrip(">") + f";tag={to_tag}>"
    headers = [
        status_line,
        f"Via: {request['headers'].get('via', '')}",
        f"From: {request['headers'].get('from', '')}",
        f"To: {to}",
        f"Call-ID: {request['headers'].get('call-id', '')}",
        f"CSeq: {request['headers'].get('cseq', '')}",
        f"Content-Length: {len(body.encode('utf-8'))}",
    ]
    return CRLF.join(headers) + CRLF + CRLF + body


def _read_request(sock) -> dict:
    """Read one request (or response) frame from a accepted UAS socket."""
    sock.settimeout(30)
    buffer = b""
    while b"\r\n\r\n" not in buffer:
        chunk = sock.recv(4096)
        if not chunk:
            raise SipError("UAS socket closed before a full frame")
        buffer += chunk
    head = buffer.split(b"\r\n\r\n", 1)[0].decode("utf-8", "replace")
    lines = head.split("\r\n")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower()
            headers[key] = value.strip()
    return {"first_line": lines[0], "headers": headers}


def missed_call(
    args,
    destination: str,
    ring_seconds: float,
) -> int:
    """One missed call, both ends scripted:

    - the callee (--user) registers with a Contact pointing at a local
      LISTENER socket;
    - a second connection (--caller-user) INVITEs the destination;
    - the listener answers sofia's INVITE with 180 Ringing and NEVER
      answers;
    - after ring_seconds the caller CANCELs (same branch as the INVITE);
    - the listener completes the UAS dance (200 for CANCEL, 487 for the
      INVITE) and the caller must see 487.

    Prints CANCELLED 487 on the honest missed-call shape; this is the
    caller-gives-up-mid-ring scenario (cause ORIGINATOR_CANCEL on the
    A-leg) the CDR suite asserts Master.csv rows for.
    """
    reg = SipConnection(
        args.server, args.port, args.domain, args.user, args.password,
        bind_address=args.bind,
    )
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind((reg.source_ip, 0))
    listener.listen(1)
    listener_ip, listener_port = listener.getsockname()
    try:
        response = register(
            reg,
            contact_override=f"<sip:{args.user}@{listener_ip}:{listener_port};transport=tcp>",
        )
        if response["status"] != 200:
            raise SipError(f"callee REGISTER got {response['status']}")

        caller = SipConnection(
            args.server, args.port, args.domain, args.caller_user, args.caller_password,
            bind_address=args.bind,
        )
        request_uri = f"sip:{destination}@{caller.domain}"
        rtp_port = (caller.source_port + 100) // 2 * 2
        sdp = CRLF.join(
            [
                "v=0",
                f"o=- {random.randint(100000, 999999)} 1 IN IP4 {caller.source_ip}",  # nosec B311
                "s=sip-helper",
                f"c=IN IP4 {caller.source_ip}",
                "t=0 0",
                f"m=audio {rtp_port} RTP/AVP 0 101",
                "a=rtpmap:0 PCMU/8000",
                "a=rtpmap:101 telephone-event/8000",
                "a=sendrecv",
            ]
        )
        caller.send(caller.build_request("INVITE", request_uri, request_uri, [
            f"Contact: <sip:{caller.user}@{caller.source_ip}:{caller.source_port};transport=tcp>",
            "Content-Type: application/sdp",
        ], sdp))
        invite_response = caller.read_response()
        invite_branch = None
        if invite_response["status"] in (401, 407):
            via = invite_response["headers"].get("via", "")
            match = re.search(r"branch=([^;]+)", via)
            invite_branch = match.group(1) if match else None
            challenge_header, challenge = caller.auth_challenge(invite_response)
            authorization = f"{challenge_header}: {caller.digest('INVITE', request_uri, challenge)}"
            caller.cseq -= 1  # the retried INVITE keeps the cancelled CSeq
            caller.send(caller.build_request("INVITE", request_uri, request_uri, [
                f"Contact: <sip:{caller.user}@{caller.source_ip}:{caller.source_port};transport=tcp>",
                "Content-Type: application/sdp",
                authorization,
            ], sdp))

        # The B-leg INVITE arrives at the listener: ring, never answer.
        # Sofia may send keepalive/NOTIFY frames to the registered Contact
        # first — ack them with 200 and keep waiting for the INVITE.
        uas, _ = listener.accept()
        deadline = _time_monotonic() + 30
        invite = None
        while _time_monotonic() < deadline:
            frame = _read_request(uas)
            if frame["first_line"].startswith("INVITE "):
                invite = frame
                break
            if not frame["first_line"].startswith("SIP/2.0"):
                uas.sendall(_raw_response("SIP/2.0 200 OK", frame, "").encode())
        if invite is None:
            raise SipError("no INVITE reached the listener within 30s")
        uas.sendall(_raw_response("SIP/2.0 180 Ringing", invite, random_token(8)).encode())
        print("RINGING", flush=True)
        time.sleep(ring_seconds)

        # CANCEL from the caller: same branch + CSeq as the INVITE.
        cancel = caller.build_request("CANCEL", request_uri, request_uri, [])
        if invite_branch:
            cancel = re.sub(r"branch=z9hG4bK\w+", f"branch={invite_branch}", cancel)
        caller.send(cancel)

        deadline = _time_monotonic() + 30
        cancelled = None
        while _time_monotonic() < deadline:
            frame = _read_request(uas)
            if frame["first_line"].startswith("CANCEL "):
                cancelled = frame
                break
            if not frame["first_line"].startswith("SIP/2.0"):
                uas.sendall(_raw_response("SIP/2.0 200 OK", frame, "").encode())
        if cancelled is None:
            raise SipError("no CANCEL reached the listener within 30s")
        uas.sendall(_raw_response("SIP/2.0 200 OK", cancelled, "").encode())
        uas.sendall(_raw_response("SIP/2.0 487 Request Terminated", invite, random_token(8)).encode())

        final = caller.read_response()
        print(f"INVITE {final['status']}", flush=True)
        if final["status"] != 487:
            raise SipError(f"expected 487 after CANCEL, got {final['status']}")
        print("CANCELLED 487", flush=True)
        uas.close()
        return 0
    finally:
        reg.sock.close()
        listener.close()


def call(
    connection: SipConnection,
    destination: str,
    hold_seconds: float,
    expect_status: int,
    dump_dialog: bool = False,
) -> None:
    """INVITE -> (200: ACK -> hold -> BYE). Raises unless the final
    response status matches `expect_status`. With dump_dialog the final
    INVITE response is printed between DIALOG-BEGIN/DIALOG-END markers
    (headers lowercased, body verbatim) so callers can assert on Via/
    Contact/SDP advertisement (the NAT suite).
    """
    request_uri = f"sip:{destination}@{connection.domain}"
    to_uri = request_uri
    contact = f"<sip:{connection.user}@{connection.source_ip}:{connection.source_port};transport=tcp>"
    rtp_port = (connection.source_port + 100) // 2 * 2
    sdp = CRLF.join(
        [
            "v=0",
            f"o=- {random.randint(100000, 999999)} 1 IN IP4 {connection.source_ip}",  # nosec B311
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
    if dump_dialog:
        print("DIALOG-BEGIN", flush=True)
        print(response["first_line"], flush=True)
        for key, value in response["headers"].items():
            print(f"{key}: {value}", flush=True)
        print(response["body"], flush=True)
        print("DIALOG-END", flush=True)

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
    parser.add_argument(
        "--caller-user",
        default=None,
        help="missed-call only: the calling user (defaults to 1001)",
    )
    parser.add_argument(
        "--caller-password",
        default=None,
        help="missed-call only: the caller's password (defaults to --password)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("register")
    missed_parser = sub.add_parser(
        "missed-call",
        help="ring --to then CANCEL mid-ring (both ends scripted; 487 expected)",
    )
    missed_parser.add_argument("--to", required=True, help="destination number that rings")
    missed_parser.add_argument("--ring-seconds", type=float, default=3.0)
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
    invite_parser.add_argument(
        "--dump-dialog",
        action="store_true",
        help="print the final INVITE response between DIALOG-BEGIN/END markers (NAT advertisement asserts)",
    )

    args = parser.parse_args()
    if args.command == "missed-call":
        args.caller_user = args.caller_user or "1001"
        args.caller_password = args.caller_password or args.password
        return missed_call(args, args.to, args.ring_seconds)
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
            call(
                connection,
                args.to,
                args.hold_seconds,
                args.expect_status,
                dump_dialog=args.dump_dialog,
            )
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
