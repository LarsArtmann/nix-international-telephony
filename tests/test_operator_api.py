"""Unit tests for the hardened operator API (packages/telephony-operator/api.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest tests.test_operator_api

Covers the ESL client (inbound protocol against a fake FreeSWITCH on a
real loopback socket), the fixed public error texts and security
headers, newest-first CDR ordering, health derivation, JSONL robustness
and CSV formula-injection neutralisation.
"""

import argparse
import base64
import csv
import importlib.util
import json
import socketserver
import subprocess
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

API_PATH = Path(__file__).resolve().parents[1] / "packages" / "telephony-operator" / "api.py"

spec = importlib.util.spec_from_file_location("telephony_operator_api_hardened", API_PATH)
assert spec is not None and spec.loader is not None, API_PATH
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)


class _FakeFreeSwitchHandler(socketserver.StreamRequestHandler):
    """Speaks the inbound ESL protocol just enough for EslClient."""

    def _send_block(self, headers, body=b""):
        payload = "".join(f"{name}: {value}\r\n" for name, value in headers.items()) + "\r\n"
        self.wfile.write(payload.encode())
        if body:
            self.wfile.write(body)
        self.wfile.flush()

    def _read_block(self):
        headers = {}
        while True:
            line = self.rfile.readline()
            if not line or line in (b"\n", b"\r\n"):
                break
            text = line.decode().strip()
            if ":" in text:
                name, _, value = text.partition(":")
                headers[name.strip()] = value.strip()
            else:
                # command lines ("auth <pw>", "api <cmd>") carry no colon
                headers["command"] = text
        return headers

    def handle(self):
        state = self.server.state
        self._send_block({"Content-Type": "auth/request"})
        request = self._read_block()
        auth_line = request.get("command", "")
        if not auth_line.startswith("auth ") or auth_line[5:] != state.password:
            self._send_block({"Reply-Text": "-ERR invalid password"})
            return
        self._send_block({"Reply-Text": "+OK accepted"})
        while True:
            request = self._read_block()
            if not request:
                break
            command_line = request.get("command", "")
            state.commands.append(command_line)
            if not command_line.startswith("api "):
                break
            command = command_line[4:]
            if state.omit_content_length:
                state.omit_content_length = False
                self._send_block({"Content-Type": "api/response"})
                continue
            if state.bad_content_length:
                state.bad_content_length = False
                self._send_block({"Content-Type": "api/response", "Content-Length": "not-a-number"})
                continue
            if command.startswith("break-glass"):
                # no Content-Length and an early close: the client must
                # not hang waiting for a body it cannot size
                self._send_block({"Content-Type": "api/response"})
                break
            if command.startswith("usage"):
                body = b"-USAGE <uuid>\n"
            elif command.startswith("boom"):
                body = b"-ERR command refused\n"
            else:
                body = f"output of {command}\n".encode()
            self._send_block({"Content-Type": "api/response", "Content-Length": str(len(body))}, body)


class _FakeFreeSwitch(socketserver.ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, password):
        self.state = type(
            "State",
            (),
            {"password": password, "commands": [], "omit_content_length": False, "bad_content_length": False},
        )()
        super().__init__(("127.0.0.1", 0), _FakeFreeSwitchHandler)


class EslClientTest(unittest.TestCase):
    def setUp(self):
        self.password = "ClueCon-4242"
        self.server = _FakeFreeSwitch(self.password)
        self.port = self.server.server_address[1]
        import threading

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def client(self, password=None):
        return api.EslClient("127.0.0.1", self.port, password or self.password, timeout=5)

    def test_auth_succeeds_and_output_is_returned(self):
        out = self.client().api("sofia status")
        self.assertEqual(out, "output of sofia status\n")
        self.assertEqual(self.server.state.commands[-1], "api sofia status")

    def test_command_arrives_as_api_line(self):
        self.client().api("status")
        self.assertEqual(self.server.state.commands[-1], "api status")

    def test_wrong_password_raises_without_password_in_message(self):
        with self.assertRaises(api.EslError) as ctx:
            self.client(password="totally-wrong").api("status")
        self.assertIn("-ERR", str(ctx.exception))
        self.assertNotIn("totally-wrong", str(ctx.exception))

    def test_err_body_raises_with_text_and_no_password(self):
        with self.assertRaises(api.EslError) as ctx:
            self.client().api("boom")
        self.assertIn("-ERR command refused", str(ctx.exception))
        self.assertNotIn(self.password, str(ctx.exception))
        self.assertEqual(ctx.exception.reply, "-ERR command refused")

    def test_a_usage_error_is_a_refusal_too(self):
        with self.assertRaises(api.EslError) as ctx:
            self.client().api("usage")
        self.assertTrue(ctx.exception.reply.startswith("-USAGE"), ctx.exception.reply)

    def test_missing_content_length_raises_fixed_message(self):
        self.server.state.omit_content_length = True
        with self.assertRaises(api.EslError) as ctx:
            self.client().api("break-glass")
        self.assertEqual(str(ctx.exception), "event socket reply has no valid content length")
        self.assertNotIn(self.password, str(ctx.exception))

    def test_non_integer_content_length_raises_fixed_message(self):
        self.server.state.bad_content_length = True
        with self.assertRaises(api.EslError) as ctx:
            self.client().api("status")
        self.assertEqual(str(ctx.exception), "event socket reply has no valid content length")

    def test_refused_connection_raises_fixed_message(self):
        closed_server = _FakeFreeSwitch(self.password)
        closed_port = closed_server.server_address[1]
        closed_server.server_close()
        client = api.EslClient("127.0.0.1", closed_port, self.password, timeout=5)
        with self.assertRaises(api.EslError) as ctx:
            client.api("status")
        self.assertEqual(str(ctx.exception), "event socket connection failed")

    def test_fs_cli_cmd_uses_esl_and_not_a_subprocess(self):
        config = api.ApiConfig(
            argparse.Namespace(
                port=0,
                domain="pbx.example",
                esl_password_file="unused",
                esl_host="127.0.0.1",
                esl_port=self.port,
                stream_token_secret_file=None,
                cdr_file="unused",
                fs_root="/tmp",
                voicemail_db="unused",
                dialplan_dir="unused",
                sms_store=None,
                tls_cert_file=None,
                unit="",
            )
        )
        config.esl_password = self.password
        with mock.patch.object(subprocess, "run") as run:
            out = config.fs_cli_cmd("sofia status")
        run.assert_not_called()
        self.assertEqual(out, "output of sofia status\n")


class _ConfigStandIn:
    """CONFIG stand-in with injectable ESL answers and unit list."""

    def __init__(self, esl_answers=None, units=(), cdr_file=None, sms_store=None):
        self.esl_answers = esl_answers or {}
        self.units = list(units)
        self.cdr_file = cdr_file
        self.sms_store = sms_store
        self.tls_cert_file = None
        self.voicemail_db = "/nonexistent/voicemail.db"

    def fs_cli_cmd(self, command, timeout=10):
        for needle, answer in self.esl_answers.items():
            if command.startswith(needle):
                return answer
        return ""


class HealthReportTest(unittest.TestCase):
    def test_ok_false_when_any_card_is_not_ok(self):
        api.CONFIG = _ConfigStandIn(
            esl_answers={
                "sofia status gateway": "State: REGED",
                "sofia status": "header line one\nheader line two\n"
                "name profile desc RUNNING 0 0\ngw1 gateway REGED 0 0\n",
            },
            units=["freeswitch.service"],
        )
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = type("Proc", (), {"stdout": "active\n", "returncode": 0})()
            report = api.health_report()
        self.assertTrue(report["ok"])

        # no gateways at all: the gateway card reads "empty", not ok
        api.CONFIG = _ConfigStandIn(
            esl_answers={"sofia status": "header line one\nheader line two\nname profile desc RUNNING 0 0\n"},
            units=["freeswitch.service"],
        )
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = type("Proc", (), {"stdout": "active\n", "returncode": 0})()
            report = api.health_report()
        self.assertEqual(report["checks"]["gateways"]["state"], "empty")
        # no gateway configured is a valid shape, not a degraded host
        self.assertTrue(report["ok"])

        # a gateway that lost its registration degrades the headline
        api.CONFIG = _ConfigStandIn(
            esl_answers={
                "sofia status gateway": "State: FAIL_WAIT",
                "sofia status": "header line one\nheader line two\n"
                "name profile desc RUNNING 0 0\ngw1 gateway NOREG 0 0\n",
            },
            units=["freeswitch.service"],
        )
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = type("Proc", (), {"stdout": "active\n", "returncode": 0})()
            report = api.health_report()
        self.assertEqual(report["checks"]["gateways"]["state"], "degraded")
        self.assertFalse(report["ok"])

        # a failed unit degrades the headline with every card ok
        api.CONFIG = _ConfigStandIn(
            esl_answers={
                "sofia status gateway": "State: REGED",
                "sofia status": "header line one\nheader line two\n"
                "name profile desc RUNNING 0 0\ngw1 gateway REGED 0 0\n",
            },
            units=["freeswitch.service"],
        )
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = type("Proc", (), {"stdout": "failed\n", "returncode": 3})()
            report = api.health_report()
        self.assertEqual(report["checks"]["units"]["state"], "degraded")
        self.assertFalse(report["ok"])

        # a degraded profile flips the headline even with the unit active
        api.CONFIG = _ConfigStandIn(
            esl_answers={
                "sofia status": "header line one\nheader line two\nname profile desc FAILING 0 0\n",
                "sofia status gateway": "State: REGED",
            },
            units=["freeswitch.service"],
        )
        with mock.patch.object(subprocess, "run") as run:
            run.return_value = type("Proc", (), {"stdout": "active\n", "returncode": 0})()
            report = api.health_report()
        self.assertFalse(report["ok"])


class CdrOrderTest(unittest.TestCase):
    FIELDS = api.CDR_FIELDS_13

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "Master.csv"

    def row(self, stamp, number, account, uuid):
        return [
            "Caller",
            number,
            "1002",
            "default",
            stamp,
            "",
            stamp,
            "60",
            "60",
            "NORMAL_CLEARING",
            uuid,
            "",
            account,
        ]

    def write(self, rows):
        with open(self.path, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh, quoting=csv.QUOTE_ALL).writerows(rows)
        api.CONFIG = _ConfigStandIn(cdr_file=str(self.path))

    def test_newest_first_with_offset_and_filters_before_limit(self):
        rows = [
            self.row("2026-01-01 10:00:00", "1000", "1002", "u1"),
            self.row("2026-01-02 10:00:00", "1000", "2001", "u2"),
            self.row("2026-01-03 10:00:00", "1000", "1002", "u3"),
            self.row("2026-01-05 09:00:00", "1000", "1002", "u4a"),
            self.row("2026-01-05 09:00:00", "1000", "1002", "u4b"),
        ]
        self.write(rows)
        page, more = api.read_cdr_rows(50)
        self.assertEqual([r["uuid"] for r in page], ["u4b", "u4a", "u3", "u2", "u1"])
        self.assertFalse(more)

        page, more = api.read_cdr_rows(2)
        self.assertEqual([r["uuid"] for r in page], ["u4b", "u4a"])
        self.assertTrue(more)

        page, _more = api.read_cdr_rows(2, offset=2)
        self.assertEqual([r["uuid"] for r in page], ["u3", "u2"])

        # filters apply before limit+offset: the 2 newest rows matching
        # account 1002, not 2 of the newest overall
        page, _more = api.read_cdr_rows(2, number_filter="1002")
        self.assertEqual([r["uuid"] for r in page], ["u4b", "u4a"])
        page, _more = api.read_cdr_rows(2, number_filter="2001")
        self.assertEqual([r["uuid"] for r in page], ["u2"])

        page, _more = api.read_cdr_rows(50, since="2026-01-03")
        self.assertEqual([r["uuid"] for r in page], ["u4b", "u4a", "u3"])

        page, _more = api.read_cdr_rows(2, since="2026-01-03", offset=1)
        self.assertEqual([r["uuid"] for r in page], ["u4a", "u3"])

    def test_history_of_a_quiet_extension_survives_a_busy_host(self):
        # account 2001 has ONE call, written first; four newer calls of
        # another account follow. The extension's history must still find
        # its call (the filter runs before the limit).
        self.write(
            [
                self.row("2026-01-01 10:00:00", "1000", "2001", "mine"),
                self.row("2026-01-02 10:00:00", "1000", "1002", "o1"),
                self.row("2026-01-03 10:00:00", "1000", "1002", "o2"),
                self.row("2026-01-04 10:00:00", "1000", "1002", "o3"),
                self.row("2026-01-05 10:00:00", "1000", "1002", "o4"),
            ]
        )
        page, more = api.read_cdr_rows(1, accountcode="2001")
        self.assertEqual([r["uuid"] for r in page], ["mine"])
        self.assertFalse(more)
        page, _more = api.read_cdr_rows(2, accountcode="1002")
        self.assertEqual([r["uuid"] for r in page], ["o4", "o3"])


class VoicemailRefusalMappingTest(unittest.TestCase):
    """A message mod_voicemail refuses is "not found"; only transport and
    protocol trouble is a 502."""

    def post_voicemail(self, raised):
        handler = object.__new__(api.Handler)
        handler.path = "/phone-api/voicemail/1002/messages/abc/read"
        sent = []
        handler.send_json = lambda status, payload: sent.append((status, payload))
        handler.auth_result = lambda: ("1002", None)
        config = _ConfigStandIn()
        config.domain = "pbx.example"

        def refusing(command, timeout=10):
            raise raised

        config.fs_cli_cmd = refusing
        message = [{"uuid": "abc", "read": False}]
        with mock.patch.object(api, "CONFIG", config), mock.patch.object(api, "voicemail_rows", return_value=message):
            handler.route_post()
        return sent

    def test_a_refused_command_answers_404_with_the_reply(self):
        sent = self.post_voicemail(
            api.EslError("event socket refused the command: -ERR no message", reply="-ERR no message")
        )
        self.assertEqual(sent, [(404, {"error": "-ERR no message"})])

    def test_a_transport_failure_answers_502_with_a_fixed_text(self):
        sent = self.post_voicemail(api.EslError("event socket timed out"))
        self.assertEqual(sent, [(502, {"error": "voicemail update failed"})])


class ParseSmsRobustnessTest(unittest.TestCase):
    def test_non_object_lines_are_skipped(self):
        store = Path(tempfile.mkdtemp()) / "inbound.jsonl"
        store.write_text(
            "[1, 2, 3]\n"
            '"just a string"\n'
            "42\n"
            + json.dumps(
                {
                    "received_at": "2026-09-30T12:00:00+00:00",
                    "from": "+15550001111",
                    "to": "+15550002222",
                    "body": "real",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        api.CONFIG = _ConfigStandIn(sms_store=str(store))
        rows = api.parse_sms(50)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["body"], "real")


class CsvFormulaInjectionTest(unittest.TestCase):
    def test_dangerous_leading_characters_get_an_apostrophe(self):
        for value in ("=cmd", " +1", "-2", "@import", "\ttotal", "\rbreak", " normal"):
            safe = api._csv_cell(value)
            if value.lstrip()[:1] in ("=", "+", "-", "@", "\t", "\r"):
                self.assertEqual(safe, "'" + value)
            else:
                self.assertEqual(safe, value)


class HandlerSecurityHeadersTest(unittest.TestCase):
    """Drives the real Handler over a loopback HTTP connection."""

    def setUp(self):
        import threading

        self.httpd = api.ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.httpd.server_close)
        api.OIDC = None
        api.OPERATOR_WEBROOT = None

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def test_every_response_carries_nosniff_and_no_referrer(self):
        status, headers, _ = self.get("/definitely/not/here")
        self.assertEqual(status, 404)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("Referrer-Policy"), "no-referrer")

    def test_healthz_answers_503_starting_when_config_is_none(self):
        api.CONFIG = None
        try:
            status, headers, body = self.get("/healthz")
        finally:
            api.CONFIG = _ConfigStandIn()
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body), {"status": "starting"})
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")

    def test_internal_error_body_is_fixed_text(self):
        api.CONFIG = None

        class Exploding(api.Handler):
            def route_get(self):
                raise RuntimeError("secret internals leaked here")

        self.httpd.RequestHandlerClass = Exploding
        try:
            with urllib.request.urlopen(self.base + "/api/cdr") as response:
                status, body = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, body = error.code, error.read()
        finally:
            self.httpd.RequestHandlerClass = api.Handler
            api.CONFIG = _ConfigStandIn()
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body), {"error": "internal error"})
        self.assertNotIn(b"secret internals", body)

    def test_access_log_redacts_query_string(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        api.CONFIG = None
        try:
            with redirect_stdout(buffer):
                try:
                    self.get("/api/cdr?limit=5&t=streamtoken123&code=abc")
                except Exception:  # noqa: BLE001 - the 401/503 body is irrelevant here
                    pass
        finally:
            api.CONFIG = _ConfigStandIn()
        log = buffer.getvalue()
        self.assertNotIn("streamtoken123", log)
        self.assertNotIn("code=abc", log)
        self.assertIn("?<redacted>", log)
        self.assertIn("/api/cdr", log)


class NonAsciiPasswordAuthTest(unittest.TestCase):
    """compare_digest on str raises TypeError for non-ASCII input; the
    byte comparison must turn such a password into a plain failed
    attempt inside the brute-force damper."""

    def config_with_directory_password(self, directory_password):
        config = api.ApiConfig(
            argparse.Namespace(
                port=0,
                domain="pbx.example",
                esl_password_file="unused",
                esl_host="127.0.0.1",
                esl_port=8021,
                stream_token_secret_file=None,
                cdr_file="unused",
                fs_root="/tmp",
                voicemail_db="unused",
                dialplan_dir="unused",
                sms_store=None,
                tls_cert_file=None,
                unit="",
            )
        )
        config.fs_cli_cmd = lambda command, timeout=10: directory_password
        return config

    def test_non_ascii_mismatch_counts_as_failed_attempt(self):
        config = self.config_with_directory_password("ClueCon")
        ok, retry_after = config.auth_gate("1002", "pässwörd")
        self.assertFalse(ok)
        self.assertEqual(retry_after, 0)
        self.assertEqual(config._auth_fails["1002"][0], 1)

    def test_non_ascii_match_authenticates(self):
        config = self.config_with_directory_password("pässwörd")
        ok, retry_after = config.auth_gate("1002", "pässwörd")
        self.assertTrue(ok)
        self.assertEqual(retry_after, 0)


class BasicAuthHeaderTest(unittest.TestCase):
    def test_parse_basic_auth_round_trip(self):
        header = "Basic " + base64.b64encode(b"1002:secret").decode()
        self.assertEqual(api.parse_basic_auth(header), ("1002", "secret"))


if __name__ == "__main__":
    unittest.main()
