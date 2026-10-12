"""Stdlib tests for the marker gates: scripts/markers_check.py,
scripts/rendering_audit.py, and the incident triangle between
CHANGELOG, the markdown-normalization lesson and AGENTS.md.

Runs with the stdlib only:

    cd "$(git rev-parse --show-toplevel)" && python3 -m unittest discover -s tests -v

The scripts carry their own --self-test arms (the flake's
checks.markers-check runs those); this module ports the load-bearing
arms into the BuildFlow pytest lane so the gates cannot rot without a
test noticing, and adds the ID-header regression arm and the
exit-code/docstring parity check explicitly.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The flake check interpolates THIS file as a single store file, so
# __file__ cannot discover the source tree there — GATE_REPO_ROOT wins.
REPO_ROOT = Path(
    os.environ.get("GATE_REPO_ROOT") or Path(__file__).resolve().parents[1]
)
SECTIONS = {"b", "c", "f", "g"}


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / rel)
    assert spec is not None and spec.loader is not None, rel
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves types via sys.modules
    spec.loader.exec_module(module)
    return module


markers = _load("markers_check_gate", "scripts/markers_check.py")
rendering = _load("rendering_audit_gate", "scripts/rendering_audit.py")


class TestMarkersCheckArms(unittest.TestCase):
    """The planted-miss arms, ported from markers_check.self_test."""

    def test_full_self_test_passes(self):
        self.assertEqual(markers.self_test(), 0)

    def test_id_header_row_is_not_an_item(self):
        # Regression (2026-10-12): a `| ID |`-headed Step-2 M-table must
        # not flag its HEADER row as one unmarked item; the DATA rows
        # must still be scoped.
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "## Step 2 — comprehensive plan\n"
                "| ID  | Task |\n"
                "| --- | ---- |\n"
                "| M01 | marked row → done — landed |\n"
                "| M02 | bare plan row |\n",
                encoding="utf-8",
            )
            hits = markers.unmarked_items(plan, SECTIONS)
            self.assertEqual([line for line, _ in hits], [5])

    def test_verdict_on_following_line_clears_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "r.md"
            report.write_text(
                "## b) PARTIALLY DONE\n1. Thing one\n   → done — landed\n",
                encoding="utf-8",
            )
            self.assertEqual(markers.unmarked_items(report, SECTIONS), [])

    def test_bare_numbered_item_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "r.md"
            report.write_text(
                "## g) QUESTIONS\n1. An unanswered question\n", encoding="utf-8"
            )
            hits = markers.unmarked_items(report, SECTIONS)
            self.assertEqual(len(hits), 1)

    def test_step3_fine_rows_stay_out_of_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(
                "## Step 2\n| M01 | marked → done |\n"
                "## Step 3\n| f01 | bare fine row inherits |\n",
                encoding="utf-8",
            )
            self.assertEqual(markers.unmarked_items(plan, SECTIONS), [])


class TestPerItemMonotonicity(unittest.TestCase):
    """The count-preserving evasion class, in pure-function form."""

    def test_flat_chain_silent(self):
        counts = {"b:#1": 1, "b:#2": 1}
        self.assertEqual(
            markers.item_monotonicity_findings(
                [("a", "x", counts), ("b", "y", counts)]
            ),
            [],
        )

    def test_strip_from_one_item_flagged(self):
        findings = markers.item_monotonicity_findings(
            [
                ("a", "seed", {"b:#1": 1, "b:#2": 1}),
                ("b", "strip", {"b:#1": 1, "b:#2": 0}),
            ]
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("b:#2", findings[0])

    def test_recovery_by_append_clears(self):
        self.assertEqual(
            markers.item_monotonicity_findings(
                [
                    ("a", "seed", {"b:#2": 1}),
                    ("b", "strip", {"b:#2": 0}),
                    ("c", "restore", {"b:#2": 1}),
                ]
            ),
            [],
        )

    def test_deleted_row_is_the_file_arms_net(self):
        self.assertEqual(
            markers.item_monotonicity_findings(
                [
                    ("a", "seed", {"b:#1": 1, "b:#2": 1}),
                    ("b", "deleted", {"b:#1": 1}),
                ]
            ),
            [],
        )


class TestExitCodeParity(unittest.TestCase):
    """Docstring, --help and the module must agree on 0/1/2."""

    def test_help_lists_all_three_codes(self):
        for script in ("markers_check.py", "rendering_audit.py"):
            out = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / script), "--help"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            self.assertIn("Exit status", out, script)
            for code in ("0", "1", "2"):
                self.assertIn(f"{code} =", out, f"{script}: exit code {code}")

    def test_docstrings_state_the_same_semantics(self):
        for module in (markers, rendering):
            self.assertIn("Exit status", module.__doc__, module.__name__)
            self.assertIn("self-test", module.__doc__, module.__name__)


class TestRenderingAudit(unittest.TestCase):
    def test_full_self_test_passes(self):
        self.assertEqual(rendering.self_test(), 0)

    def test_fenced_strike_tail_is_caught(self):
        # The 04562e787 incident shape: a strike tail at line start is a
        # CommonMark fence opener and must fire.
        self.assertTrue(rendering.findings_for("~~~2.2x faster\n"))

    def test_clean_corpus_is_silent(self):
        self.assertEqual(rendering.findings_for("1. ~~thing~~ done at `abc`\n"), [])


class TestIncidentTriangle(unittest.TestCase):
    """Every archive-damage incident closes across CHANGELOG, lesson and
    AGENTS.md; the gate scripts agree with AGENTS on arm semantics."""

    def test_triangle_holds_at_head(self):
        self.assertEqual(rendering.triangle_findings(REPO_ROOT), [])


if __name__ == "__main__":
    unittest.main()
