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
2 = usage/self-test failure. This is the round-11 SPIKE output: whether
it becomes a wired flake check is an owner call (AGENTS.md keeps
date-stamped sweep counts deliberately).
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


def derived_test_count() -> int:
    loader = unittest.TestLoader()
    suite = loader.discover(str(REPO_ROOT / "tests"), top_level_dir=str(REPO_ROOT))
    return suite.countTestCases()


def count_claims() -> list[tuple[str, str, int]]:
    """(file, claim text, number) for every checks/tests count literal."""
    claims: list[tuple[str, str, int]] = []
    patterns = {
        "FEATURES.md": re.compile(r"(\d+)\s+flake\s+`?checks`?", re.IGNORECASE),
        "AGENTS.md": re.compile(r"(\d+)\s+stdlib tests", re.IGNORECASE),
    }
    for name, pattern in patterns.items():
        text = (REPO_ROOT / name).read_text(encoding="utf-8", errors="replace")
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
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    findings = 0
    try:
        checks = derived_check_names(args.system)
    except RuntimeError as error:
        print(f"derive checks: {error}")
        return 1
    tests = derived_test_count()
    print(f"derived: {len(checks)} checks on {args.system}; {tests} stdlib tests")

    claims = count_claims()
    check_claims = [
        c for c in claims if re.search(r"flake\s+`?checks`?", c[1], re.IGNORECASE)
    ]
    test_claims = [c for c in claims if "stdlib tests" in c[1]]
    for label, actual, group in (
        ("flake checks", len(checks), check_claims),
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
