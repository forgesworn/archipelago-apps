# Spry on Archipelago

1. Install **Spry** in the ForgeSworn Archipelago bundle.
2. Open it and choose **Pair with KithMoot**. Approve the pairing.
3. Use KithMoot's normal Call button, in a conversation or group.

The matching ForgeSworn 1.9.1 bundle update includes backend p2 and catalogue p2.
Older bundles need that node update before installing this package.

Each home node runs its own Spry. Once both people have paired, their nodes
connect over Archipelago's existing mesh. A third participant's VPS is not
needed for their call. The [Linux Docker host recipe](../../node/docker.md)
uses the same real Archipelago backend and its existing Docker runtime;
its fresh-host install qualification remains separate.

The mesh must already work on the node. The package selects its `fips0` route,
the node's existing owner identities, local hostname and host certificate.
Spry waits for that route and becomes ready automatically. No port forwarding,
TURN password or relay address is entered in KithMoot. The owner approves use
of their selected Nostr read/write relays when pairing; no new default relay
or publisher-operated directory is installed.

The people in a private-only call need access to their own paired nodes. A
publicly reachable standalone Spry can also share TURN access with guests
who have no node. Spry's public HTTPS access protocol remains supported.

## Libraries and host boundaries

Spry is standalone. Its reusable Rust libraries live in the
[Spry repository](https://github.com/forgesworn/spry-turn):

| Library | Responsibility |
|---|---|
| `spry-turn` | Packet forwarding, TURN authentication and resource limits |
| `spry-access` | Pairing, scoped grants and short-lived credentials; no sockets |
| `spry-link` | Signed encrypted control messages, peer cards and packet frames; no sockets |
| `spry-service` | Optional HTTP, Nostr and OS mesh adapters, plus the standalone executable |

This package pins those libraries and supplies only the dashboard/signing
assets. Archipelago's app manager owns installation and owner keys; its app
gate owns renewing HTTPS and optional TURN TLS; its networking layer owns
FIPS, routing and firewall policy. Spry never imports an Archipelago or FIPS
SDK. Other ForgeSworn products can consume the same libraries independently.

The installed relay and service use Rust. The UI uses JavaScript and Android
uses Kotlin with native WebRTC. The image contains no Node interpreter. It
has a read-only root, no extra capabilities, 128 MiB and one CPU. FIPS/TUN
privileges belong to the Archipelago host, outside the Spry container.

## Transport and access

The owner UI is HTTPS 3744. Clients reach their own node over UDP/TCP 3478,
with host-managed TURN TLS on 5349. Signed peer traffic uses TCP 3745 bound
only to the mesh ULA. Virtual relay ports 49160–49191 remain on loopback and
cross the authenticated peer link; the package does not publish them.
Installation owns only its named firewall rules and its FIPS drop-in;
uninstallation removes those exact rules and preserves unrelated policy.

A node identity authorises a five-minute, single-use pairing link. KithMoot
creates a separate transport key. Each room receives opaque access inside its
encrypted descriptor. Devices obtain independent five-minute credentials;
KithMoot renews them and updates calls. Room and media keys stay in KithMoot.
Signed node cards let a paired app authorise room peers with its own node;
foreign adverts never make the app probe another person's local network or
open their advertised control relays.

Remove a pairing to revoke its grants, future credentials and peer routes.
Existing credentials and allocations expire within five minutes. The node
persists pairings and grants privately across restarts; room capabilities
have a 30-day idle lease extended through use. No arbitrary proxy is installed.

## Verification

Run Rust fmt, clippy and workspace tests. Image CI builds both native
architectures and runs independent UDP/TCP/TLS interop. The frontend release
waits for an anonymously pullable image on both architectures.

Spry's `tests/mesh.py` checks real encrypted packet forwarding in two isolated
Linux containers. Its `tests/home-flow.mjs` drives actual pairing screens and
a built KithMoot PWA across two or three separate services, including reload
and renewal. The receipts distinguish generated browser media, Docker routes,
TLS fixtures, the installed bundle and physical home-network acceptance.
A Docker bridge test alone does not prove FIPS across independent home NATs.
