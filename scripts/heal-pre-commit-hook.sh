#!/usr/bin/env bash
# Heal the repo's pre-commit hook installation.
#
# Why this exists (2026-09-29): git-hooks.nix installs the hook only on
# `nix develop` entry and REFUSES to reinstall while .pre-commit-config.yaml
# exists, and `pre-commit install` refuses whenever core.hooksPath is set
# (the global ~/.gitconfig sets core.hookspath=.githooks). Once the hook
# file vanishes (fresh clone metadata, .git/hooks cleanup, git upgrade),
# every daemon commit runs ungated — the auto-commit daemon itself cannot
# bypass an INSTALLED hook (it shells out to `git commit` without
# --no-verify; verified against go-commit v0.9.0 source), so restoring the
# file closes the gap completely.
#
# Usage: scripts/heal-pre-commit-hook.sh   (run from anywhere in the repo)
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
	echo "heal-pre-commit-hook: not inside a git repository" >&2
	exit 2
}
cd "$root"

hook=".git/hooks/pre-commit"
if [ -x "$hook" ]; then
	echo "heal-pre-commit-hook: $hook already present — nothing to do."
	exit 0
fi

# Regenerate the config symlink (and hooks) via the devshell installer.
nix develop -c true 2>&1 | grep -v '^$' || true
if [ -x "$hook" ]; then
	echo "heal-pre-commit-hook: devshell entry restored the hook."
	exit 0
fi

# Manual path: the installer bailed on the existing config symlink or the
# global core.hooksPath. Run the install inside the devshell with HOME
# masked (so the global gitconfig's core.hookspath=.githooks is invisible),
# the local override unset, and the override restored afterwards so the
# (broken, nonexistent) global .githooks never applies here.
nix develop -c bash -c '
	set -e
	git config --local --unset-all core.hooksPath || true
	tmp_home="$(mktemp -d)"
	trap "rm -rf $tmp_home" EXIT
	HOME="$tmp_home" pre-commit install -c "$PWD/.pre-commit-config.yaml" -t pre-commit
	git config --local core.hooksPath .git/hooks
'

[ -x "$hook" ] && echo "heal-pre-commit-hook: hook installed at $hook." || {
	echo "heal-pre-commit-hook: install reported success but $hook missing" >&2
	exit 1
}
