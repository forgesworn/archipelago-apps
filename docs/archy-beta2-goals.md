# Archy beta upgrade goals and handover

Updated 13 November 2026. This is the execution plan; detailed observations,
hashes and limitations remain in the [upgrade evidence](archy-beta2-upgrade.md).

**Outcome:** upgrade the existing owner node to our qualified Archy
`2.1.0-beta.2` integration while preserving its six applications, identities,
wallet state, files, room history, private images and network configuration.
Existing users must not need to recreate rooms or re-pair identities.

## Where the work belongs

| Work | Location and ownership |
| --- | --- |
| Upgrade implementation and evidence | Use the existing upgrade chat and `~/WebstormProjects/archipelago-apps-beta2-20261112`, branch `feat/archy-beta2-compat-20261112`. Continue [draft PR55](https://github.com/forgesworn/archipelago-apps/pull/55). |
| Original checkout | `~/WebstormProjects/archipelago-apps` remains on `feat/operator-call-transport`. Do not switch, reset or duplicate the beta work there. |
| Generated migration tests | `tests/migration/`, `scripts/test-beta-migration.sh` and `.github/workflows/beta-migration.yml` in the beta worktree. These are fixtures, not a production updater. |
| Private recovery material | `~/Backups/archy-demo-20261112/`. Start with `RECOVERY.txt`, the JSON receipts and `SHA256SUMS`. Keep payloads, identities and keys outside Git and public CI. |
| Actual-node restore rehearsal | Retained offline Podman VM `archy-restore-20261113` (2 CPUs, 4 GiB RAM, 30 GiB disk). Verified baseline `/var/restore-root`; mutable `/var/runtime-root`; external network blocked. Manager/apps stopped. |
| Maintainer review | [Named-screen review pack](reviews/archy-beta2-20261112/README.md). The owner passes it on; do not contact the maintainer without authorisation. |
| Live cutover | Only `demo.forgesworn.dev` (`95.216.164.146`), after the gates below. No other node is in scope. |

Use one chat to execute the upgrade. The other chat, “Check Archy beta and
contributions”, completed a status/adoption check and is not assigned a second
deployment. If execution moves to another chat, hand over this document,
branch, current revision and active commands first. Do not repeat completed
builds or backups merely because a new window opens.

## Starting position

- PR55 was rechecked on 13 November: no recorded maintainer approval. It is
  stacked on PR54 and PR53. The owner clarified that ZAT is required before PRs
  are accepted into core Archipelago, not before the ForgeSworn implementation,
  test, PR-merge and exact-image publication work.
- Backend/frontend CI, the fresh-host fixture and the generated rootless
  Podman migration rehearsal pass. The latter uses published alpha p3 and
  generated applications; it does not qualify our private alpha or real apps.
- The 2.43 GB encrypted online node archive, exact private KithMoot OCI image
  and individual SQLite snapshots have passed the documented readback checks.
  On 13 November the actual archive also passed a full isolated VM restore,
  all six offline application starts and exact-alpha health recovery. The
  online source's consistency limits remain. The separate coherent snapshot
  procedure passed isolated consistency/interruption tests; a fresh snapshot
  is still required at cutover. See `~/Backups/archy-demo-20261112/restore-evidence/RESTORE-REPORT.md`.
- Last live verification was 12 November, after backup: alpha
  `1.9.1-alpha-dev`, manager/nginx healthy and six running containers with
  unchanged IDs, images, mounts and start times. Refresh this before live work;
  the isolated restore is not a new live health check.
- The exact old private alpha and beta candidate artefacts remain in the
  worktree caches named in the evidence document. CI downloads have limited
  retention; preserve the verified local copies and do not substitute a newer
  unreviewed binary if an artefact expires.

## Goals, in execution order

### 1. Prove recovery of the actual node

**Where:** private recovery directory and an isolated disposable Linux host.

- [x] Select the restore environment and check disk/RAM capacity. Keep its
  network disabled before importing real node identities, wallets or images.
  The retained `archy-restore-20261113` VM has 2 CPUs, 4 GiB RAM and a 30-GiB
  disk; external networking was blocked before import.
- [x] Restore the existing recovery material into a separate destination;
  verify owners, subuid/subgid mapping, modes, ACLs, xattrs, keys, app data,
  volume bindings and the exact installed private image. Import and inspect
  the OCI image; a valid archive alone does not prove runtime recovery.
  All recorded metadata passed; the archive contains no ACL records.
- [x] Check real application storage, including Fedimint's storage engine,
  KithMoot room/history state and Wildbloom files/receipts. Record exact passes
  and failures. Do not run a restored wallet online or initiate payments.
  The private report records the runtime adaptations and manager/app results.
- [x] Prepare and rehearse a bounded, coherent snapshot procedure that accounts
  for manager/app writers, rootless health-check timers and the root NPM bridge.
  It must recover automatically from interruption and restore prior service
  choices. The existing online copy cannot establish cross-application consistency.
  `scripts/coherent-node-snapshot.py` passed consistency, timeout and SIGKILL
  rehearsals; the final 89.408-second pause restored all recorded choices and
  passed separate-destination application/data verification.

**Done when:** a private restore report demonstrates the captured state can
be recovered, and the snapshot procedure has tested consistency and interruption
handling. Any limits of the online source remain explicit. A fresh snapshot
using that procedure is still required at cutover in goal 5.

**Critical constraint:** File Browser has auto-removal and two anonymous
volumes. Do not stop/recreate it as a backup prerequisite. Qualify explicit
retention/reattachment, or a tested durable-volume conversion, before any
action that could remove its container.

### 2. Qualify the production migration procedure

**Where:** beta worktree, generated CI fixtures and the isolated restored node.

- [x] Implement/review an operator migration procedure for this derivative.
  `scripts/migrate-node.py` and its persistent startup guard are the qualified
  path. Neither the old alpha updater nor the fresh installer is used.
- [x] Promote the exact backend, frontend and runtime together. All six exact
  container/image/environment/mount/Quadlet fingerprints and both anonymous
  volumes survived beta bootstrap and a second manager restart. Four existing
  recipes were retained byte-for-byte; Wildbloom and Wildbloom Node had no old
  or candidate recipe and remained explicitly external to manager reconciliation.
- [x] Cover lifecycle locks, maintenance drain, interrupted promotion and
  persistent startup refusal for an incomplete pair. Pre-candidate interruption
  recovered alpha without starting it; a real post-beta SIGKILL resumed forward,
  and a mixed pair was rejected and repaired without alpha rollback.
- [x] Exercise the procedure against the exact private alpha executable and
  actual restored configuration. Alpha's environment-drift repair removed Spry
  and KithMoot in a negative rehearsal, so the qualified procedure bypasses
  alpha reconciliation. Private evidence remains outside Git and public CI.
- [x] Account for beta's encrypted-secret conversion and matching key. The real
  store has zero encrypted records and no key to convert; generated conversion
  tests remain the format-change evidence. No old-alpha rollback or stale
  application-data restoration is permitted after candidate startup.

**Done when:** the procedure and its failure/recovery paths pass on the actual
isolated baseline, with a recorded source revision, artefact hashes and evidence
for all six apps. This goal is complete. Environment adaptations and the absence
of real secret records are documented; they are not claims of live deployment,
real password login, physical-client acceptance or a new-install catalogue.

### 3. Resolve the authenticated catalogue contract

**Where:** beta integration and the [catalogue reproduction report](reviews/archy-beta2-20261112/catalogue-verification.md).

- [x] Recheck the upstream catalogue when resuming this work. On 13 November
  the served bytes remained identical to the rejected 12 November copy, failed
  both independent and exact-candidate verification, and omitted all four node
  integration entries. A signed release manifest passed as the positive control.
- [ ] Establish a supported authenticated distribution route for new Spry,
  Wildbloom, Wildbloom Node and KithMoot Node installs. The upstream report is
  prepared for the owner to share. Signed compatible entries and authenticated
  registry delivery are still required; do not bypass signatures or invent OTA
  authority. The exact Spry/Wildbloom packages are not yet published, all three
  public apps need immutable cosign-signed image references, and KithMoot's
  private-image distribution position needs an explicit owner/upstream decision.
- [x] Prove the four applications can actually install independently of that
  distribution gate. On 13 November a clean Debian 13 rootless Podman guest
  installed and started all four through manager RPC and passed readiness checks
  using locally loaded exact images, generated identities and no external route.
  The exact backend/frontend pair was `9a5fde6f…`/`75eb02ba…`; see the
  [public receipt](reviews/archy-beta2-20261112/fresh-apps-local-evidence.json).
  This is not a registry pull or signed-catalogue pass. KithMoot used its exact
  private OCI and Rosetta; fixture-only public addressing/certificates and FIPS
  provisioning are documented in the upgrade evidence.
- [x] Keep the fresh Podman network path installable. The rehearsal exposed and
  fixed `install-lite.sh` omitting `nftables`, without which `archy-net` apps
  cannot start. The regression and clean end-to-end rerun passed.
- [x] Independently verify that an unavailable catalogue cannot remove,
  replace or prevent use of the six already-installed apps during migration.
  The actual-node offline migration retained all six exact application/runtime
  fingerprints with no catalogue or external network available.

**Status: unqualified pending authenticated distribution.** Local application
installation has passed, but new App Store support still requires release-root
catalogue authority, immutable cosign-verified image delivery and an actual
fresh install through that authenticated route. Existing-node migration has its
own passing preservation/reconciliation proof; neither result substitutes for
the others.

### 4. Obtain approval of the exact UI candidate

**Where:** PR55, its stacked prerequisites and the existing review pack.

- [x] Supply the exact build/URL, setup, test steps and expected results for
  every named screen. Retain the existing captures; add integrated evidence
  for flows that were previously covered only by synthetic RPC. The exact
  35/36-patch pair passed the isolated embedded-app and fresh-signing browser
  checks on 13 November; safe captures and fixture limitations are in the pack.
- [ ] Obtain and record explicit Archipelago maintainer approval of the
  reviewed revision, including PR53/PR54 UI work, before accepting a PR into
  core Archipelago. Refresh the pack and approval after material UI changes.

**Maintainer must review and approve UI work on Settings, Storage & selling,
Sales & customers/refund recording, App Store, linked-signer login, Fresh
authorisation and embedded Wildbloom/Spry/KithMoot node screens before any PR
is accepted into core Archipelago or final core approval. ZAT pending.**

Automated checks and general instructions to proceed do not satisfy this gate.
The owner clarified on 13 November that it does not block the ForgeSworn PR
chain, testing or exact-image publication. Review can proceed alongside that
engineering once its exact candidate is ready.

### 5. Perform one controlled live cutover and verify existing users

**Where:** the single owner node, then the existing desktop, Android and web clients.

- [ ] After recovery/migration qualification and applicable approvals, agree
  the maintenance window and refresh live inventory, health, images and mounts.
  Stop if the live state differs materially from the qualified baseline.
- [ ] Take a fresh coherent recovery set using the rehearsed procedure. Keep
  its encrypted off-host copy on the Mac and verify its recovery evidence
  before activation. Preserve earlier retained recovery copies.
- [ ] Apply only the qualified pair/runtime through the reviewed procedure.
  Preserve keys, CA/SSH identity, credentials, firewall/ingress and timer choices.
- [ ] Verify all six actual apps: Fedimint, Wildbloom, Wildbloom Node,
  File Browser, Spry and KithMoot Node. Check old files, identities, login,
  pairing, room IDs/history and new message delivery without data recreation.
- [ ] Keep desktop, Android and web connected to the same existing rooms for
  client acceptance. Verify TURN/TLS, certificate handling and private
  dashboard/signer restrictions; record physical evidence separately from CI.
- [ ] If verification fails, use the tested recovery path appropriate to
  whether beta has written new state. Do not automatically restore stale data.

**Done when:** exact deployed bytes, service health, retained data and actual
client behaviour are recorded, with no unresolved loss or access regression.

### 6. Close delivery and clean up

**Where:** PR/release records, beta worktree and task-owned test resources.

- [ ] Complete the approved PR/release chain and document the supported
  existing-node update procedure and any still-unqualified new-install scope.
- [ ] Record final deployment identity, validation, recovery locations and
  remaining physical/maintainer acceptance honestly.
- [ ] Stop task-owned fixtures and remove task-owned scratch. Remove the beta
  worktree only after its work is merged, clean and fully pushed. Preserve
  named release evidence and encrypted recovery copies.

## Next action

Complete the ForgeSworn PR53–PR55 chain and publish the exact public images
through its normal `main` workflows. The owner has authorised that work and
clarified that it is not a core Archipelago merge. Goal 3 remains unqualified
at authenticated distribution: the public catalogue signature is invalid, all
four entries are missing, and beta requires immutable cosign-verified images.
After publication, the authorised key holders must cosign the image digests and
sign the compatible catalogue with the release root; KithMoot's private-image
route still needs an explicit decision. Then rerun the unchanged verifier and
install/start/check each app through that route on an isolated fresh node. The
separate local four-app installation and real NIP-46 signer rehearsals passed,
as did 20 current room/clipboard browser checks; do not mislabel them as
signed-registry, human-device or embedded acceptance. The owner can separately
pass the existing exact UI review pack to the maintainer for ZAT before any
core Archipelago PR acceptance. No live backup, restart, cutover or maintainer
contact is authorised by this clarification.
