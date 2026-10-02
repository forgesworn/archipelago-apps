#!/usr/bin/env bash
# Start the wildbloom-node image, upload a blob signed by a throwaway owner key, fetch it back.
set -euo pipefail
image=${1:?image}
here=$(cd "$(dirname "$0")" && pwd)
(cd "$here" && npm install --silent)
secret=$(openssl rand -hex 32)
pubkey=$(cd "$here" && node --input-type=module -e 'import { getPublicKey } from "nostr-tools/pure"; import { hexToBytes } from "nostr-tools/utils"; process.stdout.write(getPublicKey(hexToBytes(process.argv[1])));' "$secret")
data=$(mktemp -d)
# --read-only matches the manifest's readonly_root: true.
cid=$(docker run -d --read-only --tmpfs /tmp -p 127.0.0.1:3742:3742 -v "$data:/data" \
  -e WILDBLOOM_ALLOW_PUBKEYS="$pubkey" -e WILDBLOOM_PUBLIC_URL=http://localhost:3742 \
  -e WILDBLOOM_SERVER_NAME=localhost,127.0.0.1 "$image")
trap 'docker logs "$cid" | tail -n 50; docker rm -f "$cid" >/dev/null' EXIT
for _ in $(seq 30); do curl -fsS http://127.0.0.1:3742/healthz >/dev/null && break; sleep 1; done
curl -fsS http://127.0.0.1:3742/healthz
payload=$(mktemp); head -c 4096 /dev/urandom > "$payload"
sha=$(sha256sum "$payload" | awk '{print $1}')
auth=$(cd "$here" && node sign-auth.mjs "$secret" upload "$sha" localhost)
curl -fsS -X PUT --data-binary @"$payload" -H "Authorization: Nostr $auth" \
  -H "Content-Type: application/octet-stream" http://127.0.0.1:3742/upload
curl -fsS "http://127.0.0.1:3742/$sha" -o "$payload.back"
cmp "$payload" "$payload.back"
# A stranger's key must be refused.
stranger=$(openssl rand -hex 32)
bad=$(cd "$here" && node sign-auth.mjs "$stranger" upload "$sha" localhost)
code=$(curl -s -o /dev/null -w '%{http_code}' -X PUT --data-binary @"$payload" -H "Authorization: Nostr $bad" http://127.0.0.1:3742/upload)
[ "$code" -ge 400 ] || { echo "stranger upload was accepted ($code)"; exit 1; }
echo "smoke OK: $sha"
