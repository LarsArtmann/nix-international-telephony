#!/usr/bin/env python3
"""Loopback Gemini stub for the textagent VM test (tests/textagent.nix).

Serves the Interactions-API text shape the text agent calls: a
draft-reply JSON object (reply/en_gloss/language/confidence) for
drafting prompts and a translate JSON object when the prompt carries
the translate marker. Every request is logged (JSONL) to --log so the
suite can assert WHAT was asked.

Run standalone: python3 textagent_gemini_stub.py [port] (default 8444,
loopback only).
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

parser = argparse.ArgumentParser(description="stub Gemini text API")
parser.add_argument("port", nargs="?", type=int, default=8444)
parser.add_argument("--log", default="/tmp/textagent-gemini-stub.jsonl")
args = parser.parse_args()

LOG = Path(args.log)

DRAFT_REPLY = (
    '{"reply": "Guten Morgen, die VM-Test-Antwort.", '
    '"en_gloss": "Good morning, the VM-test reply.", '
    '"language": "de", "confidence": 93}'
)
TRANSLATE_REPLY = '{"text": "ubersetzte VM-Test-Antwort"}'


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        prompt_text = ""
        for step in body.get("input", []) or []:
            for block in step.get("content", []) or []:
                prompt_text += str(block.get("text", ""))
        with LOG.open("a") as handle:
            handle.write(
                json.dumps(
                    {
                        "path": self.path,
                        "key": self.headers.get("x-goog-api-key"),
                        "system_instruction": body.get("system_instruction", ""),
                        "prompt": prompt_text,
                    }
                )
                + "\n"
            )
        text = (
            TRANSLATE_REPLY
            if "Translate this SMS draft" in prompt_text
            else DRAFT_REPLY
        )
        payload = {
            "output": {
                "content": [{"type": "text", "text": text}],
            }
        }
        encoded = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
