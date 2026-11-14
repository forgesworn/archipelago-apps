#!/usr/bin/env bash
# Build the dashboard frontend from the patched archy tree and repack it as
# upstream's release layout, replacing the dashboard and patched runtime helpers.
#
# Usage: scripts/build-frontend.sh [archy-dir]
#   archy-dir  a full checkout already at ARCHY_REF with upstream/patches applied
#              (default .cache/archy-frontend; never the backend's .cache/archy)
# Env:   OUT_DIR (default .cache/frontend-out) receives frontend.tar.gz,
#        frontend.sha256 and inputs.sha256.
#
# Upstream's tarball (FRONTEND_SHA256) is flat: ./index.html, ./assets/..., plus
# runtime payload (apps, scripts, docker, radio tools). Beta's AIUI is compiled
# into the dashboard. Stage runtime helpers from the patched backend source.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
. "$root/PINS"
archy=${1:-$root/.cache/archy-frontend}
OUT_DIR=${OUT_DIR:-$root/.cache/frontend-out}
case $(cd "$archy" && pwd) in "$root/.cache/archy") echo "refusing to build in .cache/archy" >&2; exit 1;; esac
patches=("$root"/upstream/patches/*.patch)
[ "$(git -C "$archy" rev-list --count "$ARCHY_REF..HEAD")" = "${#patches[@]}" ] \
  || { echo "$archy is not $ARCHY_REF plus exactly upstream/patches" >&2; exit 1; }
[ -z "$(git -C "$archy" status --porcelain --untracked-files=all)" ] \
  || { echo "frontend source must be clean for native AIUI provenance" >&2; exit 1; }
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
    [ -n "$FRONTEND_FALLBACK_URL" ] && [ -n "$FRONTEND_FALLBACK_SHA256" ] \
      || { echo "upstream asset unavailable and no fallback pinned for $ARCHY_RELEASE" >&2; exit 1; }
    # An explicitly qualified fallback must retain the exact hash-pinned
    # upstream built runtime assets. Only archipelago-runtime survives the
    # overlay below; the dashboard and native AIUI are rebuilt.
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

# 2. Build from clean source and verify beta's native AIUI chunk receipt.
# Community metadata is a packaging overlay. Never dirty the source tree or
# imply that unsigned metadata authorises a new app installation in beta.
cp "$archy/app-catalog/catalog.json" "$work/catalog.json"
python3 "$root/scripts/include-bundle-app.py" \
  --catalogue "$work/catalog.json" --manifest "$root/apps/spry/manifest.yml"
catalogue_revision=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$work/catalog.json")
rm -rf "$archy/web/dist/neode-ui"
(cd "$archy/neode-ui" && npm ci --no-audit --no-fund && VITE_CATALOGUE_REVISION="$catalogue_revision" npm run build)
dist=$archy/web/dist/neode-ui
test -f "$dist/index.html"
# npm's prebuild copies the source catalogue into public/. Check the shipped
# file too, so that a later upstream hook cannot silently remove the listing.
cmp "$archy/app-catalog/catalog.json" "$dist/catalog.json"
python3 "$archy/scripts/release_payload.py" ui "$dist" --commit "$(git -C "$archy" rev-parse HEAD)"
cp "$work/catalog.json" "$dist/catalog.json"
for kept in archipelago-runtime; do
  ! [ -e "$dist/$kept" ] || { echo "neode-ui build now produces $kept/; the overlay needs rethinking" >&2; exit 1; }
  test -d "$work/tree/$kept" || { echo "upstream asset has no $kept/" >&2; exit 1; }
done

# 3. Overlay: everything at the top level except archipelago-runtime/
# is neode-ui's build output, so drop upstream's copy (an orphan such as a
# differently hashed workbox-*.js must not survive) and copy the fresh build in.
# Upstream's archive contract requires 755 directories and 644 regular files.
for entry in "$work"/tree/* "$work"/tree/.[!.]*; do
  [ -e "$entry" ] || continue
  case $(basename "$entry") in archipelago-runtime) ;; *) rm -rf "$entry" ;; esac
done
for entry in "$dist"/* "$dist"/.[!.]*; do
  [ -e "$entry" ] || continue
  cp -R "$entry" "$work/tree/"
done

# Include Spry's runtime definition. The verified catalogue still controls
# whether the beta App Store permits a new installation.
mkdir -p "$work/tree/archipelago-runtime/apps/spry"
cp "$root/apps/spry/manifest.yml" "$work/tree/archipelago-runtime/apps/spry/manifest.yml"

# Beta runtime and backend helpers are one compatibility unit. Retaining the
# upstream copies here would omit our ingress/lifecycle fixes. Regenerate the
# upstream byte declaration and label this derivative separately.
patch_digest=$(cat "${patches[@]}" | sha256sum | awk '{print $1}')
python3 "$root/scripts/stage-runtime-payload.py" "$archy" "$work/tree" \
  --version "${ARCHY_RELEASE#v}" --commit "$(git -C "$archy" rev-parse HEAD)" \
  --patches-sha256 "$patch_digest"

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
python3 "$archy/scripts/release_payload.py" archive "$OUT_DIR/frontend.tar.gz" \
  --version "${ARCHY_RELEASE#v}" --commit "$(git -C "$archy" rev-parse HEAD)"
(cd "$OUT_DIR" && sha256sum frontend.tar.gz | awk '{print $1"  frontend.tar.gz"}' > frontend.sha256)
"$root/scripts/frontend-inputs.sh" > "$OUT_DIR/inputs.sha256"
# inputs.sha256 pins the recipe's inputs, not the Node minor, npm, Python/zlib or runner image.
echo "built $OUT_DIR/frontend.tar.gz ($(wc -c < "$OUT_DIR/frontend.tar.gz") bytes)"; cat "$OUT_DIR/frontend.sha256"
