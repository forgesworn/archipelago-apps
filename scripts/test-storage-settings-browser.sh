#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
archy=${1:-$root/.cache/archy-selling}
archy=$(cd "$archy" && pwd)
fixture="$archy/neode-ui/storage-preview.html"
test ! -e "$fixture" || { echo "Refusing to replace existing browser fixture" >&2; exit 1; }
cp "$root/tests/dashboard/storage-preview.html" "$fixture"
pid=
cleanup() { [ -z "$pid" ] || kill "$pid" 2>/dev/null || true; rm -f "$fixture"; }
trap cleanup EXIT
mkdir -p "$root/.cache"
(cd "$archy/neode-ui" && exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 15173 --strictPort) > "$root/.cache/storage-settings-vite.log" 2>&1 &
pid=$!
for attempt in $(seq 1 60); do
  kill -0 "$pid" 2>/dev/null || { cat "$root/.cache/storage-settings-vite.log"; exit 1; }
  curl -fsS http://127.0.0.1:15173/storage-preview.html >/dev/null 2>&1 && break
  sleep 1
done
cd "$root"
node tests/dashboard/storage-selling.mjs "$archy"
