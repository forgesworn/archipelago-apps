#!/bin/sh
set -eu
# PUBLIC_HOST is an operator setting, but must never become executable JS.
origin=${WILDBLOOM_HOME_NODE_URL:-}
if [ -n "$origin" ]; then
  printf '%s\n' "$origin" | grep -Eq '^https://([A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\]):3742/?$' \
    || { echo 'Invalid Archipelago node origin' >&2; exit 1; }
fi
printf 'window.ARCHIPELAGO_NODE_ORIGIN = "%s";\n' "$origin" > /usr/share/nginx/html/archipelago-config.js
