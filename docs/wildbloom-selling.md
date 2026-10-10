# Own storage and optional sales

Archipelago and Wildbloom provide self-hosted software. ForgeSworn does not run
the operator's node, provide the storage, list sellers, set prices or terms, or
collect customer payments. A person who enables sales becomes the storage
provider and is responsible for their own offer, customers, operation and legal
obligations. Payments go directly to that operator's configured receiver.

For a start-to-finish exercise using a clean node, the dashboard, a separate
buyer, the reference mint, restart, renewal, refund and paired backup, follow
the [independent operator runbook](wildbloom-operator-runbook.md). The remainder
of this document is the technical configuration reference, including the
manual CLI path.

The Archipelago browser package selects the node's configured public HTTPS
Blossom origin on port 3742. This is populated locally, without contacting the
storage service, a discovery relay or a payment issuer. The existing node signer
still needs an explicit connection and each upload still needs consent.

Changing the destination remains possible. **Use my Archipelago node** restores
the local choice and revokes any previous upload/signing consent. Tor-only mode
clears the HTTPS destination and disables that button. Pools still require
explicit selection of their independent destinations. A full or unreachable
node does not cause automatic uploads elsewhere.

This integration applies to the Archipelago-packaged web app. The separately
hosted public Wildbloom app does not automatically know which node you own.
Use its destination field to select your node explicitly.

## Prepare an LNURLcash offer

The patched dashboard now provides **Settings → Storage & selling** for the
supported packaged node. See the [dashboard guide](storage-selling-dashboard.md)
for editable defaults, capacity checks, private drafts, applying and pausing.
The CLI below remains available for manual provisioning; the dashboard will
not overwrite an existing manually provisioned checkout profile.

`scripts/configure-wildbloom-sales.py` prepares the private checkout profile and
an operator-specific Node manifest. It never deploys, sends notes, starts a
payment, opens public guest writes, or overwrites an existing configuration.
It requires Python 3 and PyYAML (also used by the manifest validator).

1. Create your own editable settings file outside the repository:

   ```sh
   python3 scripts/configure-wildbloom-sales.py --init-settings /private/operator/settings.json
   ```

   This local-only step creates a private file without enabling sales. Fill in
   your public node origin, allowed browser origins, capacity, price and terms.
   The origin must use the same `PUBLIC_HOST` configured in Archipelago; the
   browser app uses that host automatically. Include `https://PUBLIC_HOST:3743`
   in `browser_origins`. Other browser apps require their exact origins too.
2. Set `quota_bytes` to storage you can actually provide. Set
   `owner_reserved_bytes` to the portion customers must not consume. The
   remaining capacity is the aggregate ceiling for customer allowances and
   pending quotes, **not a separate allowance for every customer**.
3. Set the per-customer offer capacity, term, grace period and integer sat price.
   Capacity counts ciphertext, including encryption overhead. Delivery is
   operator-managed; `delivery_bytes` is not an enforced download meter.
   Fill in real sale/refund terms and increment `offer_revision` when changing
   published terms. A public email, Nostr key, URL or personal contact details
   are optional. Existing quotes retain their original terms.
4. Keep the suggested `lnurlcash-reference` issuer or deliberately select
   `moneyer-dev` for development. The packaged choices pin separate origins,
   endpoints and keys; arbitrary issuer URLs are refused.
5. Prepare the files with an explicit DNS lookup:

   ```sh
   python3 scripts/configure-wildbloom-sales.py /private/operator/settings.json \
     --resolve-issuer --output /private/operator/prepared
   ```

   Alternatively repeat `--issuer-ip PUBLIC_IP` to supply verified address pins
   yourself. TLS still verifies the selected issuer hostname; redirects and
   ambient DNS refresh are disabled by the receiver. Refresh pins deliberately
   if the issuer moves. The old `--moneyer-ip` and `--resolve-moneyer` spellings
   remain compatibility aliases. The output directory is 0700 and both files
   are 0600.

Sales are **disabled in this prepared manifest**. Setup starts with editable
suggestions: 200 GiB total, 100 GiB reserved for the owner, a 10 GiB customer
allowance for 500 sats per 30 days, and 7 days of recovery grace. The suggested
delivery allowance is 100 GiB per term, operator-managed. These are starting
values, not fixed prices, capacity promises or automatic disk allocations.

The operator sets every value for their hardware and service. Changes in the
settings file are used exactly; preparation does not silently restore defaults.
Changing a term or delivery allowance also requires updating its policy text.
Check available disk space and leave headroom for the operating system and other
apps before choosing a total quota. Creating defaults does not inspect the disk
or start the node. Existing installations keep their configuration until the
operator deliberately applies a prepared manifest and profile.

New settings select the LNURLcash reference mint at
`https://mint.lnurlcash.com/`. Its key is pinned to
`027f06257d0e9af2dbef2c1c64d03962a9240a65a987eb90b36000c64de34baa6d`,
observed through its [mint discovery document](https://mint.lnurlcash.com/.well-known/lnurlw/mint)
on 10 October 2026 and matched to the
[reference implementation](https://github.com/dni/lnurl-mint). Its note endpoint
is `/w` and mutation callback is `/w/cb`.

Moneyer remains available as the explicit `moneyer-dev` choice for tests and
development. Its discovery document describes it as a proof of concept and
warns users to expect loss of funds. Selecting it requires the additional
`moneyer_evaluation_accepted` setting after reviewing
[its terms](https://moneyer.dev/terms). Existing settings written before issuer
selection continue to mean Moneyer so an upgrade never reinterprets their IP
pins or pending payment recovery. Key or endpoint changes require explicit
review; this package does not silently trust new values.

## Install and enable deliberately

Build/publish both new package revisions before staging their manifests; local
code changes do not publish an image or update an installed node.

Place `checkout-profile.json` at
`/var/lib/archipelago/wildbloom-node/operator/checkout-profile.json` on the node.
The `operator` directory must be 0700, the profile 0600, both owned by the
Archipelago service user. It appears inside the existing storage bind at
`/data/operator/checkout-profile.json`. Never put receiving material into the
public app catalogue. Do not overwrite an existing profile/ledger casually.

The daemon creates private receiving state at `/data/operator/checkout`.
That ledger can contain spendable LNURLcash notes. Back up the **whole matching
storage and checkout state together with the daemon stopped**; keep the backup
private. Do not delete receiving state to retry an uncertain payment.

After testing the receiver and reviewing the selected issuer, set
`issuer_reviewed` to `true` in your private settings. If you deliberately select
Moneyer, also set `moneyer_evaluation_accepted` to `true`. Prepare a new output
directory with `--enable-sales`. This adds only the private profile path to the
manifest; the profile and assets are never embedded in it. Check that the
profile on the node exactly matches the new prepared profile before staging:

```sh
APP_MANIFEST=/private/operator/enabled/manifest.yml \
  scripts/stage-to-node.sh wildbloom-node
scripts/stage-to-node.sh wildbloom
```

The normal staging script still needs the operator's node access and dashboard
credentials. Its `APP_MANIFEST` override accepts the generated JSON-form YAML.
Save your private manifest and reapply/review it after catalogue or frontend
updates. A default catalogue manifest leaves checkout disabled; it does not
erase stored customer claims or receiving state.

For customers outside the LAN, the selected public hostname, trusted TLS and
port 3742 must be reachable from their devices. A working dashboard inside the
LAN does not establish public reachability. Do not expose the dashboard itself
merely to expose Blossom. The customer chooses your origin in Wildbloom,
connects a signer, reads your offer, approves its quote and provides an
exact-value note from the selected issuer. The node verifies and rotates that note before it
activates the allowance. Owner identities retain their existing access and do
not have to buy storage from themselves.

Lowering the sales ceiling does not revoke existing commitments. Already
reserved quotes can still settle; new quotes remain blocked until commitments
fit. Full paid capacity counts through the retention grace period. The ceiling
prevents new paid allocations taking the owner's portion; owner/friend data,
uncollected expired data and other host disk usage still consume real space.

`checkout-operator` is included in the Node image for the upstream documented
inspection/recovery commands. Stop the owning daemon before using the tool;
do not run concurrent writers or treat `refund_required` as an issued refund.
See [upstream checkout](https://github.com/forgesworn/wildbloom-node/blob/4474ce194888b039f14cf7001e2eab43305b2c9c/docs/CHECKOUT.md)
for the recovery profile and direct operator refund procedure.

## Packaging and acceptance

See the [local acceptance record](acceptance-own-node-sales.md) for completed
checks and the remaining operational inputs.

The two capacity patches in `apps/wildbloom-node/` apply to the exact Node
`4474ce1` and Shelter v0.5.0 (`c573ca3` tag, `a2847bd` source commit). They add an atomic customer allocation
ceiling and wire optional `max_paid_bytes` from the private profile into
checkout. Existing generic Shelter admission behaviour stays unchanged.
The container build applies both patches with `git apply --check`, uses the
patched lockfile and runs the checkout and storage tests. Replace these patches
with upstream release pins when that integration is released.

Required checks include the real packaged browser (own-node default, explicit
override, revoked consent, Tor and pool isolation), simultaneous quotes under
the sales ceiling, retained/renewed allowances, restart and owner writes.
The existing Node smoke test checks owner upload, stranger refusal and
persistent-volume upgrades. These are automated local/container checks, not
evidence of a physical Archipelago deployment or real Moneyer settlement.
