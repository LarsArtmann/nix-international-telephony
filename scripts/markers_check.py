#!/usr/bin/env python3
"""Check per-item resolution markers in archived status/planning snapshots.

House convention (AGENTS.md, Conventions): every item in the open-work
sections (default: b, c, f, g) of an ARCHIVED snapshot must carry an
inline resolution marker -- ``~~...~~ done at`` strikes, routed
``-> done/open/...`` verdicts, ``Won't implement``, ``NOT-DO`` etc.
Sections a/d/e stay bare by design (achievements and process
reflections); verdicts may sit on the item's own line or on a following
line of its block (the routed-arrow style). A stale marker gets a
``-> corrected`` append, never a rewrite.

Planning snapshots get the same treatment through their Pareto tables:
``## Step 2`` medium-task rows are scoped like open-work items (every
M-row carries a verdict at archive time), while ``## Step 3`` fine-task
rows deliberately stay bare -- the house style satisfies them with a
single inheritance note above the table ("every fine task inherits its
parent M-row verdict"), so the checker leaves Step 3 out of scope.

Exit status: 0 = every scoped item marked, 1 = unmarked items (listed
with file:line), 2 = usage/self-test failure.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

SECTION_RE = re.compile(r"^## ([a-g])\)")
PLAN_STEP2_RE = re.compile(r"^## Step 2\b")
ITEM_RE = re.compile(r"^\s{0,3}(?:\d+\.\s|\|)")
HEADER_ROW_RE = re.compile(
    r"^\|\s*(?:#|Item|What|Task|Nr?|Aspect|Area|Layer|Name|Phase|Step|Cat)\s*\|",
    re.IGNORECASE,
)
SEPARATOR_ROW_RE = re.compile(r"^\|[\s:*=|-]+$")
# \b guards: "unanswered"/"unresolved" must NOT count as verdicts.
MARKER_RE = re.compile(
    r"~~|<del>|<s>|→|Won.t implement|\bNOT-DO\b|\bDUPLICATE\b|\bdone at\b|\banswered\b|\bresolved\b",
    re.IGNORECASE,
)


def unmarked_items(path: Path, sections: set[str]) -> list[tuple[int, str]]:
    """(line_number, line_text) of scoped items carrying no verdict marker."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    findings: list[tuple[int, str]] = []
    section: str | None = None
    index = 0
    while index < len(lines):
        line = lines[index]
        heading = SECTION_RE.match(line)
        if heading:
            section = heading.group(1)
            index += 1
            continue
        if PLAN_STEP2_RE.match(line):
            section = "step2"
            index += 1
            continue
        if line.startswith("## "):
            section = None
            index += 1
            continue
        if (
            (section in sections or section == "step2")
            and ITEM_RE.match(line)
            and not HEADER_ROW_RE.match(line)
            and not SEPARATOR_ROW_RE.match(line)
            and line.strip() not in ("|", "---")
            and not MARKER_RE.search(line)
            and not _block_has_verdict(lines, index)
        ):
            findings.append((index + 1, line.strip()))
        index += 1
    return findings


def _block_has_verdict(lines: list[str], index: int) -> bool:
    """True when a verdict line appears before the next item/heading."""
    probe = index + 1
    while probe < len(lines):
        following = lines[probe]
        if SECTION_RE.match(following) or following.startswith("## "):
            break
        if ITEM_RE.match(following):
            break
        if MARKER_RE.search(following):
            return True
        probe += 1
    return False


def self_test() -> int:
    """Positive and negative arms: the checker must fire on planted
    misses and stay silent on every accepted house style."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        clean = root / "clean.md"
        clean.write_text(
            "## b) PARTIALLY DONE\n"
            "1. Thing one\n"
            "   → done — landed\n"
            "2. Thing two → open — owner lane\n"
            "## f) NEXT\n"
            "| 1 | bare table row → done — x | y |\n"
            "| # | header not an item | z |\n"
            "| --- | --- |\n"
            "## a) FULLY DONE\n"
            "1. Achievement rows stay bare by convention\n",
            encoding="utf-8",
        )
        assert unmarked_items(clean, {"b", "c", "f", "g"}) == [], "clean file flagged"

        missing_block_verdict = root / "miss_block.md"
        missing_block_verdict.write_text(
            "## c) NOT STARTED\n"
            "1. Wrapped item paragraph\n"
            "   continuation line without verdict\n"
            "2. Next item → done\n",
            encoding="utf-8",
        )
        hits = unmarked_items(missing_block_verdict, {"b", "c", "f", "g"})
        assert len(hits) == 1 and hits[0][0] == 2, (
            f"planted block miss not caught: {hits}"
        )

        bare_numbered = root / "miss_row.md"
        bare_numbered.write_text(
            "## g) QUESTIONS\n1. An unanswered question\n",
            encoding="utf-8",
        )
        hits = unmarked_items(bare_numbered, {"b", "c", "f", "g"})
        assert len(hits) == 1, f"planted numbered miss not caught: {hits}"

        corrected = root / "corrected.md"
        corrected.write_text(
            "## f) NEXT\n"
            "| 7 | row → still open — stale claim → corrected 2026-09-29 — fixed |\n",
            encoding="utf-8",
        )
        assert unmarked_items(corrected, {"b", "c", "f", "g"}) == [], (
            "corrected row flagged"
        )

        plan = root / "plan.md"
        plan.write_text(
            "## Step 2 — comprehensive plan\n"
            "| M01 | marked row → done — landed | High | 30min |\n"
            "| M02 | bare plan row | High | 30min |\n"
            "## Step 3 — fine breakdown\n"
            "_Annotation: every fine task inherits its parent M-row verdict._\n"
            "| f01.01 | bare fine row is fine | 5 | — |\n",
            encoding="utf-8",
        )
        hits = unmarked_items(plan, {"b", "c", "f", "g"})
        assert len(hits) == 1 and hits[0][0] == 3, (
            f"plan scoping wrong (want exactly the bare Step-2 row at line 3): {hits}"
        )

    print("self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        default=["docs/status/archived", "docs/planning/archived"],
        help="files or directories to check (default: the archived snapshot dirs)",
    )
    parser.add_argument(
        "--sections",
        default="b,c,f,g",
        help="comma-separated open-work section letters (default: b,c,f,g)",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run the negative arms"
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    sections = {letter for letter in args.sections.split(",") if letter}
    files: list[Path] = []
    for entry in args.paths:
        path = Path(entry)
        if path.is_dir():
            files.extend(sorted(path.glob("*.md")))
        elif path.exists():
            files.append(path)

    total = 0
    for path in files:
        for line_number, text in unmarked_items(path, sections):
            print(f"{path}:{line_number}: unmarked scoped item: {text[:100]}")
            total += 1
    print(f"{len(files)} files checked, {total} unmarked scoped item(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
