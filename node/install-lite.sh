#!/usr/bin/env bash
# Hand-assemble a "lite" Archipelago node on Debian 13 for app acceptance:
# pinned release frontend + patched backend, nginx, avahi, rootless Podman,
# no Bitcoin stack. See node/README.md.
#
# Usage (on the node, as root): ./install-lite.sh <bundle-dir>
# <bundle-dir> holds: PINS, archipelago, archipelago.sha256, frontend.tar.gz,
#   archy/ (sparse checkout at ARCHY_REF), first-boot-secrets.sh
#
# Inbound traffic is limited to 22/tcp. The dashboard (443) and app ports are
# reached through an SSH SOCKS tunnel, so connections originate on the node.
set -euo pipefail
bundle=${1:?usage: install-lite.sh <bundle-dir>}
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
. "$bundle/PINS"
archy=$bundle/archy
run_user() { runuser -u archipelago -- env XDG_RUNTIME_DIR=/run/user/1000 "$@"; }

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends podman netavark aardvark-dns passt uidmap \
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
echo "archipelago ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/archipelago
chmod 0440 /etc/sudoers.d/archipelago
visudo -cf /etc/sudoers.d/archipelago

# Linger starts user@1000 asynchronously; wait for its runtime dir.
loginctl enable-linger archipelago
for _ in $(seq 1 30); do [ -d /run/user/1000 ] && break; sleep 1; done
test -d /run/user/1000

mkdir -p /var/lib/archipelago/{data,config,containers/tmp,containers/storage} /etc/archipelago/ssl \
  /opt/archipelago/{bin,scripts,web-ui} /var/log/archipelago /etc/containers /var/lib/containers
# Never run archy's first-boot container script here: it creates the Bitcoin stack.
touch /var/lib/archipelago/.first-boot-containers-done

# Backend (patched, verified).
(cd "$bundle" && sha256sum -c archipelago.sha256)
install -m 0755 "$bundle/archipelago" /usr/local/bin/archipelago

# Frontend: unpack, then flatten a single top-level directory if present.
tmp=$(mktemp -d); tar -xzf "$bundle/frontend.tar.gz" -C "$tmp"
src=$tmp
if [ "$(ls -1 "$tmp" | wc -l)" = 1 ] && [ -d "$tmp/$(ls -1 "$tmp")" ]; then src="$tmp/$(ls -1 "$tmp")"; fi
rsync -a --delete "$src/" /opt/archipelago/web-ui/
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
openssl x509 -in /etc/archipelago/ssl/archipelago.crt -noout -ext subjectAltName | grep -qF "IP Address:$public_ip" \
  || { echo "leaf certificate does not cover $public_ip" >&2; exit 1; }
test -s /etc/archipelago/ssl/ca.crt

chown -R archipelago:archipelago /var/lib/archipelago /opt/archipelago /var/log/archipelago

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
systemctl start archipelago
systemctl is-active archipelago nginx avahi-daemon

# Self-check: the dashboard answers on the public IP from the node itself,
# which is the path a SOCKS-tunnelled browser takes.
code=$(curl -sk -m 10 -o /dev/null -w '%{http_code}' "https://$public_ip/")
echo "https://$public_ip/ -> HTTP $code"
[ "$code" != 000 ] || { echo "dashboard not answering on $public_ip:443" >&2; exit 1; }
echo "lite Archipelago installed at ${ARCHY_RELEASE} (patch level ${BACKEND_PATCH_LEVEL})"
