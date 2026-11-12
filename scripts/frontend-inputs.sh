#!/usr/bin/env bash
# Print the digest of everything a frontend release is built from: the ARCHY_*
# lines of PINS, FRONTEND_SHA256 (the upstream asset we overlay), the Node
# major, every backend/frontend/runtime patch and the build recipe.
# Wildbloom pin bumps do not change it.
# CI publishes it as the release's inputs.sha256 and compares against it.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/patches.bash
{ grep -E '^(ARCHY_REPO|ARCHY_REF|ARCHY_RELEASE|FRONTEND_SHA256|FRONTEND_FALLBACK_URL|FRONTEND_FALLBACK_SHA256|FRONTEND_NODE_MAJOR)=' PINS
  # The beta frontend carries runtime helpers patched alongside the backend.
  # Hash the complete stack so a backend/helper change cannot reuse stale bytes.
  sha256sum upstream/patches/*.patch
  sha256sum scripts/apply-patches.sh scripts/build-frontend.sh scripts/stage-runtime-payload.py scripts/include-bundle-app.py scripts/lib/patches.bash apps/spry/manifest.yml; } \
  | sha256sum | awk '{print $1}'
