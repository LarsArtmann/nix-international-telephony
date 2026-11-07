#!/usr/bin/env python3
"""Unit tests for tests/sip.py's digest re-auth loop (stdlib lane).

The loop is VM-proven (the 2026-10-26 dialplan suite) but had no
stdlib-level pin: a digest over the NEW nonce after a stale=true
re-challenge, and the bounded 3-round exhaustion. A scripted fake
socket drives SipConnection without a network.
"""

import hashlib
import unittest
from unittest import mock

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.sip import SipConnection, call  # noqa: E402


class FakeSocket:
    """Scripted duplex socket: recv returns the queued frames in order."""

    def __init__(self, frames: list[bytes]):
        self.frames = list(frames)
        self.sent: list[str] = []

    def sendall(self, data) -> None:
        self.sent.append(data.decode("utf-8", "replace"))

    def recv(self, _n: int) -> bytes:
        if not self.frames:
            raise AssertionError("fake socket drained — test script too short")
        return self.frames.pop(0)

    def getsockname(self):
        return ("127.0.0.1", 5555)

    def settimeout(self, _t):
        pass

    def connect(self, _addr):
        pass


def make_connection(frames) -> SipConnection:
    conn = SipConnection.__new__(SipConnection)
    conn.server = "127.0.0.1"
    conn.port = 5060
    conn.domain = "pbx.test"
    conn.user = "1000"
    conn.password = "sekret"
    conn.sock = FakeSocket(frames)
    conn.buffer = b""
    conn.call_id = "unittest@127.0.0.1"
    conn.from_tag = "aaaa1111"
    conn.cseq = 0
    conn.source_ip = "127.0.0.1"
    conn.source_port = 5555
    return conn


def challenge_frame(status: str, nonce: str, header: str, stale: bool = False) -> bytes:
    stale_part = ", stale=true" if stale else ""
    return (
        f"SIP/2.0 {status}\r\n"
        f"Via: SIP/2.0/TCP 127.0.0.1:5555;branch=z9hG4bKx\r\n"
        f"From: <sip:1000@pbx.test>;tag=aaaa1111\r\n"
        f"To: <sip:1000@pbx.test>\r\n"
        f"Call-ID: unittest@127.0.0.1\r\n"
        f"CSeq: 1 INVITE\r\n"
        f'{header}: Digest realm="pbx.test", nonce="{nonce}"{stale_part}\r\n'
        f"Content-Length: 0\r\n\r\n"
    ).encode()


def ok_frame() -> bytes:
    return (
        "SIP/2.0 200 OK\r\n"
        "Via: SIP/2.0/TCP 127.0.0.1:5555;branch=z9hG4bKx\r\n"
        "From: <sip:1000@pbx.test>;tag=aaaa1111\r\n"
        "To: <sip:1000@pbx.test>;tag=srv9\r\n"
        "Call-ID: unittest@127.0.0.1\r\n"
        "CSeq: 1 INVITE\r\n"
        "Content-Length: 0\r\n\r\n"
    ).encode()


class DigestTest(unittest.TestCase):
    def test_digest_no_qop_matches_rfc2069_value(self) -> None:
        conn = make_connection([])
        challenge = {"realm": "pbx.test", "nonce": "N1", "algorithm": "MD5"}

        def h(text: str) -> str:
            return hashlib.md5(text.encode()).hexdigest()

        ha1 = h("1000:pbx.test:sekret")
        ha2 = h("REGISTER:sip:pbx.test")
        expected = h(f"{ha1}:N1:{ha2}")
        header = conn.digest("REGISTER", "sip:pbx.test", challenge)
        self.assertIn(f'response="{expected}"', header)
        self.assertIn('nonce="N1"', header)

    def test_digest_unsupported_algorithm_raises(self) -> None:
        conn = make_connection([])
        with self.assertRaises(Exception):
            conn.digest(
                "REGISTER",
                "sip:pbx.test",
                {"realm": "r", "nonce": "n", "algorithm": "CRAMD"},
            )


class ReAuthLoopTest(unittest.TestCase):
    """The INVITE loop: a digest over the NEW nonce after stale=true."""

    def test_re_digest_uses_new_nonce_and_converges(self) -> None:
        frames = [
            challenge_frame("401 Unauthorized", "N1", "WWW-Authenticate"),
            challenge_frame("407 stale", "N2", "Proxy-Authenticate", stale=True),
            ok_frame(),
            ok_frame(),
        ]
        conn = make_connection(frames)
        call(conn, "2000", 0.0, 200)
        invites = [m for m in conn.sock.sent if m.startswith("INVITE")]
        self.assertEqual(len(invites), 3, conn.sock.sent)
        self.assertIn('nonce="N1"', invites[1])
        self.assertIn('nonce="N2"', invites[2])
        self.assertIn("Proxy-Authorization", invites[2])
        self.assertIn("stale=true", frames[1].decode())

    def test_bounded_exhaustion_gives_up_after_three_rounds(self) -> None:
        frames = [
            challenge_frame("401 Unauthorized", "N1", "WWW-Authenticate"),
            challenge_frame("407 stale", "N2", "Proxy-Authenticate", stale=True),
            challenge_frame("407 stale", "N3", "Proxy-Authenticate", stale=True),
            challenge_frame("407 stale", "N4", "Proxy-Authenticate", stale=True),
        ]
        conn = make_connection(frames)
        call(conn, "2000", 0.0, 407)
        invites = [m for m in conn.sock.sent if m.startswith("INVITE")]
        self.assertEqual(len(invites), 4, "1 initial + 3 bounded rounds")
        # Bounded at 3 rounds: the 4th challenge (N4) arrives but the
        # client gives up WITHOUT digesting it — the final response is
        # the raw 407 and the last SENT digest was over N3.
        self.assertIn('nonce="N3"', invites[3])
        self.assertNotIn('nonce="N4"', "".join(invites))


if __name__ == "__main__":
    unittest.main()
