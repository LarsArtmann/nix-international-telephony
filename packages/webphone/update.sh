#!/usr/bin/env bash
# Refresh the pinned sip.js tarball to the latest npm release.
# Usage: ./update.sh [version]   (default: latest)
#
# Rewrites the version + hash in packages/webphone/default.nix, then
# verifies the esbuild bundle still builds. Review the diff before
# committing: sip.js majors can change the lib/ entry layout.
set -euo pipefail

default_nix="$(dirname "$0")/default.nix"
version="${1:-latest}"

resolved=$(
	curl -fsS "https://registry.npmjs.org/sip.js/$version" |
		jq -r '.version'
)
echo "Updating sip.js -> $resolved"

url="https://registry.npmjs.org/sip.js/-/sip.js-$resolved.tgz"
hash=$(nix store prefetch-file --hash-type sha256 --json "$url" | jq -r .hash)

sed -i \
	-e "s|sip\.js-[0-9][^\"]*\.tgz|sip.js-$resolved.tgz|" \
	-e "s|hash = \"sha256-[^\"]*\";|hash = \"$hash\";|" \
	"$default_nix"

echo "Pinned $url at $hash — building to verify the bundle still works:"
nix build -L "$(git rev-parse --show-toplevel)#webphone"
