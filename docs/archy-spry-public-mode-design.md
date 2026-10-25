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

## 1. Profile: a second, standard-profile instance

| Option | Verdict |
|---|---|
| Switch the one instance to standard profile | Rejected. Loses the FIPS mesh the 24 October delivery depends on; a paired node will not start, since `S lib.rs:559-561` refuses a stored transport endpoint without a peer network; strangers share the owner's 32-allocation pool (`S lib.rs:390-397`) |
| Allow public in private-node profile | Rejected. Private allocations sit on a loopback alias with the peer bridge (`S mesh.rs:81-86`); public relaying would put a second relay inside the process holding the peer identity and pairings |
| Separate `spry-public` package, standard profile | **Recommended** |

The separate instance has its own `generated_secrets` entry, so its advert key
(`S lib.rs:527-530`) differs from the private mesh identity (`S mesh.rs:71`),
plus its own `/data`, caps and container. IP address and hostname still link
the two; the owner wording should say so.

Port collisions:

- The standard profile hard-codes `:3478`, `:5349` and `49160:49191`
  (`S lib.rs:385-389`, `413`), and client rule 4 allows only advertised ports
  3478, 5349 or 443 (`docs/public-mode.md:177-184`). The public instance must
  hold 3478 and 5349.
- The private instance binds `{{HOST_IP}}:3478` (`manifest.yml:17`;
  `S node.rs:356`). Its port can move: `SPRY_TURN_PORT` takes any port ≥1024
  (`S node.rs:305-308`) and its URLs go to paired devices inside the encrypted
  descriptor (`S node.rs:396-399`), outside rule 4. Blocking the move: the
  private `turns:` port is fixed at 5349 (`S node.rs:407`) and the app gate's
  TURN-TLS relay accepts only upstream 3478 (P0025 line 189; classification
  lines 68-72).
- Firewall rules are keyed to `package_id == "spry"` (P0033 line 19) with a
  fixed list already opening `49160:49191/udp` (P0025 lines 300-306). The
  public package needs its own named rules and relay range so each uninstall
  removes only its own.
- Netbird on 3478 is stated in the brief, not verified in this checkout
  (P0033 line 78 only mentions a netbird deploy). Pre-flight refuses if any
  needed port is held.

Spry upstream therefore needs standard-profile settings for listen ports,
relay range and caps, and a private-profile TLS port.

## 2. Reachability prerequisites

| Requirement | Package checks and refuses | Package tells the owner |
|---|---|---|
| Public IPv4 | Owner-typed `SPRY_PUBLIC_IP` passes `public_v4` (`S lib.rs:315-327`, already rejecting 100.64/10 and private ranges) and equals `public_host`'s A record via the node's own resolver | Compare with the router's WAN address; a private or 100.64 WAN address means CGNAT and public mode cannot work |
| Ports | Needed ports free on the bind address; firewall rules added and read back | Forward 3478 udp/tcp, 5349 tcp, the relay range one-to-one, and external 443 to the credential front |
| Credential URL | `SPRY_PUBLIC_URL` exactly `https://<public_host>`, no port. Refuse if `public_host` is unset, since `{{PUBLIC_HOST}}` then renders `{{HOST_IP}}` (P0012 header). Spry checks only when relays are set (`S lib.rs:543-551`), so the package always checks | The DNS name is theirs |
| Certificate | Covers `public_host`, trusted, key pairs. Spry reads `/data/tls/*.pem` at start (`S lib.rs:408-419`) | Issuance and renewal are theirs; renewal restarts Spry and drops allocations (`archy-spry-public-20261023.md:102-106`) |
| External reachability | Not checkable from the node: hairpin is not evidence (`archy-call-endpoint-plan.md:37`) and ForgeSworn runs no probe | Run a relay-only ICE test from a phone on mobile data |

**The 443 front is the main new work.** Spry's HTTP binds loopback only
(`S lib.rs:569-571`), today's gate exposure carries a port (`manifest.yml:16`,
`33`) and the dashboard's 443 stays private (`archy-spry-public-20261023.md:27`).
A new Archy patch adds a dedicated gate listener that answers SNI for
`public_host` only, serves only `POST`/`OPTIONS /v1/public/credentials` (404
otherwise) and appends `X-Forwarded-For`; the owner forwards external 443 to
it. The per-source limit keys on the right-most entry (`S lib.rs:104-118`); no
patch here shows the gate setting that header, only `x-forwarded-proto`
(P0006 line 1184). Without it every stranger shares one 6-per-minute bucket.
A direct-public-IP node has 443 taken by the dashboard: unsupported in v1.

## 3. The owner-facing switch

Settings → Public call relay, following patch 0015, which renders settings
into the manifest environment at apply time (P0015 line 514). Off by default.
Turning it on needs a tick on:

> Make this relay public. Anyone on the internet can get credentials and relay
> call traffic through your node and your connection. You become the operator
> of a public service, responsible for it under the law where you and its
> users are. ForgeSworn does not run, list, approve or monitor it and cannot
> turn it off for you. Your node processes strangers' IP addresses.

Advert relays start empty; the owner types one to four `wss://` URLs. Empty
means public but unlisted (`docs/public-mode.md:35`). Spry's example list
(lines 41-48) may appear as unselected text, labelled as run by others and
unchecked. Region and note are optional and validated by Spry
(`S public.rs:40-50`). The package writes no defaults for any of them.

"Off" needs care. The standard profile requires `SPRY_PUBLIC_URL` and
`SPRY_OWNER_KEYS` at start whatever `SPRY_PUBLIC` says (`S lib.rs:487`, `491`),
so installing `spry-public` already needs `public_host`. It binds 3478 as soon
as `SPRY_PUBLIC_IP` is public, again whatever `SPRY_PUBLIC` says
(`S lib.rs:360-372`). Settings therefore sets `SPRY_PUBLIC_IP` only on
switch-on and clears it on switch-off.

## 4. Limits and turning off

| Limit | Today | Proposed home default |
|---|---|---|
| Allocations total / per user / connections | 32 / 8 / 32, hard-coded (`S lib.rs:390-395`) | 8 / 2 / 16 |
| Bytes/s per allocation, both directions | 1,000,000 (`S lib.rs:396-397`): worst case about 256 Mbit/s | 125,000: about 8 Mbit/s |
| Issuance | 32/min, 6 per source, 256 sources, 3600 s logins (`docs/public-mode.md:84-95`) | Unchanged |
| Container | 128 MiB, one CPU (`manifest.yml:22-24`) | Unchanged |

Spry has no monthly volume quota; the owner weighs their ISP's terms.

Turning off: set `SPRY_PUBLIC=false` keeping the relays and restart once, which
publishes a withdrawal (`docs/public-mode.md:144-147`); then clear the relays
and `SPRY_PUBLIC_IP`, remove the front and firewall rules, and tell the owner to remove router
forwards. An advert a relay missed lapses within two hours (lines 145-149). A
graceful stop also withdraws, waiting up to 5 s (`S public.rs:24`; SIGTERM at
`S lib.rs:626-630`); Archy's `stop_timeout_secs` (P0028 line 85) must exceed
that, and its value is unverified here.

## 5. Out of scope

Anything that would make ForgeSworn a provider: hosted hostnames or
subdomains, tunnels, relays or TURN, a directory, index or ranked list (2.13
designs c and d), default advert relays, a reachability or STUN probe, ACME or
DNS services, telemetry. Also out: UPnP/NAT-PMP auto-forwarding (opening the
router stays a deliberate owner act), IPv6 (the relay address is IPv4,
`S lib.rs:329`), and KithMoot reading adverts, which has its own change gate
(`docs/public-mode.md:157-158`).

The law position is jurisdiction-kit `law/gb/online-services.md` 2.13 design
(a), where the publisher runs nothing (lines 468-470, 569, 607-610). Forwarding
for unrelated users is a separate operating role (2.11, lines 389-391) and the
TURN access-facility application is `[U]` (lines 326-332). That role and its
data-protection and communications duties (3, 4.1, 5) sit with the owner.

## 6. Gates before building

- **Conventions:** a dated `docs/acceptance-*.md` and JSON receipt under
  `docs/evidence/`, scripted, browser and real-node evidence kept separate,
  no claim beyond the receipt. Tests extend `tests/test_spry_*.py`
  (`test_spry_public.py` covers only the lab promotion). `scripts/validate.sh`
  and both image architectures pass.
- **Soundness review:** independent security review of the front, header
  handling, firewall ownership, instance isolation and refusals before steps 4
  and 6 merge; legal-cover readback in the acceptance doc.
- **Fixture:** a disposable host with `SPRY_LOCAL_TEST` fixture relays
  (`S lib.rs:531-535`); no adverts on public relays, no ForgeSworn hostname.
  The `demo.forgesworn.dev` instance (`archy-spry-public-20261023.md:12`)
  never gets public mode.
- **Owner's node:** stays private. No change to it, including the pin bump or
  port move, without the owner's explicit go.

## Build plan

1. **spry-turn:** standard-profile settings for listen, TLS and relay ports
   and caps, bounded validation; private-profile TLS port. Defaults unchanged.
2. **archipelago-apps:** re-pin Spry to a `main` commit with step 1;
   re-qualify the private package with `SPRY_PUBLIC` unset, new image tag.
3. **archipelago-apps patch:** configurable TURN-TLS upstream port in the gate;
   per-package firewall rule sets.
4. **archipelago-apps patch:** public credential front (443 target, SNI and
   path allowlist, `X-Forwarded-For`).
5. **archipelago-apps:** `apps/spry-public` manifest, off by default, own
   secret, volume, relay range and caps; private-package revision on
   alternative ports; tests.
6. **archipelago-apps patch:** Settings → Public call relay: switch, wording,
   relay entry, pre-flight refusals, turn-off flow.
7. **archipelago-apps:** acceptance doc, receipt, soundness review, legal-cover
   readback.

## Open decisions for the owner

1. Move the private instance off 3478/5349 permanently in a new revision
   (preferred: fewer states to test) or only while public mode is on.
2. Ship public v1 with UDP/TCP only, leaving `turns:` until step 3 lands.
3. Direct-public-IP nodes: unsupported in v1, or a 443 SNI split shared with
   the dashboard.
4. The proposed home caps, and whether owners may raise them.
5. Whether Spry's example relays are shown at all.
6. Whether to add a privacy-notice URL to the advert (changes the kind 31478
   v1 schema upstream).
7. Whether `spry-public` is listed in the App Store or sideload only.
8. Final switch wording after a legal-cover pass.
