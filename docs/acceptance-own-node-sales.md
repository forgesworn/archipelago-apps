# Own-node default and seller capacity acceptance — 8 October 2026

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

Setup now supplies editable capacity and price defaults. Outstanding operational
inputs: the operator's choice of disk quota, owner reserve, customer offer size,
price and contact/refund terms; Moneyer evaluation-mint
acceptance; public reachability, live receiving/refund and paired-backup testing;
then image publication and installation on the intended node.
