#!/usr/bin/env python3
"""Single home for the tracked-input set: the flake inputs whose lock
moves are GOVERNED (CHANGELOG attribution required — lock_guard.py) and
whose commits are BLOCKED without a relock marker (lock_move_hook.py,
the commit-msg stage). Keep every consumer importing THIS list — the
2026-10-07 class was two drifted copies of the same tuple.

Sandbox note: the flake's lock-guard / lock-move-guard checks pass
PYTHONPATH=${./scripts} so `import tracked_inputs` resolves against the
store copy; CLI and pre-commit runs resolve it via the script's own
directory on sys.path.
"""

TRACKED_INPUTS = ("webphone", "pbx-lens")
