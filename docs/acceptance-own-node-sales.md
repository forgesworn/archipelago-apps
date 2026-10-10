# Own-node default and seller capacity acceptance

## 10 October 2026: reference issuer default

New Wildbloom selling configurations now select the LNURLcash reference mint at
`https://mint.lnurlcash.com/`. Its live discovery document was checked against
the packaged key and endpoints, and the packaged source identifies the public
reference implementation. Moneyer remains available as an explicit
test/development choice with its separate loss warning and acknowledgement.

Existing settings without an issuer field continue to deserialize as Moneyer.
The issuer is locked after checkout begins, so an upgrade cannot reinterpret
saved IP pins, pending notes, refunds or invoice recovery as belonging to a
different mint. The currently deployed test node therefore remains on its
operator-selected Moneyer configuration until a separate migration is designed
and accepted; this release does not claim a live payment through the reference
mint.

The dashboard and private configuration helper both keep sales disabled until
the operator chooses capacity, price and terms, reviews the selected issuer and
resolves or supplies public IP pins. The resolver accepts only the two packaged
issuer identifiers and never an operator-supplied hostname. The legacy
`wildbloom.storage.resolve-moneyer` RPC remains a fixed Moneyer-only alias for an
older cached dashboard.

Local acceptance covers the reference default and exact key/callback, legacy
Moneyer deserialization, issuer-change refusal after checkout starts, arbitrary
issuer rejection, the explicit DNS action, dashboard labelling, and the current
`wildbloom-node:0.3.5-4474ce1-2` compatibility pin.

[PR #23](https://github.com/forgesworn/archipelago-apps/pull/23) merged as
`2156a858963c80be4d5401333f43da6cf0b34693`. The immutable releases are
`backend-v1.9.0-alpha-p8` (SHA-256
`aa5d5023d6577aace06e82da07ebdf145a7b68173b35932c3c533827a846a6b2`)
and `frontend-v1.9.0-alpha-p8` (SHA-256
`ceb5d93757fa2c3c274c4b1f003ec214d6967e17ed2ad3d7c32dbaa9a90dea61`).
The final main revision passed the
[backend](https://github.com/forgesworn/archipelago-apps/actions/runs/38040995046),
[frontend](https://github.com/forgesworn/archipelago-apps/actions/runs/38040995090),
[validation](https://github.com/forgesworn/archipelago-apps/actions/runs/38040995035),
[published-service](https://github.com/forgesworn/archipelago-apps/actions/runs/38040995190)
and [image](https://github.com/forgesworn/archipelago-apps/actions/runs/38040995139)
workflows.

The p8 backend and frontend were installed on the live test node. The deployed
backend matches the release hash, nginx and the Archipelago backend are active,
and HTTPS answers successfully. The installer restarted the existing
`wildbloom-node:0.3.5-4474ce1-2` systemd container; it returned healthy on the
same data mount with all 17 blobs and 180,394 stored bytes. The seller settings
file is byte-for-byte identical to its pre-upgrade backup. It remains revision 5
with checkout started, sales enabled, and no issuer field, which p8 deliberately
interprets as the legacy Moneyer development issuer. No reference-mint quote,
note, payment, renewal or refund was created during this upgrade.

The packaged browser acceptance checked the reference default for a new
configuration, explicit Moneyer selection, desktop and mobile layouts, and the
draft/apply flow. After signing back in following the backend restart, the live
seller panel showed sales enabled with the retained 10 GiB quota, 5 GiB owner
reserve, 5 GiB customer offer, 500-sat price, 30-day term and 7-day grace. It
selected and labelled Moneyer as the test/development mint, displayed the loss
warning, and locked the issuer because checkout had started. The reference mint
remained available as the alternative for a new configuration. This was a
read-only browser check: no draft, apply, quote or payment action was submitted.

## 10 October 2026: commerce lifecycle release and live acceptance

The complete own-node commerce lifecycle is now shipped. Wildbloom Node
[PR #48](https://github.com/forgesworn/wildbloom-node/pull/48) added private,
address-bound LNURLcash refunds with durable and idempotent operator recovery.
Wildbloom [PR #84](https://github.com/forgesworn/wildbloom/pull/84) added customer
allowance, renewal and refund receipts. Archipelago apps
[PR #19](https://github.com/forgesworn/archipelago-apps/pull/19) packaged those
revisions and the dashboard recovery controls. The frontend release source was
temporarily unavailable upstream; [PR #20](https://github.com/forgesworn/archipelago-apps/pull/20)
therefore added a hash-pinned fallback that reused only byte-identical framework
inputs and rebuilt the dashboard from the current source. Wallet of Satoshi's
LNURL-pay address delegates invoice creation to a different public HTTPS origin.
Wildbloom Node [PR #49](https://github.com/forgesworn/wildbloom-node/pull/49)
supports that standard deployment while independently resolving, filtering and
pinning each origin, refusing redirects and requiring invoice verification to
remain on the callback origin. Archipelago apps
[PR #21](https://github.com/forgesworn/archipelago-apps/pull/21) packages that
exact revision in the node image and recovery tool.

| Released component | Accepted identity |
| --- | --- |
| Wildbloom Node source | `4474ce194888b039f14cf7001e2eab43305b2c9c` |
| Wildbloom source | `d7dfadb33b7eedd8b180e2165150365f91299274` |
| `wildbloom-node:0.3.5-4474ce1-2` | `sha256:6106ddb70d43071d500e71fd3052c8e59ad03336dac8f67c34bd205e4a538056` |
| `wildbloom:0.0.1-d7dfadb-2` | `sha256:d0070c13882f577387c46fa33286a327644ebd5f72a20df13940ffc7ab7e7277` |
| Backend release | `backend-v1.9.0-alpha-p7`, SHA-256 `792a17618c46d29b949e8586fac2ba24f8e9f3f8400293f8c59a38f3930ec32f` |
| Frontend release | `frontend-v1.9.0-alpha-p7`, SHA-256 `6211c116ee309ecb4f7be0d4d73be7cbd6db7be95073fe963c8ffee79628fd3f` |

The published-image customer journey passed purchase, encrypted upload, daemon
restart, full-read audit and renewal in
[run 38004200702, attempt 2](https://github.com/forgesworn/archipelago-apps/actions/runs/38004200702/attempts/2).
The final main release also passed the
[frontend](https://github.com/forgesworn/archipelago-apps/actions/runs/38030185852),
[backend](https://github.com/forgesworn/archipelago-apps/actions/runs/38030185880),
[validation](https://github.com/forgesworn/archipelago-apps/actions/runs/38030185875)
and [image](https://github.com/forgesworn/archipelago-apps/actions/runs/38030185894)
workflows.

The callback compatibility release subsequently passed main
[validation](https://github.com/forgesworn/archipelago-apps/actions/runs/38034292493),
[frontend](https://github.com/forgesworn/archipelago-apps/actions/runs/38034292572),
[image](https://github.com/forgesworn/archipelago-apps/actions/runs/38034292489)
and [backend](https://github.com/forgesworn/archipelago-apps/actions/runs/38034292491)
workflows. The Node change itself passed all eight jobs in
[run 38032264546](https://github.com/forgesworn/wildbloom-node/actions/runs/38032264546).

The live p7 upgrade preserved all 17 stored blobs, totalling 180,394 bytes, with
exact pre/post hashes. The checkout ledger migrated from schema 1 to schema 2,
passed its integrity check and retained the active allowance. An authenticated
Chrome session showed the new browser package running and selected the local
Archipelago node as the default storage destination.

A real 500-sat Moneyer renewal retained the stable 5 GiB allowance and extended
`writes_until` exactly from `2026-11-08T20:33:44Z` to
`2026-12-08T20:33:44Z`. Signed recovery returned the same active receipt after a
forced daemon restart. The customer receipt contained no bearer note.

A separate real 500-sat payment exercised the automatic-refund path. With the
writer stopped and a byte-verified full-volume backup retained, the acceptance
harness expired only that signed reservation before submitting its valid
Moneyer note. The receiver rotated the note, activation failed as intended, and
the signed order became `refund_required` without an allowance. The first
pre-fix recovery request refused Wallet of Satoshi's delegated callback before
creating an invoice. After deploying PRs #49 and #21, the first request durably
recorded one pending refund and returned an uncertain result. The operator
verified that durable state before retrying; the idempotent retry reused the
same invoice and completed the 500,000 msat refund. The signed customer result
is `refunded` with a completed refund, no allowance receipt and a refund
timestamp. It survived a forced daemon restart. The pre-existing renewed 5 GiB
allowance retained the same identifier, capacity and expiry timestamps.
The Wallet of Satoshi recipient independently confirmed arrival of the full
500-sat refund.

The callback image upgrade preserved all 17 blobs and 180,394 bytes through a
fresh verified offline backup. Both the persistent sideload manifest and the
installed-image record were updated before the Archipelago backend restarted;
the reconciler then retained the new image and exact digest. This matters on an
existing sideloaded installation: changing only the generated Quadlet unit is
temporary because the management daemon regenerates it from persistent app
state.

During verification, an ordinary `sqlite3` connection was accidentally opened
against the live WAL database. That unlinked the writer's WAL and SHM directory
entries. The open descriptors were copied to a private recovery location, the
writer was stopped cleanly, its checkpointed database was verified, and the
node was restarted with schema 2, two active orders and one quoted order intact.
The live process now holds non-deleted database, WAL and SHM files. Operators
must stop the writer before using general SQLite tools; the dashboard's bounded
read-only sales projection is the supported live inspection path.

Private signer material, bearer notes, order references, refund destinations,
backups and recovery journals are excluded from the repository.

## 9 October 2026: deployed setup and customer acceptance

The own-node integration and editable storage/selling dashboard are deployed on
the test node. Selling remains optional; it is deliberately enabled on this test
node with an operator-selected 500-sat, 5 GiB, 30-day offer and 7-day retention
grace. Personal storage requires no customer contact or refund terms; each
operator supplies their own details if they choose to sell. The earlier
local-only evidence is retained below.

| Scope | Verified result |
| --- | --- |
| Packaged own-node browser | Authenticated browser selected the configured node; Tor and pool modes cleared or disabled the own-node path as appropriate |
| Live dashboard | Authenticated draft save and reviewed apply passed; the node retained its 10 GiB quota and all 16 existing blobs byte-for-byte |
| Earlier Moneyer payment and refund, private test node | A 50-sat received note activated a 1 MiB allowance; paid upload and exact retrieval passed before the full refund exercise |
| Enabled seller acceptance | A separate 500-sat Moneyer note activated a 5 GiB allowance; a 65,608-byte encrypted blob was uploaded, fetched and decrypted to the exact 129-byte source |
| Payment recovery | The same receipt and file survived restart; a paired storage/checkout backup opened in a network-disabled clone and returned the same active receipt and exact file without another payment |
| Enabled seller restart | The active 5 GiB allowance and encrypted blob survived a real daemon restart; both databases passed integrity checks and the store retained all 17 blobs (180,394 bytes) |
| Manual refund | One journalled refund returned the full 50 sats; Moneyer reported settlement, the received note was retired, and the recipient independently confirmed receipt |
| Optional-selling frontend | The dashboard keeps price, capacity, duration, grace and delivery limits editable; public support contact remains optional |

Deployment evidence is recorded in [PR #6](https://github.com/forgesworn/archipelago-apps/pull/6)
and [PR #9](https://github.com/forgesworn/archipelago-apps/pull/9).
Private test keys, notes, order references, refund destination and journals are
not repository artifacts. The refund endpoint did not return a payment preimage:
issuer settlement and recipient confirmation are recorded separately from
cryptographic proof. This was an operator-directed refund, not a shipped
automatic refund feature or an interruption-recovery test.

Before the enabled-seller restart, the live checkout process was found to hold
an uncheckpointed SQLite WAL whose directory entries had been removed. The
operator stopped the writer, recovered the database and WAL through its open file
descriptors, verified the active and quoted orders in an isolated copy, then
installed a checkpointed database while retaining a private recovery copy. The
post-restart checkout and storage databases both report `integrity_check=ok`.

The repeated-quote fix from [Wildbloom PR #83](https://github.com/forgesworn/wildbloom/pull/83)
was published and deployed through
[Archipelago apps PR #17](https://github.com/forgesworn/archipelago-apps/pull/17).
The [main image run](https://github.com/forgesworn/archipelago-apps/actions/runs/37992126444)
built and smoke-tested both packages, pushed the new browser tag and left the
already-published storage tag unchanged. The subsequent
[published-image customer journey](https://github.com/forgesworn/archipelago-apps/actions/runs/37993127533)
passed purchase, encrypted upload, restart, full-read audit, capacity refusal,
renewal and the dashboard's private sales projection using synthetic funds.

On the test node, the dashboard lists browser version `0.0.1-1d2a7c3-2` as
running. An authenticated launch returned the new browser asset and visibly
selected `https://demo.forgesworn.dev:3742` as the default Archipelago node. The
browser-only restart left the storage daemon process unchanged. Afterwards the
active 5 GiB allowance, all 17 blobs and both database integrity checks remained
intact, and a fresh download of the paid encrypted blob matched its pre-upgrade
hash and size. No new quote or payment was created during this deployment check.

The [customer browser acceptance run](https://github.com/forgesworn/wildbloom/actions/runs/37925844453)
passed against Wildbloom `a7f79cbb237f3db56f6cab2620bd6aae16eeb07e` and
Wildbloom Node `2ea211e78e0bcd2624d6e4bc17031456c0742cef`, the upstream revisions
pinned by this package. It exercised a real daemon with synthetic receivers:
unpaid upload refusal, Lightning quote/invoice/activation, one invoice across
checks, restart and private order recovery, encrypted paid upload, full-read
audit, corruption refusal and LNURLcash renewal. It also checked that payment
and audit records were not published to relays or persisted in browser storage,
and checked service-control accessibility.

That upstream run is now complemented by the
[published-image customer journey](https://github.com/forgesworn/archipelago-apps/actions/runs/37929711659),
which passed on 9 October using the actual Archipelago app and patched Node
containers. Both images were pulled from GHCR and run by immutable digest;
neither application nor daemon was rebuilt for this acceptance run.

| Published image | Accepted registry digest |
| --- | --- |
| `wildbloom:0.0.1-a7f79cb-2` | `sha256:7880b875100ebc216072c57886e4f7cb4b39c0aee9212deeabc9ff4049c677e6` |
| `wildbloom:0.0.1-1d2a7c3-2` | `sha256:1839e74142310a5f7c531aab486d8b6ebe3c4ffa4a12b6cb74c31ad752890194` |
| `wildbloom-node:0.3.5-2ea211e-2` | `sha256:ff5ac6d45b471cfa809b07bcfe75fd2ae5cd9523f2f41c00d2fba4acb8750b95` |

The packaged browser selected its own node on first load and after reload.
Lightning purchase, private order recovery, encrypted upload, full-read retrieval
after daemon restart, deliberate corruption refusal and LNURLcash renewal all
passed. With the 1 MiB paid-capacity ceiling full, a second buyer was refused
before and after restarts; the existing buyer could renew without counting their
capacity twice. Restart and payment checks created neither a replacement invoice
nor another note rotation. Browser persistence, payment/proof relay publication
boundaries and service-control accessibility also passed.

This Linux/Chromium run used isolated synthetic receiving services and an
ephemeral loopback HTTPS certificate. It did not change the deployed node, enable
public sales or submit real payments. Synthetic renewal is not live Moneyer
renewal, and a one-host test is not multi-device or independent custody evidence.
The downloadable `packaged-services-report` CI artifact records image identities
and the passed checks.

Repeat after the images selected by `PINS` have been published:

```sh
gh workflow run packaged-services.yml --ref main
```

The workflow builds only the synthetic receiver example at `WILDBLOOM_NODE_REF`
and imports test helpers from `WILDBLOOM_REF`. The browser app and storage daemon
come from the published images. It also runs when its harness, dependencies or
workflow change; image publication itself remains a separate operation.

The test node's operator has selected the current offer, reviewed Moneyer terms
and deliberately enabled public checkout. Other operators choose their own values
and may leave selling disabled. At this packaged-test checkpoint, real renewal,
automatic refunds and refund interruption recovery had not been accepted; the
10 October section records their subsequent live acceptance.

## 8 October 2026: local implementation and container acceptance

Local implementation and container acceptance. Images were built on macOS with
Linux ARM64 containers. No image was published and no physical Archipelago node
was updated. No real payment, Moneyer rotation or customer sale was performed.

| Check | Result |
| --- | --- |
| Archipelago shell manifest validator and Rust parser | Both app manifests accepted; package tags match `PINS` |
| Generated enabled seller manifest | Accepted by the real Archipelago Rust parser |
| Python configuration tests | 6 passed: editable default creation, operator overrides including zero reserve/grace, sales off by default, explicit enablement, bounded configuration, private non-overwriting files |
| Patched Shelter tests | 103 passed natively and inside the Node image build |
| Patched checkout tests | 27 library tests and 1 operator-file test passed natively and inside the Node image build |
| Native Node workspace | Formatting, all-target Clippy with warnings denied, and workspace tests passed; the existing real-Tor test remains opt-in/ignored |
| Patched Shelter formatting/Clippy | Passed with warnings denied |
| Browser image | Production build and upstream audit guard passed |
| Packaged browser in Chrome | Configured public node selected even when dashboard hostname differs; same-host fallback, explicit override, reset to own node, consent revocation, Tor isolation, pool isolation, reload, invalid-config refusal and no background service requests passed |
| Browser visual check | Inspected the actual packaged setup page; aligned the node controls and replaced contradictory upstream default-server copy |
| Packaged seller daemon | Generated Moneyer profile loads; sale ceiling refuses the next customer quote; unpaid buyer upload is refused; owner upload uses the reserved portion; identical bytes and the immutable quote survive restart |

The aggregate ceiling is checked in the same SQLite transaction as a sale hold.
Tests cover simultaneous quotes below the total store quota, retained allowances
during grace, renewal without double counting, owner writes, restart, and
honouring an already reserved quote after a ceiling reduction.

The browser audit reports the upstream documented `GHSA-2p57-rm9w-gvfp` exception.
Its guard verifies that the affected Node-only UDP/IP modules are excluded from
the browser bundle. This is not a claim of zero advisories in the dependency tree.

Repeat the package checks with:

```sh
python3 tests/test-sales-config.py
scripts/validate.sh
# Build with the exact arguments from PINS, using local tags:
tests/smoke/wildbloom.sh archipelago-wildbloom:own-node
node tests/smoke/seller-capacity.mjs archipelago-wildbloom-node:seller
```

Install the smoke npm dependencies and Playwright Chromium first. A system Chrome
path can instead be supplied as `PLAYWRIGHT_CHROMIUM_EXECUTABLE`.

The seller smoke test uses only synthetic keys and tiny capacity values. It
generates the operator profile through the real configuration helper and never
submits a note or calls a receiving endpoint. Its Docker volume is temporary and
removed afterwards. CI retains the existing version-to-version storage-volume
upgrade test; that older-image upgrade was not repeated in this local run.

At this checkpoint, publication, installation, live receiving/refund and paired
backup testing were still outstanding. See the 9 October section above for the
subsequent results and the remaining operator choices.
