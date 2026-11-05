#!/usr/bin/env bash
# Private browser access which reconnects after VPN or Wi-Fi changes.
set -u
target=${1:-}
port=${2:-1080}
if [[ -z "$target" || "$target" == -* || ! "$port" =~ ^[0-9]+$ ]] || (( port < 1024 || port > 65535 )); then
  echo "Usage: $0 USER@NODE [LOCAL_SOCKS_PORT]" >&2
  exit 2
fi
child=
stop() {
  trap - INT TERM
  if [[ -n "$child" ]]; then kill "$child" 2>/dev/null || true; fi
  exit 0
}
trap stop INT TERM
echo "Keep this running. Browser SOCKS5: 127.0.0.1:$port, with DNS through the proxy."
while :; do
  ssh -N -D "127.0.0.1:$port" -o BatchMode=yes -o ExitOnForwardFailure=yes \
    -o ConnectTimeout=10 -o ConnectionAttempts=1 \
    -o ServerAliveInterval=5 -o ServerAliveCountMax=2 "$target" &
  child=$!
  wait "$child" || true
  child=
  echo "Private Archy connection ended; reconnecting in two seconds. Ctrl-C to stop." >&2
  sleep 2 &
  child=$!
  wait "$child" || true
  child=
done
