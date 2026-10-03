#!/usr/bin/env bash
# Print the digest of everything a backend release is built from: the ARCHY_*
# lines of PINS and the patch files that are not frontend-only (scripts/lib/patches.bash). Wildbloom pin bumps do not change it.
# CI publishes it as the release's inputs.sha256 and compares against it.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/lib/patches.bash
{ grep -E '^(ARCHY_REPO|ARCHY_REF|ARCHY_RELEASE)=' PINS; backend_patches | hash_listed; } \
  | sha256sum | awk '{print $1}'
