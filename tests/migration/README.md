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
