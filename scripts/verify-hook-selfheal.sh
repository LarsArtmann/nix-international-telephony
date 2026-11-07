#!/usr/bin/env bash
# Regression net for the pre-commit hook self-heal (2026-11-07 hardening).
#
# Proves, end to end, that the heal path leaves BOTH hook stages
# installed and executable:
#   1. post-install canary — after scripts/heal-pre-commit-hook.sh, the
#      pre-commit AND commit-msg hooks exist and are executable (a heal
#      that drops commit-msg silently disarms the lock-move tripwire);
#   2. negative arm — with both hooks moved away, the heal restores
#      them (the git-hooks.nix updater's strip-everything class);
#   3. the hooks' content still names the battery stages.
#
# Safe by construction: the negative arm ARCHIVES the working hooks
# first and restores them if the heal fails, so a red here never
# leaves the repo ungated.
#
# Exit codes: 0 every arm green; 1 at least one arm failed; 2 usage.
set -uo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
	echo "verify-hook-selfheal: not inside a git repository" >&2
	exit 2
}
cd "$root" || exit 2

hook=".git/hooks/pre-commit"
commit_msg_hook=".git/hooks/commit-msg"
archive="$(mktemp -d)"
FAILURES=0

cleanup() {
	# Last-resort restore so a failed run never leaves the repo ungated.
	if [ -x "$archive/pre-commit" ] && { [ ! -x "$hook" ] || [ ! -x "$commit_msg_hook" ]; }; then
		cp "$archive/pre-commit" "$hook" 2>/dev/null
		cp "$archive/commit-msg" "$commit_msg_hook" 2>/dev/null
		echo "verify-hook-selfheal: archived hooks restored after failure"
	fi
	rm -rf "$archive"
}
trap cleanup EXIT

echo "=== arm 1: current installation is complete"
if [ -x "$hook" ] && [ -x "$commit_msg_hook" ]; then
	echo "PASS: pre-commit and commit-msg hooks installed and executable"
else
	echo "FAIL: missing or non-executable hook stage ($hook / $commit_msg_hook)"
	FAILURES=$((FAILURES + 1))
fi

echo "=== arm 2: heal restores both stages after a full hook loss"
cp "$hook" "$archive/pre-commit" 2>/dev/null
cp "$commit_msg_hook" "$archive/commit-msg" 2>/dev/null
mv "$hook" "$hook.lost" 2>/dev/null
mv "$commit_msg_hook" "$commit_msg_hook.lost" 2>/dev/null
if bash scripts/heal-pre-commit-hook.sh > /tmp/verify-hook-selfheal-heal.log 2>&1; then
	: # heal reports its own state; verified below
fi
if [ -x "$hook" ] && [ -x "$commit_msg_hook" ]; then
	echo "PASS: heal restored both stages after the simulated loss"
else
	echo "FAIL: heal did not restore both stages (see /tmp/verify-hook-selfheal-heal.log)"
	FAILURES=$((FAILURES + 1))
fi

echo "=== arm 3: the installed hooks still name the battery stages"
stage_hits=0
grep -q "pre-commit" "$hook" 2>/dev/null && stage_hits=$((stage_hits + 1))
grep -q "commit-msg\|commit_msg" "$hook" "$commit_msg_hook" 2>/dev/null && stage_hits=$((stage_hits + 1))
if [ "$stage_hits" -ge 2 ]; then
	echo "PASS: hook content names both stages"
else
	echo "FAIL: hook content does not name both stages"
	FAILURES=$((FAILURES + 1))
fi

if [ "$FAILURES" -gt 0 ]; then
	echo "=== $FAILURES arm(s) RED"
	exit 1
fi
echo "=== hook self-heal regression green"
exit 0
