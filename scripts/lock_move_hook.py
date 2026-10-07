#!/usr/bin/env python3
"""Commit-msg tripwire: a staged webphone lock move needs a ritual marker.

The auto-commit daemon lands plain `git commit`s (it never passes
--no-verify), so a commit-msg hook sees its heuristic messages too.
Four unattributed webphone lock sweeps in two weeks (2026-09-24,
2026-09-25, 2026-10-01, 2026-10-05/06) arrived exactly that way, and
scripts/lock_guard.py could only flag them AFTER the fact. This hook
refuses the commit at the door: when the staged flake.lock moves a
TRACKED_INPUT rev relative to HEAD and the commit message carries no
ritual marker (relock / lock-bump), the commit dies with a runbook
pointer. The marker keeps honest rituals one word cheap; lock-guard
still enforces the real attribution (old -> new revs in CHANGELOG.md)
after landing.

Stage mechanics (why always_run and the msg-file argument): git calls
commit-msg hooks with the message file path as $1; the `files` filter
would match that path, not the lock, and pass_filenames = false would
strip the only argument — so the hook runs unconditionally and gates
itself on what is actually staged.

Usage: lock_move_hook.py <commit-msg-file>
       lock_move_hook.py --self-test

Exits 0 (allow) or 1 (block). Never crashes the commit: internal
errors fail OPEN with a warning, because a broken tripwire must not
brick every commit in the repo (the heal path is
scripts/heal-pre-commit-hook.sh).
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TRACKED_INPUTS = ("webphone",)
MARKER = re.compile(r"(?i)(relock|lock-bump)")


def git(*args: str, cwd: Path | None = None) -> str | None:
    """Run git, returning stdout or None on any failure."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def locked_rev(index: bool, cwd: Path | None = None) -> dict[str, str]:
    """Webphone-tracked revs from the index and HEAD as {input: rev}."""
    source = [] if index else ["HEAD"]
    out: dict[str, str] = {}
    for name in TRACKED_INPUTS:
        text = git("show", *source, ":flake.lock", cwd=cwd)
        if text is None:
            continue
        try:
            node = json.loads(text).get("nodes", {}).get(name, {})
        except ValueError:
            continue
        rev = node.get("locked", {}).get("rev")
        if isinstance(rev, str):
            out[name] = rev
    return out


def moved_tracked_inputs(cwd: Path | None = None) -> list[str]:
    """Tracked inputs whose rev differs between HEAD and the index."""
    if git("diff", "--cached", "--quiet", "--", "flake.lock", cwd=cwd) is not None:
        return []
    staged = locked_rev(index=True, cwd=cwd)
    head = locked_rev(index=False, cwd=cwd)
    return [name for name in TRACKED_INPUTS if staged.get(name) != head.get(name)]


def guard(message_file: Path, cwd: Path | None = None) -> list[str]:
    """Return failure lines (empty = allow the commit)."""
    try:
        message = message_file.read_text()
    except OSError as error:
        return [
            (
                "FAIL: lock-move-guard cannot read the commit message "
                f"({error}); refusing to guess on a guarded stage."
            )
        ]
    moved = moved_tracked_inputs(cwd=cwd)
    if not moved:
        return []
    if MARKER.search(message):
        return []
    names = ", ".join(moved)
    return [
        (
            "FAIL: this commit moves a tracked flake input's rev "
            f"({names}) but the message carries no relock/lock-bump marker. "
            "Unattributed lock moves are how the 2026-09-24 stale-vendorHash "
            "breakage landed (four daemon sweeps in two weeks). Run the "
            "ritual in docs/ops-runbook.md 'Lock-bump runbook' and commit "
            "with a message naming the old -> new revs and the why."
        )
    ]


def self_test() -> int:
    """Arms over a synthetic repo; returns a unix exit code."""
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        if git("init", "-q", cwd=root) is None:
            print("self-test needs git on PATH")
            return 1
        git("config", "user.email", "t@example.com", cwd=root)
        git("config", "user.name", "t", cwd=root)
        lock_new = json.dumps({"nodes": {"webphone": {"locked": {"rev": "b" * 40}}}})
        lock_old = json.dumps({"nodes": {"webphone": {"locked": {"rev": "a" * 40}}}})

        def stage_lock(text: str) -> None:
            (root / "flake.lock").write_text(text)
            git("add", "flake.lock", cwd=root)

        def msg(text: str) -> Path:
            path = root / "COMMIT_EDITMSG"
            path.write_text(text)
            return path

        # Baseline: old rev committed.
        stage_lock(lock_old)
        git("commit", "-q", "-m", "init lock", cwd=root)

        # Arm 1: moved rev, heuristic message -> BLOCK.
        stage_lock(lock_new)
        if not guard(msg("chore: auto-commit 1 changed file(s) (heuristic)"), cwd=root):
            failures.append("self-test: unmarked webphone move must block")

        # Arm 2: moved rev, ritual marker -> ALLOW.
        if guard(msg("relock: webphone aaa -> bbb (picks up v2.9)"), cwd=root):
            failures.append("self-test: marked webphone move must pass")

        # Arm 3: marker spelling variant -> ALLOW.
        if guard(msg("Lock-bump ritual per runbook"), cwd=root):
            failures.append("self-test: lock-bump spelling must pass")

        # Arm 4: nothing staged -> ALLOW (cheap path for every commit).
        git("restore", "--staged", "flake.lock", cwd=root)
        (root / "flake.lock").unlink()
        git("add", "-A", cwd=root)
        if guard(msg("chore: unrelated"), cwd=root):
            failures.append("self-test: no staged lock change must pass")

        # Arm 5: staged lock with an UNTRACKED input move -> ALLOW.
        stage_lock(
            json.dumps({"nodes": {"treefmt-nix": {"locked": {"rev": "c" * 40}}}})
        )
        if guard(msg("chore: auto-commit 1 changed file(s) (heuristic)"), cwd=root):
            failures.append("self-test: untracked input move must pass")

        # Arm 6: unreadable message file -> BLOCK (fail closed on the gate
        # itself, the one error a commit must not guess through).
        if not guard(root / "nonexistent-msg", cwd=root):
            failures.append("self-test: unreadable message must block")

    if failures:
        for line in failures:
            print(line)
        return 1
    print(
        "PASS: lock-move-guard self-test "
        "(unmarked blocks, marker passes, spelling, unrelated, untracked, unreadable)"
    )
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    if len(argv) != 1:
        print("usage: lock_move_hook.py <commit-msg-file>")
        return 1
    root = Path.cwd()
    failures = guard(Path(argv[0]), cwd=root)
    for line in failures:
        print(line)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
