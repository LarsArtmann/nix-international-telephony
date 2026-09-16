#!/usr/bin/env bash
# Personal-data scrub gate.
#
# Greps REAL VALUES (DIDs, personal numbers, usernames, IPs, key IDs)
# from secrets/scrub-patterns.txt over the tracked tree (always) and,
# with --history, over every commit via `git log --all -S` — the
# tripwire that caught an unredacted DID during history surgery.
#
# Patterns file is gitignored on purpose: it holds the personal values
# themselves. Every value must be listed in ALL its spellings
# (+48123..., 48123..., "+48 123 ...", spaced, dashed).
#
# Usage:
#   scripts/scrub-check.sh             # tree scan (what pre-commit runs)
#   scripts/scrub-check.sh --history   # + git log --all -S per pattern
#   scripts/scrub-check.sh --strict    # missing patterns file is an error
set -uo pipefail

history=0
strict=0
patterns_arg=""
while [ $# -gt 0 ]; do
	case "$1" in
	--history) history=1 ;;
	--strict) strict=1 ;;
	--patterns)
		[ $# -ge 2 ] || {
			echo "scrub-check: --patterns needs a file" >&2
			exit 2
		}
		patterns_arg="$2"
		shift
		;;
	-h | --help)
		sed -n '2,16p' "$0"
		exit 0
		;;
	*)
		echo "scrub-check: unknown arg: $1" >&2
		exit 2
		;;
	esac
	shift
done

root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
	echo "scrub-check: not inside a git repository" >&2
	exit 2
}
cd "$root"

patterns_file="${patterns_arg:-secrets/scrub-patterns.txt}"
if [ ! -f "$patterns_file" ]; then
	if [ "$strict" = 1 ]; then
		echo "scrub-check: STRICT FAIL — $patterns_file missing." >&2
		echo "Copy secrets/scrub-patterns.example to it and list every personal" >&2
		echo "value in all spellings, then rerun." >&2
		exit 1
	fi
	echo "scrub-check: WARNING — $patterns_file missing, personal-data gate OFF." >&2
	echo "scrub-check: copy secrets/scrub-patterns.example to it (gitignored)." >&2
	exit 0
fi

mapfile -t patterns < <(grep -vE '^\s*(#|$)' "$patterns_file" || true)
if [ "${#patterns[@]}" -eq 0 ]; then
	echo "scrub-check: WARNING — $patterns_file has no patterns, gate is a no-op." >&2
	exit 0
fi

hits=0
for pattern in "${patterns[@]}"; do
	pattern="$(printf '%s' "$pattern" | sed 's/[[:space:]]*$//')"
	[ -n "$pattern" ] || continue

	tree_hits="$(git grep -nIF -e "$pattern" -- . || true)"
	if [ -n "$tree_hits" ]; then
		hits=$((hits + 1))
		count="$(printf '%s\n' "$tree_hits" | wc -l)"
		echo "scrub-check: TREE HIT [$pattern] — $count tracked file(s):" >&2
		printf '%s\n' "$tree_hits" | head -5 | sed 's/^/  /' >&2
		[ "$count" -le 5 ] || echo "  … ($((count - 5)) more)" >&2
	fi

	if [ "$history" = 1 ]; then
		log_hits="$(git log --all --oneline -S"$pattern" || true)"
		if [ -n "$log_hits" ]; then
			hits=$((hits + 1))
			count="$(printf '%s\n' "$log_hits" | wc -l)"
			echo "scrub-check: HISTORY HIT [$pattern] — $count commit(s) touched it:" >&2
			printf '%s\n' "$log_hits" | head -5 | sed 's/^/  /' >&2
			[ "$count" -le 5 ] || echo "  … ($((count - 5)) more)" >&2
		fi
	fi
done

if [ "$hits" -gt 0 ]; then
	echo "scrub-check: FAIL — $hits pattern(s) found; scrub before committing/pushing." >&2
	echo "scrub-check: history hits need rewrite (see AGENTS.md history-surgery entry)." >&2
	exit 1
fi

echo "scrub-check: OK — ${#patterns[@]} pattern(s) clean over $([ $history = 1 ] && echo 'tree+history' || echo 'tree')."
exit 0
