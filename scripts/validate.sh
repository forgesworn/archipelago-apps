#!/usr/bin/env bash
# Validate every apps/*/manifest.yml with archy's shell validator and its Rust parser.
# Expects archy fetched (and patched) at .cache/archy.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
archy=$root/.cache/archy
shopt -s nullglob
manifests=("$root"/apps/*/manifest.yml)
[ ${#manifests[@]} -gt 0 ] || { echo "no manifests"; exit 0; }
for m in "${manifests[@]}"; do
  out=$("$archy/scripts/validate-app-manifest.sh" "$m" 2>&1) || true
  echo "$out" | tail -n 5
  echo "$out" | grep -q 'STATUS: APPROVED' || { echo "REJECTED by archy validator: $m"; exit 1; }
done
cargo run -q --manifest-path "$root/tools/manifest-check/Cargo.toml" -- "${manifests[@]}"
# The checker itself must still reject a bad placeholder.
if cargo run -q --manifest-path "$root/tools/manifest-check/Cargo.toml" -- "$root/tests/manifests/bad-placeholder.yml" >/dev/null; then
  echo "manifest-check accepted a bad placeholder"; exit 1
fi
