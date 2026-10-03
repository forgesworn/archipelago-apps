# Route upstream/patches/*.patch by the paths they touch. Source from the repo root.
# A patch is frontend-only when every path it touches is under neode-ui/.
# Backend digests cover every patch that is not frontend-only; frontend digests
# cover every patch that touches neode-ui/ (a patch touching both counts for both).
# Paths are read from the "diff --git a/<path> b/<path>" lines (both sides, for renames).
patch_paths() { grep '^diff --git ' "$1" | awk '{sub(/^a\//, "", $3); sub(/^b\//, "", $4); print $3; print $4}'; }
patch_touches_frontend() { patch_paths "$1" | grep -q '^neode-ui/'; }
patch_frontend_only() { ! patch_paths "$1" | grep -qv '^neode-ui/'; }
# Print patch paths (relative to the repo root), one per line. Plain stdout, no
# arrays: macOS ships bash 3.2.
backend_patches() { local p; for p in upstream/patches/*.patch; do patch_frontend_only "$p" || echo "$p"; done; }
frontend_patches() { local p; for p in upstream/patches/*.patch; do ! patch_touches_frontend "$p" || echo "$p"; done; }
# Print "<sha256>  <path>" for each path on stdin (nothing for empty input).
hash_listed() { local l; l=$(cat); [ -z "$l" ] || printf '%s\n' "$l" | xargs sha256sum; }
