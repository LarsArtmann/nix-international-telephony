#!/usr/bin/env python3
"""Drift alarm: keep TODO_LIST.md rows honest against FEATURES.md and the tree.

Doc drift in this repo historically needed archaeology to notice (a feature
shipped, its TODO row survived, and sessions re-did or re-triaged finished
work, see the 2026-08-27 docs-health audit). This script makes the drift a
gate error instead. Four failure classes:

1. Duplication: a TODO task whose stable identifiers (backtick-quoted
   spans, e.g. option or file names) overlap a FULLY_FUNCTIONAL FEATURES
   row is presumed to describe already-shipped work. Two shared
   identifiers always flag; a single identifier that is an option-style
   path (dotted lowercase, like recording.retentionDays) flags on its
   own, while generic single tokens (a shared file path or port number)
   do not.
2. Archived-snapshot citation: a row citing a path under an archived/
   directory points at history no future session will be routed to.
3. Live-snapshot citation: a row citing docs/status/ or docs/planning/
   (not yet archived) will rot into class 2 the day the snapshot is
   filed away; evidence for open work belongs in living docs or code.
4. Ghost citation: a cited repo-relative path that does not exist in
   the source tree the gate runs against (the 2026-09-18 round-4
   rebuild repaired two of these by hand; the gate catches the class).

Usage: drift_alarm.py TODO_LIST.md FEATURES.md [repo-root]
       drift_alarm.py --self-test

repo-root defaults to the TODO file's parent directory (correct for
local runs); the flake check passes the flake source explicitly because
a per-file store path lands directly in /nix/store with no tree around
it.
"""

import re
import sys
import tempfile
from pathlib import Path

BACKTICK = re.compile(r"`([^`]+)`")
# Option-style identifier: lowercase first segment, dotted, e.g.
# recording.retentionDays or services.telephony. Dashes/slashes (file
# paths, package names) deliberately do not match: too easy to share
# incidentally across distinct work items.
OPTION_PATH = re.compile(r"^[a-z][a-zA-Z0-9]*(\.[a-zA-Z0-9]+)+$")
STATUS_FULLY = "FULLY_FUNCTIONAL"
SNAPSHOT_DIRS = ("docs/status/", "docs/planning/")
ARCHIVED = "archived/"
# Plain-text path candidates: must not start mid-path (so absolute
# paths like /var/tmp are never matched at their second segment).
PLAIN_PATH = re.compile(r"(?<![\w/])[A-Za-z][\w.-]*(?:/[\w.-]+)+")
GLOB_CHARS = set("*?[]")
# Gitignored operator-local files: they exist on the operator's machine
# but never in the flake source this gate sees (the committed *.example
# template is the in-repo contract).
LOCAL_ONLY_PATHS = {"secrets/scrub-patterns.txt"}


def table_rows(text: str):
    """Yield the cell list of every markdown table data row."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= {"|", "-", " ", ":"}:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells and cells[0]:
            yield cells


def is_relative_path(text: str) -> bool:
    """A candidate citation that can resolve inside the repo source."""
    return (
        "/" in text
        and not text.startswith("/")
        and not (set(text) & GLOB_CHARS)
        and not any(char.isspace() for char in text)
    )


def cited_paths(row_text: str) -> set[str]:
    """All repo-relative path candidates cited anywhere in a row.

    Two tiers: backticked spans containing a slash (the stable-name
    convention for citations) and plain-text candidates that carry a
    dot, so annotated mentions like "see docs/deploy.md (section 3)"
    still resolve. The dot filter keeps section refs like P31/P32 from
    being mistaken for paths. Absolute paths and globs are out of scope.
    """
    candidates = set()
    for span in BACKTICK.findall(row_text):
        if is_relative_path(span):
            candidates.add(span)
    for match in PLAIN_PATH.findall(row_text):
        if "." in match and is_relative_path(match):
            candidates.add(match)
    return candidates


def missing_paths(row_text: str, repo_root: Path) -> list[str]:
    """Cited candidates that resolve to nothing in the source tree."""
    return [
        path
        for path in sorted(cited_paths(row_text))
        if path not in LOCAL_ONLY_PATHS and not (repo_root / path).exists()
    ]


def collect_failures(todo_text: str, features_text: str, repo_root: Path) -> list[str]:
    """Return one report block per gate violation (empty list = pass)."""
    failures: list[str] = []

    shipped: list[tuple[str, set[str]]] = []
    for line in features_text.splitlines():
        if STATUS_FULLY not in line:
            continue
        rows = list(table_rows(line))
        if rows:
            feature = rows[0][0]
            shipped.append((feature, set(BACKTICK.findall(feature))))

    for cells in table_rows(todo_text):
        task = cells[0]
        row_text = " | ".join(cells)

        task_ids = set(BACKTICK.findall(task))
        for feature, feature_ids in shipped:
            shared = task_ids & feature_ids
            duplicates_work = len(shared) >= 2 or any(
                OPTION_PATH.match(s) for s in shared
            )
            if shared and duplicates_work:
                failures.append(
                    "FAIL: TODO_LIST row duplicates a FULLY_FUNCTIONAL feature\n"
                    f"  todo-list row: {task}\n"
                    f"  shipped feature: {feature}\n"
                    f"  shared identifiers: {', '.join(sorted(shared))}\n"
                    "  (delete the TODO row, or the feature status is lying)"
                )

        for path in sorted(cited_paths(row_text)):
            if not any(directory in path for directory in SNAPSHOT_DIRS):
                continue
            if ARCHIVED in path:
                failures.append(
                    "FAIL: TODO_LIST row cites an archived/ snapshot as evidence\n"
                    f"  todo-list row: {task}\n"
                    f"  cited path: {path}\n"
                    "  (archived reports are history; cite code or a live doc)"
                )
            else:
                failures.append(
                    "FAIL: TODO_LIST row cites a not-yet-archived snapshot\n"
                    f"  todo-list row: {task}\n"
                    f"  cited path: {path}\n"
                    "  (docs/status and docs/planning are point-in-time"
                    " snapshots; cite a living doc or code so the row"
                    " survives their archival)"
                )

        for path in missing_paths(row_text, repo_root):
            failures.append(
                "FAIL: TODO_LIST row cites a path missing from the tree\n"
                f"  todo-list row: {task}\n"
                f"  missing path: {path}\n"
                "  (a moved or deleted file; fix the citation or the path)"
            )

    return failures


def self_test() -> int:
    """Negative tests: every arm must fire on crafted violations and stay
    silent on the control rows next to them."""
    features = "\n".join(
        [
            "| Feature | Status |",
            "| --- | --- |",
            "| `recording.retentionDays` auto-delete | FULLY_FUNCTIONAL |",
        ]
    )

    def todo(row: str) -> str:
        return "\n".join(["| Task | Status |", "| --- | --- |", row])

    cases = [
        (
            "control backticked live path",
            "| polish `docs/exists.md` wording | TODO |",
            None,
        ),
        (
            "control plain-text live path",
            "| discussed in docs/exists.md already | TODO |",
            None,
        ),
        ("control absolute path", "| kill `/var/tmp/fspbx-trial` | TODO |", None),
        ("control glob", "| batch `scripts/*.sh` checks | TODO |", None),
        ("control section ref", "| rerun the P31/P32 probes | TODO |", None),
        (
            "control gitignored local file",
            "| rotate keys per `secrets/scrub-patterns.txt` | TODO |",
            None,
        ),
        (
            "duplication",
            "| add `recording.retentionDays` again | TODO |",
            "duplicates a FULLY_FUNCTIONAL",
        ),
        (
            "ghost backticked",
            "| fix `docs/missing.md` drift | TODO |",
            "missing path: docs/missing.md",
        ),
        (
            "ghost plain-text",
            "| read docs/missing-too.md closely | TODO |",
            "missing path: docs/missing-too.md",
        ),
        (
            "archived snapshot",
            "| see `docs/status/archived/2026-01-01_a.md` | TODO |",
            "archived/ snapshot",
        ),
        (
            "live status snapshot",
            "| see `docs/status/2026-01-02_b.md` | TODO |",
            "docs/status/2026-01-02_b.md",
        ),
        (
            "live planning snapshot",
            "| see `docs/planning/2026-01-03_c.md` | TODO |",
            "docs/planning/2026-01-03_c.md",
        ),
    ]

    broken = 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "docs").mkdir()
        (root / "docs" / "exists.md").write_text("live doc\n")
        for label, row, expected in cases:
            got = collect_failures(todo(row), features, root)
            if expected is None:
                if got:
                    broken += 1
                    print(f"SELF-TEST FAIL ({label}): control row was flagged:")
                    for block in got:
                        print(block)
                else:
                    print(f"self-test ok (control clean): {label}")
            elif not any(expected in block for block in got):
                broken += 1
                print(
                    f"SELF-TEST FAIL ({label}): expected a report containing {expected!r}"
                )
            else:
                print(f"self-test ok (arm fires): {label}")

    if broken:
        print(f"FAIL: {broken} drift_alarm self-test case(s) broken")
        return 1
    print("PASS: drift_alarm self-test (every arm fires, every control clean)")
    return 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        return self_test()
    if len(sys.argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    todo_path = Path(sys.argv[1])
    todo_text = todo_path.read_text()
    features_text = Path(sys.argv[2]).read_text()
    repo_root = Path(sys.argv[3]) if len(sys.argv) == 4 else todo_path.resolve().parent

    failures = collect_failures(todo_text, features_text, repo_root)
    if failures:
        for block in failures:
            print(block)
        return 1
    print("PASS: TODO_LIST rows agree with FEATURES.md, cite live paths only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
