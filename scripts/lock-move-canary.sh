#!/usr/bin/env bash
# End-to-end lock-move tripwire canary (2026-11-07 hardening).
#
# The unit-level arms live in scripts/lock_move_hook.py --self-test
# (synthetic repo); THIS canary proves the tripwire through REAL git
# plumbing, the standard the 2026-10-07 hook-bypass postmortem set:
# a scratch clone gets the real commit-msg hook installed, plants an
# unmarked tracked-input lock move, and the commit must FAIL; the same
# move with a `relock:` marker must PASS.
#
# Scope: webphone (the tracked input every clone has in flake.lock).
# Everything happens in a mktemp scratch repo — the working tree is
# never touched.
#
# Exit codes: 0 both arms behaved; 1 the tripwire leaked or misfired;
# 2 usage/environment failure.
set -uo pipefail

repo="$(git rev-parse --show-toplevel 2>/dev/null)" || {
	echo "lock-move-canary: not inside a git repository" >&2
	exit 2
}

scratch="$(mktemp -d)"
FAILURES=0
cleanup() { rm -rf "$scratch"; }
trap cleanup EXIT

git clone -q "$repo" "$scratch/clone" || { echo "clone failed" >&2; exit 2; }
cd "$scratch/clone" || exit 2
git config user.email canary@example.invalid
git config user.name lock-move-canary

# Install BOTH hook stages the way the devshell installer would, but
# pointed at this repo's scripts (the clone has them — it cloned HEAD).
# ALSO anchor core.hooksPath locally: the global ~/.gitconfig points it
# at a nonexistent .githooks, and git would silently run NO hooks (the
# documented landmine — arm 1 proves the tripwire only with a correct
# anchor).
mkdir -p .git/hooks
git config core.hooksPath .git/hooks
cat > .git/hooks/commit-msg <<'HOOK'
#!/usr/bin/env bash
exec python3 "$(git rev-parse --show-toplevel)/scripts/lock_move_hook.py" "$1"
HOOK
chmod +x .git/hooks/commit-msg

# Arm 1: unmarked move must BLOCK.
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("flake.lock")
d = json.loads(p.read_text())
node = d["nodes"]["root"]["inputs"]["webphone"]
if isinstance(node, str):
    node = d["nodes"][node]
node["locked"]["rev"] = "0" * 40
node["locked"]["narHash"] = "sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
p.write_text(json.dumps(d, indent=2) + "\n")
PY
git add flake.lock
if git commit -q -m "chore: auto-commit (heuristic)" 2> /dev/null; then
	echo "FAIL: unmarked lock move COMMITTED — the tripwire leaked"
	FAILURES=$((FAILURES + 1))
else
	echo "PASS: unmarked lock move blocked at commit-msg"
fi
git reset -q --mixed HEAD 2>/dev/null || true

# Arm 2: the same move with a relock marker must PASS (the gate's
# purpose is attribution, not prohibition).
git add flake.lock
if git commit -q -m "chore(deps): relock webphone deadbeef -> 00000000 (canary)"; then
	echo "PASS: marker-attributed move committed"
else
	echo "FAIL: marker-attributed move BLOCKED — the tripwire misfires"
	FAILURES=$((FAILURES + 1))
fi

if [ "$FAILURES" -gt 0 ]; then
	echo "=== $FAILURES canary arm(s) RED"
	exit 1
fi
echo "=== lock-move canary green"
exit 0
