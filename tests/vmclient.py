#!/usr/bin/env python3
"""Scripted voicemail client for the NixOS VM test (stdlib only).

Builds on tests/sip.py (imported from the same /etc directory in the VM)
and adds the media half that voicemail needs:

  deposit — REGISTER, INVITE a number whose voicemail fallback answers,
            stream G.711 µ-law NOISE RTP for several seconds (mod_voicemail
            discards recordings under min-record-len=3s and silence-aware
            recording, so quiet audio would be dropped), then BYE. The
            message must land in the callee's box (asserted host-side by
            the file appearing).
  check   — REGISTER, INVITE *98 (voicemail check), wait for the answer,
            send the PIN as RFC 4733 telephone-event RTP digits, then
            count the RTP bytes streamed back: after a correct PIN
            mod_voicemail auto-plays new messages, which is real audio.
            With --repeat-pin N the PIN is entered N times: mod_voicemail
            allows max-login-attempts=3, then plays goodbye and hangs up
            — the server-side BYE is the wrong-PIN denial proof.

mod_voicemail behaviour relied on here was verified against the upstream
source (v1.10.12 src/mod/applications/mod_voicemail/mod_voicemail.c).
"""

import argparse
import os
import random
import re
import select
import socket
import struct
import sys
import time

sys.path.insert(0, "/etc")
import sip  # noqa: E402  (tests/sip.py shipped next to this file)

PT_PCMU = 0
PT_EVENT = 101
DTMF_EVENTS = {c: i for i, c in enumerate("0123456789*#ABCD")}


def pcmu_noise() -> bytes:
    """160 samples (20 ms) of loud µ-law noise: above the record-silence
    threshold so the deposit actually lands."""
    return bytes(random.getrandbits(8) for _ in range(160))


class RtpStream:
    """One UDP RTP stream: sends PCMU noise / DTMF events, counts input."""

    def __init__(self, local_ip: str, local_port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((local_ip, local_port))
        self.sock.setblocking(False)
        self.ssrc = random.randint(1, 2**31 - 1)
        self.seq = random.randint(1, 2**15 - 1)
        self.timestamp = random.randint(1, 2**31 - 1)
        self.peer = None  # (ip, port) from the answer's SDP
        # telephone-event payload type from the ANSWER's SDP (sofia does
        # not always echo our 101 — sending events on an unnnegotiated PT
        # makes them vanish silently).
        self.event_pt = 101

    def adopt_sdp_answer(self, body: str) -> None:
        self.peer = sdp_peer(body)
        match = re.search(r"^a=rtpmap:(\d+) telephone-event/8000", body, re.MULTILINE)
        if match:
            self.event_pt = int(match.group(1))
        if os.environ.get("VM_DEBUG"):
            print(f"VM-DEBUG sdp-peer={self.peer} event_pt={self.event_pt}", flush=True)

    def send_pcmu(self) -> None:
        self._send(pcmu_noise(), PT_PCMU, marker=False)
        self.timestamp += 160

    def send_digit(self, char: str) -> None:
        """One RFC 4733 digit: three event repeats with rising duration
        plus the end-bit packet (payload is event, E|volume, duration16)."""
        event = DTMF_EVENTS[char]
        start_ts = self.timestamp
        duration = 0
        for _ in range(3):
            self._send(
                struct.pack("!BBH", event, 0x0A, duration),
                self.event_pt,
                marker=True,
                ts=start_ts,
            )
            duration += 160
            time.sleep(0.02)
        self._send(
            struct.pack("!BBH", event, 0x8A, duration),
            self.event_pt,
            marker=False,
            ts=start_ts,
        )
        self.timestamp += duration

    def _send(
        self, payload: bytes, payload_type: int, marker: bool, ts: int | None = None
    ) -> None:
        header = struct.pack(
            "!BBHII",
            0x80,
            (0x80 if marker else 0) | payload_type,
            self.seq,
            self.timestamp if ts is None else ts,
            self.ssrc,
        )
        self.seq = (self.seq + 1) & 0xFFFF
        if self.peer:
            self.sock.sendto(header + payload, self.peer)

    def pump(self, seconds: float) -> tuple[int, int]:
        """Run the stream for `seconds`: send noise, count received
        bytes/packets. Returns (bytes, packets)."""
        received_bytes = 0
        packets = 0
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.send_pcmu()
            readable, _, _ = select.select([self.sock], [], [], 0.02)
            for sock in readable:
                while True:
                    try:
                        chunk, _ = sock.recvfrom(2048)
                    except BlockingIOError:
                        break
                    received_bytes += len(chunk)
                    packets += 1
        return received_bytes, packets


def sdp_peer(body: str) -> tuple[str, int]:
    """Connection address + audio port from an SDP answer."""
    address = re.search(r"^c=IN IP4 (\S+)", body, re.MULTILINE)
    media = re.search(r"^m=audio (\d+)", body, re.MULTILINE)
    if not address or not media:
        raise sip.SipError(f"no RTP peer in SDP answer:\n{body}")
    return address.group(1), int(media.group(1))


def invite_and_answer(
    connection: sip.SipConnection, destination: str, rtp: RtpStream
) -> tuple[dict, str, str]:
    """INVITE with our real RTP socket in the SDP; ACKs the 200 and
    returns (response, remote_uri, dialog_to)."""
    request_uri = f"sip:{destination}@{connection.domain}"
    contact = (
        f"<sip:{connection.user}@{connection.source_ip}:{connection.source_port};transport=tcp>"
    )
    sdp = sip.CRLF.join(
        [
            "v=0",
            f"o=- {random.randint(100000, 999999)} 1 IN IP4 {connection.source_ip}",
            "s=vmclient",
            f"c=IN IP4 {connection.source_ip}",
            "t=0 0",
            f"m=audio {rtp.sock.getsockname()[1]} RTP/AVP 0 101",
            "a=rtpmap:0 PCMU/8000",
            "a=rtpmap:101 telephone-event/8000",
            "a=fmtp:101 0-16",
            "a=sendrecv",
        ]
    )
    headers = [
        f"Contact: {contact}",
        "Content-Type: application/sdp",
    ]
    connection.send(
        connection.build_request("INVITE", request_uri, request_uri, headers, sdp)
    )
    response = connection.read_response()
    if response["status"] in (401, 407):
        name, challenge = connection.auth_challenge(response)
        headers.append(f"{name}: {connection.digest('INVITE', request_uri, challenge)}")
        connection.send(
            connection.build_request("INVITE", request_uri, request_uri, headers, sdp)
        )
        response = connection.read_response()
    if response["status"] != 200:
        raise sip.SipError(f"INVITE answered {response['status']}, expected 200")
    ack_target = re.search(r"<([^>]+)>", response["headers"].get("contact", ""))
    remote_uri = ack_target.group(1) if ack_target else request_uri
    to_tag = re.search(r"tag=([^;>]+)", response["headers"].get("to", ""))
    dialog_to = f"<{request_uri}>" + (f";tag={to_tag.group(1)}" if to_tag else "")
    connection.send(connection.build_request("ACK", remote_uri, dialog_to, []))
    return response, remote_uri, dialog_to


def bye(connection: sip.SipConnection, remote_uri: str, dialog_to: str) -> None:
    connection.send(connection.build_request("BYE", remote_uri, dialog_to, []))
    connection.read_response()


def make_rtp(connection: sip.SipConnection) -> RtpStream:
    return RtpStream(connection.source_ip, (connection.source_port + 100) // 2 * 2)


def deposit(connection: sip.SipConnection, rtp: RtpStream, destination: str, seconds: float) -> None:
    response, remote_uri, dialog_to = invite_and_answer(connection, destination, rtp)
    print("VM-DEPOSIT-ANSWERED", flush=True)
    rtp.adopt_sdp_answer(response["body"])
    # The greeting plays before the record beep; keep noise flowing the
    # whole window so >= min-record-len seconds land after the beep.
    rtp.pump(seconds)
    bye(connection, remote_uri, dialog_to)
    print("VM-DEPOSIT-BYE", flush=True)


def enter_pin(rtp: RtpStream, pin: str) -> None:
    """Enter digits as RFC 4733 telephone-event RTP, terminated by '#'.

    Corrected after source-reading mod_sofia: sofia.c's ONLY dtmf-relay
    parser looks for "Signal=" (equals form) and sits behind the
    off-by-default profile flag `extended-info-parsing` — the
    "Signal: <d>" (colon) INFO bodies this client once sent were 200-OK'd
    and silently dropped, so no scripted digit ever arrived (the IVR
    suite's deterministic no-collection failure proved it live). Real
    telephone-events on the negotiated PT need no server-side flags.
    """
    for digit in pin + "#":
        rtp.send_digit(digit)
        time.sleep(0.05)


def check(
    connection: sip.SipConnection,
    rtp: RtpStream,
    pin: str,
    repeat_pin: int,
    listen_seconds: float,
) -> int:
    response, remote_uri, dialog_to = invite_and_answer(connection, "*98", rtp)
    print("VM-CHECK-ANSWERED", flush=True)
    rtp.adopt_sdp_answer(response["body"])
    # The *98 login asks for the MAILBOX ID first, then the password.
    # Digits arriving while a phrase macro plays are consumed as its
    # cancel input and dropped, so each entry waits out the preceding
    # phrases before sending (hello ~2 s; the ID prompt follows, then
    # the password prompt).
    rtp.pump(5.0)
    enter_pin(rtp, connection.user)
    rtp.pump(5.0)

    for _ in range(repeat_pin):
        enter_pin(rtp, pin)
        if repeat_pin > 1:
            rtp.pump(4.0)

    # Correct PIN: folder summary + auto-played messages arrive as real
    # audio. Wrong PIN (all attempts): goodbye phrase, then the server
    # hangs the call up.
    received_bytes, packets = rtp.pump(listen_seconds)
    print(f"VM-CHECK-RTP bytes={received_bytes} packets={packets}", flush=True)

    server_bye = False
    connection.sock.setblocking(False)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not server_bye:
        readable, _, _ = select.select([connection.sock], [], [], 0.2)
        if readable:
            try:
                chunk = connection.sock.recv(65536)
            except BlockingIOError:
                continue
            if not chunk:
                break
            server_bye = b"BYE " in chunk
    print(f"VM-SERVER-HANGUP {'yes' if server_bye else 'no'}", flush=True)
    if not server_bye:
        connection.sock.setblocking(True)
        bye(connection, remote_uri, dialog_to)
        print("VM-CHECK-BYE", flush=True)
    return 0


def join(
    connection: sip.SipConnection,
    rtp: RtpStream,
    destination: str,
    seconds: float,
) -> int:
    """Join a conference bridge: stay for `seconds` streaming noise and
    counting received audio (the mixed bridge), then leave cleanly."""
    response, remote_uri, dialog_to = invite_and_answer(connection, destination, rtp)
    print("VM-JOIN-ANSWERED", flush=True)
    rtp.adopt_sdp_answer(response["body"])
    received_bytes, packets = rtp.pump(seconds)
    print(f"VM-JOIN-RTP bytes={received_bytes} packets={packets}", flush=True)
    bye(connection, remote_uri, dialog_to)
    print("VM-JOIN-BYE", flush=True)
    return 0


def menu(
    connection: sip.SipConnection,
    rtp: RtpStream,
    destination: str,
    key: str,
    listen_seconds: float,
) -> int:
    """Dial an IVR menu, press `key` (SIP INFO dtmf-relay), and report the
    audio that streams back plus whether the server hung up."""
    response, remote_uri, dialog_to = invite_and_answer(connection, destination, rtp)
    print("VM-MENU-ANSWERED", flush=True)
    rtp.adopt_sdp_answer(response["body"])
    # Digits sent while a PROMPT is still playing get swallowed by the
    # prompt's own input handling before the collector sees them — wait
    # out the menu's greeting tone so collection is definitely active.
    rtp.pump(2.5)
    enter_pin(rtp, key)
    received_bytes, packets = rtp.pump(listen_seconds)
    print(f"VM-MENU-RTP bytes={received_bytes} packets={packets}", flush=True)
    server_bye = False
    connection.sock.setblocking(False)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and not server_bye:
        readable, _, _ = select.select([connection.sock], [], [], 0.2)
        if readable:
            try:
                chunk = connection.sock.recv(65536)
            except BlockingIOError:
                continue
            if not chunk:
                break
            server_bye = b"BYE " in chunk
    print(f"VM-SERVER-HANGUP {'yes' if server_bye else 'no'}", flush=True)
    if not server_bye:
        connection.sock.setblocking(True)
        bye(connection, remote_uri, dialog_to)
        print("VM-MENU-BYE", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True)
    parser.add_argument("--bind", default=None)
    parser.add_argument("--port", type=int, default=5060)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--domain", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    dep = sub.add_parser("deposit")
    dep.add_argument("--to", required=True)
    dep.add_argument("--seconds", type=float, default=10.0)
    jn = sub.add_parser("join")
    jn.add_argument("--to", required=True)
    jn.add_argument("--seconds", type=float, default=8.0)
    men = sub.add_parser("menu")
    men.add_argument("--to", required=True, help="IVR extension to dial")
    men.add_argument("--key", required=True, help="key to press (digits and *)")
    men.add_argument("--listen-seconds", type=float, default=8.0)
    chk = sub.add_parser("check")
    chk.add_argument("--pin", required=True)
    chk.add_argument("--listen-seconds", type=float, default=12.0)
    chk.add_argument(
        "--repeat-pin",
        type=int,
        default=1,
        help="enter the PIN this many times (3 wrong entries exhaust "
        "max-login-attempts and the server hangs up)",
    )
    args = parser.parse_args()

    connection = sip.SipConnection(
        args.server, args.port, args.domain, args.user, args.password,
        bind_address=args.bind,
    )
    rtp = make_rtp(connection)
    try:
        sip.register(connection)
        if args.command == "deposit":
            deposit(connection, rtp, args.to, args.seconds)
            return 0
        if args.command == "join":
            return join(connection, rtp, args.to, args.seconds)
        if args.command == "menu":
            return menu(connection, rtp, args.to, args.key, args.listen_seconds)
        return check(connection, rtp, args.pin, args.repeat_pin, args.listen_seconds)
    except sip.SipError as error:
        print(f"VM-ERROR: {error}", file=sys.stderr, flush=True)
        return 2
    finally:
        connection.sock.close()


if __name__ == "__main__":
    sys.exit(main())
