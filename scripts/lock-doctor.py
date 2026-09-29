#!/usr/bin/env python3
"""Lock doctor: mechanize the ~10 manual gh/nix invocations of a lock review.

For every github-backed flake input:
  * locked rev vs the upstream HEAD of its tracked ref (behind-by count)
For this repository's own CI:
  * the last COMPLETED verdict for the current HEAD — a canceled run is
    reported as "no verdict", never red (house rule 2026-09-29: GitHub
    runner-shutdown cancellations are infrastructure, not code failures;
    three in a row on this repo alone).

Usage:
  scripts/lock-doctor.py            # full report
  scripts/lock-doctor.py --self-test

Exit codes: 0 = report produced (stale tracked inputs are information,
not failure); 1 = repo HEAD has a completed RED verdict or no verdict at
all; 2 = tool/environment problems (no gh, offline, broken lock).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

NO_VERDICT_NOTE = (
    "canceled runs are infra, not code — check the log tail for a runner "
    "shutdown signal before trusting any completed failure"
)


def load_lock(path: Path) -> dict:
    return json.loads(path.read_text())


def github_inputs(lock: dict) -> list[dict]:
    """One entry per github-backed input node: name, slug, ref, rev.

    The tracking ref lives in `original` (locked dropped it in the
    current lock format); `original.rev` present means deliberately
    pinned — reported without a branch comparison.
    """
    entries: list[dict] = []
    for name, node in sorted(lock.get("nodes", {}).items()):
        if name == "root":
            continue
        locked = node.get("locked", {})
        original = node.get("original", {})
        if locked.get("type") != "github":
            continue
        entries.append(
            {
                "name": name,
                "slug": f"{locked['owner']}/{locked['repo']}",
                "ref": locked.get("ref") or original.get("ref"),
                "rev": locked.get("rev", ""),
                "pinned": original.get("rev") is not None,
            }
        )
    return entries


def dedupe(entries: list[dict]) -> list[dict]:
    """Aliased inputs (flake-parts_2, …) share slug+rev: collapse them."""
    by_key: dict[tuple, dict] = {}
    for entry in entries:
        key = (entry["slug"], entry["ref"], entry["rev"])
        if key in by_key:
            by_key[key]["name"] += f" (+{entry['name']})"
        else:
            by_key[key] = dict(entry)
    return sorted(by_key.values(), key=lambda e: e["name"])


def gh(args: list[str]) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)}: {proc.stderr.strip()}")
    return proc.stdout


def upstream_head(slug: str, ref: str | None) -> tuple[str, str]:
    """(head_sha, resolved_ref) for the tracked ref (default branch if None)."""
    target = ref if ref else "HEAD"
    out = gh(["api", f"repos/{slug}/commits/{target}", "--jq", ".sha"])
    return out.strip(), (ref or "default branch")


def behind_by(slug: str, locked: str, head: str) -> int | None:
    """Commits upstream HEAD carries beyond the locked rev (base...head
    ahead_by — behind_by is the opposite direction and reads 0 for every
    ancestor, which made everything look current once)."""
    if locked == head:
        return 0
    out = gh(
        [
            "api",
            f"repos/{slug}/compare/{locked}...{head}",
            "--jq",
            ".ahead_by",
        ]
    )
    try:
        return int(out.strip())
    except ValueError:
        return None


def repo_slug() -> str:
    out = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    out = out.removesuffix(".git")
    return "/".join(out.split(":")[-1].split("/")[-2:])


def classify_verdict(runs: list[dict], head: str) -> str:
    """GREEN / RED / NO VERDICT for HEAD from newest-first run list."""
    for run in runs:
        if run.get("headSha") != head:
            continue
        if run.get("status") != "completed":
            return f"NO VERDICT (run {run['databaseId']} still {run['status']})"
        conclusion = run.get("conclusion")
        if conclusion == "success":
            return f"GREEN (run {run['databaseId']})"
        if conclusion in ("cancelled", "canceled"):
            return f"NO VERDICT (run {run['databaseId']} canceled — {NO_VERDICT_NOTE})"
        if conclusion == "failure":
            return f"RED (run {run['databaseId']} — read the failed step log before blaming code)"
        return f"UNKNOWN conclusion {conclusion!r} (run {run['databaseId']})"
    return "NO VERDICT (no CI run for this HEAD yet)"


def self_test() -> int:
    fixture = {
        "nodes": {
            "root": {},
            "webphone": {
                "locked": {
                    "type": "github",
                    "owner": "LarsArtmann",
                    "repo": "webphone",
                    "rev": "abc1234",
                    "ref": "main",
                }
            },
            "nixpkgs": {
                "locked": {
                    "type": "github",
                    "owner": "NixOS",
                    "repo": "nixpkgs",
                    "rev": "def5678",
                }
            },
            "local": {"locked": {"type": "path", "path": "/x"}},
        }
    }
    entries = dedupe(github_inputs(fixture))
    assert [e["slug"] for e in entries] == [
        "NixOS/nixpkgs",
        "LarsArtmann/webphone",
    ], entries
    assert entries[1]["ref"] == "main"
    assert entries[0]["pinned"] is False
    runs = [
        {
            "headSha": "h2",
            "status": "completed",
            "conclusion": "cancelled",
            "databaseId": 2,
        },
        {
            "headSha": "h1",
            "status": "completed",
            "conclusion": "success",
            "databaseId": 1,
        },
        {"headSha": "h3", "status": "in_progress", "conclusion": None, "databaseId": 3},
    ]
    assert classify_verdict(runs, "h1") == "GREEN (run 1)"
    assert "NO VERDICT" in classify_verdict(runs, "h2")
    assert "still in_progress" in classify_verdict(runs, "h3")
    assert "no CI run" in classify_verdict(runs, "h9")
    print("self-test: ok")
    return 0


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return self_test()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()
    lock_path = Path(root) / "flake.lock"
    if not lock_path.exists():
        print(f"lock-doctor: {lock_path} missing", file=sys.stderr)
        return 2
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()

    print(f"== locked inputs vs upstream ({lock_path.name}) ==")
    stale = 0
    for entry in dedupe(github_inputs(load_lock(lock_path))):
        if entry["pinned"]:
            print(
                f"  {entry['name']:<24} {entry['slug']:<40} "
                f"{entry['rev'][:9]} pinned (no branch comparison)"
            )
            continue
        try:
            head_sha, ref_name = upstream_head(entry["slug"], entry["ref"])
        except (RuntimeError, OSError) as err:
            print(f"  {entry['name']:<24} {entry['slug']}: unreachable ({err})")
            continue
        count = behind_by(entry["slug"], entry["rev"], head_sha)
        if count == 0:
            state = "up to date"
        elif count is None:
            state = "LOCKED REV NOT COMPARABLE (force-push upstream?)"
            stale += 1
        else:
            state = f"{count} commit(s) behind {ref_name}"
            stale += 1
        print(
            f"  {entry['name']:<24} {entry['slug']:<40} "
            f"{entry['rev'][:9]} -> {head_sha[:9]}  {state}"
        )

    print(f"== CI verdict for HEAD {head[:9]} ==")
    verdict = "NO VERDICT (gh unavailable)"
    try:
        runs = json.loads(
            gh(
                [
                    "run",
                    "list",
                    "--repo",
                    repo_slug(),
                    "--branch",
                    "main",
                    "--limit",
                    "30",
                    "--json",
                    "headSha,status,conclusion,databaseId",
                ]
            )
        )
        verdict = classify_verdict(runs, head)
    except (RuntimeError, OSError, json.JSONDecodeError) as err:
        print(f"  gh query failed: {err}", file=sys.stderr)
    print(f"  {verdict}")

    if verdict.startswith("RED") or verdict.startswith("NO VERDICT"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
