# Archy 2.1.0-beta.2 compatibility and node preservation

Status: compatibility candidate passes backend/frontend CI and the fresh-host
fixture; **not approved for a live upgrade**.
Scope: the owner confirmed only `demo.forgesworn.dev` (`95.216.164.146`).
No live services, data, firewall rules or credentials were changed by this task.

The [goals and handover](archy-beta2-goals.md) identify the remaining work,
its locations and completion gates. This document retains the supporting evidence.

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

A further read-only check confirmed that File Browser has `AutoRemove=true`
and both `/config` and `/database` volumes have `Anonymous=true`. An aggregate
read found one 130-byte file in `/config` and no files in `/database`; both
volume bindings still need preservation and re-inventory before maintenance. The other
five live containers also use automatic removal. Podman's [run documentation](https://docs.podman.io/en/latest/markdown/podman-run.1.html)
specifies removal of anonymous volumes when an automatically removed container
exits. **Do not stop/restart File Browser as a backup prerequisite:** that can
remove the very data being protected. No live container was stopped here.

The generated rehearsal now freezes its running workloads with Podman pause,
retains their container/volume references, flushes the filesystem and validates
the resulting crash-consistent snapshot by restoring database, blob and volume
contents. This is not yet a qualified live backup procedure: identify every
host-side writer, bound the pause window, guarantee unpause on interruption,
and verify recovery before any live action. The current node also has three
rootless Podman health-check timers and a 15-second root NPM bridge timer;
pausing app processes alone does not quiesce every writer or prevent health
checks from reacting to the pause. Planned app recreation also needs
explicit retention and reattachment of the existing anonymous volumes, or a
separately tested conversion to durable named volumes/binds.

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

### Secrets format and rollback

Beta's security RPC opens the encrypted secrets manager through
`SecretsManager::open_protected`. It migrates `secrets/<app>/*.secret` records
from `ARCHI_ENC1` to `ARCHI_ENC2` and retains the random key in
`secrets/.manager/key-v2`. The alpha implementation only understands the old
envelope. Switching back to the alpha binary after v2 records exist is therefore
not a qualified rollback. Preserve the entire secrets tree and its matching
key; never regenerate the key to work around a failed read.

Legacy authentication derives its key from the original data-directory path.
An isolated restore rehearsal must preserve `/var/lib/archipelago` inside the
disposable host, or use an explicitly reviewed offline recovery procedure that
retains the original derivation. Simply moving the legacy store to a different
data directory and opening it does not establish recovery.

A read-only count on the live node found zero `secrets/*/*.secret` records and
no `.manager/key-v2`. This concerns that specific encrypted manager store;
the node still has identities, wallet state and other application secrets that
must be backed up. Repeat the inventory at cutover and account for records
created during beta use before attempting any rollback.

All five upstream protected-store migration tests passed in an offline Linux
container using generated records and this worktree's existing Rust target.
They cover preserved values and reopening, corrupt/wrong-key refusal before
record replacement, missing/public-key refusal, interrupted migration and
symlink custody, and independent random keys/unknown-envelope refusal. This
does not establish restoration of the live node's complete state.

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
- A focused 31-test fresh-authorisation/linked-bridge run passes, covering the
  beta signing grant UI and existing bridge behaviour. The integrated app
  consent, password/TOTP and linked-device flow still requires maintainer review.
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

Backend CI, isolated installed-node migration and physical/client checks
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
The retained production binary independently reproduces the refusal while
accepting the signed release manifest; see the [reproduction report](reviews/archy-beta2-20261112/catalogue-verification.md).
Resolve authenticated catalogue availability before claiming working beta
App Store support. Do not suppress verification or use the rejected catalogue
as installation authority.

This derivative cannot reuse the upstream release signature to authorise its
modified backend/frontend. Do not feed our bundle through official signed OTA
as though it were the upstream artefact. A tested operator migration path is
still required, and the old binary/frontend-only updater remains guarded.

[Maintainer review pack and screenshots](reviews/archy-beta2-20261112/README.md).
Maintainer must review and approve UI work on Settings, Storage & selling,
Sales & customers/refund recording, App Store, linked-signer login, Fresh authorisation and the
embedded Wildbloom/Spry/KithMoot node screens before merging or approval.
ZAT pending.

## Repository refresh

The two clean tracked integration worktrees (`feat/kithmoot-node-20261102`
and `fix/kithmoot-node-clipboard-20261108`) passed `git pull --ff-only` and
were already current. GitHub refs were fetched for the original checkout.
The original operator branch, detached alpha source and local patched source
branches have no tracking upstream; none was switched, reset or merged.
Full Gitea ref/tag refreshes timed out, including a bounded retry. The beta
tag identity was verified remotely and its exact source commit fetched into
this task's separate shallow checkout. The original source checkouts retain
their alpha revisions; a complete ref/tag refresh is not claimed.

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
also been removed. The corrected full suite passed 3,119 tests with no failures,
29 upstream ignores and eight exclusions. Seven isolated host-operation
tests, exact identity patch checks and all selected signer/integration modules
also passed in [backend run 43261318325](https://github.com/forgesworn/archipelago-apps/actions/runs/43261318325).
The packaged Wildbloom storage-profile check, release backend build and matching
frontend build also passed. The fresh Debian host installed successfully and
ran Spry through readiness, stop, start and restart. It then correctly refused
the older fixture's signing request because beta requires fresh authorisation.
The fixture now requests a session/operation-bound one-use grant and verifies
both missing-grant and token-replay refusal. The complete rerun at
`664be6ce144931625c9e09ff66245c77914f186e` passed all these stages, including
the fresh Debian host, on 12 November at 17:53 UTC:
[backend run 43268204623](https://github.com/forgesworn/archipelago-apps/actions/runs/43268204623).
The full suite again passed 3,119 tests, with 29 ignores and eight exclusions;
the seven host cases passed separately. The container suite passed 104 tests
and production TLS passed 22. Release publication was skipped on this branch.

The generated [fresh-host evidence](reviews/archy-beta2-20261112/fresh-host-evidence.json)
records actual controller installation, seeded FIPS, Spry readiness and
uninstall, dashboard stop/start/restart, LAN/mDNS owner origins, foreign-origin
refusal, fresh signing grants and both grant/owner-proof replay refusal.
This is a fresh Docker-runtime host test, not migration of the existing Podman
node, Docker Desktop qualification or physical home-network acceptance.

The [exact backend/frontend pair](https://github.com/forgesworn/archipelago-apps/actions/runs/43268204623/artifacts/13967879604)
is retained for 14 days. Its downloaded archives, source identity and input
hashes were verified locally:

- Backend: `.cache/beta2-node-review/backend-review/archipelago`
  (82,369,024 bytes), SHA-256
  `e887b68d4232523bbf48a722b906b4759e9bf3270b98cc604630d8d92f57124d`.
- Backend input digest:
  `cb4cc545e29dbe65df1ed3b40b9c0ca362fcf52a4ee7f91dc79c9f23bdfbcb57`.
- Source commit `18260448bb570d96962f5da2f2e30c163b351dd4`, tree
  `fadcb6832e0077194aa2fcbbaea5083b8d9e7f47`.
- The matching frontend is byte-identical to the retained local archive and
  earlier frontend CI artefact documented above. The duplicate download was
  removed after comparison; the canonical local frontend and backend remain.

No task-owned fixture server, browser or test container remains running.
The unmerged worktree, source checkouts and named review artefacts are retained
for maintainer review and installed-node migration qualification.

At the backend-qualification checkpoint, a read-only node check found
manager/nginx active, health `ok`, recovery complete and the same alpha version
and binary hash recorded above. No live upgrade or backup had been performed
at that checkpoint; the later off-host copy is recorded below.

## Generated installed-node migration rehearsal

[Run 43280738065](https://github.com/forgesworn/archipelago-apps/actions/runs/43280738065)
passed the rootless Podman rehearsal on Debian 13 at integration revision
`10467fd7d918400c37695d73e564489ec634ced0`. The
[recorded evidence](reviews/archy-beta2-20261112/migration-evidence.json) includes
archive, recipe and Quadlet hashes. Its generated 228,116,480-byte snapshot
was paused for 1.26 seconds; that timing is not a live-node estimate. It used
published alpha
backend p3 (SHA-256
`e6158a4a34641562b77a1cbe754e60168caa07a6d558cb1fa9d7fdf1d3e7d94e`),
frontend p5 and the exact retained beta backend/frontend pair above.

The six generated manifest-driven workloads include a stopped app, private
and overlapping recipes, SQLite room-history records, blobs and ten anonymous
volumes attached to the five running workloads. They are test workloads, not
Fedimint, File Browser, Wildbloom, Spry or KithMoot acceptance. The nine offline
recipe-preparation regressions pass, including missing/indirect paths and
non-destructive refusal of existing or overlapping destinations.

The rehearsal passed:

- Existing container IDs, image IDs, mounts, Quadlets and app recipe hashes
  retained through beta startup and a second manager restart.
- Existing password login, personal identity and node key bytes retained.
- Deliberately stopped app remained stopped.
- Paused-workload backup restored to a separate directory with matching file
  bytes, numeric owners (including subuid/subgid values), permissions and
  extended attributes; SQLite integrity and generated history checked.
- A persistent service guard refused an interrupted mixed code pair before
  beta could run; restoring the old code restored alpha and the original login.
- No public update runtime record, altered signature verifier or test root.

The guard and recipe preparation are CI rehearsal mechanisms, not a released
operator updater. Recovery after beta has written incompatible state, complete
live-machine restore, exact private alpha compatibility and real application/
physical-client behaviour remain unqualified. The archive is a generated
crash-consistent snapshot, not a claim of a live coherent recovery set.

The exact live alpha executable was copied read-only into
`.cache/beta2-live-alpha/archipelago` (113,043,064 bytes) and verified against
`81a184a97a04b02ac65d44fe2b71e7c34f3d9c91486001b3cced60efa913230d`.
This retains code for a private rehearsal; it is not a backup of identities,
wallets, application data or the rest of the host. No live app was paused,
stopped or restarted. The owner selected an encrypted recovery copy on this
Mac; capture and qualification are recorded separately below. Do not treat
the representative public alpha build as this private
binary or publish private recovery material as a CI artefact.

## Encrypted off-host recovery material

The owner selected this Mac as the recovery destination. Private artefacts are
retained outside Git in `~/Backups/archy-demo-20261112`, with a 0700
directory and 0600 files. They use the existing age recovery recipients; the
primary working identity was verified by encryption/decryption before capture.
No age recovery identity was copied into the backup directory or onto the
server. Node identities and host keys are intentionally inside the encrypted
recovery archives.

The exact installed KithMoot image was exported read-only to an encrypted OCI
archive (270,344,821 bytes). Authenticated decryption, every OCI descriptor and
blob hash, and the configuration's match to the installed image ID passed.
Image import and application startup are not established by those checks.
An encrypted inventory preserves all six container definitions and mounts,
image/volume identities, UID mappings, packages, firewall and service/timer
choices; all 20 read-only inventory commands succeeded and the encrypted
result round-tripped exactly.

Ten SQLite files were separately captured with SQLite's online backup API
using read-only source connections, then restored into isolated temporary
files on the Mac. All ten integrity checks passed and schema table counts
matched. A second restore in a network-disabled Linux container also passed
for all ten, including restored numeric owners and modes. It used only a
64 MiB temporary filesystem, with no host mounts or application startup; the
container was removed afterwards. Their encrypted archive is 15,138,698 bytes. These are individually
consistent database snapshots, not one cross-application snapshot or a
Fedimint wallet-engine recovery test. Temporary plaintext restores were
removed after checking.

The copy includes the entire `/var/lib/archipelago` backing store (including
all inventoried bind data, anonymous volumes and image layers),
`/opt/archipelago`, `/etc`, `/usr/local`, FIPS, user container configuration,
root SSH recovery configuration and service state. Historical build/backup
directories outside these recovery roots and unrelated OS files are omitted;
this is a node recovery archive, not a disk image. The private receipt records
the exact roots and exclusions.

The completed archive is 2,425,957,028 bytes. Authenticated decryption and
complete gzip/tar reading passed across 100,821 entries and 4,981,922,098
regular-file bytes. Required roots and the exact alpha executable hash were
verified; ten SQLite files extracted from this copy also passed offline
integrity checks. Tar reported changes to the data and container-storage
directories during reading and omitted 3,869 ephemeral sockets. The encrypted
private diagnostic and receipts preserve that warning; it is not a pristine
shutdown snapshot.

Post-capture, manager/nginx are active, health/recovery is OK on the same
alpha binary, and all six running, unpaused containers retain their original
IDs, images, mounts and start timestamps. No app was restarted.

The live copy was captured while services kept running. It must not be used as
proof of a coherent cutover backup, complete host restore or wallet recovery.
A fresh, bounded maintenance snapshot and isolated restore qualification
remain required before activation; the File Browser and timer precautions
above apply. None of this recovery material is uploaded to public CI or Git.
