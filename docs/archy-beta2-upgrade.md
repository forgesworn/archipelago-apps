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
- This candidate branch pins beta.2 and contains 34 rebased patches. Main,
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

### Migration-specific startup hazard

Beta's ordinary legacy bootstrap still replaces `/opt/archipelago/apps`,
`scripts` and `docker` from the frontend runtime payload. The public update
transaction avoids this by retaining omitted private app sources and owning
runtime promotion, including a startup guard for older binaries during recovery.
Simply copying our new binary/frontend onto the alpha node does not establish
that ownership and can lose private app definitions on the next manager start.

The operator migration therefore needs an explicit, tested runtime handoff
before starting the candidate. Assert that all six installed definitions,
resolved image IDs, Quadlets, bind mounts and anonymous volumes remain exact,
including KithMoot's locally built image. Catalogue defaults may change images
during reconciliation unless the installed version is properly retained; copying
an old manifest alone is insufficient proof. These conditions must survive a
second manager restart and interrupted recovery on the disposable node.

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
Separate test patches fix an upstream beta parent-module import, two ambiguous
federation result types and the added TURN field in beta's network fixture.

The runtime build now stages patched scripts/configuration with a regenerated
`RELEASE-PAYLOAD.json` and a separate ForgeSworn provenance record. It retains
upstream built assets, uses the canonical 755/644 archive modes and includes every patch in
the frontend input digest. The two bundled NIP-07 providers are refreshed to
beta's origin-bound messages. New Wildbloom/Spry package revision numbers avoid
reusing immutable image tags; they do not replace any live app image.

Verified locally so far:

- Exact beta Git source fetched. All 34 patches applied cleanly; current
  assembled source is `18260448bb570d96962f5da2f2e30c163b351dd4`, tree
  `fadcb6832e0077194aa2fcbbaea5083b8d9e7f47`. The earlier 33-patch local
  frontend build and clean replay had identical tree
  `47f1d4f7044bc9897fdc394239b79acebd63f430`; their last committer differed.
- Dashboard and embedded AIUI type checks; production dashboard build.
- 125 storage/settings/linked-bridge frontend tests, additional route/login
  tests, and 26 catalogue/provider tests. The old unsigned-store assertion was
  replaced with an explicit rejection test for beta's authenticated catalogue.
- Desktop/mobile browser storage, draft/apply, sales, refund-record and failure
  paths, with synthetic RPC and no payments. Captures are in the review pack.
- 90 Python bundle/recovery/installer tests; all eight nginx/certificate tests
  and 23 dashboard-public-guard tests in an isolated, offline Linux container.
- All 22 production-source TLS tests pass in isolated Linux. Ten runtime
  transaction and four maintenance-drain regressions also pass, covering
  private app retention, code recovery, interrupted renames and timer choices.
  These are generated filesystem fixtures, not an installed-node rehearsal.
- Runtime staging tests cover changed helper bytes, declaration refresh,
  canonical staging and symlink refusal before existing payload replacement.

The local frontend package completed on Node 24.21. Initial CI exposed the
upstream Node 20 setting as stale: the locked Vitest and vue-i18n require Node
22/24, and npm 10 could not install that lockfile. CI now pins Node 24. The final local artefact below was rebuilt after that
correction and all 34 patches, using a clean source checkout.
Its two deterministic repacks matched and the upstream complete-archive
validator accepted the runtime byte declaration and native AIUI receipt:

- Retained local artefact: `.cache/beta2-frontend-out/frontend.tar.gz`
  (119,836,125 bytes).
- SHA-256: `45b440d1896a0c51e4b71aba64c768a82e6487f4e0cb84a26e9d9ebadd839793`.
- Build-input digest: `99e8a841cd42aa256d26cc3546d41aa6e482b1a4ec80cd09308fba67059bcc94`.
- Patched source commit in this artefact:
  `18260448bb570d96962f5da2f2e30c163b351dd4`.

Hosted frontend CI at `dd8216be3b66a2870ece8b81451ef6767322e746`
passed the complete package build, 59 UI tests, browser acceptance, 27 upstream
release-payload tests, 14 runtime/maintenance tests and three integration
staging tests. The local ARM container could run 26 of those 27 payload cases;
the remaining native-manifest fixture requires x86_64 and passed in CI.
[Frontend run](https://github.com/forgesworn/archipelago-apps/actions/runs/43258922145).

Linux backend, isolated installed-node migration and physical/client checks
are separate gates. No current complete off-host recovery set or restore
qualification is claimed.

The first local Linux production check used Rust 1.94.1, which is too old for
upstream's `AtomicU64::try_update`, and its compiler subsequently received SIGKILL. This is not a backend pass; hosted CI uses the
current stable toolchain and remains the backend build gate.

## Known beta integration differences

The beta App Store only admits the daemon's release-root-verified catalogue.
Our unsigned community Spry entry can supply presentation metadata for an
already signed entry, but cannot offer a new install by itself. This security
boundary is retained. New Spry store installation is unqualified until a
supported verified catalogue path exists; the existing installed relay must
remain in place and be qualified through installed-app controls.

The [current public catalogue](https://source.archipelago-foundation.org/lfg2025/archy/raw/branch/main/releases/app-catalog.json),
fetched on 12 November, reports `updated: 2026-10-05`. Its claimed release-root
signature did not pass independent verification, so it is not qualification
evidence for authenticated catalogue availability. It has no entries for `spry`, `wildbloom`,
`wildbloom-node` or `kithmoot-node`; new App Store installation therefore needs
a supported verified catalogue path for each, not only Spry. This observation
does not authorise removing or replacing any installed private app.

The catalogue SHA-256 is
`ba2cbc4dafbf3c4d843ea2cac55910c279ea3b478aaf5075f64773346bb3f1b2`, identical
to `releases/app-catalog.json` in pinned beta source. The verifier uses the
source's sorted, compact UTF-8 JSON preimage with both signature fields removed,
and the pinned Ed25519 root. As a positive control it successfully verifies the
downloaded beta release manifest (SHA-256
`59234917bd97a1f89dc7d5b77292d08fa40a4c7d3b085b82b1cf9b276b2eabe0`).
Resolve authenticated catalogue availability before claiming working beta
App Store support. Do not suppress verification or use the rejected catalogue
as installation authority.

This derivative cannot reuse the upstream release signature to authorise its
modified backend/frontend. Do not feed our bundle through official signed OTA
as though it were the upstream artefact. A tested operator migration path is
still required, and the old binary/frontend-only updater remains guarded.

[Maintainer review pack and screenshots](reviews/archy-beta2-20261112/README.md).
Maintainer must review and approve UI work on Settings, Storage & selling,
Sales & customers/refund recording, App Store, linked-signer login and the
embedded Wildbloom/Spry/KithMoot node screens before merging or approval.
ZAT pending.

## Repository refresh

The two clean tracked integration worktrees (`feat/kithmoot-node-20261102`
and `fix/kithmoot-node-clipboard-20261108`) passed `git pull --ff-only` and
were already current. GitHub refs were fetched for the original checkout.
The original operator branch, detached alpha source and local patched source
branches have no tracking upstream; none was switched, reset or merged.
Full Gitea ref/tag refreshes timed out, including a bounded retry. The exact
beta tag/source was fetched successfully into this task's separate source
checkout; the original source checkouts retain their alpha revisions.

## Backend CI qualification

The complete beta backend test executable compiled in CI. Its first executed
suite passed 3,115 tests with three failures, 29 upstream ignores and nine
explicit exclusions. The failures were a missing `/usr/bin/tor` and two actual
Quadlet tests encountering Ubuntu 24's Podman 4.9 `StopTimeout` limitation.
The runner now installs Tor without starting its host services and builds the
real Podman 5.4.2 generator from upstream commit
`be85287fcf4590961614ee37be65eeb315e5d9ff`. Tor remains offline inside the isolated
harness. This qualifies generation only; it does not upgrade the runner's
Podman runtime or the live node. The older stop-order generator exclusion has
also been removed. The corrected full suite, seven isolated host-operation
tests, exact identity patch checks and all selected signer/integration modules
passed in [backend run 43261318325](https://github.com/forgesworn/archipelago-apps/actions/runs/43261318325).
The packaged Wildbloom storage-profile check and release backend build also
passed. The matching frontend and fresh Debian host checks are still running;
this is not yet a complete backend workflow pass.

A final read-only node check found manager/nginx active, health `ok`, recovery
complete and the same alpha version and binary hash recorded above. No live
upgrade or backup was performed.
