#!/usr/bin/env python3
"""Derive the living docs' count claims from the repo instead of trusting
hand-maintained literals (docs-health BUILD rule: "prefer a standing gate
that re-derives doc numbers").

Derives today:
* flake checks (per system) via `nix eval`;
* the stdlib test count via unittest discovery over tests/;
* the pytest-module method count (subset of the above, informative).

Compares them against the count claims in FEATURES.md and AGENTS.md and
reports every mismatch. Exit status: 0 = every derived count matches a
claim, 1 = at least one mismatch (update the docs — the code wins),
2 = usage/self-test failure. (Wired as the doc-counts flake check since
2026-11-07; this docstring keeps the origin note.)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def derived_check_names(system: str) -> list[str]:
    out = subprocess.run(
        [
            "nix",
            "eval",
            f".#checks.{system}",
            "--apply",
            "builtins.attrNames",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    if out.returncode != 0:
        raise RuntimeError(f"nix eval checks.{system}: {out.stderr.strip()[:400]}")
    return sorted(json.loads(out.stdout))


def derived_test_count(repo_root: Path = REPO_ROOT) -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(str(repo_root / "tests"), top_level_dir=str(repo_root))
    return suite.countTestCases()


def count_claims(repo_root: Path = REPO_ROOT) -> list[tuple[str, str, int]]:
    """(file, claim text, number) for every checks/tests count literal."""
    claims: list[tuple[str, str, int]] = []
    patterns = {
        "FEATURES.md": re.compile(r"(\d+)\s+flake\s+`?checks`?", re.IGNORECASE),
        "AGENTS.md": re.compile(r"(\d+)\s+stdlib tests", re.IGNORECASE),
    }
    for name, pattern in patterns.items():
        text = (repo_root / name).read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            claims.append((name, match.group(0).strip(), int(match.group(1))))
    return claims


def self_test() -> int:
    """The claim scanners must find the seeded literals and nothing else."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "FEATURES.md").write_text(
            "- 43 flake `checks` re-derived 2026-10-12; no other checks\n",
            encoding="utf-8",
        )
        (root / "AGENTS.md").write_text(
            "# 169 stdlib tests across six modules; checks: 42 flake checks\n",
            encoding="utf-8",
        )
        found = _claims_in(root)
        assert ("FEATURES.md", "43 flake `checks`", 43) in found, found
        assert ("AGENTS.md", "169 stdlib tests", 169) in found, found
        assert all("42 flake checks" not in c[1] for c in found), found
    print("self-test: ok")
    return 0


def _claims_in(root: Path) -> list[tuple[str, str, int]]:
    claims: list[tuple[str, str, int]] = []
    patterns = {
        "FEATURES.md": re.compile(r"(\d+)\s+flake\s+`?checks`?", re.IGNORECASE),
        "AGENTS.md": re.compile(r"(\d+)\s+stdlib tests", re.IGNORECASE),
    }
    for name, pattern in patterns.items():
        text = (root / name).read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            claims.append((name, match.group(0).strip(), int(match.group(1))))
    return claims


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "Exit status: 0 = every derived count matches a doc claim; "
            "1 = at least one mismatch (update the docs); 2 = "
            "usage/self-test failure."
        ),
    )
    parser.add_argument("--system", default="x86_64-linux")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="tree holding tests/ + FEATURES.md + AGENTS.md "
        "(the flake check passes a store copy; default: this checkout)",
    )
    parser.add_argument(
        "--check-count",
        type=int,
        default=None,
        help="flake checks count provided by the caller (the wired flake "
        "check passes its own attrNames count — a sandboxed check cannot "
        "run nix eval); default: derive via nix eval",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    findings = 0
    if args.check_count is None:
        try:
            checks = derived_check_names(args.system)
        except RuntimeError as error:
            print(f"derive checks: {error}")
            return 1
        check_count = len(checks)
    else:
        check_count = args.check_count
    tests = derived_test_count(args.repo_root)
    print(f"derived: {check_count} checks on {args.system}; {tests} stdlib tests")

    claims = count_claims(args.repo_root)
    check_claims = [
        c for c in claims if re.search(r"flake\s+`?checks`?", c[1], re.IGNORECASE)
    ]
    test_claims = [c for c in claims if "stdlib tests" in c[1]]
    for label, actual, group in (
        ("flake checks", check_count, check_claims),
        ("stdlib tests", tests, test_claims),
    ):
        for file, text, number in group:
            status = "ok" if number == actual else "MISMATCH"
            print(f"{file}: '{text}' -> {number} ({status}; derived {actual})")
            if number != actual:
                findings += 1
        if not group:
            print(
                f"no '{label}' claim found in FEATURES.md/AGENTS.md (add one or drop the claim class)"
            )
    return 1 if findings else 0


if __name__ == "__main__":
    import tempfile

    sys.exit(main())
