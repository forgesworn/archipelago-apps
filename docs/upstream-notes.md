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

Our backend workflow runs both crates' tests with plain `cargo test` (default
features). Archy's `.github/workflows/ci.yml` does the same
(`cargo test --all-features`), and on a hosted Ubuntu runner that fails five
install and manifest-file tests in `container::prod_orchestrator`. They create
paths under `/var/lib/archipelago` and report that host-operation tests require
`scripts/test-backend-isolated.sh`. Our plain run skips those five, and a
second step runs only them through archy's harness, which gives them a private
`/var/lib/archipelago`:

- `install_applies_data_uid_chown_before_create`
- `install_resolves_derived_and_secret_env_before_create`
- `install_writes_manifest_generated_files_before_create`
- `manifest_generated_files_can_overwrite_when_declared`
- `manifest_generated_files_do_not_overwrite_by_default`

We do not run the whole suite through the harness because some tests read the
repository's real `apps/*/manifest.yml` files. They find them at runtime through
`CARGO_MANIFEST_DIR`, which `cargo test` sets but the harness does not, since it
runs the test binary directly. Its working directory is `core`, so the relative
`apps` fallback finds nothing either. Under the harness these six tests in the
`archipelago` crate fail, although they pass under plain `cargo test`:

- `api::rpc::package::dependencies::tests::manifest_declared_archival_bitcoin_covers_a_new_app_without_a_code_change`
- `api::rpc::package::dependencies::tests::mempool_api_is_directly_installable_and_covered_by_the_archival_gate`
- `api::rpc::package::runtime::tests::runtime_host_ports_are_manifest_derived_for_public_apps`
- `appgate::identity::tests::real_manifests_classify_into_both_sets`
- `appgate::identity::tests::relay_port_list_respects_local_and_gated_declarations`
- `appgate::identity::tests::reproduced_open_ports_are_now_gated`

The lookups are `manifest_apps_dirs` in `core/archipelago/src/api/rpc/package/runtime.rs`
(~line 1811) and `apps_dirs` in `core/archipelago/src/appgate/identity.rs`
(~line 115). The `lan_address` tests in `archipelago-container` behave the same
way through `manifest_apps_dirs` in `core/container/src/podman_client.rs`
(~line 989). These are production lookups, so a compile-time `env!` would be
the wrong fix. In the harness, `--setenv=CARGO_MANIFEST_DIR=$REPO/core/<package>`
would cover both crates. `--setenv=ARCHIPELAGO_APPS_DIR=$REPO/apps` would also
work for the `archipelago` crate, whose two lookups check that variable first.

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

## Boot reconcile on a node without the BTCPay stack (archy `6d5f3ff`)

On a fresh node that has never installed BTCPay, every boot reconcile pass
(every 30 seconds) logs three `ERROR … reconcile failed` lines and ends with
`reconcile pass completed with failures ok=59 failed=3`:

```
reconcile failed app_id=btcpay-server error=resolving secret_env for btcpay-server
from /var/lib/archipelago/secrets: Invalid manifest: required secret
'btcpay-db-password' is missing …
```

The same happens for `archy-btcpay-db` and `archy-nbxplorer`. Nothing is
created; the containers stay absent, as intended. The noise comes from the
order of operations in `ensure_running_with_mode`
(`core/archipelago/src/container/prod_orchestrator.rs`, ~line 2264). It calls
`ensure_app_secrets` and `resolve_dynamic_env`, which resolves `secret_env`,
before it looks for the container. The `ExistingOnly` rule that leaves an
absent, non-baseline app alone (~line 2735) is only reached afterwards. A
missing secret for an app that is not installed is therefore reported as a
reconcile failure. Checking for an absent container in `ExistingOnly` mode
before resolving secrets would make a clean node report `failed=0`, and real
failures easier to spot.

## Renaming a node replaces the CA-issued certificate (archy `6d5f3ff`)

`setup-node-ca.sh` issues the leaf certificate from the node's own CA, with
every global address as a SAN, so one installed CA covers the dashboard and
every app port. A later `server.set-name` calls `regenerate_tls_cert`
(`core/archipelago/src/api/rpc/system/handlers.rs`, ~line 845). Through
`TlsMaterial::stage_validate_and_swap` (~line 702) that mints a **self-signed**
leaf whose SAN is only `DNS:<name>`, `DNS:<name>.local`, `DNS:localhost` and
`IP:127.0.0.1`. After a rename, the node therefore serves a certificate that
the installed CA does not vouch for, and that does not name the node's IP
addresses. Cross-origin requests to `https://<ip>:<app-port>` then fail until
someone runs `system.node-ca.generate` (Settings → Node certificate), which
re-runs `setup-node-ca.sh`. Having the rename path reissue through
`setup-node-ca.sh` whenever a node CA exists would keep the two producers in
step.

## Sideloaded manifests live inside the frontend payload (archy `6d5f3ff`)

An app that is not in a registry catalog can be installed by placing its
manifest under `/opt/archipelago/web-ui/archipelago-runtime/apps/<id>/`. On
every start, `run_runtime_assets` (`core/archipelago/src/bootstrap.rs`, ~line
384) replaces `/opt/archipelago/apps` with that directory, and the orchestrator
loads manifests only afterwards (`core/archipelago/src/main.rs`, ~lines 261 and
299). Writing to `/opt/archipelago/apps` directly does not survive a restart.

The runtime directory is part of the frontend archive. An OTA frontend update
swaps `/opt/archipelago/web-ui` for the new archive's contents
(`core/archipelago/src/update.rs`, ~lines 1700–1811), and the next start then
replaces `/opt/archipelago/apps` from the new payload. A sideloaded manifest
would therefore disappear after an update, leaving an installed app with no
manifest for the orchestrator to manage. A separate local manifests directory,
merged at load time like the registry overlay, would give developers and
operators a sideload path that outlives updates.

## The test RPC helper exposes the password in argv (archy `6d5f3ff`)

`rpc_login` in `tests/lifecycle/lib/rpc.bash` builds the `auth.login` body by
splicing `$ARCHY_PASSWORD` into a JSON string and passes it to curl with
`--data-raw`. The password is therefore in curl's argument list, readable by any
local user through `ps` or `/proc/<pid>/cmdline` while the request runs. A
password containing `"` or `\` also produces invalid JSON, so the login fails.
Building the body with jq from stdin and sending it on curl's stdin avoids both:

```bash
printf '%s' "$ARCHY_PASSWORD" \
  | jq -Rsc '{jsonrpc:"2.0",method:"auth.login",params:{password:.},id:1}' \
  | curl -sk -D "$headers" -X POST "${ARCHY_BASE_URL}/rpc/v1" \
      -H 'Content-Type: application/json' --data-binary @-
```

(`jq -n --arg p "$ARCHY_PASSWORD"` fixes the escaping but moves the password
into jq's argument list instead.) Our scripts use this form in
`scripts/lib/archy-login.bash` and keep the helper's session-file format, so
`rpc_call` works unchanged afterwards.
