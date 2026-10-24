# Spry on Archipelago

Install **Spry** in Archipelago, open it, and choose **Pair with KithMoot**.
Approve the pairing in KithMoot. Then use the normal Call button in a
conversation or group. The people joining need no Spry installation or relay
settings. The paired app can close after sharing access.

The node runs the Rust Spry relay and a separate Rust pairing service. The
browser interface uses JavaScript; Android uses Kotlin and native WebRTC.
There is no Node interpreter in the installed package.

## Node prerequisites

This package needs an Archipelago node with a public IPv4 address, a public
HTTPS hostname and the host's renewing certificate configuration. An explicit
IPv4 NAT mapping is supported through operator configuration. Spry does not
silently configure a router, select a central relay or bypass CGNAT.
These are node requirements, not settings each caller must enter.

The package needs the backend containing patch 0025 and the matching frontend
catalogue. It declares its complete transport surface: control HTTPS 3744,
TURN UDP/TCP 3478, host-terminated TURN TLS 5349 and UDP peer ports
49160–49191. Installation adds only its named rules to an already active UFW;
uninstallation removes only its own rules. Existing firewall policy and
rules remain under node administration. External provider firewalls and NAT
still need to permit this surface.

The host terminates TLS using Archipelago's certificate resolver, including
renewal. The container receives no dashboard TLS key. It runs rootless with
a read-only root, no extra capabilities, 128 MiB and one CPU. Packet forwarding
remains in the separate Spry executable.

## Pairing and access

A node identity authorises a five-minute, single-use pairing link. KithMoot
creates a separate transport signing key and confirms the pairing. The
node's TURN secret never leaves the node.

Each room receives an opaque capability inside its encrypted descriptor.
Every device proves possession of its own transport key to obtain independent
five-minute TURN credentials. KithMoot renews them and updates live calls.
Guests can retain and restate shared access while the paired participant is
offline. The node persists capabilities privately across restarts; their
30-day idle lease extends through use. A capability authorises bounded relay
use, and does not itself grant room membership or media decryption keys.

Remove a pairing in Spry to revoke its room capabilities and future
credentials. Credentials already issued expire within five minutes. Pairing
management is signed and restricted to node identities; no anonymous issuer
or arbitrary upstream proxy is installed.

## Verification

Run `cargo fmt --all -- --check`, `cargo clippy --locked --workspace --all-targets -- -D warnings`
and `cargo test --locked --workspace`. The image workflow builds both native
architectures and runs independent socket interop against the packaged relay.
The frontend release waits for an anonymously pullable image for both
architectures before publishing its install catalogue.

`tests/spry-flow.mjs` drives the actual pairing and call interfaces with
locally generated identities and media. It requires a built KithMoot checkout,
Playwright Chromium, the Rust control executable and a Spry relay executable.
Its receipt distinguishes local browser/loopback proof from public TLS/NAT,
independent-node installation and physical Android acceptance. Raw failure
artifacts belong in ignored local storage.
