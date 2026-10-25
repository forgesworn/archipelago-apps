# Spry public mode on Archy: design

25 October 2026. Design only: nothing here is built, installed or switched on.
`S` means spry-turn at `origin/main` 0261719, path `crates/spry-service/src/`
unless another is given. `P00NN` means `upstream/patches/00NN-*.patch` here.

## Starting point

Spry's public mode (spry-turn `docs/public-mode.md`) is off unless
`SPRY_PUBLIC=true`, has no default relays, region or note (lines 32-39), and
refuses the private-node profile (lines 59-64; `S lib.rs:481-483`). The Archy
package runs that profile: `SPRY_PEER_INTERFACE=fips0`
(`apps/spry/manifest.yml:21`) selects it (`S node.rs:249-254`). It pins Spry
2efb051 (`apps/spry/Dockerfile:3`, `apps/spry/runtime/Cargo.toml:12-13`), which
is not an ancestor of `origin/main` and has no `public.rs`, so public mode
(cae40cb) is not in the shipped image.

## 1. One Spry per box: private or public

v1 runs one Spry instance. It is private (today's private-node profile and
mesh) by default. The owner may switch it to public, which restarts the same
package in the standard profile with `SPRY_PUBLIC=true`. Never both at once.

Allowing public relaying inside the private-node profile is rejected. Private
allocations sit on a loopback alias with the peer bridge (`S mesh.rs:81-86`),
so strangers would need a second relay inside the process that holds the peer
identity and pairings.

## 2. Separate state per mode

A plain profile switch fails on a paired node. After `authority.restore()`, a
stored `transport_endpoint` makes the standard profile refuse with "Private
relay settings require a peer network" (`S lib.rs:557-561`). The state file
defaults to `/data/pairings.json` (`S lib.rs:495-496`), and the package mounts
`/var/lib/archipelago/spry` at `/data` (`manifest.yml:30-31`). The secret is
`SPRY_TURN_SECRET` from the generated `spry-turn-rest-secret`
(`manifest.yml:11-14`).

Each mode therefore gets its own state, selected when the app is applied. The
precedent is patch 0015, which renders owner settings into the manifest
environment (P0015 line 514). The Settings patch extends that to two more
fields:

| Field | Private (default) | Public |
|---|---|---|
| Volume source at `/data` | `/var/lib/archipelago/spry` | `/var/lib/archipelago/spry-public` |
| `SPRY_TURN_SECRET` from | `spry-turn-rest-secret` | `spry-public-secret`, a second `generated_secrets` entry |
| Profile selector | `SPRY_PEER_INTERFACE=fips0` and the peer settings | Peer settings removed; `SPRY_PUBLIC=true`, `SPRY_PUBLIC_URL`, `SPRY_PUBLIC_IP`, relays, region, note |

Rendering a volume source and `secret_env` per mode is new orchestrator work
beyond 0015 and needs its own tests. In public mode the private directory is
not mounted at all. It stays on disk untouched, so even a bug reached by
strangers cannot read the private pairings.

What happens to paired apps and grants:

- **Private to public.** The public store starts empty, so it has no
  `transport_endpoint` and passes `S lib.rs:559-561`. Paired apps' grants
  live in the unmounted private file, so their credential requests are
  refused. Credentials already issued expire within five minutes
  (`apps/spry/README.md:67-68`).
- **Public to private.** The private file is restored as it was. Pairings and
  grants return with no re-pairing. The same secret derives the same mesh
  identity, so the "pairing identity has changed" refusal (`S node.rs:382-387`)
  does not fire. Room capabilities have a 30-day idle lease
  (`apps/spry/README.md:69-70`), so a public spell longer than that can expire
  idle room capabilities, though not the pairings themselves.
- **The public store** keeps its secret across spells, so the advert key stays
  stable and clients' watermarks stay valid.

The advert key derives from the public secret (`S lib.rs:527-530`), the mesh
identity from the private one (`S mesh.rs:71`): different keys, neither the
owner's signing key (`docs/public-mode.md:112-113`). IP address and hostname
can still link the modes. In public mode the UI (`apps/spry/public/`) shows
status instead of "Pair with KithMoot", so nothing pairs into the public store.

## 3. Ports

Public mode uses the ports the package already declares and opens:

- 3478 udp/tcp on `{{HOST_IP}}` (`manifest.yml:17`; `S lib.rs:329-331`,
  `385`), with `--public-ip` taken from `SPRY_PUBLIC_IP` (`S lib.rs:363-372`,
  `399-404`);
- relays on `49160:49191` (`S lib.rs:388-389`);
- TLS through the app gate's 5349 relay to 3478 (`manifest.yml:36`; P0025
  line 189). With `SPRY_TLS_GATE=true`, Spry adds `turns:<public_host>:5349`
  (`S lib.rs:435-441`).

Existing firewall rules cover these (P0025 lines 300-306) and rule 4 accepts
them (`docs/public-mode.md:177-184`). The gate picks the public certificate by
SNI and reloads renewals (P0012 header), so Spry needs no restart. Private
ports never move. Netbird on 3478 is unverified here (P0033 line 78 only
mentions a deploy); pre-flight refuses a foreign holder of any needed port.

## 4. Reachability and pre-flight

| Requirement | Package checks and refuses | Package tells the owner |
|---|---|---|
| Public IPv4 | Owner-typed `SPRY_PUBLIC_IP` passes `public_v4` (`S lib.rs:315-327`, which already rejects 100.64/10 and private ranges) and equals `public_host`'s A record via the node's own resolver | Compare it with the router's WAN address. A private or 100.64 WAN address means CGNAT, and public mode cannot work |
| Ports | No foreign holder; the rules above are read back | Forward 3478 udp/tcp, 5349 tcp and 49160-49191 udp one-to-one, and external 443 to the credential front |
| Credential URL | `SPRY_PUBLIC_URL` is exactly `https://<public_host>` with no port. Refuse if `public_host` is unset, since `{{PUBLIC_HOST}}` then renders `{{HOST_IP}}` (P0012 header). Spry checks this only when relays are set (`S lib.rs:543-551`) | The DNS name and certificate are theirs |
| External reachability | Cannot be checked from the node: a hairpin test is not evidence (`archy-call-endpoint-plan.md:37`), and ForgeSworn runs no probe | Run a relay-only ICE test from a phone on mobile data |
| Private calls | Shows the list below and needs a second tick | KithMoot pairing calls stop |

**The 443 front.** Spry's HTTP binds loopback only (`S lib.rs:569-571`). The
gate exposure carries a port (`manifest.yml:16`, `33`), and the dashboard's 443
stays private (`archy-spry-public-20261023.md:27`). A new Archy patch adds a
gate listener that:

- answers SNI for `public_host` only;
- serves only `POST`/`OPTIONS /v1/public/credentials` and returns 404 for
  everything else;
- appends `X-Forwarded-For`, which the per-source limit keys on
  (`S lib.rs:104-118`).

No patch here shows the gate setting that header today. Only
`x-forwarded-proto` appears (P0006 line 1184). The owner forwards external 443
to this listener. Nodes with a direct public IP have 443 taken by the
dashboard.

## 5. The owner-facing switch

Settings → Public call relay. Off by default. Turning it on needs two ticks:

> Make this relay public. Anyone on the internet can get credentials and relay
> call traffic through your node and your connection. You become the operator
> of a public service, responsible for it under the law where you and its
> users are. ForgeSworn does not run, list, approve or monitor it and cannot
> turn it off for you. Your node processes strangers' IP addresses.

> While public, your node's private calling is off. KithMoot pairing, room
> grants and the mesh link to other people's nodes stop until you switch
> back. Calls set up through the 24 October pairing flow will not use your
> node. Switching back restores your pairings.

Advert relays start empty, and the owner types one to four `wss://` URLs.
Leaving it empty means public but unlisted (`docs/public-mode.md:35`). Spry's
example list (lines 41-48) may appear as unselected text, labelled as run by
others and unchecked. Region and note are optional, and Spry validates them
(`S public.rs:40-50`). No defaults are written.

## 6. Limits and switching off

| Limit | Today | Proposed home default |
|---|---|---|
| Allocations total / per user / connections | 32 / 8 / 32, hard-coded (`S lib.rs:390-395`) | 8 / 2 / 16 |
| Bytes/s per allocation, both directions | 1,000,000 (`S lib.rs:396-397`): worst case about 256 Mbit/s | 125,000: about 8 Mbit/s |
| Issuance | 32 per minute, 6 per source, 256 sources, 3600 s logins (`docs/public-mode.md:84-95`) | Unchanged |
| Container | 128 MiB, one CPU (`manifest.yml:22-24`) | Unchanged |

There is no monthly volume quota, so the owner weighs their ISP's terms.

The private profile ignores `SPRY_PUBLIC_*` (`docs/public-mode.md:63-64`), so
switching straight to private would never publish the "public mode turned
off" withdrawal. Switch-off therefore runs in three steps:

1. Stop the public instance. A graceful stop withdraws the advert, waiting up
   to 5 s (`docs/public-mode.md:141-143`; `S public.rs:24`; SIGTERM handling
   at `S lib.rs:626-630`). Archy's `stop_timeout_secs` (P0028 line 85) must
   exceed that, and its value is still unverified.
2. Start once in the public state with `SPRY_PUBLIC` unset, relays kept and
   `SPRY_PUBLIC_IP` cleared. The relay does not start (`S lib.rs:363-372`),
   but a newer withdrawal is published after one second
   (`S lib.rs:599-612`). Stop after about 10 s.
3. Render and start private mode; tell the owner to remove router forwards.
   A missed withdrawal lapses within two hours (`docs/public-mode.md:145-149`).

## 7. Out of scope

Anything making ForgeSworn a provider: hosted hostnames, tunnels, relays or
TURN, a directory, index or list (2.13 designs c and d), default advert relays,
a reachability probe, ACME or DNS services, telemetry. Also out: UPnP
auto-forwarding, IPv6 (`S lib.rs:329`), and KithMoot reading adverts, which has
its own gate (`docs/public-mode.md:157-158`).

Law: jurisdiction-kit `law/gb/online-services.md` 2.13 design (a), the
publisher runs nothing (lines 468-470, 607-610). Forwarding for unrelated users
is the owner's own operating role (2.11, lines 389-391), with its
data-protection and communications duties (3, 4.1, 5).

## 8. Gates before building

- **Conventions:** dated `docs/acceptance-*.md` plus a JSON receipt in
  `docs/evidence/`, evidence kinds kept separate, no claim beyond the receipt;
  tests in `tests/test_spry_*.py` (`test_spry_public.py` covers only the lab
  promotion), `scripts/validate.sh`, both architectures. Round-trip test:
  private, public, private with pairings intact, plus the withdrawal.
- **Soundness review** of the front, header handling, state separation and
  refusals before PRs 3 and 4 merge; legal-cover readback.
- **Fixture:** disposable host, `SPRY_LOCAL_TEST` relays (`S lib.rs:531-535`),
  no public relays or ForgeSworn hostname. `demo.forgesworn.dev`
  (`archy-spry-public-20261023.md:12`) never gets public mode.
- **Owner's node** stays private; nothing changes on it, re-pin included,
  without the owner's go.

## Build plan

1. **spry-turn:** standard-profile settings for caps, with bounded validation.
   Defaults stay unchanged. Skip this PR if Spry's built-in caps are accepted.
2. **archipelago-apps:** re-pin Spry to a `main` commit with public mode,
   under a new image tag. Add the second generated secret and the public
   status in the UI. Re-qualify private mode unchanged.
3. **archipelago-apps (Archy patch):** the 443 credential front.
4. **archipelago-apps (Archy patch):** Settings → Public call relay. It covers
   per-mode volume, secret and environment rendering, pre-flight, both ticks
   and the three-step switch-off.
5. **archipelago-apps:** acceptance doc, receipt, soundness review and
   legal-cover readback.

## Later, if owners ask: both at once

A second package beside the private one would reuse PRs 2 to 5 (pin, front,
per-mode state, withdrawal flow) and add private port moves
(`S node.rs:305-308`, `407`), a configurable gate TURN-TLS port (P0025 line
189) and per-package firewall rules (P0033 line 19).

## Open decisions for the owner

1. The home caps above, whether owners may raise them, and therefore whether
   PR 1 is needed.
2. Whether Spry's example relays are shown at all.
3. Whether to add a privacy-notice URL to the advert. That changes the kind
   31478 v1 schema upstream.
4. Whether public mode is offered in the App Store package or only in a
   sideloaded revision.
5. The final wording of both ticks after a legal-cover pass.
6. Direct-public-IP nodes: unsupported in v1, or a 443 SNI split shared with
   the dashboard.
