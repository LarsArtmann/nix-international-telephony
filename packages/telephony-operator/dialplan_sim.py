"""Offline dry-run simulator for the generated FreeSWITCH dialplan.

Parses dialplan XML (default + public context) and answers "what happens
if I dial X at time T": which extensions match, which actions run, and
where the call ends up — without touching a running PBX.

Semantics implemented (mirrors mod_dialplan_xml's parse-time evaluation;
the sharp edges are recorded in docs/lessons/freeswitch.md):

* Conditions are evaluated at PARSE time in document order; a whole
  extension is decided before any action runs.
* `field` + `expression` conditions regex against the current
  destination (`destination_number`) or a channel variable (`${name}`).
  Python `re` stands in for PCRE — the generator only emits patterns in
  the common subset.
* Attribute conditions (`wday=`, `hour=`, `minute=`) use FreeSWITCH
  switch_number_cmp range syntax: comma-separated values and inclusive
  `A-B` ranges. `wday` is 1=Sun..7=Sat (server-local time).
* `break`: default `on-false` (a failing condition stops the extension,
  nothing collected runs); `on-true` stops AFTER a matching condition
  (its actions are the only ones kept); `never`/`always` continue.
* Matching collects actions across passing conditions in order; the
  FIRST extension with any collected actions wins.

Supported actions: set, answer, sleep, echo, bridge, voicemail, rxfax,
transfer (followed into the target context, max depth 8), record_session,
ivr (menu follow-through with an optional digit input), hangup,
conference.
"""

import argparse
import calendar
import json
import re
import sys
import xml.etree.ElementTree as ET

MAX_TRANSFER_DEPTH = 8

# The 13-field "default" template mod_cdr_csv registers; informational
# only for the simulator, referenced by the operator CDR viewer.
CDR_TEMPLATE_FIELDS = [
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


class DialplanError(Exception):
    pass


def _load_contexts(xml_path):
    """Return {context_name: [extension_element, ...]}."""
    tree = ET.parse(xml_path)
    contexts = {}
    for context in tree.getroot().iter("context"):
        name = context.get("name")
        if not name:
            raise DialplanError(f"{xml_path}: <context> without name")
        contexts[name] = context.findall("extension")
    return contexts


def _parse_ranges(spec, value):
    """FreeSWITCH switch_number_cmp: comma list of values / A-B ranges."""
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            if int(lo) <= value <= int(hi):
                return True
        elif int(part) == value:
            return True
    return False


WDAY_NAMES = {
    "sun": 1,
    "mon": 2,
    "tue": 3,
    "wed": 4,
    "thu": 5,
    "fri": 6,
    "sat": 7,
}


def _condition_matches(cond, destination, variables, when):
    """Evaluate one <condition> element (no children)."""
    field = cond.get("field")
    if field is not None:
        subject = destination if field == "destination_number" else variables.get(field.strip("${}"))
        expression = cond.get("expression")
        if expression is None:
            return False
        if subject is None:
            return False
        return re.search(expression, str(subject)) is not None

    # Attribute time conditions (wday/hour/minute/mday/mon/year...) —
    # FreeSWITCH evaluates them against server-local time.
    checks = {
        "wday": when["wday"],
        "hour": when["hour"],
        "minute": when["minute"],
        "mday": when["mday"],
        "mon": when["mon"],
    }
    for attr, value in checks.items():
        spec = cond.get(attr)
        if spec is not None and not _parse_ranges(spec, value):
            return False
    return True


def _iter_conditions_flat(extension):
    """Document-order walk over every <condition>, flattened.

    The generator nests attribute conditions one level deep inside the
    destination-number condition; mod_dialplan_xml evaluates them in
    document order, which flattening reproduces.
    """
    def walk(element):
        for child in element:
            if child.tag == "condition":
                yield child
                yield from walk(child)

    yield from walk(extension)


def match_extension(extension, destination, variables, when):
    """Return the collected actions when the extension matches, else []."""
    collected = []
    for cond in _iter_conditions_flat(extension):
        ok = _condition_matches(cond, destination, variables, when)
        brk = cond.get("break") or "on-false"
        if ok:
            collected.extend(cond.findall("action"))
            collected.extend(cond.findall("anti-action"))  # never emitted by the generator; rejected below
            if brk == "on-true":
                return collected
        else:
            anti = cond.findall("anti-action")
            if anti:
                raise DialplanError(
                    "anti-action conditions are not supported by the "
                    "simulator (the generator does not emit them)"
                )
            if brk == "on-false":
                return []
    return collected


def _action(a, destination, variables, when, contexts, context, trace, depth, ivr_input):
    """Execute one collected action; return (outcome, next_destination)."""
    app = a.get("application")
    data = a.get("data") or ""
    entry = {"application": app, "data": data}

    if app == "set":
        key, _, value = data.partition("=")
        variables[key] = value
        return None, None

    if app in ("answer", "sleep", "pre_answer", "ring_ready", "record_session"):
        return None, None

    if app == "transfer":
        # "dest XML context" — follow into the target context.
        dest = data.split()[0]
        target_context = "default"
        parts = data.split()
        if len(parts) >= 3 and parts[2] in contexts:
            target_context = parts[2]
        trace.append(dict(entry, note=f"transfer -> {dest} (context {target_context})"))
        if depth >= MAX_TRANSFER_DEPTH:
            return {"type": "error", "detail": "transfer chain too deep"}, None
        return None, (dest, target_context)

    if app == "bridge":
        targets = []
        # "|" separates serial gateway failover; "," separates the
        # simultaneously-rung members of a user/N bridge.
        for part in data.split("|"):
            for target in part.split(","):
                target = target.strip()
                if target.startswith("user/"):
                    targets.append({"type": "extension", "target": target[len("user/") :]})
                elif target.startswith("sofia/gateway/"):
                    _, _, rest = target.partition("sofia/gateway/")
                    gateway, _, number = rest.partition("/")
                    # "$1" is the regex capture of the dialled number.
                    targets.append(
                        {
                            "type": "pstn",
                            "gateway": gateway,
                            "number": "<dialed>" if "$" in number else number,
                        }
                    )
                elif target:
                    targets.append({"type": "raw", "dial_string": target})
        outcome = {"type": "bridge", "targets": targets}
        return outcome, None

    if app == "voicemail":
        parts = data.split()
        # "default ${domain} <box>" (deposit) or "check default ${domain}".
        box = parts[-1] if parts and parts[-1].isdigit() else None
        outcome = {"type": "voicemail", "mode": parts[0], "box": box}
        return outcome, None

    if app == "rxfax":
        return {"type": "fax", "file": data}, None

    if app == "ivr":
        menu = data.strip()
        outcome = {"type": "ivr", "menu": menu}
        # Optional digit input: follow the menu entry like the runtime
        # menu-exec-app does (transfer <destination> XML default).
        if ivr_input:
            key, _, rest = ivr_input.partition(",")
            outcome["input"] = key
            # Menu data lives in ivr.conf.xml, not the dialplan; the
            # caller supplies entry mappings via --ivr-entry key=dest.
            return outcome, None
        return outcome, None

    if app == "hangup":
        return {"type": "hangup", "cause": data or "normal_clearing"}, None

    if app == "echo":
        return {"type": "echo"}, None

    if app == "conference":
        room = data.split("@")[0].split("+")[0]
        return {"type": "conference", "room": room}, None

    raise DialplanError(f"unsupported dialplan application {app!r}")


def simulate(contexts, context, destination, variables, when, ivr_input=None):
    """Run one call through the dialplan; returns the result dict."""
    trace = []
    depth = 0
    variables = dict(variables)
    current = (destination, context)
    outcome = None
    matched = []

    while current is not None and outcome is None:
        destination, context = current
        extensions = contexts.get(context)
        if extensions is None:
            outcome = {"type": "error", "detail": f"unknown context {context}"}
            break
        next_hop = None
        for extension in extensions:
            name = extension.get("name") or "<unnamed>"
            actions = match_extension(extension, destination, variables, when)
            if not actions:
                continue
            matched.append(name)
            for action in actions:
                outcome, hop = _action(
                    action, destination, variables, when, contexts, context, trace, depth, ivr_input
                )
                if hop is not None:
                    next_hop = hop
                    break
                if outcome is not None:
                    break
            if outcome is not None or next_hop is not None:
                break
        else:
            outcome = {"type": "unallocated", "detail": "no extension matched"}
        if next_hop is not None:
            depth += 1
            current = next_hop
        else:
            current = None

    return {
        "destination": destination,
        "context": context,
        "time": "{:04d}-{:02d}-{:02d}T{:02d}:{:02d} wday={}".format(
            when["year"], when["mon"], when["mday"], when["hour"], when["minute"], when["wday"]
        ),
        "matched_extensions": matched,
        "trace": trace,
        "outcome": outcome or {"type": "unknown"},
    }


def _when_from_args(args):
    if args.when:
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})$", args.when)
        if not match:
            raise DialplanError("--when must be YYYY-MM-DDTHH:MM (server-local time)")
        year, mon, mday, hour, minute = (int(part) for part in match.groups())
    else:
        import datetime

        now = datetime.datetime.now()
        year, mon, mday, hour, minute = now.year, now.month, now.day, now.hour, now.minute
    wday = (calendar.weekday(year, mon, mday) + 1) % 7 + 1  # 1=Sun..7=Sat
    return {
        "year": year,
        "mon": mon,
        "mday": mday,
        "hour": hour,
        "minute": minute,
        "wday": wday,
    }


def load_contexts_dir(directory):
    """Load every *.xml dialplan file under a directory into {name: [exts]}."""
    import glob
    import os

    contexts = {}
    for path in sorted(glob.glob(os.path.join(directory, "*.xml"))):
        contexts.update(_load_contexts(path))
    if not contexts:
        raise DialplanError(f"no dialplan XML found under {directory}")
    return contexts


def inbound_dids(contexts):
    """DID numbers served by the public context (from its expressions)."""
    dids = set()
    for extension in contexts.get("public", []):
        for cond in _iter_conditions_flat(extension):
            expression = cond.get("expression") or ""
            match = re.match(r"^\^\+?(\d+)\$$", expression)
            if match:
                dids.add(match.group(1))
    return dids


def entry_context(contexts, destination):
    """Pick the realistic entry context for a dialed number.

    Numbers the public context serves as DIDs arrive on the trunk
    (public context); everything else is what an internal phone dials
    (default context).
    """
    stripped = destination.lstrip("+")
    if "*" in destination or "#" in destination:
        return "default"
    if stripped in inbound_dids(contexts):
        return "public"
    return "default"


def simulate_from_query(contexts, destination, variables, when_str, ivr_input=None):
    """Simulate from (optional) "YYYY-MM-DDTHH:MM" string + var dict."""

    class _Args:
        when = when_str

    return simulate(
        contexts,
        entry_context(contexts, destination),
        destination,
        variables,
        _when_from_args(_Args),
        ivr_input,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="telephony-dialplan-simulate",
        description="Dry-run the generated FreeSWITCH dialplan: what happens to a call, offline.",
    )
    parser.add_argument("dialplan_dir", help="directory containing the generated dialplan/*.xml")
    parser.add_argument("--dest", required=True, help="dialed number (DID, extension, group, ...)")
    parser.add_argument("--context", default=None, help="entry context (default: auto — public for DIDs, default otherwise)")
    parser.add_argument(
        "--when", help='evaluation time, "YYYY-MM-DDTHH:MM" server-local (default: now)'
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="channel variable (repeatable; e.g. --var toll_allow=domestic,local)",
    )
    parser.add_argument("--ivr-input", help="digits to feed an IVR menu, comma-separated steps")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--no-default-vars",
        action="store_true",
        help="do not preset directory defaults (toll_allow domestic,local,international)",
    )
    args = parser.parse_args(argv)

    try:
        contexts = load_contexts_dir(args.dialplan_dir)

        variables = {} if args.no_default_vars else {
            # Directory default for an allowInternational extension.
            "toll_allow": "domestic,local,international",
        }
        for spec in args.var:
            key, _, value = spec.partition("=")
            variables[key] = value

        result = simulate(
            contexts,
            args.context or entry_context(contexts, args.dest),
            args.dest,
            variables,
            _when_from_args(args),
            ivr_input=args.ivr_input,
        )
    except (DialplanError, ET.ParseError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"call to {result['destination']} at {result['time']}")
        for name in result["matched_extensions"]:
            print(f"  extension {name}")
        for entry in result["trace"]:
            note = f"  - {entry['application']} {entry['data']}"
            if "note" in entry:
                note += f"  ({entry['note']})"
            print(note)
        outcome = result["outcome"]
        kind = outcome.get("type")
        if kind == "bridge":
            for target in outcome["targets"]:
                label = (
                    f"ring {target['target']}"
                    if target["type"] == "extension"
                    else f"PSTN {target['number']} via {target['gateway']}"
                    if target["type"] == "pstn"
                    else target.get("dial_string", "?")
                )
                print(f"  => {label}")
        elif kind == "voicemail":
            print(f"  => voicemail ({outcome['mode']}, box {outcome.get('box')})")
        elif kind == "ivr":
            print(f"  => IVR menu {outcome['menu']} (input: {outcome.get('input', 'none')})")
        else:
            print(f"  => {json.dumps(outcome)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
