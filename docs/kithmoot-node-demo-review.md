# KithMoot Node review on demo

The private Linux x64 review candidate is installed. The real linked signer,
setup, pairing hand-off, pause/start and deletion preparation/cancellation
have passed. [Deployment evidence and captures](evidence/kithmoot-node-demo-20261103/qualification.json)
identify the tested revisions. The owner confirmed web pairing and status as “Paired and ready”.

The owner authorised this private installation on 3 November 2026. It is a
review candidate, outside the published app catalogue. No Shelter source,
private image or public node release has been published.

## Access

Keep an SSH SOCKS tunnel open:

```sh
scripts/node-management-tunnel.sh root@95.216.164.146 1080
```

The [tunnel helper](../scripts/node-management-tunnel.sh) reconnects after a VPN
or Wi-Fi change. Keep it running. It binds only local loopback.

Use an Archy browser profile with SOCKS5 `127.0.0.1:1080` and DNS through the
proxy. Open <https://demo.forgesworn.dev/dashboard>, log in with the existing
dashboard account, then launch **KithMoot Node**. The app endpoint is
<https://demo.forgesworn.dev:3753/>; its outer gate requires the dashboard
session. Inside the app, choose the existing linked identity and approve
the local sign-in proof on its signer. This is separate from pairing a keeper's KithMoot app.

The public certificate covers `demo.forgesworn.dev` and
`turn.demo.forgesworn.dev`. The dashboard and operator app remain private.
External callers receive only the room node's explicit API and authenticated
TURN transports. Existing Spry ports and app data are retained.

## Devices and connections

“Your KithMoot account” replaces “keeper device” in the controls. Open the
pairing link in the browser, computer or phone you want to use; sign in to the
same KithMoot account on each device. No special hardware is required.
The [updated component review](evidence/kithmoot-node-copy-20261103/component-review.json)
contains 15 captures and six clean accessibility scans, including a failed
management fetch and retry. A lost management connection is now named as an
Archy controls connection error instead of “The node is unreachable” or the
browser’s raw “Failed to fetch”.

KithMoot room HTTPS, relay and TURN traffic use the public node routes. Private
Archy management uses its private connection. Keep those two access paths
separate when diagnosing VPN changes.

## Revision

- Operator UI/controller source: `3d447f14b13ea8fa5d6f7703a3f2cb98017cb5cd`.
- Patched host source: `f389e68b904e21dbd54343d4b71a61bac78efd11`, patches
  0035–0045, backend patch level 10.
- Native private image: `localhost/kithmoot-node:0.1.0-rc.1-ee8307c5b832`.
- Bundle inventory SHA-256:
  `65b951512c9dc1df845cbcf7183bc1685585500a934d1096a90217d629a8de47`.
- The existing dashboard frontend is retained. The real host supplies its
  session gate, identity picker and Nostr signer.

The native daemon uses release-built dependencies with the daemon crate at
opt-level 0 and 256 codegen units to fit the review host. Normal full-release
builds run separately in CI. This candidate establishes functionality, with no
capacity or performance claim. The UI/controller assets are unchanged.

## Review

Use the named-screen actions and expected results in the
[Archy review pack](kithmoot-node-archy-review.md#named-screens-and-review-steps).
In particular:

1. Launch from the authenticated dashboard. Check sign-in, denied identity,
   cancellation, expiry and retry in standalone and embedded views.
2. Confirm the away-from-home setting before setup. Check unconfigured,
   ready, paused, restarting and failed-start status, including recovery.
3. Create a pairing code. Check its QR, copy and same-device link, explicit
   keeper instructions, one-use behaviour and expiry. Use the separately
   identified KithMoot client candidate; the public clients do not yet contain
   these unapproved UI changes.
4. With no rooms, prepare deletion, cancel it and check admission is restored.
   Review Archy's normal **Delete app and data** hand-off. Do not delete any
   room that another reviewer is using.
5. Check keyboard, focus, 320/390/768/1440 widths, landscape, enlarged text,
   reduced motion and standalone/embedded appearance.

The owner clarified on 3 November that ZAT is required only when submitting
back to the official Archy repository. It does not gate ForgeSworn's KithMoot
or private node delivery. No official upstream submission or approval is claimed.
For that official submission: **Maintainer must review and approve UI work on
the Archy install, launch, pairing hand-off, delete-everything and status screens
before merging or approval. ZAT pending.** No maintainer message has been sent.

## Pair from the web

The web client was deployed from merge `2c1977dacad883d730bd7ec6cfc9c66dbfe99486`
as release `20261103T101924Z`. Open KithMoot and accept **Update now** if an older
installed web app is still running. Refreshing alone can retain the previous
service worker. Generate a fresh code in Archy, open its link, sign in to the
keeper's KithMoot account and choose **Pair node**. **Check status** should show
`demo.forgesworn.dev` ready. No native app is required. The owner completed this
journey successfully. No site data, saved room or identity was cleared.

## Completed live checks

- Normal public certificate validation and actual dashboard identity picker.
  The owner approved the linked signer authentication proof. No local identity
  or signing key was created.
- Initial setup on the rented host; ready, unpaired, zero rooms/devices/requests.
  Local pairing QR and link presence checked without recording a live secret.
- Pause/start and empty-state deletion preparation/cancellation. No room created
  by the automated review. The owner subsequently paired their own account.
- Actual dashboard embedded launcher and HTTPS app gate. The local controller
  interface declares HTTP for readiness; the browser gate remains authenticated
  HTTPS. No container restart or node data change was needed for that correction.
- Effective kernel memory limit 268435456 bytes; `/tmp` is a 16 MiB tmpfs with
  noexec/nosuid/nodev. UID 1000, read-only root, no capabilities and no-new-privileges
  confirmed. Existing five app containers retained their IDs and images.
- Public TURN TLS443 STUN binding response; external dashboard and signer
  denied, including spoofed forwarding headers. This is not a media-call test.
- Ingress install/remove/recovery on Debian 13 with Python 3.13 and the real
  certificate. Certificate regression tests: 8 passed; dashboard guard: 13
  passed; Nginx Proxy Manager bridge: 24 passed.
- Existing dashboard frontend, original app manifests and session secret
  retained. Maintenance and manager restart preserved ingress and running apps.

[Live sign-in](evidence/kithmoot-node-demo-20261103/01-sign-in.png),
[setup at 390 px](evidence/kithmoot-node-demo-20261103/02-setup-390.png),
[ready](evidence/kithmoot-node-demo-20261103/03-ready.png) and
[deletion prepared](evidence/kithmoot-node-demo-20261103/04-prepared-delete.png),
[embedded launch](evidence/kithmoot-node-demo-20261103/05-embedded.png) and
[web pairing at 390 px](evidence/kithmoot-node-demo-20261103/pairing-phone.png).

## Recovery

The host's private review directory is
`/root/kithmoot-node-review-20261103`. It retains build/deployment receipts,
the previous daemon and a private control-plane rollback archive. It contains
private material and must not be uploaded to a PR.

To roll back, close any review rooms in their keeper's app, then uninstall only
`kithmoot-node` through Archy's normal lifecycle with `preserve_data: true`.
Wait for removal and the node ingress transaction to restore its original
configuration. The node helper restores the normalised managed base profile;
the legacy custom demo TLS profile requires the saved full control-plane
rollback. Restore the saved daemon/runtime/nginx control plane, reload
systemd and nginx, and verify the dashboard and original apps. Remove only UFW
rules labelled `kithmoot-node-review-20261103`. Retain the app's data and the
expanded certificate; neither needs to be destroyed for rollback.

Public NAT/media, forced TURN-over-TLS443, capacity and physical GrapheneOS
acceptance are separate from making this review UI available.
