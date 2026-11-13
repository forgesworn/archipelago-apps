#!/usr/bin/env bash
set -euo pipefail
[ "${SPRY_RELAY_HOST_TEST:-}" = 1 ] || { echo 'Set SPRY_RELAY_HOST_TEST=1 for the disposable privileged Linux fixture' >&2; exit 2; }
root=$(cd "$(dirname "$0")/.." && pwd)
name="spry-relay-host-$$"
cleanup() {
  code=$?
  if [ "$code" != 0 ]; then
    docker exec "$name" bash -c 'systemctl list-units --failed --no-pager; journalctl --no-pager -n 250' || true
    docker exec "$name" bash -c 'uid=$(id -u spry-relay); runuser -u spry-relay -- env HOME=/var/lib/spry-relay XDG_RUNTIME_DIR=/run/user/$uid DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus podman ps -a; runuser -u spry-relay -- env HOME=/var/lib/spry-relay XDG_RUNTIME_DIR=/run/user/$uid DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus podman inspect spry-relay; journalctl --user -u spry-relay.service --no-pager -n 100' || true
  fi
  docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker build -f "$root/tests/node/Dockerfile" -t "$name" "$root/tests/node"
docker run -d --name "$name" --privileged --cgroupns host \
  --mount type=bind,source=/sys/fs/cgroup,target=/sys/fs/cgroup \
  --tmpfs /run --tmpfs /tmp "$name" >/dev/null
docker cp "$root/node/spry-relay.py" "$name:/usr/local/sbin/spry-relay"
docker exec --env SPRY_RELAY_HOST_DIAG_ONLY="${SPRY_RELAY_HOST_DIAG_ONLY:-}" "$name" bash -euxo pipefail -c '
  apt-get update
  apt-get install -y --no-install-recommends ufw iproute2 podman uidmap \
    dbus-user-session libpam-systemd fuse-overlayfs runc crun attr
  ufw allow 22/tcp
  ufw --force enable
  ip addr add 8.8.8.8/32 dev lo
  printf "8.8.8.8 relay.example.org\n" >> /etc/hosts
  useradd --system --home /var/lib/spry-relay --shell /usr/sbin/nologin --user-group spry-relay
  usermod --add-subuids 100000-165535 --add-subgids 100000-165535 spry-relay
  mkdir -p /var/lib/spry-relay
  chown spry-relay:spry-relay /var/lib/spry-relay
  chmod 700 /var/lib/spry-relay
  loginctl enable-linger spry-relay
  systemctl start user@$(id -u spry-relay).service
  relay_podman() {
    runuser -u spry-relay -- env HOME=/var/lib/spry-relay \
      XDG_RUNTIME_DIR=/run/user/$(id -u spry-relay) podman "$@"
  }
  printf "\nHost file capabilities and process capabilities\n"
  getfattr -d -m security.capability /bin/sh /bin/dash || true
  grep -E "^(Cap|NoNewPrivs|Seccomp)" /proc/self/status
  for driver in overlay vfs; do
    printf "\nStorage driver: %s\n" "$driver"
    storage=(--root="/var/lib/spry-relay/diagnostic-$driver" --storage-driver="$driver")
    findmnt -T /var/lib/spry-relay
    findmnt -T "/run/user/$(id -u spry-relay)"
    relay_podman "${storage[@]}" info --format "{{json .Store}}" || true
    relay_podman "${storage[@]}" pull \
      ghcr.io/forgesworn/spry@sha256:15dd7a0aa83c2d9ed9a439af264e79062cecaf1cab5902910a914d4526e30ee8
    relay_podman "${storage[@]}" create --name "diagnostic-$driver" --runtime=crun --cgroups=disabled \
      --network=host --read-only --cap-drop=ALL --security-opt=no-new-privileges \
      ghcr.io/forgesworn/spry@sha256:15dd7a0aa83c2d9ed9a439af264e79062cecaf1cab5902910a914d4526e30ee8
    relay_podman "${storage[@]}" inspect "diagnostic-$driver" \
      --format "CapDrop={{json .HostConfig.CapDrop}} SecurityOpt={{json .HostConfig.SecurityOpt}} Readonly={{.HostConfig.ReadonlyRootfs}}"
    relay_podman "${storage[@]}" rm "diagnostic-$driver"
    for mode in baseline drop-capabilities no-new-privileges isolated; do
      flags=()
      case "$mode" in
        drop-capabilities) flags=(--cap-drop=ALL) ;;
        no-new-privileges) flags=(--security-opt=no-new-privileges) ;;
        isolated) flags=(--cap-drop=ALL --security-opt=no-new-privileges) ;;
      esac
      log="/root/spry-relay-diagnostic-$driver-$mode.log"
      printf "\nProbe: driver=%s mode=%s\n" "$driver" "$mode"
      relay_podman "${storage[@]}" run --rm --runtime=crun --cgroups=disabled --network=host --read-only "${flags[@]}" \
        --entrypoint /bin/sh \
        ghcr.io/forgesworn/spry@sha256:15dd7a0aa83c2d9ed9a439af264e79062cecaf1cab5902910a914d4526e30ee8 \
        -c "getfattr -d -m security.capability /bin/sh /bin/dash || true; grep -E ^Cap /proc/self/status; grep -E ^NoNewPrivs /proc/self/status; grep -E ^Seccomp /proc/self/status" \
        >"$log" 2>&1 || true
      cat "$log"
    done
  done
  if [ "${SPRY_RELAY_HOST_DIAG_ONLY:-}" = 1 ]; then
    exit 0
  fi
  mkdir -p /etc/letsencrypt/live/relay.example.org
  openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj /CN=relay.example.org \
    -addext subjectAltName=DNS:relay.example.org \
    -keyout /etc/letsencrypt/live/relay.example.org/privkey.pem \
    -out /etc/letsencrypt/live/relay.example.org/fullchain.pem
  chmod 700 /usr/local/sbin/spry-relay
  SPRY_RELAY_TEST_NO_CGROUP=1 /usr/local/sbin/spry-relay activate --hostname relay.example.org --ip 8.8.8.8
  SPRY_RELAY_TEST_NO_CGROUP=1 /usr/local/sbin/spry-relay status
  /usr/local/sbin/spry-relay profile --output /root/device.json --ttl 3600
  python3 - <<"PY"
import json
from pathlib import Path
profile = json.loads(Path("/root/device.json").read_text())
assert profile["urls"] == [
    "turn:relay.example.org:3478?transport=udp",
    "turn:relay.example.org:3478?transport=tcp",
    "turns:relay.example.org:5349?transport=tcp",
]
assert Path("/root/device.json").stat().st_mode & 0o777 == 0o600
print("Generated profile contract passed")

import secrets
import socket
import ssl
import struct

transaction = secrets.token_bytes(12)
request = struct.pack("!HHI12s", 1, 0, 0x2112A442, transaction)

def check_response(response):
    kind, length, magic, response_transaction = struct.unpack("!HHI12s", response[:20])
    assert kind == 0x0101
    assert length == len(response) - 20
    assert magic == 0x2112A442
    assert response_transaction == transaction

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
    client.settimeout(3)
    client.sendto(request, ("relay.example.org", 3478))
    check_response(client.recv(2048))

with socket.create_connection(("relay.example.org", 3478), timeout=3) as client:
    client.sendall(request)
    response = client.recv(2048)
    check_response(response)

context = ssl.create_default_context(cafile="/etc/letsencrypt/live/relay.example.org/fullchain.pem")
with socket.create_connection(("relay.example.org", 5349), timeout=3) as raw:
    with context.wrap_socket(raw, server_hostname="relay.example.org") as client:
        client.sendall(request)
        response = client.recv(2048)
        check_response(response)
print("Activated UDP, TCP and trusted-TLS Binding checks passed")
PY
  /usr/local/sbin/spry-relay deactivate
'
