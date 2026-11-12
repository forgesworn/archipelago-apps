# Archy beta 2 maintainer review pack

**Maintainer must review and approve UI work on Settings, Storage & selling,
Sales & customers/refund recording, App Store, linked-signer login and the
embedded Wildbloom/Spry/KithMoot node screens before merging or approval. ZAT pending.**

No maintainer has been contacted. This pack does not supersede the outstanding
PR53/PR54 review or authorise deployment to `demo.forgesworn.dev`.

## Reviewed candidate

- Integration branch: `feat/archy-beta2-compat-20261112`.
- Upstream: `v2.1.0-beta.2`, commit `5aac0d20571e6f673b8a5df95a5c8fcab2932c39`.
- Candidate source: the upstream commit plus this branch's `upstream/patches`,
  applied by `scripts/apply-patches.sh`. Build inputs and source identity are
  recorded in the generated frontend `inputs.sha256` and runtime
  `FORGESWORN-BUNDLE.json`; approval must identify those exact reviewed bytes.
- Browser captures here use the actual beta Vue components with synthetic RPC
  responses. They do not show or modify a live wallet, receiver or customer.
- No public preview URL. The temporary browser fixture uses
  `http://127.0.0.1:15173/storage-preview.html` and the `?sales` variant.
  The automated runner stops its server and removes the fixture on exit.
- The completed local frontend package is retained at
  `.cache/beta2-frontend-out/frontend.tar.gz`, SHA-256
  `45b440d1896a0c51e4b71aba64c768a82e6487f4e0cb84a26e9d9ebadd839793`.
  Its source commit is `18260448bb570d96962f5da2f2e30c163b351dd4`.
  This identifies a local review candidate, not a deployed build. CI's pinned
  Node 24 build may produce different bytes and needs its own reviewed identity.

## Setup and checks

On a clean checkout, fetch and apply the pinned source, build the dashboard and
run `scripts/test-storage-settings-browser.sh <archy-source>`. The runner needs
Playwright Chromium; `PLAYWRIGHT_CHROMIUM_EXECUTABLE` can select an installed
Chrome. Review at desktop width and 390 px mobile width.

| Screen | Steps | Expected result |
| --- | --- | --- |
| Settings | Open the System group, search for storage and open Storage & selling. | The existing beta grouping and search work; storage controls are discoverable and fit the documented design baseline. |
| Storage & selling | Inspect the reference issuer, select the explicitly labelled development issuer, edit quota/reserved capacity, save a draft, then review/apply. | Sales remain optional and off initially. Draft saving causes no runtime change. Applying requires explicit confirmation. Zero reserve/grace values remain valid. No overflow on mobile. |
| Sales & customers | Inspect paid, renewal, pending, refund-required and completed-refund examples; expand long references and filter attention items. Simulate a failed read. | Dates and current allowances remain clear. Unavailable data is not presented as an empty ledger. Private references fit the viewport. |
| Refund recording | Open a completed-refund record, supply its payment hash and confirm customer receipt. | Save is disabled until confirmation. Recording a historical refund does not send a payment or remove the allowance. Automatic recovery refers to the original payment. |
| App Store | Load a verified catalogue plus community metadata, then make the verified catalogue unavailable. | Signed versions/images remain authoritative. Unsigned Spry metadata cannot grant installation or native integration. A new Spry store install is currently unqualified; do not interpret its absence as permission to remove the installed relay. |
| Linked-signer login and app identity chooser | On an isolated node, use an existing linked signer, enrol another, cancel a request and select identities in an embedded app. | Existing identities remain selectable; cancellation/rejection is clear; signing requests stay bound to the expected node origin. This integrated browser/device review remains pending. |
| Embedded Wildbloom, Spry and KithMoot node | On an isolated upgraded fixture, open the existing apps and rooms, inspect status, copy the node information and exercise the signer flow. | Existing data, configuration and rooms remain present; clipboard and private signer routes work. Production/client acceptance remains pending. |

## Captures and evidence limits

- [Storage desktop](storage-selling-desktop.png)
- [Storage mobile](storage-selling-mobile.png)
- [Sales desktop](storage-sales-desktop.png)
- [Sales mobile](storage-sales-mobile.png)
- [Refund form mobile](storage-refund-mobile.png)

Automated checks passed for the captured storage/sales flows. Settings grouping,
complete login/embedding flows, visual acceptance and physical clients still
need review of the final integrated build. Refresh this pack and approval after
any material UI change. See [upgrade preparation](../../archy-beta2-upgrade.md)
for server-preservation and activation gates.
