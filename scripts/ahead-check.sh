#!/usr/bin/env bash
# Standing ahead-count check against the upstream branch.
#
# The auto-commit daemon pushes asynchronously; three times in two days
# (2026-09-16) it stalled silently and origin sat red on stale code for
# hours while local was green. Run this (cron/timer/shell prompt) to
# make a stall loud: exit 1 when the local branch is ahead by more than
# the threshold (default 0 — any unpushed commit fails the check).
#
# The core.hooksPath probe (P29, 2026-09-17): unset in this repo and
# .git/hooks holds only samples — nothing shadows the daemon's hooks.
#
# Usage:
#   scripts/ahead-check.sh [max-ahead]   # default 0
set -euo pipefail

max_ahead="${1:-0}"

origin="$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)" || {
	echo "ahead-check: no upstream configured" >&2
	exit 2
}

# $origin is the tracking ref ("origin/main"); fetch the REMOTE it
# names, not the ref itself (git fetch origin/main fails and always
# took the "cannot judge" exit below).
remote="${origin%%/*}"
git fetch --quiet "$remote" 2>/dev/null || {
	echo "ahead-check: fetch failed (offline or auth?) — cannot judge" >&2
	exit 2
}

ahead="$(git rev-list --count "@{upstream}..HEAD")"
behind="$(git rev-list --count "HEAD..@{upstream}")"
branch="$(git rev-parse --abbrev-ref HEAD)"

echo "ahead-check: $branch is ahead $ahead, behind $behind (vs $origin)"

if [ "$behind" -gt 0 ]; then
	echo "ahead-check: local branch diverged — the daemon's rebase/push loop is stuck" >&2
	exit 1
fi

if [ "$ahead" -gt "$max_ahead" ]; then
	echo "ahead-check: FAIL — $ahead unpushed commit(s) (max $max_ahead)" >&2
	exit 1
fi

exit 0
