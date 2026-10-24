#!/usr/bin/env bash
# CI-only privileged disposable Debian host, with its own nested Docker daemon.
set -euo pipefail
[ "${CI:-}" = true ] || { echo 'Run this host fixture on an isolated CI runner' >&2; exit 1; }
root=$(cd "$(dirname "$0")/.." && pwd)
archy=${1:?pass patched Archipelago checkout}
frontend=${2:?pass matching built frontend directory}
binary=${3:?pass built release controller}
image=${4:?pass locally built Spry image}
name="spry-docker-host-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}"
work=$(mktemp -d)
cleanup() {
  code=$?
  if [ "$code" != 0 ]; then
    docker exec "$name" journalctl -u archipelago -u docker -u archipelago-fips --no-pager -n 1000 > "$root/.local/docker-host-journal.log" 2>&1 || true
  fi
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker image rm "$name" >/dev/null 2>&1 || true
  rm -rf "$work"
  exit "$code"
}
trap cleanup EXIT
mkdir -p "$root/.local" "$work/bundle/archy/image-recipe/configs/snippets" \
  "$work/bundle/archy/scripts" "$work/bundle/archy/tests/lifecycle/lib"
bundle=$work/bundle
cp "$root/PINS" "$root/node/install-lite.sh" "$root/scripts/recover-wildbloom-payment.py" "$bundle/"
cp "$binary" "$bundle/archipelago"
(cd "$bundle" && sha256sum archipelago > archipelago.sha256)
cp "$frontend/frontend.tar.gz" "$frontend/frontend.sha256" "$bundle/"
cp "$archy/image-recipe/configs/archipelago.service" "$archy/image-recipe/configs/archipelago-fips.service" \
  "$archy/image-recipe/configs/nginx-archipelago.conf" "$bundle/archy/image-recipe/configs/"
cp "$archy"/image-recipe/configs/snippets/*.conf "$bundle/archy/image-recipe/configs/snippets/"
cp "$archy/scripts/setup-node-ca.sh" "$bundle/archy/scripts/"
cp "$archy/tests/lifecycle/lib/rpc.bash" "$bundle/archy/tests/lifecycle/lib/"
sed -n "/<<'SECRETSSCRIPT'/,/^SECRETSSCRIPT\$/p" "$archy/image-recipe/_archived/build-auto-installer-iso.sh" \
  | sed '1d;$d' > "$bundle/first-boot-secrets.sh"
gh release download v0.4.1 --repo jmcorgan/fips --pattern fips_0.4.1_amd64.deb --dir "$work"
cp "$work/fips_0.4.1_amd64.deb" "$bundle/fips.deb"
docker build -f "$root/tests/node/Dockerfile" -t "$name" "$root/tests/node"
# No host network, Docker socket, host data or host service files are mounted.
# cgroup access and privileges belong only to this disposable CI host fixture.
docker run -d --name "$name" --privileged --cgroupns host \
  --mount type=bind,source=/sys/fs/cgroup,target=/sys/fs/cgroup \
  --tmpfs /run --tmpfs /tmp "$name" >/dev/null
docker cp "$bundle" "$name:/bundle"
docker cp "$root/tests/node/docker-host.py" "$name:/docker-host.py"
docker exec "$name" bash /bundle/install-lite.sh /bundle docker
docker save "$image" | docker exec -i "$name" docker load >/dev/null
# Stop external networking before generating identities. The physical home
# and independent NAT gates remain separate from this host-install check.
docker exec "$name" sh -c 'ip -4 route del default; ip -6 route del default 2>/dev/null || true'
docker exec "$name" python3 /docker-host.py > "$root/.local/docker-host.json"
cat "$root/.local/docker-host.json"
