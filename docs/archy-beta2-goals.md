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
| Actual-node restore rehearsal | A disposable Linux environment with network access disabled before importing live identities or wallet data. Select a resource-suitable environment before starting; none is currently reserved. |
| Maintainer review | [Named-screen review pack](reviews/archy-beta2-20261112/README.md). The owner passes it on; do not contact the maintainer without authorisation. |
| Live cutover | Only `demo.forgesworn.dev` (`95.216.164.146`), after the gates below. No other node is in scope. |

Use one chat to execute the upgrade. The other chat, “Check Archy beta and
contributions”, completed a status/adoption check and is not assigned a second
deployment. If execution moves to another chat, hand over this document,
branch, current revision and active commands first. Do not repeat completed
builds or backups merely because a new window opens.

## Starting position

- PR55 was rechecked on 13 November: draft, no recorded maintainer approval,
  code/evidence baseline `298d7ab`. It is stacked on PR54 and PR53; their
  outstanding acceptance gates still apply.
- Backend/frontend CI, the fresh-host fixture and the generated rootless
  Podman migration rehearsal pass. The latter uses published alpha p3 and
  generated applications; it does not qualify our private alpha or real apps.
- The 2.43 GB encrypted online node archive, exact private KithMoot OCI image
  and individual SQLite snapshots have passed the documented readback checks.
  Ten SQLite snapshots also passed Linux ownership/mode and integrity checks.
  A complete node restore and coherent cutover snapshot remain unqualified.
- Last live verification was 12 November, after backup: alpha
  `1.9.1-alpha-dev`, manager/nginx healthy and six running containers with
  unchanged IDs, images, mounts and start times. Refresh this before live work;
  this document is not a new live health check.
- The exact old private alpha and beta candidate artefacts remain in the
  worktree caches named in the evidence document. CI downloads have limited
  retention; preserve the verified local copies and do not substitute a newer
  unreviewed binary if an artefact expires.

## Goals, in execution order

### 1. Prove recovery of the actual node

**Where:** private recovery directory and an isolated disposable Linux host.

- [ ] Select the restore environment and check disk/RAM capacity. Keep its
  network disabled before importing real node identities, wallets or images.
- [ ] Restore the existing recovery material into a separate destination;
  verify owners, subuid/subgid mapping, modes, ACLs, xattrs, keys, app data,
  volume bindings and the exact installed private image. Import and inspect
  the OCI image; a valid archive alone does not prove runtime recovery.
- [ ] Check real application storage, including Fedimint's storage engine,
  KithMoot room/history state and Wildbloom files/receipts. Record exact passes
  and failures. Do not run a restored wallet online or initiate payments.
- [ ] Prepare and rehearse a bounded, coherent snapshot procedure that accounts
  for manager/app writers, rootless health-check timers and the root NPM bridge.
  It must recover automatically from interruption and restore prior service
  choices. The existing online copy cannot establish cross-application consistency.

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

- [ ] Implement/review an operator migration procedure for this derivative.
  Neither the old alpha updater nor the fresh installer is the migration path.
- [ ] Promote the exact backend, frontend and runtime together. Retain all six
  installed recipes, exact images, Quadlets, bind/anonymous volumes and
  running/stopped choices across beta bootstrap and a second manager restart.
- [ ] Cover lifecycle locks, maintenance drain, interrupted promotion and
  persistent startup refusal for an incomplete pair. Test recovery before
  candidate startup and recovery after candidate state changes separately.
- [ ] Exercise the procedure against the exact private alpha executable and
  actual restored configuration. Keep private evidence out of public CI.
- [ ] Account for beta's encrypted-secret conversion and matching key. Do not
  promise old-alpha rollback after incompatible beta writes, or restore stale
  wallet/application data merely to undo a code change.

**Done when:** the procedure and its failure/recovery paths pass on the actual
isolated baseline, with a recorded source revision, artefact hashes and evidence
for all six apps. Generated fixture passes alone do not close this goal.

### 3. Resolve the authenticated catalogue contract

**Where:** beta integration and the [catalogue reproduction report](reviews/archy-beta2-20261112/catalogue-verification.md).

- [ ] Recheck the upstream catalogue when resuming this work. The 12 November
  copy failed the unchanged release-root verifier and omitted the four node
  integration entries; this is a dated observation, not a permanent claim.
- [ ] Establish a supported authenticated distribution route for new Spry,
  Wildbloom, Wildbloom Node and KithMoot Node installs. Prepare any upstream
  report for the owner to share; do not bypass signatures or invent OTA authority.
- [ ] Independently verify that an unavailable catalogue cannot remove,
  replace or prevent use of the six already-installed apps during migration.

**Done when:** new-install support has verified catalogue authority and real
installation evidence. If that remains unresolved, keep it explicitly
unqualified. Existing-node migration requires its own preservation/reconciliation
proof; an upstream catalogue fix is not a substitute for that proof.

### 4. Obtain approval of the exact UI candidate

**Where:** PR55, its stacked prerequisites and the existing review pack.

- [ ] Supply the exact build/URL, setup, test steps and expected results for
  every named screen. Retain the existing captures; add integrated evidence
  for flows that were previously covered only by synthetic RPC.
- [ ] Obtain and record explicit Archipelago maintainer approval of the
  reviewed revision, including unresolved PR53/PR54 UI work. Refresh the pack
  and approval after material UI changes.

**Maintainer must review and approve UI work on Settings, Storage & selling,
Sales & customers/refund recording, App Store, linked-signer login, Fresh
authorisation and embedded Wildbloom/Spry/KithMoot node screens before merging
or approval. ZAT pending.**

Automated checks and general instructions to proceed do not satisfy this gate.
The review can proceed alongside engineering once its exact candidate is ready.

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

Start goal 1 by selecting the isolated Linux restore environment and checking
its capacity. Use the existing encrypted archive for a private restore rehearsal;
do not start another live archive transfer or restart the node just to resume.
Then qualify the migration against that restored baseline. The active upgrade
chat owns this sequence; the other status chat needs only this plan and PR55.
