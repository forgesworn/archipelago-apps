#!/usr/bin/env bash
# Serve the wildbloom image and check the signer injection and cache headers.
set -euo pipefail
image=${1:?image}
cid=$(docker run -d --sysctl net.ipv6.conf.all.disable_ipv6=0 --sysctl net.ipv6.conf.lo.disable_ipv6=0 --cap-drop=ALL --cap-add CHOWN --cap-add SETGID --cap-add SETUID --security-opt no-new-privileges -p 127.0.0.1:3743:3743 "$image")
trap 'docker logs "$cid" | tail -n 30; docker rm -f "$cid" >/dev/null' EXIT
# Match the node (Podman/netavark gives containers ::1 on lo): GitHub's Docker disables IPv6.
ipv6_check() {
  docker exec "$cid" sh -c 'test -s /proc/net/if_inet6' \
    || { echo "FAIL: container has no IPv6 loopback; the sysctl did not take effect, so the localhost probe would not match the node" >&2; exit 1; }
}
ipv6_check
echo '// provider stub for smoke test' | docker exec -i "$cid" sh -c 'cat > /usr/share/nginx/html/nostr-provider.js'
for _ in $(seq 20); do curl -fsS http://127.0.0.1:3743/ >/dev/null && break; sleep 1; done
# Archipelago's generated health check (quadlet.rs:610 at the pinned core) runs wget against
# localhost inside the container, which resolves to ::1. Probe it the same way.
docker exec "$cid" sh -c 'wget -q -T 5 -O /dev/null http://localhost:3743/'
html=$(curl -fsS http://127.0.0.1:3743/)
echo "$html" | grep -qF '<script src="/nostr-provider.js?v=tab-signer-v4"></script></head>'
echo "$html" | grep -qF "script-src 'self'"
curl -fsSI http://127.0.0.1:3743/nostr-provider.js | grep -qi '^cache-control: no-cache, no-store'
# SPA fallback keeps the injection; this does not prove deep-link assets load (Vite base "./").
curl -fsS http://127.0.0.1:3743/some/deep/link | grep -qF 'nostr-provider.js?v=tab-signer-v4'
echo "smoke OK: wildbloom"
