# Own-node default and seller capacity acceptance

## 9 October 2026: deployed setup and customer acceptance

The own-node integration and editable storage/selling dashboard are deployed on
the test node. Selling remains optional and off. Personal storage requires no
customer contact or refund terms; each operator supplies their own details if
they choose to sell. The earlier local-only evidence is retained below.

| Scope | Verified result |
| --- | --- |
| Packaged own-node browser | Authenticated browser selected the configured node; Tor and pool modes cleared or disabled the own-node path as appropriate |
| Live dashboard | Authenticated draft save and reviewed apply passed; the node retained its 10 GiB quota and all 16 existing blobs byte-for-byte |
| Real Moneyer payment, private test node | A 50-sat received note activated a 1 MiB allowance; paid upload and exact retrieval passed |
| Payment recovery | The same receipt and file survived restart; a paired storage/checkout backup opened in a network-disabled clone and returned the same active receipt and exact file without another payment |
| Manual refund | One journalled refund returned the full 50 sats; Moneyer reported settlement, the received note was retired, and the recipient independently confirmed receipt |
| Optional-selling frontend | Released p3 files match the live HTTPS bytes; the generic seller name, blank contact/refund terms and sales-off configuration remain unchanged |

Deployment evidence is recorded in [PR #6](https://github.com/forgesworn/archipelago-apps/pull/6)
and [PR #9](https://github.com/forgesworn/archipelago-apps/pull/9).
Private test keys, notes, order references, refund destination and journals are
not repository artifacts. The refund endpoint did not return a payment preimage:
issuer settlement and recipient confirmation are recorded separately from
cryptographic proof. This was an operator-directed refund, not a shipped
automatic refund feature or an interruption-recovery test.

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

Remaining operational work belongs to an operator who chooses to sell: select
their offer and support/refund terms, review the issuer, and deliberately enable
sales. Public customer checkout on this test node remains disabled. Real renewal,
automatic refunds and refund interruption recovery have not been accepted.

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
