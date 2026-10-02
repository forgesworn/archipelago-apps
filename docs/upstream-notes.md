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

## Running the backend tests in CI (archy `6d5f3ff`)

Our backend workflow runs the `archipelago` crate's unit tests through archy's
own harness, `scripts/test-backend-isolated.sh`, which gives each run a private
`/var/lib/archipelago`. The `archipelago-container` crate runs under plain
`cargo test`: it has no host-operation tests, and two of its `lan_address`
tests find `apps/` through `CARGO_MANIFEST_DIR`, which only `cargo test` sets.
Run from the harness's `core` working directory, they find no manifests. A plain `cargo test` on a hosted Ubuntu runner, which is
what archy's `.github/workflows/ci.yml` runs (`cargo test --all-features`), fails
five install and manifest-file tests in `container::prod_orchestrator`. Those tests
create paths under `/var/lib/archipelago` and report that host-operation tests
require the isolated harness.

Two tests are skipped in our workflow. Neither touches the code our patch
changes.

- `container::quadlet::tests::actual_quadlet_generator_stops_before_forced_removal`
  runs the host's real quadlet generator. Ubuntu 24.04 ships Podman 4.9, whose
  generator rejects the `StopTimeout` key. Archipelago targets Debian 13 with
  Podman 5, where the key is supported, so the test is correct for its target
  and simply needs a newer Podman than the runner has.
- `container::prod_orchestrator::tests::reconcile_wallet_start_precedes_unrelated_failed_image_pull`
  starts `lnd` through `reconcile_all`. LND's pre-start hook reads
  `bitcoin-rpc-password` from the orchestrator's `secrets_dir` and writes
  `lnd.conf` under `lnd_paths`. The test does not redirect either, so both
  resolve to `/var/lib/archipelago/...`. The secret is absent on a CI host and
  in the harness's empty private `/var/lib/archipelago`, so `lnd` is never
  started and the test's `start_container:lnd` lookup finds nothing. Setting
  `set_secrets_dir` (with a seeded password) and `set_lnd_paths` to temporary
  directories, as the test around line 7681 does, would likely make it
  self-contained.
