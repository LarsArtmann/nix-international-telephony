#!/usr/bin/env python3
"""Archive-time checklist for status/planning snapshots: annotate →
gate → move, in that order, mechanically.

The 2026-10-12 round-10 sweep proved the ordering matters: annotation
and archiving interleaved by hand left a `| ID |` header flagged as an
unmarked item and a check-rows pass nobody ran. This script makes the
order the only path:

1. preflight — the file is tracked and lives in docs/status/ or
   docs/planning/ (never already archived);
2. content gate — `markers_check.py <file>` must be clean (every
   scoped item carries a verdict; the file-level monotonicity arm
   runs too);
3. row-uniformity gate — `annotate.go check-rows` when the docs-health
   skill checkout is available (GO toolchain + ANNOTATE_GO env or the
   default ~/.config/crush path); otherwise a loud skip (the ordering
   guarantee degrades honestly, it does not silently pass);
4. `git mv` into the sibling archived/ dir;
5. post-move gates over the archived file — markers_check (now with
   the per-item arm baselined) and rendering_audit (including the
   incident triangle).

Exit status: 0 = archived and gates green, 1 = findings (refusals and
gate failures), 2 = usage/self-test failure.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANNOTATE_GO = (
    Path.home() / ".config/crush/skills/docs-health/assets/annotate.go"
)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)


def find_annotate_go() -> Path | None:
    """The docs-health skill's annotator, if its checkout is reachable."""
    candidate = os.environ.get("ANNOTATE_GO")
    paths = [Path(candidate)] if candidate else [DEFAULT_ANNOTATE_GO]
    go = _run(["go", "version"])
    for path in paths:
        if go.returncode == 0 and path.exists():
            return path
    return None


def archive_snapshot(path: Path, repo_root: Path = REPO_ROOT) -> int:
    """Run the checklist for one snapshot; 0 = archived, 1 = refused."""
    abs_path = path.resolve()
    try:
        rel = abs_path.relative_to(repo_root.resolve())
    except ValueError:
        print(f"{path}: refuse: outside the repository {repo_root}")
        return 1
    parts = rel.parts
    if (
        len(parts) != 3
        or parts[0] != "docs"
        or parts[1] not in ("status", "planning")
        or parts[1] + "/archived" in str(rel)
    ):
        print(f"{rel}: refuse: not a docs/status|planning snapshot")
        return 1
    probe = _run(
        ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", str(rel)]
    )
    if probe.returncode != 0:
        print(
            f"{rel}: refuse: not tracked (git add first — untracked files are "
            "invisible to the flake)"
        )
        return 1

    gate = _run(
        [sys.executable, str(repo_root / "scripts/markers_check.py"), str(rel)],
        cwd=repo_root,
    )
    if gate.returncode != 0:
        print(
            f"{rel}: content gate RED (annotate first — every scoped item "
            "needs a verdict):"
        )
        print(gate.stdout.strip())
        return 1

    annotate_go = find_annotate_go()
    if annotate_go is None:
        print(
            f"{rel}: check-rows skipped (annotator or go toolchain not "
            "found; set ANNOTATE_GO)"
        )
    else:
        rows = _run(
            ["go", "run", str(annotate_go), "check-rows", str(rel)],
            cwd=repo_root,
        )
        if rows.returncode != 0:
            print(f"{rel}: row-uniformity gate RED:")
            print(rows.stdout.strip())
            return 1

    archived_rel = rel.parent / "archived" / rel.name
    move = _run(
        ["git", "-C", str(repo_root), "mv", str(rel), str(archived_rel)]
    )
    if move.returncode != 0:
        print(f"{rel}: git mv failed: {move.stderr.strip()}")
        return 1
    print(f"{rel}: moved to {archived_rel}")

    post = _run(
        [
            sys.executable,
            str(repo_root / "scripts/markers_check.py"),
            str(archived_rel),
        ],
        cwd=repo_root,
    )
    if post.returncode != 0:
        print(f"{archived_rel}: post-move markers gate RED:")
        print(post.stdout.strip())
        return 1
    render = _run(
        [
            sys.executable,
            str(repo_root / "scripts/rendering_audit.py"),
            str(archived_rel),
        ],
        cwd=repo_root,
    )
    if render.returncode != 0:
        print(f"{archived_rel}: post-move rendering gate RED:")
        print(render.stdout.strip())
        return 1
    print(f"{archived_rel}: archived, gates green")
    return 0


def _synthetic_repo(root: Path) -> Path:
    """A minimal repo with the gate scripts and the triangle files."""
    repo = root / "repo"
    (repo / "docs/status/archived").mkdir(parents=True)
    (repo / "docs/lessons").mkdir()
    (repo / "scripts").mkdir()
    for script in ("markers_check.py", "rendering_audit.py"):
        (repo / "scripts" / script).write_text(
            (REPO_ROOT / "scripts" / script).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (repo / "CHANGELOG.md").write_text(
        "5ba5d2b 04562e787 row 36\n", encoding="utf-8"
    )
    (repo / "AGENTS.md").write_text(
        "docs/lessons/markdown-normalization.md scripts/markers_check.py "
        "scripts/rendering_audit.py per-item (post-archive revisions only)\n",
        encoding="utf-8",
    )
    (repo / "docs/lessons/markdown-normalization.md").write_text(
        "5ba5d2b 04562e787 row 36\n", encoding="utf-8"
    )
    return repo


def self_test() -> int:
    """Negative arms on a synthetic repo: an unmarked snapshot is
    refused BEFORE any move; a fully marked one moves and passes."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = _synthetic_repo(Path(tmp))
        _git = lambda *a: _run(  # noqa: E731
            ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *a]
        )
        snapshot = repo / "docs/status/2026-10-12_demo-snapshot.md"
        snapshot.write_text(
            "## b) OPEN\n1. unmarked thing\n", encoding="utf-8"
        )
        _git("init", "-q")
        _git("add", "-A")
        _git("commit", "-q", "-m", "seed")

        refused = archive_snapshot(snapshot, repo_root=repo)
        assert refused == 1, "unmarked snapshot was not refused"
        assert snapshot.exists(), "refused snapshot was moved anyway"
        assert not (snapshot.parent / "archived" / snapshot.name).exists(), (
            "refusal left an archived copy"
        )

        snapshot.write_text(
            "## b) OPEN\n1. marked thing → done — landed\n", encoding="utf-8"
        )
        _git("add", "-A")
        _git("commit", "-q", "-m", "annotate")
        moved = archive_snapshot(snapshot, repo_root=repo)
        assert moved == 0, "marked snapshot failed the checklist"
        assert not snapshot.exists(), "snapshot not moved"
        archived = snapshot.parent / "archived" / snapshot.name
        assert archived.exists(), "no archived copy"

    print("self-test: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "Exit status: 0 = archived and gates green; 1 = findings "
            "(refusals and gate failures); 2 = usage/self-test failure."
        ),
    )
    parser.add_argument(
        "snapshot", type=Path, nargs="?", help="the docs/status|planning snapshot to archive"
    )
    parser.add_argument("--self-test", action="store_true", help="run the negative arms")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    if args.snapshot is None:
        parser.error("a snapshot path is required unless --self-test")
    return archive_snapshot(args.snapshot)


if __name__ == "__main__":
    sys.exit(main())
