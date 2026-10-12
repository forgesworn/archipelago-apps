#!/usr/bin/env bash
# CI acceptance: use an immutable published package, or build a candidate locally.
# Never pushes. Missing tags may be built; registry errors fail closed.
set -euo pipefail
cd "$(dirname "$0")/.."
app=${1:?app id}
. ./PINS
. scripts/lib/app-image.bash
app_image "$app"
if probe=$(docker manifest inspect "$APP_TAG" 2>&1); then
  docker pull "$APP_TAG"
  echo "Acceptance uses published package $APP_TAG"
elif grep -qiE 'no such manifest|manifest unknown|name unknown|not found' <<<"$probe"; then
  case "$app" in
    wildbloom-node) arg=WILDBLOOM_NODE_REF ;;
    wildbloom) arg=WILDBLOOM_REF ;;
  esac
  docker buildx build --load --build-arg "$arg=$APP_REF" --tag "$APP_TAG" "apps/$app"
  echo "Acceptance uses locally built candidate $APP_TAG; nothing published"
else
  echo "Cannot establish package publication: $probe" >&2
  exit 1
fi
docker image inspect "$APP_TAG" --format 'Acceptance image ID: {{.Id}}'
