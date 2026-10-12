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

Per-item monotonicity arm: the file-level count nets to equal when a
verdict is REMOVED from one surviving item and a new verdict appears
ELSEWHERE in the file (a prose aside, a different item) in the same
commit -- the count-preserving evasion class. This arm counts verdict
markers per scoped ITEM (same line-plus-block attribution as the
content sweep), keyed by "<section>:<item identity>" (``#N`` for
numbered items, the first table cell for rows), and flags a key whose
count permanently drops below its peak. Scope: POST-ARCHIVE history
only (revisions from the first commit whose path contains
``/archived/``). While a snapshot is live, verdicts legitimately move,
get deduplicated (the 2026-08-22 verdict-twin cleanup) and are
superseded -- the content sweep plus check-rows govern that state; once
archived, ANY permanent per-item decrease is damage (the 2026-09-18
row-36 verdict-cell drop, repaired to only one of its two markers).
Files with no archived revision in history (open snapshots checked
explicitly) skip the arm. Only keys still present at HEAD are tracked
-- a row deleted wholesale loses the file count and remains the
file-level arm's net -- and repeated first cells across tables in one
section merge into one key (masking, never false flagging: a merge
hides losses, it cannot invent them).

Exit status: 0 = every scoped item marked and no unrepaired verdict
loss (file or per-item), 1 = findings (unmarked items and/or marker-
count decreases), 2 = usage/self-test failure.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

SECTION_RE = re.compile(r"^## ([a-g])\)")
PLAN_STEP2_RE = re.compile(r"^## Step 2\b")
ITEM_RE = re.compile(r"^\s{0,3}(?:\d+\.\s|\|)")
HEADER_ROW_RE = re.compile(
    r"^\|\s*(?:#|ID|Item|What|Task|Nr?|Aspect|Area|Layer|Name|Phase|Step|Cat)\s*\|",
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
        check=False,
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
    current: tuple[str, str, list[tuple[str, str, str]]] | None = None
    for line in log.splitlines():
        header = _REV_HEADER_RE.match(line)
        if header:
            if current is not None:
                blocks.append(current)
            current = (header.group(1), header.group(2), [])
        elif current is not None and line and "\t" in line:
            parts = line.split("\t")
            status = parts[0]
            if status[:1] in ("R", "C") and len(parts) >= 3:
                current[2].append((status[:1], parts[1], parts[2]))
            elif len(parts) >= 2:
                current[2].append((status[:1], parts[1], parts[1]))
    if current is not None:
        blocks.append(current)
    return blocks


def _history_chain(
    repo: Path, path: str
) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
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
        check=False,
    )
    if log.returncode != 0:
        raise RuntimeError(f"git log --follow {path}: {log.stderr.strip()}")
    return _parse_name_status(log.stdout)


def history_texts(repo: Path, path: str) -> list[tuple[str, str, str, str]]:
    """(commit, subject, tracked_path, blob_text) per commit for `path`,
    oldest first, back through renames."""
    chain = _history_chain(repo, path)
    texts: list[tuple[str, str, str, str]] = []
    tracked = path
    for commit, subject, entries in chain:
        blob = subprocess.run(
            ["git", "-C", str(repo), "show", f"{commit}:{tracked}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if blob.returncode != 0:
            raise RuntimeError(f"git show {commit}:{tracked}: {blob.stderr.strip()}")
        texts.append((commit, subject, tracked, blob.stdout))
        born = False
        for status, source, destination in entries:
            if destination != tracked:
                continue
            if status in ("R", "C"):
                tracked = source
            elif status == "A":
                born = True
        if born:
            break
    texts.reverse()
    return texts


def history_counts(
    repo: Path, path: str, disk_path: Path | None = None
) -> list[_Revision]:
    """Marker count per commit for `path`, oldest first, across renames.

    With `disk_path`, the newest revision reflects the working tree so a
    repair that is not yet committed already satisfies the gate (the
    content sweep reads disk too)."""
    revisions = [
        _Revision(commit, subject, tracked, marker_count(text))
        for commit, subject, tracked, text in history_texts(repo, path)
    ]
    if disk_path is not None and disk_path.exists() and revisions:
        revisions[-1] = replace(
            revisions[-1],
            commit="worktree",
            subject="uncommitted working tree",
            count=marker_count(
                disk_path.read_text(encoding="utf-8", errors="replace")
            ),
        )
    return revisions


def history_marker_stats(
    repo: Path,
    path: str,
    sections: set[str],
    disk_path: Path | None = None,
) -> tuple[list[_Revision], list[tuple[str, str, dict[str, int]]], int | None]:
    """File-level and per-item marker counts per commit in ONE git walk
    (the per-item arm must not double the sweep's git-show traffic);
    same `disk_path` worktree semantics as history_counts. The third
    element is the index of the first ARCHIVED revision (path contains
    "/archived/"), or None while the file has no archived revision --
    the per-item arm slices from it (post-archive scope)."""
    texts = history_texts(repo, path)
    revisions = [
        _Revision(commit, subject, tracked, marker_count(text))
        for commit, subject, tracked, text in texts
    ]
    items = [
        (commit, subject, item_counts(text, sections))
        for commit, subject, _, text in texts
    ]
    archived_index: int | None = None
    for index, (_, _, tracked, _) in enumerate(texts):
        if "/archived/" in tracked:
            archived_index = index
            break
    if disk_path is not None and disk_path.exists() and revisions:
        worktree_text = disk_path.read_text(encoding="utf-8", errors="replace")
        revisions[-1] = replace(
            revisions[-1],
            commit="worktree",
            subject="uncommitted working tree",
            count=marker_count(worktree_text),
        )
        items[-1] = (
            "worktree",
            "uncommitted working tree",
            item_counts(worktree_text, sections),
        )
    return revisions, items, archived_index


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


def item_key(line: str) -> str | None:
    """Item identity: ``#N`` for numbered items, first table cell for rows."""
    numbered = re.match(r"^\s{0,3}(\d+)\.\s", line)
    if numbered:
        return f"#{numbered.group(1)}"
    row = line.strip()
    if row.startswith("|"):
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if cells and cells[0]:
            return cells[0]
    return None


def item_counts(text: str, sections: set[str]) -> dict[str, int]:
    """Verdict markers per scoped item (own line plus its trailing block,
    the content sweep's attribution), keyed "<section>:<identity>"."""
    lines = text.splitlines()
    counts: dict[str, int] = {}
    section: str | None = None
    current_key: str | None = None
    for line in lines:
        heading = SECTION_RE.match(line)
        if heading:
            section = heading.group(1)
            current_key = None
            continue
        if PLAN_STEP2_RE.match(line):
            section = "step2"
            current_key = None
            continue
        if line.startswith("## "):
            section = None
            current_key = None
            continue
        if (
            (section in sections or section == "step2")
            and ITEM_RE.match(line)
            and not HEADER_ROW_RE.match(line)
            and not SEPARATOR_ROW_RE.match(line)
            and line.strip() not in ("|", "---")
        ):
            key = item_key(line)
            current_key = f"{section}:{key}" if key else None
            if current_key:
                counts.setdefault(current_key, 0)
        if (section in sections or section == "step2") and current_key:
            counts[current_key] += len(MARKER_RE.findall(line))
    return counts


def item_monotonicity_findings(
    revisions: list[tuple[str, str, dict[str, int]]],
) -> list[str]:
    """Findings for per-item verdict losses never repaired back to the
    item's peak. Callers pass the POST-ARCHIVE slice only (see
    history_marker_stats): while a snapshot is live, verdict dedup and
    supersede are the annotator's business. Only keys present in the
    newest revision are tracked: a row deleted wholesale drops the FILE
    count (the file-level arm's net), while the count-preserving evasion
    class keeps the row and strips its verdict -- exactly the shape this
    arm catches."""
    if len(revisions) < 2:
        return []
    newest = revisions[-1][2]
    findings: list[str] = []
    for key in sorted(newest):
        peak: int | None = None
        peak_revision: tuple[str, str] | None = None
        decreases: list[str] = []
        for commit, subject, counts in revisions:
            count = counts.get(key, 0)
            if peak is None or count > peak:
                peak, peak_revision = count, (commit, subject)
            elif count < peak:
                decreases.append(
                    f"{peak} -> {count} at {commit[:12]} ({subject})"
                )
        if decreases and newest[key] < peak:
            assert peak_revision is not None
            findings.append(
                f"{key}: verdict markers lost and never restored: peak "
                f"{peak} ({peak_revision[0][:12]} {peak_revision[1]}); "
                "decreases: " + "; ".join(decreases)
            )
    return findings


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
        check=False,
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
            "| ID | header with an ID first cell | x |\n"
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

            # An uncommitted repair already satisfies the gate: the newest
            # point reads the working tree, like the content sweep does.
            snapshot.write_text(
                snapshot.read_text(encoding="utf-8").replace(
                    "3. three bare\n", "3. three → done — restored\n"
                ),
                encoding="utf-8",
            )
            assert (repo / "archived-snapshot.md").read_text(encoding="utf-8").count(
                "→"
            ) == 5, "repair did not restore five arrows"
            assert monotonicity_findings(
                history_counts(repo, "archived-snapshot.md")
            ) == [findings[0]], "HEAD-only view changed"
            assert (
                monotonicity_findings(
                    history_counts(repo, "archived-snapshot.md", disk_path=snapshot)
                )
                == []
            ), "worktree-repaired file flagged"

        # --- per-item monotonicity arms ----------------------------------
        # Pure-function arms over fabricated per-item chains.
        def irev(counts: dict[str, int], label: str = "x"):
            return ("0" * 40, label, counts)

        sections = {"b", "c", "f", "g"}
        assert item_counts(
            "## a) DONE\n1. achievements stay bare\n", sections
        ) == {}, "out-of-scope section counted"
        assert item_counts(
            "## f) NEXT\n| ID | header |\n| --- | --- |\n| 7 | → done |\n", sections
        ) == {"f:7": 1}, "header or separator leaked into per-item counts"
        assert item_counts(
            "## f) NEXT\n| 3 | bare row\n   block verdict → done — x\n", sections
        ) == {"f:3": 1}, "block verdict not attributed to its item"
        assert item_monotonicity_findings(
            [irev({"b:#1": 1, "b:#2": 1}), irev({"b:#1": 1, "b:#2": 1})]
        ) == [], "flat per-item chain flagged"
        evasions = item_monotonicity_findings(
            [
                irev({"b:#1": 1, "b:#2": 1}, "seed"),
                irev({"b:#1": 1, "b:#2": 0}, "strip"),
            ]
        )
        assert len(evasions) == 1 and "b:#2" in evasions[0], evasions
        assert item_monotonicity_findings(
            [
                irev({"b:#1": 1, "b:#2": 1}, "seed"),
                irev({"b:#1": 1, "b:#2": 0}, "strip"),
                irev({"b:#1": 1, "b:#2": 1}, "restore"),
            ]
        ) == [], "repaired per-item loss flagged"
        # A key absent from the newest revision (row deleted wholesale)
        # is the FILE arm's net -- the per-item arm must stay silent.
        assert item_monotonicity_findings(
            [
                irev({"b:#1": 1, "b:#2": 1}, "seed"),
                irev({"b:#1": 1}, "row deleted"),
            ]
        ) == [], "deleted row flagged by the per-item arm"

        # Synthetic-repo arm for the count-preserving evasion class:
        # strip one item's verdict and add a compensating prose arrow in
        # the same commit -- the file count stays flat (file arm blind),
        # the per-item count drops for the stripped item. PRE-archive
        # the same shape stays silent (live-file churn is out of scope).
        with tempfile.TemporaryDirectory() as git_tmp:
            repo2 = Path(git_tmp) / "repo"
            repo2.mkdir()
            (repo2 / "archived").mkdir()
            snapshot2 = repo2 / "snapshot.md"
            snapshot2.write_text(
                "## b) OPEN\n"
                "1. one → done — a\n"
                "2. two → done — b\n",
                encoding="utf-8",
            )
            _git(repo2, "init", "-q")
            _git(repo2, "add", ".")
            _git(repo2, "commit", "-q", "-m", "seed two verdicts")
            # Live-file churn: verdict moves + dedup are the annotator's
            # business while the snapshot is open -- per-item silent.
            snapshot2.write_text(
                "Intro aside: also → done, see notes.\n"
                "\n"
                "## b) OPEN\n"
                "1. one → done — a\n"
                "2. two bare after a rewrite\n",
                encoding="utf-8",
            )
            _git(repo2, "add", ".")
            _git(repo2, "commit", "-q", "-m", "count-preserving verdict move")
            _, items_live, live_archived_index = history_marker_stats(
                repo2, "snapshot.md", sections
            )
            assert live_archived_index is None, live_archived_index
            assert item_monotonicity_findings(
                items_live[live_archived_index:]
                if live_archived_index is not None
                else []
            ) == [], "pre-archive churn flagged"
            # Archive it; the archived state is the per-item baseline.
            _git(repo2, "mv", "snapshot.md", "archived/snapshot.md")
            _git(repo2, "commit", "-q", "-m", "archive: git mv")
            _, items_archived, archived_index = history_marker_stats(
                repo2, "archived/snapshot.md", sections
            )
            assert archived_index is not None and archived_index >= 0
            assert item_monotonicity_findings(
                items_archived[archived_index:]
            ) == [], "single archived revision flagged"
            # Post-archive count-preserving strip: now it is damage.
            snapshot2 = repo2 / "archived" / "snapshot.md"
            snapshot2.write_text(
                "Intro aside: also → done, see notes.\n"
                "\n"
                "## b) OPEN\n"
                "1. one → done — a\n"
                "2. two bare after a normalization pass\n",
                encoding="utf-8",
            )
            _git(repo2, "add", ".")
            _git(repo2, "commit", "-q", "-m", "post-archive verdict strip")
            revisions2, items2, archived_index2 = history_marker_stats(
                repo2, "archived/snapshot.md", sections
            )
            assert [r.count for r in revisions2] == [2, 2, 2], revisions2
            assert monotonicity_findings(revisions2) == [], (
                "file arm fired on a count-preserving move"
            )
            findings2 = item_monotonicity_findings(items2[archived_index2:])
            assert (
                len(findings2) == 1
                and "b:#2" in findings2[0]
                and "1 -> 0" in findings2[0]
            ), findings2

    print("self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "Exit status: 0 = every scoped item marked and no unrepaired "
            "verdict loss (file-level or per-item); 1 = findings (unmarked "
            "items and/or marker-count decreases); 2 = usage/self-test "
            "failure."
        ),
    )
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
                    revisions, items, archived_index = history_marker_stats(
                        repo, repo_path, sections, disk_path=path
                    )
                except RuntimeError as error:
                    print(f"{path}: monotonicity arm error: {error}")
                    total += 1
                    continue
                for finding in monotonicity_findings(revisions):
                    print(f"{path}: monotonicity: {finding}")
                    total += 1
                post_archive = (
                    items[archived_index:] if archived_index is not None else []
                )
                for finding in item_monotonicity_findings(post_archive):
                    print(f"{path}: per-item monotonicity: {finding}")
                    total += 1
    if mono_skipped:
        print(f"monotonicity arm: skipped ({mono_skipped})")
    print(f"{len(files)} files checked, {total} finding(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
