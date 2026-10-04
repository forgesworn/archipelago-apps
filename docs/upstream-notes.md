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

The `{{NODE_IDENTITY_PUBKEYS}}` placeholder in
`upstream/patches/0001-feat-add-NODE_IDENTITY_PUBKEYS-derived-env-placeholder.patch`
does not depend on this function, nor on the node's discovery key at all. It
reads the Nostr keys stored with the identities in `identities/`, the records
`identity.list` returns, and keeps only those `NostrIdentityPicker.vue` offers
to apps.

## App signing uses identities, not the discovery key (archy `6d5f3ff`)

An app's NIP-07 requests go through the dashboard bridge, which signs with
`identity.nostr-sign` and the identity the user picked
(`neode-ui/src/views/appSession/useNostrBridge.ts:154`). The picker hides the
node identity (`neode-ui/src/components/NostrIdentityPicker.vue:156-162`). The
node's discovery key, which `node.nostr-pubkey` reports, is therefore never what
signs an app's events once an identity is picked. Our first placeholder,
`{{NODE_NOSTR_PUBKEY}}`, injected that discovery key, and on a real node no
upload signed through the bridge could match it. The patch now injects every
identity the picker offers.

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

An app that is not in a registry catalogue can be installed by placing its
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

## `post_install` hooks are not re-applied when a container is recreated (archy `6d5f3ff`)

`hooks::run_post_install` (`core/archipelago/src/container/hooks.rs`, ~line
62) has one caller, `install_fresh`
(`core/archipelago/src/container/prod_orchestrator.rs`, ~line 2908), and its
doc comment says as much: the hooks run only when the install path creates a
fresh container. The other ways a container comes back do not call it:

- The health monitor's `restart_container`
  (`core/archipelago/src/health_monitor.rs`, ~line 731, called at ~line 1130)
  runs `podman restart` (or `start`) on the container directly.
- The orchestrator's `restart` (`prod_orchestrator.rs`, ~line 4804) calls
  `quadlet::restart_service` (`core/archipelago/src/container/quadlet.rs`,
  ~line 784) and then `run_post_start_hooks` (~line 2951), which handles a few
  built-in apps by id.

Quadlet renders `podman run … --rm` under `Restart=always` (`quadlet.rs`,
~lines 76–100 and 542), and the unit on our node also ran with `--replace`, so
a stopped container is deleted and
systemd starts a new one from the image. Anything a `post_install` step wrote
into the container is gone after that. We saw this on a node: the health
monitor logged `Auto-restarting unhealthy container: wildbloom … attempt
3/10`, and afterwards the `/nostr-provider.js` placed by `copy_from_host` was
missing, so the app had no `window.nostr`.

IndeeHub avoids the problem by baking the provider into its image and keeping
the hooks as an idempotent refresh (`apps/indeedhub/manifest.yml`, ~lines
60–75). We now do the same for Wildbloom. Running `run_post_install` (or a
subset of idempotent steps such as `copy_from_host`) after a quadlet restart or
recreation would make the hooks dependable for apps that do not bake.

## Gated sideloaded apps get an `http://` frame on an HTTPS dashboard (archy `6d5f3ff`)

The dashboard decides whether an app frame uses https or http from the signed
catalogue only. `portAuth` (`neode-ui/src/views/discover/curatedApps.ts`, ~line
143) reads the port's `auth` from the catalogue's embedded manifests and
returns `null` for an app the catalogue does not list.
`appPortIsGateFronted` (`neode-ui/src/views/appSession/appSessionConfig.ts`,
~line 86) is therefore false for such an app (apart from the
`PRE_CATALOG_GATED_PORTS` entry for `archipelago-source`), and `resolveAppUrl`
(~line 170) leaves the backend's `http://` runtime URL as it is.

A sideloaded app whose manifest declares `auth: gated` is still fronted by the
app gate, which serves TLS on that port. The backend knows this:
`build_port_map` (`core/archipelago/src/appgate/identity.rs`, ~line 157)
classifies the catalogue's manifests and then the installed ones from
`/opt/archipelago/apps`. On a dashboard served over HTTPS the browser blocks the
`http://` frame as mixed content, and the app session stays on "is starting…".

Taking the port's auth from the installed manifest, for example by having the
backend report it alongside the runtime URL, would give sideloaded and
not-yet-catalogued apps the same https frame as catalogued ones.

Patches 0008 and 0009 do this. The backend reports the launch port's declared
auth as `lan-port-auth` on the app's main interface address, from the same
classification `build_port_map` uses, and the dashboard falls back to it only
when the catalogue has no answer for the app.

## A round-trip test that fails about 2 runs in 256 (archy `6d5f3ff`)

`seal_open_round_trips` (`core/archipelago/src/storage_crypto.rs`, lines
91-98) asserts `!is_plaintext_json(&sealed)` (line 95). `is_plaintext_json`
(line 81) is true when the first byte is `{` or `[`, and the first bytes of
`seal`'s output are a random nonce (the test itself slices at `sealed[12..]`).
Two of the 256 possible first bytes qualify, so about 1 run in 128 fails
whatever the code does. We saw it once in our CI, and it passed on re-run.
Checking the ciphertext after the nonce (`&sealed[12..]`), or asserting that
`sealed` differs from the plaintext, would remove the dependence on the random
byte. The negated assertion at line 113 has the same shape.

## The app NIP-07 provider requests a NIP-98 login in every app (archy `6d5f3ff`)

When the user picks an identity, the dashboard posts an `archipelago:identity`
message to the app frame (`neode-ui/src/views/appSession/useAppIdentity.ts`,
`sendIdentity`, line 43). The provider's listener for it
(`neode-ui/public/nostr-provider.js`, lines 372-382) calls `doNip98Auth`
(line 315) 1.5 seconds later unless a session token is already stored. That
function probes `/api/nostr-auth/health` on the app's origin, accepts any
`response.ok` (lines 318-320), and then asks the signer for a kind 27235 event
(line 327). The user therefore sees a second consent prompt for a login that
only apps with that endpoint can use.

The opt-out exists: a `data-no-nip98` attribute on the provider's script tag
(line 15). It has to be set by whoever injects the script, and apps that merely
copy the provider do not know to. The health probe can also pass for an app
that answers unknown paths with a catch-all page (we have not checked which
way it passed for ours). Making the login opt-in, so that an
app declares support (for example through a manifest field or the attribute's
opposite), would stop apps without the endpoint showing the extra prompt.
Checking that the health response is the expected JSON would be a smaller
step.

## Identity picker hint names the wrong place (archy `6d5f3ff`)

The empty state in `neode-ui/src/components/NostrIdentityPicker.vue` (line 50)
says "Create one in Settings → Credentials". Identities are created from the
Web5 page: `Web5.vue` (line 66) mounts `Web5Identities`, whose "Create
Identity" dialog is at `neode-ui/src/views/web5/Web5Identities.vue` (line
228). `Settings.vue` has no credentials entry, and the `credentials` route
(`neode-ui/src/router/index.ts`, line 221) is the verifiable-credentials page
under `web5/`. Pointing the hint at Web5 → Identities would send a first-time
user to the right page.

## Signing calls give up before a button-press signer can answer (archy `6d5f3ff`)

The dashboard's RPC client (`neode-ui/src/api/rpc-client.ts`, `callInner`)
defaults to a 15 s timeout and up to three attempts, and the NIP-07 bridge
(`neode-ui/src/views/appSession/useNostrBridge.ts`, ~line 154) calls
`identity.nostr-sign` with those defaults. That suits keys held on the node.
For an identity whose key is in a remote NIP-46 signer that waits for a human
tap (patches `0003`–`0005`), each retry is a fresh request, so a slow approval
could raise up to three prompts on the device, and the app sees "Request
timeout" after about 47 s. The patches de-duplicate retries on the backend (a
retry joins the request already in flight, or gets its result for 60 s), so
the device sees one prompt. A denial that lands between two retries is not
cached, so the next retry asks again. The frontend would still do better to
pass `timeout: 90000` and `maxRetries: 1` for the sign and encrypt/decrypt
calls on linked identities.

## Linking a remote signer has no dashboard UI yet (archy `6d5f3ff`)

Patches `0003`–`0005` implement Phase 3 of `docs/nostr-identity-import-plan.md`
(NIP-46 "linked" identities) in the backend only: `identity.link-nip46`
(`bunker://`) and `identity.link-nostrconnect-start` / `-finish`
(`nostrconnect://`, the "flow B" of `docs/nostr-signer-login-research.md`).
Here they are driven by `scripts/link-signer.sh`. The plan's "Add existing"
modal on `Web5Identities.vue` would be the natural home: a paste box for
`bunker://`, and a QR code for `nostrconnect://` with the finish call polled
underneath. `identity.list` already reports `origin: "linked"` and the
signer's public details, which an origin badge could use.

## New identities reach running apps only on restart (archy `6d5f3ff`)

When an identity is added, the backend re-renders the quadlet units of apps
whose manifests template `{{NODE_IDENTITY_PUBKEYS}}` (patch `0001`), but a
running container keeps the environment it started with until the app is
restarted (`package.restart`, the dashboard's Restart button). Restarting
affected apps when the rendered value changes, or noting it in the identity
screens, would save users a step.
