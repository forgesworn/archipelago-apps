# Archy beta 2 maintainer review pack

**Maintainer must review and approve UI work on Settings, Storage & selling,
Sales & customers/refund recording, App Store, linked-signer login, Fresh authorisation and the
embedded Wildbloom/Spry/KithMoot node screens before any PR is accepted into core
Archipelago or final core approval. ZAT pending.**

The owner clarified on 13 November that this gate applies to acceptance into
core Archipelago. ForgeSworn implementation, testing, its PR53–PR55 chain and
exact public-image publication may proceed without recording that as ZAT. No
maintainer has been contacted. This pack does not authorise a core Archipelago
merge or deployment to `demo.forgesworn.dev`.

**Candidate update, 13 November:** the earlier backend/frontend pair below is
superseded for approval. Integrated review found that externally managed
Wildbloom had no launch URL or app-gate ingress after migration. Patches 35 and
36 restore its reviewed launch and ingress without adding installation authority.
The replacement source is `0430c8cf2622a06f474eb991b8cd278dc95abb5b`; its clean
frontend archive is `.cache/beta2-ui-release-frontend/frontend.tar.gz`, SHA-256
`75eb02bab32700e73b038fb5fabe57118b9a36972be7ff43c3b080804f53f19d`.
The ARM64 backend is `.cache/beta2-ui-release-backend/archipelago`, SHA-256
`9a5fde6fc0555f3675f052b9e3d8a141bda21e7b4f0e5bf94256a17b97deb5b7`.
Both retained-ingress backend tests pass, along with 120 App Session and 137
fresh-authorisation/linked-signer frontend tests and the storage/sales browser
checks. The replacement pair then passed integrated browser checks on the
isolated restored node: all four app health/launch endpoints returned HTTP 200;
Wildbloom, Spry and KithMoot Node loaded without app-subresource HTTP errors;
identity selection cancellation and app-consent denial reached the app; fresh
authorisation rejected a wrong password, honoured cancellation and returned a
well-formed signature for the exact synthetic event. Event content did not enter
the password dialog, and external networking was blocked throughout. These
checks do not constitute maintainer approval or physical-client acceptance.
Do not approve the older pair.

**Linked integration evidence, 13 November:** a real `nak` NIP-46 signer and
loopback relay passed linked identity creation, secret-free export,
fresh-authorised event signing, login-signer enrolment and signer login on the
exact ARM64 backend. Both fresh-grant and completed-login replay attempts were
refused, and `nak verify` independently accepted the synthetic event. See the
[signer receipt](signer-integration-evidence.json). Approval was automatic, not
a human or physical-device action, and this was not embedded-browser UI
acceptance. The isolated manager/VM was removed after evidence capture.

Current KithMoot source `e56ac08482fa7a207e2dbc36e34774188440d4ab` also passed
20 Chromium room/chat/pairing checks against its offline relay, including real
rooms, two-device pairing/unpairing and clipboard refusal. The exact node
controller's component check passed blocked-policy, no-Clipboard-API and
late-expiry paths with no page errors or accessibility violations. See the
[room/clipboard receipt](room-clipboard-evidence.json) and inspected
[manual-copy capture](pairing-copy-blocked-390.png). These do not establish
physical-client or embedded-host acceptance.

## Reviewed candidate

- Integration branch: `feat/archy-beta2-compat-20261112`.
- Upstream: `v2.1.0-beta.2`, commit `5aac0d20571e6f673b8a5df95a5c8fcab2932c39`.
- Candidate source: the upstream commit plus this branch's `upstream/patches`,
  applied by `scripts/apply-patches.sh`. Build inputs and source identity are
  recorded in the generated frontend `inputs.sha256` and runtime
  `FORGESWORN-BUNDLE.json`; approval must identify those exact reviewed bytes.
- Storage/sales captures use the actual beta Vue components with synthetic RPC
  responses. Integrated captures use the exact frontend/backend pair on the
  isolated restored node. Neither shows or modifies a live wallet, receiver or
  customer.
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
- The matching [complete node candidate](https://github.com/forgesworn/archipelago-apps/actions/runs/43268204623/artifacts/13967879604)
  passed backend CI and the disposable fresh Debian host fixture at integration
  commit `664be6ce144931625c9e09ff66245c77914f186e`. Backend SHA-256:
  `e887b68d4232523bbf48a722b906b4759e9bf3270b98cc604630d8d92f57124d`.
  Source identity and frontend bytes match the candidate above. Full hashes and
  local retention paths are in the [upgrade evidence](../../archy-beta2-upgrade.md#backend-ci-qualification).
  [Fresh-host results](fresh-host-evidence.json) cover generated state only;
  the [generated installed-node rehearsal](migration-evidence.json) also passes.
  The actual restored-node migration has passed offline; integrated maintainer
  review and controlled live cutover remain pending.

## Setup and checks

On a clean checkout, fetch and apply the pinned source, build the dashboard and
run `scripts/test-storage-settings-browser.sh <archy-source>`. The runner needs
Playwright Chromium; `PLAYWRIGHT_CHROMIUM_EXECUTABLE` can select an installed
Chrome. Review at desktop width and 390 px mobile width.

For the integrated candidate checks, the retained offline VM restored the actual
backup into separate writable state, used a temporary test password and kept
external networking blocked. No payment, room change or signed-event publication
was requested. The task runner is `.cache/ui-review-smoke.mjs`; a loopback-only
review proxy serves the exact frontend archive while the runner exercises the
real ARM64 candidate backend. Review light and dark OS preferences: the dashboard
is deliberately dark-only and must remain dark in both. Cover empty, loading,
failed and successful reads. This headless node does not include kiosk or
physical-client acceptance.

The public catalogue rechecked on 13 November remains byte-identical to the
12 November copy and was rejected again by independent signature verification
and the [exact beta executable verifier](catalogue-verification.md).
It also has no entries for our four node integrations; see the
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
   For signing, review the existing app consent and beta fresh-authorisation
   dialog: cancellation, incorrect password/TOTP and successful confirmation.
   A remembered app consent is not a substitute for the fresh signing grant.

| Screen | Steps | Expected result |
| --- | --- | --- |
| Settings | Open the System group, search for storage and open Storage & selling. | The existing beta grouping and search work; storage controls are discoverable and fit the documented design baseline. |
| Storage & selling | Inspect the reference issuer, select the explicitly labelled development issuer, edit quota/reserved capacity, save a draft, then review/apply. | Sales remain optional and off initially. Draft saving causes no runtime change. Applying requires explicit confirmation. Zero reserve/grace values remain valid. No overflow on mobile. |
| Sales & customers | Inspect paid, renewal, pending, refund-required and completed-refund examples; expand long references and filter attention items. Simulate a failed read. | Dates and current allowances remain clear. Unavailable data is not presented as an empty ledger. Private references fit the viewport. |
| Refund recording | Open a completed-refund record, supply its payment hash and confirm customer receipt. | Save is disabled until confirmation. Recording a historical refund does not send a payment or remove the allowance. Automatic recovery refers to the original payment. |
| App Store | Load a verified catalogue plus community metadata, then make the verified catalogue unavailable. | Signed versions/images remain authoritative. Unsigned Spry metadata cannot grant installation or native integration. A new Spry store install is currently unqualified; do not interpret its absence as permission to remove the installed relay. |
| Linked-signer login and app identity chooser | On an isolated node, use an existing linked signer, enrol another, cancel a request and select identities in an embedded app. | Existing identities remain selectable; cancellation/rejection is clear; signing requests stay bound to the expected node origin. Real NIP-46 RPC integration passed; embedded visual and human-device review remains pending. |
| Fresh authorisation | Trigger embedded signing, inspect the operation, cancel, submit incorrect credentials and then approve with the generated owner credentials. | The grant is bound to the frozen operation and session, used once and never persisted or automatically reacquired. Private event content stays out of the password dialog. Linked-device approval remains a separate signer step. |
| Embedded Wildbloom, Spry and KithMoot node | On an isolated upgraded fixture, open the existing apps and rooms, inspect status, copy the node information and exercise the signer flow. | Existing data, configuration and rooms remain present; clipboard and private signer routes work. Current-client room/clipboard checks passed separately; production/client acceptance remains pending. |

## Captures and evidence limits

- [Storage desktop](storage-selling-desktop.png)
- [Storage mobile](storage-selling-mobile.png)
- [Sales desktop](storage-sales-desktop.png)
- [Sales mobile](storage-sales-mobile.png)
- [Refund form mobile](storage-refund-mobile.png)
- [Storage desktop with a light OS preference](storage-selling-desktop-os-light.png)
- [Sales mobile with a light OS preference](storage-sales-mobile-os-light.png)
- [Embedded Wildbloom](integrated-wildbloom.png)
- [Embedded Spry](integrated-spry.png)
- [Embedded KithMoot Node](integrated-kithmoot-node.png)
- [Fresh-authorisation incorrect-password response](integrated-fresh-authorization-error.png)
- [Clipboard-blocked manual pairing link](pairing-copy-blocked-390.png)

The integrated captures were inspected before inclusion. A dashboard capture
containing a restored companion QR code is deliberately excluded; do not copy it
from the task cache into this pack.

The offline fixture uses rootless `keep-id` containers with host networking and
explicit loopback app binds because this VM's rootless fixed-port forwarder was
faulty. It also uses fixture-only SELinux `label=disable`, dummy FIPS addresses,
Wildbloom discovery manifests and loopback proxies that present the configured
production origins. These adaptations let the unchanged candidate run the
browser checks; they are not production rootless-port, firewall, physical-device
or client acceptance. The original backup remains untouched.

Automated checks passed for the captured storage/sales flows. An additional
Chromium run explicitly emulated `colorScheme: light`, asserted the light OS
media query and the root computed `color-scheme: dark`, and passed the complete
desktop/mobile flow without horizontal overflow. This verifies the existing
dark-only baseline, not a new light theme. Real NIP-46 RPC integration, current
room/clipboard checks and the node clipboard component now pass. Embedded visual
acceptance, human/physical signer approval and physical clients still need final
review. Refresh this pack and approval after any material UI change. See
[upgrade preparation](../../archy-beta2-upgrade.md) for server-preservation and
activation gates.
