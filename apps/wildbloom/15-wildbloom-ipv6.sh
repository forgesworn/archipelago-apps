#!/bin/sh
# nginx refuses to start if it cannot bind an IPv6 listener. Drop ours when the
# container has no IPv6 loopback (no module, or disable_ipv6=1). In such a
# container Archipelago's localhost health probe only passes if the client falls
# back to 127.0.0.1. Test the content: procfs files always stat as size 0, so
# [ -s /proc/net/if_inet6 ] is false even when ::1 is up.
set -eu
if ! grep -qs '^00000000000000000000000000000001 ' /proc/net/if_inet6; then
  sed -i '/listen \[::\]:3743;/d' /etc/nginx/conf.d/wildbloom.conf
  echo "15-wildbloom-ipv6.sh: no IPv6 loopback in this container, serving IPv4 only"
fi
