"""Unit tests for the operator API's SMS-store flattening
(packages/telephony-operator/api.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest tests.test_operator_sms

The bridge's receiver logs Telnyx events as envelope rows
({received_at, remote, body: {data: {event_type, payload}}}); the
operator window's SMS tab needs flat {from, to, body, channel} rows with
the WhatsApp channel rendered distinctly (type WHATSAPP in the payload).
These tests pin the flattening: envelope rows of both channels, the
Meta-style WhatsApp body text, non-message events skipped, legacy flat
rows passed through.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

API_PATH = (
    Path(__file__).resolve().parents[1] / "packages" / "telephony-operator" / "api.py"
)

spec = importlib.util.spec_from_file_location("telephony_operator_api", API_PATH)
assert spec is not None and spec.loader is not None, API_PATH
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class _Store:
    """CONFIG stand-in: parse_sms only reads CONFIG.sms_store."""

    def __init__(self, path):
        self.sms_store = str(path)


class SmsFlattenTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store_path = Path(self._tmp.name) / "inbound.jsonl"
        self.addCleanup(self._tmp.cleanup)

    def entries(self, lines):
        self.store_path.write_text("".join(line + "\n" for line in lines))
        api.CONFIG = _Store(self.store_path)
        return api.parse_sms(50)

    def envelope(self, event_type, payload):
        return json.dumps(
            {
                "received_at": "2026-09-30T12:00:00+00:00",
                "remote": "127.0.0.1",
                "body": {"data": {"event_type": event_type, "payload": payload}},
            }
        )

    def test_sms_envelope_flattened_with_sms_channel(self):
        rows = self.entries(
            [
                self.envelope(
                    "message.received",
                    {
                        "from": {"phone_number": "+15550001111"},
                        "to": [{"phone_number": "+15550002222"}],
                        "text": "plain sms",
                        "type": "SMS",
                    },
                )
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0],
            {
                "received_at": "2026-09-30T12:00:00+00:00",
                "from": "+15550001111",
                "to": "+15550002222",
                "body": "plain sms",
                "channel": "SMS",
            },
        )

    def test_whatsapp_envelope_carries_whatsapp_channel_and_body_text(self):
        rows = self.entries(
            [
                self.envelope(
                    "message.received",
                    {
                        "from": {"phone_number": "+15550003333"},
                        "to": "+15550002222",
                        "type": "WHATSAPP",
                        "body": {"type": "text", "text": {"body": "wa hello"}},
                    },
                )
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "WHATSAPP")
        self.assertEqual(rows[0]["body"], "wa hello")
        self.assertEqual(rows[0]["from"], "+15550003333")
        self.assertEqual(rows[0]["to"], "+15550002222")  # string-`to` tolerated

    def test_status_events_are_not_messages(self):
        rows = self.entries(
            [
                self.envelope(
                    "message.finalized",
                    {
                        "id": "out-1",
                        "to": [{"phone_number": "+15550002222", "status": "delivered"}],
                    },
                )
            ]
        )
        self.assertEqual(rows, [])

    def test_legacy_flat_rows_pass_through_with_channel(self):
        legacy = json.dumps(
            {
                "received_at": "2026-08-01T00:00:00+00:00",
                "from": "+15550001111",
                "to": "+15550002222",
                "body": "old shape",
            }
        )
        rows = self.entries([legacy])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "SMS")
        self.assertEqual(rows[0]["body"], "old shape")

    def test_newest_first_and_limit(self):
        lines = [
            self.envelope(
                "message.received",
                {"from": {"phone_number": f"+15550001{i:03d}"}, "text": f"m{i}"},
            )
            for i in range(4)
        ]
        rows = self.entries(lines)
        self.assertEqual([row["from"] for row in rows][0], "+15550001003")
        api.CONFIG = _Store(self.store_path)
        self.assertEqual(len(api.parse_sms(2)), 2)


if __name__ == "__main__":
    unittest.main()
