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

The packaged integration pins this native source and applies the existing
sales-capacity patches. Image `wildbloom-node:0.3.5-b9a7cf4-2` uses the same
aggregate `max_paid_bytes` ceiling for new quotes and advertised paid availability.
The capacity read counts retained allowances and live new-sale holds, counting
renewals once, and also checks total store commitments. An exhausted ceiling
appears full even when physical owner space remains. Failed reads appear unknown.
Discovery discloses neither the ceiling nor precise usage. Existing holds remain
honourable after a ceiling reduction; a listing reserves nothing.

Installing a new image does not enable discovery or update existing installations.
Before replacing a writer, stop it, retain its whole matching storage/checkout
volume and private configuration, and verify restart, old-file recovery and exact
installed-image identity. Never run old and new writers against the same volume.
See the [upgrade instructions](wildbloom-upgrade.md). Publication, free shelter and
sales remain separate deliberate choices.

For an independently installed upstream-compatible daemon, follow the native
[configuration and transport runbook](https://github.com/forgesworn/wildbloom-node/blob/main/docs/SERVICE-DISCOVERY.md)
with the steps below.

## Prepare an operator manifest locally

`scripts/configure-wildbloom-discovery.py` uses Python 3 and PyYAML. It performs
no DNS lookup, signing, relay connection, deployment or payment. It writes a new
0700 output directory and 0600 profile/manifest files, refusing overwrites and
existing discovery configuration. Settings accept public keys only; signing
secrets are never generated or accepted.

```sh
python3 scripts/configure-wildbloom-discovery.py \
  --init-settings /private/operator/discovery-settings.json
```

Replace the synthetic public key, name, origins and service selection with your
own. Use a dedicated operator-controlled service key; the daemon refuses its
owner/friend keys. In your existing private Node manifest, change only the image
tag to the validated discovery image, preserving quota, checkout profile,
identity-derived environment, mounts and other operator settings. For paid
listings, prepare/enable your offer separately using the sales workflow first.
The helper never adds a checkout profile or changes capacity/prices.

```sh
python3 scripts/configure-wildbloom-discovery.py \
  /private/operator/discovery-settings.json \
  --manifest /private/operator/upgraded-node-manifest.yml \
  --output /private/operator/discovery-prepared
```

Default preparation preserves the manifest exactly and leaves `announcement`
null. To prepare HTTP inspection, use a new output directory and explicitly add
`--enable-inspection`. For free shelter, select `free` in `public_services` and
also add `--enable-free-shelter`: this deliberately enables signed guest mirrors
and direct public HTTPS mirror transport. Unknown direct uploads stay refused.
The profile lists all enabled services; it cannot hide enabled paid/free services
behind a partial selection.

An enabled manifest adds the separate bind
`/var/lib/archipelago/wildbloom-service:/service`. Create that host directory
0700, owned by the Archipelago service user, and install `service-profile.json`
there at 0600. The storage/checkout volume remains `/data`. Default catalogue
manifests do not contain this mount or service-profile environment entry.

For publication, choose 1–8 canonical public WSS relays with approved public
`IP:port` socket pins in `relays`, install your Linux-compatible external signer
at `/service/signer` (host `wildbloom-service/signer`), and set
`publication_reviewed: true` only after reviewing the public metadata and
transport. The signer must be executable, owned by the service user, use the
bounded JSON stdin/stdout contract and keep its key/configuration private.
No signer, secret, arguments or default relays are supplied by the package.
Use `--enable-publication` with a new output directory after the inspection
checks below. It also enables inspection; it never deploys the result.

The helper supports the package's direct HTTPS mode. Its publisher state is
`/service/publisher`, outside the blob store, and must persist through restart.
For Tor, use the separately documented native configuration and validate routing;
the helper refuses Tor/proxy overrides instead of silently changing them.

Applying a prepared manifest still requires the existing operator staging and
backup procedure. Do not use the default catalogue manifest over an operator's
private sales/discovery manifest. Dashboard sales controls on the new Node image
require the compatible backend described in the upgrade instructions.

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
