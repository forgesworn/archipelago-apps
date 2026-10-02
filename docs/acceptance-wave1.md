# Wave 1 acceptance: Wildbloom on a lite Archipelago node

Acceptance for `wildbloom-node` and `wildbloom` on a lite Archipelago node (see
`node/README.md`). The scripted half runs `scripts/acceptance.sh`, which makes
every check on the node over SSH, through the dashboard's JSON-RPC and the
node's own signer. The browser half uses the real dashboard and its consent
prompt.

## Run 1: 2 October 2026

### Pins

- Archipelago `v1.8.22-alpha`, archy `6d5f3ffb850bfd3dcd396bac986ba770935d1daa`,
  with `upstream/patches` applied (backend patch level 1, release
  `backend-v1.8.22-alpha-p1`).
- `ghcr.io/forgesworn/wildbloom-node:0.2.2-b3b254b` (wildbloom-node `b3b254b`).
- `ghcr.io/forgesworn/wildbloom:0.0.1-29d382e` (wildbloom `29d382e`).
- Node identity: `<node npub>` (a throwaway test node).

### Staging

Both apps were staged with `scripts/stage-to-node.sh`, `wildbloom-node` first
because `wildbloom` depends on it. Each install went through the orchestrator
from the staged manifest, pulled its image from ghcr.io and reached `running`.

```
package.install wildbloom-node (ghcr.io/forgesworn/wildbloom-node:0.2.2-b3b254b):
{
  "package_id": "wildbloom-node",
  "status": "installing"
}
wildbloom-node: state=running health=none

package.install wildbloom (ghcr.io/forgesworn/wildbloom:0.0.1-29d382e):
{
  "package_id": "wildbloom",
  "status": "installing"
}
wildbloom: state=running health=none
```

`health=none` is the dashboard state's `health` field, which was unset for both
apps throughout this run. It hid a real fault: Podman reported `wildbloom`
unhealthy (see Findings). Check 3 below probes Blossom's health endpoint
directly.

### Scripted half

```
wildbloom-node: state=running health=none
wildbloom: state=running health=none
node=<node hex> env=<node hex> (<node npub>)
unauthenticated UI :3743 -> 401
Blossom :3742 healthz via gate -> 200
unsigned upload :3742 -> 401
server tag: injected mDNS name matches hostname.local
signed upload accepted: 6dd4900f36d1e02b18e2740c49a48fccda1c589afa399fb83d7e4a0b7db1db3c
fetch by sha matches the uploaded bytes
signer injection and provider present
ACCEPTANCE (scripted) PASSED: blob 6dd4900f36d1e02b18e2740c49a48fccda1c589afa399fb83d7e4a0b7db1db3c
```

What this shows:

1. Both apps are installed and running.
2. The owner key injected into `wildbloom-node` (`WILDBLOOM_ALLOW_PUBKEYS`) is
   the key `node.nostr-pubkey` reports.
3. The Wildbloom UI refuses a request with no dashboard session (401). The
   Blossom port answers through the app gate over TLS, and refuses an unsigned
   upload for want of authorisation (401), not for a malformed request.
4. An upload authorisation (kind 24242) signed by `node.nostr-sign`, with the
   node's injected mDNS name as its `server` tag, is accepted, and fetching the
   blob by its SHA-256 returns the same bytes.
5. Wildbloom's page loads the node's signer script, and the provider file was
   copied into the container from the host by the `post_install` hook.

### Browser half

Browser run: pending.

### Reboot

Reboot test: pending.

### Browser half after reboot

Browser run after reboot: pending.

### Findings

- `wildbloom` was unhealthy in Podman for this run. Its in-container health
  check requests `localhost`, which resolves to `::1`, and the image's nginx
  listened on IPv4 only. The page itself was served, so checks 1–6 passed. The
  image is being rebuilt to listen on both families; acceptance must be re-run
  against the new image.
- The dashboard state's `health` field was unset for both apps throughout this
  run, so it did not surface the fault above. Acceptance now records it but
  cannot rely on it.
- Sideloaded manifests sit inside the frontend payload and would not survive
  an OTA frontend update. See `docs/upstream-notes.md`.
