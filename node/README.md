# Lite Archipelago test node

`install-lite.sh` hand-assembles a "lite" Archipelago node on a stock Debian 13
(trixie) x86_64 server. It exists to run acceptance on the apps in this repository
(`wildbloom-node` on 3742, `wildbloom` on 3743) against the real backend, nginx and
rootless Podman layout, without the cost of a full install.

## What it contains

- The patched backend from this repository's `backend-<ARCHY_RELEASE>-p<BACKEND_PATCH_LEVEL>`
  release, checked against its `.sha256`, at `/usr/local/bin/archipelago`.
- The frontend at `/opt/archipelago/web-ui`: this repository's
  `frontend-<ARCHY_RELEASE>-p<FRONTEND_PATCH_LEVEL>` release, checked against its
  `frontend.sha256` (with no patches that touch `neode-ui` it is byte-identical in content
  to upstream's own release asset, which `FRONTEND_SHA256` in `PINS` pins).
- From archy at `ARCHY_REF`, installed unmodified: `archipelago.service`,
  `nginx-archipelago.conf` and its snippets, `setup-node-ca.sh`, the first-boot
  secrets script (extracted from the archived ISO builder) and
  `tests/lifecycle/lib/rpc.bash` (installed as `/opt/archipelago/rpc.bash`).
  The backend then manages some of these itself: on every start
  (`bootstrap::ensure_runtime_assets_ready`) it promotes the frontend's
  `archipelago-runtime/` payload into `/opt/archipelago/{apps,scripts,docker}`,
  reinstalls the nginx site from it and installs the `archipelago-doctor` and
  `archipelago-host-secrets-audit` units (`core/archipelago/src/bootstrap.rs`).
  What runs is therefore the release's copy of those files, not the installer's.
- The `archipelago` user (uid 1000, lingering), subuid/subgid ranges, passwordless
  sudo and the rootless Podman configuration the ISO writes (graphroot under
  `/var/lib/archipelago/containers/storage`, netavark, pasta), plus the `archy-net`
  network and the user's `podman.socket`.
- Per-device TLS and SSH host keys from archy's first-boot script, then the
  per-node CA, which reissues the leaf with every global address as a SAN so one
  certificate covers 443 and every app port.
- nginx, avahi and ufw (inbound `22/tcp` only).

## What it leaves out

- The Bitcoin stack. The installer never runs archy's first-boot container
  script, which is what creates it on an ISO install. The frontend payload still
  carries a manifest for every catalogue app, but the boot reconcile only
  recreates apps that already exist, apart from a fixed baseline allow-list
  (`is_required_baseline_app`, `core/archipelago/src/container/prod_orchestrator.rs:75`).
  So `filebrowser` and `fedimint-clientd` **will** appear, as on every real node;
  Bitcoin, LND, ElectrumX, BTCPay and mempool will not.
- Tor, the kiosk, OTA updates, WireGuard, FIPS, the nostr relay and the LUKS data
  volume. `/var/lib/archipelago` sits on the root filesystem. The unit's crash-guard
  `ExecStartPre` is `-`-prefixed, so it is tolerated if absent.
- No Rust toolchain or builds on the node: everything arrives in the bundle.

## Building the node

1. Rebuild the server as Debian 13 (Hetzner Cloud Console → server → Rebuild).
   Then forget the old host key and check the OS:

   ```bash
   ssh-keygen -R <node-ip>
   ssh -o StrictHostKeyChecking=accept-new root@<node-ip> '. /etc/os-release; echo $VERSION_CODENAME; uname -m'
   ```

   Expect `trixie` and `x86_64`.

2. Assemble the bundle on your machine and copy it over (the archy checkout's
   `.git` is not needed on the node):

   ```bash
   S=<scratch-dir>/bundle
   . ./PINS
   rm -rf "$S" && mkdir -p "$S"
   cp PINS node/install-lite.sh scripts/recover-wildbloom-payment.py "$S/"
   gh release download "backend-${ARCHY_RELEASE}-p${BACKEND_PATCH_LEVEL}" -D "$S"
   # The patched frontend (frontend.tar.gz, frontend.sha256, inputs.sha256):
   gh release download "frontend-${ARCHY_RELEASE}-p${FRONTEND_PATCH_LEVEL}" -D "$S"
   # Or upstream's own asset instead (no frontend.sha256; PINS FRONTEND_SHA256 checks it):
   #   curl -fL -o "$S/frontend.tar.gz" \
   #     "https://source.archipelago-foundation.org/lfg2025/archy/releases/download/${ARCHY_RELEASE}/archipelago-frontend-${ARCHY_RELEASE#v}.tar.gz"
   scripts/fetch-archy.sh "$S/archy"
   sed -n "/<<'SECRETSSCRIPT'/,/^SECRETSSCRIPT\$/p" "$S/archy/image-recipe/_archived/build-auto-installer-iso.sh" \
     | sed '1d;$d' > "$S/first-boot-secrets.sh"
   ssh root@<node-ip> 'rm -rf /root/bundle'
   rsync -a --exclude .git "$S/" root@<node-ip>:/root/bundle/
   ```

3. Run the installer, then re-accept the host key (the first-boot script
   regenerates it):

   ```bash
   ssh root@<node-ip> 'bash /root/bundle/install-lite.sh /root/bundle'
   ssh-keygen -R <node-ip>
   ssh -o StrictHostKeyChecking=accept-new root@<node-ip> 'systemctl is-active archipelago nginx avahi-daemon'
   ```

   Expect three `active`. The installer finishes by requesting
   `https://<node-ip>/` from the node itself, then the backend's unauthenticated
   JSON-RPC `health` method through nginx, and fails if either does not answer.
   It is safe to re-run, for example with a new backend or frontend release: it
   restarts the service, regenerates the SSH host keys, and keeps the existing
   TLS CA (a re-run reissues the leaf certificate under the same CA, so its
   fingerprint changes). Re-verify and accept the new SSH host-key fingerprint
   before reconnecting. The installer never recursively chowns
   `/var/lib/archipelago`, where image layers and app volumes belong to
   subuid-mapped ids.

4. Confirm the running backend is the patched one:

   ```bash
   ssh root@<node-ip> 'sha256sum /usr/local/bin/archipelago; cat /root/bundle/archipelago.sha256'
   ```

5. Onboard in the browser through the tunnel (below): set the dashboard password,
   back up the seed and create the first identity. Skip any Bitcoin setup. Keep
   the password in a password manager; acceptance scripts read it as
   `ARCHY_PASSWORD`.

6. Check that no Bitcoin stack appeared after a reconcile:

   ```bash
   sleep 120
   ssh root@<node-ip> "cd / && runuser -u archipelago -- env XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus podman ps -a --format '{{.Names}}'"
   ```

   None of `bitcoin-*`, `lnd`, `electrumx`, `mempool*`, `btcpay*` or `fedimint*`
   should be listed, except `fedimint-clientd`, which is a baseline app alongside
   `filebrowser`.

## Reaching the node

Only SSH is open. Open a SOCKS proxy and send a separate browser profile through
it; the node then sees the requests as coming from itself, and ufw's loopback rule
lets them reach 443, 3742 and 3743 on its public address.

```bash
ssh -N -D 1080 root@<node-ip>
```

On macOS, launch Chrome with a throwaway profile that uses the tunnel and does no
local DNS:

```bash
open -na "Google Chrome" --args --user-data-dir=/tmp/archy-chrome --proxy-server="socks5://127.0.0.1:1080" --host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"
```

Then browse to `https://<node-ip>/`.

To check the arrangement:

```bash
ssh root@<node-ip> "curl -sk -o /dev/null -w '%{http_code}\n' https://<node-ip>/"   # answers
curl -m 5 -sk https://<node-ip>/                                                 # times out
```

### Trusting the node CA

Wildbloom fetches `https://<node-ip>:3742` cross-origin, which needs the leaf to
be trusted rather than clicked through. Download the CA from the dashboard
(Settings → Node certificate) or `http://<node-ip>/ca.crt` through the tunnel,
check its SHA-256 fingerprint against
`ssh root@<node-ip> 'openssl x509 -in /etc/archipelago/ssl/ca.crt -noout -fingerprint -sha256'`,
and import it in the tunnelled profile at `chrome://certificate-manager` (Local
certificates → Custom → Installed by you), trusted for websites. That keeps the
trust inside `/tmp/archy-chrome` rather than the system keychain. A rebuilt node
has a new CA, so remove the old one first.
