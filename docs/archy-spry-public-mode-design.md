# Spry public mode on Archy: design

25 October 2026. Design only: nothing here is built, installed or switched on.
`S` means spry-turn at `origin/main` 58563c9, path `crates/spry-service/src/`
unless another is given; that directory is unchanged since 0261719, so the
line references hold. `P00NN` means `upstream/patches/00NN-*.patch` here.

## Starting point

Spry's public mode (spry-turn `docs/public-mode.md`) is off unless
`SPRY_PUBLIC=true`, has no default relays, region or note (lines 32-39), and
refuses the private-node profile (lines 59-64; `S lib.rs:481-483`). The Archy
package runs that profile: `SPRY_PEER_INTERFACE=fips0`
(`apps/spry/manifest.yml:21`) selects it (`S node.rs:244-254`). It pins Spry
2efb051 (`apps/spry/Dockerfile:3`, `apps/spry/runtime/Cargo.toml:12-13`), an
ancestor of `main` via e5bc49e (PR #14) but older than public mode (cae40cb).
The re-pin target is a `main` commit at or after 58563c9.

The ForgeSworn demo issuer (`operator/turn-issuer/`,
`docs/archy-spry-public-20261023.md`) was switched off on 25 October 2026:
service and timer disabled, firewall port closed, proxy configuration moved
aside, all reversibly. `demo.forgesworn.dev` never gets public mode.

## 1. One Spry per box: private or public

v1 runs one Spry instance, private (today's private-node profile and mesh) by
default. The owner may switch it to public, which restarts the same package
in the standard profile with `SPRY_PUBLIC=true`. Never both at once.

Public relaying inside the private-node profile is rejected: private
allocations sit on a loopback alias with the peer bridge (`S mesh.rs:81-86`),
so strangers would need a second relay inside the process holding the peer
identity and pairings. In the standard profile the relay itself refuses
private, loopback and other non-public peers (spry-turn `src/turn.rs:2128-2177`)
and relays IPv4 only (`src/turn.rs:1186`), so strangers cannot reach the
owner's LAN through it.

## 2. Separate state per mode

A plain profile switch fails on a paired node: after `authority.restore()`, a
stored `transport_endpoint` makes the standard profile refuse ("Private relay
settings require a peer network", `S lib.rs:557-561`). The state file defaults
to `/data/pairings.json` (`S lib.rs:495-496`), the package mounts
`/var/lib/archipelago/spry` at `/data` (`manifest.yml:30-31`), and the secret
is `SPRY_TURN_SECRET` from `spry-turn-rest-secret` (`manifest.yml:11-14`).

Each mode gets its own state, selected when the app is applied. Patch 0015 is
the precedent for rendering owner settings into the environment (P0015 line
514); the Settings patch extends it to the volume and secret:

| Field | Private (default) | Public |
|---|---|---|
| Volume at `/data` | `/var/lib/archipelago/spry` | `/var/lib/archipelago/spry-public`, created 0700 for the service user, since restore refuses group or world access (`spry-access/src/lib.rs:322`) |
| `SPRY_TURN_SECRET` | `spry-turn-rest-secret` | `spry-public-secret`, a second `generated_secrets` entry, materialised on upgrade by the self-healing generator |
| Profile | `SPRY_PEER_INTERFACE=fips0` and peer settings | `SPRY_PEER_INTERFACE` and `SPRY_PEER_BIND` both removed (either selects private, `S node.rs:244-254`); `SPRY_PUBLIC=true`, `SPRY_PUBLIC_URL`, `SPRY_OWNER_KEYS`, `SPRY_PUBLIC_IP`, relays, region, note |

Each data directory carries a mode marker naming its mode and secret file.
Apply refuses a mismatched directory and secret pair, because grant tokens are
re-derived from the secret on restore (`spry-access/src/lib.rs:355`) and a
wrong secret would silently void them. An existing private directory gets its
marker on the first apply after upgrade. In public mode the private directory
is not mounted; it stays on disk untouched.

The switch state (target mode, phase, and the rendered public environment that
switch-off step 2 needs) is persisted outside both data directories. Apply
renders from it, and an interrupted switch, including power loss, resumes from
its recorded phase on boot.

Paired apps and grants:

- **Private to public.** The public store starts empty, so it has no
  `transport_endpoint`. Paired apps' grants live in the unmounted private file,
  so their credential requests are refused; issued credentials expire within
  five minutes (`apps/spry/README.md:67-68`).
- **Public to private.** The private file is restored as it was: no
  re-pairing, and the same secret gives the same mesh identity, so
  `S node.rs:382-387` does not fire. Room capabilities have a 30-day idle
  lease (`apps/spry/README.md:69-70`), so a longer public spell can expire
  idle ones, not the pairings.
- The public secret persists across spells, so the advert key and clients'
  watermarks stay stable.

The advert key derives from the public secret (`S lib.rs:527-530`), the mesh
identity from the private one (`S mesh.rs:71`): different keys, neither the
owner's signing key (`docs/public-mode.md:112-113`). In public mode the UI
(`apps/spry/public/`) shows status instead of "Pair with KithMoot". The pairing
API itself stays and still needs an owner identity signature
(`manifest.yml:33`), so the UI change alone is not a gate.

## 3. Ports and origins

Public mode reuses the package's ports: 3478 udp/tcp on `{{HOST_IP}}`
(`manifest.yml:17`; `S lib.rs:329-331`, `385`) with `--public-ip` from
`SPRY_PUBLIC_IP` (`S lib.rs:363-372`, `399-404`), relays on `49160:49191`
(`S lib.rs:388-389`), and TLS through the gate's 5349 relay to 3478
(`manifest.yml:36`; P0025 line 189), advertised when `SPRY_TLS_GATE=true`
(`S lib.rs:435-441`). Firewall rules exist (P0025 lines 300-306) and rule 4
accepts these ports (`docs/public-mode.md:177-184`). The gate reloads renewed
public certificates by SNI (P0012 header). TLS connections share the gate's
global connection cap (P0025 line 204). Private ports never move. Netbird on
3478 is unverified (P0033 line 78); pre-flight refuses a foreign holder.

`SPRY_ALLOWED_ORIGINS` (`manifest.yml:21`, the KithMoot origins) does not
limit public credentials: the public path answers any `Origin` with
`Access-Control-Allow-Origin: *` (`docs/public-mode.md:69-72`), so any web
client can use them. Other paths keep the list.

## 4. Reachability and pre-flight

| Requirement | Package checks and refuses | Package tells the owner |
|---|---|---|
| Public IPv4 | `SPRY_PUBLIC_IP` passes `public_v4` (`S lib.rs:315-327`, rejecting 100.64/10 and private ranges) and equals `public_host`'s A record | Compare with the router's WAN address; private or 100.64 means CGNAT. A wrong IP in both DNS and the field passes and fails silently |
| Ports | No foreign holder; rules read back | Forward 3478 udp/tcp, 5349 tcp, 49160-49191 udp one-to-one, and 443 to 8443 |
| Credential URL | Exactly `https://<public_host>`, no port; refuse if `public_host` is unset, since it then renders `{{HOST_IP}}` (P0012 header); Spry checks only when relays are set (`S lib.rs:543-551`) | The DNS name and certificate are theirs |
| External reachability | Not checkable on the node; hairpin is not evidence (`archy-call-endpoint-plan.md:37`); ForgeSworn runs no probe | Relay-only ICE test from a phone on mobile data |
| Private calls | Second tick | Pairing calls stop |

**The 443 front.** Spry's HTTP binds loopback only (`S lib.rs:569-571`) and
the dashboard's 443 stays private (`archy-spry-public-20261023.md:27`). A new
Archy patch adds a gate listener on internal 8443/tcp, with its own ufw rule
under the `archipelago-spry` mark alongside P0025 lines 300-306. It is created
only in public mode and removed on switch-off. It answers SNI for
`public_host` only, serves only `POST`/`OPTIONS /v1/public/credentials` (404
otherwise), and overwrites `X-Forwarded-For` with the connecting address. The
owner forwards external 443 to 8443.

The per-source limit keys on the right-most entry (`S lib.rs:104-118`). The
3744 gate (`manifest.yml:33`, opened by P0025's rules) also reaches the
credential path, without the method filter. It must therefore overwrite the
header too; no patch shows either gate doing so today (only
`x-forwarded-proto`, P0006 line 1184). A CDN or proxy in front collapses every
stranger into one 6-per-minute bucket. Direct-public-IP nodes have 443 taken by
the dashboard.

## 5. The owner-facing switch

Settings → Public call relay, off by default, needs two ticks:

> You will run a public relay. Anyone on the internet can get credentials and
> relay call traffic through your node and connection. You run it, not
> ForgeSworn, and an individual can be a service provider. Whether a public
> relay brings legal duties is unresolved, so you may have duties where you
> and its users are. Your node handles strangers' IP addresses, and you owe
> them a privacy notice. Whether a pseudonym is enough to name yourself is an
> open question. Your hostname and IP address are published to the relays you
> choose and cannot be recalled; those relays may keep copies. Your node,
> its proxy and system logs may record connections: [INPUT: retention].
> ForgeSworn does not run, list, approve or monitor it and cannot turn it off.

> While public, private calling is off. KithMoot pairing, room grants and the
> mesh link to other people's nodes (the 24 October pairing flow) stop until
> you switch back, which restores your pairings.

The wording never says "no logs". Advert relays start empty, and the owner
types one to four `wss://` URLs. Empty means public but unlisted
(`docs/public-mode.md:35`). The Archy UI and docs show no example relay list
and never call any relay recommended, keeping 2.13 design (a) true. Region
and note are optional, and Spry validates them (`S public.rs:82-95`).

## 6. Limits and switching off

| Limit | Today | Proposed home default |
|---|---|---|
| Allocations / per user / connections | 32 / 8 / 32, hard-coded (`S lib.rs:390-395`) | 8 / 2 / 16 |
| Bytes/s per allocation, both directions | 1,000,000 (`S lib.rs:396-397`): worst case about 256 Mbit/s | 125,000: about 8 Mbit/s |
| Issuance | 32/min, 6 per source, 256 sources, 3600 s logins (`docs/public-mode.md:84-95`) | Unchanged |
| Container | 128 MiB, one CPU (`manifest.yml:22-24`) | Unchanged |

There is no monthly quota, so the owner weighs their ISP's terms.

The private profile ignores `SPRY_PUBLIC_*` (`docs/public-mode.md:63-64`), so
switch-off is three persisted phases:

1. **Graceful stop.** This withdraws, waiting up to 5 s
   (`docs/public-mode.md:141-143`; `S public.rs:24`; SIGTERM at
   `S lib.rs:626-630`). Archy's `stop_timeout_secs` (P0028 line 85) must
   exceed that; its value is unverified.
2. **One start in the public state.** `SPRY_PUBLIC` is unset; relays,
   `SPRY_PUBLIC_URL` (`S lib.rs:487`) and `SPRY_OWNER_KEYS` (`S lib.rs:492`)
   are kept. `start_relay` runs on every standard start (`S lib.rs:573-574`),
   so `SPRY_RELAY_IP` is rendered unparseable, making `node_address()` return
   None (`S lib.rs:329-330`) and binding nothing. A newer withdrawal follows
   after one second (`S lib.rs:599-612`); stop after about 10 s. Failures
   are silent (`S public.rs:157-158`), so "done" only means the time passed.
3. **Private mode.** Remove the 8443 front and its rule, then render and
   start private mode. The owner removes the router forwards. A missed
   withdrawal lapses within two hours (`docs/public-mode.md:145-149`).

## 7. Out of scope

Anything making ForgeSworn a provider is out of scope: hosted hostnames,
tunnels, relays or TURN, a directory, index or list (2.13 designs c and d),
default or example advert relays, a reachability probe, ACME or DNS services,
and telemetry. Also out: UPnP auto-forwarding, IPv6, and KithMoot reading
adverts, which has its own gate (`docs/public-mode.md:157-158`).

Law: jurisdiction-kit `law/gb/online-services.md` 2.13 design (a), where the
publisher runs nothing (lines 468-470, 607-610). Forwarding for unrelated
users is the owner's own role (2.2; 2.11 lines 389-391, `[U]`), as are privacy
duties (3.2 `[P]`) and operator naming (9 `[U]`). App stores as access
facilities (s.146(11)(b), 2.13 lines 597-603) carry information powers, not
provider duties, and their application is `[U]`. Listing text is ForgeSworn's
own content: no "public relay for anyone" and no relay names.

## 8. Building

Each step needs:

- **Conventions.** A dated `docs/acceptance-*.md` plus a JSON receipt in
  `docs/evidence/`, with evidence kinds kept separate and no claim beyond the
  receipt. Tests go in `tests/test_spry_*.py` (`test_spry_public.py` covers
  only the lab promotion). `scripts/validate.sh` and both architectures must
  pass. Round trip: private, public, private with pairings intact. The
  switch-off phases and power loss mid-switch are also tested.
- **Fixture.** A disposable host with `SPRY_LOCAL_TEST` relays
  (`S lib.rs:531-535`), no public relays and no ForgeSworn hostname.
- **Owner's node.** It stays private; nothing changes on it, including the
  re-pin, without the owner's go.

PRs:

1. **spry-turn:** standard-profile cap settings, bounded, defaults unchanged.
   Skip if the built-in caps are accepted.
2. **archipelago-apps:** re-pin at or after 58563c9 under a new image tag,
   with the second secret, mode markers and UI status. Re-qualify private mode
   unchanged.
3. **archipelago-apps (Archy patch):** the 8443 front with its rule, plus
   `X-Forwarded-For` overwrite on the 3744 gate.
4. **archipelago-apps (Archy patch):** Settings → Public call relay. Per-mode
   volume, secret and environment; persisted switch state with resume;
   pre-flight; both ticks; switch-off phases.
5. **archipelago-apps:** acceptance doc, receipt, and the
   `docs/archy-call-services.md` update below.

When this ships, `docs/archy-call-services.md` changes:

- replace "This package does not turn public mode on" and "nothing in this
  package lists, approves or ranks operators" (lines 166-167) with the opt-in
  two-tick switch and the owner's operator role;
- add the 443 front and the logging readback;
- record the demo issuer switch-off;
- record the example-list and App Store decisions.

## Later, if owners ask: both at once

A second package beside the private one would reuse PRs 2 to 5 (pin, front,
per-mode state, withdrawal). It would add private port moves
(`S node.rs:305-308`, `407`), a configurable gate TURN-TLS port (P0025 line
189) and per-package firewall rules (P0033 line 19).

## Gates

- **Soundness review, 25 October 2026:** sound with changes. All required
  changes are folded in: base commit and ancestry, switch-off step 2,
  power-loss resume, state markers and permissions, the named 8443 front,
  `X-Forwarded-For` on every gate, and recall in the first tick.
- **Legal readback, 25 October 2026:** passes with wording changes, folded
  in: no example relay list, origins in public mode, the demo issuer
  switch-off, the owner wording, App Store neutrality, and the call-services
  update list.

Remaining owner decisions:

1. Home caps, whether owners may raise them, and therefore whether PR 1 is
   needed.
2. Whether to add a privacy-notice URL to the advert. That changes the kind
   31478 v1 schema upstream.
3. App Store or sideload only for public mode (`[U]`).
4. Final wording of both ticks, including the `[INPUT: retention]` statement
   after the logging readback.
5. Direct-public-IP nodes: unsupported in v1, or a 443 SNI split shared with
   the dashboard.
6. Overriding the recommendation to show no example relay list (default: none
   shown).
