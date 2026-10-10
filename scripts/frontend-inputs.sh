#!/usr/bin/env bash
# Print the digest of everything a frontend release is built from: the ARCHY_*
# lines of PINS, FRONTEND_SHA256 (the upstream asset we overlay), the Node
# major, the patches that touch neode-ui/ (scripts/lib/patches.bash) and the build recipe. Wildbloom pin bumps do not change it.
# CI publishes it as the release's inputs.sha256 and compares against it.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/patches.bash
{ grep -E '^(ARCHY_REPO|ARCHY_REF|ARCHY_RELEASE|FRONTEND_SHA256|FRONTEND_FALLBACK_URL|FRONTEND_FALLBACK_SHA256|FRONTEND_NODE_MAJOR)=' PINS
  frontend_patches | hash_listed
  sha256sum scripts/build-frontend.sh scripts/lib/patches.bash; } \
  | sha256sum | awk '{print $1}'
