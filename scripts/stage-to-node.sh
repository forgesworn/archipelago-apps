#!/usr/bin/env bash
# Stage an app manifest on a node and install it through the dashboard's JSON-RPC.
#
# Usage: ARCHY_PASSWORD=... scripts/stage-to-node.sh <app-id>
# Env:   NODE (default root@95.216.164.146), ARCHY_PASSWORD (dashboard password),
#        INSTALL_TIMEOUT (seconds to wait for running, default 600).
#
# The manifest goes under web-ui/archipelago-runtime/apps/<id>/. On every start
# the backend replaces /opt/archipelago/apps with that directory before it loads
# manifests, so this is the only staging path that survives a restart. The RPC
# listener opens after the manifest load, so a successful RPC call after the
# restart means the orchestrator knows the app.
set -euo pipefail
app=${1:?app id}
: "${NODE:=root@95.216.164.146}" "${ARCHY_PASSWORD:?dashboard password}"
: "${INSTALL_TIMEOUT:=600}"
root=$(cd "$(dirname "$0")/.." && pwd)
manifest=$root/apps/$app/manifest.yml
[ -f "$manifest" ] || { echo "no manifest at $manifest" >&2; exit 1; }
image=$(grep -oE 'image: *[^[:space:]]+' "$manifest" | head -1 | awk '{print $2}')
dir=/opt/archipelago/web-ui/archipelago-runtime/apps/$app

ssh "$NODE" "install -d -o archipelago -g archipelago '$dir'"
scp -q "$manifest" "$NODE:$dir/manifest.yml"
ssh "$NODE" "chown archipelago:archipelago '$dir/manifest.yml' && systemctl restart archipelago"

# The remote script travels as an argument and the password alone on stdin,
# so the password stays off the ssh command line.
read -r -d '' remote <<'EOF' || true
set -euo pipefail
IFS= read -r ARCHY_PASSWORD
export ARCHY_PASSWORD ARCHY_FORCE_LOGIN=1
app=$1 image=$2 timeout=$3

# Wait for the backend to answer RPC again after the restart.
for _ in $(seq 60); do
  curl -sk -m 5 -X POST https://127.0.0.1/rpc/v1 -H 'Content-Type: application/json' \
    --data-raw '{"jsonrpc":"2.0","method":"health","id":1}' | jq -e '.result' >/dev/null 2>&1 && break
  sleep 2
done

source /opt/archipelago/rpc.bash
rpc_login >/dev/null
echo "package.install $app ($image):"
rpc_result package.install "{\"id\":\"$app\",\"dockerImage\":\"$image\"}"

# Bounded wait: running and healthy (or no health reported), fail fast on a
# terminal failure. A failed install with no container removes the entry; one
# that left a container behind is set to stopped with the reason attached.
deadline=$(( $(date +%s) + timeout )); seen=0
while (( $(date +%s) < deadline )); do
  entry=$(rpc_result server.get-state | jq -c --arg id "$app" '.data["package-data"][$id] // empty')
  if [ -z "$entry" ]; then
    if [ "$seen" = 1 ]; then
      echo "FAIL: $app install entry vanished (install failed with nothing left behind)" >&2
      journalctl -u archipelago --since '-15min' --no-pager | grep -F "$app" | tail -20 >&2
      exit 1
    fi
  else
    seen=1
    state=$(jq -r '.state' <<<"$entry"); health=$(jq -r '.health // "none"' <<<"$entry")
    case "$state" in
      running) if [ "$health" = healthy ] || [ "$health" = none ]; then
                 echo "$app: state=$state health=$health"; exit 0
               fi ;;
      stopped|exited)
        echo "FAIL: $app state=$state: $(jq -r '.["install-progress"].message // "no message"' <<<"$entry")" >&2
        journalctl -u archipelago --since '-15min' --no-pager | grep -F "$app" | tail -20 >&2
        exit 1 ;;
    esac
  fi
  sleep 5
done
echo "FAIL: $app not running and healthy within ${timeout}s" >&2
exit 1
EOF
argv=$(printf '%q ' "$app" "$image" "$INSTALL_TIMEOUT")
printf '%s\n' "$ARCHY_PASSWORD" | ssh "$NODE" "bash -c $(printf '%q' "$remote") remote $argv"
