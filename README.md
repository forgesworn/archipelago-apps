# archipelago-apps

ForgeSworn apps packaged for [Archipelago](https://source.archipelago-foundation.org/lfg2025/archy) nodes.

Each `apps/<id>/` holds an Archipelago `manifest.yml` and the Dockerfile that
builds a pinned release of the app. Images are published to
`ghcr.io/forgesworn/<id>`. `upstream/patches/` holds changes we propose to
Archipelago itself.

| App | What it is |
|---|---|
| `wildbloom-node` | Blossom storage owned by your node identities |
| `wildbloom` | Encrypt, replicate or shard files, recover from receipts, and use your node identities to sign |
| `spry` | Pair with KithMoot once and share your node’s call relay automatically |

For existing installations, see the [Wildbloom upgrade guide](docs/wildbloom-upgrade.md).

With the matching ForgeSworn node update, install **Spry**, open it and choose
**Pair with KithMoot**. Then use the normal Call button in a conversation or
group. On private home nodes, each person pairs their own node once; a public
Spry can also serve guests without a node. See the [Spry guide](apps/spry/README.md)
for node requirements and qualification limits. Its install catalogue is
released only after the public image is available for both architectures.

The earlier `spry-turn-lab` experiment and independent transport qualification
remain documented in [Archy call services](docs/archy-call-services.md).

The browser defaults to your own node. Optional LNURLcash sales default to the
reference mint at `mint.lnurlcash.com`; Moneyer remains an explicit test/development
choice. For capacity reserved for yourself and private configuration, see
[own storage and selling](docs/wildbloom-selling.md).
Configure it in **Settings → Storage & selling** with the matching patched
dashboard/backend: see the [dashboard guide](docs/storage-selling-dashboard.md).
For a complete clean-node, operator, buyer, renewal, refund and backup exercise,
follow the [independent operator runbook](docs/wildbloom-operator-runbook.md).

The patches also let a node identity keep its key in a NIP-46 remote signer
(a hardware signer such as Heartwood, or a phone app): see
[`docs/linked-signers.md`](docs/linked-signers.md).

Validate locally: `scripts/fetch-archy.sh && scripts/apply-patches.sh && scripts/validate.sh`.

MIT licence.

`apps/wildbloom/nostr-provider.js` and `apps/spry/public/nostr-provider.js`
contain Archipelago's NIP-07 provider
(`neode-ui/public/nostr-provider.js`), vendored unchanged at the pinned
`ARCHY_REF`. Copyright (c) 2026 Dorian and the Archipelago Project
contributors, MIT licence.
