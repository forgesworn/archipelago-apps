# Spry pairing delivery — 24 October 2026

Update, 25 October: catalogue **p4** adds the missing Spry App Store listing,
refreshes the dashboard's catalogue cache after a bundle update and corrects
the peer DNS endpoint to Archipelago's configured `127.0.0.1:5354`.
Backend p2 and the Spry image remain unchanged. The p3 release receipt below
remains the original delivery record.

For an existing ForgeSworn Archipelago bundle, install the matching 1.9.1
backend p2 and catalogue p4 update using the
[existing-node update command](existing-node-update.md) on a compatible
installed 1.9.1 node. Then:

1. Open **App Store** beside **My Apps**, search **Spry** and choose **Install**.
2. Open it, choose **Pair with KithMoot** and approve the pairing.
3. Use KithMoot's normal Call button for a conversation or group.

Each private home caller pairs their own node once. KithMoot shares scoped
relay access inside the encrypted conversation automatically. Both callers
must be able to reach their own paired nodes; another participant's browser
and VPS can be offline. Spry uses Archipelago's existing owner identity,
certificates and FIPS mesh. No TURN password or router port mapping is entered
in KithMoot.

Spry remains standalone Rust libraries. Archipelago supplies host adapters;
other ForgeSworn applications can use the same packet, authority, signed-link
and optional service libraries. See the [package guide](../apps/spry/README.md).

## Published components

The [public release receipt](evidence/spry-delivery-public-20261024.json)
records the anonymously downloaded backend, catalogue and both image
architectures, their hashes and the qualified source.

KithMoot web and Android 0.6.111 (code 134) are published. Android uses the
existing production signing certificate and update lineage. The
[KithMoot publication record](https://github.com/forgesworn/kithmoot/blob/main/docs/android-production-publication.md)
records GitHub downloads, both website hosts and the independently verified
Zapstore listing. Installing through the device's Zapstore client remains a
separate check.

## What has been exercised

The [fresh-host receipt](evidence/spry-docker-host-20261024.json) covers a real
Rust controller on a disposable Debian 13 amd64 host, its existing Docker
runtime, seeded FIPS, HTTPS owner approval, foreign-origin and replay refusal,
Stop/Start/Restart and exact container/firewall uninstall. The suite also
passed 85 container-library tests, 2,256 main controller tests and seven
isolated host tests. The upstream ignored and filtered cases are recorded in
the receipt.

The core's [creator-offline browser receipt](https://github.com/forgesworn/spry-turn/blob/main/docs/evidence/spry-creator-offline-browser-20261024.json)
starts a fresh call between two reloaded clients after the creator browser and
node stop, with fresh decoded generated media after 330 seconds. The separate
[two-NAT FIPS receipt](https://github.com/forgesworn/spry-turn/blob/main/docs/evidence/spry-fips-two-nats-20261024.json)
checks packet forwarding through real FIPS across two simulated home NATs.
These are controlled fixtures, not physical broadband acceptance.

For a new Docker installation, use the [Debian host recipe](../node/docker.md).
Windows/macOS Docker Desktop is unqualified; the supported host recipe uses a
Debian 13 amd64 machine or virtual machine. The installer is for a dedicated
fresh node and configures host services.

The remaining owner check is two independent home nodes making a fresh
audio/video call while the third participant's node is off. Sustained
physical no-Play GrapheneOS media, echo and volume acceptance remain separate.
