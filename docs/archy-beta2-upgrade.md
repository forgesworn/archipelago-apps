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
fetched again on 13 November, remains byte-identical to the 12 November copy
and reports `updated: 2026-10-05`. Its claimed release-root signature failed
both independent verification and the exact candidate's production verifier,
so it is not qualification evidence for authenticated catalogue availability.
It has 64 entries but none for `spry`, `wildbloom`, `wildbloom-node` or
`kithmoot-node`; new App Store installation therefore needs a supported
verified catalogue path for each, not only Spry. This observation does not
authorise removing or replacing any installed private app.

The catalogue SHA-256 is
`ba2cbc4dafbf3c4d843ea2cac55910c279ea3b478aaf5075f64773346bb3f1b2`, identical
to `releases/app-catalog.json` in pinned beta source. The verifier uses the
source's sorted, compact UTF-8 JSON preimage with both signature fields removed,
and the pinned Ed25519 root. On 12 November it successfully verified the
downloaded beta release manifest (SHA-256
`59234917bd97a1f89dc7d5b77292d08fa40a4c7d3b085b82b1cf9b276b2eabe0`).
That manifest URL returned 404 on 13 November; the fresh control used a retained
signed alpha manifest (SHA-256
`19dfbac51a9f266aafa6342aa1df32fc6e48b5e35a7b332a253ae2edcb49dcad`),
which both verifiers accepted. The exact candidate rejected the catalogue with
exit 1; see the [reproduction report and owner-ready upstream request](reviews/archy-beta2-20261112/catalogue-verification.md).
Resolve authenticated catalogue availability and exercise actual fresh installs
before claiming working beta App Store support. Do not suppress verification
or use the rejected catalogue as installation authority.

This derivative cannot reuse the upstream release signature to authorise its
modified backend/frontend. Do not feed our bundle through official signed OTA
as though it were the upstream artefact. A tested operator migration path is
still required, and the old binary/frontend-only updater remains guarded.

[Maintainer review pack and screenshots](reviews/archy-beta2-20261112/README.md).
Maintainer must review and approve UI work on Settings, Storage & selling,
Sales & customers/refund recording, App Store, linked-signer login, Fresh authorisation and the
embedded Wildbloom/Spry/KithMoot node screens before any PR is accepted into
core Archipelago or final core approval. ZAT pending. The owner clarified on
13 November that this does not gate the ForgeSworn PR53–PR55 chain or exact
public-image publication.

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
proof of a coherent cutover backup. A fresh, bounded maintenance snapshot and
restore qualification remain required before activation; the File Browser and
timer precautions above apply. None of this recovery material is uploaded to
public CI or Git.

### Actual-node isolated restore rehearsal, 13 November

The private report is
`~/Backups/archy-demo-20261112/restore-evidence/RESTORE-REPORT.md`; its JSON
receipts and logs remain outside Git. A task-owned 2-CPU/4-GiB Fedora CoreOS
VM with a 30-GiB disk was selected after Docker proved unable to restore
overlay whiteout device nodes. External networking was blocked before import,
with only the host SSH control channel retained; runtime containers also used
`network=none`. No live backup, server restart, payment or live-node change
occurred.

The full filesystem comparison passed: all 100,821 entries, 59,113 file hashes,
numeric owners, modes, recorded timestamps, links, FIFOs, eight whiteouts and
67 extended attributes matched, with no unexpected paths. The archive has no
ACL records, so non-default ACL recovery is not demonstrated. Original UID and
subuid/subgid mappings and the original data path were restored. The standalone
OCI import recovered the exact KithMoot image ID. All six original container
IDs, image IDs/names, binds and mounts matched the captured inventory.

A failed first runtime open exposed an important crash-recovery requirement:
Podman deleted the six stale-running auto-remove containers and anonymous
volumes. The untouched baseline was recopied, and the runtime-only preparation
disabled auto-removal in both the Podman SQLite configuration and OCI specs
before opening them. Both anonymous volumes then survived application start
and stop; the captured File Browser settings file hash remained exact.

All six real applications started offline and later stopped with exit code
zero. Fedimint opened its existing RocksDB/federation state and started its
monitors without external connectivity or payments. Six KithMoot room
databases passed integrity checks with 3,399 events. Wildbloom's 17 blob
records matched 17 restored files, and its sales/allowance records remained.
The exact private alpha reported `1.9.1-alpha-dev` and returned local health
`status=ok`, `crash_recovery_complete=true`. One manager discovery sample had
`wildbloom-node` exited, so manager health alone is not treated as integrated
per-app health evidence.

The VM uses Fedora CoreOS, Podman 5.1.2 and Rosetta rather than the live
Debian/Podman 4.3 environment. It is retained with manager/apps stopped and
isolation enabled for migration qualification. The online-copy consistency
limits, full host/disk-image recovery, physical clients and external network
acceptance remain unqualified. A later alpha repair run removed Spry and
KithMoot from a mutable runtime copy. Goal 2 reproduced that environment-drift
path and qualified a direct guarded-beta migration that bypasses alpha repair.

### Coherent snapshot procedure and rehearsal

`scripts/coherent-node-snapshot.py` is the operator procedure, distinct from
the generated fixture. It takes the snapshot/update lifecycle locks, records
manager, root NPM bridge and container health-timer choices, stops the manager
and root writers, and pauses running rootless containers without stopping or
recreating them. It synchronizes the filesystem and writes an uncompressed,
mode-0600 tar while streaming SHA-256. Output cannot overwrite an existing
archive or reside inside captured roots. The manifest records exact roots,
container/service choices and recovery status.

The capture runs as a transient systemd unit with an always-run recovery
action. Recovery terminates any incomplete tar process group, removes an
uncommitted archive, unpauses only containers paused by the operation, and
restores recorded service/timer choices. Missing transient health timers are
recreated with the recorded container health interval, with an initial check
and without container restart. A deadline-aware read enforces the pause budget;
unit tests cover timeout cleanup, health-timer discovery/recreation, idempotent
recovery and archive hashing/refusal.

For a live maintenance window only, after reviewing the current inventory and
free disk/RAM, the documented command is:

```sh
sudo install -m 700 scripts/coherent-node-snapshot.py /opt/archipelago/scripts/
sudo /opt/archipelago/scripts/coherent-node-snapshot.py \
  --output /root/archy-coherent-YYYYMMDD.tar --pause-budget 120
```

This stops the manager during capture. Do not run it outside an agreed window.
The default manager/NPM units match the real node; `--additional-root` exists
only for host layouts such as the rehearsal VM's `/usr/local` symlink to
`/var/usrlocal`. Verify the archive and restore separately, then encrypt and
transfer it off-host before activation. If recovery reports errors, use the
state's recorded recovery command rather than starting an upgrade.

The final isolated rehearsal used a 300-second VM budget and completed with an
89.408-second pause and 2.3-GiB service memory peak. A separate restore passed
full tar comparison and exact alpha/application checks. Six managed writer
databases all contained sequence 11279, the root writer remained readable,
all six container definitions and both anonymous volumes were present, and
KithMoot's 3,399 events and Wildbloom's 17 blob files/records survived. A
one-second timeout and a real SIGKILL during tar both terminated capture,
removed uncommitted output and restored all services; all three health timers
received future runs. Private receipts are under
`~/Backups/archy-demo-20261112/restore-evidence/coherent-snapshot-*` and
`*-interruption-result.json`. Goal 1 is complete; a fresh coherent snapshot is
still required at cutover.


## Actual-node operator migration qualification, 13 November

Goal 2 is complete on the isolated restored baseline. This is not live upgrade
approval. No live backup, restart, deployment, payment or maintainer contact
occurred.

### Procedure and exact artefacts

`scripts/migrate-node.py` owns the pair/runtime transaction;
`scripts/migration-startup-guard.py` is its persistent systemd startup guard.
Base revision `3e1dc3f` with the current reviewed working-tree additions:

- Migration SHA-256 `0a8d5314ac677f933c4d606233f4b3906be33fcce13f4ecb971158c771a71775`.
- Guard SHA-256 `c9bd6ed3ebdfb23d67a49db1480d9949bd7e1d0928a286ad6d19b024768473c3`.
- Candidate backend SHA-256 `e887b68d4232523bbf48a722b906b4759e9bf3270b98cc604630d8d92f57124d`.
- Candidate frontend SHA-256 `45b440d1896a0c51e4b71aba64c768a82e6487f4e0cb84a26e9d9ebadd839793`.
- Exact alpha SHA-256 `81a184a97a04b02ac65d44fe2b71e7c34f3d9c91486001b3cced60efa913230d`.
- The candidate's actual health version is `2.1.0-beta.2-dev`; the procedure
  requires that exact string rather than accepting a prefix.

The transaction binds the old and new hashes, records manager/root-NPM choices,
stops those control-plane writers without stopping application containers,
takes snapshot/update lifecycle locks, and preserves every observed Quadlet in
`update-transactions/installed-units` before candidate startup. It verifies six
container IDs, image IDs/names, mounts, auto-remove/network/port settings,
environment/command/labels, running state, recipe hashes and anonymous volumes
on two manager starts. It retains externally managed apps rather than inventing
recipes for them. On SELinux hosts the guard receives the executable `bin_t`
label; an unlabelled `var_t` copy was correctly rejected by systemd during the
rehearsal and that installation defect was fixed.

After a fresh coherent recovery set and a matching live inventory, install the
reviewed scripts and run with the running manager:

```sh
sudo install -m 755 scripts/migrate-node.py scripts/migration-startup-guard.py \
  /opt/archipelago/scripts/
sudo /opt/archipelago/scripts/migrate-node.py promote \
  --backend /root/beta2/archipelago \
  --frontend /root/beta2/frontend.tar.gz \
  --backend-sha256 e887b68d4232523bbf48a722b906b4759e9bf3270b98cc604630d8d92f57124d \
  --old-backend-sha256 81a184a97a04b02ac65d44fe2b71e7c34f3d9c91486001b3cced60efa913230d \
  --frontend-sha256 45b440d1896a0c51e4b71aba64c768a82e6487f4e0cb84a26e9d9ebadd839793 \
  --version 2.1.0-beta.2-dev --health-timeout 600 \
  --app fedimint-clientd --app filebrowser --app kithmoot-node \
  --app spry --app wildbloom --app wildbloom-node
```

The explicit app list is sorted and must match the current inventory; a changed
set is a stop condition, not permission to add or remove applications. The
operation state is `/etc/archipelago/node-migration.json`; code backups/staging
are under `/opt/archipelago/.node-migration`, and mode-0600 inventory evidence
is under `/var/lib/archipelago/node-migration`. Keep those recovery records
until delivery closes. `--manager-stopped` exists for a reviewed maintenance
entry and then requires the exact old backend hash. Normal cutover uses the
healthy running-manager precondition above.

Before candidate startup, `recover` restores only the old code pair and removes
new runtime-ownership records. Once candidate startup is authorised, recovery
is forward-only: rerun the same `promote` command. Do not restore an old
filesystem/database snapshot to undo a code change. The guard accepts only a
complete pair for the recorded phase; an incomplete or mixed pair cannot start
the manager.

### Alpha repair negative result

The exact alpha was also run on a fresh copy to diagnose the earlier loss. It
reported healthy `1.9.1-alpha-dev` recovery while removing both Spry and
KithMoot for environment drift. The VM's missing live sudo policy then blocked
recreation. Original host networking did not prevent that drift path; the
earlier `network=none` adaptation was not its sole cause. Alpha does not honour
beta's installed-runtime records or lifecycle lock, so alpha self-repair is not
a safe migration step. The qualified procedure bypasses it. The negative log is
`alpha-migration-repair.log` and its analysis is `alpha-repair-analysis.json`
in the private evidence directory.

The captured baseline has no `wildbloom` or `wildbloom-node` recipe in
`/opt/archipelago/apps`, and the candidate supplies neither. Those two
containers are therefore retained as explicitly external to manager
reconciliation. The other four installed recipes are retained exactly. This
corrects the earlier assumption that all six had on-disk recipes.

### Passing real-data rehearsals

Operation `214243d3-12c1-49df-bb84-829b12dc0190` promoted the exact pair. Both
beta starts returned `status=ok`, `crash_recovery_complete=true` and the exact
version. All six application fingerprints and both File Browser anonymous
volumes matched after the second start. KithMoot retained 3,399 events in six
rooms; Wildbloom retained 17 blob records/files and five paid sales; File
Browser's settings hash matched; Fedimint's RocksDB files remained present.
No catalogue or external network was available, demonstrating that installed
app preservation does not depend on catalogue availability.

The same operation then rejected an alpha/beta mixed pair and refused alpha
rollback. Forward repair was interrupted with a real SIGKILL after its first
beta inventory receipt while in `candidate-starting`; resumption completed a
further two-start verification and returned to `active`. The application/data
checks above passed again.

A separate fresh-baseline operation `8e481f76-a058-4b10-b65c-27134619aa48`
was killed during frontend replacement in `prepared`, before candidate startup
was authorised. `recover` restored the exact alpha pair, removed the new
runtime-ownership records and preserved all six original running containers,
images and mounts. An earlier checkpoint that observed `candidate-starting`
was not counted as pre-start evidence or rolled back.

Private receipts and logs are under
`~/Backups/archy-demo-20261112/restore-evidence/migration-success/`,
`migration-forward-recovery/` and `migration-prestart-recovery/`. The private
restore report summarises the failed environment adaptations as well as these
passes. All six final rehearsal containers were stopped cleanly with both
anonymous volumes retained; the VM remains offline and the verified baseline's
alpha hash is unchanged. The migration and snapshot test suite now has 30
passing tests.

### Qualification limits

The VM uses Fedora CoreOS, Podman 5.1.2 and Rosetta rather than live
Debian/Podman 4.3. Application execution used `network=none` and disabled
auto-remove solely as recovery adaptations; the operator procedure does not
change those settings on the source node. Host networking was still blocked
by the VM firewall. Live sudo policy, external ingress and real client traffic
were not exercised.

The actual store contains zero `secrets/*/*.secret` records and no v2 key, so
there is no real record to convert in this baseline. An unauthenticated
`security.list-expiring` request was rejected with 401 and did not create a key;
no owner password was available or changed for a real login test. The five
generated protected-store migration tests above remain the v1-to-v2 conversion
and matching-key evidence. Existing-password login on the real restored node,
physical clients and a controlled live cutover remain separate acceptance
steps. Goal 3 (authenticated new installs) and exact-revision maintainer UI
approval remain open.

## Fresh application installation and distribution readiness, 13 November

Goal 3 remains unqualified at authenticated distribution, but a separate local
fresh-install rehearsal passed for all four integration applications. The clean
Debian 13 ARM64 guest used rootless Podman 5.4.2 and the exact reviewed pair:
backend `9a5fde6fc0555f3675f052b9e3d8a141bda21e7b4f0e5bf94256a17b97deb5b7`,
frontend `75eb02bab32700e73b038fb5fabe57118b9a36972be7ff43c3b080804f53f19d`.
Through authenticated manager RPCs it installed, started and readiness-checked
Wildbloom Node, Wildbloom, Spry and KithMoot Node. All remained running on
readback; both Wildbloom containers were healthy, Spry's private relay was
ready, and KithMoot's exact private image ID was
`bc57a79baf111d3e2bc4a5c2c15bebb91c96469bca96dda49ceb32d51461cd86`.
The [public receipt](reviews/archy-beta2-20261112/fresh-apps-local-evidence.json)
records every local image ID and explicit non-claims.

The public images were built from their pinned ARM64 inputs; Wildbloom Node's
application and Shelter test stages passed during its build. KithMoot used only
the retained code OCI through Rosetta, not restored identity or room data.
External routing was removed before seed onboarding and stayed absent through
installation. The fixture used generated credentials, a loopback dummy public
address and self-signed public certificate for KithMoot preflight, and the
release-checksummed ARM64 FIPS package omitted by the lite recipe. It did not
exercise public CA issuance, external ingress, physical clients or payments.
The guarded driver is `tests/node/fresh-apps-host.py`.

A first install attempt exposed a real lite-host dependency defect: the Podman
package list omitted `nftables`, so netavark could not create `archy-net` and
Wildbloom Node repeatedly exited. `node/install-lite.sh` now includes it, the
new `tests/test_fresh_install.py` regression failed before the fix and passes
with the complete fresh-install tests. The final clean run used the corrected
bundle without mid-run repair.

This is local image/manifest transport, not signed App Store distribution.
The registry check found exact Spry `0.1.0-6b34f06-4` and Wildbloom
`0.0.1-ee21ed5-5` tags unpublished; Wildbloom Node's pinned tag is available
only as amd64. Older public tags do not contain the candidate's provider
changes and were not substituted. Beta also requires an immutable image digest
and valid cosign claim under the node's pinned image key at every pull, in
addition to the release-root catalogue signature. KithMoot remains deliberately
private with a private Shelter input; publishing it or inventing a catalogue
entry would change the chosen distribution position. See the
[owner-ready distribution request](reviews/archy-beta2-20261112/catalogue-verification.md).
Publish and cosign the exact public artefacts, sign the compatible catalogue
with the authorised release root, decide authenticated private KithMoot
delivery, then repeat fresh installation through that authenticated route.

## Linked signer, room and clipboard integration evidence, 13 November

A real `nak` NIP-46 signer and loopback relay passed against the exact ARM64
backend `9a5fde6fc0555f3675f052b9e3d8a141bda21e7b4f0e5bf94256a17b97deb5b7`.
The production RPC flow linked an identity, exported no Nostr or pairing secret,
signed a synthetic event with a fresh grant, enrolled that identity for login,
and completed a signer login. Reusing either the signing grant or completed
login attempt failed. `nak verify` independently accepted the event. The
[signer receipt](reviews/archy-beta2-20261112/signer-integration-evidence.json)
records that approval was automatic: no human/physical signer, embedded-browser
UI or public-relay acceptance is claimed. The guarded driver is
`tests/node/signer-integration-host.py`. Its generated fixture password was
removed on success and the VM/relay/signer were stopped and removed.

Current KithMoot source `e56ac08482fa7a207e2dbc36e34774188440d4ab` passed 20
Chromium checks against its deterministic offline relay. These covered real
rooms, chat reliability, two-device pairing/unpairing and clipboard refusal.
The node controller's component review separately passed clipboard-policy
refusal, absent Clipboard API and late-expiry handling, with no page errors or
accessibility violations. See the [room/clipboard receipt](reviews/archy-beta2-20261112/room-clipboard-evidence.json)
and [inspected manual-copy capture](reviews/archy-beta2-20261112/pairing-copy-blocked-390.png).
These are current-client and component results, not evidence that the exact
embedded candidate's existing rooms, physical Android/desktop clients or human
approval journeys have passed. Those remain live/maintainer acceptance steps.
