#!/usr/bin/env python3
"""Loopback Gemini stub for the agent VM test (tests/agent.nix).

Serves the three Interactions-API shapes the voice agent calls, with
identical response envelopes to the sibling E2E stub
(tests/test_voice_agent_e2e.py):

  * speech (response_format audio)  -> output/content audio data b64 WAV
  * transcription (input audio)     -> output/content text
  * chat (text turns)               -> output/content text with an
                                       [ACTION: end] directive so the
                                       call terminates deterministically

Run standalone: python3 gemini_stub.py [port]  (default 8443, loopback).
"""

import base64
import json
import struct
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TRANSCRIPT_TEXT = "hello from the stubbed caller"
CHAT_REPLY = "This is the stubbed reply. [ACTION: end]"
SAMPLE_RATE = 8000


def tiny_wav(seconds: float = 0.4) -> bytes:
    data = b"\x00\x00" * int(SAMPLE_RATE * seconds)
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(data))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(data))
        + data
    )


WAV_BYTES = tiny_wav()
WAV_B64 = base64.b64encode(WAV_BYTES).decode()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")

        if "response_format" in body:
            payload = {
                "output": [
                    {
                        "content": [
                            {
                                "type": "audio",
                                "data": WAV_B64,
                                "mime_type": "audio/wav",
                            }
                        ]
                    }
                ]
            }
        else:
            text = None
            for step in body.get("input", []):
                for block in step.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "audio":
                        text = TRANSCRIPT_TEXT
            if text is None:
                text = CHAT_REPLY
            payload = {"output": [{"content": [{"type": "text", "text": text}]}]}

        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):
        sys.stderr.write("gemini-stub: " + (fmt % args) + "\n")


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"gemini-stub: listening on 127.0.0.1:{port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
