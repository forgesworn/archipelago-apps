#!/usr/bin/env bash
# Link a Nostr identity on the node to a NIP-46 remote signer (Heartwood,
# Signet Lite, Amber, nak, ...). The node keeps no key for it: apps sign
# through the dashboard as usual, and the node forwards each request to the
# signer.
#
# Usage: read -rs ARCHY_PASSWORD; export ARCHY_PASSWORD
#   scripts/link-signer.sh --name NAME [--purpose personal|business|anonymous]
#       Paste the signer's bunker://… link when asked (or pipe it on stdin).
#   scripts/link-signer.sh --nostrconnect --relay wss://… [--relay …] --name NAME [--purpose …]
#       Prints a nostrconnect://… link (and a QR code if qrencode is installed)
#       for the signer to scan or paste, then waits up to 5 minutes for it.
# Env: NODE (default root@95.216.164.146), ARCHY_PASSWORD (dashboard password).
#
# The password and the bunker link can both carry secrets, so they travel on
# stdin only: never in argv here, over ssh, or on the node (see
# lib/archy-login.bash).
set -euo pipefail
: "${NODE:=root@95.216.164.146}" "${ARCHY_PASSWORD:?dashboard password}"
root=$(cd "$(dirname "$0")/.." && pwd)

mode=bunker name="" purpose=personal relays=()
while [ $# -gt 0 ]; do
  case $1 in
    --name) name=$2; shift 2 ;;
    --purpose) purpose=$2; shift 2 ;;
    --nostrconnect) mode=nostrconnect; shift ;;
    --relay) relays+=("$2"); shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[ -n "$name" ] || { echo "--name is required" >&2; exit 2; }
case $purpose in personal|business|anonymous) ;; *) echo "bad --purpose: $purpose" >&2; exit 2 ;; esac
if [ "$mode" = nostrconnect ] && [ ${#relays[@]} -eq 0 ]; then
  echo "--nostrconnect needs at least one --relay the signer's device can reach" >&2; exit 2
fi

uri=""
if [ "$mode" = bunker ]; then
  if [ -t 0 ]; then read -rs -p "bunker:// link: " uri; echo >&2; else IFS= read -r uri || true; fi
  case $uri in bunker://*) ;; *) echo "expected a bunker:// link" >&2; exit 2 ;; esac
fi

read -r -d '' remote <<'EOF' || true
set -euo pipefail
IFS= read -r ARCHY_PASSWORD
mode=$1 name=$2 purpose=$3; shift 3
source /opt/archipelago/rpc.bash
hdr=$(umask 077; mktemp)
trap 'rpc_logout_local; rm -f "$hdr"' EXIT
archy_login
unset ARCHY_PASSWORD
# rpc.bash's rpc_call puts the payload and session in curl's argv; here the
# params come in on stdin and the session headers from a 0600 file.
printf 'Cookie: session=%s; csrf_token=%s\nX-CSRF-Token: %s\n' "$RPC_SESSION" "$RPC_CSRF" "$RPC_CSRF" > "$hdr"
rpc_stdin() {
  jq -c --arg m "$1" '{jsonrpc:"2.0",method:$m,params:.,id:1}' \
    | curl -sk -X POST "${ARCHY_BASE_URL}/rpc/v1" -H 'Content-Type: application/json' \
        -H @"$hdr" --data-binary @-
}
result_or_die() {
  local err
  err=$(jq -r '.error.message // .error // empty' <<<"$1")
  if [ -n "$err" ]; then echo "FAIL: $err" >&2; exit 1; fi
  jq -c '.result' <<<"$1"
}
report() {
  jq -r '"linked: \(.name) \(.nostr_npub // .nostr_pubkey) origin=\(.origin)"' <<<"$1"
}

if [ "$mode" = bunker ]; then
  IFS= read -r uri
  echo "asking the signer to connect and prove its key (approve it there if it asks)…" >&2
  res=$(printf '%s' "$uri" \
    | jq -Rc --arg n "$name" --arg p "$purpose" '{bunker_uri:., name:$n, purpose:$p}' \
    | rpc_stdin identity.link-nip46)
  unset uri
  # Assign first: an exit inside $(...) would not stop the script.
  res=$(result_or_die "$res")
  report "$res"
  exit 0
fi

start=$(jq -nc --arg n "$name" --arg p "$purpose" '{name:$n, purpose:$p, relays:$ARGS.positional}' --args "$@" \
  | rpc_stdin identity.link-nostrconnect-start)
start=$(result_or_die "$start")
pairing=$(jq -r '.pairing_id' <<<"$start")
echo "URI: $(jq -r '.uri' <<<"$start")"
deadline=$(( $(date +%s) + 300 ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  res=$(jq -nc --arg id "$pairing" '{pairing_id:$id}' | rpc_stdin identity.link-nostrconnect-finish)
  res=$(result_or_die "$res")
  case $(jq -r '.status' <<<"$res") in
    linked) res=$(jq -c '.identity' <<<"$res"); report "$res"; exit 0 ;;
    pending) ;;
    *) echo "FAIL: unexpected reply: $res" >&2; exit 1 ;;
  esac
done
echo "FAIL: no signer connected within 5 minutes" >&2
exit 1
EOF

remote="$(cat "$root/scripts/lib/archy-login.bash")"$'\n'"$remote"
argv=$(printf '%q ' "$mode" "$name" "$purpose" ${relays[@]+"${relays[@]}"})
# The %q quoting assumes the node's root login shell is bash. Expanding on
# the client side is intended: $remote and $argv are already %q-quoted.
# shellcheck disable=SC2029
printf '%s\n%s\n' "$ARCHY_PASSWORD" "$uri" \
  | ssh "$NODE" "bash -c $(printf '%q' "$remote") remote $argv" \
  | while IFS= read -r line; do
      case $line in
        "URI: "*)
          link=${line#URI: }
          echo "Scan or paste this into the signer:"
          echo "$link"
          if command -v qrencode >/dev/null; then qrencode -t ANSIUTF8 "$link"; fi
          echo "waiting for the signer (up to 5 minutes)…" ;;
        *) echo "$line" ;;
      esac
    done
