#!/usr/bin/env bash
# Serve the wildbloom image and check the signer injection and cache headers.
set -euo pipefail
image=${1:?image}
cid=$(docker run -d --cap-drop=ALL --cap-add CHOWN --cap-add SETGID --cap-add SETUID --security-opt no-new-privileges -p 127.0.0.1:3743:3743 "$image")
trap 'docker logs "$cid" | tail -n 30; docker rm -f "$cid" >/dev/null' EXIT
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
for _ in $(seq 20); do curl -fsS http://127.0.0.1:3743/ >/dev/null && break; sleep 1; done
# Archipelago's generated health check (quadlet.rs:610 at the pinned core) runs wget against
# localhost inside the container, which resolves to ::1. Probe it the same way.
docker exec "$cid" sh -c 'wget -q -T 5 -O /dev/null http://localhost:3743/'
html=$(curl -fsS http://127.0.0.1:3743/)
grep -qF '<script src="/nostr-provider.js?v=tab-signer-v4"></script></head>' <<<"$html"
grep -qF "script-src 'self'" <<<"$html"
# The baked provider is served (no post_install here, so it must come from the image),
# uncached, and is Archipelago's real file rather than a placeholder.
curl -fsSI http://127.0.0.1:3743/nostr-provider.js | grep -qi '^cache-control: no-cache, no-store'
# Capture first: under pipefail, grep -q exiting early could fail curl with SIGPIPE.
provider=$(curl -fsS http://127.0.0.1:3743/nostr-provider.js)
grep -qF "type: 'nostr-request'" <<<"$provider"
# SPA fallback keeps the injection; this does not prove deep-link assets load (Vite base "./").
fallback=$(curl -fsS http://127.0.0.1:3743/some/deep/link)
grep -qF 'nostr-provider.js?v=tab-signer-v4' <<<"$fallback"
# Unsupported API probes must never look like a working login service.
for path in /api/nostr-auth/health /api/auth/nostr/session; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:3743$path")
  [ "$code" = 404 ] || { echo "FAIL: $path expected 404, got $code"; exit 1; }
done
# The pinned client must include the refreshed local recovery and service UI.
for marker in 'id="client-retrieve"' 'id="saved-recovery"' 'id="storage-layout-summary"' 'id="storage-audit"' 'id="checkout-offers"'; do
  grep -qF "$marker" <<<"$html"
done
echo "smoke OK: wildbloom"
