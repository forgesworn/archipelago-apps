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
root=$(cd "$(dirname "$0")/.." && pwd)
# The remote script (scripts/lib/archy-login.bash, then the body below) travels
# as an ssh argument; the password alone travels on stdin, so it is on neither
# the local nor the remote command line, and archy_login keeps it out of argv on
# the node too. It is held in a shell variable, not exported. The %q quoting
# below is bash syntax: it assumes the node's root login shell is bash.
read -r -d '' remote <<'EOF' || true
set -euo pipefail
IFS= read -r ARCHY_PASSWORD
host=$1
source /opt/archipelago/rpc.bash
archy_login
unset ARCHY_PASSWORD
fail() { echo "FAIL: $*"; exit 1; }
payload=""
trap 'rm -f "${payload:-}" "${payload:+$payload.back}"' EXIT
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

# 2. Owners injected are exactly the identities the app signer offers (Review
# Focus #1). identity.list returns {identities:[{id,name,is_node,nostr_pubkey,..}]}
# (handle_identity_list, archy core/archipelago/src/api/rpc/identity/handlers.rs:52-71
# with our patch applied); the filter is
# NostrIdentityPicker.vue's (neode-ui/src/components/NostrIdentityPicker.vue:156-162)
# plus a Nostr key, which signing needs.
signable=$(rpc_result identity.list | jq -c '[.identities[]
  | select((.is_node // false) | not)
  | select(.id | gsub("^\\s+|\\s+$"; "") | ascii_downcase | startswith("node-") | not)
  | select((.name | gsub("^\\s+|\\s+$"; "") | ascii_downcase) != "node")
  | select(.nostr_pubkey != null)]')
want_pks=$(jq -r '[.[].nostr_pubkey | ascii_downcase] | unique | join(",")' <<<"$signable")
signer_id=$(jq -r '.[0].id // empty' <<<"$signable")
signer_pk=$(jq -r '.[0].nostr_pubkey // empty | ascii_downcase' <<<"$signable")
wbn_env=$(podman_inspect_env wildbloom-node)
env_pks=$(sed -n 's/^WILDBLOOM_ALLOW_PUBKEYS=//p' <<<"$wbn_env")
echo "signable=$want_pks env=$env_pks"
[ -n "$want_pks" ] && [ -n "$signer_id" ] || fail "no signable identity with a Nostr key"
[ "$want_pks" = "$env_pks" ] || fail "owner pubkeys differ from the signable identities"

# 3. Review Focus #2: the UI is gated; the Blossom port is open but refuses unsigned writes.
code=$(curl -sk -o /dev/null -w '%{http_code}' "https://$host:3743/")
echo "unauthenticated UI :3743 -> $code"
case "$code" in 401|403) ;; *) fail "Wildbloom UI not refused for want of a session (got $code)";; esac
code=$(curl -sk -o /dev/null -w '%{http_code}' "https://$host:3742/healthz")
echo "Blossom :3742 healthz via gate -> $code"; [ "$code" = 200 ] || fail "Blossom port not reachable through the gate over TLS"
x_sha=$(printf x | sha256sum | awk '{print $1}')
code=$(curl -sk -o /dev/null -w '%{http_code}' -X PUT --data-binary 'x' \
  -H "X-SHA-256: $x_sha" -H 'Content-Type: application/octet-stream' "https://$host:3742/upload")
echo "unsigned upload :3742 -> $code"
case "$code" in 401|403) ;; *) fail "unsigned upload not refused for want of auth (got $code)";; esac

# 4/5. Upload signed through identity.nostr-sign by the first signable identity,
# as the NIP-07 bridge signs (neode-ui/src/views/appSession/useNostrBridge.ts:154);
# the server tag is the mDNS name the orchestrator injected, which must equal this
# host's (Review Focus #3).
mdns=$(sed -n 's/^WILDBLOOM_SERVER_NAME=//p' <<<"$wbn_env" | tr ',' '\n' | grep -E '\.local$' | head -1 || true)
[ -n "$mdns" ] && [ "$mdns" = "$(hostname).local" ] || fail "WILDBLOOM_SERVER_NAME has no .local member matching this host"
echo "server tag: injected mDNS name matches hostname.local"
payload=$(mktemp); head -c 8192 /dev/urandom > "$payload"
sha=$(sha256sum "$payload" | awk '{print $1}')
now=$(date +%s)
sign_params=$(jq -nc --arg id "$signer_id" --arg sha "$sha" --arg srv "$mdns" --argjson now "$now" --arg pk "$signer_pk" \
  '{id:$id,event:{kind:24242,created_at:$now,pubkey:$pk,content:("upload "+$sha),tags:[["t","upload"],["x",$sha],["expiration",(($now+300)|tostring)],["server",$srv]]}}')
# identity.nostr-sign returns the whole signed event {id,pubkey,created_at,kind,
# tags,content,sig} (handle_identity_nostr_sign, handlers.rs:443-451 patched).
signed=$(rpc_result identity.nostr-sign "$sign_params" | jq -c 'select(has("sig"))')
[ -n "$signed" ] || fail "identity.nostr-sign returned no signed event"
[ "$(jq -r .pubkey <<<"$signed")" = "$signer_pk" ] || fail "signed event pubkey is not the signable identity's key"
auth=$(printf '%s' "$signed" | base64 -w0)
curl -fsS -X PUT --data-binary @"$payload" -H "Authorization: Nostr $auth" -H "X-SHA-256: $sha" \
  -H "Content-Type: application/octet-stream" "http://127.0.0.1:3742/upload" >/dev/null || fail "upload refused"
echo "signed upload accepted: $sha"
curl -fsS "http://127.0.0.1:3742/$sha" -o "$payload.back" && cmp "$payload" "$payload.back" || fail "fetch mismatch"
echo "fetch by sha matches the uploaded bytes"
echo "$sha" > /root/acceptance-blob.sha
cp "$payload" /root/acceptance-blob.bin

# 6. Signer script present in the Wildbloom container.
page=$(curl -fsS http://127.0.0.1:3743/) || fail "Wildbloom page not served on loopback"
grep -qF 'nostr-provider.js?v=tab-signer-v4' <<<"$page" || fail "no signer injection"
provider=$(curl -fsS http://127.0.0.1:3743/nostr-provider.js) || fail "provider not served"
grep -q 'NIP-07' <<<"$provider" || fail "provider not copied from host"
echo "signer injection and provider present"
echo "ACCEPTANCE (scripted) PASSED: blob $sha"
EOF
argv=$(printf '%q ' "$host")
remote="$(cat "$root/scripts/lib/archy-login.bash")"$'\n'"$remote"
printf '%s\n' "$ARCHY_PASSWORD" | ssh "$NODE" "bash -c $(printf '%q' "$remote") remote $argv"
