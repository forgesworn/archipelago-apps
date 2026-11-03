# Private KithMoot Node candidate

This is the Archy operator app for the KithMoot room node. It is deliberately
outside `apps/`: the public catalogue and automatic image publisher do not ship
it. Shelter remains a private input. No public signed node release is claimed.

The controller sets up and runs the existing node supervisor as uid/gid 1000.
It signs no room grants and stores no room keys. Archy owns its HTTPS/TURN TLS
front and certificate keys; the app has no certificate mount or root commands.
The operator UI uses Archy's app gate, then a body-bound NIP-98 proof from a
declared node identity. Its five-minute session stays in browser memory.
Changing the host's declared identities requires recreating the container so
its derived identity list is current. The outer app gate still checks host
sessions on each request. Guest room admission remains in the keeper's app.

Use a rented server or an Archy hosted away from home. Setup requires that
confirmation and the supervisor rejects private/local relay addresses. This
does not prove that a public address belongs to a data centre.

## Build without publishing

Use Node 24 and an already verified private Linux node bundle with its complete
`release.json` inventory. The preparation script accepts ARM64 or x64 inputs;
only the ARM64 candidate has been exercised locally. Build for the bundle's
architecture. Do not mix native architectures.

```sh
cd experimental/kithmoot-node
npm ci --ignore-scripts --no-audit --no-fund
npm test
npm run build
cd ../..
python3 scripts/prepare-kithmoot-node.py \
  --bundle "$node_bundle" --output .cache/kithmoot-node-private
```

The output directory is private, mode 0700. It contains the local Docker build
context, inventory receipt and `apps/kithmoot-node/manifest.yml`. It refuses an
existing output directory. No credentials belong in that context.

```sh
node_image=$(python3 -c 'import json; print(json.load(open(".cache/kithmoot-node-private/candidate.json"))["image"])')
podman build --network=none --tag "$node_image" .cache/kithmoot-node-private
```

The resulting image uses `pull_policy: never`. Privately load it into the
target's actual container runtime before installing its local manifest. It
does not belong in a public registry or catalogue. Host installation, live
certificate changes and publication require their own owner authorisation.
See the [maintainer review pack](../../docs/kithmoot-node-archy-review.md).

The patched Archy host must already have a public hostname and a current
certificate covering it and `turn.` plus that hostname. Root preflight refuses
an unsupported/custom host listener before starting the app. The host retains
private dashboard and signer routes and routes only the exact node API paths
publicly. The application cannot read the host's TLS keys.

## Ports and data

| Purpose | Port |
| --- | --- |
| Operator UI behind Archy's HTTPS app gate | 3753 |
| Supervisor, Spry HTTP, Shelter HTTP, all loopback | 3750, 3751, 3752 |
| Node TURN UDP/TCP | 34790 |
| Node TURN TLS through host TLS | 53499 |
| TURN TLS through host SNI routing | 443 |
| Node TURN UDP relay sockets | 49192–49223 |

The separate ports preserve the existing Spry app's HTTP, TURN and relay range.
The image has a read-only root, no capabilities, no privilege escalation, a
16 MiB temporary filesystem and a 256 MiB memory limit. Persistent node data
uses its declared owned bind volume. No browser form accepts paths, commands,
hostnames or binaries. Resource limits are bounded choices.

Pausing preserves saved rooms and data. Closing rooms and removing devices
happen in KithMoot. **Delete everything** checks the supervisor's durable empty
room/device/request state and freezes new admission, then hands back to Archy's
normal **Delete app and data** action. The host repeats that check before
teardown. A busy node refuses deletion; cancelling the preparation unfreezes it.
The controller never attempts to sign keeper closures or delete files itself.

The host app-gate override applies to gate-fronted ports. Forcing that override
on for the native TURN mapping closes that mapping, since TURN cannot answer
an HTTP login challenge. Leave the manifest's native TURN declaration in place.

## Verification

```sh
python3 -m unittest discover -s tests -p test_kithmoot_node.py -v
cd experimental/kithmoot-node
npm test
```

The browser component review additionally uses the existing pinned browser
tools in `tests/smoke`. It supplies a fixture signer and node adapter while
running the actual signed controller. It is not the real Archy app gate:

```sh
cd tests/smoke
npm ci --ignore-scripts --no-audit --no-fund
cd ../../experimental/kithmoot-node
E2E_KITHMOOT_NODE_UI=component-review node browser-review.mjs
```

`controller-driver.mjs` is a disposable offline Linux fixture driver. Its known
test key has authority only inside the guarded fixture. The host qualification
runs the actual production supervisor/backends, Rust TLS and nginx, including
authenticated TURN on 443. See the separate evidence receipt for its limits.

Maintainer must review and approve UI work on the Archy install, launch,
pairing hand-off, delete-everything and status screens before merging or
approval. ZAT pending.
