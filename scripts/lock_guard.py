#!/usr/bin/env python3
"""Lock-move guard: tracked flake inputs must be attributed in CHANGELOG.md.

Lock moves in this repo historically landed through the auto-commit
daemon's heuristic messages with no attribution anywhere (the 2026-09-24
stale-vendorHash breakage and the two same-day 2026-09-30 webphone moves
are the incident class; the relock ritual in docs/ops-runbook.md is the
process fix). This script makes an unattributed move a gate error
instead: every TRACKED input's locked revision must be nameable in
CHANGELOG.md — any section, so a release that moves the mention into a
dated heading does not false-positive — as a backticked (or plain) hex
prefix of the full rev, at least MIN_PREFIX characters.

Only inputs listed in TRACKED_INPUTS are governed: the webphone input
tracks upstream main (a lock bump can import breakage the same day), so
its moves need a hand-authored record naming old → new rev and why.
Routine sweeps over the leaf tooling inputs (treefmt-nix, flake-parts,
flake-compat — same-rev aliases of each other) stay ungoverned on
purpose; extend TRACKED_INPUTS only when an input starts riding a moving
upstream.

Why a file-diff gate and not git archaeology: the flake check runs
against the store source with no .git, so the guard compares two committed
files that both live in that source (flake.lock ↔ CHANGELOG.md) — the
same two-file pattern as tests/drift_alarm.py.

Usage: lock_guard.py [flake.lock] [CHANGELOG.md]
       lock_guard.py --self-test

Defaults resolve relative to this script's repo root (correct for local
runs); the flake check passes store paths explicitly.
"""

import json
import re
import sys
import tempfile
from pathlib import Path

TRACKED_INPUTS = ("webphone",)
# A rev mention must carry at least this many leading hex characters of
# the full rev (GitHub short-rev shape; shorter prefixes could name a
# different commit by accident).
MIN_PREFIX = 7
HEX = re.compile(r"^[0-9a-f]+$")


def locked_rev(lock: dict, input_name: str) -> str | None:
    node = lock.get("nodes", {}).get(input_name, {})
    return node.get("locked", {}).get("rev")


def rev_mentioned(changelog: str, rev: str) -> bool:
    """True when the changelog names a >=MIN_PREFIX hex prefix of rev."""
    for length in range(len(rev), MIN_PREFIX - 1, -1):
        prefix = rev[:length]
        if prefix in changelog:
            return True
    return False


def guard(lock_path: Path, changelog_path: Path) -> list[str]:
    """Return a list of failure lines (empty = clean)."""
    failures = []
    try:
        lock = json.loads(lock_path.read_text())
    except (OSError, ValueError) as error:
        return [f"FAIL: cannot parse {lock_path}: {error}"]
    try:
        changelog = changelog_path.read_text()
    except OSError as error:
        return [f"FAIL: cannot read {changelog_path}: {error}"]
    for name in TRACKED_INPUTS:
        rev = locked_rev(lock, name)
        if rev is None or not HEX.match(rev):
            failures.append(
                f"FAIL: tracked input {name!r} carries no hex rev in {lock_path} "
                "(renamed input? update TRACKED_INPUTS in scripts/lock_guard.py)"
            )
            continue
        if not rev_mentioned(changelog, rev):
            failures.append(
                f"FAIL: tracked input {name!r} sits at rev {rev[:12]}, but "
                f"CHANGELOG.md never mentions it — a lock move without a "
                "hand-authored record is how the 2026-09-24 stale-vendorHash "
                "breakage landed silently. Add the old → new revs (and why) "
                "to CHANGELOG.md [Unreleased]; see docs/ops-runbook.md "
                "'Lock-bump runbook'."
            )
    return failures


def self_test() -> int:
    """Negative tests for every arm; return a unix exit code."""
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        lock = {
            "nodes": {
                "webphone": {"locked": {"rev": "0e1d1743629600b1"}},
                "nixpkgs": {"locked": {"rev": "7a0f122f50900000"}},
            }
        }
        lock_path = root / "flake.lock"
        lock_path.write_text(json.dumps(lock))

        clean = root / "CHANGELOG-clean.md"
        clean.write_text(
            "## [Unreleased]\n- Relock: webphone `a8868fd` -> `0e1d174`, picks up v2.8.0.\n"
        )
        if guard(lock_path, clean):
            failures.append("self-test: attributed rev must pass")

        missing = root / "CHANGELOG-missing.md"
        missing.write_text(
            "## [Unreleased]\n- Relock: webphone `a8868fd` -> `93d3a53`.\n"
        )
        if not guard(lock_path, missing):
            failures.append("self-test: unattributed new rev must fail")

        dated = root / "CHANGELOG-dated.md"
        dated.write_text(
            "## [0.3.0] 2026-09-30\n- Relock: webphone `0e1d174` (v2.8.0).\n"
        )
        if guard(lock_path, dated):
            failures.append(
                "self-test: attribution in a dated release section must pass"
            )

        short = root / "CHANGELOG-short.md"
        short.write_text(
            "## [Unreleased]\n- Relock: webphone -> `0e1d17` (too short).\n"
        )
        if not guard(lock_path, short):
            failures.append("self-test: a prefix shorter than MIN_PREFIX must fail")

        moved_input = {
            "nodes": {"webphone-renamed": {"locked": {"rev": "0e1d1743629600b1"}}}
        }
        moved_path = root / "flake-moved.json"
        moved_path.write_text(json.dumps(moved_input))
        if not guard(moved_path, clean):
            failures.append("self-test: tracked input missing from the lock must fail")

        if not guard(root / "nonexistent.lock", clean):
            failures.append("self-test: unreadable lock must fail (not crash)")

    if failures:
        for line in failures:
            print(line)
        return 1
    print(
        "PASS: lock-guard self-test (attributed, unattributed, dated, short, renamed, unreadable)"
    )
    return 0


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    root = Path(__file__).resolve().parent.parent
    lock_path = Path(argv[0]) if len(argv) > 0 else root / "flake.lock"
    changelog_path = Path(argv[1]) if len(argv) > 1 else root / "CHANGELOG.md"
    failures = guard(lock_path, changelog_path)
    for line in failures:
        print(line)
    if not failures:
        tracked = ", ".join(TRACKED_INPUTS)
        print(f"PASS: lock-move guard clean (tracked inputs attributed: {tracked})")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
