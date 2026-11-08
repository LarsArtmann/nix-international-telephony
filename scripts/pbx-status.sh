#!/usr/bin/env bash
# One-shot PBX status answer for operator triage: unit states, sofia
# registrations, gateway REG, listeners, webphone health, disk/memory.
# Read-only; runs ON a deployed host (or any machine with the units).
# Usage: scripts/pbx-status.sh [domain]   (domain defaults to the
# machine's own TLS vhost; harmless offline — every section degrades
# to a dash instead of failing the run).
set -u
domain="${1:-pbx.test}"

section() { printf '\n== %s ==\n' "$1"; }

section "units"
systemctl --no-pager --full status freeswitch.service webphone.service \
	telnyx-webhooks.service nginx.service coturn.service 2>/dev/null |
	grep -E '^(●|[0-9]{2}:)|Active:' | head -30

section "sofia registrations"
fs_cli -x 'sofia status profile internal reg' 2>/dev/null | grep -c 'Call-ID:' ||
	echo "-"

section "gateway states"
fs_cli -x 'sofia status gateway' 2>/dev/null | grep -E '^(gateway|State|REG)' | head -12 ||
	echo "-"

section "listeners"
ss -ltn 2>/dev/null | grep -E ':(5060|5061|7443|443|3478|8021)\b' || echo "-"

section "webphone health"
curl -skf -o /dev/null -w 'https://%{url_effective} -> %{http_code}\n' \
	"https://${domain}/healthz" 2>/dev/null || echo "-"

section "disk / memory"
df -h / 2>/dev/null | tail -1
free -m 2>/dev/null | sed -n '2p'

section "recent failures"
journalctl -p err --since "-1h" --no-pager 2>/dev/null | tail -10 || echo "-"
