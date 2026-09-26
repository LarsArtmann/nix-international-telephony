"""Unit tests for the Telnyx reconciler (scripts/telnyx_reconcile.py).

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest tests.test_telnyx_reconcile

A scripted sender stands in for the Telnyx V2 API: every test plays canned
responses keyed by (method, path) and records mutations for assertions. No
network is touched (the DNS preflight is monkeypatched out where needed).
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

RECONCILER_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "telnyx_reconcile.py"
)

spec = importlib.util.spec_from_file_location("telnyx_reconcile", RECONCILER_PATH)
reconcile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reconcile)

# The engine loads its desired state from the --desired JSON in production
# (load_desired); tests pin a neutral in-memory desired state instead.
reconcile.DESIRED = {
    "connection_name": "example-pbx-fqdn",
    "transport_protocol": "TCP",
    "fqdn": "pbx.example.test",
    "fqdn_port": 5080,
    "dns_record_type": "A",
    "phone_number": "+15550100000",
    "messaging_profile_name": "example-pbx-sms",
    "webhook_url": "https://pbx.example.test/telnyx/webhooks",
    "mms_transcoding": True,
    "outbound_authentication_method": "ip-authentication",
    "outbound_voice_profile_id": "1234567890123456789",
}

CREATED_CONNECTION_ID = "9001000000000000001"
NUMBER_ID = "3040070019414230591"
PROFILE_ID = "4001a061-b2aa-4a58-8f98-a0c7cb45acde"
CREDENTIAL_CONNECTION_ID = "3037275614705878285"


class FakeTelnyx:
    """Scripted API responses + a log of every mutation attempt."""

    def __init__(self, connections, fqdns, number, profiles, fail_paths=None):
        self.fail_paths = fail_paths or {}
        self.log = []
        self.store = {
            "GET /connections?page[size]=100": {"data": connections},
            "GET /fqdns?page[size]=100": {"data": fqdns},
            "GET /phone_numbers?page[size]=100": {"data": [number]},
            "GET /messaging_profiles?page[size]=100": {"data": profiles},
        }
        self.number = number
        self.profiles = profiles
        self.created_ids = iter(
            [CREATED_CONNECTION_ID, "9002000000000000002", PROFILE_ID]
        )
        for record in connections:
            if record.get("record_type") == "fqdn_connection":
                # The mixed /connections list is a summary view...
                record["transport_protocol"] = None
                # ...the dedicated endpoint returns the full record.
                self.store[f"GET /fqdn_connections/{record['id']}"] = {
                    "data": dict(record, transport_protocol="TCP")
                }

    def __call__(self, method, path, body):
        key = f"{method} {path}"
        if key in self.fail_paths:
            status, payload = self.fail_paths[key]
            return status, payload
        if method == "GET" and key in self.store:
            return 200, self.store[key]
        if path.startswith(("/fqdn_connections/", "/fqdns/")):
            if method == "PATCH":
                self.log.append((method, path, body))
                return 200, {"data": {"id": "patched"}}
            raise AssertionError(f"unexpected {key}")
        if method in ("POST", "PATCH"):
            self.log.append((method, path, body))
            if method == "POST":
                return 200, {"data": {"id": next(self.created_ids), **body}}
            return 200, {"data": {"id": "patched"}}
        if key in self.store:
            return 200, self.store[key]
        raise AssertionError(f"unscripted request: {key}")


def credential_connection():
    return {
        "id": CREDENTIAL_CONNECTION_ID,
        "record_type": "credential_connection",
        "connection_name": "example-pbx-trial",
        "active": True,
    }


def number_record(connection_id=CREDENTIAL_CONNECTION_ID, profile_id=PROFILE_ID):
    return {
        "id": NUMBER_ID,
        "record_type": "phone_number",
        "phone_number": reconcile.DESIRED["phone_number"],
        "connection_id": connection_id,
        "messaging_profile_id": profile_id,
        "status": "active",
    }


def fqdn_connection_record(outbound=None):
    # Models the REAL API: connection ids are strings here...
    return {
        "id": CREATED_CONNECTION_ID,
        "record_type": "fqdn_connection",
        "connection_name": reconcile.DESIRED["connection_name"],
        "transport_protocol": reconcile.DESIRED["transport_protocol"],
        "active": True,
        # Converged outbound origination (nested, exactly as the API returns
        # it) unless a test overrides it to plant drift.
        "outbound": (
            outbound
            if outbound is not None
            else {
                "fqdn_authentication_method": reconcile.DESIRED[
                    "outbound_authentication_method"
                ],
                "outbound_voice_profile_id": reconcile.DESIRED[
                    "outbound_voice_profile_id"
                ],
            }
        ),
    }


def fqdn_record(port=None):
    # ...while /fqdns returns connection_id as an INT and dns_record_type
    # lowercase — the type skew the reconciler must survive (2026-09-21).
    return {
        "id": "9003000000000000003",
        "fqdn": reconcile.DESIRED["fqdn"],
        "port": port if port is not None else reconcile.DESIRED["fqdn_port"],
        "dns_record_type": reconcile.DESIRED["dns_record_type"].lower(),
        "connection_id": int(CREATED_CONNECTION_ID),
    }


def messaging_profile(webhook_url=None, enabled=True, mms_transcoding=True):
    return {
        "id": PROFILE_ID,
        "record_type": "messaging_profile",
        "name": reconcile.DESIRED["messaging_profile_name"],
        "webhook_url": webhook_url,
        "webhook_api_version": "2",
        "enabled": enabled,
        "mms_transcoding": mms_transcoding,
    }


class ReconcilerTests(unittest.TestCase):
    def run_plan(self, fake):
        client = reconcile.TelnyxClient("test-key", sender=fake)
        state = reconcile.discover(client)
        steps = reconcile.build_plan(state)
        for step in steps:
            step.apply(client, state)
        return steps

    def test_clean_state_plans_five_steps_in_order(self):
        fake = FakeTelnyx(
            connections=[credential_connection()],
            fqdns=[],
            number=number_record(),
            profiles=[messaging_profile()],
        )
        client = reconcile.TelnyxClient("test-key", sender=fake)
        state = reconcile.discover(client)
        steps = reconcile.build_plan(state)
        verbs = [step.verb for step in steps]
        self.assertEqual(
            verbs,
            [
                "CREATE fqdn_connection",
                "PATCH fqdn_connection outbound",
                "CREATE fqdn",
                "PATCH phone_number",
                "PATCH messaging_profile",
            ],
        )
        self.assertIn("webhook_url: None ->", steps[4].detail)

    def test_outbound_drift_plans_two_ordered_patches(self):
        # 2026-09-21 burned twice by hand: the fields are nested under
        # `outbound`, and the OVP must be attached AFTER the auth method or
        # Telnyx 422s "must be fully configured".
        fake = FakeTelnyx(
            connections=[
                credential_connection(),
                fqdn_connection_record(outbound={}),
            ],
            fqdns=[fqdn_record()],
            number=number_record(connection_id=CREATED_CONNECTION_ID),
            profiles=[messaging_profile(webhook_url=reconcile.DESIRED["webhook_url"])],
        )
        steps = self.run_plan(fake)
        self.assertEqual(
            [step.verb for step in steps], ["PATCH fqdn_connection outbound"]
        )
        self.assertIn("outbound.fqdn_authentication_method", steps[0].detail)
        patches = [body for method, path, body in fake.log if method == "PATCH"]
        self.assertEqual(
            [body["outbound"] for body in patches],
            [
                {"fqdn_authentication_method": "ip-authentication"},
                {"outbound_voice_profile_id": "1234567890123456789"},
            ],
        )

    def test_fresh_connection_attaches_outbound_to_the_created_id(self):
        fake = FakeTelnyx(
            connections=[credential_connection()],
            fqdns=[],
            number=number_record(),
            profiles=[messaging_profile(webhook_url=reconcile.DESIRED["webhook_url"])],
        )
        steps = self.run_plan(fake)
        self.assertEqual(
            [step.verb for step in steps][:2],
            ["CREATE fqdn_connection", "PATCH fqdn_connection outbound"],
        )
        outbound_patches = [
            (path, body)
            for method, path, body in fake.log
            if method == "PATCH" and "outbound" in body
        ]
        self.assertEqual(len(outbound_patches), 2)
        for path, _ in outbound_patches:
            self.assertIn(CREATED_CONNECTION_ID, path)

    def test_apply_wires_created_connection_into_followups(self):
        fake = FakeTelnyx(
            connections=[credential_connection()],
            fqdns=[],
            number=number_record(),
            profiles=[messaging_profile()],
        )
        steps = self.run_plan(fake)
        self.assertEqual(len(steps), 5)
        fqdn_create = next(b for m, p, b in fake.log if m == "POST" and p == "/fqdns")
        self.assertEqual(fqdn_create["connection_id"], CREATED_CONNECTION_ID)
        number_patch = next(
            b for m, p, b in fake.log if m == "PATCH" and "phone_numbers" in p
        )
        self.assertEqual(number_patch["connection_id"], CREATED_CONNECTION_ID)
        profile_patch = next(
            b for m, p, b in fake.log if m == "PATCH" and "messaging_profiles" in p
        )
        self.assertEqual(profile_patch["webhook_url"], reconcile.DESIRED["webhook_url"])

    def test_converged_state_is_a_no_op(self):
        fake = FakeTelnyx(
            connections=[credential_connection(), fqdn_connection_record()],
            fqdns=[fqdn_record()],
            number=number_record(connection_id=CREATED_CONNECTION_ID),
            profiles=[messaging_profile(webhook_url=reconcile.DESIRED["webhook_url"])],
        )
        steps = self.run_plan(fake)
        self.assertEqual(steps, [])
        self.assertEqual(fake.log, [])

    def test_transcoding_disabled_plans_profile_patch(self):
        # 2026-09-21: the live profile shipped with mms_transcoding off —
        # outbound MMS with phone-camera images would hit carrier limits
        # (600 KB safe, 1 MB hard) instead of being auto-resized.
        fake = FakeTelnyx(
            connections=[credential_connection(), fqdn_connection_record()],
            fqdns=[fqdn_record()],
            number=number_record(connection_id=CREATED_CONNECTION_ID),
            profiles=[
                messaging_profile(
                    webhook_url=reconcile.DESIRED["webhook_url"],
                    mms_transcoding=False,
                )
            ],
        )
        steps = self.run_plan(fake)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].verb, "PATCH messaging_profile")
        self.assertIn("mms_transcoding", steps[0].detail)
        method, _path, body = fake.log[0]
        self.assertEqual((method, body["mms_transcoding"]), ("PATCH", True))

    def test_wrong_port_fqdn_plans_patch(self):
        fake = FakeTelnyx(
            connections=[credential_connection(), fqdn_connection_record()],
            fqdns=[fqdn_record(port=5060)],
            number=number_record(connection_id=CREATED_CONNECTION_ID),
            profiles=[messaging_profile(webhook_url=reconcile.DESIRED["webhook_url"])],
        )
        steps = self.run_plan(fake)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].verb, "PATCH fqdn")
        method, _path, body = fake.log[0]
        self.assertEqual((method, body["port"]), ("PATCH", 5080))

    def test_missing_number_fails_discovery_without_mutations(self):
        fake = FakeTelnyx(
            connections=[credential_connection()],
            fqdns=[],
            number={
                "id": "123",
                "phone_number": "+15550000000",
                "connection_id": CREDENTIAL_CONNECTION_ID,
            },
            profiles=[messaging_profile()],
        )
        client = reconcile.TelnyxClient("test-key", sender=fake)
        with self.assertRaises(reconcile.ReconcileError):
            reconcile.discover(client)
        self.assertEqual(fake.log, [])

    def test_api_error_surfaces_status_and_body(self):
        fake = FakeTelnyx(
            connections=[credential_connection()],
            fqdns=[],
            number=number_record(),
            profiles=[messaging_profile()],
            fail_paths={
                "GET /connections?page[size]=100": (
                    401,
                    {"errors": [{"detail": "invalid api token"}]},
                )
            },
        )
        client = reconcile.TelnyxClient("test-key", sender=fake)
        with self.assertRaises(reconcile.ReconcileError) as caught:
            reconcile.discover(client)
        self.assertIn("HTTP 401", str(caught.exception))

    def test_drift_exit_code_gates_ci(self):
        # --drift-exit-code turns a non-empty dry-run plan into exit 2
        # (0 = converged, 1 = fatal, 2 = drift) so CI can gate on drift
        # without parsing stdout.
        fake = FakeTelnyx(
            connections=[credential_connection()],
            fqdns=[],
            number=number_record(),
            profiles=[messaging_profile()],  # webhook_url=None -> drift
        )
        backed = reconcile.TelnyxClient("test-key", sender=fake)
        originals = (
            reconcile.TelnyxClient,
            reconcile.load_api_key,
            reconcile.preflight,
        )
        try:
            reconcile.TelnyxClient = lambda key: backed
            reconcile.load_api_key = lambda path: ("test-key", path)
            reconcile.preflight = lambda client: []
            with tempfile.NamedTemporaryFile("w", suffix=".json") as desired_file:
                json.dump(reconcile.DESIRED, desired_file)
                desired_file.flush()
                self.assertEqual(
                    reconcile.main(
                        ["--desired", desired_file.name, "--drift-exit-code"]
                    ),
                    2,
                )
                self.assertEqual(reconcile.main(["--desired", desired_file.name]), 0)
        finally:
            (
                reconcile.TelnyxClient,
                reconcile.load_api_key,
                reconcile.preflight,
            ) = originals


if __name__ == "__main__":
    unittest.main()
