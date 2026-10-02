#!/usr/bin/env bash
# Print the digest of everything a backend release is built from: the ARCHY_*
# lines of PINS and the patch files. Wildbloom pin bumps do not change it.
# CI publishes it as the release's inputs.sha256 and compares against it.
set -euo pipefail
cd "$(dirname "$0")/.."
{ grep -E '^(ARCHY_REPO|ARCHY_REF|ARCHY_RELEASE)=' PINS; sha256sum upstream/patches/*.patch; } \
  | sha256sum | awk '{print $1}'
