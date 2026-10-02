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
else
  git -C "$dest" sparse-checkout disable
fi
# The Gitea host sometimes resets the connection mid-fetch: retry, briefly.
for attempt in 1 2 3; do
  git -C "$dest" fetch -q --depth 1 origin "$ARCHY_REF" && break
  [ "$attempt" = 3 ] && { echo "fetching $ARCHY_REF failed after 3 attempts" >&2; exit 1; }
  echo "fetch attempt $attempt failed; retrying in $((attempt * 5))s" >&2
  sleep $((attempt * 5))
done
# Pristine tree at the pin, whatever a previous run left: an interrupted
# `git am`, applied patches, edits or untracked files (inside $dest only).
# (am --abort writes a reflog entry, so it needs an identity, as in apply-patches.sh.)
git -C "$dest" -c user.name=archipelago-apps -c user.email=ci@invalid am --abort >/dev/null 2>&1 || true
git -C "$dest" checkout -q -f --detach FETCH_HEAD
git -C "$dest" clean -fdq
test "$(git -C "$dest" rev-parse HEAD)" = "$ARCHY_REF"
echo "archy at $ARCHY_REF in $dest"
