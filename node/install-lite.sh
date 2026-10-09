#!/usr/bin/env bash
# Hand-assemble a "lite" Archipelago node on Debian 13 for app acceptance:
# pinned release frontend + patched backend, nginx, avahi, rootless Podman,
# no Bitcoin stack. See node/README.md.
#
# Usage (on the node, as root): ./install-lite.sh <bundle-dir>
# <bundle-dir> holds: PINS, archipelago, archipelago.sha256, frontend.tar.gz
#   (checked against frontend.sha256 from our frontend release when present,
#   else against PINS FRONTEND_SHA256, i.e. upstream's own asset),
#   archy/ (sparse checkout at ARCHY_REF), first-boot-secrets.sh
#
# Inbound traffic is limited to 22/tcp. The dashboard (443) and app ports are
# reached through an SSH SOCKS tunnel, so connections originate on the node.
set -euo pipefail
bundle=${1:?usage: install-lite.sh <bundle-dir>}
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
. "$bundle/PINS"
test -f "$bundle/recover-wildbloom-payment.py" || { echo "bundle is missing the payment recovery tool" >&2; exit 1; }
archy=$bundle/archy
# From /, because the service user cannot enter root's cwd and podman exits on
# that; with the user's own bus, not one inherited from root's login session.
run_user() {
  (cd / && runuser -u archipelago -- env XDG_RUNTIME_DIR=/run/user/1000 \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "$@")
}

export DEBIAN_FRONTEND=noninteractive
# A fresh cloud image runs apt-daily in the background; wait for its lock.
apt-get -o DPkg::Lock::Timeout=600 update
apt-get -o DPkg::Lock::Timeout=600 install -y --no-install-recommends podman netavark aardvark-dns passt uidmap \
  slirp4netns fuse-overlayfs dbus-user-session nginx avahi-daemon openssl curl jq \
  python3 python3-yaml ufw ca-certificates rsync sudo iproute2

# Service user: archipelago.service hard-codes /run/user/1000.
if ! id archipelago >/dev/null 2>&1; then
  if getent passwd 1000 >/dev/null; then echo "uid 1000 is taken" >&2; exit 1; fi
  useradd -m -u 1000 -s /bin/bash -G sudo,dialout archipelago
fi
# The unit's SupplementaryGroups= names these; systemd refuses to start without them.
for g in debian-tor fips; do getent group "$g" >/dev/null || groupadd --system "$g"; done
grep -q '^archipelago:' /etc/subuid || echo "archipelago:100000:65536" >> /etc/subuid
grep -q '^archipelago:' /etc/subgid || echo "archipelago:100000:65536" >> /etc/subgid
# As the ISO does: the daemon uses sudo for volume ownership, hostname sync and
# certificate reissue, some of it non-interactively (sudo -n).
sudoers_tmp=$(mktemp)
echo "archipelago ALL=(ALL) NOPASSWD:ALL" > "$sudoers_tmp"
visudo -cf "$sudoers_tmp"
install -m 0440 -o root -g root "$sudoers_tmp" /etc/sudoers.d/archipelago
rm -f "$sudoers_tmp"

# Linger starts user@1000 asynchronously; wait for its user bus, which
# `systemctl --user` and rootless Podman need.
loginctl enable-linger archipelago
for _ in $(seq 1 30); do [ -S /run/user/1000/bus ] && break; sleep 1; done
systemctl is-active --quiet user@1000.service
test -S /run/user/1000/bus

# Directories the service user owns. Created and chowned individually, never
# recursively: on a re-run /var/lib/archipelago holds image layers and app
# volumes owned by subuid-mapped ids, which a recursive chown would corrupt.
install -d -o archipelago -g archipelago /var/lib/archipelago \
  /var/lib/archipelago/data /var/lib/archipelago/config /var/lib/archipelago/containers \
  /var/lib/archipelago/containers/tmp /var/lib/archipelago/containers/storage
mkdir -p /etc/archipelago/ssl /opt/archipelago/bin /opt/archipelago/scripts /opt/archipelago/web-ui \
  /var/log/archipelago /etc/containers /var/lib/containers

# Database passwords the ISO's first boot (first-boot-containers.sh) creates
# up front so they stay stable. Manifests that name one in secret_env fail
# every reconcile pass while it is missing, installed or not (btcpay-server,
# archy-btcpay-db and archy-nbxplorer, each pass). Never overwrite one.
install -d -o archipelago -g archipelago -m 700 /var/lib/archipelago/secrets
for svc in mempool btcpay mysql-root; do
  f=/var/lib/archipelago/secrets/${svc}-db-password
  [ -f "$f" ] || (umask 077 && openssl rand -hex 16 > "$f")
  chown archipelago:archipelago "$f"
  chmod 600 "$f"
done

# Backend (patched, verified).
(cd "$bundle" && sha256sum -c archipelago.sha256)
install -m 0755 "$bundle/archipelago" /usr/local/bin/archipelago
install -m 0755 "$bundle/recover-wildbloom-payment.py" /usr/local/bin/recover-wildbloom-payment

# Frontend, verified, then unpacked (a single top-level directory is flattened).
# Our frontend release ships frontend.sha256; without it the bundle must be
# upstream's own asset, pinned by PINS FRONTEND_SHA256.
# Hash the exact file we are about to unpack; never trust a filename inside the sha file.
if [ -f "$bundle/frontend.sha256" ]; then
  want=$(awk 'NF==2 && $2=="frontend.tar.gz" {print $1}' "$bundle/frontend.sha256")
  [ "$(wc -l < "$bundle/frontend.sha256")" -le 1 ] && [[ "$want" =~ ^[0-9a-f]{64}$ ]] \
    || { echo "frontend.sha256 must be one line naming frontend.tar.gz" >&2; exit 1; }
else
  want=${FRONTEND_SHA256:?PINS has no FRONTEND_SHA256}
fi
have=$(sha256sum "$bundle/frontend.tar.gz" | awk '{print $1}')
[ "$have" = "$want" ] || { echo "frontend.tar.gz is $have, expected $want" >&2; exit 1; }
tmp=$(mktemp -d); tar -xzf "$bundle/frontend.tar.gz" -C "$tmp"
src=$tmp
if [ "$(ls -1 "$tmp" | wc -l)" = 1 ] && [ -d "$tmp/$(ls -1 "$tmp")" ]; then src="$tmp/$(ls -1 "$tmp")"; fi
# --checksum: our frontend tarballs are repacked with one fixed mtime, so rsync's
# size+mtime quick check would keep an old index.html of the same size while
# --delete removes the assets it points to (a blank dashboard).
rsync -a --checksum --delete "$src/" /opt/archipelago/web-ui/
rm -rf "$tmp"
test -f /opt/archipelago/web-ui/index.html
test -f /opt/archipelago/web-ui/nostr-provider.js
mkdir -p /opt/archipelago/web-ui/archipelago-runtime/apps

# Per-device TLS (and SSH host keys) via archy's own first-boot script.
# It regenerates /etc/ssh/ssh_host_*: re-accept the host key afterwards.
install -m 0755 "$bundle/first-boot-secrets.sh" /opt/archipelago/scripts/first-boot-secrets.sh
/opt/archipelago/scripts/first-boot-secrets.sh
test -s /etc/archipelago/ssl/archipelago.crt
# The first-boot leaf names only the hostname and localhost. Archipelago's per-node CA
# reissues the leaf with every global IP as a SAN, which the app gate serves on every
# app port; without it a fetch to https://<ip>:3742 fails on hostname mismatch.
install -m 0755 "$archy/scripts/setup-node-ca.sh" /opt/archipelago/scripts/setup-node-ca.sh
/opt/archipelago/scripts/setup-node-ca.sh
public_ip=$(ip -4 -o addr show scope global | awk '{print $4}' | cut -d/ -f1 | head -1)
openssl x509 -in /etc/archipelago/ssl/archipelago.crt -noout -ext subjectAltName | grep -qE "IP Address:${public_ip//./\\.}(,|$)" \
  || { echo "leaf certificate does not cover $public_ip" >&2; exit 1; }
test -s /etc/archipelago/ssl/ca.crt

# Recursive is safe here: nothing under /opt/archipelago or /var/log/archipelago
# is mounted into containers (manifests reference /opt only as build contexts).
chown -R archipelago:archipelago /opt/archipelago /var/log/archipelago

# Rootless Podman config, as the ISO lays it out: graphroot on the data volume,
# netavark for container DNS on archy-net. Every path in the unit's
# ReadWritePaths= must exist or ProtectSystem=strict fails the service.
install -d -o archipelago -g archipelago /home/archipelago/.config \
  /home/archipelago/.config/containers /home/archipelago/.local \
  /home/archipelago/.local/share /home/archipelago/.local/share/containers
ln -sfn /var/lib/archipelago/containers/storage /home/archipelago/.local/share/containers/storage
cat > /home/archipelago/.config/containers/storage.conf <<'EOF'
[storage]
driver = "overlay"
graphroot = "/var/lib/archipelago/containers/storage"
runroot = "/run/user/1000/containers"
EOF
cat > /home/archipelago/.config/containers/containers.conf <<'EOF'
[network]
network_backend = "netavark"
default_rootless_network_cmd = "pasta"
[engine]
image_copy_tmp_dir = "/var/lib/archipelago/containers/tmp"
EOF
chown -h archipelago:archipelago /home/archipelago/.local/share/containers/storage \
  /home/archipelago/.config/containers/storage.conf /home/archipelago/.config/containers/containers.conf
run_user podman system migrate
run_user sh -c 'podman network exists archy-net || podman network create archy-net'
run_user systemctl --user enable --now podman.socket

# nginx + systemd unit, verbatim from archy at the pinned ref.
install -m 0644 "$archy/image-recipe/configs/nginx-archipelago.conf" /etc/nginx/sites-available/archipelago
mkdir -p /etc/nginx/snippets && install -m 0644 "$archy"/image-recipe/configs/snippets/*.conf /etc/nginx/snippets/
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/archipelago /etc/nginx/sites-enabled/archipelago
nginx -t
install -m 0644 "$archy/image-recipe/configs/archipelago.service" /etc/systemd/system/archipelago.service
install -m 0644 "$archy/tests/lifecycle/lib/rpc.bash" /opt/archipelago/rpc.bash

# Firewall: SSH only. Dashboard and app ports are reached through an SSH tunnel.
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw --force enable

systemctl daemon-reload
# apt already started nginx on the default site; restart to load ours.
systemctl enable avahi-daemon nginx archipelago
systemctl restart avahi-daemon nginx
# restart, not start: a re-run with a new binary must take effect.
systemctl restart archipelago
systemctl is-active archipelago nginx avahi-daemon

# Self-check, on the public IP from the node itself, which is the path a
# SOCKS-tunnelled browser takes. First nginx answers at all (curl reports 000
# and fails when nothing does; || true keeps that readable).
code=$(curl -sk -m 10 -o /dev/null -w '%{http_code}' "https://$public_ip/") || true
echo "https://$public_ip/ -> HTTP $code"
[ "$code" != 000 ] || { echo "dashboard not answering on $public_ip:443" >&2; exit 1; }
# Then the backend behind it. JSON-RPC `health` needs no session (it is in
# UNAUTHENTICATED_METHODS, core/archipelago/src/api/rpc/middleware.rs; handler
# handle_health in core/archipelago/src/api/rpc/dispatcher.rs) and returns
# {status,crash_recovery_complete,uptime_seconds,version}. The RPC listener
# opens a while after systemd reports the unit active, so poll.
status=""
for _ in $(seq 60); do
  status=$(curl -sk -m 5 -X POST "https://$public_ip/rpc/v1" -H 'Content-Type: application/json' \
    --data-raw '{"jsonrpc":"2.0","method":"health","id":1}' | jq -r '.result.status // empty' 2>/dev/null) || true
  [ -n "$status" ] && break
  sleep 2
done
echo "https://$public_ip/rpc/v1 health -> ${status:-no answer}"
[ -n "$status" ] || { echo "backend not answering JSON-RPC behind nginx on $public_ip:443" >&2; exit 1; }
echo "lite Archipelago installed at ${ARCHY_RELEASE} (patch level ${BACKEND_PATCH_LEVEL})"
