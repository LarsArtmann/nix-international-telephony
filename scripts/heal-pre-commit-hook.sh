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
# global core.hooksPath. Mask HOME so the global gitconfig is invisible,
# unset the local override, install, then restore the local override so
# the (broken, nonexistent) global .githooks never applies here.
pre_commit_bin="$(
	nix eval --raw .#devShells."$(nix eval --raw .#currentSystem 2>/dev/null || echo x86_64-linux)".shellHook 2>/dev/null \
		| grep -oE '/nix/store/[a-z0-9]+-pre-commit-[0-9.]+/bin/pre-commit' | head -1 || true
)"
if [ -z "$pre_commit_bin" ] || [ ! -x "$pre_commit_bin" ]; then
	echo "heal-pre-commit-hook: could not locate the flake's pre-commit binary;" >&2
	echo "  enter 'nix develop' once and rerun, or install from the devshell:" >&2
	echo "    nix develop -c sh -c 'git config --local --unset-all core.hooksPath; HOME=\$(mktemp -d) pre-commit install -c .pre-commit-config.yaml -t pre-commit; git config --local core.hooksPath .git/hooks'" >&2
	exit 1
fi

git config --local --unset-all core.hooksPath || true
tmp_home="$(mktemp -d)"
trap 'rm -rf "$tmp_home"' EXIT
HOME="$tmp_home" "$pre_commit_bin" install -c .pre-commit-config.yaml -t pre-commit
git config --local core.hooksPath .git/hooks

[ -x "$hook" ] && echo "heal-pre-commit-hook: hook installed at $hook." || {
	echo "heal-pre-commit-hook: install reported success but $hook missing" >&2
	exit 1
}
