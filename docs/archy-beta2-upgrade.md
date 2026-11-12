# Archy 2.1.0-beta.2 compatibility and node preservation

Status: preparation in progress; **not approved for a live upgrade**.
Scope: the owner confirmed only `demo.forgesworn.dev` (`95.216.164.146`).
No live services, data, firewall rules or credentials were changed by this task.

## Candidate and source baseline

- Upstream release: `v2.1.0-beta.2`, published 10 November 2026.
- Source commit: `5aac0d20571e6f673b8a5df95a5c8fcab2932c39`.
- Upstream frontend SHA-256:
  `c2ef014b5ce3c660c5c0f09a552202923d1425e63610a4976745b50bd5340195`.
- Upstream backend SHA-256:
  `3b4ad21823597ad47f16984e3456960f4ac6aa5e4fce5ad94980b081099af581`.
- These hashes came from the upstream HTTPS release manifest. Its Ed25519 signature was independently verified against the release root
  pinned in beta source, using the documented canonical JSON preimage. The
  downloaded frontend also matches its signed SHA-256.
- Our compatibility branch starts at `3b295e3e79e228ef1fdacd221feed85191932a28`,
  retaining the KithMoot node and clipboard work in PR53/PR54. Neither PR is
  treated as maintainer-approved or merged.
- This candidate branch pins beta.2 and contains 33 rebased patches. Main,
  the existing alpha branches and the live node remain unchanged. These pins
  are preparation for review, not activation authority.

Upstream has incorporated linked NIP-46 identities and dashboard login. Do not
blindly reapply the old patches or omit their interoperability checks. The beta
also replaces application code and runtime helpers together, drains maintenance
jobs and preserves timer choices. Our old binary/frontend-only updater is not
a cross-version migration tool; its source-hash refusal remains in place.

Sources: [release](https://source.archipelago-foundation.org/lfg2025/archy/releases/tag/v2.1.0-beta.2),
[manifest](https://source.archipelago-foundation.org/lfg2025/archy/releases/download/v2.1.0-beta.2/manifest.json),
[upstream changelog](https://source.archipelago-foundation.org/lfg2025/archy/src/commit/5aac0d20571e6f673b8a5df95a5c8fcab2932c39/CHANGELOG.md).

## Read-only live baseline, 12 November 2026

- Manager health: `ok`, crash recovery complete, `1.9.1-alpha-dev`.
- Installed manager SHA-256:
  `81a184a97a04b02ac65d44fe2b71e7c34f3d9c91486001b3cced60efa913230d`.
- Manager and nginx active. Root disk: approximately 21 GiB used / 15 GiB free.
- Six app containers running: fedimint-clientd, wildbloom, wildbloom-node,
  filebrowser, spry and kithmoot-node.
- KithMoot uses the newer private image
  `localhost/kithmoot-node:group-headroom-20261110-db34017b49e3`.
  Preserve that exact installed image/configuration; do not replace it with
  the older experimental image implied by our integration branch.
- The firewall has owner-configured call and ingress ports. Historical
  documentation saying only SSH is open is not the current baseline. Preserve
  the actual rules and dashboard restrictions; do not replay installer defaults.
- Existing private backup directories exist, but their presence is **not** proof
  of a current, complete, recoverable backup. No restore was performed here.

## Required recovery coverage

| State | Coverage to capture and restore-test |
| --- | --- |
| Node identities and authentication | Entire `/var/lib/archipelago`, including identities, identity, secrets, credentials, settings, sessions, remember-secret/revocations, grants and app configurations. Preserve numeric owners, modes, ACLs and extended attributes. |
| KithMoot | `/var/lib/archipelago/kithmoot-node` (about 23 MiB at inspection), all room/history/access state, configuration, private runtime image, manifests and Quadlet. No new identity, room re-creation or re-pairing. |
| Wildbloom | `/var/lib/archipelago/wildbloom-node`, receipts/entitlements/payment-recovery state and the exact current image/manifests. Retain existing blobs and do not repay for recovery. |
| Fedimint | `/var/lib/archipelago/fmcd` (about 92 MiB). Treat as wallet state regardless of known balance. Do not run restored copies online or revert financial state without a wallet-specific recovery assessment. |
| File Browser | `/var/lib/archipelago/filebrowser`, `filebrowser-data`, and **both anonymous volumes** under `/var/lib/archipelago/containers/storage/volumes/*/_data`, mounted at `/config` and `/database`. |
| Spry | `/var/lib/archipelago/spry`, existing credentials, limits, network configuration and installed image. |
| Runtime and recovery | Current binary, frontend, `/opt/archipelago`, `/etc/archipelago`, nginx, system/user units and Quadlets, user/container configuration, UID/subuid/subgid mapping, CA and SSH host identity, firewall rules and enabled/stopped timer/service choices. |
| External state | Re-inventory bind mounts and named volumes immediately before backup. Any newly discovered path outside the captured roots blocks the upgrade until covered. |

Do not omit Podman volumes as a generic cache. Image layers may be reproducible;
named/anonymous volumes are application state. Save exact custom image IDs and
retain/export any image that cannot be pulled by immutable digest.

## Qualification and activation gates

1. Reconcile the beta source against every local patch. Retain Wildbloom sales,
   refunds and exact image allowlists; Spry host TLS and mesh controls; KithMoot
   ingress, private signer routing, lifecycle/deletion protections and resource
   limits. Re-vendor the provider only after its host/embedded contract is tested.
2. Build and test the combined backend, dashboard and runtime payload. Include
   beta runtime helpers in the produced payload: merely overlaying our old
   runtime would silently undo upstream upgrade and security fixes.
3. Exercise upgrade, interrupted upgrade and rollback on an isolated disposable
   node with representative **generated** 1.9.1 state. Verify existing/stopped
   apps, private apps, identities, stored files and room history survive. Use
   upstream's isolated backend harness; never run its host tests on this server.
4. Prepare exact artefact hashes and the named-screen maintainer review pack.
   Retain PR53/PR54's unfulfilled acceptance gates. Obtain approval for the
   reviewed revision before merging or final UI approval.
5. Immediately before activation, agree the short maintenance window, prevent
   concurrent upgrades/maintenance, quiesce all persistent writers and take a
   fresh coherent recovery set. Verify archive checksums and restore to a
   separate isolated destination, including numeric ownership, database
   integrity and representative blobs/history. Keep the original untouched.
   Retain a private off-host recovery copy or separately verified machine
   snapshot; same-disk files alone do not protect against loss of the server.
6. Record whether schemas allow code-only rollback. After new writes/payments,
   never restore stale databases merely to undo a UI/runtime update. If a
   backwards-incompatible migration occurs, require a tested forward-recovery
   or consistent cutover/restore procedure before starting it.
7. Activate only the qualified pair and runtime through the reviewed updater.
   Preserve application image IDs and volume mounts, keys, CA, SSH identity,
   public ingress and private management policy. Do not rebuild the server,
   reinstall from ISO, prune volumes or use the fresh-host installer.
8. Verify manager health and exact bytes, all six existing apps, old-file
   retrieval, sign-in and pairing, room IDs/history and new message delivery.
   Keep desktop, Android and web connected in the same existing rooms. Verify
   TURN/TLS443, certificate renewal and private dashboard/signer denial from an
   external network. Record physical/client and maintainer evidence separately.

## Current installer safeguard

`node/install-lite.sh` now refuses either runtime when any existing Archipelago
state/configuration/runtime root, backend or service unit is present (including
broken symlinks). The refusal precedes reading the bundle's executable PINS,
package installation, service changes, firewall reset and SSH key generation.
It has no bypass switch. Interrupted fresh installs need diagnosis and a
reviewed recovery action, not deletion of state to satisfy this check.

## Compatibility changes and evidence

The beta has incorporated the earlier linked NIP-46 identities, signer login,
multiple login signers, QR pairing, pairing-reply recovery and installed-port
classification. Those alpha patches are retired from the candidate stack.
Public-host certificates still need our integration; they now use beta's
rustls 0.23 APIs, including positive certificate/key pairing and hostname
checks. The focused source-sharing TLS harness uses the same TLS version.

The remaining Wildbloom storage/sales/refund, Spry runtime/TLS/mesh and KithMoot
private ingress/lifecycle patches have been rebased. Beta's protected ingress,
new Settings grouping, ecash host facts and broader safe Quadlet resource
handling are retained. Storage appears within Settings' System group and search.
A separate patch fixes an upstream beta test's invalid parent-module import.

The runtime build now stages patched scripts/configuration with a regenerated
`RELEASE-PAYLOAD.json` and a separate ForgeSworn provenance record. It retains
upstream built assets, uses the canonical 755/644 archive modes and includes every patch in
the frontend input digest. The two bundled NIP-07 providers are refreshed to
beta's origin-bound messages. New Wildbloom/Spry package revision numbers avoid
reusing immutable image tags; they do not replace any live app image.

Verified locally so far:

- Exact beta Git source fetched. The archive-derived build tree matched the
  real Git tree after all 33 compatibility patches, byte for byte. The final
  series replayed cleanly as `193bbef45d685d47fbfcf2dff0f5760a2d0da80e`.
  Both the replay and local build have Git tree
  `47f1d4f7044bc9897fdc394239b79acebd63f430`; their last committer differs.
- Dashboard and embedded AIUI type checks; production dashboard build.
- 125 storage/settings/linked-bridge frontend tests, additional route/login
  tests, and 26 catalogue/provider tests. The old unsigned-store assertion was
  replaced with an explicit rejection test for beta's authenticated catalogue.
- Desktop/mobile browser storage, draft/apply, sales, refund-record and failure
  paths, with synthetic RPC and no payments. Captures are in the review pack.
- 90 Python bundle/recovery/installer tests; all eight nginx/certificate tests
  and 23 dashboard-public-guard tests in an isolated, offline Linux container.
- Runtime staging tests cover changed helper bytes, declaration refresh,
  canonical staging and symlink refusal before existing payload replacement.

The local frontend package completed on Node 24.21 (CI uses pinned Node 20).
Its two deterministic repacks matched and the upstream complete-archive
validator accepted the runtime byte declaration and native AIUI receipt:

- Retained local artefact: `.cache/beta2-frontend-out/frontend.tar.gz`
  (119,836,169 bytes).
- SHA-256: `783a858a77246c7db526c5328a3dddfeb9dcf9668f75ee3f62b089e1401c8cfb`.
- Build-input digest: `9d40d90c6cabe1e90ef2994d1cc184b704176800cc556c0246e805f1c11141a0`.
- Patched source commit in this artefact:
  `3f0b5e0645896af238364d77402f02086979b6b4`.

Linux backend, isolated installed-node migration and physical/client checks
are separate gates. No current complete off-host recovery set or restore
qualification is claimed.

## Known beta integration differences

The beta App Store only admits the daemon's release-root-verified catalogue.
Our unsigned community Spry entry can supply presentation metadata for an
already signed entry, but cannot offer a new install by itself. This security
boundary is retained. New Spry store installation is unqualified until a
supported verified catalogue path exists; the existing installed relay must
remain in place and be qualified through installed-app controls.

This derivative cannot reuse the upstream release signature to authorise its
modified backend/frontend. Do not feed our bundle through official signed OTA
as though it were the upstream artefact. A tested operator migration path is
still required, and the old binary/frontend-only updater remains guarded.

[Maintainer review pack and screenshots](reviews/archy-beta2-20261112/README.md).
Maintainer must review and approve UI work on Settings, Storage & selling,
Sales & customers/refund recording, App Store, linked-signer login and the
embedded Wildbloom/Spry/KithMoot node screens before merging or approval.
ZAT pending.
