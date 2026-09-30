#!/usr/bin/env python3
"""WhatsApp lane smoke probe: one real round trip through the deployment.

Sends a WhatsApp text FROM the deployment's WhatsApp number TO your
personal number via the Telnyx WhatsApp API (the same POST
/v2/messages/whatsapp the bridge rides), then waits for you to reply and
watches the bridge receiver's /recent log for the inbound event. A
nonce in the sent text makes the echo match unambiguous (no stale-event
false positives).

Verdict table + exit codes (the vantage-probe contract):

  exit 0  ROUND_TRIP    send accepted, nonce-matched WHATSAPP echo seen
  exit 2  SEND_FAILED   Telnyx refused the send (24 h window closed /
                         40008 template catch-all, or auth)
  exit 3  NO_ECHO       send accepted but no matching inbound event
                         within the await window
  exit 4  UNREACHABLE   the bridge receiver never answered /recent

The thread tag: the bridge tags inbound WhatsApp senders
`whatsapp+<number>` (both directions collapse to one webphone thread);
the probe PRINTS the expected tag — the raw receiver log cannot prove
the webphone store row, the whatsapp+ derivation is pinned by the
bridge unit tests instead.

Usage (credentials never on the command line):

  TELNYX_API_KEY=$(cat <key-file) TELNYX_WEBHOOK_TOKEN=$(cat <token-file) \
    python3 tests/whatsapp_probe.py \
      --from +15550100001 --to +4917012345678 \
      --bridge https://pbx.example.com --await 300
"""

import argparse
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser(description="WhatsApp lane smoke probe")
parser.add_argument("--from", dest="from_number", required=True, help="the deployment's WhatsApp DID (E164)")
parser.add_argument("--to", dest="to_number", required=True, help="your personal number (E164) — reply to the probe text")
parser.add_argument("--bridge", required=True, help="deployment base URL (https://…)")
parser.add_argument("--await", dest="await_secs", type=int, default=300, help="seconds to wait for your reply (default 300)")
parser.add_argument("--api-key", default=os.environ.get("TELNYX_API_KEY", ""), help="Telnyx V2 key (default: $TELNYX_API_KEY; prefer the env)")
parser.add_argument("--token", default=os.environ.get("TELNYX_WEBHOOK_TOKEN", ""), help="bridge receiver token (default: $TELNYX_WEBHOOK_TOKEN)")
args = parser.parse_args()

API = "https://api.telnyx.com/v2/messages/whatsapp"
TIMEOUT = 20

if not args.api_key:
    sys.exit("API key missing (set $TELNYX_API_KEY or pass --api-key)")
if not args.token:
    sys.exit("receiver token missing (set $TELNYX_WEBHOOK_TOKEN or pass --token)")

nonce = secrets.token_hex(4)
text = f"smoke probe {nonce} — please reply with any message"
expected_tag = "whatsapp+" + args.to_number.lstrip("+")


def verdicts(rows):
    width = max(len(name) for name, _ in rows)
    for name, value in rows:
        print(f"  {name.ljust(width)}  {value}")


def recent_entries():
    request = urllib.request.Request(  # nosec B310 - operator-supplied deployment URL
        f"{args.bridge}/telnyx/webhooks/recent?limit=50",
        headers={"Authorization": f"Bearer {args.token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response).get("entries", [])
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        print(f"[probe] bridge /recent unreachable: {error}")
        verdicts(
            [
                ("send", "not attempted"),
                ("echo", "not attempted"),
                ("thread tag (expected)", expected_tag),
                ("verdict", "UNREACHABLE"),
            ]
        )
        sys.exit(4)


# 1. Outbound send via the same API the bridge rides (spec-verified
#    WhatsappMessage shape: from, to, whatsapp_message{type,text{body}}).
body = json.dumps(
    {
        "from": f"+{args.from_number.lstrip('+')}",
        "to": f"+{args.to_number.lstrip('+')}",
        "whatsapp_message": {
            "type": "text",
            "text": {"body": text, "preview_url": False},
        },
    }
).encode()
request = urllib.request.Request(  # nosec B310 - Telnyx API URL, constant above
    API,
    data=body,
    headers={"Authorization": f"Bearer {args.api_key}", "Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        payload = json.load(response)
        provider_ref = payload.get("data", {}).get("id", "?")
except urllib.error.HTTPError as error:
    detail = error.read().decode(errors="replace")[:300]
    print(f"[probe] send refused: HTTP {error.code}: {detail}")
    verdicts(
        [
            ("send", f"FAILED (HTTP {error.code})"),
            ("echo", "not attempted"),
            ("thread tag (expected)", expected_tag),
            ("verdict", "SEND_FAILED"),
        ]
    )
    sys.exit(2)
except (urllib.error.URLError, TimeoutError) as error:
    print(f"[probe] send transport failure: {error}")
    sys.exit(3)

print(f"[probe] sent {nonce} to {args.to_number} (provider ref {provider_ref})")

# 2. Await the human echo: poll /recent for a WHATSAPP message.received
#    from the personal number whose text/body mentions the nonce.
deadline = time.time() + args.await_secs
match = None
while time.time() < deadline:
    for entry in recent_entries():
        event = entry.get("body", {}).get("data", {})
        if event.get("event_type") != "message.received":
            continue
        payload = event.get("payload", {})
        sender = payload.get("from")
        sender = sender.get("phone_number") if isinstance(sender, dict) else sender
        if sender != f"+{args.to_number.lstrip('+')}":
            continue
        if str(payload.get("type", "")).upper() != "WHATSAPP":
            continue
        haystack = json.dumps(payload)
        if nonce in haystack:
            match = payload
            break
    if match:
        break
    remaining = int(deadline - time.time())
    print(f"[probe] awaiting your reply … {remaining}s (reply on WhatsApp to {args.from_number})")
    time.sleep(min(15, max(2, args.await_secs / 20)))

if not match:
    verdicts(
        [
            ("send", f"accepted ({provider_ref})"),
            ("echo", f"NOT seen within {args.await_secs}s"),
            ("thread tag (expected)", expected_tag),
            ("verdict", "NO_ECHO"),
        ]
    )
    sys.exit(3)

verdicts(
    [
        ("send", f"accepted ({provider_ref})"),
        ("echo", f"nonce-matched WHATSAPP event at {time.strftime('%H:%M:%S')}"),
        ("thread tag (expected)", expected_tag),
        ("verdict", "ROUND_TRIP"),
    ]
)
print("[probe] the webphone thread for this peer must show the tag above (pinned by the bridge unit tests)")
sys.exit(0)
