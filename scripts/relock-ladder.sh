#!/usr/bin/env bash
# relock-ladder.sh — run the lock-bump gate ladder with per-gate verdicts.
#
# WHY: the manual ladder bookkeeping produced the 2026-10-28 `5f331e6`
# CHANGELOG overclaim (a gate was claimed green in anticipation, before
# it ran). This script runs the runbook's gate ladder ("Lock-bump
# runbook (webphone input)" in docs/ops-runbook.md), tees every gate's
# log to a verdict directory, records `NIX_EXIT` per gate, and prints a
# verdict table. The commit message cites the table, never a claim.
#
# SCOPE: gates 2-6 of the runbook ladder. Gate 1 (the relock itself:
# `nix flake lock --update-input webphone`) is NOT run here — the move
# stays a hand-authored, lock-move-guard-tripped act (AGENTS.md). Run
# this script AFTER the relock, on any red stop and forward-pin per the
# runbook's forward-pin rule.
#
# Gate set (cheap first; stop at the first red unless --keep-going):
#   2  binary-proof   nix build -L .#webphone
#   3a fast-fmt       nix fmt
#   3b fast-eval      nix flake check --no-build
#   4  webphone-suites every suite in GATE4_SUITES below (webphone,
#                     dynamic-directory, empty-secret, textagent, fax,
#                     fax-feed), each built with --no-eval-cache — the
#                     runbook's post-move rule, encoded so a relock run
#                     cannot forget it
#   5  browser-e2e    nix build -L .#telephony-browser   (flag --browser-e2e;
#                     run only on upstream markup/bundle deltas per the
#                     runbook's gate-5 clause)
#   6  full-check     nix flake check --no-eval-cache    (flag --full-check)
#
# Usage:
#   scripts/relock-ladder.sh [--browser-e2e] [--full-check] [--keep-going]
#                            [--log-dir DIR] [--dry-run]
#
# Exit codes: 0 every gate green; 1 at least one gate red (the verdict
# table names which); 2 usage error.
set -uo pipefail

LOG_DIR="/tmp/relock-ladder-$(date +%Y%m%d-%H%M%S)"
KEEP_GOING=0
DRY_RUN=0
RUN_BROWSER_E2E=0
RUN_FULL_CHECK=0
# Every webphone-config surface a relock can move. This list is the single
# source for gate 4 and MUST stay in lockstep with the runbook's gate-4 row
# (docs/ops-runbook.md "Lock-bump runbook") — a ladder that under-covers its
# own documented gate is how the 2026-10-28 `5f331e6` overclaim class starts.
GATE4_SUITES=(
	telephony-webphone
	telephony-webphone-dynamic-directory
	telephony-webphone-empty-secret
	telephony-textagent
	telephony-fax
	telephony-fax-feed
)

while [ $# -gt 0 ]; do
	case "$1" in
	--browser-e2e) RUN_BROWSER_E2E=1 ;;
	--full-check) RUN_FULL_CHECK=1 ;;
	--keep-going) KEEP_GOING=1 ;;
	--log-dir)
		LOG_DIR="$2"
		shift
		;;
	--dry-run) DRY_RUN=1 ;;
	-h | --help)
		sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//'
		exit 0
		;;
	*)
		echo "unknown arg: $1" >&2
		exit 2
		;;
	esac
	shift
done

mkdir -p "$LOG_DIR"
declare -a GATE_NAMES=()
declare -a GATE_EXITS=()

run_gate() {
	local name="$1"
	shift
	GATE_NAMES+=("$name")
	local log="$LOG_DIR/$name.log"
	echo "=== gate $name — logging to $log"
	if [ "$DRY_RUN" = 1 ]; then
		printf 'would run: %s\n' "$*" | tee "$log"
		GATE_EXITS+=("dry")
		return 0
	fi
	"$@" > >(tee "$log") 2>&1
	local rc=$?
	GATE_EXITS+=("$rc")
	echo "=== gate $name exit: $rc"
	return $rc
}

STOP=0
should_run() { [ $KEEP_GOING = 1 ] || [ $STOP = 0 ]; }
run_gate binary-proof nix build -L .#webphone || { STOP=1; }
if should_run; then run_gate fast-fmt nix fmt || { STOP=1; }; fi
if should_run; then run_gate fast-eval nix flake check --no-build || { STOP=1; }; fi
for suite in "${GATE4_SUITES[@]}"; do
	if should_run; then
		run_gate "$suite" nix build -L --no-eval-cache ".#checks.x86_64-linux.$suite" || { STOP=1; }
	fi
done
if should_run && [ $RUN_BROWSER_E2E = 1 ]; then
	run_gate browser-e2e nix build -L --no-eval-cache .#telephony-browser || { STOP=1; }
fi
if should_run && [ $RUN_FULL_CHECK = 1 ]; then
	run_gate full-check nix flake check --no-eval-cache || { STOP=1; }
fi

echo
echo "=== relock-ladder verdict table (logs in $LOG_DIR)"
FAILURES=0
i=0
while [ $i -lt ${#GATE_NAMES[@]} ]; do
	rc="${GATE_EXITS[$i]}"
	name="${GATE_NAMES[$i]}"
	if [ "$rc" = "0" ]; then
		verdict="GREEN"
	elif [ "$rc" = "dry" ]; then
		verdict="DRY"
	else
		verdict="RED"
		FAILURES=$((FAILURES + 1))
	fi
	printf '%-36s %-5s (exit %s)\n' "$name" "$verdict" "$rc"
	i=$((i + 1))
done

if [ $FAILURES -gt 0 ]; then
	echo "=== $FAILURES gate(s) RED — stop and forward-pin per the runbook"
	exit 1
fi
echo "=== ladder green — record every verdict line in the relock commit"
exit 0
