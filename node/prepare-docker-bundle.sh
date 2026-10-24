#!/usr/bin/env bash
# Assemble reviewed release assets for a fresh Debian 13 amd64 Docker host.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
output=${1:?usage: prepare-docker-bundle.sh <new-output-directory>}
. "$root/PINS"
mkdir "$output"
output=$(cd "$output" && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
gh release download "backend-${ARCHY_RELEASE}-p${BACKEND_PATCH_LEVEL}" \
  --repo forgesworn/archipelago-apps --pattern archipelago --pattern archipelago.sha256 \
  --pattern inputs.sha256 --dir "$output"
[ "$(cat "$output/inputs.sha256")" = "$("$root/scripts/backend-inputs.sh")" ] \
  || { echo 'Backend release does not match this checkout' >&2; exit 1; }
(cd "$output" && sha256sum -c archipelago.sha256)
gh release download "frontend-${ARCHY_RELEASE}-p${FRONTEND_PATCH_LEVEL}" \
  --repo forgesworn/archipelago-apps --pattern frontend.tar.gz --pattern frontend.sha256 \
  --pattern inputs.sha256 --dir "$work"
[ "$(cat "$work/inputs.sha256")" = "$("$root/scripts/frontend-inputs.sh")" ] \
  || { echo 'Frontend release does not match this checkout' >&2; exit 1; }
(cd "$work" && sha256sum -c frontend.sha256)
cp "$work/frontend.tar.gz" "$work/frontend.sha256" "$output/"
gh release download v0.4.1 --repo jmcorgan/fips --pattern fips_0.4.1_amd64.deb --dir "$work"
cp "$work/fips_0.4.1_amd64.deb" "$output/fips.deb"
echo '9befcc0990c7e08742b5a88f75d753a1088134b20525156688d559a317334ded  fips.deb' \
  | (cd "$output" && sha256sum -c -)
cp "$root/PINS" "$root/node/install-lite.sh" "$root/scripts/recover-wildbloom-payment.py" "$output/"
"$root/scripts/fetch-archy.sh" "$output/archy"
sed -n "/<<'SECRETSSCRIPT'/,/^SECRETSSCRIPT\$/p" "$output/archy/image-recipe/_archived/build-auto-installer-iso.sh" \
  | sed '1d;$d' > "$output/first-boot-secrets.sh"
test -s "$output/first-boot-secrets.sh"
echo 'Bundle prepared. On the fresh Debian host: sudo bash install-lite.sh . docker'
