"""Reconcile a Telnyx account against a desired-state JSON file.

Generic engine for deployments of the telephony module that ride a
Telnyx trunk + messaging: it idempotently converges the four API
mutations a deployment otherwise clicks through the portal:

  1. an FQDN connection (TCP) for inbound voice. Deliberately WITHOUT an
     outbound voice profile until the outbound-auth leg is configured:
     Telnyx refuses OVP assignment on an FQDN connection whose outbound
     leg is not fully configured (error 10015). When outbound keys are
     present in the desired state they ride NESTED under the connection's
     `outbound` object, and the authentication method is set BEFORE the
     profile is attached (a flat outbound_voice_profile_id PATCH is
     silently ignored; wrong order 422s "must be fully configured") —
     hence two calls, never one.
  2. an FQDN record pointing Telnyx INVITEs at <fqdn>:<port>,
  3. the DID moved onto that connection (inbound routing),
  4. the messaging profile's webhook_url aimed at the messaging bridge
     receiver (services.telephony.messaging).

The desired state lives with the DEPLOYMENT, never in this public repo
(DIDs, domains and resource ids are deployment facts). Expected shape,
all keys required (see REQUIRED_DESIRED_KEYS):

    {
      "connection_name": "...",        # inbound FQDN connection name
      "transport_protocol": "TCP",
      "fqdn": "pbx.example.com",
      "fqdn_port": 5080,
      "dns_record_type": "A",
      "phone_number": "+1555...",
      "messaging_profile_name": "...",
      "webhook_url": "https://pbx.example.com/telnyx/webhooks",
      "mms_transcoding": true,          # let Telnyx resize oversized MMS
      "outbound_authentication_method": "ip-authentication",
      "outbound_voice_profile_id": "..."
    }

Usage:

    python3 scripts/telnyx_reconcile.py --desired desired.json           # dry-run
    python3 scripts/telnyx_reconcile.py --desired desired.json --apply   # execute

API key resolution order: --api-key-file, then the TELNYX_API_KEY
environment variable. The key is never printed or logged. In a dry-run,
--drift-exit-code exits 2 on drift (CI gate: 0 = converged, 1 = fatal,
2 = drift).
"""

import argparse
import json
import os
import socket
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.telnyx.com/v2"
HTTP_TIMEOUT = 20

# Loaded from the --desired JSON before any planning (see load_desired);
# tests assign it directly. None means "not loaded" — every consumer
# fails loudly on that.
DESIRED = None

REQUIRED_DESIRED_KEYS = [
    "connection_name",
    "transport_protocol",
    "fqdn",
    "fqdn_port",
    "dns_record_type",
    "phone_number",
    "messaging_profile_name",
    "webhook_url",
    "mms_transcoding",
    "outbound_authentication_method",
    "outbound_voice_profile_id",
]


def load_desired(path):
    """Load and validate the desired-state JSON, setting the module global."""
    global DESIRED
    with open(path) as handle:
        desired = json.load(handle)
    missing = [key for key in REQUIRED_DESIRED_KEYS if key not in desired]
    if missing:
        raise ReconcileError(
            f"{path}: desired state is missing key(s): {', '.join(missing)}"
        )
    DESIRED = desired
    return desired


class ReconcileError(Exception):
    """Fatal planning error: the account cannot carry the desired state."""


class TelnyxClient:
    """Thin stdlib HTTP client for the Telnyx V2 API.

    `sender` is injectable so tests can script responses without network.
    """

    def __init__(self, api_key, base=API_BASE, sender=None):
        self.api_key = api_key
        self.base = base
        if sender is None:
            sender = self._http_sender
        self.sender = sender

    def _http_sender(self, method, path, body):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            payload = error.read().decode(errors="replace")
            try:
                payload = json.dumps(json.loads(payload))
            except ValueError:
                pass
            return error.code, {"error": payload}

    def _request(self, method, path, body=None):
        status, payload = self.sender(method, path, body)
        if status >= 400:
            excerpt = json.dumps(payload)
            if len(excerpt) > 400:
                excerpt = excerpt[:400] + "…"
            raise ReconcileError(f"{method} {path} -> HTTP {status}: {excerpt}")
        return payload.get("data", payload)

    def get(self, path):
        return self._request("GET", path)

    def post(self, path, body):
        return self._request("POST", path, body)

    def patch(self, path, body):
        return self._request("PATCH", path, body)


class State:
    """Everything the planner needs, fetched read-only in discover()."""

    def __init__(self):
        self.fqdn_connection = None
        self.fqdn_records = []
        self.number = None
        self.messaging_profile = None


def discover(client):
    state = State()
    connections = client.get("/connections?page[size]=100")
    state.fqdn_connection = next(
        (
            record
            for record in connections
            if record.get("record_type") == "fqdn_connection"
            and record.get("connection_name") == DESIRED["connection_name"]
        ),
        None,
    )
    if state.fqdn_connection is not None:
        # The mixed /connections list is a summary view (transport_protocol
        # comes back null there); the dedicated endpoint is authoritative.
        state.fqdn_connection = client.get(
            f"/fqdn_connections/{state.fqdn_connection['id']}"
        )
    # NB: /fqdns returns connection_id as a NUMBER while /connections
    # returns id as a STRING — compare through str() or records vanish.
    connection_id = (
        str(state.fqdn_connection.get("id")) if state.fqdn_connection else None
    )
    state.fqdn_records = [
        record
        for record in client.get("/fqdns?page[size]=100")
        if connection_id is None or str(record.get("connection_id")) == connection_id
    ]
    numbers = client.get("/phone_numbers?page[size]=100")
    state.number = next(
        (
            record
            for record in numbers
            if record.get("phone_number") == DESIRED["phone_number"]
        ),
        None,
    )
    if state.number is None:
        raise ReconcileError(
            f"phone number {DESIRED['phone_number']} not found in the account "
            "(ordering a number is out of scope)"
        )
    profiles = client.get("/messaging_profiles?page[size]=100")
    state.messaging_profile = next(
        (
            record
            for record in profiles
            if record.get("name") == DESIRED["messaging_profile_name"]
        ),
        None,
    )
    return state


class Step:
    """One planned mutation. describe() is printed; apply() runs it."""

    def __init__(self, verb, detail, apply):
        self.verb = verb
        self.detail = detail
        self.apply = apply


def outbound_drift(connection):
    """Outbound-origination drift as {api_key: (current, wanted)}.

    The fields are nested under the connection's `outbound` object (a flat
    PATCH of `outbound_voice_profile_id` is accepted and silently ignored —
    burned 2026-09-21), so they are read and written through that object.
    """
    current = connection.get("outbound") or {}
    wanted = {
        "fqdn_authentication_method": DESIRED["outbound_authentication_method"],
        "outbound_voice_profile_id": DESIRED["outbound_voice_profile_id"],
    }
    return {
        key: (current.get(key), value)
        for key, value in wanted.items()
        if current.get(key) != value
    }


def build_plan(state):
    steps = []
    desired_connection = {
        "connection_name": DESIRED["connection_name"],
        "transport_protocol": DESIRED["transport_protocol"],
        "active": True,
    }

    def outbound_step(nested):
        """One step per key, applied in order, each in its own PATCH.

        Telnyx 422s ("must be fully configured") when the voice profile is
        attached before the authentication method, so the verified
        2026-09-21 two-call procedure is what gets replayed here.
        """

        def patch_outbound(client, state):
            connection_id = state.fqdn_connection["id"]
            for key in ("fqdn_authentication_method", "outbound_voice_profile_id"):
                if key in nested:
                    client.patch(
                        f"/fqdn_connections/{connection_id}",
                        {"outbound": {key: nested[key][1]}},
                    )

        summary = ", ".join(
            f"outbound.{key}: {current!r} -> {wanted!r}"
            for key, (current, wanted) in nested.items()
        )
        return Step("PATCH fqdn_connection outbound", summary, patch_outbound)

    connection = state.fqdn_connection

    if connection is None:

        def create_connection(client, state):
            created = client.post(
                "/fqdn_connections",
                desired_connection,
            )
            state.fqdn_connection = created
            return f"connection id {created.get('id')}"

        steps.append(
            Step(
                "CREATE fqdn_connection",
                f"{DESIRED['connection_name']} ({DESIRED['transport_protocol']}, "
                "inbound-only, no OVP)",
                create_connection,
            )
        )
        # A freshly created connection never carries outbound origination,
        # so the plan always attaches it next (auth first, profile second).
        steps.append(
            outbound_step(
                {
                    "fqdn_authentication_method": (
                        None,
                        DESIRED["outbound_authentication_method"],
                    ),
                    "outbound_voice_profile_id": (
                        None,
                        DESIRED["outbound_voice_profile_id"],
                    ),
                }
            )
        )
    else:
        drift = {
            key: (connection.get(key), value)
            for key, value in desired_connection.items()
            if connection.get(key) != value
        }
        if drift:
            summary = ", ".join(
                f"{key}: {current!r} -> {wanted!r}"
                for key, (current, wanted) in drift.items()
            )

            def patch_connection(client, state, drift=drift):
                client.patch(
                    f"/fqdn_connections/{state.fqdn_connection['id']}",
                    {key: wanted for key, (_, wanted) in drift.items()},
                )

            steps.append(
                Step(
                    "PATCH fqdn_connection",
                    f"{DESIRED['connection_name']}: {summary}",
                    patch_connection,
                )
            )

        nested = outbound_drift(connection)
        if nested:
            steps.append(outbound_step(nested))

    def connection_id(state):
        if state.fqdn_connection is None:
            raise ReconcileError("internal: fqdn connection missing at apply time")
        return state.fqdn_connection["id"]

    record = next(
        (
            record
            for record in state.fqdn_records
            if record.get("fqdn") == DESIRED["fqdn"]
        ),
        None,
    )
    if record is None:

        def create_fqdn(client, state):
            created = client.post(
                "/fqdns",
                {
                    "fqdn": DESIRED["fqdn"],
                    "port": DESIRED["fqdn_port"],
                    "dns_record_type": DESIRED["dns_record_type"],
                    "connection_id": connection_id(state),
                },
            )
            state.fqdn_records.append(created)
            return f"fqdn record id {created.get('id')}"

        steps.append(
            Step(
                "CREATE fqdn",
                f"{DESIRED['fqdn']}:{DESIRED['fqdn_port']} "
                f"({DESIRED['dns_record_type']}) on {DESIRED['connection_name']}",
                create_fqdn,
            )
        )
    else:
        drift = {}
        if record.get("port") != DESIRED["fqdn_port"]:
            drift["port"] = (record.get("port"), DESIRED["fqdn_port"])
        current_connection = record.get("connection_id")
        if connection is None:
            # The connection is being created this run; any existing record
            # for this fqdn sits on a foreign connection and must move.
            if current_connection is not None:
                drift["connection_id"] = (current_connection, None)
        elif current_connection is not None and str(current_connection) != str(
            connection["id"]
        ):
            drift["connection_id"] = (current_connection, connection["id"])
        if drift:
            summary = ", ".join(
                f"{key}: {current!r} -> {wanted!r}"
                for key, (current, wanted) in drift.items()
            )

            def patch_fqdn(client, state):
                body = {key: wanted for key, (_, wanted) in drift.items()}
                if "connection_id" in drift and body["connection_id"] is None:
                    body["connection_id"] = connection_id(state)
                client.patch(f"/fqdns/{record['id']}", body)

            steps.append(
                Step(
                    "PATCH fqdn",
                    f"{DESIRED['fqdn']}: {summary}",
                    patch_fqdn,
                )
            )

    number_needs_move = connection is None or (
        str(state.number.get("connection_id")) != str(connection["id"])
    )
    if number_needs_move:

        def move_number(client, state):
            client.patch(
                f"/phone_numbers/{state.number['id']}",
                {"connection_id": connection_id(state)},
            )
            return f"{DESIRED['phone_number']} -> {DESIRED['connection_name']}"

        steps.append(
            Step(
                "PATCH phone_number",
                f"{DESIRED['phone_number']} inbound routing "
                f"{state.number.get('connection_id')!r} -> {DESIRED['connection_name']}",
                move_number,
            )
        )

    profile = state.messaging_profile
    if profile is None:

        def create_profile(client, state):
            created = client.post(
                "/messaging_profiles",
                {
                    "name": DESIRED["messaging_profile_name"],
                    "webhook_url": DESIRED["webhook_url"],
                    "webhook_api_version": "2",
                    "mms_transcoding": DESIRED["mms_transcoding"],
                    "enabled": True,
                },
            )
            client.patch(
                f"/phone_numbers/{state.number['id']}",
                {"messaging_profile_id": created["id"]},
            )
            return f"profile id {created.get('id')}"

        steps.append(
            Step(
                "CREATE messaging_profile",
                f"{DESIRED['messaging_profile_name']} -> {DESIRED['webhook_url']} "
                f"+ attach {DESIRED['phone_number']}",
                create_profile,
            )
        )
    else:
        profile_drift = {}
        if profile.get("webhook_url") != DESIRED["webhook_url"]:
            profile_drift["webhook_url"] = (
                profile.get("webhook_url"),
                DESIRED["webhook_url"],
            )
        if profile.get("enabled") is False:
            profile_drift["enabled"] = (False, True)
        if profile.get("mms_transcoding") is not DESIRED["mms_transcoding"]:
            profile_drift["mms_transcoding"] = (
                profile.get("mms_transcoding"),
                DESIRED["mms_transcoding"],
            )
        if state.number.get("messaging_profile_id") != profile.get("id"):
            profile_drift["__attach_number"] = (
                state.number.get("messaging_profile_id"),
                profile.get("id"),
            )
        if profile_drift:
            summary = ", ".join(
                f"{key}: {current!r} -> {wanted!r}"
                for key, (current, wanted) in profile_drift.items()
            )

            def patch_profile(client, state):
                body = {
                    key: wanted
                    for key, (_, wanted) in profile_drift.items()
                    if key != "__attach_number"
                }
                if body:
                    client.patch(f"/messaging_profiles/{profile['id']}", body)
                if "__attach_number" in profile_drift:
                    client.patch(
                        f"/phone_numbers/{state.number['id']}",
                        {"messaging_profile_id": profile["id"]},
                    )

            steps.append(
                Step(
                    "PATCH messaging_profile",
                    f"{DESIRED['messaging_profile_name']}: {summary}",
                    patch_profile,
                )
            )

    return steps


def preflight(client):
    """Fail fast on states no plan should run against."""
    try:
        socket.getaddrinfo(DESIRED["fqdn"], None, socket.AF_INET)
    except socket.gaierror as error:
        raise ReconcileError(f"{DESIRED['fqdn']} has no A record: {error}") from error
    try:
        ipv6 = socket.getaddrinfo(DESIRED["fqdn"], None, socket.AF_INET6)
    except socket.gaierror:
        ipv6 = []
    return ipv6


def load_api_key(path):
    if path and os.path.isfile(path):
        with open(path) as handle:
            key = handle.read().strip()
        if key:
            return key, path
    env_key = os.environ.get("TELNYX_API_KEY", "").strip()
    if env_key:
        return env_key, "$TELNYX_API_KEY"
    raise ReconcileError(
        f"no API key: {f'--api-key-file {path}' if path else 'no --api-key-file given'} "
        "is missing/empty and TELNYX_API_KEY is unset (mint a V2 key in the "
        "Telnyx portal)"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--desired",
        required=True,
        help="path to the deployment's desired-state JSON (see module docstring)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="execute the plan (default: dry-run, read-only)",
    )
    parser.add_argument(
        "--api-key-file",
        default=None,
        help="path to the Telnyx V2 API key (falls back to $TELNYX_API_KEY)",
    )
    parser.add_argument(
        "--drift-exit-code",
        action="store_true",
        help="in a dry-run, exit 2 when the plan is non-empty (CI gate: 0 = converged, 1 = fatal, 2 = drift)",
    )
    args = parser.parse_args(argv)

    try:
        load_desired(args.desired)
        key, source = load_api_key(args.api_key_file)
        client = TelnyxClient(key)
        if args.apply:
            print(f"api key: {source}")
        ipv6 = preflight(client)
        if ipv6:
            print(
                f"WARN: {DESIRED['fqdn']} has an AAAA record but the server's "
                "static IPv6 is not pinned — Telnyx may route "
                "inbound over the dead IPv6 path."
            )
        state = discover(client)
        steps = build_plan(state)
        mode = "APPLY" if args.apply else "DRY-RUN"
        print(f"{mode}: {len(steps)} step(s)")
        for index, step in enumerate(steps, 1):
            print(f"  {index}. {step.verb}: {step.detail}")
        if not args.apply:
            if args.drift_exit_code and steps:
                print(
                    "drift detected — re-run with --apply (or fix the cause) "
                    "to converge"
                )
                return 2
            print("dry-run only — re-run with --apply to execute")
            return 0
        for index, step in enumerate(steps, 1):
            note = step.apply(client, state)
            print(
                f"DID  {index}. {step.verb}: {step.detail}"
                + (f" ({note})" if note else "")
            )
        print(
            f"converged: inbound {DESIRED['phone_number']} arrives at "
            f"{DESIRED['fqdn']}:{DESIRED['fqdn_port']} via "
            f"{DESIRED['connection_name']}; SMS webhooks -> {DESIRED['webhook_url']}"
        )
        return 0
    except ReconcileError as error:
        print(f"FATAL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
