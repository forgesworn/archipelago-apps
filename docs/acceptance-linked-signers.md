# Linked signers acceptance

Acceptance for NIP-46 linked identities (`upstream/patches/0003` to `0005`, with
`0002`) on the lite test node used for wave 1. Each check goes
through the dashboard's JSON-RPC on the node: `scripts/link-signer.sh` links a
signer, and `scripts/acceptance.sh` with `SIGN_AS` uploads to Wildbloom's
Blossom server with an event the linked signer signed.

## Run 1: 3 October 2026

### Pins

- Archipelago `v1.8.22-alpha`, archy `6d5f3ffb850bfd3dcd396bac986ba770935d1daa`,
  with `upstream/patches` applied (backend patch level 4), built
  locally for linux/amd64 on Debian 13 and staged by hand.
- `wildbloom-node` and `wildbloom` as in wave 1.
- Signers: `nak bunker` with a throwaway key; My Signet Lite
  (`lite.mysignet.app`) with a throwaway identity, driven in a browser and
  approved on its screen; Heartwood in WiFi-standalone mode on a LilyGo
  T-Display.

### Baseline

- Identities written before the patch load unchanged: the node identity
  reports `origin: seed`, the generated one `origin: generated`.
- `scripts/acceptance.sh` passes as in wave 1.

### nak

- Linked over `bunker://` in 3 s; `identity.list` reports `origin: linked`.
- The unit for `wildbloom-node` re-renders with the new key in
  `WILDBLOOM_ALLOW_PUBKEYS`; the running container picks it up after
  **Restart** (`package.restart`).
- `SIGN_AS="nak test" scripts/acceptance.sh` passes: the kind 24242
  authorisation is signed by the nak key, the upload is accepted and the fetch
  by hash matches.
- Signer stopped: a sign fails with `linked signer is offline (no reply from
  …)` in about 10 s, including when the signer had answered moments before.
- Signer restarted without its client list: the request is refused. Restarted
  with the original link's secret: the next request re-pairs and signs.

### Signet Lite

- `bunker://`: the link challenge (kind 27235) and the upload (kind 24242) each
  raised one approval screen; approved, the upload passed.
- A second link of the same key is refused (`key already belongs to identity`).
- `identity.export-keys` on a linked identity returns the identity's own DID
  key and public keys only: no Nostr secret, bunker secret or pairing key.
- Deleting the linked identity works; the key can then be linked again.
- `nostrconnect://`: the node's link pasted into Signet Lite, "Connect"
  approved, then the challenge; the upload passed as above.
- Signet Lite accepts a `bunker://` link once, so a retry needs a fresh link.

### Heartwood

- Linked over `bunker://` with two button presses (the connection, then the
  challenge).
- The first build failed every sign with "offline" at 5 s although the
  Heartwood's reply reached the node in 0.5 s: the node read replies only
  after every relay in the link had acknowledged the request, and one never
  connected. Fixed in `0004`: the first reply wins and the request no longer
  waits on slow relays.
- The Heartwood's `bunker://` link lists four relays but it replies on the
  first only, so it was linked with that relay alone
  (`relay=wss://relay.trotters.cc`).
- After **Restart** of `wildbloom-node`,
  `SIGN_AS="Heartwood" scripts/acceptance.sh` passes with one button press
  for the kind 24242 authorisation.
- Unplugged: a sign fails with `linked signer is offline` in 5 s.
- Plugged back in: the next sign raises an approval on the device and
  succeeds, with no re-link.
- An approval left on the device for 30 s comes back as `linked signer sent
  a bad response: … failed: timeout`, the Heartwood's own reply.
