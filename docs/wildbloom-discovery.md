# Opt-in public Wildbloom service discovery

Public discovery covers paid storage and explicitly public free/open mirror
shelter. Private owner/friend nodes remain unpublished. A service listing does
not enable sales, guest mirrors or new write authority. Operator payments stay
direct; ForgeSworn provides software and does not take custody or list a seller
on their behalf.

## Package prerequisite

The discovery feature is in native
[`wildbloom-node` PR 51](https://github.com/forgesworn/wildbloom-node/pull/51),
merged as `b9a7cf48752037fe3588e62ec3a6a12aaebf7ee5`. The public browser supports
it in [Wildbloom PR 90](https://github.com/forgesworn/wildbloom/pull/90), merged as
`bb082787a7da0bd18dc6c640364f06c5253f5bf3`. The shared contract is published as
`402-announce` 2.3.0. This is a versioned kind 31402 extension, not a ratified
NIP interoperability claim.

**The current Archipelago package pins predate native discovery.** Its installed
container and dashboard do not gain this feature from a documentation or public
browser update. Before enabling it on a packaged node, prepare and validate a
new pinned Node image and manifest, including the existing sales-capacity
patches, backup/restart/restore checks and exact installed-image verification.
Do not add an unknown flag to the current production image or replace the
writer over a live storage/checkout volume. This runbook enables nothing and
does not change the packaged pins, owner reserve or existing operator settings.

The Archipelago capacity patches impose an extra aggregate paid-sale ceiling
to preserve owner space. Upstream discovery observes the upstream quota and
commitment rules. A future packaged integration must also use the patched
ceiling when reporting paid availability; it must not advertise accepting
capacity that its checkout will refuse. Keep that packaging gate separate from
the verified upstream feature and public-browser deployment.

For an independently installed upstream-compatible daemon, follow the native
[configuration and transport runbook](https://github.com/forgesworn/wildbloom-node/blob/main/docs/SERVICE-DISCOVERY.md)
with the steps below.

## 1. Choose what to make public

Choose paid storage, free mirror shelter, or both. Keep private owner/friend-only
nodes without a service profile. Free shelter requires explicit open-shelter
and mirror transport settings. It accepts authorised BUD-04 mirrors, refuses
unknown users' direct uploads, and stores guest copies with best-effort,
evictable retention. Paid storage requires its separate enabled checkout profile.
Existing sales controls and private order recovery remain separate.

Choose a stable public listing identifier, operator name/about text and exactly
the origin used by this daemon. Direct publication requires trusted public
HTTPS, not a LAN/VPN/private-IP origin. A Tor node uses its checksum-valid v3
onion origin. Prices, rails, retention/refund terms and coarse availability are
derived from the running node; do not copy them into a second public profile.
An accepting snapshot reserves nothing. A fresh quote still has to atomically
reserve paid capacity before offering payment.

## 2. Prepare HTTP inspection first

Create an ordinary private service profile (0600 on Unix) at an absolute path
outside the blob store. Use the native runbook's profile example with:

- a dedicated service public key, separate from owner, friend, buyer, payment
  and Archipelago's internal node identity;
- exactly the canonical public origin, including its trailing slash;
- explicit HTTPS browser origins that may inspect it, for example the public
  Wildbloom browser or the chosen packaged app origin;
- `withdrawn: false` and `announcement: null`.

Pass `--service-profile /absolute/private/service-profile.json` or the matching
`WILDBLOOM_SERVICE_PROFILE` environment variable only to a compatible daemon.
With `announcement: null`, HTTP inspection is enabled without signing or relay
connections. Verify `GET /services/v1` reports this dedicated key, listing,
origin, current timestamp, expiry, service types and actual admission state.
It must be JSON with `Cache-Control: no-store`. Confirm an unknown signer still
cannot directly upload to free shelter and paid users still need an allowance.

## 3. Configure publication deliberately

Replace `announcement: null` only after reviewing what the listing discloses:
public key, origin, public policy/price text, coarse availability and timing.
It must carry no owner/friend lists, customer keys, file hashes, private payment
records, recovery keys or precise physical capacity/usage.

Use an absolute external-signer executable. It receives one bounded unsigned
event through stdin and returns the exact signed event through stdout. Keep
key material in the signer; never put it in the profile, arguments, shell
history or logs. Choose a private durable publisher state directory separate
from the blob store and mount it explicitly if using a container. Preserve it
through restart; one process holds its lock.

Choose at most eight relays yourself. For `transport: direct`, enable `--no-tor`,
configure no mirror proxy and supply approved public socket-address pins for
every WSS relay. TLS still verifies its hostname; refresh pins deliberately.
For `transport: tor-only`, use the daemon's managed Tor or its explicit loopback
`socks5h` mirror proxy and empty address-pin lists. Proxy refusal must fail
closed: no local DNS and no direct fallback. No relay AUTH or automatic relay
selection is supported.

Defaults refresh every 30 minutes, expire after two hours and limit state-change
publication to once per five minutes. Only an exact NIP-01 `OK` with the event
ID and boolean `true` counts. Review accepted/configured relay counts; a partial
acknowledgement is not proof all relays stored the event or will serve it.

## 4. Check discovery as a separate client

In a fresh compatible Wildbloom page, configure your own relays and choose
**Find storage services on my relays**. Selection must contact no node.
Explicitly load current terms and verify the service key, listing and origin
match the signed announcement. Free results must say mirror-only, best-effort
and evictable. Paid results must show current terms and the actual
`wildbloom-checkout-v1` flow, not L402/x402/Cashu middleware.

Choosing a checked paid node, loading offers, obtaining a fresh private quote
and approving payment are separate actions. Changed prices or identities must
clear old checkout state and consent. Follow the existing
[operator purchase/restart/refund runbook](wildbloom-operator-runbook.md) for
an explicitly agreed buyer test. The directory and MCP integrations do not
automatically buy storage or establish durable retention.

## 5. Exercise withdrawal, expiry and restart

Confirm full/paused/unknown snapshots cannot be mistaken for new accepting
capacity. Observe a newer withdrawn event, then replay an older accepting one:
the same client session must keep the newer watermark. Repeat after a failed
relay query. A fresh client cannot detect a newer event its relays omit.

Graceful shutdown attempts a newer withdrawal before Tor stops. Abrupt failure,
signer failure or relay refusal uses signed expiry as the fallback. Setting
`withdrawn: true` withdraws discovery only: it does not cancel allowances,
erase files, stop the configured writer, reconcile payments or refund customers.
Restart must preserve the exact signed publisher state and publish strictly
newer records without bypassing the five-minute limit. A backwards clock or
corrupt/rebound state must refuse publication.

Keep the private service profile, publisher state and signer configuration in
the operator's recovery plan alongside the existing paired storage/checkout
backup. They are distinct from public browser event exports. Do not restore an
old publisher/checkout ledger over newer live state.

Record source/image versions, service types, transport mode, acknowledgement
counts and the outcomes of capacity, withdrawal/expiry, restart and retrieval
checks. Keep credentials, customer/payment records, file/recovery metadata and
raw packet captures private. Controlled fixture tests cover the shared contract,
browser consent, two-daemon free-mirror admission and refused SOCKS routing;
live relay retrieval, real Tor and independent wallet/mint settlement remain
separate acceptance evidence.
