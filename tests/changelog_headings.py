#!/usr/bin/env python3
"""Fail when one CHANGELOG version repeats a `### <type>` heading.

Keep-a-Changelog style groups entries under headings like `### Added` /
`### Fixed`. The 2026-08 docs-health audit found a release section that
had grown TWO `### Added` blocks (merged since); readers and tooling
assume one per section per version. This lint makes the decay a commit-
time error instead of an audit finding.

Usage: changelog_headings.py CHANGELOG.md
       changelog_headings.py --self-test
"""

import sys
import tempfile
from pathlib import Path

VERSION = "## ["
SECTION = "### "


def duplicates_in(text: str) -> list[tuple[str, str]]:
    """Return (version heading, repeated section heading) pairs."""
    current_version = None
    seen: dict[str, list[str]] = {}
    duplicates: list[tuple[str, str]] = []
    for line in text.splitlines():
        if line.startswith(VERSION):
            current_version = line
        elif line.startswith(SECTION) and current_version:
            seen.setdefault(current_version, [])
            if line in seen[current_version]:
                duplicates.append((current_version, line))
            else:
                seen[current_version].append(line)
    return duplicates


def self_test() -> int:
    """Negative + positive arms over synthetic changelogs."""
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        clean = Path(tmp) / "clean.md"
        clean.write_text(
            "## [Unreleased]\n### Added\n- one\n### Fixed\n- two\n"
            "## [0.1.0] 2026-01-01\n### Added\n- three\n"
        )
        if duplicates_in(clean.read_text()):
            failures.append("self-test: distinct headings must pass")

        decayed = Path(tmp) / "decayed.md"
        decayed.write_text(
            "## [Unreleased]\n### Added\n- one\n### Fixed\n- two\n"
            "### Added\n- merged-since block\n"
        )
        if not duplicates_in(decayed.read_text()):
            failures.append("self-test: a repeated heading must fail")

        scoped = Path(tmp) / "scoped.md"
        scoped.write_text(
            "## [Unreleased]\n### Added\n- one\n"
            "## [0.1.0] 2026-01-01\n### Added\n- two\n"
        )
        if duplicates_in(scoped.read_text()):
            failures.append(
                "self-test: the same heading in different versions must pass"
            )

        preamble = Path(tmp) / "preamble.md"
        preamble.write_text("### Added\nbefore any version heading\n")
        if duplicates_in(preamble.read_text()):
            failures.append("self-test: pre-version headings are out of scope")

    if failures:
        for line in failures:
            print(line)
        return 1
    print("PASS: changelog-headings self-test (clean, decayed, scoped, preamble)")
    return 0


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        text = Path(sys.argv[1]).read_text()
    except OSError as error:
        print(f"FAIL: cannot read {sys.argv[1]}: {error}")
        return 1
    duplicates = duplicates_in(text)
    if duplicates:
        print("FAIL: repeated section headings inside one CHANGELOG version")
        for version, heading in duplicates:
            print(f"  {version} has a second {heading}")
        print("Merge the blocks; one heading per type per version.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
