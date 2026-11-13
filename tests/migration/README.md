# Generated installed-node migration rehearsal

Run through `.github/workflows/beta-migration.yml` on a disposable Linux CI
runner. `scripts/test-beta-migration.sh` refuses a non-CI invocation. It never
connects to `demo.forgesworn.dev` or imports live identities, wallets or rooms.

The fixture installs the published 1.9.1-alpha backend p3/frontend p5 on a fresh
Debian 13 guest with rootless Podman. This is a representative alpha baseline,
not the live node's newer private binary. The beta pair is the exact candidate
retained by backend run 43268204623. Downloaded hashes are checked before use.
The beta CI artefact expires after 14 days; failure to download is a hard stop,
not permission to select a different unreviewed binary.

Six generated manifest-driven applications use a local BusyBox image, SQLite
records and blobs. They exercise runtime/data preservation, not real wallet,
Wildbloom, Spry or KithMoot application behaviour. The fixture includes private
and overlapping recipes, an explicitly stopped application, image-declared
anonymous volumes, a generated owner login and node/personal identities.

Checks cover:

- Preserving installed recipes in an offline candidate tree, without writing
  to either input or inventing public OTA admission. Missing recipes, indirect
  paths and overlapping/existing output destinations are refused.
- Snapshotting paused workloads and restoring into a separate directory with
  numeric ownership, modes, extended attributes, SQLite integrity and exact
  database/blob/volume/key bytes. This is crash-consistent generated-state
  evidence, not a complete live-machine restore qualification.
- Interrupting the code-pair replacement before beta starts. A persistent
  systemd guard must refuse the mixed pair; restoring only the old code must
  restore alpha startup and the existing password login.
- Starting beta through its ordinary legacy runtime bootstrap, then restarting
  it again. Existing container/image identities, mounts, Quadlets, recipes,
  files, login and identities must remain intact. A stopped app must stay stopped.

Podman's automatic container removal can delete anonymous image volumes on
exit. The fixture therefore pauses its running workloads for backup; it never
uses stop as a generic backup prerequisite. The generated stopped app is
stopped before anonymous-volume sentinels are created. The owner node's File
Browser needs explicit volume preservation before any stop/recreation.

The runner destroys its guest, temporary archives and image on success or
failure. Only bounded generated-state result/journal files are uploaded.
The code is a rehearsal, not a production updater or backup command. It does
not qualify post-beta database rollback, a maintenance window, the exact live
private build, real application behaviour, physical clients or maintainer ZAT.

## Operator snapshot tests

`test_coherent_node_snapshot.py` covers the separate operator procedure in
`scripts/coherent-node-snapshot.py`. These unit tests use generated fake units,
containers and tar programs; they do not connect to the owner node. The actual
isolated-node recovery, consistency, timeout and SIGKILL evidence is recorded
in `docs/archy-beta2-upgrade.md` and the private restore report. The production
command must only be used in an agreed maintenance window.

## Operator pair/runtime migration tests

`test_migrate_node.py` covers `scripts/migrate-node.py` and
`scripts/migration-startup-guard.py` with generated filesystems and a fake host.
It checks exact pair activation, retained Quadlets/images/mounts, candidate or
external recipe classification, two manager starts, interrupted activation,
resumption, forward repair and refusal of alpha rollback after beta startup.
These tests do not run real applications or connect to the owner node.

The operator transaction preserves observed installed units before beta starts,
keeps application containers running, stops the manager/root NPM writers, takes
the snapshot/lifecycle locks during replacement, and leaves a persistent guard
against mixed or incomplete pairs. Once candidate startup is attempted, recovery
is forward-only; it never restores stale application data or automatically
returns to alpha. Use only with the reviewed hashes and recovery evidence in
`docs/archy-beta2-upgrade.md`, during an agreed maintenance window.
