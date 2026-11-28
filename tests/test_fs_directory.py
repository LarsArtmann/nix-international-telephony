"""Unit tests for the FreeSWITCH directory bridge
(modules/telephony/fs-directory.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -W error::ResourceWarning -m unittest tests.test_fs_directory

The bridge must answer every authenticated FreeSWITCH lookup with a
parsable directory document (real credentials or the not-found
fall-through), never drop the connection, and never let proxy
environment variables redirect the webphone lookup. These tests pin the
fail-closed behaviour against a real loopback webphone stub and a real
loopback client.
"""

import base64
import hashlib
import http.client
import importlib.util
import json
import os
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "modules", "telephony", "fs-directory.py"
)

SECRET = "s3cret-staging"
USER = "1001"
DOMAIN = "sip.example"
PASSWORD = "derived-password-1"


def basic_header(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


class _StubHandler(BaseHTTPRequestHandler):
    """Webphone stand-in: self.server.mode picks the answer shape."""

    server_version = "webphone-stub/1.0"

    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        mode = self.server.mode
        if mode == "dict":
            body = json.dumps({"credentials": [PASSWORD]}).encode()
            self._answer(200, body)
        elif mode == "list":
            self._answer(200, json.dumps([PASSWORD]).encode())
        elif mode == "oversize":
            # Larger than the bridge's 64 KiB read cap.
            self._answer(200, b'{"credentials": "' + b"x" * (64 * 1024) + b'"}')
        elif mode == "garbage":
            self.wfile.write(b"NOT-HTTP AT ALL\r\n\r\n")
            self.close_connection = True
        elif mode == "close":
            self.close_connection = True
        else:
            self._answer(500, b"{}")

    def _answer(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FsDirectoryTest(unittest.TestCase):
    def setUp(self):
        self.stub_server = ThreadingHTTPServer(("127.0.0.1", 0), _StubHandler)
        self.stub_server.mode = "dict"
        self.stub_thread = threading.Thread(
            target=self.stub_server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        self.stub_thread.start()
        self.addCleanup(self._stop_stub)
        self.module = self._load_bridge()

    def _stop_stub(self):
        self.stub_server.shutdown()
        self.stub_server.server_close()

    def _load_bridge(self, secret=SECRET, extra_env=None):
        """Fresh module per configuration: the module reads its whole
        configuration from the environment at import time."""
        credentials_dir = tempfile.mkdtemp(prefix="t12-creds-")
        self.addCleanup(shutil.rmtree, credentials_dir, True)
        with open(os.path.join(credentials_dir, "webphone_directory_secret"), "w") as handle:
            handle.write(secret)
        env = {
            "PORT": "0",
            "CREDENTIALS_DIRECTORY": credentials_dir,
            "WEBPHONE_URL": f"http://127.0.0.1:{self.stub_server.server_port}",
        }
        env.update(extra_env or {})
        spec = importlib.util.spec_from_file_location("fs_directory_under_test", MODULE_PATH)
        assert spec is not None and spec.loader is not None, MODULE_PATH
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, env, clear=True):
            spec.loader.exec_module(module)
        return module

    def _start_bridge(self, module):
        server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
        self.addCleanup(connection.close)
        return connection

    def directory_post(self, connection, body=None, authorization=None, content_length=None):
        """Hand-built POST: lets tests send negative, absent, or omitted
        Content-Length headers that http.client would never produce."""
        if body is None:
            body = b""
            if content_length is None:
                content_length = 0
        elif content_length is None:
            content_length = len(body)
        connection.putrequest("POST", "/fs-directory")
        connection.putheader("Host", "127.0.0.1")
        if authorization is not None:
            connection.putheader("Authorization", authorization)
        if content_length is not None:
            connection.putheader("Content-Length", str(content_length))
        connection.putheader("Content-Type", "application/x-www-form-urlencoded")
        connection.endheaders()
        if body:
            connection.send(body)
        return connection.getresponse()

    def form_body(self, user=USER, domain=DOMAIN):
        from urllib.parse import urlencode

        return urlencode({"user": user, "domain": domain}).encode()

    # --- defect 1: empty secret must authenticate nobody -----------------

    def test_authorized_rejects_empty_secret(self):
        module = self._load_bridge(secret="")
        self.assertFalse(module.authorized(basic_header("x", "")))
        self.assertFalse(module.authorized("Bearer "))

    def test_basic_with_empty_password_answers_401(self):
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), basic_header("x", ""))
        self.assertEqual(response.status, 401)
        response.read()

    def test_bearer_with_empty_token_answers_401(self):
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), "Bearer ")
        self.assertEqual(response.status, 401)
        response.read()

    # --- defect 2: bounded, dict-only webphone answer --------------------

    def test_query_webphone_rejects_non_dict_payloads(self):
        self.stub_server.mode = "list"
        self.assertIsNone(self.module.query_webphone(USER))

    def test_webphone_list_answers_not_found_document(self):
        self.stub_server.mode = "list"
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), basic_header("webphone", SECRET))
        self.assertEqual(response.status, 200)
        self.assertIn(b"<not-found/>", response.read())

    def test_oversize_webphone_body_answers_not_found(self):
        self.stub_server.mode = "oversize"
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), basic_header("webphone", SECRET))
        self.assertEqual(response.status, 200)
        self.assertIn(b"<not-found/>", response.read())

    def test_garbage_status_line_answers_not_found_and_keeps_serving(self):
        self.stub_server.mode = "garbage"
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), basic_header("webphone", SECRET))
        self.assertEqual(response.status, 200)
        self.assertIn(b"<not-found/>", response.read())
        # The bridge connection survives the failed upstream call.
        self.stub_server.mode = "dict"
        response = self.directory_post(connection, self.form_body(), basic_header("webphone", SECRET))
        self.assertEqual(response.status, 200)
        self.assertIn(PASSWORD.encode(), response.read())

    # --- defect 3: invalid UTF-8 credential ------------------------------

    def test_load_credential_invalid_utf8_returns_empty(self):
        credentials_dir = tempfile.mkdtemp(prefix="t12-creds-")
        self.addCleanup(shutil.rmtree, credentials_dir, True)
        with open(os.path.join(credentials_dir, "webphone_directory_secret"), "wb") as handle:
            handle.write(b"\xff\xfe\xfd binary")
        env = {
            "PORT": "0",
            "CREDENTIALS_DIRECTORY": credentials_dir,
            "WEBPHONE_URL": f"http://127.0.0.1:{self.stub_server.server_port}",
        }
        spec = importlib.util.spec_from_file_location("fs_directory_bad_creds", MODULE_PATH)
        assert spec is not None and spec.loader is not None, MODULE_PATH
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, env, clear=True):
            spec.loader.exec_module(module)
        self.assertEqual(module.DIRECTORY_SECRET, "")

    # --- defect 4: malformed request shapes ------------------------------

    def test_negative_content_length_answers_not_found_and_next_request_served(self):
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, None, basic_header("webphone", SECRET), content_length=-5)
        self.assertEqual(response.status, 200)
        self.assertIn(b"<not-found/>", response.read())
        # The bridge must still serve the next request on the connection.
        response = self.directory_post(connection, self.form_body(), basic_header("webphone", SECRET))
        self.assertEqual(response.status, 200)
        self.assertIn(PASSWORD.encode(), response.read())

    def test_no_body_answers_not_found_document(self):
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, None, basic_header("webphone", SECRET), content_length=0)
        self.assertEqual(response.status, 200)
        self.assertIn(b"<not-found/>", response.read())

    def test_non_integer_content_length_answers_not_found(self):
        connection = self._start_bridge(self.module)
        response = self.directory_post(
            connection, self.form_body(), basic_header("webphone", SECRET), content_length="bogus"
        )
        self.assertEqual(response.status, 200)
        self.assertIn(b"<not-found/>", response.read())

    # --- happy paths -----------------------------------------------------

    def test_valid_basic_auth_answers_directory_document(self):
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), basic_header("webphone", SECRET))
        self.assertEqual(response.status, 200)
        body = response.read()
        expected_a1 = hashlib.md5(f"{USER}:{DOMAIN}:{PASSWORD}".encode()).hexdigest()
        self.assertIn(f'value="{PASSWORD}"'.encode(), body)
        self.assertIn(f'value="{expected_a1}"'.encode(), body)

    def test_bearer_auth_answers_directory_document(self):
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), f"Bearer {SECRET}")
        self.assertEqual(response.status, 200)
        self.assertIn(PASSWORD.encode(), response.read())

    def test_wrong_secret_answers_401(self):
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), basic_header("webphone", "wrong"))
        self.assertEqual(response.status, 401)
        response.read()

    def test_unknown_path_answers_404(self):
        connection = self._start_bridge(self.module)
        connection.request("GET", "/other")
        response = connection.getresponse()
        self.assertEqual(response.status, 404)
        response.read()

    def test_health_answers_ok(self):
        connection = self._start_bridge(self.module)
        connection.request("GET", "/health")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read()), {"status": "ok"})

    # --- defect 6: proxy environment must not redirect the lookup -------

    def test_http_proxy_is_ignored_for_webphone_lookup(self):
        self.module = self._load_bridge(
            extra_env={"http_proxy": "http://127.0.0.1:1", "HTTP_PROXY": "http://127.0.0.1:1"}
        )
        connection = self._start_bridge(self.module)
        response = self.directory_post(connection, self.form_body(), basic_header("webphone", SECRET))
        self.assertEqual(response.status, 200)
        self.assertIn(PASSWORD.encode(), response.read())


# Module-level reference so static analysis sees the loaded module name
# as used; tests always load fresh copies per configuration.
fs_directory_reference = FsDirectoryTest


if __name__ == "__main__":
    unittest.main()
