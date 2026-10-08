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

For existing installations, see the [Wildbloom upgrade guide](docs/wildbloom-upgrade.md).

The patches also let a node identity keep its key in a NIP-46 remote signer
(a hardware signer such as Heartwood, or a phone app): see
[`docs/linked-signers.md`](docs/linked-signers.md).

Validate locally: `scripts/fetch-archy.sh && scripts/apply-patches.sh && scripts/validate.sh`.

MIT licence.

`apps/wildbloom/nostr-provider.js` is Archipelago's NIP-07 provider
(`neode-ui/public/nostr-provider.js`), vendored unchanged at the pinned
`ARCHY_REF`. Copyright (c) 2026 Dorian and the Archipelago Project
contributors, MIT licence.
