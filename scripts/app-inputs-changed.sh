#!/usr/bin/env bash
# Did this app's own image inputs change between two commits? Prints
# "changed=true|false" and a reason on stdout (CI appends the first to
# $GITHUB_OUTPUT). Usage: app-inputs-changed.sh <app-id> <before-sha> [event]
#
# An app's inputs are its apps/<id>/ tree, its smoke test, and its own PINS
# lines. wildbloom-node's smoke test also uses tests/smoke/package*.json and
# sign-auth.mjs. Anything we cannot compare (a manual run, the first push, an
# all-zero or unknown "before" sha) counts as changed.
set -euo pipefail
app=${1:?app id}
before=${2-}
event=${3:-push}

case "$app" in
  wildbloom-node)
    paths=(apps/wildbloom-node tests/smoke/wildbloom-node.sh
           tests/smoke/package.json tests/smoke/package-lock.json tests/smoke/sign-auth.mjs)
    pin_re='^(WILDBLOOM_NODE_REF|WILDBLOOM_NODE_PKG_REV)=' ;;
  wildbloom)
    paths=(apps/wildbloom tests/smoke/wildbloom.sh)
    pin_re='^(WILDBLOOM_REF|WILDBLOOM_PKG_REV)=' ;;
  *) echo "unknown app: $app" >&2; exit 2 ;;
esac

emit() { echo "changed=$1"; echo "reason: $2" >&2; exit 0; }

[ "$event" = push ] || emit true "event is $event, not push"
[ -n "$before" ] || emit true "no before sha"
[[ "$before" =~ ^0+$ ]] && emit true "first push (all-zero before sha)"
git cat-file -e "$before^{commit}" 2>/dev/null || emit true "before sha $before not in the clone"

if ! git diff --quiet "$before" HEAD -- "${paths[@]}"; then
  emit true "files changed under: ${paths[*]}"
fi
old=$(git show "$before:PINS" 2>/dev/null | grep -E "$pin_re" || true)
new=$(grep -E "$pin_re" PINS || true)
[ "$old" = "$new" ] || emit true "PINS lines for $app changed"
emit false "no inputs of $app changed since $before"
