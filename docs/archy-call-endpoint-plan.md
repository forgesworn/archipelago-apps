# Independent call endpoint plan

**Later qualification:** see the [public candidate handover](archy-spry-public-20261023.md).
This document retains the original plan and local-preparation snapshot.

23 October 2026. Operator checklist for a later public candidate, not an
installation command or deployment evidence. The prepared `spry-turn-lab`
package remains loopback-only, unlisted and without a TLS endpoint.

## What revision 2 provides

The [package preparer](../scripts/prepare-spry-turn.py) pins Spry commit
`a76496bbcb60e637c0606c8da5919b5a3b2b3cf3`. Its bind arguments select
`127.0.0.1:3478` for UDP/TCP clients and `49160:49191` for UDP peer-relay
sockets. The root secret is requested from the installing node, separately
from its Nostr identity. No endpoint, issuer or discovery URL is supplied.

Spry validates inclusive nonzero ranges, skips occupied UDP ports and
refuses allocation with an authenticated 508 when the range is exhausted.
It never falls back outside a configured range. Without `--relay-ports`,
Spry's standalone default still uses OS-assigned ephemeral ports; the
package explicitly supplies the bound. This changes exposure/resource
control, not room membership or who operates the underlying call service.
The [bounded package receipt](evidence/archy-spry-bounded-20261023.json)
keeps native/browser, image, manifest and actual-installation evidence separate.

## Public candidate contract

The installing operator must deliberately supply and control these items
before a public package can be qualified:

| Item | Required behaviour | Evidence still owed |
|---|---|---|
| Bind address | Concrete local relay IP and deliberate client-facing listener address; a wildcard listener requires explicit `--relay-ip` | Actual process arguments and bound sockets on the operator node |
| Relay capacity | An explicit inclusive UDP range, sized alongside allocation/descriptor/bandwidth limits; no ephemeral fallback | Allocate until exhaustion, authenticated TURN 508 refusal, deallocate/reuse and unaffected live traffic |
| Firewalls | Host and provider rules cover chosen UDP/TCP client port, optional TLS TCP port and UDP relay range; unrelated inbound traffic stays restricted | Read back both sets of rules and test allowed/blocked traffic externally |
| NAT, if present | Preserve the relay ports with operator-managed address translation; configure the matching `--public-ip` | Independent-network candidate addresses and bidirectional traffic, not a local hairpin test |
| TLS identity | Operator-chosen DNS name in `turns:` URI, valid trusted certificate chain for that name, private key kept on the operator node | Browser/native acceptance without certificate bypass, plus wrong-name/untrusted-certificate refusal |
| Certificate lifecycle | Operator-controlled issuance/renewal and read-only runtime access to key/chain; replacement currently needs a restart | Renewal and restart/rejoin test, including the loss of active allocation state |
| Private credentials | Node-owned random TURN root secret, short-lived transport credentials provided directly to authorised clients, no root secret in browser/WASM/profile/catalogue | Rootless Archy install, secret location/permissions, package/export/client-bundle inspection and rotation/recovery |
| Retention | No persistent call logs by default; no room, member, media or credential collection by the publisher | Container/process-manager/host/crash/provider logging readback; transient packet/auth/address state is still processed |
| Owner control | Owner selects updates, exposure, capacity and publication independently; publisher has no runtime management credential | Actual lifecycle/upgrade path and successful replacement with another operator |

Host networking bypasses ordinary container port mapping: declared manifest
ports do not enforce these restrictions. An HTTP gate or ordinary TLS
reverse proxy is not a substitute for the TURN UDP/TCP/TLS and UDP peer
paths. TURN over TCP/TLS still forwards to its peers using UDP. A node's
self-signed web certificate is not automatically trusted by browser guests.
Do not enable `--allow-loopback-peers` on a public candidate; it is a local
test opt-in and the CLI refuses it with a non-loopback client listener.

## Acceptance sequence

1. Install the pinned image on an owner-controlled Linux Archy node with
   rootless Podman. Verify runtime secret isolation, resource limits and
   logging before exposure. Local Docker build/smoke and manifest parsing
   are separate evidence.
2. Supply the operator's endpoint/certificate/firewall configuration without
   placing private files in the build context. Verify startup refusal for
   absent/mismatched key material and any invalid range. Public preparation
   must require explicit operator inputs; it must not infer a hostname,
   request a publisher entitlement or silently publish discovery.
3. Test authenticated data, decoded audio/video and received protected
   screen pixels from separate networks; test blocked UDP, expiry, refresh,
   rejoin, operator replacement and certificate renewal. Preserve relay-only
   privacy if selected. A port-listening or process-alive check is insufficient.
4. Qualify physical GrapheneOS without Play separately. Investigate the
   previously observed native media stall independently; green relay tests
   do not establish its cause or repair.
5. Implement a shared signed transport profile with bounded parsing,
   endpoint binding, expiry, withdrawal/replay policy and independent client
   interoperability. Listing publication is a separate opt-in action; no
   mandatory ForgeSworn directory, signer, relay or remote manager.

No public node, certificate order, firewall change, discovery announcement
or remote installation was performed by this increment. Larger group media
distribution through RelaySwarm/Sapflow still needs a new measured encrypted
real-time forwarding adapter; bounded TURN ports do not reduce mesh uploads.

## Legal-cover readback

The intended role remains software/protocol publication with independent
operation. This source/package increment operates no public endpoint. See
the [legal-cover boundary](archy-call-services.md#legal-cover-boundary) and
jurisdiction-kit's GB note, verified overall 28 September 2026, review due
28 March 2027, section 2.11 updated 23 October 2026. The access-facility
distinction is recorded `[P]`; its application to deployments and the combined
offering remains `[U]`. Port bounds, encryption, independent packages and
no-log settings do not establish an OSA exemption. A public operator's actual
service, discovery and communications/data-protection roles require their
own assessment.

## Local handover

Spry's default TLS and portable TLS builds each passed 22 socket tests.
Chromium checked actual selected relay ports and generated media/data over
UDP, TCP and TLS. The Archy increment passed 11 package tests and both
manifest validators; its refreshed Linux ARM64 image passed an isolated
process/credential smoke, with no network media in that container test.
These local checks are not hosted CI or a real-node installation.

Task test processes and containers are stopped. The local image, private
build context, package-test bytecode and newly created manifest-check target
were removed after recording evidence. Spry's task-built package outputs
were cleaned within its existing target; shared dependency/Docker caches,
the pinned upstream Archy source and unrelated local work were preserved.
No push, merge, package publication or deployment was performed.
