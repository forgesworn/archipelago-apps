#!/usr/bin/env bash
# Print the digest of everything a frontend release is built from: the ARCHY_*
# lines of PINS, FRONTEND_SHA256 (the upstream asset we overlay), the Node
# major, the patch files and the build recipe. Wildbloom pin bumps do not change it.
# CI publishes it as the release's inputs.sha256 and compares against it.
set -euo pipefail
cd "$(dirname "$0")/.."
{ grep -E '^(ARCHY_REPO|ARCHY_REF|ARCHY_RELEASE|FRONTEND_SHA256|FRONTEND_NODE_MAJOR)=' PINS
  sha256sum upstream/patches/*.patch scripts/build-frontend.sh; } \
  | sha256sum | awk '{print $1}'
