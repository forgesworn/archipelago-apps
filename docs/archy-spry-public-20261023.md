# Invited TURN qualification on the owner-controlled Archy node

23 October 2026. This supersedes the loopback-only status in the
[installed-lab handover](archy-spry-installed-20261023.md). It qualifies public
transport for invited testing, not a complete production call service.
The [receipt](evidence/archy-spry-public-20261023.json) records versions,
measurements, failed intermediate checks and remaining gates.

## Current deployment

The existing `spry-turn-lab` package now runs an explicit public candidate on
`demo.forgesworn.dev`, using the same reviewed AMD64 image and node-owned
transport secret. No image was rebuilt or published. The base package
preparer still produces a loopback-only lab. The separate
[owner promotion helper](../node/expose-spry-lab.py) changes this installed
qualification instance through the owner's root SSH administration.
It requires the exact installed lab and inspected nginx checksum, saves
configuration backups, checks the running service before opening ports and
closes its added rules on failure. It is not a general upgrade manager.

| Surface | Current behaviour |
|---|---|
| TURN clients | IPv4 UDP/TCP 3478 and trusted TLS TCP 5349 |
| UDP peer sockets | Only 49160–49191; no ephemeral fallback |
| Private peers | Loopback and private-network permissions refused |
| HTTP 80 | Existing webroot ACME challenge; dashboard paths return 404 |
| Dashboard 443 | No public firewall rule; external TLS attempt timed out |
| Credentials | Node CLI, expiring opaque per-device usernames; no HTTP issuer |
| Discovery and defaults | No announcement or client-default change |
| Isolation | Rootless, read-only root and TLS mount, 128 MiB and one CPU |
| Application call logging | Log driver none, null process output, core limit zero |

UFW retains SSH and adds only the listed transport/ACME rules, in IPv4 and
IPv6 forms. Spry's listeners and relay sockets bind the explicit IPv4 address.
Provider firewall configuration was not inventoried; actual allowed-path
traffic was verified from outside the node.

TURN ports use `auth: none` with an explicit protocol-authentication rationale.
Archy's `auth: open` still installs its HTTP gateway and competes for the
sockets; it cannot proxy native TURN. The first two activation attempts stopped
before opening the firewall. Saved configuration and the loopback runtime were
restored. The helper now also waits for both generated and actual runtime
arguments, rather than racing Archy's asynchronous reconciler.

## Evidence and limits

- 33 package/installer/public-boundary unit tests and 18 shell manifest checks
  passed. The deployed Archy parser accepted and rendered the public manifest.
  Hosted CI has not run for this local increment.
- External independent Python clients passed authenticated bidirectional
  ChannelData, Refresh and deallocation over UDP, TCP and trusted TLS before
  and after renewal restart. Wrong passwords, expired credentials,
  private/loopback peers and a wrong TLS hostname were refused.
- Chromium, with certificate bypass removed, selected bounded relay candidates
  and passed bidirectional data and decoded video over all three transports
  before and after restart. The final audio gate measured remote decoded PCM
  through Web Audio with silent output: RMS 0.705–0.711 on both peers. Content
  was generated oscillator/canvas media; no person or screen was captured.
- Public HTTP challenge content was read back. `/`, `/rpc/v1`, `/ca.crt` and
  `/app/filebrowser/` returned 404.
- Certbot's staging renewal dry run passed with deploy hooks enabled. The hook
  copied the existing production certificate and restarted Spry. Subsequent
  transport/media tests passed. No production certificate was replaced.

Both browser peers ran on one external Mac and used one remote relay. This is
an external client path, not two independent access networks, the KithMoot
room UI, physical GrapheneOS or multiparty/screen-redaction acceptance. There
is no throughput, latency, load, availability or loss-rate claim.

An intermediate test incorrectly required Chromium's `totalAudioEnergy` to
increase; it stayed zero even with positive decoded waveform/sample counts.
The final gate measures the waveform. A separate intermediate UDP ChannelData
receive timed out; its cause remains unresolved. The final test allowed at most
three UDP attempts and recorded one attempt in each direction. The previously
observed native media stall remains a separate open issue.

## Credentials and owner operations

The node's root secret is uid 1000, mode 0600 and absent from container
inspection. No anonymous credential endpoint is exposed. The current web
client's automatic issuer fetch carries no operator access token; exposing the
existing unauthenticated issuer would allow strangers to obtain bandwidth.
Automatic issuance needs a reviewed access mechanism and client support.

For a real test, replace `operator-node` with the owner's SSH alias or hostname,
and mint a separate profile for each device shortly before use:

```sh
ssh root@operator-node \
  '/root/archy-spry-qualification/expose-spry-lab.py profile --output /root/my-call-relay.json --ttl 3600'
scp root@operator-node:/root/my-call-relay.json ./my-call-relay.json
chmod 600 ./my-call-relay.json
```

Use a fresh filename for another device. Import the JSON through supported
private call-relay settings, or enter its TURN URLs, username and password.
Deliver profiles privately. They are bearer credentials; expiry does not
promise immediate termination of every established allocation. Never share
the root key or put credentials in room links, discovery events or Git.
Remove profile copies when no longer needed. Refresh automation is unfinished.

Runtime TLS copies live under `/var/lib/archipelago/spry-turn-lab/tls`, directory
0700 and files 0600 owned by uid 1000. The new Certbot deploy hook is
`/etc/letsencrypt/renewal-hooks/deploy/spry-turn-certificate`; it acts only on the
configured lineage. Spry reads TLS files at startup. Renewal restarts lose
active allocations; seamless renewal and call rejoin remain unqualified.

The owner can close the candidate and restore saved configuration with:

```sh
ssh root@operator-node \
  '/root/archy-spry-qualification/expose-spry-lab.py rollback'
```

Inspect any later operator changes before rollback. Private configuration and
backups remain under `/root/archy-spry-qualification/public-candidate`, with the
small failed-attempt backups alongside. `public-test-source` there preserves
the executed fixture source and its pinned wire/browser bases, without
credentials. Test credentials, ACME probe, local scratch, diagnostic container,
browser and HTTP fixture are removed. The requested installed service, image,
secret, TLS copies, renewal hook, logging drop-in and rollback material remain.

## Legal-cover and next gates

Today this is project qualification on an owner-controlled node, running
publicly reachable transport with invitation-restricted allocation. It is not
independent third-party operation. Actual SSH administration and credential
authority remain with this operator; no zero-control claim is made.
Transport credentials grant allocation separately from room admission.
No household/internal-business exemption is assumed. This package has no room,
membership, recording or HTTP issuer service; assess the combined offering
separately. The intended product role remains software/protocol publication
with people installing, managing and selecting independent services.

See jurisdiction-kit's [GB note, section 2.11](../../jurisdiction-kit/law/gb/online-services.md):
verified overall 28 September 2026, section updated 23 October 2026, review due
28 March 2027. The access-facility distinction is `[P]`; applying it to this
transport and combined offering remains `[U]`. OSA exemption has not been
established. Data-protection, communications and investigatory-powers roles
remain separate assessment items. No new U2U deadline is assigned here.

Existing nginx, UFW low-level, Archy administration, Podman/systemd lifecycle
and Certbot logs remain; provider retention is unverified. No persistent
application call logs configured is a narrow statement: transient transport
addresses/authentication state still exist. A later issuer needs its own
access/retention assessment.

Next: real KithMoot calls on separate devices/networks, including physical
GrapheneOS without Play; protected screen/window/area sharing and redaction;
blocked-UDP failover, expiry/rejoin, limits under public load, operator
replacement and independent installation. Then add operator-owned automatic
credentials and signed opt-in discovery. RelaySwarm/Sapflow group forwarding
requires a measured encrypted real-time adapter; TURN does not reduce mesh
upload requirements.
