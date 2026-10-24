# Update an existing ForgeSworn 1.9.1 node

Backend **p2** and catalogue **p3** are an in-place node update. The updater
supports the published ForgeSworn 1.9.1 p1/p2 backend and the existing
directory-based `web-ui` layout. Other versions or custom backend binaries
are refused; use their appropriate migration path first.

From a checkout of this repository on your computer, check the node:

```sh
ssh root@your-node 'python3 - --check' < scripts/update-node-bundle.py
```

When a brief Archipelago restart is acceptable, apply the update:

```sh
ssh root@your-node 'python3 - --apply' < scripts/update-node-bundle.py
```

Replace `root@your-node` with your existing SSH login. Use an administrator
with root access; if your SSH login uses sudo, run the downloaded script on
the node with `sudo python3 update-node-bundle.py --apply` instead. Python 3
and curl must already be installed. The updater uses the existing node CA to
verify local controller health.

The apply command downloads the two pinned releases and verifies their exact
sizes and SHA-256 hashes before stopping Archipelago. It checks the lifecycle
lock, keeps a private backup, preserves existing runtime and other app
configuration, replaces the backend and dashboard, restarts the controller
and checks health plus the promoted Spry manifest. Failed startup, health or
promotion restores the previous bundle and live app definitions. A failure
during rollback reports that manual attention is needed and names the backup.
Identity and application data under `/var/lib/archipelago` are retained.
SSH keys and host certificates are retained. The command replaces the Spry
package definition with the matching release's definition.

Backups and the successful receipt remain under
`/opt/archipelago/.forgesworn-bundle-backups/`, readable only by the
administrator. Review and retain the backup until the updated node is
accepted. Repeating the command when the expected backend, dashboard entry
and Spry manifest are present does not download or restart again.

Refresh the Archipelago dashboard after success. Then install/open Spry,
choose **Pair with KithMoot**, approve the node request and choose **Pair Spry**
in KithMoot.

The updater reports whether `fips0` is present. Spry's private node-to-node
mode also needs Archipelago's working seeded FIPS mesh. This updater replaces
the bundle; it does not install or enable FIPS, expose a public relay or
edit host firewall rules itself. Controller startup still performs
its usual runtime promotion and app reconciliation. An older lite node with
no working mesh needs that separate host setup before Spry can become ready.

The [fresh Debian Docker-host recipe](../node/docker.md) is a separate path
for a new dedicated host or VM. Use this existing-node updater for an already
installed compatible node.

Verification: fifteen generated-filesystem tests cover configuration and
identity preservation, rollback, busy locks, unexpected versions, low disk,
damaged downloads, unsafe archives and repeat application. The exact public
p3 archive passed extraction, and a compatible existing node passed the
read-only check. A production application is a separate acceptance step.
