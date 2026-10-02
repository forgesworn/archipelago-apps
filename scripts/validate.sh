#!/usr/bin/env bash
# Validate every apps/*/manifest.yml with archy's shell validator and its Rust parser.
# Expects archy fetched (and patched) at .cache/archy.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
archy=$root/.cache/archy
shopt -s nullglob
manifests=("$root"/apps/*/manifest.yml)
# The checker must reject a bad placeholder, for the right reason. Runs first so
# CI builds and exercises it even when there are no apps yet.
if selftest=$(cargo run -q --manifest-path "$root/tools/manifest-check/Cargo.toml" -- "$root/tests/manifests/bad-placeholder.yml" 2>&1); then
  echo "manifest-check accepted a bad placeholder"; exit 1
fi
grep -q 'unknown placeholder' <<<"$selftest" || { echo "manifest-check self-test failed for the wrong reason:"; echo "$selftest"; exit 1; }
echo "manifest-check self-test passed"
[ ${#manifests[@]} -gt 0 ] || { echo "no manifests"; exit 0; }
for m in "${manifests[@]}"; do
  out=$("$archy/scripts/validate-app-manifest.sh" "$m" 2>&1) || true
  tail -n 5 <<<"$out"
  grep -q 'STATUS: APPROVED' <<<"$out" || { echo "REJECTED by archy validator: $m"; exit 1; }
done
cargo run -q --manifest-path "$root/tools/manifest-check/Cargo.toml" -- "${manifests[@]}"
