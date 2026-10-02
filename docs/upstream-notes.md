# Upstream notes

Observations about Archipelago (archy) made while packaging apps, kept here so
they can be offered to the maintainers. Each entry names the archy commit it was
checked against.

## Node Nostr public key file name (archy `6d5f3ff`)

`read_nostr_pubkey_hex` in `core/archipelago/src/api/rpc/package/config.rs`
(~line 663) reads `identity/nostr_pub`, the file written by
`nostr_discovery::load_or_create_nostr_keys`. The seed paths in
`core/archipelago/src/api/rpc/seed_rpc.rs` (~lines 145 and 265) write the
derived key to `identity/nostr_pubkey` instead, alongside `nostr_secret`. Read
errors fall back to an empty string.

As a result, after a seed restore or seed generation the function can return
either the previous key (if an older `nostr_pub` remains) or an empty string (if
none exists). Neither matches the key the node actually signs with.

The `{{NODE_NOSTR_PUBKEY}}` placeholder in
`upstream/patches/0001-feat-add-NODE_NOSTR_PUBKEY-derived-env-placeholder.patch`
does not depend on this function. It uses `nostr_discovery::get_nostr_pubkey`,
which derives the public key from `nostr_secret`, in the same way as the
`node.nostr-pubkey` RPC.
