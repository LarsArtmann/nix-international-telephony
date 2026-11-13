#!/usr/bin/env bash
# verify-live.sh — replayable OFF-host post-deploy probe (deploy.md §5
# companion, upstreamed from the private deployment repo 2026-09-29).
#
# Everything checkable about a deployed stack WITHOUT ssh, from any
# machine: DNS, sshd banner, HTTP->HTTPS, webphone, TLS cert
# issuer/expiry, the webhook receiver's health + designed-404 + token
# gate, the /mms-media/ location, the operator/phone-API session gate
# (designed 401), and TCP reachability of TURN/SIP. Each probe prints
# one PASS/FAIL/SKIP line; exit 1 if anything FAILED, exit 2 on usage
# problems. Checks that genuinely need the host are printed at the end
# as ready-to-paste ssh commands instead of being silently omitted.
#
# Usage:
#   scripts/verify-live.sh <domain>
#   PBX_DOMAIN=<domain> scripts/verify-live.sh
#     PBX_WEBHOOK_TOKEN=…     also exercise the token-gated /recent reader
#     PBX_CERT_ISSUER=<glob>  cert issuer expectation, ONE glob (default
#                             '*Encrypt*' — matches every Let's Encrypt
#                             intermediate shape; '*' accepts any issuer)
#                             (a single glob because an expanded case
#                             pattern cannot carry | alternation)
set -uo pipefail

domain="${1:-${PBX_DOMAIN:-}}"
if [ -z "$domain" ]; then
	echo "verify-live: a domain is required (arg 1 or PBX_DOMAIN) — no default by design" >&2
	exit 2
fi
issuer_want="${PBX_CERT_ISSUER:-*Encrypt*}"
pass=0
fail=0
skip=0
warn=0

result() { # result PASS|FAIL|SKIP|WARN <name> <detail>
	case "$1" in
	PASS) pass=$((pass + 1)) ;;
	FAIL) fail=$((fail + 1)) ;;
	WARN) warn=$((warn + 1)) ;;
	SKIP) skip=$((skip + 1)) ;;
	esac
	printf '%-4s %-28s %s\n' "$1" "$2" "$3"
}

have() { command -v "$1" >/dev/null 2>&1; }

# --- DNS --------------------------------------------------------------------
if a="$(getent ahostsv4 "$domain" | head -1 | awk '{print $1}')"; then
	result PASS "dns A" "$domain -> ${a:-no answer}"
	[ -n "$a" ] || result FAIL "dns A" "empty answer"
else
	result FAIL "dns A" "no A record for $domain"
fi

# --- sshd banner ------------------------------------------------------------
# Reverse-DNS stall class (observed 2026-09-22): TCP accepts instantly,
# the identification string only after the resolver gives up. Alive-but-
# slow is a WARN, dead is a FAIL; the wait must outlive the stall.
start=$(date +%s)
banner="$(timeout 45 bash -c "exec 3</dev/tcp/$domain/22 && head -c 64 <&3" 2>/dev/null || true)"
elapsed=$(($(date +%s) - start))
case "$banner" in
SSH-2.0-*)
	if [ "$elapsed" -ge 10 ]; then
		result WARN "ssh banner" "$banner after ${elapsed}s (reverse-DNS stall class)"
	else
		result PASS "ssh banner" "$banner (${elapsed}s)"
	fi
	;;
*) result FAIL "ssh banner" "no SSH banner on port 22 within 45s (installed system up?)" ;;
esac

# --- HTTP -> HTTPS ----------------------------------------------------------
if have curl; then
	code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://$domain/" || true)"
	case "$code" in
	301 | 308) result PASS "http redirect" "$code to https" ;;
	*) result FAIL "http redirect" "got $code, want 301/308" ;;
	esac

	code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$domain/" || true)"
	[ "$code" = 200 ] &&
		result PASS "webphone https" "200" ||
		result FAIL "webphone https" "got $code, want 200"

	code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$domain/healthz" || true)"
	[ "$code" = 200 ] &&
		result PASS "webphone healthz" "200 (app up + ready)" ||
		result FAIL "webphone healthz" "got $code, want 200"

	# receiver: designed-404 on the POST-only path = nginx + receiver alive
	code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$domain/telnyx/webhooks" || true)"
	[ "$code" = 404 ] &&
		result PASS "receiver post-only 404" "nginx + receiver alive" ||
		result FAIL "receiver post-only 404" "got $code, want 404"

	body="$(curl -fsS --max-time 10 "https://$domain/telnyx/webhooks/health" 2>/dev/null || true)"
	[ "$body" = '{"ok": true}' ] || [ "$body" = '{"ok":true}' ] &&
		result PASS "receiver health" "$body" ||
		result FAIL "receiver health" "got: ${body:-no answer}"

	code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$domain/telnyx/webhooks/recent" || true)"
	[ "$code" = 403 ] &&
		result PASS "recent token gate" "403 without token" ||
		result FAIL "recent token gate" "got $code, want 403"

	if [ -n "${PBX_WEBHOOK_TOKEN:-}" ]; then
		code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
			-H "Authorization: Bearer $PBX_WEBHOOK_TOKEN" "https://$domain/telnyx/webhooks/recent" || true)"
		[ "$code" = 200 ] &&
			result PASS "recent with token" "200" ||
			result FAIL "recent with token" "got $code, want 200"
	else
		result SKIP "recent with token" "set PBX_WEBHOOK_TOKEN to exercise"
	fi

	code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$domain/mms-media/definitely-not-a-token.png" || true)"
	[ "$code" = 404 ] &&
		result PASS "mms-media location" "404 on garbage token" ||
		result FAIL "mms-media location" "got $code, want 404"

	# The phone-API proxy is session-gated by the app: an anonymous hit
	# MUST answer 401 — a 200 here would mean the operator API surface
	# leaked past the session gate.
	code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$domain/phone-api/" || true)"
	case "$code" in
	401 | 403) result PASS "phone-api session gate" "$code without session" ;;
	*) result FAIL "phone-api session gate" "got $code, want 401/403" ;;
	esac
else
	result SKIP "http probes" "curl not found on this machine"
fi

# --- TLS cert ---------------------------------------------------------------
if have openssl; then
	cert="$(timeout 10 openssl s_client -connect "$domain:443" -servername "$domain" </dev/null 2>/dev/null | openssl x509 -noout -issuer -enddate 2>/dev/null || true)"
	if [ -n "$cert" ]; then
		issuer="$(printf '%s\n' "$cert" | grep '^issuer=' | cut -d= -f2-)"
		end="$(printf '%s\n' "$cert" | grep '^notAfter=' | cut -d= -f2-)"
		# shellcheck disable=SC2254  # issuer_want is an intentional glob
		case "$issuer" in
		$issuer_want) result PASS "cert issuer" "$issuer" ;;
		*) result FAIL "cert issuer" "$issuer (want glob $issuer_want; PBX_CERT_ISSUER='*' for self-signed)" ;;
		esac
		if end_epoch=$(date -d "$end" +%s 2>/dev/null); then
			days=$(((end_epoch - $(date +%s)) / 86400))
			[ "$days" -ge 14 ] &&
				result PASS "cert expiry" "$days days ($end)" ||
				result FAIL "cert expiry" "only $days days left ($end)"
		fi
	else
		result FAIL "tls handshake" "no certificate on $domain:443"
	fi
else
	result SKIP "tls cert" "openssl not found on this machine"
fi

# --- service ports (TCP reachability) ---------------------------------------
tcp_probe() { # tcp_probe <port> <label>
	if timeout 5 bash -c "exec 3<>/dev/tcp/$domain/$1" 2>/dev/null; then
		result PASS "$2" "tcp $1 open"
	else
		result FAIL "$2" "tcp $1 closed/filtered"
	fi
}
tcp_probe 3478 "turn (coturn)"
tcp_probe 5061 "sip tls (wss)"
tcp_probe 5080 "sip external"

# --- authenticated voicemail recording fetch (pareto T17/F58) ---------------
# Env-gated: PBX_EXTENSION + PBX_PASSWORD (both or none). Mints a real
# session through the vhost (CSRF dance), reads the extension's voicemail
# feed, and byte-range-fetches the first recording — asserting the SAME
# 206 Range passthrough operator.nix pins inside the VM, from OFF-host,
# through the production caddy. Absent creds SKIP (a probe must never
# invent credentials).
if [ -n "${PBX_EXTENSION:-}" ] && [ -n "${PBX_PASSWORD:-}" ]; then
	jar="$(mktemp)"
	trap 'rm -f "$jar"' EXIT
	# 1. Anonymous CSRF: /api/csrf sets the csrf_token cookie and names the token.
	csrf_body="$(curl -ksS -c "$jar" "https://$domain/api/csrf")" || csrf_body=""
	csrf_token="$(printf '%s' "$csrf_body" | sed -n 's/.*"token"\s*:\s*"\([^"]*\)".*/\1/p' | head -1)"
	if [ -z "$csrf_token" ]; then
		result SKIP "vm audio fetch" "no csrf_token from /api/csrf (shape drift?)"
	elif login_code="$(curl -ksS -b "$jar" -c "$jar" -o /dev/null -w '%{http_code}' \
		-X POST "https://$domain/api/session" \
		-H "Content-Type: application/json" \
		-H "Origin: https://$domain" \
		-H "X-CSRF-Token: $csrf_token" \
		--data "{\"extension\":\"$PBX_EXTENSION\",\"password\":\"$PBX_PASSWORD\"}")" &&
		[ "$login_code" = "201" ] || [ "$login_code" = "200" ]; then
		feed="$(curl -ksS -b "$jar" "https://$domain/phone-api/voicemail/$PBX_EXTENSION/messages")" || feed=""
		audio="$(printf '%s' "$feed" | python3 -c 'import json,sys; msgs=json.load(sys.stdin); m=[x for x in (msgs.get("messages") or msgs if isinstance(msgs,list) else []) if isinstance(x,dict) and x.get("audio_url")]; print(m[0]["audio_url"] if m else "")' 2>/dev/null)"
		if [ -z "$audio" ]; then
			result SKIP "vm audio fetch" "no recording in $PBX_EXTENSION's box (deposit one first)"
		else
			case "$audio" in
			http*) url="$audio" ;;
			*) url="https://$domain$audio" ;;
			esac
			code="$(curl -ksS -b "$jar" -o /dev/null -w '%{http_code}' -H "Range: bytes=0-1023" "$url")"
			[ "$code" = "206" ] &&
				result PASS "vm audio fetch" "206 on byte-range ($url)" ||
				result FAIL "vm audio fetch" "ranged fetch answered $code (want 206): $url"
		fi
		curl -ksS -b "$jar" -o /dev/null -X POST "https://$domain/logout" || true
	else
		result FAIL "vm audio fetch" "session mint answered $login_code (bad creds? csrf drift?)"
	fi
else
	result SKIP "vm audio fetch" "PBX_EXTENSION/PBX_PASSWORD not set (authenticated leg)"
fi

echo
echo "host-side (needs ssh — paste manually):"
echo "  ssh root@$domain systemctl is-active freeswitch nginx coturn telnyx-webhooks"
echo "  ssh root@$domain 'fs_cli -p \"\$(cat /var/lib/telephony-secrets/telephony_event_socket)\" -x \"sofia status\"'"
echo "  ssh root@$domain systemctl list-timers 'telephony-backup*' telephony-health"
echo "  ssh root@$domain readlink -f /run/current-system/sw/bin/webphone  # store-path moved?"

echo
echo "verify-live: $pass passed, $fail failed, $warn warned, $skip skipped"
[ "$fail" -eq 0 ]
