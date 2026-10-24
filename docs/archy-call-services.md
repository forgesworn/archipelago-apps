# Operator-owned call services on Archy

23 October 2026. Package experiment, owner-operated public transport
qualification and proposed discovery boundary. This is not a complete call
stack, implemented signed discovery or legal advice.

**Current qualification:** after signer-authorised lab installation, the owner
promoted this instance to invited public TURN. External UDP/TCP/trusted-TLS
data and generated browser media passed, including after certificate-renewal
dry-run/restart. The dashboard remains private; credentials are minted offline
and discovery is unfinished. See the [public candidate handover](archy-spry-public-20261023.md).
Earlier receipts describe their own snapshots; the base preparer still
produces a loopback-only lab.

The owner has chosen software and protocols: people install services on their
own Archy nodes, run and manage them themselves, and choose which services
their clients use. ForgeSworn must not hold their operating keys, issue a
global call entitlement or manage their installations. Publishing
owner-controlled package updates is distinct from exercising runtime
management; update and orchestration mechanisms must preserve that separation.

## Prepared implementation

`scripts/prepare-spry-turn.py` creates a private local build context and Archy
manifest from Spry commit `a76496bbcb60e637c0606c8da5919b5a3b2b3cf3`.
It reads committed files with Git, checks the reviewed source hashes and
copies only allowlisted source/licence files. Dirty and untracked operator
files are not copied. Full commit IDs are required; other source revisions
need a deliberate recipe update. The output directory is 0700, its files
0600, and existing paths/symlinks are refused. Preparation does not fetch,
build, sign, publish, deploy or generate any operator credential.

The manifest requests a node-generated, transport-only TURN root secret
through Archy's `generated_secrets` and `secret_env`. It does not request
reuse of the node's Nostr identity. The design requires that secret to stay
on the operator's node, outside room links, public service listings, client
bundles and publisher accounts. The installed-node readback verifies uid 1000,
mode 0600 and absence of the value from container inspection. Broader
secret-isolation review remains open.
An operator may later mint temporary transport credentials; room admission
stays separate.

The initial package is deliberately `spry-turn-lab`, outside the installable
catalogue. It has a local image tag, `pull_policy: never`, bounded allocations,
connections and bandwidth, no capability grants and a read-only root. Host
networking avoids claiming an HTTP app gate can proxy TURN's relay sockets.
The process binds **127.0.0.1 only** and both declared ports have `auth: local`.
Loopback peer permission is for this local experiment only. It has no TLS
certificate, public listener, directory, credential HTTP server, database,
media recorder or discovery publisher. It is not a usable Internet relay as
prepared. No HTTP health check is invented for a non-HTTP protocol.

Package revision 2 explicitly bounds UDP peer-relay sockets to **49160–49191**
on loopback. Spry skips occupied host ports and returns a signed TURN 508
on exhaustion; it does not fall back outside the range. This is separate
from the UDP/TCP client listener on 3478 and does not open a firewall or
publish the service. These are process bind arguments: host networking
does not make manifest port declarations an enforcement boundary.

Prepare it under an existing private parent directory:

```sh
python3 scripts/prepare-spry-turn.py \
  --source /private/checkouts/spry-turn \
  --output /private/experiments/spry-turn-lab
```

The prepared Dockerfile builds only the pinned source, with optional TLS
support compiled in. Building is a separate local action:

```sh
docker build --tag localhost/spry-turn:0.1.0-a76496bbcb60-2 \
  /private/experiments/spry-turn-lab
```

Building in Docker does not load the image into a separate Archy node's
rootless Podman store. Transfer and verify an owner-selected image on that
node before any install; a manifest is not installation evidence. Do not
push the private source context or image. Production packaging needs the
remaining networking and certificate qualification below. The [operator
endpoint plan](archy-call-endpoint-plan.md) separates process bind arguments,
host/provider firewalls, NAT and certificate responsibilities.

## Discovery design to implement

Use the existing Wildbloom opt-in discovery work as a design precedent, not
its storage schema as a transport schema. The current `402-announce/storage`
contract describes storage and cannot be presented as TURN interoperability.
A shared, versioned transport profile and signed fixtures are still needed.

1. Installing a service does not publish it or make it public transit.
   The operator separately chooses exposure, capacity and publication.
   Private owner/friend installations may remain unlisted and share a
   connection profile directly.
2. A public operator signs its own description using an operator-controlled
   service key and publishes to operator-selected relays. The design requires
   no mandatory ForgeSworn directory, signer, relay list, registration or approval.
3. A listing binds an operator key to a service identifier, protocol version,
   endpoints, supported transports, authentication method, expiry and a
   coarse availability state. No credential, room ID, participant list,
   media key or call record belongs in it. A signature authenticates the
   statement, not its honesty, legal identity, uptime or logging claims.
4. Clients verify the signature and endpoint binding, bound input sizes and
   time skew, enforce freshness/withdrawal and retain replay watermarks.
   Conflicting same-time updates must not restore older authority. Local
   selection remains replaceable; publisher-curated listings must not become
   a mandatory calling entitlement.
5. Reading a listing grants neither transport allocation nor room admission.
   Credentials come directly from the selected operator or a private profile.
   Root secrets must remain on the node. Any automatic issuer is a separate
   operator-owned component whose API and retention need their own review.
6. Do not blindly probe all advertised URLs or turn discovery into an SSRF
   path. Public discovery needs destination restrictions, bounded requests,
   trusted TLS and redirect/referrer/cookie policy. A deliberate private-node
   configuration is a separate path. Do not substitute weaker transport when
   relay-only privacy was selected.
7. Cache and rank locally. Do not send discovery choices, calls, latency
   measurements or failure reports to ForgeSworn by default. Any synthetic
   test evidence is separate from production collection.

The package preparer implements none of these network publication steps.
The clients do not yet automatically discover Spry services. There is no
ratified NIP or cross-implementation transport profile claim here.

## Combined media stack

Spry supplies packet reachability. RelaySwarm can contribute bounded peer
distribution and rendezvous mechanisms. Sapflow can contribute media/queue
primitives and native adapters. Conversational forwarding still needs a
separate encrypted real-time adapter and measurements against existing mesh.
Reusing the whole Sapflow origin or RelaySwarm demo would introduce their
publishing authority, credential services, state/logging or recording options.
Do not describe that combined offering as an opaque no-logging packet relay.

Room membership and media protection must remain participant-controlled.
The forwarding design must qualify browser encryption support, key rotation,
joining/leaving, forwarder replacement, congestion, loss and screen redaction.
Do not make every software installation forward unrelated calls by default.

## Legal-cover boundary

This follows jurisdiction-kit's [GB online-services note](https://github.com/forgesworn/jurisdiction-kit/blob/main/law/gb/online-services.md),
verified overall 28 September 2026, review due 28 March 2027, including the
23 October 2026 update to section 2.11. `[P]` means primary text read, not a
settled application; `[U]` means an unresolved application or interpretation.

Publishing software and an ordinary package catalogue is the intended role.
The prepared source adds no operated public service. OSA section 226(12)'s
access-facility distinction exists `[P]`; applying it to an actual TURN,
discovery or forwarding deployment and the combined offering remains `[U]`
(2.2, 2.11). Independent ownership and absence of publisher authority support
the intended position; a package name, protocol, encryption or no-log setting
does not establish an exemption. A publisher-operated discovery directory
or a service managed through nominal third parties needs its own assessment.

An operator's transport authentication is distinct from room membership.
Each deployment's actual service role still matters. Do not promise that
every Archy owner or voluntary forwarding peer is outside the OSA. Data
protection and communications/investigatory-powers questions are separate
(3, 4.1, 5, 7). No persistent call logs is a design requirement; transient
addresses, authentication state and packet buffers are still processed.
Host, orchestration, crash-dump and provider logging need deployment readback.
No new service-launch deadline or cost is assigned by this local experiment.

## Remaining gates

- Apply and read back the bounded relay-port firewall/NAT plan on a real
  operator node. Range selection is implemented; this package remains local.
- Public certificate validation, renewal/reload and a transport-specific
  readiness check. An Archy self-signed node certificate is not automatically
  trusted by arbitrary browser guests' TURN clients.
- Independent source/security review, longer rootless Podman operation,
  upgrade/uninstall behaviour and resource-pressure testing. Basic installation,
  restart, kernel limits, secret permissions/inspection and app-scoped logging
  now have actual-node readback; these are narrower than production acceptance.
- Shared transport-discovery contract, signed fixtures, withdrawal/replay
  handling and independent publisher/client interoperability.
- Actual KithMoot multi-party media, refresh/rejoin, loss/jitter/blocked UDP,
  operator replacement and cross-network acceptance. The companion browser
  experiment has passed five local TLS cases against each of Spry and coturn,
  including received redacted screen pixels; those
  use a disposable issuer and synthetic media, not an installed Archy package.
- The previously observed intermittent native media stall remains open even
  when a later browser run passes. Physical no-Play GrapheneOS acceptance
  and a measured larger-call distribution design remain separate gates.

No public node or service was deployed by this work.

The subsequent [existing-node qualification](archy-spry-node-qualification.md)
and [installed-service handover](archy-spry-installed-20261023.md) built the
same pinned source for Linux AMD64, verified it on the node and installed it
through the package API after signer approval. Public exposure and discovery
remain pending.

The [revision 2 evidence](evidence/archy-spry-bounded-20261023.json) records
eleven passing package tests, both manifest validators, the refreshed Linux
ARM64 image build and isolated process/credential smoke. The image was not
installed on Archy and carried no network media in that smoke test. The
[earlier revision 1 receipt](evidence/archy-spry-package-20261023.json) remains
historical evidence for its own source pin, not this updated package.
