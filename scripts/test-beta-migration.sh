#!/usr/bin/env bash
# Generated-state fixture only. Never connects to the owner's node.
set -euo pipefail
[ "${CI:-}" = true ] || { echo 'Use an isolated CI runner' >&2; exit 1; }
root=$(cd "$(dirname "$0")/.." && pwd)
name="beta-migration-${GITHUB_RUN_ID:-$$}-${GITHUB_RUN_ATTEMPT:-1}"
work=$(mktemp -d)
mkdir -p "$root/.local"
cleanup() {
  result=$?
  docker exec "$name" journalctl --no-pager -n 3000 > "$root/.local/beta-migration-journal.log" 2>&1 || true
  if [ "$result" != 0 ]; then
    tail -n 100 "$root/.local/beta-migration-journal.log" >&2
  fi
  docker rm -f "$name" >/dev/null 2>&1 || true
  docker image rm "$name" >/dev/null 2>&1 || true
  rm -rf "$work"
  exit "$result"
}
trap cleanup EXIT
archy=$root/.cache/migration-alpha-source/.cache/archy
bundle=$work/bundle
mkdir -p "$bundle/archy/image-recipe/configs/snippets" "$bundle/archy/scripts" "$bundle/archy/tests/lifecycle/lib"
cp "$root/.cache/migration-alpha-source/PINS" "$root/node/install-lite.sh" "$root/scripts/recover-wildbloom-payment.py" "$bundle/"
cp "$root/.cache/migration-alpha/archipelago" "$root/.cache/migration-alpha/frontend.tar.gz" "$bundle/"
(cd "$bundle" && sha256sum archipelago > archipelago.sha256 && sha256sum frontend.tar.gz > frontend.sha256)
cp "$archy/image-recipe/configs/archipelago.service" "$archy/image-recipe/configs/nginx-archipelago.conf" "$bundle/archy/image-recipe/configs/"
cp "$archy"/image-recipe/configs/snippets/*.conf "$bundle/archy/image-recipe/configs/snippets/"
cp "$archy/scripts/setup-node-ca.sh" "$bundle/archy/scripts/"
cp "$archy/tests/lifecycle/lib/rpc.bash" "$bundle/archy/tests/lifecycle/lib/"
sed -n "/<<'SECRETSSCRIPT'/,/^SECRETSSCRIPT\$/p" "$archy/image-recipe/_archived/build-auto-installer-iso.sh" | sed '1d;$d' > "$bundle/first-boot-secrets.sh"
test -s "$bundle/first-boot-secrets.sh"
docker build -f "$root/tests/node/Dockerfile" -t "$name" "$root/tests/node"
docker run -d --name "$name" --privileged --cgroupns host \
  --mount type=bind,source=/sys/fs/cgroup,target=/sys/fs/cgroup \
  --tmpfs /run --tmpfs /tmp "$name" >/dev/null
docker cp "$bundle" "$name:/bundle"
docker cp "$root/.cache/migration-beta" "$name:/beta"
docker cp "$root/tests/migration" "$name:/rehearsal"
docker exec "$name" bash /bundle/install-lite.sh /bundle podman
# Fetch a tiny generated-data workload before the fixture loses external routes.
docker exec "$name" runuser -u archipelago -- env XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus podman pull docker.io/library/busybox:1.37.0
# No live identities or wallet copies: disconnect before generating any state.
docker exec "$name" sh -c 'ip -4 route del default; ip -6 route del default 2>/dev/null || true'
docker exec -e ARCHY_GENERATED_MIGRATION_FIXTURE=1 "$name" python3 /rehearsal/installed-node.py > "$root/.local/beta-migration-result.json"
cat "$root/.local/beta-migration-result.json"
