#!/usr/bin/env python3
"""Fail when one CHANGELOG version repeats a `### <type>` heading.

Keep-a-Changelog style groups entries under headings like `### Added` /
`### Fixed`. The 2026-08 docs-health audit found a release section that
had grown TWO `### Added` blocks (merged since); readers and tooling
assume one per section per version. This lint makes the decay a commit-
time error instead of an audit finding.

Usage: changelog_headings.py CHANGELOG.md
"""

import sys

VERSION = "## ["
SECTION = "### "


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    current_version = None
    seen: dict[str, list[str]] = {}
    duplicates: list[tuple[str, str]] = []
    for line in open(sys.argv[1]):
        line = line.rstrip("\n")
        if line.startswith(VERSION):
            current_version = line
        elif line.startswith(SECTION) and current_version:
            seen.setdefault(current_version, [])
            if line in seen[current_version]:
                duplicates.append((current_version, line))
            else:
                seen[current_version].append(line)
    if duplicates:
        print("FAIL: repeated section headings inside one CHANGELOG version")
        for version, heading in duplicates:
            print(f"  {version} has a second {heading}")
        print("Merge the blocks; one heading per type per version.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
