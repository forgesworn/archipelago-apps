#!/usr/bin/env bash
# Build the dashboard frontend from the patched archy tree and repack it as
# upstream's own release tarball, with only the neode-ui build replaced.
#
# Usage: scripts/build-frontend.sh [archy-dir]
#   archy-dir  a full checkout already at ARCHY_REF with upstream/patches applied
#              (default .cache/archy-frontend; never the backend's .cache/archy)
# Env:   OUT_DIR (default .cache/frontend-out) receives frontend.tar.gz,
#        frontend.sha256 and inputs.sha256.
#
# Upstream's tarball (FRONTEND_SHA256) is flat: ./index.html, ./assets/..., plus
# payload that is not neode-ui's build: aiui/ (scripts/build-aiui.sh) and
# archipelago-runtime/ (apps, scripts, docker, radio tools). We keep those from
# the verified upstream asset and replace everything neode-ui's build produces.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
. "$root/PINS"
archy=${1:-$root/.cache/archy-frontend}
OUT_DIR=${OUT_DIR:-$root/.cache/frontend-out}
case $(cd "$archy" && pwd) in "$root/.cache/archy") echo "refusing to build in .cache/archy" >&2; exit 1;; esac
patches=("$root"/upstream/patches/*.patch)
[ "$(git -C "$archy" rev-list --count "$ARCHY_REF..HEAD")" = "${#patches[@]}" ] \
  || { echo "$archy is not $ARCHY_REF plus exactly upstream/patches" >&2; exit 1; }
node_major=$(node -p 'process.versions.node.split(".")[0]')
[ "$node_major" = "$FRONTEND_NODE_MAJOR" ] \
  || echo "warning: node $node_major, release builds use $FRONTEND_NODE_MAJOR" >&2

work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
mkdir -p "$OUT_DIR" "$root/.cache"
# A failed run must not leave outputs from an earlier one behind.
rm -f "$OUT_DIR"/frontend.tar.gz* "$OUT_DIR"/frontend.sha256 "$OUT_DIR"/inputs.sha256

# 1. Upstream's asset, verified against the pin.
asset="archipelago-frontend-${ARCHY_RELEASE#v}.tar.gz"
url="${ARCHY_REPO%.git}/releases/download/${ARCHY_RELEASE}/$asset"
cache=$root/.cache/upstream-$asset
base=$cache
if ! { [ -f "$cache" ] && echo "$FRONTEND_SHA256  $cache" | sha256sum -c - >/dev/null 2>&1; }; then
  if curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors -o "$cache.part" "$url"; then
    mv "$cache.part" "$cache"
  else
    rm -f "$cache.part"
    # A previous ForgeSworn frontend release retains aiui/ and
    # archipelago-runtime/ from this exact, hash-pinned upstream release. Only
    # those directories survive the overlay below; the dashboard is rebuilt.
    base=$root/.cache/frontend-fallback-${FRONTEND_FALLBACK_SHA256}.tar.gz
    if ! { [ -f "$base" ] && echo "$FRONTEND_FALLBACK_SHA256  $base" | sha256sum -c - >/dev/null 2>&1; }; then
      curl -fsSL --retry 5 --retry-delay 5 --retry-all-errors \
        -o "$base.part" "$FRONTEND_FALLBACK_URL"
      mv "$base.part" "$base"
    fi
  fi
fi
if [ "$base" = "$cache" ]; then
  echo "$FRONTEND_SHA256  $base" | sha256sum -c -
else
  echo "$FRONTEND_FALLBACK_SHA256  $base" | sha256sum -c -
fi
mkdir "$work/tree"; tar -xzf "$base" -C "$work/tree"

# 2. Build neode-ui as upstream's scripts/create-release.sh does (npm run build
# into web/dist/neode-ui); the same staleness check on the embedded version.
rm -rf "$archy/web/dist/neode-ui"
(cd "$archy/neode-ui" && npm ci --no-audit --no-fund && npm run build)
dist=$archy/web/dist/neode-ui
test -f "$dist/index.html"
grep -rqo "${ARCHY_RELEASE#v}" "$dist"/assets/*.js \
  || { echo "$dist does not embed ${ARCHY_RELEASE#v}: build no-opped or is stale" >&2; exit 1; }
for kept in aiui archipelago-runtime; do
  ! [ -e "$dist/$kept" ] || { echo "neode-ui build now produces $kept/; the overlay needs rethinking" >&2; exit 1; }
  test -d "$work/tree/$kept" || { echo "upstream asset has no $kept/" >&2; exit 1; }
done

# 3. Overlay: everything at the top level except aiui/ and archipelago-runtime/
# is neode-ui's build output, so drop upstream's copy (an orphan such as a
# differently hashed workbox-*.js must not survive) and copy the fresh build in.
# Note: all files end up 644, so a future runtime payload file that needs an
# execute bit would lose it here; revisit the repack modes if one ever does.
for entry in "$work"/tree/* "$work"/tree/.[!.]*; do
  [ -e "$entry" ] || continue
  case $(basename "$entry") in aiui|archipelago-runtime) ;; *) rm -rf "$entry" ;; esac
done
for entry in "$dist"/* "$dist"/.[!.]*; do
  [ -e "$entry" ] || continue
  cp -R "$entry" "$work/tree/"
done

# 4. Deterministic repack: sorted names, root:root, fixed mtime, 755/644, no
# gzip timestamp, "./" prefixes and a "./" root entry as upstream's tar writes.
epoch=$(git -C "$archy" show -s --format=%ct "$ARCHY_REF")
repack() {
python3 - "$work/tree" "$1" "$epoch" <<'PY'
import gzip, os, sys, tarfile
tree, out, epoch = sys.argv[1], sys.argv[2], int(sys.argv[3])
names = ["."]
for d, dirs, files in os.walk(tree):
    dirs.sort()
    for n in dirs + files:
        names.append("./" + os.path.relpath(os.path.join(d, n), tree))
names.sort()
def norm(ti):
    ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"; ti.mtime = epoch
    ti.mode = 0o755 if ti.isdir() else 0o644
    return ti
with open(out, "wb") as raw, gzip.GzipFile("", "wb", 9, raw, mtime=0) as gz, \
     tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tf:
    for n in names:
        p = tree if n == "." else os.path.join(tree, n[2:])
        if os.path.islink(p):
            sys.exit("symlink in payload: " + n)
        tf.add(p, arcname=n + "/" if os.path.isdir(p) and n != "." else n, recursive=False, filter=norm)
PY
}
# Repack twice from the same tree: gzip and tar framing must not vary between runs.
repack "$OUT_DIR/frontend.tar.gz.part"
repack "$work/second.tar.gz"
cmp "$OUT_DIR/frontend.tar.gz.part" "$work/second.tar.gz" \
  || { echo "repack is not deterministic: two packs of one tree differ" >&2; exit 1; }
mv "$OUT_DIR/frontend.tar.gz.part" "$OUT_DIR/frontend.tar.gz"
(cd "$OUT_DIR" && sha256sum frontend.tar.gz | awk '{print $1"  frontend.tar.gz"}' > frontend.sha256)
"$root/scripts/frontend-inputs.sh" > "$OUT_DIR/inputs.sha256"
# inputs.sha256 pins the recipe's inputs, not the Node minor, npm, Python/zlib or runner image.
echo "built $OUT_DIR/frontend.tar.gz ($(wc -c < "$OUT_DIR/frontend.tar.gz") bytes)"; cat "$OUT_DIR/frontend.sha256"
