#!/usr/bin/env bash
# Decide what the images workflow does for one app, asking the registry first.
# Usage: image-plan.sh <app-id> <before-sha> [event]
#
# Writes build=, push=, tag= and ref= to $GITHUB_OUTPUT (stdout when unset) and
# explains itself with ::notice:: / ::error:: lines on stdout.
#
#   Tag not in the registry               build, smoke-test, push.
#   Tag published, image inputs changed   fail: bump the app's PKG_REV in PINS.
#   Tag published, image inputs unchanged build and smoke-test without pushing
#     if the smoke test or its helpers changed, on a manual run, or when the
#     change cannot be determined (no usable "before" sha); otherwise nothing.
#
# A published tag is never replaced: the node never re-pulls a tag it has.
# Image inputs are the Docker build context (apps/<id>/ without manifest.yml,
# which is not in the image) and the app's own PINS lines. Smoke inputs are the
# smoke script, its npm helpers (wildbloom-node), this script, its library and
# the workflow itself. The packages are public, so the registry probe needs no
# login. Anything other than a clear "found" or "not found" fails closed.
set -euo pipefail
cd "$(dirname "$0")/.."
app=${1:?app id}
before=${2-}
event=${3:-push}
. ./PINS
. scripts/lib/app-image.bash
app_image "$app"

common_smoke=(.github/workflows/images.yml scripts/image-plan.sh scripts/lib/app-image.bash)
case "$app" in
  wildbloom-node)
    smoke=(tests/smoke/wildbloom-node.sh tests/smoke/package.json
           tests/smoke/package-lock.json tests/smoke/sign-auth.mjs)
    pin_re='^(WILDBLOOM_NODE_REF|WILDBLOOM_NODE_PKG_REV)=' ;;
  wildbloom)
    smoke=(tests/smoke/wildbloom.sh)
    pin_re='^(WILDBLOOM_REF|WILDBLOOM_PKG_REV)=' ;;
esac
smoke+=("${common_smoke[@]}")
context=("apps/$app" ":(exclude)apps/$app/manifest.yml")

out=${GITHUB_OUTPUT:-/dev/stdout}
decide() { # build push message-kind message
  { echo "build=$1"; echo "push=$2"; echo "tag=$APP_TAG"; echo "ref=$APP_REF"; } >> "$out"
  echo "::$3::$app: $4"
  exit 0
}
die() { echo "::error::$app: $1"; exit 1; }

# 1. The registry.
if probe=$(docker manifest inspect "$APP_TAG" 2>&1); then
  published=true
elif grep -qiE 'no such manifest|manifest unknown|name unknown|not found' <<<"$probe"; then
  published=false
else
  die "cannot tell whether $APP_TAG is published: $probe"
fi
[ "$published" = true ] || decide true true notice "$APP_TAG is not published; building, testing and pushing it"

# 2. Published: what changed since "before"?
comparable=true
if [ "$event" != push ]; then comparable=false why="event is $event"
elif [ -z "$before" ] || [[ "$before" =~ ^0+$ ]]; then comparable=false why="no usable before sha"
elif ! git cat-file -e "$before^{commit}" 2>/dev/null; then comparable=false why="before sha $before is not in the clone"
fi

if [ "$comparable" = true ]; then
  image_changed=false
  git diff --quiet "$before" HEAD -- "${context[@]}" || image_changed=true
  old=$(git show "$before:PINS" 2>/dev/null | grep -E "$pin_re" || true)
  new=$(grep -E "$pin_re" PINS || true)
  [ "$old" = "$new" ] || image_changed=true
  [ "$image_changed" = false ] \
    || die "$APP_TAG is already published but its image inputs changed since $before; bump the app's PKG_REV in PINS (and the manifest tag)"
  if git diff --quiet "$before" HEAD -- "${smoke[@]}"; then
    decide false false notice "$APP_TAG is already published and nothing it is built or tested from changed; nothing to do"
  fi
  decide true false notice "$APP_TAG is already published; its smoke test changed, so building and testing it without pushing"
fi
# A manual run, or a change we cannot see: test the published inputs again.
decide true false notice "$APP_TAG is already published ($why); building and testing it without pushing"
