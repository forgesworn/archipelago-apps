# Spry installed through signer-authorised Archy access

23 October 2026. The loopback-only Spry lab is now installed and running on
the owner-controlled Archy qualification node. It was installed through
Archy's normal package API after approval on an enrolled signer. It is not
a public call service or a signed-discovery implementation.

## Result and evidence

The [receipt](evidence/archy-spry-installed-20261023.json) separates the gates:

- The installer uses the deployed signer availability/start/finish protocol.
  The first request reported a NIP-46 response timeout and stopped before
  installation. The owner explicitly requested one retry; that approval
  succeeded. Comparison codes, signer identifiers, cookies and credentials
  are not retained in the receipt.
- The normal `package.install` API installed the pinned Linux AMD64 image
  `sha256:a1eebc1872ead4c304cd53e746f93d39c019dda37cdbf95c031fce4d77b7b6b0`.
  Source remains `a76496bbcb60e637c0606c8da5919b5a3b2b3cf3`; no image rebuild
  or source upgrade was hidden in the configuration correction below.
- Actual kernel cgroups enforce 134,217,728 bytes of memory and one CPU
  (`100000 100000`). The generated unit retains both limits after restart.
- Archy generated the TURN root secret on the node: uid 1000, mode 0600.
  It is absent from container inspection output and survived restart.
  This does not prevent the node owner/administrator reading their secret.
- Independent Python wire clients, running as the node's unprivileged
  user, exchanged authenticated UDP and TCP traffic through the installed
  service before and after restart. Allocations stayed in 49160–49191 and
  were explicitly deallocated. No camera or microphone was used.
- The root filesystem is read-only. The service's own container log driver
  is `none`, stdout/stderr go to null and its systemd core-dump limit is zero.
  These settings survive restart. Twenty-seven package/installer boundary
  tests passed across the final increment (11 package and 16 installer).

The earlier 22 standalone socket tests on this node and the earlier browser
media tests belong to their own receipts. They are not newly run public
media tests or physical GrapheneOS acceptance for this installation.

## Runtime limit correction

The initial post-install check correctly refused readiness: the pinned
Quadlet renderer silently drops `memory_limit: 128Mi`, even though the API
manifest parser accepts it. CPU quota was effective, but `memory.max` was
`max` at the container and every relevant ancestor.

The package now uses `128m`, which that renderer converts to
`PodmanArgs=--memory=128m`. The running container was capped immediately,
then the frontend runtime manifest and promoted app manifest were corrected
and the backend reloaded. The generated unit and kernel were read back.
The corrected manifest checksum is
`d10a81f2b565c0f4e348f9b06cd3f5b637cc9a1f31683e4fb4f840ce5c079688`.

This is a package compatibility fix, not a fix to the upstream parser's
silent failure for other manifests. Parser acceptance alone did not prove
resource enforcement; the live gate found the difference.

## Scoped logging policy

The pinned manifest schema has no container log-driver setting. The node
installer therefore owns one app-specific Quadlet drop-in:

```ini
[Container]
LogDriver=none

[Service]
StandardOutput=null
StandardError=null
LimitCORE=0
```

It refuses an existing differing operator policy or symlink and changes no
other app. Archy still owns the generated main unit. The helper applies
the policy before final readiness verification. This is an installer-level
policy; installing the YAML alone does not configure this override.
An uninstall procedure must remove this task-owned drop-in alongside the app.

Host administration, Archy login diagnostics, systemd lifecycle messages,
firewall logging and hosting-provider behaviour are separate. Existing
host settings were preserved. This is not a claim of zero host logging,
zero metadata processing or verified provider retention.

## Authentication and lifecycle

The [installer](../node/install-spry-lab.py) supports `--signer-login`,
prints only the four-digit comparison code and uses an in-memory cookie
jar for the attempt binding and authenticated session. Availability,
challenge shape, approval and full session are checked before installation.
A denial/error/timeout stops the attempt; it never falls back to a password,
retries a signer prompt automatically or changes authentication settings.
The task session is logged out on exit.

The resource/logging correction used the owner's existing SSH administration
and affected this installed service. It did not require or request another
signer approval. Signer enrolment, password and TOTP configuration were not
changed by this increment. The owner's earlier password reset is recorded
separately and was an unnecessary detour caused by missing the deployed
signer support.

The backend and other existing apps remain running. The installed Spry lab,
node-owned secret, Podman secret, runtime manifest, generated service and
private logging drop-in are intentionally retained as the requested result.
Disposable wire clients, allocations and fixture directories were removed.
No task browser, Docker image or media test server was left running locally.
No push, merge, public firewall opening or discovery publication occurred.

## Remaining gates

- An explicit public manifest with trusted TURN TLS, certificate lifecycle,
  bounded host/provider firewall rules and private-peer restrictions.
- Operator-controlled temporary credential delivery. Do not expose the
  existing unauthenticated issuer unchanged as an invitation-only service.
- Separate-network browser group audio/video, refresh/rejoin, blocked UDP,
  received redacted sharing and operator replacement against that endpoint.
- Shared signed transport profiles and independent client verification,
  freshness, withdrawal/replay and opt-in publication. No mandatory publisher
  directory or automatic public forwarding was added.
- Physical no-Play GrapheneOS acceptance, the unresolved intermittent native
  media stall and the larger-call RelaySwarm/Sapflow forwarding design.

The legal-cover source remains jurisdiction-kit's GB note: verified overall
28 September 2026, review due 28 March 2027, section 2.11 updated 23 October
2026. This is owner-authorised operation of a private qualification service,
not proof of independent third-party operation. The access-facility distinction
is recorded `[P]`; its application to actual deployments and the combined
offering remains `[U]`. These technical gates do not establish an OSA exemption.
