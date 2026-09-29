#!/usr/bin/env python3
"""Telnyx trunk vantage probe: can calls be placed FROM this machine's IP?

Places a real outbound INVITE to a target number (by default your own DID —
success then rings only your own ring group) against sip.telnyx.com with the
trunk's digest credentials, riding Telnyx's nonce re-challenge roulette
until a verdict:

  exit 0  SUCCESS        (provisional -> CANCEL, or answered 200 -> BYE)
  exit 2  BLOCKED_403    (Telnyx rejected the AUTHED invite: IP screening /
                          account policy — the datacenter-IP signature)
  exit 3  UNEXPECTED     (final response neither 1xx/2xx/407/401)
  exit 4  AUTH_LOOP      (6 challenges, never accepted or blocked)

The nonce roulette needs up to ~5 authed attempts; mod_sofia only tolerates
ONE re-challenge, which is why a probe verdict of SUCCESS does not imply a
FreeSWITCH gateway can complete the same dance.

Usage (credentials never on the command line):

  PW=$(cat <trunk-password-file>) TELNYX_TRUNK_USER=<user> \
    python3 tests/vantage_probe.py --did +15550100000

Run from DIFFERENT machines to map which source IPs Telnyx accepts. NB:
SIP-ALG routers rewrite the Via received= parameter — treat it as ALG
noise, not as the public vantage IP (locked-down LANs also block HTTP echo
services, hence no self-IP lookup here).
"""

import argparse
import hashlib
import os
import re
import socket
import sys
import time

parser = argparse.ArgumentParser(description="Telnyx trunk vantage probe")
parser.add_argument(
    "--did", required=True, help="target E.164 number (usually your own DID)"
)
parser.add_argument(
    "--user",
    default=os.environ.get("TELNYX_TRUNK_USER", ""),
    help="trunk auth username (default: $TELNYX_TRUNK_USER)",
)
parser.add_argument(
    "--pw",
    default=os.environ.get("PW", ""),
    help="trunk password (default: $PW; prefer the env over this flag)",
)
args = parser.parse_args()

SERVER, PORT, DOMAIN = "sip.telnyx.com", 5060, "sip.telnyx.com"
USER = args.user
PW = args.pw
FROM, TO = (
    args.did,
    args.did,
)  # own DID by default: success rings only the own ring group
egress = "pending (see received= below)"
if not PW:
    sys.exit("PW missing (set $PW or pass --pw)")
if not USER:
    sys.exit("trunk user missing (set $TELNYX_TRUNK_USER or pass --user)")

sdp = "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=p\r\nc=IN IP4 127.0.0.1\r\nt=0 0\r\nm=audio 9 RTP/AVP 0\r\na=rtpmap:0 PCMU/8000\r\n"
cid = f"vp-{int(time.time())}@probe"
n = [0]


def mk(method, uri, extra="", cseq=1):
    n[0] += 1
    body = sdp if method == "INVITE" else ""
    return (
        f"{method} {uri} SIP/2.0\r\nVia: SIP/2.0/TCP 127.0.0.1:9{n[0] % 10}{n[0] % 7};branch=z9hG4bKv{n[0]}\r\n"
        f"From: <sip:{FROM}@{DOMAIN}>;tag=vt{n[0]}\r\nTo: <sip:{TO}@{DOMAIN}>\r\nCall-ID: {cid}\r\n"
        f"CSeq: {cseq} {method}\r\nContact: <sip:{FROM}@127.0.0.1:9{n[0] % 10}{n[0] % 7};transport=tcp>\r\nMax-Forwards: 70\r\nContent-Type: application/sdp\r\n"
        f"Content-Length: {len(body)}\r\n{extra}\r\n{body}"
    )


def read_final(sock, secs=20):
    sock.settimeout(secs)
    buf = b""
    statuses = []
    auth = ""
    end = time.time() + secs
    while time.time() < end:
        try:
            c = sock.recv(4096)
            if not c:
                break
            buf += c
        except TimeoutError:
            break
        while True:
            he = buf.find(b"\r\n\r\n")
            if he < 0:
                break
            head = buf[:he].decode(errors="replace")
            m = re.search(r"Content-Length:\s*(\d+)", head)
            cl = int(m.group(1)) if m else 0
            if len(buf) < he + 4 + cl:
                break
            msg = head
            buf = buf[he + 4 + cl :]
            statuses += [l for l in msg.split("\r\n") if l.startswith("SIP/2.0")]
            for l in msg.split("\r\n"):
                if l.lower().startswith("via:") and "received=" in l:
                    print(
                        f"[probe] Telnyx saw source IP: {l.split('received=')[1].split(';')[0].strip()}"
                    )
            for line in msg.split("\r\n"):
                if line.lower().startswith(
                    ("proxy-authenticate:", "www-authenticate:")
                ):
                    auth = line
            if statuses and int(statuses[-1].split()[1]) >= 200:
                return statuses[-1], statuses, auth
    return (statuses[-1] if statuses else "NONE"), statuses, auth


sock = socket.create_connection((SERVER, PORT), timeout=20)
uri = f"sip:{TO}@{DOMAIN}"
final = ""
auth = ""
for attempt, cseq in enumerate(range(1, 7), start=1):
    extra = ""
    if auth:
        realm = re.search(r'realm="([^"]+)"', auth).group(1)
        nonce = re.search(r'nonce="([^"]+)"', auth).group(1)
        cn = hashlib.md5(f"cn{time.time()}".encode()).hexdigest()[:16]
        resp = hashlib.md5(
            f"{hashlib.md5(f'{USER}:{realm}:{PW}'.encode()).hexdigest()}:{nonce}:00000001:{cn}:auth:{hashlib.md5(f'INVITE:{uri}'.encode()).hexdigest()}".encode()
        ).hexdigest()
        extra = (
            f'Proxy-Authorization: Digest username="{USER}",realm="{realm}",nonce="{nonce}",uri="{uri}",'
            f'response="{resp}",algorithm=MD5,qop=auth,nc=00000001,cnonce="{cn}"\r\n'
        )
    sock.sendall(mk("INVITE", uri, extra, cseq).encode())
    final, statuses, auth2 = read_final(sock)
    print(f"[probe] attempt {attempt}: {statuses}")
    if final.startswith("SIP/2.0 403"):
        print(f"[probe] VERDICT: BLOCKED_403 from {egress}")
        sys.exit(2)
    if final.startswith("SIP/2.0 1"):
        sock.sendall(mk("CANCEL", uri, cseq=cseq).encode())
        print("[probe] VERDICT: SUCCESS (provisional, cancelled)")
        sys.exit(0)
    if final.startswith("SIP/2.0 2"):
        sock.sendall(mk("ACK", uri, cseq=cseq).encode())
        time.sleep(0.3)
        sock.sendall(mk("BYE", uri, cseq=cseq + 1).encode())
        print("[probe] VERDICT: SUCCESS (answered 200, BYE sent)")
        sys.exit(0)
    if not final.startswith(("SIP/2.0 407", "SIP/2.0 401")):
        print(f"[probe] VERDICT: UNEXPECTED final {final} from {egress}")
        sys.exit(3)
    auth = auth2 or auth
print(
    f"[probe] VERDICT: AUTH_LOOP (6 challenges, never accepted/blocked) from {egress}"
)
sys.exit(4)
