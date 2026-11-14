# Public Spry STUN/TURN relay on a fresh VPS

Status: **operator-deployment candidate**. The installer and isolated tests do
not deploy a VPS or establish production call acceptance. Use an instance you
control and assess before directing real calls to it.

This recipe runs only the native Spry packet relay. It does not install
Archipelago, a dashboard, a room service, a Nostr advert or a public credential
endpoint. STUN Binding and authenticated TURN allocations use the same service.
Each device receives an opaque, expiring profile generated over SSH.

## Artefact and boundary

The Quadlet pulls this multi-architecture image by immutable digest:

```text
ghcr.io/forgesworn/spry@sha256:15dd7a0aa83c2d9ed9a439af264e79062cecaf1cab5902910a914d4526e30ee8
```

It is the published `0.1.0-2efb051-2` image, with linux/amd64 and linux/arm64
variants. The digest and source revision are deliberate; do not replace them
with `latest` or the unpublished `0.1.0-6b34f06-4` tag. A checksum verifies the
pulled bytes, not independent release approval or future availability.

The service has 32 allocations, eight per credential, 32 TCP/TLS connections,
1,000,000 bytes/second aggregate per allocation, one CPU and 128 MiB memory.
Relay UDP ports are limited to 49160–49191, with no ephemeral fallback. The
container has a read-only root, no capabilities and no application log driver.
The host account is an unprivileged, dedicated `spry-relay` user. The transport
secret and TLS private key are mounted read-only and are absent from container
configuration inspection.

The relay handles IP addresses, credential identifiers, allocation metadata and
forwarded datagrams. TLS terminates at the relay; endpoint media encryption is
still required for content confidentiality. Inspect host, process-manager,
crash-dump and provider logging separately. Public operation also needs an
operator-specific legal/privacy assessment; see the
[transport position](https://github.com/forgesworn/spry-turn/blob/main/docs/legal/transport-position.md).

## Prerequisites

Use a dedicated Debian 13 VPS with systemd, a public IPv4 address and a DNS
hostname resolving to that address. amd64 and arm64 are supported by the pinned
image. Keep the clock accurate and root SSH access available. Do not use an
existing Archy host: the installer refuses common Archipelago state markers.

The VPS firewall must initially be active with only SSH allowed. The installer
does not reset or replace existing rules and refuses another fresh baseline.
For a new VPS only:

```sh
ufw allow 22/tcp
ufw --force enable
```

At the provider firewall, permit the same ports as the installer:

| Port | Purpose |
| --- | --- |
| TCP 80 | HTTP-01 certificate issuance and renewal; no dashboard |
| UDP/TCP 3478 | STUN/TURN clients |
| TCP 5349 | TURN-over-TLS clients |
| UDP 49160–49191 | Bounded peer-relay sockets |

Outbound UDP and return traffic are required even when clients use TCP or TLS.
Opening only TCP 5349 is insufficient. NAT, if any, needs one-to-one translation
and preservation of the relay range. Provider firewalls are outside the
installer's control. No public TCP 443 dashboard or management listener is added.

Copy the reviewed installer to the VPS:

```sh
scp node/spry-relay.py root@relay.example.org:/usr/local/sbin/spry-relay
ssh root@relay.example.org 'chmod 700 /usr/local/sbin/spry-relay'
```

Replace the example hostname and every example address with your own.

## Activate

```sh
ssh root@relay.example.org
/usr/local/sbin/spry-relay activate --hostname relay.example.org --ip 8.8.8.8
```

The address above is only an input example; supply the VPS's actual public IPv4.
Activation validates DNS and the existing host, installs bounded OS packages,
creates the service account and a random 32-byte secret, opens the recorded
rules, obtains a certificate if the lineage is absent, pulls the immutable
image, and verifies the running arguments and isolation. Existing secret,
certificate and state are retained on a same-endpoint rerun. The user-mode
service does not wait for a provider-specific network manager; its restart
policy handles a configured address that is not yet available after boot.

Certbot registers an ACME account and accepts its terms as part of `certonly`;
use an existing account if present. The HTTP listener exists only while Certbot
runs. No HTTP API or credential issuer is installed. Inspect the ACME account
and hosting terms as part of deployment.

A failed activation attempts to stop the service and remove only the rules added
by that activation. It leaves private state for diagnosis and retry. A status of
`rollback-error` means some recovery action needs inspection; it is not a pass.

Check the result:

```sh
/usr/local/sbin/spry-relay status
```

## Give each device a profile

```sh
/usr/local/sbin/spry-relay profile --output /root/device-alice.json --ttl 3600
```

Use a new output filename for every device. Profiles are mode 0600, are never
overwritten, and contain UDP, TCP and trusted-TLS URLs plus an opaque expiring
username/password. Share each profile privately with one device. Usernames are
random and are not linked to a room, person or source address.

These are bearer transport credentials, not room membership or call admission.
Do not publish them or put them in Git, room links or discovery events. The
application must renew before expiry and restart ICE as needed; expiry is not
immediate revocation of every established allocation. Generate another profile
for another device rather than copying a previous one.

## Deactivate or recover

```sh
/usr/local/sbin/spry-relay deactivate
```

This stops the service, removes its certificate hook and deletes only the
firewall rules recorded for the current activation. It preserves the secret,
state, certificates, packages and account for diagnosis and same-endpoint
reactivation. It does not undo package installation or remove unrelated rules.
Use the same command after inspecting an automatic rollback.

## Renewal

The activation installs a Certbot deploy hook which copies the selected lineage
to the private TLS directory and restarts the relay. The hook does nothing for a
different lineage. `/usr/local/sbin/spry-relay renew` performs the same operation
manually and requires an active relay.

**Every relay restart closes existing allocations.** There is no hot certificate
reload, seamless renewal or dual-secret rotation. Test renewal and client
reconnection before relying on them. Replacing the transport secret invalidates
previous credentials.

## Qualification and remaining acceptance

Local implementation checks for this recipe are in `tests/test_spry_relay.py`.
They cover input refusal, the immutable unit, credential output, secret handling,
runtime arguments and rollback. `tests/test-spry-relay-host.sh` is a separate,
explicitly enabled privileged disposable-host rehearsal:

```sh
SPRY_RELAY_HOST_TEST=1 tests/test-spry-relay-host.sh
```

When the nested fixture cannot delegate cgroup controllers, its explicit
`SPRY_RELAY_TEST_NO_CGROUP=1` adaptation selects `crun` and disables cgroups
only for that rehearsal. Its capability/storage matrix found that rootless
overlay on this nested Docker backing cannot execute even an unhardened shell;
`vfs` passes baseline, independent hardening flags and full isolation. The
fixture therefore selects `vfs` at both pull and runtime. These are not
production defaults: the production unit still includes and verifies memory,
CPU and PID limits and uses the normal storage and runtime configuration.

The disposable Debian rehearsal passes activation, status, private profile
creation, real STUN Binding over UDP, TCP and hostname-validated TLS, and
deactivation. Runtime checks confirm zero process capabilities, enforced
`NoNewPrivs`, a read-only root, no application logs, the exact shell/relay
command and no transport secret in container inspection. This rehearsal does
not exercise production cgroup limits on a real VPS.

The published binary also passed nine network-disabled wire checks covering
bidirectional UDP, TCP and TLS ChannelData, refresh/deallocation, wrong-key and
private-peer refusal, credential expiry and bounded-port reuse. A full run of
the current upstream suite is not claimed: that checkout includes newer
`relay-port-map` features and behaviour absent from this older pinned image.

These checks do not establish provider reachability, sustained load, renewal
availability, physical-device acceptance or two independent restrictive-NAT
paths. Before production use, verify authenticated relay operation from separate
networks, including one with UDP blocked, then audio, video, screensharing and
chat with forced relay, long calls, reconnects and credential renewal. Keep an
existing relay configuration as rollback; changing server addresses does not
migrate active calls. See the [public-lab evidence and limits](archy-spry-public-20261023.md)
for the earlier external qualification scope.
