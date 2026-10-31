"""Reconcile a Telnyx account against a desired-state JSON file.

Generic engine for deployments of the telephony module that ride a
Telnyx trunk + messaging: it idempotently converges the account's
mutable state a deployment would otherwise click through the portal —
the mandatory inbound core plus the OPTIONAL families (present key =
managed, absent = untouched, report-only lanes never mutate):

  1. an FQDN connection (TCP) for inbound voice, incl. its NESTED
     outbound leg (auth method set BEFORE the profile attaches — a flat
     outbound_voice_profile_id PATCH is silently ignored; wrong order
     422s "must be fully configured" — hence two calls, never one).
  2. an FQDN record pointing Telnyx INVITEs at <fqdn>:<port>,
  3. the DID moved onto that connection (inbound routing),
  4. the messaging profile's webhook_url aimed at the messaging bridge
     receiver (services.telephony.messaging),
  5. credential-connection voice profiles (the nested outbound PATCH —
     the lane the FreeSWITCH gateway actually authenticates as),
  6. OVP whitelisted destinations per profile (set-compared),
  7. the messaging profile's country allowlist + alpha sender,
  8. AI assistants present with pinned models (multi-entry, name+model),
  9. call-control application pins (id-keyed, report-only today),
  10. extra managed phone numbers (each onto a connection and/or
      messaging profile), and
  11. retired OVPs (report-only survivors — never destroyed).

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
      "outbound_voice_profile_id": "...",
      "whatsapp_did": "+1555...",        # OPTIONAL: assert this number is
                                         # registered on a WABA (embedded
                                         # signup + VOICE OTP are portal
                                         # steps the API cannot replay)
      "ai_assistants": [                 # OPTIONAL: AI assistants to keep
        {"name": "…", "model": "…"}     # present with the pinned model
      ],                                  # (missing assistant = report-only;
                                         # full config is taste, snapshotted
                                         # deployment-side, never reconciled)
      "call_control_applications": {     # OPTIONAL: app id -> pins (id-keyed:
        "3044…": {                       # apps may have no name; unknown id =
          "active": true,                # report-only). `active` is always
          "webhook_event_url":           # checked; the other two only when
            "https://…",                 # present (a console-side webhook
          "outbound_voice_profile_id":   # swap previously shipped invisibly;
            "…"                          # the OVP rides NESTED `outbound` in
        }                                 # the PATCH, same shape as the
      },                                  # credential-connection lane)
      "ovp_whitelisted_destinations": {  # OPTIONAL: OVP name -> ISO 3166-1
        "test-outbound": ["US", …]       # alpha-2 destination list (set-
      }                                   # compared; order is portal-cosmetic)
      "credential_connection_ovps": {    # OPTIONAL: credential connection
        "example-pbx-trial": "…id…"      # name -> outbound voice profile id
      },                                  # (nested `outbound` PATCH, live-proven)
      "messaging_profile_whitelisted_destinations":
        ["US", "CA", "DE"],              # OPTIONAL: alpha-2 SMS allowlist
                                         # (set-compared; order is portal-
                                         # cosmetic)
      "messaging_profile_alpha_sender": "Woolly",  # OPTIONAL: alpha identity
      "phone_numbers": {                 # OPTIONAL: extra managed DIDs (the
        "+441234567890": {               # core `phone_number` above stays the
          "connection": "…name…",        # primary row; each extra DID maps
          "messaging_profile":           # onto a connection (voice) and/or
            "…name…"                     # the messaging profile (SMS) by
        }                                 # NAME; a number the account does
      },                                  # not carry is report-only — ordering
                                          # a number stays out of scope)
      "retired_outbound_voice_profiles": # OPTIONAL: OVP names that should no
        ["old-profile"]                  # longer exist; live survivors surface
    }                                    # as report-only NOTICE steps (the
                                         # engine never deletes — the removal
                                         # stays owner-gated)
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
PAGE_SIZE = 100
# Loud stop for list pagination: a real account sits far below 5000
# objects per family; hitting the cap means the API stopped honouring
# page[number] and truncation must surface, never hide.
MAX_PAGES = 50

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
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:  # nosec B310 - Telnyx API URL, never file:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            payload = error.read().decode(errors="replace")
            try:
                payload = json.dumps(json.loads(payload))
            except ValueError:
                pass
            return error.code, {"error": payload}

    def _request_payload(self, method, path, body=None):
        status, payload = self.sender(method, path, body)
        if status >= 400:
            excerpt = json.dumps(payload)
            if len(excerpt) > 400:
                excerpt = excerpt[:400] + "…"
            raise ReconcileError(f"{method} {path} -> HTTP {status}: {excerpt}")
        return payload

    def _request(self, method, path, body=None):
        payload = self._request_payload(method, path, body)
        return payload.get("data", payload)

    def get(self, path):
        return self._request("GET", path)

    def get_list(self, path):
        """GET a list endpoint, following pagination until exhausted.

        Page 1 keeps the historical single-page URL (the suite's canned
        shapes key on it); pages 2+ append page[number]. Termination:
        meta.total_results when the API carries it, a short page when it
        does not, MAX_PAGES as the loud stop — a silently truncated
        discovery would hide every object past the first page.
        """
        records = []
        for number in range(1, MAX_PAGES + 1):
            url = f"{path}?page[size]={PAGE_SIZE}"
            if number > 1:
                url += f"&page[number]={number}"
            payload = self._request_payload("GET", url)
            data = payload.get("data")
            if not isinstance(data, list):
                raise ReconcileError(f"GET {path} -> non-list payload")
            records.extend(data)
            total = (payload.get("meta") or {}).get("total_results")
            if isinstance(total, int):
                if len(records) >= total:
                    return records
            elif len(data) < PAGE_SIZE:
                return records
        raise ReconcileError(
            f"GET {path}: pagination did not terminate within "
            f"{MAX_PAGES} pages"
        )

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
        self.phone_numbers = []
        self.connections = []
        self.messaging_profiles = []
        self.messaging_profile = None
        self.whatsapp_number = None
        self.assistants = []
        self.call_control_apps = []
        self.outbound_voice_profiles = []
        self.credential_connections = []


def discover(client):
    state = State()
    connections = client.get_list("/connections")
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
        for record in client.get_list("/fqdns")
        if connection_id is None or str(record.get("connection_id")) == connection_id
    ]
    numbers = client.get_list("/phone_numbers")
    state.phone_numbers = numbers
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
    profiles = client.get_list("/messaging_profiles")
    state.messaging_profile = next(
        (
            record
            for record in profiles
            if record.get("name") == DESIRED["messaging_profile_name"]
        ),
        None,
    )
    # WhatsApp lane (optional): one read-only list answers whether the
    # configured DID is registered on a WABA and enabled (spec-verified
    # WhatsappPhoneResponse shape: phone_number, enabled, status,
    # waba_id, coexistence_state, ...).
    if DESIRED.get("whatsapp_did"):
        whatsapp = client.get_list("/whatsapp/phone_numbers")
        state.whatsapp_number = next(
            (
                record
                for record in whatsapp
                if record.get("phone_number") == DESIRED["whatsapp_did"]
            ),
            None,
        )
    # AI assistants / call-control applications / OVP whitelists are
    # optional desired-state families (gate discovery on presence so a
    # deployment that codifies none pays no extra API round-trips).
    if DESIRED.get("ai_assistants"):
        state.assistants = client.get_list("/ai/assistants")
    if DESIRED.get("call_control_applications"):
        state.call_control_apps = client.get_list("/call_control_applications")
    if DESIRED.get("ovp_whitelisted_destinations") or DESIRED.get(
        "retired_outbound_voice_profiles"
    ):
        state.outbound_voice_profiles = client.get_list("/outbound_voice_profiles")
    if DESIRED.get("credential_connection_ovps"):
        # The dedicated list endpoint returns the FULL nested record (the
        # mixed /connections list is a summary view) — live-proven 2026-10-30.
        state.credential_connections = client.get_list("/credential_connections")
    if DESIRED.get("phone_numbers"):
        # The extra-DID map resolves CONNECTION and PROFILE rows by NAME:
        # the mixed /connections list carries connection_name (the summary
        # view), the profile list carries the profile names.
        state.connections = client.get_list("/connections")
        state.messaging_profiles = client.get_list("/messaging_profiles")
    return state


class Step:
    """One planned mutation. describe() is printed; apply() runs it.

    report_only steps carry operator actions no API call converges
    (e.g. the WABA signup): they print in the plan and NEVER count as
    drift for --drift-exit-code, because --apply cannot fix them.
    """

    def __init__(self, verb, detail, apply, report_only=False):
        self.verb = verb
        self.detail = detail
        self.apply = apply
        self.report_only = report_only


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
            state.messaging_profile = created
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

    # Messaging allowlist + alpha sender: both ride the SAME profile record
    # and the profile LIST endpoint already carries both fields (live-proven
    # 2026-10-30, no extra fetch). The allowlist is set-compared (the portal
    # reorders freely). A portal-side allowlist narrowing previously shipped
    # invisibly — the 2026-10-27 CH/GB/IE appends were runtime-only state no
    # gate could see.
    allowlist_wanted = DESIRED.get("messaging_profile_whitelisted_destinations")
    alpha_wanted = DESIRED.get("messaging_profile_alpha_sender")

    def extras_drift_body(record):
        body = {}
        if allowlist_wanted is not None and set(
            record.get("whitelisted_destinations") or []
        ) != set(allowlist_wanted):
            body["whitelisted_destinations"] = sorted(allowlist_wanted)
        if alpha_wanted is not None and record.get("alpha_sender") != alpha_wanted:
            body["alpha_sender"] = alpha_wanted
        return body

    if allowlist_wanted is not None or alpha_wanted is not None:
        if profile is None:
            # A profile created this run starts without the extras (the
            # create body stays minimal), so the follow-up PATCH targets the
            # id the create returns — same shape as the connection+outbound
            # pair above.

            def patch_extras(client, state):
                record = state.messaging_profile
                if record is None:
                    raise ReconcileError(
                        "internal: messaging profile missing at apply time"
                    )
                body = extras_drift_body(record)
                if body:
                    client.patch(f"/messaging_profiles/{record['id']}", body)

            steps.append(
                Step(
                    "PATCH messaging_profile extras",
                    f"{DESIRED['messaging_profile_name']}: allowlist "
                    f"{sorted(allowlist_wanted) if allowlist_wanted is not None else None} "
                    f"/ alpha sender {alpha_wanted!r} onto the created profile",
                    patch_extras,
                )
            )
        else:
            body = extras_drift_body(profile)
            if body:
                summary = ", ".join(f"{key} -> {value!r}" for key, value in body.items())

                def patch_extras(client, state, body=body, profile_id=profile["id"]):
                    client.patch(f"/messaging_profiles/{profile_id}", body)

                steps.append(
                    Step(
                        "PATCH messaging_profile extras",
                        summary,
                        patch_extras,
                    )
                )

    # Extra managed DIDs: the ONE core phone_number above generalizes
    # here — every extra DID is a desired-file row mapping it onto a
    # connection (voice) and/or the messaging profile (SMS) by NAME. A
    # number the account does not carry is report-only (ordering a
    # number is out of scope), as are unknown connection/profile names;
    # a messaging_profile row naming the CORE profile attaches against
    # the profile the core steps create this run.
    for number_value, wanted_routing in (DESIRED.get("phone_numbers") or {}).items():
        row = next(
            (
                record
                for record in state.phone_numbers
                if record.get("phone_number") == number_value
            ),
            None,
        )
        if row is None:
            steps.append(
                Step(
                    "VERIFY phone_number",
                    f"{number_value} not found in the account (ordering a "
                    "number is out of scope) — fix the phone_numbers row "
                    "or remove it",
                    lambda client, state: None,
                    report_only=True,
                )
            )
            continue
        conn_name = wanted_routing.get("connection")
        profile_name = wanted_routing.get("messaging_profile")
        conn_id = None
        profile_record = None
        profile_created_this_run = False
        if conn_name is not None:
            conn = next(
                (
                    record
                    for record in state.connections
                    if record.get("connection_name") == conn_name
                ),
                None,
            )
            if conn is None:
                steps.append(
                    Step(
                        "VERIFY connection",
                        f"no connection named {conn_name!r} in the account "
                        f"— the phone_numbers row for {number_value} must "
                        "name an existing connection",
                        lambda client, state: None,
                        report_only=True,
                    )
                )
                continue
            conn_id = str(conn.get("id"))
        if profile_name is not None:
            if profile_name == DESIRED["messaging_profile_name"]:
                profile_record = state.messaging_profile
                profile_created_this_run = profile_record is None
            else:
                profile_record = next(
                    (
                        record
                        for record in state.messaging_profiles
                        if record.get("name") == profile_name
                    ),
                    None,
                )
                if profile_record is None:
                    steps.append(
                        Step(
                            "VERIFY messaging_profile",
                            f"no messaging profile named {profile_name!r} in "
                            f"the account — the phone_numbers row for "
                            f"{number_value} must name an existing profile",
                            lambda client, state: None,
                            report_only=True,
                        )
                    )
                    continue
        needs_conn = conn_id is not None and str(
            row.get("connection_id") or ""
        ) != conn_id
        needs_profile = profile_name is not None and (
            profile_created_this_run
            or str(row.get("messaging_profile_id") or "")
            != str(profile_record.get("id"))
        )
        if needs_conn or needs_profile:
            labels = []
            if needs_conn:
                labels.append(
                    f"connection {row.get('connection_id')!r} -> {conn_name}"
                )
            if needs_profile:
                labels.append(
                    f"messaging_profile "
                    f"{row.get('messaging_profile_id')!r} -> {profile_name}"
                )

            def patch_number(
                client,
                state,
                row=row,
                needs_conn=needs_conn,
                conn_id=conn_id,
                needs_profile=needs_profile,
                profile_name=profile_name,
            ):
                body = {}
                if needs_conn:
                    body["connection_id"] = conn_id
                if needs_profile:
                    if profile_name == DESIRED["messaging_profile_name"]:
                        target = state.messaging_profile
                    else:
                        target = next(
                            (
                                record
                                for record in state.messaging_profiles
                                if record.get("name") == profile_name
                            ),
                            None,
                        )
                    if target is None:
                        raise ReconcileError(
                            "internal: messaging profile missing at apply time"
                        )
                    body["messaging_profile_id"] = target["id"]
                client.patch(f"/phone_numbers/{row['id']}", body)

            steps.append(
                Step(
                    "PATCH phone_number routing",
                    f"{number_value}: {', '.join(labels)}",
                    patch_number,
                )
            )

    # WhatsApp lane: registration and enablement are portal actions (Meta
    # embedded signup + VOICE OTP verification — SMS-to-VoIP is Meta
    # "Not Recommended"), so this is a REPORT-ONLY step: it names the
    # operator action, never claims API-convergible drift.
    whatsapp_did = DESIRED.get("whatsapp_did")
    if whatsapp_did:
        registered = state.whatsapp_number
        if registered is None:
            steps.append(
                Step(
                    "VERIFY whatsapp",
                    f"{whatsapp_did} is NOT registered on any WABA in the account — "
                    "run the portal's WhatsApp embedded signup and verify the "
                    "number by VOICE OTP (portal: Messaging → WhatsApp)",
                    lambda client, state: None,
                    report_only=True,
                )
            )
        elif not registered.get("enabled"):
            steps.append(
                Step(
                    "VERIFY whatsapp",
                    f"{whatsapp_did} is registered (status "
                    f"{registered.get('status')!r}) but NOT enabled — finish the "
                    "portal-side enablement",
                    lambda client, state: None,
                    report_only=True,
                )
            )

    # AI assistants: presence + model only. The full configuration
    # (instructions, voice, greeting, integrations) is owner taste that
    # evolves faster than a desired-state file — deployments snapshot it
    # (e.g. telnyx/assistants.<name>.snapshot.json) instead of reconciling
    # it. A MISSING assistant is therefore report-only; a model drift is
    # an actionable PATCH (Telnyx rejects the PATCH honestly when the
    # target model needs a BYOK key the assistant lacks — error 10015).
    for wanted_assistant in DESIRED.get("ai_assistants") or []:
        name = wanted_assistant["name"]
        assistant = next(
            (record for record in state.assistants if record.get("name") == name),
            None,
        )
        if assistant is None:
            steps.append(
                Step(
                    "VERIFY ai_assistant",
                    f"{name} does not exist in the account — create it (portal or "
                    "POST /ai/assistants) and snapshot the configuration; the "
                    "engine never synthesizes taste-heavy creates",
                    lambda client, state: None,
                    report_only=True,
                )
            )
        elif assistant.get("model") != wanted_assistant["model"]:
            steps.append(
                Step(
                    "PATCH ai_assistant",
                    f"{name}: model {assistant.get('model')!r} -> "
                    f"{wanted_assistant['model']!r}",
                    lambda client, state, assistant=assistant, wanted=wanted_assistant: (
                        client.patch(
                            f"/ai/assistants/{assistant['id']}",
                            {"model": wanted["model"]},
                        )
                    ),
                )
            )

    # Call-control applications: id-keyed pins (apps may carry no
    # human name — the API's first_name is nullable). `active` is always
    # checked; webhook_event_url and the outbound voice profile (NESTED
    # `outbound` in the PATCH, same shape as the credential-connection
    # lane) only when the desired row carries them — a console-side
    # webhook swap previously shipped invisibly. An id the account
    # does not carry is report-only: creating an app needs webhook URLs
    # and an OVP, which are deployment secrets the engine does not hold.
    for app_id, wanted_app in (DESIRED.get("call_control_applications") or {}).items():
        app = next(
            (
                record
                for record in state.call_control_apps
                if str(record.get("id")) == str(app_id)
            ),
            None,
        )
        if app is None:
            steps.append(
                Step(
                    "VERIFY call_control_application",
                    f"app id {app_id} not found in the account — create it "
                    "(portal: Voice > Call Control Applications) or fix the id",
                    lambda client, state: None,
                    report_only=True,
                )
            )
        else:
            patch_body = {}
            labels = []
            if app.get("active") is not wanted_app["active"]:
                patch_body["active"] = wanted_app["active"]
                labels.append(
                    f"active {app.get('active')!r} -> {wanted_app['active']!r}"
                )
            wanted_webhook = wanted_app.get("webhook_event_url")
            if (
                wanted_webhook is not None
                and app.get("webhook_event_url") != wanted_webhook
            ):
                patch_body["webhook_event_url"] = wanted_webhook
                labels.append(
                    f"webhook_event_url {app.get('webhook_event_url')!r} -> "
                    f"{wanted_webhook!r}"
                )
            wanted_ovp = wanted_app.get("outbound_voice_profile_id")
            if wanted_ovp is not None:
                current_ovp = (app.get("outbound") or {}).get(
                    "outbound_voice_profile_id"
                )
                if current_ovp != wanted_ovp:
                    patch_body["outbound"] = {"outbound_voice_profile_id": wanted_ovp}
                    labels.append(
                        f"outbound.outbound_voice_profile_id {current_ovp!r} -> "
                        f"{wanted_ovp!r}"
                    )
            if patch_body:

                def patch_app(client, state, app_id=app_id, body=patch_body):
                    client.patch(f"/call_control_applications/{app_id}", body)

                steps.append(
                    Step(
                        "PATCH call_control_application",
                        f"app {app_id}: {', '.join(labels)}",
                        patch_app,
                    )
                )

    # OVP whitelisted destinations: set-compared per OVP name (the portal
    # reorders freely). Drift PATCHes the sorted desired list — the API
    # replaces the whole list in one call.
    for ovp_name, wanted_destinations in (
        DESIRED.get("ovp_whitelisted_destinations") or {}
    ).items():
        profile = next(
            (
                record
                for record in state.outbound_voice_profiles
                if record.get("name") == ovp_name
            ),
            None,
        )
        if profile is None:
            steps.append(
                Step(
                    "VERIFY outbound_voice_profile",
                    f"no OVP named {ovp_name!r} in the account — the whitelist "
                    "key must name an existing profile",
                    lambda client, state: None,
                    report_only=True,
                )
            )
        elif set(profile.get("whitelisted_destinations") or []) != set(
            wanted_destinations
        ):
            steps.append(
                Step(
                    "PATCH outbound_voice_profile",
                    f"{ovp_name} whitelisted_destinations "
                    f"{sorted(profile.get('whitelisted_destinations') or [])} -> "
                    f"{sorted(wanted_destinations)}",
                    lambda client, state, profile=profile, wanted=wanted_destinations: (
                        client.patch(
                            f"/outbound_voice_profiles/{profile['id']}",
                            {"whitelisted_destinations": sorted(wanted)},
                        )
                    ),
                )
            )

    # Retired outbound voice profiles: a desired list of names that
    # should no longer exist. Live survivors surface as report-only
    # NOTICE steps — the deletion itself stays owner-gated (a profile
    # may still be the silent ride of an unmanaged connection). A
    # retired name an ACTIVE desired key still references is called out
    # as a conflict inside the notice, never patched away.
    retired_names = DESIRED.get("retired_outbound_voice_profiles") or []
    if retired_names:
        # References carry IDs in most lanes (core, credential connections,
        # call-control apps) but NAMES in the OVP-whitelist lane — check
        # both shapes against the live record.
        referenced_ids = {DESIRED["outbound_voice_profile_id"]}
        referenced_ids.update((DESIRED.get("credential_connection_ovps") or {}).values())
        referenced_ids.update(
            app["outbound_voice_profile_id"]
            for app in (DESIRED.get("call_control_applications") or {}).values()
            if app.get("outbound_voice_profile_id")
        )
        referenced_names = set(
            (DESIRED.get("ovp_whitelisted_destinations") or {}).keys()
        )
        for record in state.outbound_voice_profiles:
            name = record.get("name")
            if name not in retired_names:
                continue
            if record.get("id") in referenced_ids or name in referenced_names:
                conflict = (
                    "still referenced by the desired state — retire the "
                    "reference first"
                )
            else:
                conflict = (
                    "delete it in the portal (owner-gated; the engine "
                    "never deletes)"
                )
            steps.append(
                Step(
                    "NOTICE retired_outbound_voice_profile",
                    f"{name!r} is marked retired but still live — {conflict}",
                    lambda client, state: None,
                    report_only=True,
                )
            )

    # Credential-connection voice profiles: the SIP trunk lane rides a
    # credential connection whose nested `outbound.outbound_voice_profile_id`
    # is invisible to the fqdn-connection steps. The 2026-10-26 +41 burn: a
    # profile destination widening landed on the trunk connections while the
    # credential lane kept its trial-era US/CA profile — every non-US/CA dial
    # died in ~1 s, and the mixed /connections summary's FLAT field is the
    # only shape some reads surface (the nested one is authoritative).
    for conn_name, wanted_ovp in (
        DESIRED.get("credential_connection_ovps") or {}
    ).items():
        conn = next(
            (
                record
                for record in state.credential_connections
                if record.get("connection_name") == conn_name
            ),
            None,
        )
        if conn is None:
            steps.append(
                Step(
                    "VERIFY credential_connection",
                    f"no credential connection named {conn_name!r} in the account "
                    "— the voice-profile key must name an existing connection",
                    lambda client, state: None,
                    report_only=True,
                )
            )
            continue
        current = (conn.get("outbound") or {}).get("outbound_voice_profile_id")
        if current is None:
            # Summary-view fallback; the dedicated endpoint nests the field.
            current = conn.get("outbound_voice_profile_id")
        if current != wanted_ovp:

            def patch_credential_ovp(client, state, conn=conn, wanted=wanted_ovp):
                client.patch(
                    f"/credential_connections/{conn['id']}",
                    {"outbound": {"outbound_voice_profile_id": wanted}},
                )

            steps.append(
                Step(
                    "PATCH credential_connection",
                    f"{conn_name}: outbound.outbound_voice_profile_id "
                    f"{current!r} -> {wanted_ovp!r}",
                    patch_credential_ovp,
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
            if args.drift_exit_code and any(not s.report_only for s in steps):
                print(
                    "drift detected — re-run with --apply (or fix the cause) "
                    "to converge"
                )
                return 2
            print("dry-run only — re-run with --apply to execute")
            return 0
        for index, step in enumerate(steps, 1):
            if step.report_only:
                print(f"NOTE {index}. {step.verb}: {step.detail}")
                continue
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
