#!/usr/bin/env bash
# Wave 1 acceptance, scripted half. The browser half is in docs/acceptance-wave1.md.
#
# Usage: ARCHY_PASSWORD=... scripts/acceptance.sh
# Env:   NODE (default root@95.216.164.146), ARCHY_PASSWORD (dashboard password).
# Every check runs on the node over SSH, through the real RPC and the real signer.
# Exits 0 only when every check passes.
set -euo pipefail
: "${NODE:=root@95.216.164.146}" "${ARCHY_PASSWORD:?dashboard password}"
host=${NODE#*@}
# The remote script travels as an argument and the password alone on stdin,
# so the password stays off the ssh command line.
read -r -d '' remote <<'EOF' || true
set -euo pipefail
IFS= read -r ARCHY_PASSWORD
export ARCHY_PASSWORD ARCHY_FORCE_LOGIN=1
host=$1
source /opt/archipelago/rpc.bash
rpc_login >/dev/null
fail() { echo "FAIL: $*"; exit 1; }
podman_inspect_env() {
  runuser -u archipelago -- sh -c "cd / && XDG_RUNTIME_DIR=/run/user/1000 \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
    podman inspect $1 --format '{{range .Config.Env}}{{println .}}{{end}}'"
}

# 1. Both apps installed, running and not unhealthy (server.get-state package-data).
state_json=$(rpc_result server.get-state)
for app in wildbloom-node wildbloom; do
  state=$(jq -r --arg id "$app" '.data["package-data"][$id].state // "absent"' <<<"$state_json")
  health=$(jq -r --arg id "$app" '.data["package-data"][$id].health // "none"' <<<"$state_json")
  echo "$app: state=$state health=$health"
  [ "$state" = running ] || fail "$app not running"
  if [ "$health" = unhealthy ]; then fail "$app unhealthy"; fi
done

# 2. Owner pubkey injected equals the node key (Review Focus #1).
node_pk=$(rpc_result node.nostr-pubkey | jq -r '.nostr_pubkey // empty')
node_npub=$(rpc_result node.nostr-pubkey | jq -r '.nostr_npub // empty')
wbn_env=$(podman_inspect_env wildbloom-node)
env_pk=$(sed -n 's/^WILDBLOOM_ALLOW_PUBKEYS=//p' <<<"$wbn_env")
echo "node=$node_pk env=$env_pk ($node_npub)"
[ -n "$node_pk" ] && [ "$node_pk" = "$env_pk" ] || fail "owner pubkey mismatch"

# 3. Review Focus #2: the UI is gated; the Blossom port is open but refuses unsigned writes.
code=$(curl -sk -o /dev/null -w '%{http_code}' "https://$host:3743/")
echo "unauthenticated UI :3743 -> $code"
if [ "$code" = 200 ]; then fail "Wildbloom UI served without a session"; fi
code=$(curl -sk -o /dev/null -w '%{http_code}' "https://$host:3742/healthz")
echo "Blossom :3742 healthz via gate -> $code"; [ "$code" = 200 ] || fail "Blossom port not reachable through the gate over TLS"
x_sha=$(printf x | sha256sum | awk '{print $1}')
code=$(curl -sk -o /dev/null -w '%{http_code}' -X PUT --data-binary 'x' \
  -H "X-SHA-256: $x_sha" -H 'Content-Type: application/octet-stream' "https://$host:3742/upload")
echo "unsigned upload :3742 -> $code"
case "$code" in 401|403) ;; *) fail "unsigned upload not refused for want of auth (got $code)";; esac

# 4/5. Upload signed by the node key via node.nostr-sign; the server tag is the
# mDNS name the orchestrator injected, which must equal this host's (Review Focus #3).
mdns=$(sed -n 's/^WILDBLOOM_SERVER_NAME=//p' <<<"$wbn_env" | tr ',' '\n' | grep -E '\.local$' | head -1)
[ -n "$mdns" ] && [ "$mdns" = "$(hostname).local" ] || fail "WILDBLOOM_SERVER_NAME has no .local member matching this host"
echo "server tag: injected mDNS name matches hostname.local"
payload=$(mktemp); head -c 8192 /dev/urandom > "$payload"
sha=$(sha256sum "$payload" | awk '{print $1}')
now=$(date +%s)
unsigned=$(jq -nc --arg sha "$sha" --arg srv "$mdns" --argjson now "$now" --arg pk "$node_pk" \
  '{kind:24242,created_at:$now,pubkey:$pk,content:("upload "+$sha),tags:[["t","upload"],["x",$sha],["expiration",(($now+300)|tostring)],["server",$srv]]}')
signed=$(rpc_result node.nostr-sign "{\"event\":$unsigned}" | jq -c 'select(has("sig"))')
[ -n "$signed" ] || fail "node.nostr-sign returned no signed event"
[ "$(jq -r .pubkey <<<"$signed")" = "$node_pk" ] || fail "signed event pubkey is not the node key"
auth=$(printf '%s' "$signed" | base64 -w0)
curl -fsS -X PUT --data-binary @"$payload" -H "Authorization: Nostr $auth" -H "X-SHA-256: $sha" \
  -H "Content-Type: application/octet-stream" "http://127.0.0.1:3742/upload" >/dev/null || fail "upload refused"
echo "signed upload accepted: $sha"
curl -fsS "http://127.0.0.1:3742/$sha" -o "$payload.back" && cmp "$payload" "$payload.back" || fail "fetch mismatch"
echo "fetch by sha matches the uploaded bytes"
echo "$sha" > /root/acceptance-blob.sha
cp "$payload" /root/acceptance-blob.bin
rm -f "$payload" "$payload.back"

# 6. Signer script present in the Wildbloom container.
curl -fsS http://127.0.0.1:3743/ | grep -qF 'nostr-provider.js?v=tab-signer-v4' || fail "no signer injection"
curl -fsS http://127.0.0.1:3743/nostr-provider.js | grep -q 'NIP-07' || fail "provider not copied from host"
echo "signer injection and provider present"
echo "ACCEPTANCE (scripted) PASSED: blob $sha"
EOF
argv=$(printf '%q ' "$host")
printf '%s\n' "$ARCHY_PASSWORD" | ssh "$NODE" "bash -c $(printf '%q' "$remote") remote $argv"
