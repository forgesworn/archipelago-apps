# Wildbloom app refresh — October 2026

The two packages share Archipelago's existing identities. Updating them does
not require a new identity or a new remote-signer pairing.

## What changes

- Wildbloom Node moves from 0.2.2 to 0.3.5. The image contains the newer storage,
  replica and coded-pool support, optional operator checkout and authenticated
  full-read storage audits.
- The browser package includes encrypted replicas and coded pools, local recovery
  from saved receipts, trusted signed node recommendations, optional operator
  checkout and storage audits, with clearer setup/publish/recover navigation.
- The browser uses the Archipelago NIP-07 provider already supplied by this
  package. No extension is required inside the dashboard.

These are the headless daemon and web app, not the desktop tray application's
pool-management controls. Importing a pool receipt does not automatically enable
unattended repair on an Archipelago node. Configure the separate owner repair
service deliberately; do not give ordinary storage nodes the recovery key.

## Existing installations

1. Save your private signed file events/pool receipts and recovery keys separately.
   Back up the node's existing data while its writer is stopped. The storage bind
   path remains `/var/lib/archipelago/wildbloom-node`, mounted at `/data`.
2. Update the storage app and then the browser app using the manifests and exact
   image tags from the same repository revision. Do not remove the storage volume
   or run the old and new writers against it at the same time.
3. Open the browser app from the dashboard. Connect its existing node identity,
   check the automatically selected HTTPS Blossom URL and recover a known file. The node CA
   must already be trusted by this browser.
4. Verify a new upload from an allowed identity and refusal of a stranger's write.
   Keep the offline backup until both old-file retrieval and new writes pass.
   Roll back with the old image and its matching offline backup, not by assuming
   an older daemon can read a migrated database.

The published packages do not update already-running installations automatically.
`scripts/stage-to-node.sh` is available to operators who already use this repo's
sideloading workflow; it restarts the Archipelago backend and requires its dashboard
credentials. A later frontend OTA may replace sideloaded manifests; preserve the
chosen manifests and re-check their image tags after such an update.

## Optional services

Audits are off by default. To opt in, change the storage app's environment entry to
`WILDBLOOM_STORAGE_PROOFS=true` and recreate the container through Archipelago.
The endpoint authenticates requests, bounds concurrency and rate, and reads the
whole stored ciphertext. Audits use bandwidth and establish current retrievability,
not continuous custody, a dedicated copy or future availability.

Paid storage remains off. Selling requires the operator's own receiving service,
private checkout profile and persistent checkout state, with coordinated offline
backups of checkout and storage. Do not paste receiving credentials into a public
manifest. See the upstream [checkout documentation](https://github.com/forgesworn/wildbloom-node/blob/main/docs/CHECKOUT.md)
before enabling it. Installing the app does not configure a merchant service.
The [Archipelago Moneyer setup](wildbloom-selling.md) prepares a private profile
and manifest with an aggregate sales ceiling and an owner reserve.

## Upgrade evidence

The [container acceptance run](https://github.com/forgesworn/archipelago-apps/actions/runs/37787137521)
passed on Linux: upload a synthetic file with 0.2.2, stop that container, start
0.3.5 with the same volume, recover identical bytes, independently verify a fresh
full-read proof, reject an unsigned proof and a stranger's upload, then accept and
retrieve a new owner upload. No payment or real user data was involved.

This is container upgrade evidence. It does not establish a completed update of
an existing physical Archipelago installation or independent multi-device recovery.

## Existing test-node upgrade (8 October)

Both new packages were also installed on the existing Archipelago 1.9.0-alpha
test node. Before changing the storage image, its writer was stopped and a
private offline copy of its volume and original manifests was retained.
After upgrading, all 16 pre-existing blobs (114,786 bytes) were downloaded and
compared byte-for-byte against that backup. SQLite integrity passed; the owner
allowlist and public URL matched their previous values. Both containers became
healthy. The external web UI still required authentication (HTTP 401 without a
session) and the storage health endpoint returned HTTP 200.

The refreshed browser opened at `/#client` inside the dashboard and selected
the existing Heartwood identity without re-pairing. The provider's optional
NIP-98 bootstrap exposed a packaging bug: SPA fallback returned 200 for its
non-existent health endpoint. Packaging revision 2 returns 404 for `/api/`
routes, so that unsupported login flow cannot start. The provider itself is
unchanged.

The dashboard's quick Start control did not recreate the stopped storage
container, and its sideload form rejected the already-installed app ID. The
operator completed the upgrade using the existing rootless systemd container
units after staging the same new manifests. A missing Podman temporary directory
was recreated with ownership limited to the Archipelago user; no recursive
ownership changes were made. Existing volumes, identities and authorisation
rules were preserved.

New signed writes and proof checks passed in container acceptance. The additional
live-browser fixture upload was not completed because browser automation did not
receive the file chooser. Do not count that attempt as a live write/recovery pass.
This upgrade is separate from soak testing and independent node-loss acceptance.


## Browser usability refresh

Browser image `0.0.1-045e35a-1` includes the refreshed overview, corrected hover contrast,
responsive text layouts and larger consent controls. Saved-file recovery now
explicitly accepts both signed file events and pool receipts. The visible client
has its own level-one heading and clearer field spacing.

This is a browser-only update. The Wildbloom Node image, storage volume, existing
identities and signer provider remain unchanged. The unsupported `/api/` routes
still return 404, preserving the fix for the unwanted authentication prompt.

The upstream production-browser checks include expanded service panels and
18 viewport widths with enlarged text and WCAG text spacing. Spoken screen-reader
and physical mobile acceptance remain separate from these automated checks.

## Marketing film refresh

Browser image `0.0.1-a7f79cb-1` adds the illustrated 32-second recovery film and
its full text alternative. Playback is requested explicitly and stays on the
node's own web origin. The client still opens directly from the dashboard;
visitors can reach the film through the Wildbloom home link.

The package smoke check verifies the new player, same-origin media policy,
MP4 MIME type and partial-content response used for seeking. This is a
browser-only refresh. The storage daemon, identities and signer provider keep
their existing versions. The real app and Archipelago walkthrough is separate
work; the illustrated film is not a live storage demonstration.

## Private quote retry fix

Browser image `0.0.1-1d2a7c3-2` creates a fresh checkout request after each
successful private quote. Repeating the quote flow therefore creates a new order
instead of reopening an expired order from an earlier attempt. The same request
identifier is still retained while an outcome is unknown, so retrying a timed-out
request remains idempotent.

The upstream acceptance deliberately aborts one quote request at the network
boundary and verifies that consecutive explicit quote attempts use different
request identifiers. This is a browser-only update; the Wildbloom Node image,
checkout database, stored blobs, identities and signer provider remain unchanged.
