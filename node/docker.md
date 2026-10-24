# Archipelago with Docker apps

This recipe runs the real Rust Archipelago controller and seeded FIPS service
on a fresh **Debian 13 amd64 Linux host**, with Spry managed by Archipelago's
existing Docker runtime. The controller uses systemd; it is not a Docker
Desktop application. On Windows or macOS, use a Debian virtual machine.
Existing ForgeSworn Archipelago bundle owners install Spry from their dashboard
instead; they do not run this host installer.

1. On the machine with this checkout, GitHub CLI, Git and coreutils, assemble
   the matching released bundle:

   ```sh
   node/prepare-docker-bundle.sh docker-bundle
   ```

2. Copy `docker-bundle` onto the fresh Debian host. From that directory, run:

   ```sh
   sudo bash install-lite.sh . docker
   ```

3. Complete Archipelago's normal onboarding, create an owner identity, then
   **install Spry → Pair with KithMoot → Call**. Each person pairs their own
   home node once. The node activates its existing mesh using its seeded
   identity; a third participant's VPS is unnecessary.

The installer verifies the matching backend/frontend release inputs and the
pinned FIPS 0.4.1 Debian package. It keeps an installed Docker engine, or installs
Debian's engine when absent. Archipelago's service account receives Docker
access and the existing host privileges described in the [lite-node guide](README.md).
Spry itself receives no extra capabilities. This is a dedicated-node install:
it configures nginx, host certificates, SSH keys and the SSH-only firewall
described in that guide. Reach onboarding through its SSH tunnel and trust the
node CA as documented there. It refuses an existing Archipelago data directory
rather than migrating its containers between runtimes.

The Bitcoin stack is omitted. Catalogue apps which require rootless Podman
network modes remain unsupported by the existing Docker runtime; Spry uses
host networking. This recipe has not yet passed a complete fresh-host install
or physical home-network call. The separate Spry/FIPS NAT and browser receipts
do not establish this host-install gate.
