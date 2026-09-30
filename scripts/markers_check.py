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

Monotonicity arm: the count of verdict markers (``MARKER_RE`` matches)
in each checked file may never permanently decrease across its git
history (``git log --follow``, renames included). This is the net for
the 5ba5d2b incident class: a table normalization dropped a verdict
column while a prose arrow masked the loss from the content sweep. A
decrease that a later commit repairs back to the historical peak stays
silent -- restoration-by-append is the house remedy -- so the arm flags
exactly "markers lost and never restored at HEAD". It needs a git repo;
without one (e.g. the sandboxed flake check, whose source tree has no
.git) the arm skips with a notice and the self-test's synthetic-repo
arms carry the CI proof instead.

Exit status: 0 = every scoped item marked and no unrepaired verdict
loss, 1 = findings (unmarked items and/or marker-count decreases),
2 = usage/self-test failure.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
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


def marker_count(text: str) -> int:
    """Number of verdict markers in one file revision."""
    return len(MARKER_RE.findall(text))


def _repo_toplevel(start: Path) -> Path | None:
    """Git toplevel containing `start`, or None outside a repo."""
    probe = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return None
    return Path(probe.stdout.strip())


@dataclass(frozen=True)
class _Revision:
    commit: str
    subject: str
    path: str
    count: int


_REV_HEADER_RE = re.compile(r"^@([0-9a-f]{40}) (.*)$")


def _parse_name_status(log: str) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """(commit, subject, [(status, src, dst)]) blocks, newest first, from
    `git log --follow --format='@%H %s' --name-status` output."""
    blocks: list[tuple[str, str, list[tuple[str, str, str]]]] = []
    commit = subject = None
    entries: list[tuple[str, str, str]] = []
    for line in log.splitlines():
        header = _REV_HEADER_RE.match(line)
        if header:
            if commit is not None:
                blocks.append((commit, subject, entries))
            commit, subject, entries = header.group(1), header.group(2), []
        elif commit is not None and line and "\t" in line:
            parts = line.split("\t")
            status = parts[0]
            if status[:1] in ("R", "C") and len(parts) >= 3:
                entries.append((status[:1], parts[1], parts[2]))
            elif len(parts) >= 2:
                entries.append((status[:1], parts[1], parts[1]))
    if commit is not None:
        blocks.append((commit, subject, entries))
    return blocks


def _history_chain(repo: Path, path: str) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """Name-status blocks for `path` back through renames, newest first."""
    log = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "log",
            "--follow",
            "--format=@%H %s",
            "--name-status",
            "--",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if log.returncode != 0:
        raise RuntimeError(f"git log --follow {path}: {log.stderr.strip()}")
    return _parse_name_status(log.stdout)


def history_counts(repo: Path, path: str) -> list[_Revision]:
    """Marker count per commit for `path`, oldest first, across renames."""
    chain = _history_chain(repo, path)
    revisions: list[_Revision] = []
    tracked = path
    for commit, subject, entries in chain:
        blob = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit}:{tracked}"],
            capture_output=True,
            text=True,
        )
        if blob.returncode != 0:
            raise RuntimeError(f"git show {commit}:{tracked}: {blob.stderr.strip()}")
        revisions.append(_Revision(commit, subject, tracked, marker_count(blob.stdout)))
        for status, source, destination in entries:
            if destination == tracked:
                if status in ("R", "C"):
                    tracked = source
                elif status == "A":
                    return list(reversed(revisions))
    return list(reversed(revisions))


def monotonicity_findings(revisions: list[_Revision]) -> list[str]:
    """Findings for verdict-count decreases never repaired back to the peak."""
    if len(revisions) < 2:
        return []
    peak = revisions[0].count
    peak_revision = revisions[0]
    decreases: list[str] = []
    for revision in revisions[1:]:
        if revision.count < peak:
            decreases.append(
                f"{peak} -> {revision.count} at {revision.commit[:12]} ({revision.subject})"
            )
        if revision.count > peak:
            peak, peak_revision = revision.count, revision
    if not decreases or revisions[-1].count >= peak:
        return []
    return [
        "verdict markers lost and never restored: peak "
        f"{peak} ({peak_revision.commit[:12]} {peak_revision.subject}); "
        "decreases: " + "; ".join(decreases)
    ]


def _git(repo: Path, *args: str) -> str:
    """Run git with a fixed identity; raise on failure, return stdout."""
    probe = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.email=markers-check@local",
            "-c",
            "user.name=markers-check",
            *args,
        ],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {probe.stderr.strip()}")
    return probe.stdout


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

        # --- monotonicity arms ------------------------------------------
        # Pure-function arms over fabricated revision chains.
        def rev(count: int, label: str = "x") -> _Revision:
            return _Revision("0" * 40, label, "f.md", count)

        assert monotonicity_findings([rev(2), rev(3)]) == [], "increase flagged"
        assert monotonicity_findings([rev(3), rev(3)]) == [], "flat flagged"
        assert monotonicity_findings([rev(3)]) == [], "single revision flagged"
        assert monotonicity_findings([rev(3), rev(2), rev(4)]) == [], (
            "repaired dip flagged"
        )
        dips = monotonicity_findings([rev(3, "seed"), rev(1, "drop"), rev(2, "part")])
        assert len(dips) == 1 and "3 -> 1" in dips[0] and "never restored" in dips[0], (
            dips
        )

        # Synthetic-repo arm: real git history, rename, and the 5ba5d2b
        # incident shape (verdict column dropped, prose arrow survives).
        with tempfile.TemporaryDirectory() as git_tmp:
            repo = Path(git_tmp) / "repo"
            repo.mkdir()
            snapshot = repo / "snapshot.md"
            snapshot.write_text(
                "## b) OPEN\n"
                "1. one → done — a\n"
                "2. two → done — b\n"
                "3. three → done — c\n",
                encoding="utf-8",
            )
            _git(repo, "init", "-q")
            _git(repo, "add", ".")
            _git(repo, "commit", "-q", "-m", "seed three verdicts")
            assert _repo_toplevel(repo) == repo.resolve(), "toplevel arm"
            assert _repo_toplevel(repo.parent) is None, "non-repo arm"

            snapshot.write_text(
                snapshot.read_text(encoding="utf-8") + "4. four → done — d\n",
                encoding="utf-8",
            )
            _git(repo, "add", ".")
            _git(repo, "commit", "-q", "-m", "append fourth verdict")
            # git log simplifies away commits not touching the path, so the
            # flat arm is a real edit that keeps the count (formatting etc.).
            snapshot.write_text(
                snapshot.read_text(encoding="utf-8") + "\nClosing prose, no markers.\n",
                encoding="utf-8",
            )
            _git(repo, "add", ".")
            _git(repo, "commit", "-q", "-m", "reformat without verdict change")
            revisions = history_counts(repo, "snapshot.md")
            assert [r.count for r in revisions] == [3, 4, 4], revisions
            assert monotonicity_findings(revisions) == [], "increase/flat flagged"

            # The incident: verdict column dropped from rows 1-2 while a
            # prose arrow in row 1 masks the loss from the content sweep.
            snapshot.write_text(
                "## b) OPEN\n"
                "1. one → new --flag prose survives\n"
                "2. two plain continuation text\n"
                "3. three → done — c\n"
                "4. four → done — d\n",
                encoding="utf-8",
            )
            _git(repo, "add", ".")
            _git(repo, "commit", "-q", "-m", "normalization drops verdicts")
            revisions = history_counts(repo, "snapshot.md")
            findings = monotonicity_findings(revisions)
            assert len(findings) == 1 and "4 -> 3" in findings[0], findings

            # House remedy: restore in-cell (append grammar), count recovers.
            snapshot.write_text(
                "## b) OPEN\n"
                "1. one → new --flag prose survives → done — restored\n"
                "2. two plain continuation text → done — restored\n"
                "3. three → done — c\n"
                "4. four → done — d\n",
                encoding="utf-8",
            )
            _git(repo, "add", ".")
            _git(repo, "commit", "-q", "-m", "restore verdicts in-cell")
            assert monotonicity_findings(history_counts(repo, "snapshot.md")) == [], (
                "repaired incident flagged"
            )

            # Rename then a fresh unrepaired drop: --follow must keep the
            # chain (and the per-revision paths) intact across the move.
            _git(repo, "mv", "snapshot.md", "archived-snapshot.md")
            _git(repo, "commit", "-q", "-m", "archive: git mv")
            revisions = history_counts(repo, "archived-snapshot.md")
            assert [r.count for r in revisions] == [3, 4, 4, 3, 5, 5], revisions
            assert [r.path for r in revisions] == ["snapshot.md"] * 5 + [
                "archived-snapshot.md"
            ], revisions
            assert monotonicity_findings(revisions) == [], "rename flagged"
            snapshot = repo / "archived-snapshot.md"
            snapshot.write_text(
                snapshot.read_text(encoding="utf-8").replace(
                    "3. three → done — c\n", "3. three bare\n"
                ),
                encoding="utf-8",
            )
            _git(repo, "add", ".")
            _git(repo, "commit", "-q", "-m", "post-archive verdict loss")
            revisions = history_counts(repo, "archived-snapshot.md")
            findings = monotonicity_findings(revisions)
            assert len(findings) == 1 and "5 -> 4" in findings[0], findings

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
    parser.add_argument(
        "--no-monotonicity",
        action="store_true",
        help="skip the git-history verdict-count monotonicity arm",
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

    mono_skipped = ""
    if args.no_monotonicity:
        mono_skipped = "disabled via --no-monotonicity"
    else:
        repo = _repo_toplevel(Path.cwd())
        if repo is None:
            mono_skipped = "not a git repository (e.g. the sandboxed flake check)"
        else:
            for path in files:
                try:
                    repo_path = path.resolve().relative_to(repo).as_posix()
                except ValueError:
                    print(f"{path}: monotonicity arm: outside the repository, skipped")
                    continue
                try:
                    revisions = history_counts(repo, repo_path)
                except RuntimeError as error:
                    print(f"{path}: monotonicity arm error: {error}")
                    total += 1
                    continue
                for finding in monotonicity_findings(revisions):
                    print(f"{path}: monotonicity: {finding}")
                    total += 1
    if mono_skipped:
        print(f"monotonicity arm: skipped ({mono_skipped})")
    print(f"{len(files)} files checked, {total} finding(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
