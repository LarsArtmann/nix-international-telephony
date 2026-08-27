#!/usr/bin/env python3
"""Drift alarm: fail when a TODO_LIST row re-requests a FULLY_FUNCTIONAL feature.

Doc drift in this repo historically needed archaeology to notice (a feature
shipped, its TODO row survived, and sessions re-did or re-triaged finished
work — see the 2026-08-27 docs-health audit). This script makes the drift a
gate error instead.

Model: both files are markdown tables. A TODO task whose stable identifiers
(backtick-quoted spans, e.g. option or file names) overlap a
FULLY_FUNCTIONAL FEATURES row is presumed to describe already-shipped work.
Two shared identifiers always flag; a single identifier that is an
option-style path (dotted lowercase, like recording.retentionDays) flags on
its own, while generic single tokens (a shared file path or port number)
do not — genuine duplication names the thing AND its option, or an option
so specific it cannot be incidental.

Usage: drift_alarm.py TODO_LIST.md FEATURES.md
"""

import re
import sys

BACKTICK = re.compile(r"`([^`]+)`")
# Option-style identifier: lowercase first segment, dotted, e.g.
# recording.retentionDays or services.telephony. Dashes/slashes (file
# paths, package names) deliberately do not match — too easy to share
# incidentally across distinct work items.
OPTION_PATH = re.compile(r"^[a-z][a-zA-Z0-9]*(\.[a-zA-Z0-9]+)+$")
STATUS_FULLY = "FULLY_FUNCTIONAL"


def table_rows(text: str):
    """Yield the first-column cell of every markdown table data row."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= {"|", "-", " ", ":"}:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0]:
            yield cells[0]


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    todo_text = open(sys.argv[1]).read()
    features_text = open(sys.argv[2]).read()

    shipped = []
    for line in features_text.splitlines():
        if STATUS_FULLY not in line:
            continue
        names = list(table_rows(line))
        if names:
            shipped.append((names[0], set(BACKTICK.findall(names[0]))))

    drift = []
    for task in table_rows(todo_text):
        task_ids = set(BACKTICK.findall(task))
        for feature, feature_ids in shipped:
            shared = task_ids & feature_ids
            duplicates_work = (
                len(shared) >= 2
                or any(OPTION_PATH.match(s) for s in shared)
            )
            if shared and duplicates_work:
                drift.append((task, feature, sorted(shared)))

    if drift:
        print("FAIL: TODO_LIST rows duplicate FULLY_FUNCTIONAL FEATURES rows")
        print("(delete the TODO row, or the feature status is lying)")
        for task, feature, shared in drift:
            print(f"  TODO: {task}")
            print(f"  SHIPPED: {feature}")
            print(f"  shared identifiers: {', '.join(shared)}")
        return 1
    print("PASS: no TODO_LIST row duplicates a FULLY_FUNCTIONAL feature")
    return 0


if __name__ == "__main__":
    sys.exit(main())
