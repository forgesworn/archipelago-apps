#!/usr/bin/env bash
# Decide whether the frontend job can stop early. Prints "skip=true|false" on
# stdout and the reason on stderr. Usage: frontend-release-plan.sh <before-sha> [event]
#
# Skip only when a push changed nothing the build depends on AND the release
# for this tag already exists with an identical inputs.sha256. Anything unclear
# (manual run, unknown "before" sha, no release, no record, gh failing) means
# "do not skip", so the tests and build run as usual. A change to the workflow
# file or to the scripts it runs is never skipped, so such edits are exercised.
set -euo pipefail
cd "$(dirname "$0")/.."
before=${1-}
event=${2:-push}
. ./PINS
tag="frontend-${ARCHY_RELEASE}-p${FRONTEND_PATCH_LEVEL}"

no() { echo "skip=false"; echo "reason: $1" >&2; exit 0; }

[ "$event" = push ] || no "event is $event, not push"
[ -n "$before" ] && ! [[ "$before" =~ ^0+$ ]] || no "no usable before sha"
git cat-file -e "$before^{commit}" 2>/dev/null || no "before sha not in the clone"
git diff --quiet "$before" HEAD -- .github/workflows/frontend.yml scripts/fetch-archy.sh scripts/apply-patches.sh \
  scripts/frontend-inputs.sh scripts/frontend-release-plan.sh scripts/build-frontend.sh || no "frontend.yml or a script it runs changed"
gh release view "$tag" >/dev/null 2>&1 || no "release $tag does not exist"
prev=$(mktemp -d)
gh release download "$tag" -p inputs.sha256 -D "$prev" >/dev/null 2>&1 || no "release $tag has no inputs.sha256"
[ "$(cat "$prev/inputs.sha256")" = "$(scripts/frontend-inputs.sh)" ] || no "inputs differ from release $tag"
echo "skip=true"
echo "reason: $tag already built from these inputs; keeping the published tarball" >&2
