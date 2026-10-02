# Wave 1 acceptance: Wildbloom on a lite Archipelago node

Acceptance for `wildbloom-node` and `wildbloom` on a lite Archipelago node (see
`node/README.md`). The scripted half runs `scripts/acceptance.sh`, which makes
every check on the node over SSH, through the dashboard's JSON-RPC and the
node's identity signer. The browser half uses the real dashboard and its consent
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

What this shows, as five checks (`scripts/acceptance.sh` labels them 1, 2, 3,
4/5 and 6 in its comments; this document numbers them 1 to 5):

1. Both apps are installed and running.
2. The owner key injected into `wildbloom-node` (`WILDBLOOM_ALLOW_PUBKEYS`) is
   the key `node.nostr-pubkey` reports. (Run 1 only: that is the discovery key,
   which apps never sign with. See Findings.)
3. The Wildbloom UI refuses a request with no dashboard session (401). The
   Blossom port answers through the app gate over TLS, and refuses an unsigned
   upload for want of authorisation (401), not for a malformed request.
4. An upload authorisation (kind 24242) signed by `node.nostr-sign` (run 1;
   the script now uses `identity.nostr-sign`), with the
   node's injected mDNS name as its `server` tag, is accepted, and fetching the
   blob by its SHA-256 returns the same bytes.
5. Wildbloom's page loads the node's signer script, and the provider file was
   copied into the container from the host by the `post_install` hook.

### Browser half

Run on 2 October 2026, after the fixes listed under Findings, against:

- Lite Archipelago `v1.8.22-alpha` on Debian 13, backend release
  `backend-v1.8.22-alpha-p3` (our `NODE_IDENTITY_PUBKEYS` patch).
- `ghcr.io/forgesworn/wildbloom-node:0.2.2-b3b254b-2` and
  `ghcr.io/forgesworn/wildbloom:0.0.1-29d382e-4`.
- The injected `WILDBLOOM_ALLOW_PUBKEYS` equalled the node's single signable
  identity, "Personal" (`<identity npub>`).

The browser was Chromium, reaching the node through an SSH SOCKS tunnel.

1. Wildbloom loaded inside the dashboard's app session iframe.
2. "Connect NIP-07 signer" opened Archipelago's identity picker. It offered
   only the user identity; the node identity is hidden, as the patch assumes.
3. The provider also requested a NIP-98 login (kind 27235) into the app on its
   own. It was denied. Wildbloom does not use it.
4. Uploading a small plaintext file raised Archipelago's consent prompt:
   "Upload blob `<sha>` to `<node address>`", kind 24242, identity Personal.
   After approval `PUT /upload` returned 201, and `GET /<sha>` returned
   identical bytes.

Two workarounds were needed only because of the upstream issue described in
`docs/upstream-notes.md` under
[Gated sideloaded apps get an `http://` frame on an HTTPS dashboard](upstream-notes.md#gated-sideloaded-apps-get-an-http-frame-on-an-https-dashboard-archy-6d5f3ff):

- The dashboard was opened over plain HTTP, so the app frame was not blocked
  as mixed content.
- Chromium was started with `--unsafely-treat-insecure-origin-as-secure` for
  the dashboard and app origins, because WebCrypto needs a secure context.

Earlier in the same run, three faults were found and fixed (see Findings):

- Wildbloom's nginx listened on IPv4 only, while the health check goes to
  `localhost`, which resolves to `::1`. Fixed in the image.
- The `copy_from_host` provider was lost when the health monitor recreated the
  container. Fixed by baking the provider into the image.
- The owner was originally the node discovery key, which apps cannot sign with.
  Fixed by the `NODE_IDENTITY_PUBKEYS` patch.

### Reboot

After a full node reboot, both apps came back healthy.

### Browser half after reboot

- Blobs uploaded before the reboot returned identical bytes.
- The provider was served.
- `scripts/acceptance.sh` passed again, printing "ACCEPTANCE (scripted) PASSED",
  against backend `backend-v1.8.22-alpha-p3`,
  `ghcr.io/forgesworn/wildbloom-node:0.2.2-b3b254b-2` and
  `ghcr.io/forgesworn/wildbloom:0.0.1-29d382e-4`.

### Findings

- `wildbloom` was unhealthy in Podman for this run. Its in-container health
  check requests `localhost`, which resolves to `::1`, and the image's nginx
  listened on IPv4 only. The page itself was served, so all five checks passed.
  The image now listens on both families (`wildbloom:0.0.1-29d382e-4`), and
  the post-reboot acceptance run passed against it.
- The dashboard state's `health` field was unset for both apps throughout this
  run, so it did not surface the fault above. Acceptance now records it but
  cannot rely on it.
- Sideloaded manifests sit inside the frontend payload and would not survive
  an OTA frontend update. See `docs/upstream-notes.md`.
- Checks 2 and 4 proved the wrong owner. The run-1 backend injected the
  node's discovery key (`{{NODE_NOSTR_PUBKEY}}`), but the NIP-07 bridge signs
  app uploads with an identity the user picks, and the picker never offers the
  node identity. On the test node "Personal" is `<identity npub>`, "Node" is
  `<node identity npub>` and the discovery key is `<node npub>`, so no upload
  from Wildbloom's page could be accepted. The owner is now every identity the picker offers,
  through `{{NODE_IDENTITY_PUBKEYS}}` (backend patch level 3,
  `backend-v1.8.22-alpha-p3`, which supersedes the pre-review p2; image `wildbloom-node:0.2.2-b3b254b-2`). Check 2
  now compares the injected list with `identity.list` filtered as the picker
  filters it, and check 4 signs with `identity.nostr-sign` as the first such
  identity. The browser half and the post-reboot `scripts/acceptance.sh` run
  passed against that backend and image ("ACCEPTANCE (scripted) PASSED").
