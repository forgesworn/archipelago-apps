# Private KithMoot Node candidate

This is the Archy operator app for the KithMoot room node. It is deliberately
outside `apps/`: the public catalogue and automatic image publisher do not ship
it. Shelter remains a private input. No public signed node release is claimed.

The controller sets up and runs the existing node supervisor as uid/gid 1000.
It signs no room grants and stores no room keys. Archy owns its HTTPS/TURN TLS
front and certificate keys; the app has no certificate mount or root commands.
The operator UI uses Archy's app gate, then a body-bound NIP-98 proof from a
declared node identity. Its controls token stays in browser memory. Explicit use extends its 30-minute
inactivity timeout, up to an eight-hour absolute limit. Status polling alone
does not keep it alive. Signing out revokes that token without stopping rooms
or calls. TURN logins remain limited to five minutes.
Changing the host's declared identities requires recreating the container so
its derived identity list is current. The outer app gate still checks host
sessions on each request. Guest room admission remains in the keeper's app.

Use a rented server or an Archy hosted away from home. Setup requires that
confirmation and the supervisor rejects private/local relay addresses. This
does not prove that a public address belongs to a data centre.

## Build without publishing

Use Node 24 and an already verified private Linux node bundle with its complete
`release.json` inventory. The preparation script accepts ARM64 or x64 inputs;
ARM64 has passed local fixture checks and Linux x64 is installed on the
authorised demo host. See the [live review pack](../../docs/kithmoot-node-demo-review.md).
Build for the bundle's architecture. Do not mix native architectures.

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
uses its declared owned bind volume. The manifest uses Podman-compatible
`256m`; patched Quadlet generation also preserves the bounded `/tmp` mount. No browser form accepts paths, commands,
hostnames or binaries. Resource limits are bounded choices.

Pausing preserves saved rooms and data. Closing rooms and removing devices
happen in KithMoot. **Delete everything** checks the supervisor's durable empty
room/device/request state and freezes new admission, then hands back to Archy's
normal **Delete app and data** action. The host repeats that check through the controller's owned, private Unix
socket before teardown. An unused or partially initialised node can also prepare
deletion. Its durable freeze survives a controller/container restart; unknown
runtime data refuses deletion. A paused node with saved runtime state must be
started so the supervisor can check and close its rooms. A busy node refuses deletion; cancelling the preparation unfreezes it.
The controller never attempts to sign keeper closures or delete files itself.

The host app-gate override applies to gate-fronted ports. Forcing that override
on for the native TURN mapping closes that mapping, since TURN cannot answer
an HTTP login challenge. Leave the manifest's native TURN declaration in place.

## Private dashboard observations

The signed status API now powers Overview, Connections, Usage, Settings and
Diagnostics. It exposes only a fixed summary: aggregate room/access/operation
counts, four service observations, the nine allowlisted local doctor checks,
saved limits, local certificate expiry, container resources, filesystem free
space, Shelter's encrypted-message storage total and private aggregate relay metrics. Detailed supervisor or
socket replies, keys, identities, room identifiers and participant addresses
are never forwarded. Support copying is explicit and sends nothing itself.

`pending` means unfinished supervisor operations, not waiting guests. Access
counts can include offline devices and count one device in multiple rooms.
Local STUN responses and a trusted local TLS connection do not qualify outside
media calls. Outside-network tests, historical charts and client video-quality
measurements are not collected by this version. UDP and TCP/TLS allocation
gauges, payload totals, rates, drops and stream errors come from the existing
paired-authority Spry status request. No room grant is created for observation.
Payload includes both directions and queued stream output, excluding protocol
headers; it is not verified delivery or billable network usage. TCP and TLS
share one stream bucket. Errors are relay stream failures, not failed calls
or failures in the host TLS terminator. Stale/malformed samples are unknown;
rates need two increasing samples and reset after restart or outage.

CPU and memory use the private cgroup v2 root, only when the process reports
`0::/`. Other cgroup layouts and platforms show unavailable counters. CPU is a
delta between observations, with 100% representing one core. Filesystem reserve
uses available bytes on the data volume; Shelter's owned private socket returns
only its storage total and lease state. Missing data is unknown, not zero.
The first CPU sample needs another observation. Backend-specific version/uptime
are shown as not reported/unavailable when the existing protocol lacks them.

Observations are cached for 10 seconds, supervisor status for two seconds and
doctor checks for 15 seconds. Concurrent tabs share one in-flight status probe.
A stopped/replaced supervisor cannot reuse an in-flight predecessor's readiness.
The fixed status command is limited to eight seconds, doctor to 45 seconds and
the new socket/TLS observations to two seconds each. Backend failure leaves the
configured limits and recovery controls visible. Polling does not extend sign-in.

Settings edits the same four bounded limits after an explicit pause. Saving
or restoring previous limits keeps the node paused; Start on Overview applies
them. A stale configuration revision, active child, deletion freeze, unfinished
operation, unsupported ledger schema, unsafe storage or insufficient capacity
refuses the change. Only limits change, never authority, paths or keys. The
owner-only atomic backup precedes the configuration commit. Manual restoration
revalidates present usage and never rewinds room data. Pause ends calls and
preserves saved data; there is no drain action. Destructive deletion retains
the existing supervisor freeze and host deletion handshake.

See the [5 November dashboard review pack](../../docs/kithmoot-node-dashboard-review.md)
for exact source, component evidence, deliberate style choices and pending gates.

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
pairing hand-off, delete-everything, Overview, Connections, Usage, Settings and
Diagnostics screens before merging or
approval. ZAT pending.
