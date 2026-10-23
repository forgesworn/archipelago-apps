# Spry qualification on an existing Archy node

23 October 2026. Owner-authorised qualification on an owner-controlled
Debian 13 x86-64 node. This is not evidence of independent third-party
operation, a public service launch or an OSA exemption.

## Current result

- Built the unchanged pinned Spry source for Linux AMD64 and transferred
  the exact image into the existing Archy user's rootless Podman store.
- Verified archive checksum, immutable image ID and architecture on the
  node. The image has not been installed through Archy's package API yet.
- Extracted that image's executable for a disposable unprivileged test.
  All 22 independent UDP/TCP/TLS socket tests passed on the node, including
  permissions, authentication, quotas, bounded relay ports and exhaustion.
  The export container, test executable, fixture keys and test directory
  were removed. This test used loopback and generated TLS material.
- The operator-supplied dashboard hostname resolves to the node. It already
  has a publicly trusted certificate and a renewal timer. A strict HTTPS
  request from the node passed without a trust bypass. This does not test
  a TURN TLS listener or demonstrate external public reachability.
- The host firewall still allows inbound SSH only. No firewall, DNS, nginx,
  certificate, runtime manifest, dashboard, existing app or discovery
  publication was changed by preparation.

An external strict TLS handshake to the dashboard and the proposed TURN TLS
port timed out. Socket connection alone appeared successful from that test
network, so it is not used as proof of an externally reachable service.
The existing certificate uses HTTP webroot renewal; challenge reachability
through the current firewall still needs qualification before public use.

Exact source/image/checksum evidence is in the [bounded receipt](evidence/archy-spry-node-20261023.json).
The prepared package still binds loopback only. Nobody can discover or use
a public Spry service from this node on this evidence.

## Authenticated installation

The [node installer](../node/install-spry-lab.py) accepts only the exact
reviewed loopback manifest checksum and the expected local image. It uses
Archy's existing `auth.login` and `package.install` API over verified HTTPS;
it does not reset a password, bypass dashboard authentication or change
the dashboard's network access. It reloads the backend after staging the
manifest in the frontend runtime directory, which is the source the
backend promotes on restart. Existing applications remain installed.

The owner supplies a temporary dashboard password file on the node:

```bash
ssh -t root@<node> 'umask 077; install -m 600 /dev/null /root/archy-spry-dashboard-password; read -rs -p "Archy dashboard password: " archy_password; printf "\n"; printf "%s\n" "$archy_password" > /root/archy-spry-dashboard-password; unset archy_password'
```

The helper refuses symlinks, non-root ownership, non-0600 permissions,
empty/oversized input, changed manifests, image mismatches and redirects.
The password remains in its temporary node-local file until removal and
in the installer process; session cookies remain in that process. Neither
appears in command arguments, reports or files copied back to the publisher. After
a full authenticated session is confirmed, the password file is removed;
the task session is logged out on completion/failure. A failed login leaves
the owner's file in place for correction or deliberate deletion.

On the node, after the verified image has been loaded:

```bash
python3 /root/archy-spry-qualification/install-spry-lab.py \
  --manifest /root/archy-spry-qualification/manifest.yml \
  --manifest-sha256 02f28c27e033a193c2aa268d0a73ff4498ae74828c7ab698ed22a012679f82c1 \
  --image-id sha256:a1eebc1872ead4c304cd53e746f93d39c019dda37cdbf95c031fce4d77b7b6b0 \
  --dashboard-origin https://<operator-dashboard-hostname>
```

The JSON result checks TURN secret ownership, permissions, whether it existed
before installation and its absence from container inspection. It also
reads actual kernel cgroup memory/CPU limits. This check is not a claim that a
node administrator cannot read its own secret. Lifecycle restart, pressure
behaviour under the resource limits, logging and media acceptance remain separate
readbacks after installation. The helper requires root access for staging;
the actual backend and container runtime use the existing unprivileged user.

## Public endpoint and discovery remain separate

Next, qualify an explicit public manifest with operator-controlled TLS,
bounded firewall ports and temporary credentials. Keep the dashboard's
443 port private; a separately exposed listener can serve transport and
credentials. The existing unauthenticated KithMoot credential issuer is
not an invitation gate: CORS and rate limiting do not provide eligibility.
Do not expose it unchanged as a private credential service.

The current node uses journald for containers and low-level firewall
logging. These settings were read, not altered. Do not claim zero host
logging, zero metadata processing or verified hosting-provider retention.
No persistent call-log default remains a requirement awaiting deployment
readback, including wrappers, crash handling and certificate renewal.

There is still no shared signed transport-discovery implementation, no
announcement published and no default client service changed. See the
[endpoint plan](archy-call-endpoint-plan.md) for the remaining PKI, network,
media, physical GrapheneOS and independent substitution gates. Prior
intermittent native media stalls are not repaired by these socket tests.

## Legal-cover readback

The intended general distribution model remains software and protocols,
with independently installed and managed operator services. This particular
qualification node is owner-controlled, and delegated SSH work is real
operational access. Existing owner-authorised SSH access remains in place;
no new SSH key or remote management agent was installed. Node ownership,
update control and withdrawal must be recorded before claiming independent
third-party operation.

The [GB law note](https://github.com/forgesworn/jurisdiction-kit/blob/main/law/gb/online-services.md)
was verified overall 28 September 2026, review due 28 March 2027, with
section 2.11 updated 23 October 2026. The access-facility distinction is
recorded `[P]`; application to actual deployments and the combined offering
remains `[U]`. Project qualification does not establish the household or
internal-business exemption. Public hosting, issuer eligibility, discovery
operation and the underlying application service require their own factual
assessment. No public-service deadline or fee is assigned by this staging
and disposable loopback test.

Task-local Docker image and private build/archive files were removed after
recording their checksums. The node's verified image and small private install
bundle are intentionally retained for the authenticated installation step.
No new test service remains running. Existing apps, source checkouts and
shared build caches were preserved. No push or merge was performed.
