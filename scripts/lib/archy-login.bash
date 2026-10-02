# shellcheck shell=bash
# Dashboard login for scripts that run on a node, sourced after
# /opt/archipelago/rpc.bash. It replaces rpc.bash's rpc_login, which puts the
# password into curl's argv (visible in `ps`) and splices it into JSON
# unescaped. Here the password goes from a shell variable (printf is a builtin,
# so no process sees it as an argument) through jq's stdin into curl's stdin.
#
# Contract kept with rpc.bash: writes $RPC_SESSION_FILE (mode 0600; line 1 the
# session cookie, line 2 the csrf_token cookie) and sets RPC_SESSION and
# RPC_CSRF, so rpc_call and rpc_result work afterwards.

# archy_login_body: print the auth.login request body for $ARCHY_PASSWORD.
archy_login_body() {
  printf '%s' "$ARCHY_PASSWORD" \
    | jq -Rsc '{jsonrpc:"2.0",method:"auth.login",params:{password:.},id:1}'
}

archy_login() {
  local headers body err
  [ -n "${ARCHY_PASSWORD:-}" ] || { echo "archy_login: ARCHY_PASSWORD not set" >&2; return 1; }
  headers=$(mktemp)
  body=$(archy_login_body | curl -sk -D "$headers" -X POST "${ARCHY_BASE_URL}/rpc/v1" \
    -H 'Content-Type: application/json' --data-binary @-) || { rm -f "$headers"; return 1; }
  err=$(jq -r '.error // empty' <<<"$body")
  if [ -n "$err" ] && [ "$err" != null ]; then
    echo "archy_login failed: $err" >&2; rm -f "$headers"; return 1
  fi
  RPC_SESSION=$(grep -i '^set-cookie: session=' "$headers" | head -1 | sed -E 's/.*session=([^;]+).*/\1/' | tr -d '\r' || true)
  RPC_CSRF=$(grep -i '^set-cookie: csrf_token=' "$headers" | head -1 | sed -E 's/.*csrf_token=([^;]+).*/\1/' | tr -d '\r' || true)
  rm -f "$headers"
  if [ -z "$RPC_SESSION" ] || [ -z "$RPC_CSRF" ]; then
    echo "archy_login: missing session or csrf cookie in response" >&2; return 1
  fi
  (umask 077; printf '%s\n%s\n' "$RPC_SESSION" "$RPC_CSRF" > "$RPC_SESSION_FILE")
}
