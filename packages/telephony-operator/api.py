"""telephony-operator read-model API.

A stdlib-only HTTP service that renders PBX runtime state for two
consumers:

* the webphone's voicemail/history panels (/phone-api/... — authenticated
  per extension with the extension's own SIP credentials, verified
  through FreeSWITCH's directory), and
* the operator window (/api/... — basic-auth gated by nginx before the
  request ever reaches this service; loopback bind, proxied only).

It is a WINDOW, never an editor: the only state-changing operation is
deleting a voicemail message, which is delegated to mod_voicemail's own
vm_delete API (DB row + file removed by FreeSWITCH itself, MWI
invalidated correctly).

Endpoints (all JSON unless noted):
  GET  /healthz                                   liveness (no auth)
  GET  /api/health                                operator: profiles, gateways, units, cert
  GET  /api/cdr?limit&number&since                operator: call detail records
  GET  /api/sms?limit                             operator: SMS store (if configured)
  GET  /api/simulate?dest&when&var&ivr-input      operator: dialplan dry run
  GET  /phone-api/voicemail/<ext>/summary         extension: MWI badge counts
  GET  /phone-api/voicemail/<ext>/messages        extension: message list
  GET  /phone-api/voicemail/<ext>/messages/<uuid>/audio[?t=<tok>&e=<exp>]
                                                    extension: WAV stream
  DELETE /phone-api/voicemail/<ext>/messages/<uuid>  extension: delete via vm_delete
  GET  /phone-api/history?limit                   extension: own CDR history
"""

import argparse
import base64
import csv
import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

MAX_JSON_BODY = 0  # this service never reads request bodies
AUTH_CACHE_TTL = 300
READ_LIMIT_DEFAULT = 50
READ_LIMIT_MAX = 500
EXT_RE = re.compile(r"^[0-9]{2,7}$")
UUID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# mod_cdr_csv "default" template (registered name), 13 quoted fields.
CDR_FIELDS_13 = [
    "caller_id_name",
    "caller_id_number",
    "destination_number",
    "context",
    "start_stamp",
    "answer_stamp",
    "end_stamp",
    "duration",
    "billsec",
    "hangup_cause",
    "uuid",
    "bleg_uuid",
    "accountcode",
]
# mod_cdr_csv compiled-in fallback (used when default-template named a
# template that does not exist — the pre-2026-09-16 generator shape).
CDR_FIELDS_18 = [
    "accountcode",
    "caller_id_number",
    "destination_number",
    "context",
    "caller_id",
    "channel_name",
    "bridge_channel",
    "last_app",
    "last_arg",
    "start_stamp",
    "answer_stamp",
    "end_stamp",
    "duration",
    "billsec",
    "hangup_cause",
    "amaflags",
    "uuid",
    "userfield",
]


class ApiConfig:
    def __init__(self, args):
        self.port = args.port
        self.domain = args.domain
        self.esl_password = None
        self.esl_password_file = args.esl_password_file
        self.fs_cli = args.fs_cli
        self.cdr_file = args.cdr_file
        self.fs_root = args.fs_root
        self.voicemail_db = args.voicemail_db
        self.dialplan_dir = args.dialplan_dir
        self.sms_store = args.sms_store
        self.tls_cert_file = args.tls_cert_file
        self.units = [u for u in args.unit.split(",") if u]
        self._auth_cache = {}

    def esl(self):
        if self.esl_password is None:
            with open(self.esl_password_file, encoding="utf-8") as fh:
                self.esl_password = fh.read().strip()
        return self.esl_password

    def fs_cli_cmd(self, command, timeout=10):
        """Run an fs_cli API command; return stdout or raise RuntimeError."""
        proc = subprocess.run(  # nosec B603 - fixed argv, no shell
            [self.fs_cli, "-p", self.esl(), "-x", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"fs_cli failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return proc.stdout

    def check_extension_auth(self, ext, password):
        """Verify an extension/password pair against the directory via ESL.

        The password compared is the SAME secret the webphone already
        holds (SIP registration credential); nothing new is minted.
        """
        key = hashlib.sha256(f"{ext}:{password}".encode()).hexdigest()
        now = time.monotonic()
        cached = self._auth_cache.get(key)
        if cached and cached > now:
            return True
        if cached is not None:
            del self._auth_cache[key]
        try:
            actual = self.fs_cli_cmd(f"user_data {ext}@{self.domain} param password").strip()
        except (RuntimeError, subprocess.TimeoutExpired):
            return False
        if not actual or not hmac.compare_digest(actual, password):
            return False
        self._auth_cache[key] = now + AUTH_CACHE_TTL
        return True

    def stream_token(self, ext, uuid, expiry):
        msg = f"{ext}:{uuid}:{expiry}".encode()
        return hmac.new(self.esl().encode(), msg, hashlib.sha256).hexdigest()[:32]


CONFIG = None  # set in main()


def parse_basic_auth(header):
    if not header or not header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:].strip()).decode("utf-8")
        user, _, password = decoded.partition(":")
    except (ValueError, UnicodeDecodeError):
        return None
    return user, password


def read_cdr_rows(limit, number_filter=None, since=None):
    """Parse Master.csv (either template shape) newest-last-file-first."""
    rows = []
    try:
        with open(CONFIG.cdr_file, encoding="utf-8", errors="replace", newline="") as fh:
            raw = list(csv.reader(fh))
    except FileNotFoundError:
        return []
    for line in raw:
        if not line or len(line) < 10:
            continue
        # Strip the ";" the compiled-in fallback template terminates with.
        line = [field.rstrip(";").strip('"') for field in line]
        if len(line) == len(CDR_FIELDS_13):
            shape = dict(zip(CDR_FIELDS_13, line))
        elif len(line) == len(CDR_FIELDS_18):
            shape = dict(zip(CDR_FIELDS_18, line))
        else:
            continue
        row = {
            "caller_id_number": shape.get("caller_id_number", ""),
            "destination_number": shape.get("destination_number", ""),
            "context": shape.get("context", ""),
            "start": shape.get("start_stamp", ""),
            "answer": shape.get("answer_stamp", ""),
            "end": shape.get("end_stamp", ""),
            "duration": _to_int(shape.get("duration")),
            "billsec": _to_int(shape.get("billsec")),
            "hangup_cause": shape.get("hangup_cause", ""),
            "uuid": shape.get("uuid", ""),
            "accountcode": shape.get("accountcode", ""),
        }
        if number_filter and not (
            number_filter in row["caller_id_number"]
            or number_filter in row["destination_number"]
            or number_filter in row["accountcode"]
        ):
            continue
        if since and row["start"] and row["start"] < since:
            continue
        uuid = row["uuid"]
        if uuid and row["destination_number"]:
            row["recording"] = f"/recordings/{uuid}_{row['destination_number']}.wav"
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def _to_int(value):
    try:
        return int(value or 0)
    except ValueError:
        return 0


def voicemail_rows(ext):
    """Message rows for one mailbox, newest first (read-only DB open)."""
    if not os.path.exists(CONFIG.voicemail_db):
        raise RuntimeError("voicemail database not present yet")
    conn = sqlite3.connect(f"file:{CONFIG.voicemail_db}?mode=ro", uri=True, timeout=5)
    try:
        cur = conn.execute(
            "select created_epoch, read_epoch, uuid, cid_name, cid_number,"
            " file_path, message_len, read_flags from voicemail_msgs"
            " where username = ? and in_folder = 'INBOX'"
            " order by created_epoch desc",
            (ext,),
        )
        rows = [
            {
                "created": r[0],
                "read": bool(r[1]),
                "uuid": r[2],
                "cid_name": r[3],
                "cid_number": r[4],
                "file_path": r[5],
                "seconds": r[6],
                "read_flags": r[7],
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()
    return rows


def parse_sms(limit):
    if not CONFIG.sms_store:
        return []
    try:
        with open(CONFIG.sms_store, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return []
    messages = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        messages.append(
            {
                "received_at": item.get("received_at", ""),
                "from": item.get("from", ""),
                "to": item.get("to", ""),
                "body": item.get("body", ""),
            }
        )
        if len(messages) >= limit:
            break
    return messages


def health_report():
    report = {"ok": True, "checks": {}}
    errors = []

    def check(name, fn):
        try:
            report["checks"][name] = fn()
        except Exception as exc:  # noqa: BLE001 - every probe is best-effort
            report["checks"][name] = {"state": "unavailable", "error": str(exc)[:200]}
            errors.append(name)

    def sofia_status():
        out = CONFIG.fs_cli_cmd("sofia status", timeout=8)
        profiles = {}
        for line in out.splitlines()[2:]:
            parts = line.split()
            if len(parts) >= 4 and parts[1] == "profile":
                profiles[parts[0]] = parts[3].split()[0]
        degraded = {n: s for n, s in profiles.items() if s != "RUNNING"}
        return {
            "state": "ok" if profiles and not degraded else "degraded",
            "profiles": profiles,
        }

    def gateways():
        out = CONFIG.fs_cli_cmd("sofia status", timeout=8)
        names = [line.split()[0] for line in out.splitlines() if " gateway " in line]
        states = {}
        for name in names:
            gw_out = CONFIG.fs_cli_cmd(f"sofia status gateway {name}", timeout=8)
            match = re.search(r"State:\s+(\S+)", gw_out)
            states[name] = match.group(1) if match else "UNKNOWN"
        bad = {n: s for n, s in states.items() if s not in ("REGED", "NOREG")}
        return {
            "state": "ok" if states and not bad else ("degraded" if bad else "empty"),
            "gateways": states,
        }

    def units():
        states = {}
        for unit in CONFIG.units:
            proc = subprocess.run(  # nosec B603 - fixed argv, no shell
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                timeout=5,
            )
            states[unit] = proc.stdout.strip() or "unknown"
        bad = {n: s for n, s in states.items() if s != "active"}
        return {"state": "ok" if not bad else "degraded", "units": states}

    def cert():
        if not CONFIG.tls_cert_file or not os.path.exists(CONFIG.tls_cert_file):
            return {"state": "unavailable"}
        proc = subprocess.run(  # nosec B603 - fixed argv, no shell
            ["openssl", "x509", "-enddate", "-noout", "-in", CONFIG.tls_cert_file],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return {"state": "unavailable"}
        _, _, value = proc.stdout.strip().partition("=")
        return {"state": "ok", "not_after": value}

    check("sofia_profiles", sofia_status)
    check("gateways", gateways)
    check("units", units)
    check("certificate", cert)
    report["ok"] = not errors
    return report


class Handler(BaseHTTPRequestHandler):
    server_version = "telephony-operator/0.1"

    def log_message(self, fmt, *args):
        print(f"{self.client_address[0]} {fmt % args}", flush=True)

    def send_json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except (FileNotFoundError, PermissionError):
            self.send_json(404, {"error": "audio not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "private, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    # --- auth helpers -----------------------------------------------------

    def authenticated_ext(self):
        auth = parse_basic_auth(self.headers.get("Authorization"))
        if not auth:
            return None
        ext, password = auth
        if not EXT_RE.match(ext):
            return None
        if CONFIG.check_extension_auth(ext, password):
            return ext
        return None

    def token_admitted(self, ext, uuid, query):
        token = (query.get("t") or [""])[0]
        expiry = _to_int((query.get("e") or ["0"])[0])
        if not token or expiry < time.time():
            return False
        expected = CONFIG.stream_token(ext, uuid, expiry)
        return hmac.compare_digest(expected, token)

    # --- routing ----------------------------------------------------------

    def do_GET(self):  # noqa: N802 - http.server naming
        try:
            self.route_get()
        except Exception as exc:  # noqa: BLE001 - one answer per request
            traceback.print_exc()
            self.send_json(500, {"error": f"internal error: {exc}"})

    def do_DELETE(self):  # noqa: N802 - http.server naming
        try:
            self.route_delete()
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.send_json(500, {"error": f"internal error: {exc}"})

    def route_get(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/healthz":
            self.send_json(200, {"ok": True})
            return

        if path == "/api/health":
            self.send_json(200, health_report())
            return

        if path == "/api/cdr":
            limit = min(_to_int((query.get("limit") or [READ_LIMIT_DEFAULT])[0]) or READ_LIMIT_DEFAULT, READ_LIMIT_MAX)
            rows = read_cdr_rows(
                limit,
                number_filter=(query.get("number") or [None])[0],
                since=(query.get("since") or [None])[0],
            )
            self.send_json(200, {"entries": rows})
            return

        if path == "/api/sms":
            limit = min(_to_int((query.get("limit") or [READ_LIMIT_DEFAULT])[0]) or READ_LIMIT_DEFAULT, READ_LIMIT_MAX)
            self.send_json(200, {"entries": parse_sms(limit)})
            return

        if path == "/api/simulate":
            self.api_simulate(query)
            return

        # Per-extension phone API.
        match = re.match(r"^/phone-api/voicemail/(\d+)(/.*)?$", path)
        if match:
            ext = match.group(1)
            rest = match.group(2) or ""
            authed = self.authenticated_ext()

            if rest in ("", "/") or rest == "/summary":
                if authed != ext:
                    self.unauthorized()
                    return
                rows = voicemail_rows(ext)
                self.send_json(
                    200,
                    {
                        "new": sum(1 for r in rows if not r["read"]),
                        "saved": sum(1 for r in rows if r["read"]),
                    },
                )
                return

            if rest == "/messages":
                if authed != ext:
                    self.unauthorized()
                    return
                rows = voicemail_rows(ext)
                expiry = int(time.time()) + 3600
                messages = []
                for row in rows:
                    messages.append(
                        {
                            "uuid": row["uuid"],
                            "created": row["created"],
                            "read": row["read"],
                            "cid_name": row["cid_name"],
                            "cid_number": row["cid_number"],
                            "seconds": row["seconds"],
                            "audio_url": f"/phone-api/voicemail/{ext}/messages/{row['uuid']}/audio"
                            f"?t={CONFIG.stream_token(ext, row['uuid'], expiry)}&e={expiry}",
                        }
                    )
                self.send_json(200, {"messages": messages})
                return

            audio = re.match(r"^/messages/([A-Za-z0-9_-]+)/audio$", rest)
            if audio:
                uuid = audio.group(1)
                if not (authed == ext or self.token_admitted(ext, uuid, query)):
                    self.unauthorized()
                    return
                rows = voicemail_rows(ext)
                file_path = next((r["file_path"] for r in rows if r["uuid"] == uuid), None)
                if not file_path:
                    self.send_json(404, {"error": "no such message"})
                    return
                # The DB carries FreeSWITCH's view (/var/lib/freeswitch/...);
                # this service reads the same tree via its read-only bind.
                local = file_path.replace("/var/lib/freeswitch/", CONFIG.fs_root, 1)
                if not os.path.abspath(local).startswith(CONFIG.fs_root):
                    self.send_json(404, {"error": "no such message"})
                    return
                self.send_file(local, "audio/wav")
                return

            self.send_json(404, {"error": "not found"})
            return

        if path == "/phone-api/history":
            authed = self.authenticated_ext()
            if not authed:
                self.unauthorized()
                return
            limit = min(_to_int((query.get("limit") or [READ_LIMIT_DEFAULT])[0]) or READ_LIMIT_DEFAULT, READ_LIMIT_MAX)
            rows = read_cdr_rows(limit * 4)
            mine = [r for r in rows if r["accountcode"] == authed][:limit]
            self.send_json(200, {"entries": mine})
            return

        self.send_json(404, {"error": "not found"})

    def api_simulate(self, query):
        dest = (query.get("dest") or [""])[0]
        if not dest or not re.match(r"^[0-9+*#]{1,20}$", dest):
            self.send_json(400, {"error": "dest must be a dialable number"})
            return
        when = (query.get("when") or [None])[0]
        variables = {
            "toll_allow": "domestic,local,international",
            **{k: v[0] for k, v in query.items() if k.startswith("var_")},
        }
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import dialplan_sim

        try:
            contexts = dialplan_sim.load_contexts_dir(CONFIG.dialplan_dir)
            result = dialplan_sim.simulate_from_query(
                contexts, dest, variables, when, (query.get("ivr-input") or [None])[0]
            )
        except Exception as exc:  # noqa: BLE001 - surface the simulator error
            self.send_json(500, {"error": f"simulation failed: {exc}"})
            return
        self.send_json(200, result)

    def route_delete(self):
        parsed = urlparse(self.path)
        match = re.match(r"^/phone-api/voicemail/(\d+)/messages/([A-Za-z0-9_-]+)$", parsed.path)
        if not match:
            self.send_json(404, {"error": "not found"})
            return
        ext, uuid = match.groups()
        if self.authenticated_ext() != ext:
            self.unauthorized()
            return
        try:
            out = CONFIG.fs_cli_cmd(f"vm_delete {ext}@{CONFIG.domain} {uuid}", timeout=15)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            self.send_json(502, {"error": f"voicemail delete failed: {exc}"})
            return
        if "-ERR" in out or "-USAGE" in out:
            self.send_json(404, {"error": out.strip()[:200]})
            return
        rows = voicemail_rows(ext)
        self.send_json(
            200,
            {
                "deleted": uuid,
                "new": sum(1 for r in rows if not r["read"]),
                "saved": sum(1 for r in rows if r["read"]),
            },
        )

    def unauthorized(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="pbx-phone-api"')
        self.send_header("Content-Type", "application/json")
        body = b'{"error": "unauthorized"}'
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="telephony-operator-api")
    parser.add_argument("--port", type=int, default=8071)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--esl-password-file", required=True)
    parser.add_argument("--fs-cli", default="fs_cli")
    parser.add_argument("--cdr-file", required=True)
    parser.add_argument("--fs-root", default="/var/lib/private/freeswitch")
    parser.add_argument("--voicemail-db", required=True)
    parser.add_argument("--dialplan-dir", required=True)
    parser.add_argument("--sms-store", default=None)
    parser.add_argument("--tls-cert-file", default=None)
    parser.add_argument(
        "--unit", default="freeswitch.service,nginx.service", help="comma-separated units in the health view"
    )
    args = parser.parse_args(argv)

    global CONFIG
    CONFIG = ApiConfig(args)
    CONFIG.esl()

    server = ThreadingHTTPServer(("127.0.0.1", CONFIG.port), Handler)
    print(f"telephony-operator-api listening on 127.0.0.1:{CONFIG.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
