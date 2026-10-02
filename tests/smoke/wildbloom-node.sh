#!/usr/bin/env bash
# Start the wildbloom-node image, upload a blob signed by a throwaway owner key, fetch it back.
set -euo pipefail
image=${1:?image}
here=$(cd "$(dirname "$0")" && pwd)
(cd "$here" && npm ci --silent)
secret=$(openssl rand -hex 32)
pubkey=$(cd "$here" && node --input-type=module -e 'import { getPublicKey } from "nostr-tools/pure"; import { hexToBytes } from "nostr-tools/utils"; process.stdout.write(getPublicKey(hexToBytes(process.argv[1])));' "$secret")
# Production ownership: rootless Podman maps container uid 0 to the host user that owns the bind
# directory, so container root owns /data. Reproduce that with a root-owned dir; wildbloomd chmods
# /data to 0700 on start, which needs ownership (or CAP_FOWNER, which the manifest drops).
data=$(mktemp -d)
sudo chown 0:0 "$data"
# --read-only matches the manifest's readonly_root: true.
cid=$(docker run -d --cap-drop=ALL --security-opt no-new-privileges --read-only --tmpfs /tmp -p 127.0.0.1:3742:3742 -v "$data:/data" \
  -e WILDBLOOM_ALLOW_PUBKEYS="$pubkey" -e WILDBLOOM_PUBLIC_URL=http://localhost:3742 \
  -e WILDBLOOM_SERVER_NAME=localhost,127.0.0.1 "$image")
trap 'docker logs "$cid" | tail -n 50; docker rm -f "$cid" >/dev/null; sudo rm -rf "$data"' EXIT
# The node's containers (Podman/netavark) have ::1 on lo, and so do Docker 26+ containers on an
# IPv4-only network. Assert it so the localhost probe below matches the node. Test the content:
# procfs files always stat as size 0, so `test -s /proc/net/if_inet6` is always false.
ipv6_check() {
  docker exec "$cid" grep -qs '^00000000000000000000000000000001 ' /proc/net/if_inet6 && return 0
  echo "FAIL: container has no ::1 on lo, so the localhost probe would not match the node" >&2
  echo "--- /proc/net/if_inet6 in the container:" >&2
  docker exec "$cid" cat /proc/net/if_inet6 >&2 || true
  exit 1
}
ipv6_check
for _ in $(seq 30); do curl -fsS http://127.0.0.1:3742/healthz >/dev/null && break; sleep 1; done
curl -fsS http://127.0.0.1:3742/healthz
# Archipelago's generated health check (quadlet.rs:610 at the pinned core) runs this exact chain
# inside the container. debian-slim has neither wget nor curl, so in practice it is the bash
# /dev/tcp branch against localhost; run the whole command as the node does.
docker exec "$cid" sh -c "if command -v wget >/dev/null 2>&1; then wget -q -T 5 -O /dev/null http://localhost:3742/healthz; elif command -v curl >/dev/null 2>&1; then curl -fsS -m 5 http://localhost:3742/healthz; elif command -v bash >/dev/null 2>&1; then bash -c 'exec 3<>/dev/tcp/localhost/3742'; else exit 0; fi"
payload=$(mktemp); head -c 4096 /dev/urandom > "$payload"
sha=$(sha256sum "$payload" | awk '{print $1}')
auth=$(cd "$here" && node sign-auth.mjs "$secret" upload "$sha" localhost)
# The server reads X-SHA-256 (and Content-Length, which curl sets) before it checks authorisation.
curl -fsS -X PUT --data-binary @"$payload" -H "Authorization: Nostr $auth" \
  -H "X-SHA-256: $sha" -H "Content-Type: application/octet-stream" http://127.0.0.1:3742/upload
curl -fsS "http://127.0.0.1:3742/$sha" -o "$payload.back"
cmp "$payload" "$payload.back"
# A stranger's key must be refused. Fresh payload, so the refusal is about auth, not a stored blob.
stranger=$(openssl rand -hex 32)
payload2=$(mktemp); head -c 4096 /dev/urandom > "$payload2"
sha2=$(sha256sum "$payload2" | awk '{print $1}')
bad=$(cd "$here" && node sign-auth.mjs "$stranger" upload "$sha2" localhost)
code=$(curl -s -o /dev/null -w '%{http_code}' -X PUT --data-binary @"$payload2" -H "Authorization: Nostr $bad" \
  -H "X-SHA-256: $sha2" -H "Content-Type: application/octet-stream" http://127.0.0.1:3742/upload)
{ [ "$code" = 401 ] || [ "$code" = 403 ]; } || { echo "stranger upload expected 401 or 403, got $code"; exit 1; }
echo "smoke OK: $sha (stranger refused with $code)"
