# Upgrade an existing ForgeSworn-patched node to Archy 2.1.0-beta.2

This is the operator procedure for an **existing ForgeSworn-patched Archy node**
moving to the reviewed `2.1.0-beta.2` **patch-level-4** backend, frontend and
runtime. It preserves the installed applications, identities, wallet state,
files, room history, images, mounts and host configuration.

The qualified reference upgrade was from `1.9.1-alpha-dev` with Fedimint,
Wildbloom, Wildbloom Node, File Browser, Spry and KithMoot Node. Other existing
application sets require an explicit inventory and the corresponding `--app`
arguments. This is not a generic upstream-Archy OTA, a fresh installer or a
signed App Store installation procedure. Custom binaries and unrelated Archy
versions need their own reviewed migration first.

Do not use `scripts/update-node-bundle.py` for this beta upgrade; that updater
is for the older 1.9.1 bundle. Do not run `node/install-lite.sh` on an existing
node: it is a fresh-host installer and regenerates host identity and firewall
configuration.

## What to expect

- The coherent backup briefly stops the manager and root NPM writer and pauses
  running application containers. The reference capture took 44 seconds.
- Promotion stops and starts the manager twice while checking every installed
  application fingerprint. It does not stop or recreate application containers.
  The reference promotion took 105 seconds.
- Choose a maintenance window accordingly. Existing clients may reconnect and
  continue writing between the backup and promotion; never overlay the backup
  onto those newer live databases.
- File Browser has auto-removal and anonymous volumes. **Never stop or recreate
  it as a backup prerequisite.** The snapshot procedure pauses it and preserves
  both its container and volumes.

New Spry, Wildbloom, Wildbloom Node and KithMoot Node App Store installs remain
subject to the authenticated-catalogue gate. This existing-node procedure does
not bypass catalogue or image signatures and does not publish private images.

## 1. Prepare the exact inputs

Run these commands as the operator on your own Linux or macOS computer. Use an
SSH administrator with root access on the node. Replace `root@192.0.2.10`.

```sh
export NODE=root@192.0.2.10
export ARCHY_RELEASE=v2.1.0-beta.2
export PATCH_LEVEL=4
export ARCHY_APPS_REF=backend-${ARCHY_RELEASE}-p${PATCH_LEVEL}
export RAW=https://raw.githubusercontent.com/forgesworn/archipelago-apps/${ARCHY_APPS_REF}
export RELEASE=https://github.com/forgesworn/archipelago-apps/releases/download
umask 077
mkdir -m 700 archy-beta2-p4
cd archy-beta2-p4
```

Check the node architecture and select the matching native backend:

```sh
case "$(ssh "$NODE" uname -m)" in
  x86_64) BACKEND_ASSET=archipelago ;;
  aarch64|arm64) BACKEND_ASSET=archipelago-arm64 ;;
  *) echo 'Unsupported node architecture' >&2; exit 1 ;;
esac
export BACKEND_ASSET
```

Download the release and the three reviewed operator scripts. The release tag
selects the exact script revision; do not substitute scripts from an unpinned
branch checkout.

```sh
curl -fSLO "$RAW/scripts/coherent-node-snapshot.py"
curl -fSLO "$RAW/scripts/migrate-node.py"
curl -fSLO "$RAW/scripts/migration-startup-guard.py"
curl -fSLO "$RELEASE/backend-${ARCHY_RELEASE}-p${PATCH_LEVEL}/${BACKEND_ASSET}"
curl -fSLO "$RELEASE/backend-${ARCHY_RELEASE}-p${PATCH_LEVEL}/${BACKEND_ASSET}.sha256"
curl -fSLO "$RELEASE/backend-${ARCHY_RELEASE}-p${PATCH_LEVEL}/inputs.sha256"
mv inputs.sha256 backend-inputs.sha256
curl -fSLO "$RELEASE/frontend-${ARCHY_RELEASE}-p${PATCH_LEVEL}/frontend.tar.gz"
curl -fSLO "$RELEASE/frontend-${ARCHY_RELEASE}-p${PATCH_LEVEL}/frontend.sha256"
curl -fSLO "$RELEASE/frontend-${ARCHY_RELEASE}-p${PATCH_LEVEL}/inputs.sha256"
mv inputs.sha256 frontend-inputs.sha256
sha256sum -c "${BACKEND_ASSET}.sha256"
sha256sum -c frontend.sha256
```

On macOS, use `shasum -a 256 -c` in place of `sha256sum -c`. Record the hashes
and input receipts with your deployment evidence. A checksum file verifies the
downloaded bytes against the published release; it is not a substitute for the
separate catalogue/image signing contract.

## 2. Inventory and stop on unexpected state

Confirm that the manager and nginx are healthy and note the current backend:

```sh
ssh "$NODE" 'set -e
systemctl is-active archipelago.service nginx.service
sha256sum /usr/local/bin/archipelago
curl -fsS --cacert /etc/archipelago/ssl/ca.crt \
  -H "Content-Type: application/json" \
  --data-binary "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"health\",\"params\":{}}" \
  https://127.0.0.1/rpc/v1
echo
df -h /
free -h'
```

List every container, but distinguish installed applications from old build or
scratch containers:

```sh
ssh "$NODE" 'cd / && runuser -u archipelago -- env \
  HOME=/home/archipelago XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  podman ps -a --no-trunc --format "{{.Names}} {{.ID}} {{.Image}} {{.State}}"'
```

Write down the exact application IDs, image IDs, mounts and start times. The
promotion command requires the sorted application IDs; it does not infer them.
The reference set is:

```text
fedimint-clientd
filebrowser
kithmoot-node
spry
wildbloom
wildbloom-node
```

Do not blindly include every container shown by `podman ps -a`, and do not drop
externally managed Wildbloom containers merely because they have no manager
recipe. Stop if the state differs materially from your reviewed baseline.

Check for an earlier migration:

```sh
ssh "$NODE" 'test ! -e /etc/archipelago/node-migration.json || \
  /opt/archipelago/scripts/migrate-node.py status'
```

If a state file exists, do not delete it or start a different operation. Review
its phase and resume only the identical reviewed command. If beta startup was
attempted, recovery is forward-only; do not roll back to alpha or restore stale
application data.

Ensure enough free space for the uncompressed coherent archive, release files
and migration records. The reference archive was 5.16 GB and 9.8 GB was free
before promotion.

## 3. Take and verify a fresh coherent recovery set

Copy and install the snapshot helper, then choose a new archive path:

```sh
scp coherent-node-snapshot.py "$NODE:/root/"
ssh "$NODE" 'install -m 700 /root/coherent-node-snapshot.py \
  /opt/archipelago/scripts/coherent-node-snapshot.py'
SNAPSHOT=/root/archy-coherent-$(date -u +%Y%m%dT%H%M%SZ).tar
ssh "$NODE" "/opt/archipelago/scripts/coherent-node-snapshot.py \
  --output '$SNAPSHOT' --pause-budget 120"
```

The helper takes the lifecycle locks, records service/timer choices, pauses
running containers without stopping them, synchronizes the filesystem and writes
a stream-hashed tar through a recovery-enabled transient systemd unit. On
failure or interruption it removes the incomplete archive and restores the
recorded services and timers. If recovery reports errors, stop and use the
recorded recovery command; do not promote.

Copy the manifest and capture log locally and verify the reported state:

```sh
scp "$NODE:$SNAPSHOT.json" snapshot-manifest.json
scp "$NODE:$SNAPSHOT.capture.log" snapshot-capture.log
python3 - <<'PY'
import json
m = json.load(open('snapshot-manifest.json'))
assert m['recoveryComplete'] and not m['recoveryErrors']
print(m['sha256'], m['bytes'], m['pauseSeconds'])
PY
ssh "$NODE" 'systemctl is-active archipelago.service nginx.service'
```

Socket-ignored messages are expected for ephemeral application/container
sockets. Any changed-file warning, missing required root, recovery error or
application loss is a stop condition.

Encrypt the archive directly to a new off-host file using **your own** age
recovery recipient. Never put the age identity on the server or in Git:

```sh
export RECOVERY_RECIPIENT=age1replace-with-your-own-recipient
ssh "$NODE" "cat '$SNAPSHOT'" | age -r "$RECOVERY_RECIPIENT" \
  -o archy-coherent.tar.age
age -d -i /secure/your-age-identity.txt archy-coherent.tar.age \
  | sha256sum
```

Compare the streamed digest with `snapshot-manifest.json`. Then restore the
archive into a **separate, network-isolated Linux host or VM** before promotion:

```sh
ssh root@isolated-restore 'install -d -m 700 /var/restore-root'
age -d -i /secure/your-age-identity.txt archy-coherent.tar.age \
  | ssh root@isolated-restore \
    'tar --xattrs --acls --numeric-owner --sparse \
       --delay-directory-restore -xpf - -C /var/restore-root'
```

Keep the isolated host's external network disabled before importing identities,
wallets or images. Verify the restored backend hash and compare every archived
entry's type, regular-file hash, numeric owner, mode, timestamp, link and xattr.
Check for unexpected paths. Run read-only application checks against copies of
SQLite databases (opening a database can change its `-shm` sidecar):

- Podman and application databases pass `PRAGMA integrity_check`.
- All installed container definitions, images, mounts and anonymous volumes are present.
- Fedimint's RocksDB files, KithMoot room IDs/history, Wildbloom blobs/sales and
  File Browser settings are present and match the captured state.
- The old backend at `usr/local/bin/archipelago` has the expected baseline hash.

Do not start a restored wallet or node identity with external network access.
Do not promote until the authenticated off-host readback and isolated restore
both pass. Preserve the earlier recovery copies as well.

## 4. Promote the reviewed pair and runtime

Install the staged inputs and migration scripts on the node:

```sh
ssh "$NODE" 'test ! -e /root/archy-beta2-p4 && \
  install -d -m 700 /root/archy-beta2-p4'
scp "$BACKEND_ASSET" frontend.tar.gz migrate-node.py migration-startup-guard.py \
  "$NODE:/root/archy-beta2-p4/"
ssh "$NODE" 'install -m 755 /root/archy-beta2-p4/migrate-node.py \
  /root/archy-beta2-p4/migration-startup-guard.py /opt/archipelago/scripts/'
```

Set the expected hashes from the verified downloads and record the installed
old backend hash:

```sh
BACKEND_SHA256=$(awk '{print $1}' "${BACKEND_ASSET}.sha256")
FRONTEND_SHA256=$(awk '{print $1}' frontend.sha256)
OLD_BACKEND_SHA256=$(ssh "$NODE" \
  'sha256sum /usr/local/bin/archipelago' | awk '{print $1}')
printf '%s\n' "$BACKEND_SHA256" "$FRONTEND_SHA256" "$OLD_BACKEND_SHA256"
```

The following is the reference command. **Edit the sorted `--app` list to match
your actual installed application set.** Do not add build containers or omit an
installed app.

```sh
ssh "$NODE" "/opt/archipelago/scripts/migrate-node.py promote \
  --backend '/root/archy-beta2-p4/$BACKEND_ASSET' \
  --frontend /root/archy-beta2-p4/frontend.tar.gz \
  --backend-sha256 '$BACKEND_SHA256' \
  --old-backend-sha256 '$OLD_BACKEND_SHA256' \
  --frontend-sha256 '$FRONTEND_SHA256' \
  --version 2.1.0-beta.2-dev --health-timeout 600 \
  --app fedimint-clientd --app filebrowser --app kithmoot-node \
  --app spry --app wildbloom --app wildbloom-node"
```

The transaction preserves observed Quadlets, environment, command, labels,
mounts, network/port settings, image/container IDs, recipe hashes and anonymous
volumes. It checks all of them after both beta starts and installs a persistent
guard against starting a mixed backend/frontend pair.

If interrupted **before** candidate startup, its recovery restores the old code
pair without starting alpha reconciliation. After beta startup has been
attempted, do not use alpha rollback or an old filesystem/database snapshot:
resume forward with the identical `promote` command. Keep
`/etc/archipelago/node-migration.json`, `/opt/archipelago/.node-migration/` and
`/var/lib/archipelago/node-migration/` until delivery is accepted.

## 5. Verify the running node and existing clients

Check exact deployed hashes, health, service state and original containers:

```sh
ssh "$NODE" 'set -e
sha256sum /usr/local/bin/archipelago
systemctl is-active archipelago.service nginx.service
systemctl is-active archipelago-npm-bridge.timer
systemctl is-active archipelago-npm-bridge.service || true
curl -fsS --cacert /etc/archipelago/ssl/ca.crt \
  -H "Content-Type: application/json" \
  --data-binary "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"health\",\"params\":{}}" \
  https://127.0.0.1/rpc/v1
echo
cd / && runuser -u archipelago -- env \
  HOME=/home/archipelago XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  podman ps --no-trunc --format "{{.Names}} {{.ID}} {{.Image}} {{.State}}"'
```

Expect health `status=ok`, `crash_recovery_complete=true` and version
`2.1.0-beta.2-dev`. The NPM service is a timer-driven oneshot, so `inactive`
after a successful run is normal; `failed` is not. With patch level 4, the
KithMoot host-ingress status accepts only the reviewed beta dashboard additions;
other configuration drift still refuses maintenance.

Compare every original application ID, image ID/name, mount and start time with
the inventory. Confirm all three health-checked apps are healthy where
applicable. Verify actual files, identities, login, pairing, room IDs/history,
message delivery, Wildbloom blobs/receipts/sales, File Browser settings and
Fedimint state without recreating data or initiating a test payment.

Finally, exercise the existing desktop, Android and web clients against the same
rooms and identities. Check embedded app launch, linked signers and fresh
signing authorisation, TURN UDP/TCP/trusted TLS, public certificate names and
private dashboard/signer restrictions. Keep physical-device and maintainer UI
acceptance separate from automated health checks; a green migration is not
physical-client or UI approval.
