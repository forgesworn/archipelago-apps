#!/usr/bin/env bash
# Fetch archy at the pinned commit. Sparse by default (local disk is tight);
# ARCHY_FULL=1 fetches the whole tree (CI backend builds).
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
. "$root/PINS"
dest=${1:-$root/.cache/archy}
if [ ! -d "$dest/.git" ]; then
  git init -q "$dest"
  git -C "$dest" remote add origin "$ARCHY_REPO"
fi
if [ "${ARCHY_FULL:-0}" != 1 ]; then
  git -C "$dest" sparse-checkout set --no-cone \
    /core/ /docs/app-manifest-spec.md /docs/app-developer-guide.md \
    /scripts/validate-app-manifest.sh /scripts/setup-node-ca.sh /apps/ /neode-ui/public/nostr-provider.js \
    /image-recipe/configs/ /image-recipe/_archived/build-auto-installer-iso.sh \
    /tests/lifecycle/lib/
fi
git -C "$dest" fetch -q --depth 1 origin "$ARCHY_REF"
git -C "$dest" checkout -q --detach FETCH_HEAD
test "$(git -C "$dest" rev-parse HEAD)" = "$ARCHY_REF"
echo "archy at $ARCHY_REF in $dest"
