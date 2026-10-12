#!/usr/bin/env python3
"""Residual rendering audit over archived status/planning snapshots.

The marker gates prove marker COUNTS, not rendering: a normalization
pass can mangle markdown so strikes and asides RENDER as code or plain
text while every marker still counts. This sweep checks the documented
damage classes from the two normalization incidents (CHANGELOG
2026-09-29/30):

* fence class — a line starting with ``~~~`` (a CommonMark fence
  opener; auto-commit `04562e787` turned a strike tail into a fenced
  code block this way), and files whose ``` fences do not pair up;
* strike class — a strikethrough still open at a paragraph boundary
  (GFM strikes cannot cross blank lines, headings, list or table
  starts, so legal multi-line strikes stay silent and a swallowed
  closer fires);
* (del class retired: the .md archives carry no real ``<del>``
  markup -- only prose MENTIONS of the tag, e.g. "marker forms incl.
  HTML <del>", which a parity check cannot separate from markup; the
  HTML-era snapshots self-resolved inline in their own era.)
* emphasis class — a table row carrying an odd number of ``**``
  (single-line rows make bold parity meaningful).

The live run also asserts the INCIDENT TRIANGLE: every archive-damage
incident's identifying hash/keyword must appear in BOTH the CHANGELOG
and ``docs/lessons/markdown-normalization.md``, and the AGENTS.md
marker paragraph must reference the lesson and both gate scripts —
three homes, one story, no split brain (the round-11 F51/F52 rows
shipped this as a standing check because the triangle was asserted
nowhere).

Exit status: 0 = no rendering damage found, 1 = findings, 2 =
usage/self-test failure. Repairs follow the house grammar: append-only
restorations in fence-immune shapes, never rewrites (a marker-count
repair must also keep the monotonicity arms green).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FENCE_RE = re.compile(r"^\s*(```|~~~)")
TILDE_FENCE_RE = re.compile(r"^~~~")
STRIKE_RE = re.compile(r"~~")
EMPHASIS_RE = re.compile(r"\*\*")
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")

INCIDENTS: list[tuple[str, str]] = [
    # (id substring, what it was) — one row per archive-damage incident;
    # a new incident means a new row here PLUS its CHANGELOG and lesson
    # mentions (that triangle is the point of this check).
    ("5ba5d2b", "verdict-column drop (2026-09-29)"),
    ("04562e787", "fence destruction (2026-09-29)"),
    ("row36", "partial-repair residue found by the per-item arm (2026-10-12)"),
]


def _norm(text: str) -> str:
    """Lowercase alphanumerics only, so 'row 36' and 'row-36' match."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def triangle_findings(repo_root: Path) -> list[str]:
    """Incident-triangle + docstring-vs-AGENTS split-brain assertions."""
    results: list[str] = []
    changelog = _norm(
        (repo_root / "CHANGELOG.md").read_text(encoding="utf-8", errors="replace")
    )
    lesson_path = repo_root / "docs" / "lessons" / "markdown-normalization.md"
    lesson = (
        lesson_path.read_text(encoding="utf-8", errors="replace")
        if lesson_path.exists()
        else ""
    )
    agents = _norm(
        (repo_root / "AGENTS.md").read_text(encoding="utf-8", errors="replace")
    )
    markers_doc = _norm(
        (repo_root / "scripts" / "markers_check.py").read_text(
            encoding="utf-8", errors="replace"
        )
    )
    for incident_id, what in INCIDENTS:
        needle = _norm(incident_id)
        if needle not in _norm(lesson):
            results.append(
                f"triangle: incident {incident_id} ({what}) missing from "
                "docs/lessons/markdown-normalization.md"
            )
        if needle not in changelog:
            results.append(
                f"triangle: incident {incident_id} ({what}) missing from CHANGELOG.md"
            )
    if "markdownnormalizationmd" not in agents:
        results.append(
            "split-brain: AGENTS.md does not reference docs/lessons/markdown-normalization.md"
        )
    for gate in ("markerscheckpy", "renderingauditpy"):
        if gate not in agents:
            results.append(f"split-brain: AGENTS.md does not reference scripts/{gate}")
    if "postarchive" not in markers_doc:
        results.append(
            "split-brain: markers_check.py docstring lost the per-item post-archive scope"
        )
    if "postarchive" not in agents:
        results.append(
            "split-brain: AGENTS.md lost the per-item post-archive scope wording"
        )
    return results


def _outside_code_spans(line: str) -> str:
    """Line with single-line inline code spans removed (their content is
    literal text: the fence-immune repair shape keeps a `~~` in a code
    span on purpose)."""
    return re.sub(r"`[^`]*`", "", line)


def findings_for(text: str) -> list[str]:
    """(rendering-class) findings for one snapshot's text. Strikes are
    checked per PARAGRAPH (GFM strikethrough cannot cross blank lines,
    headings, list or table starts), so legal multi-line strikes stay
    silent."""
    results: list[str] = []
    in_fence = False
    fence_marker = ""
    strike_open = 0
    boundary_re = re.compile(r"^\s*(?:#|-|\*|\+|\d+\.\s|\||$)")

    def boundary(line: str) -> bool:
        return bool(boundary_re.match(line))

    for number, line in enumerate(text.splitlines(), start=1):
        fence = FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            if not in_fence:
                in_fence, fence_marker = True, marker[0]
            elif marker[0] == fence_marker:
                in_fence, fence_marker = False, ""
                continue
            continue
        if in_fence:
            continue
        plain = _outside_code_spans(line)
        if strike_open and boundary(plain):
            results.append(
                f"{number}: strike class: strikethrough still open at a paragraph boundary (a closer was swallowed?)"
            )
            strike_open = 0
        if TILDE_FENCE_RE.match(plain):
            results.append(
                f"{number}: fence class: line starts with '~~~' (CommonMark fence where a strike was meant?)"
            )
        strike_open ^= len(STRIKE_RE.findall(plain)) % 2
        if TABLE_ROW_RE.match(line) and len(EMPHASIS_RE.findall(plain)) % 2 == 1:
            results.append(f"{number}: emphasis class: odd '**' count in a table row")
    if strike_open:
        results.append("eof: strike class: strikethrough still open at eof")
    if in_fence:
        results.append("eof: fence class: unclosed code fence")
    return results


def self_test() -> int:
    """Positive and negative arms: every documented class must fire, the
    accepted shapes (fence-immune repairs, paired strikes, real fences,
    inline code tildes) must stay silent."""
    cases: list[tuple[str, str, bool]] = [
        ("clean snapshot", "## b) OPEN\n1. ~~thing~~ done at `abc`\n", False),
        (
            "fence-immune repaired strike",
            "1. ~~slow~~ done — `~~ ~2.2x faster` measured\n",
            False,
        ),
        (
            "deliberate code fence",
            "```\nstrikethrough ~~not rendered~~ here\n```\n",
            False,
        ),
        ("inline-code tildes", "run `a ~~ b` on the CLI\n", False),
        ("inline-code del mention", "resolved via `<del>` + evidence rows\n", False),
        ("prose del mention", "marker forms incl. HTML <del> in old cells\n", False),
        (
            "legal multi-line strike",
            "1. ~~wrapped item\n   continues here~~ done at `abc`\n",
            False,
        ),
        ("line-start tilde fence", "~~~2.2x faster than the baseline\n", True),
        ("unclosed strike", "1. ~~thing never closed\n", True),
        ("strike open across a blank line", "1. ~~opened here\n\n2. next item\n", True),
        ("unclosed code fence", "```\nnever closed\n", True),
        ("odd emphasis in row", "| 7 | a **bold row | x |\n", True),
    ]
    for name, text, want in cases:
        got = findings_for(text)
        assert bool(got) == want, (
            f"{name}: want {'finding' if want else 'clean'}, got {got}"
        )
    print("self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "Exit status: 0 = no rendering damage found; 1 = findings "
            "(fence/strike/emphasis classes); 2 = usage/self-test "
            "failure."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["docs/status/archived", "docs/planning/archived"],
        help="files or directories to audit (default: the archived snapshot dirs)",
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run the negative arms"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="repository root for the incident-triangle check (default: cwd)",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    files: list[Path] = []
    for entry in args.paths:
        path = Path(entry)
        if path.is_dir():
            files.extend(sorted(path.glob("*.md")))
        elif path.exists():
            files.append(path)

    total = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        for finding in findings_for(text):
            print(f"{path}:{finding}")
            total += 1
    for finding in triangle_findings(args.repo_root):
        print(f"triangle: {finding}")
        total += 1
    print(f"{len(files)} files audited, {total} finding(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
