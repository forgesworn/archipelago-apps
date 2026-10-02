#!/bin/sh
# nginx refuses to start if it cannot bind an IPv6 listener. Drop ours when the
# container has no IPv6 address at all (no module, or disable_ipv6=1). In such a
# container Archipelago's localhost health probe only passes if the client falls
# back to 127.0.0.1.
set -eu
if ! [ -s /proc/net/if_inet6 ]; then
  sed -i '/listen \[::\]:3743;/d' /etc/nginx/conf.d/wildbloom.conf
  echo "15-wildbloom-ipv6.sh: no IPv6 in this container, serving IPv4 only"
fi
