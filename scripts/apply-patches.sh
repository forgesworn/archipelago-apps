#!/usr/bin/env bash
# Apply upstream/patches/*.patch onto a pristine archy checkout, in order.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
dest=${1:-$root/.cache/archy}
git -C "$dest" -c user.name=archipelago-apps -c user.email=ci@invalid am --abort >/dev/null 2>&1 || true
shopt -s nullglob
for p in "$root"/upstream/patches/*.patch; do
  git -C "$dest" -c user.name=archipelago-apps -c user.email=ci@invalid am --3way "$p"
done
