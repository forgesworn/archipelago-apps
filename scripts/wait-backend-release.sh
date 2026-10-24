#!/usr/bin/env bash
# Publish a catalogue only when its matching backend is available.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
. "$root/PINS"
expected=$("$root/scripts/backend-inputs.sh")
tag="backend-${ARCHY_RELEASE}-p${BACKEND_PATCH_LEVEL}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
for attempt in $(seq 1 120); do
  if gh release download "$tag" --repo forgesworn/archipelago-apps \
      --pattern inputs.sha256 --pattern archipelago.sha256 --dir "$work" --clobber 2>"$work/error" \
      && [ -s "$work/inputs.sha256" ] && [ -s "$work/archipelago.sha256" ]; then
    actual=$(cat "$work/inputs.sha256")
    [ "$actual" = "$expected" ] || { echo "Backend release $tag has different inputs; refusing to publish this catalogue" >&2; exit 1; }
    echo "Matching backend $tag is available"
    exit 0
  fi
  if [ "$attempt" -lt 120 ]; then sleep 30; fi
done
echo "Matching backend $tag was not published; catalogue remains unpublished" >&2
exit 1
