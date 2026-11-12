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
  CI at `dd8216be3b66a2870ece8b81451ef6767322e746` produced the same archive.
  [Download the exact CI review candidate](https://github.com/forgesworn/archipelago-apps/actions/runs/43258922145/artifacts/13962842901)
  (14-day retention). This is a review candidate, not a deployed build.

## Setup and checks

On a clean checkout, fetch and apply the pinned source, build the dashboard and
run `scripts/test-storage-settings-browser.sh <archy-source>`. The runner needs
Playwright Chromium; `PLAYWRIGHT_CHROMIUM_EXECUTABLE` can select an installed
Chrome. Review at desktop width and 390 px mobile width.

For the integrated review, use a disposable node with generated identities,
installed fixture apps and synthetic payment records. Review light and dark
OS preferences: the dashboard is deliberately dark-only and must remain dark
in both. Cover empty, loading, failed and successful reads. This headless node
does not include kiosk acceptance.

The public catalogue fetched on 12 November failed independent signature
verification and has no entries for our four node integrations; see the
[catalogue evidence](../../archy-beta2-upgrade.md#known-beta-integration-differences).
Verified-catalogue success needs an authenticated candidate accepted by the
unchanged backend verifier. Synthetic UI responses only qualify rendering;
they cannot establish working integrated App Store installation.

1. Sign in at `/login`, then open `/dashboard/settings`. Find Storage & selling
   through both the System group and search.
2. At `/dashboard/settings/storage`, edit limits, save a draft and review the
   confirmation before applying to the disposable node.
3. At `/dashboard/settings/storage/sales`, inspect sales and open the refund
   recording dialog. Confirm that recording receipt does not initiate payment.
4. At `/dashboard/discover`, exercise verified catalogue success and failure;
   check the unsigned Spry installation refusal.
5. Return to `/login` and exercise existing linked signers, another enrolment,
   cancellation and rejection without replacing the original identity.
6. Open `/dashboard/app-session/wildbloom`, `/dashboard/app-session/spry` and
   `/dashboard/app-session/kithmoot-node`. Exercise the identity chooser and
   `/nostr-signer` broker through the app, plus existing rooms and clipboard.

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
- [Storage desktop with a light OS preference](storage-selling-desktop-os-light.png)
- [Sales mobile with a light OS preference](storage-sales-mobile-os-light.png)

Automated checks passed for the captured storage/sales flows. An additional
Chromium run explicitly emulated `colorScheme: light`, asserted the light OS
media query and the root computed `color-scheme: dark`, and passed the complete
desktop/mobile flow without horizontal overflow. This verifies the existing
dark-only baseline, not a new light theme. Settings grouping,
complete login/embedding flows, visual acceptance and physical clients still
need review of the final integrated build. Refresh this pack and approval after
any material UI change. See [upgrade preparation](../../archy-beta2-upgrade.md)
for server-preservation and activation gates.
