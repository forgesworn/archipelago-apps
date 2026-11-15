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

**Multi-platform packaging update, 13 November:** the assembled patch source is
now `09c92087ca40e37a0ce881dcf4cd7e76f493f676`. Frontend run
[43524870915](https://github.com/forgesworn/archipelago-apps/actions/runs/43524870915)
passed and produced patch-level-3 archive
`.cache/beta2-ui-release-frontend-p3/frontend.tar.gz`, SHA-256
`92a5aba6ff9c1253ee0e3db3fb64ffeeacf9d30c78505f679b3c8939552dac70`.
Only `NATIVE-AIUI.json`, `FORGESWORN-BUNDLE.json` and `RELEASE-PAYLOAD.json`
changed from the integrated patch-level-2 archive above; all 1,277 other files
are byte-identical. Native ARM64 backend run
[43529354420](https://github.com/forgesworn/archipelago-apps/actions/runs/43529354420)
passed and produced `.cache/beta2-ui-release-backend-p3/archipelago-arm64`,
SHA-256 `ef2917fd030548fa1b0492f3694042e892480ed8dea472f99ff2ddd35c41dad3`.
The downloaded hash matches its receipt and the file is an AArch64 Linux
executable. The [published frontend release](https://github.com/forgesworn/archipelago-apps/releases/tag/frontend-v2.1.0-beta.2-p3)
is byte-identical to the archive above. The [published backend release](https://github.com/forgesworn/archipelago-apps/releases/tag/backend-v2.1.0-beta.2-p3)
contains the same ARM64 binary and x86-64 `archipelago`, SHA-256
`642fab8ebb78d8a7446f817cf5018e06ce0890f4c55dfb78d4451168df4e62ef`.
Downloaded release hashes, architectures and input receipts all match.
Multi-platform image run
[43525691004](https://github.com/forgesworn/archipelago-apps/actions/runs/43525691004)
passed native Wildbloom and Wildbloom Node build/smoke jobs on amd64 and arm64.
These release changes add no new UI flow; final approval must still identify the
resulting frontend/backend pair.

**Patch-level-4 and live deployment, 14 November:** PR58 merged as
`6358efc41ad6913bb7268b06026c7a6fc9ded45e`; assembled source is
`f46f9bd54818f0c8d3cb3634b6101b7334f1962f`, tree
`a615625d42b0f3e9069eb0d4d3507d325721bbd8`. Patch 37 accepts only the five
reviewed beta nginx additions during host-ingress status/check/sync; rollback
and unrelated drift remain strict. This adds no UI flow or screen change.
The [published frontend p4](https://github.com/forgesworn/archipelago-apps/releases/tag/frontend-v2.1.0-beta.2-p4)
has SHA-256 `69fc037b5650c02b2f220238fad6f0e70556c0a3a92238e7ba4025c26cc5ad49`;
the [published backend p4](https://github.com/forgesworn/archipelago-apps/releases/tag/backend-v2.1.0-beta.2-p4)
contains x86-64 `60c161b285c9458daf79528b2daeece6c06c6bdfa9b12a6f722a8e63bcbcfb4a`
and ARM64 `048daabea25ca9847fa85b470f0d288be31b9bd3f5efd323a0f9e49a02a6e28f`.
Public downloads are byte-identical to the reviewed CI artefacts. Backend input
receipt `a3942254b9663e39c2c898ccefc05c9eb053a1a687d0403ac70cb4607eaacf66`;
frontend input receipt `312ad9a0388d144009d881890a618a68d29dc871160cd4dc0b9cb8f4bd819283`.
The p4 pair supersedes p3 for exact-candidate review.

Live operation `8a0ebdd9-6f22-4009-a6e2-1e574b40b4f7` is active on
`demo.forgesworn.dev`. The fresh pre-p4 coherent archive passed authenticated
off-host readback and two full isolated filesystem comparisons around
copied-database checks. All six original containers, images, mounts and start
times are preserved; manager/NPM health, three app health checks and local app
endpoints pass. Seven rooms with 3,609 events, 17 blobs, five paid sales,
File Browser settings and Fedimint RocksDB state remain. External TURN TCP and
trusted TLS pass. See the [live verification receipt](live-p4-verification.json).
Physical clients, physical signer, embedded visual acceptance and ZAT remain
pending; automated deployment evidence does not replace them.

**Patch-level-6 and live acceptance, 14 November:** PR63 merged as
`0951aa70855a11df681d84c3309b9322391abfe5`; exact assembled source is
`f3b7c0d0c58df6f772b6ce26cd529970eb072e8d`. Patch 38 separates external
Wildbloom sales/capacity reads from packaged apply/restart authority. Patch 39
accepts the early completed checkout-refund shape only when it matches the
original quote and has valid settlement evidence; partial records remain rejected.
The [published backend p6](https://github.com/forgesworn/archipelago-apps/releases/tag/backend-v2.1.0-beta.2-p6)
contains x86-64 `e298ab2075896d85be82dd428ed0ce75f97f6406859b809e36e06ecb50e52ccf`
and ARM64 `7dcbeb488fa4fe6030f0bf972431b63d245226f4a1d4ce0cc7312e609ab59fd8`.
The [published frontend p6](https://github.com/forgesworn/archipelago-apps/releases/tag/frontend-v2.1.0-beta.2-p6)
has SHA-256 `8d421246749636cbd5e4149ccdb448d8b5f8ae0b9ea159204bfeda45d985488c`.
Public downloads are byte-identical to the reviewed CI candidates. Backend input
receipt `bf35ce5c6723667e220e46a458a7e4fa6b9e2f795f0ffcaa05b742cbddb35f45`;
frontend input receipt `597b931e95f740f0a3b0996d0ef5c4cc6e31006531de442c5a4e8e26c3574ace`.
No UI source, styling, route or text changed; the affected screens remain
Storage & selling, Sales & customers and refund recording. This pair supersedes
p4 and p5 for exact-candidate review.

Live operation `e319cb79-1725-478f-9a4b-570a2aff3af4` is active on
`demo.forgesworn.dev`. The fresh pre-p6 recovery set passed authenticated
off-host readback, 12 SQLite checks and isolated restore of all 105,812 archived
entries with zero unexpected paths. All six app fingerprints and retained data
passed independent post-migration checks: 10 rooms with 3,680 events at read
time, 17 blobs and five paid sales. Chrome returned seven orders, two paid orders
and one retained customer, displayed real capacity and kept Apply unavailable
for the externally managed node. The early refunded order rendered its matched
settlement evidence on desktop and 390px mobile layouts with no horizontal
overflow. No payment, message, room change or refund was submitted. See the
[live p6 verification receipt](live-p6-verification.json). Live customer captures
are retained privately, not published in this pack. Physical signer/client
acceptance and ZAT remain pending.

**Patch-level-7 CI candidate, 15 November:** candidate commit `2a2d0d8` on
`fix/signer-app-launch-20261115` is based on p6 commit `14c141a`.
Patch 40 adopts current upstream's managed-app-login exemption for File Browser,
Datum, PhotoPrism, Grafana and Portainer. It leaves Qortal, unknown apps, key
exports, security changes and funds operations under fresh password proof. The
runtime recipe retains Spry, Wildbloom and Wildbloom Node manifests across
frontend updates; it does not add catalogue installation authority.

Local checks: 106 Python tests and the manifest validator pass. The production
frontend assembled at `f095d66f1e566f8f562e3231677c267800cd1849`; archive
SHA-256 `0366459f1fa711ca64c9787ac2df91162d022e011895fd0c72b8b015482d8c02`,
input receipt `cfbc62cd32e09cca781e45bb18a731f4a0941ec676e5d39ee095d1b896ffe854`.
The archive's three bundled manifests match their pinned sources byte-for-byte.
[Frontend CI](https://github.com/forgesworn/archipelago-apps/actions/runs/43686958633)
passed its UI and browser acceptance checks and produced byte-identical bytes.
[Backend CI](https://github.com/forgesworn/archipelago-apps/actions/runs/43686958641)
passed 3,123 core tests, the fresh Debian host fixture, and both new managed-login
boundary regressions. Its x86-64 backend SHA-256 is
`0c56ec04676f7d8d70ac098693f1f6683e2cd7effed1acafd8818459075adb29`, with
input receipt `bf80f43517c0503fb2f198d44b9ec0ae64e21757bc2b67df0bd5720aee66773f`.
No firewall change is part of this candidate.

**Live p7 deployment, 15 November:** operation
`48d32d2d-890a-48fb-b2af-a648f67cda3b` is active on `demo.forgesworn.dev`.
The fresh coherent archive is SHA-256
`3e6862587110e82d1a3104df676d20ecc3feef73044b4c9d40d263827e7036f8`;
authenticated off-host decryption matched, and a network-isolated restore
verified all 107,304 entries with zero unexpected paths. GNU tar independently
passed its content/xattr/ACL comparison and all 12 selected SQLite databases
passed integrity checks on copies. The exact historical Wildbloom and Wildbloom
Node manifests were restored before candidate preparation, preserving their
running images and all six original container IDs. Manager and nginx health,
crash recovery, all three local app endpoints and the startup guard pass. The
active frontend tree is `7a6ef1df03ed1f4689caf042f20e131a50bf9249ff5e5b3b08db2c34e980c9be`.
No firewall or application-container change was made. The trusted dashboard
route returns HTTP 200; untrusted external callers retain the intended private
404. Owner acceptance then confirmed that p7 did not complete signer-only app
authentication: linked `identity.sign` still failed. The separately requested
KithMoot **Show application credentials** operation remains intentionally
password-protected. See the [live p7 verification receipt](live-p7-verification.json).

**Patch-level-8 CI candidate, 15 November:** patch 41 addresses the failed
linked-identity path without adding general signer support for sensitive
reauthentication. Wildbloom, Wildbloom Node, Spry and KithMoot Node receive the
linked public identity without an impossible Ed25519 signature, then their real
full-event request goes to the linked signer and its verified response is the
fresh proof. A valid session and explicit linked identity are required. Local
identities, raw hashes, generic `identity.sign`, credential displays/exports and
other sensitive operations retain password grants. Five focused frontend tests,
106 Python tests, clean patch validation and the production frontend build pass.
The local assembled source is `1acc4e98b35b025aa305a0765d43f08fbfbf6cbc`;
CI assembled `b0e93b58dfb8c5ae13447282e3df5a7bfb57c106` with the identical
tree `3812aa341359ec339a4fb4275faa87ac55977023`. Local frontend
SHA-256 is `8a5ef416a7476e15e1d28ca5146b3f44cbcf0ab112d46c0a4c83e5560df601f7`,
with input receipt `b02037f7d33a224b733bda740ed2738bce580162210aa4e1ba9bc0ab7ae7223c`.
[Frontend CI](https://github.com/forgesworn/archipelago-apps/actions/runs/43694458729)
passed; its exact archive is SHA-256
`a31cbb48682180d65db7c9cac12e89579b538fbe0b37dafcd73363d0775e6a38`.
Only the three generated source-metadata files differ from the local archive;
all 1,279 other files are byte-identical. [Backend CI](https://github.com/forgesworn/archipelago-apps/actions/runs/43694458769)
passed 3,124 tests, including the linked-signing regression and its local
password-grant control, after an unrelated container-liveness test passed on
rerun. The exact x86-64 backend SHA-256 is
`1347052801b735ac0c80bf57f0ae79012af8d2ff07af2a5108ef3b8a7a2b8485`,
with input receipt `d5a0481311b9a223db08ee5701f456e75458c39ed6fc6c01ada07ac67a237b11`.

**Live p8 deployment, 15 November:** operation
`1c127f4d-0dfc-4904-80aa-9bb1293e3940` is active on `demo.forgesworn.dev`.
The fresh recovery archive is SHA-256
`52977be81656d9ed3716c6a7769e1c9379c7e4b930d4ce661bfa80380851ba8e`;
authenticated off-host decryption matched, and a pristine network-isolated
restore verified all 108,806 entries with zero unexpected paths. GNU tar passed
its content/xattr/ACL comparison and all 12 selected SQLite checks passed on
copies. The active frontend tree is
`0f20b293aa8be7d702832c64ddffb232ad47afa4d21cee3343510ce915c596c1`.
Manager health, crash recovery, the trusted dashboard and all three local app
endpoints pass; all six original container IDs, images and manifests remain.
No firewall or application-container change was made. Physical signer acceptance
and post-deployment captures remain pending. See the
[live p8 verification receipt](live-p8-verification.json).

**Patch-level-9 CI candidate, 15 November:** owner acceptance showed that
the remaining ordinary-launch password was caused by both legacy Apps launchers
preflighting `package.credentials-authorize` for every app, not only managed
logins. Patch 42 limits that preflight to the existing managed interstitials and
Qortal, preserving its API-key flow. KithMoot Node, Spry, Wildbloom and Wildbloom
Node now launch directly and are included in the generated launcher-title map,
keeping their declared UIs under My Apps rather than Web. Credential display and
export retain fresh password proof, and the p8 backend remains compatible. All
107 focused launcher tests, clean patch validation and the production frontend
build pass. The assembled source is `359a65220bbb2b0f8ab294e7cfd379c6589dd394`;
local frontend SHA-256 is `50f2a0dacac44390ef1af9a8fbc1253716412254101cb572b3d8984887d938f7`,
with input receipt `a6ea806da1e170241c955550a00f794b1593780b8ba15f6df1dcb747257c2284`.
[Frontend CI](https://github.com/forgesworn/archipelago-apps/actions/runs/43701574552)
passed. Its exact source is `23a2a58e33a3b240f9b1d5c89c54f52fc436343f`;
archive SHA-256 is `236da86fd8cfccf58992b3382de9d7a47dd9db372af4b67666cce5727846a0c3`.
Only the three generated source-metadata files differ from local; all 1,279
other files are byte-identical. [Full backend CI](https://github.com/forgesworn/archipelago-apps/actions/runs/43701576985)
also passed; deployment retains the already verified p8 backend. Physical
acceptance is pending. Review **My Apps** in both desktop and icon-grid
modes, direct native launches, File Browser's managed-login interstitial and
Qortal's existing credential prompt.

**Live p9 deployment, 15 November:** operation
`6d76d777-ab55-4d70-acbd-afe76a989f4e` is active on `demo.forgesworn.dev`.
The backend remains at the verified p8 hash. The fresh recovery archive is
SHA-256 `b2eeff905c97f339e2414f9191ded89bb1cdc0fde4e11c2c429b4169fa56880b`;
authenticated off-host decryption matched, and a pristine network-isolated
restore verified all 110,293 entries with zero unexpected paths. GNU tar passed
its content/xattr/ACL comparison and all 12 selected SQLite checks passed on
copies. The active frontend tree is
`645d1b3f8254efddefdb68914754dfe84bc1b28fd797ed958eb7bf78226962fc`.
Manager health, crash recovery, the trusted dashboard and all three local app
endpoints pass; all six original container IDs, images and manifests remain.
No firewall or application-container change was made. Physical acceptance and
post-deployment captures remain pending. See the
[live p9 verification receipt](live-p9-verification.json).

**Patch-level-10 CI candidate, 15 November:** owner acceptance still reached
`identity.sign` because the saved linked identity predated the `origin` field.
Patch 43 resolves legacy selections with authenticated `identity.get`, uses the
native Nostr handoff only when the backend confirms `linked`, and writes the
corrected origin back to storage. Explicit local identities retain their Ed25519
proof. The regression and all 108 focused launcher tests, clean patch validation
and the production frontend build pass. Assembled source is
`613479a7bbda317e38609f7bcc7965bd7f54f5e1`; local frontend SHA-256 is
`f5aafeb1fa8b9cbe8d6b28fa323aa0e925b742023828bec6b1cd260b08bb1153`,
with input receipt `d73da105037ad6b1d6ab8971cd6295eea5ddad50b35799a523b23848d14559ee`.
[Frontend CI](https://github.com/forgesworn/archipelago-apps/actions/runs/43706424327)
passed. Its exact source is `34467c0752cc117935f1f27e03573f68b606e438`;
archive SHA-256 is `0e2c4b6e1174b72acea7e2c4c6644c3a52a57a6db0f422e9ae9879b224e7b635`.
Only the three generated source-metadata files differ from local; all 1,279
other files are byte-identical. Physical acceptance is pending.

**Live p10 deployment, 15 November:** operation
`6e3c7d60-81d0-4251-9dc7-19d11fbf22d8` is active on `demo.forgesworn.dev`.
The backend remains at the verified p8 hash. The fresh recovery archive is
SHA-256 `2aaa83f21655da1dfba887d143fefdb3babce37cc6c10d1113e12d2cbf299f05`;
authenticated off-host decryption matched, and a pristine network-isolated
restore verified all 111,797 entries with zero unexpected paths. GNU tar passed
its content/xattr/ACL comparison and all 12 selected SQLite checks passed on
copies. The active frontend tree is
`0a0756afbcde730de85647003430f9bf689850be306a77e2528e9e966e731cc7`.
Manager health, crash recovery, the trusted dashboard and all three local app
endpoints pass; all six original container IDs and images remain. No firewall
or application-container change was made. Physical acceptance and post-deployment
captures remain pending. See the
[live p10 verification receipt](live-p10-verification.json).

**Patch-level-11 CI candidate, 15 November:** the owner's detailed
acceptance flow confirmed that the second App Session identity injector still
called `identity.sign`. Patch 44 removes the app allowlist and applies the same
rule in both injectors: linked identities never request an impossible
node-local Ed25519 signature. Only public fields are injected; the app's real
full Nostr event then goes to Heartwood. Local identities retain their existing
proof, and legacy origins are resolved through `identity.get`. All 113 focused
launcher and identity tests, clean patch validation and the production frontend
build pass. Assembled source is `8e420b5d486d2e2a083728b6b0e481b668c3852f`;
local frontend SHA-256 is `a143975bc4b97245dd720a4853d2208c3da5dec7c1931d87db8775185aa587eb`,
with input receipt `1ac9ba8f9f78df954d39624ad0c1258ede1ab33ba0b3eb2cc6fe2c2e3c3abec0`.
[Frontend CI](https://github.com/forgesworn/archipelago-apps/actions/runs/43709473971)
passed. Its exact source is `9c97e082535510202586a6c58e3a93031958adba`;
archive SHA-256 is `c859b90d1ae706eba349d3190516857403ab69545271ef8500210c4b9a645948`.
Only the three generated source-metadata files differ from local; all 1,279
other files are byte-identical. Owner acceptance passed on 15 November.

**Live p11 deployment, 15 November:** operation
`10688326-d365-43e8-a13d-b7f5d057ce14` is active on `demo.forgesworn.dev`.
The backend remains at the verified p8 hash. The fresh recovery archive is
SHA-256 `60a5c451539484a11c0760e8eaf50fc87f18bf76f5bfad103236f73d2f59ad9f`;
authenticated off-host decryption matched, and a pristine network-isolated
restore verified all 113,281 entries with zero unexpected paths. GNU tar passed
its content/xattr/ACL comparison and all 12 selected SQLite checks passed on
copies. The active frontend tree is
`6ded1f80c6f7da97fafa8a51b92f3452d335a298e636223dfd43104c610e8e59`.
Manager health, crash recovery, the trusted dashboard and all three local app
endpoints pass; all six original container IDs and images remain. No firewall
or application-container change was made. The owner then confirmed that launch,
identity selection and Heartwood sign-in work without a node-password or
authenticator prompt. Post-deployment captures and maintainer ZAT remain pending.
See the [live p11 verification receipt](live-p11-verification.json).

**Patch-level-12 working candidate, 15 November:** Spry's `node.nostr-sign`
fallback used the appliance key because no identity was selected. Patch 45 adds
Spry and the other native apps to App Session's first-launch identity picker and
refuses node signing when an identity-aware app has no selected identity. This
preserves linked/local signing and non-identity-aware app behavior. The Spry
regressions and all 232 App Session/launcher tests, clean patch validation and
the production frontend build pass. Assembled source is
`b363018ec0feef063fcf39dd16842c3cef52db15`; local frontend SHA-256 is
`100b566c76847dea42c9e97e01d2d74088b36b01b66064b52d6343f3f67751df`,
with input receipt `618ceac3b4674106c90110378655a9d5897131e0cb1b4b0f13a8ebc195123681`.
Exact CI artifacts will be recorded before deployment. Hosted CI, deployment and
physical Spry acceptance are pending.

For launch review on a backed-up test node with File Browser installed and a
login signer enrolled: sign in with the signer, open **My Apps** and launch
**File Browser**, then continue through its managed-login interstitial. Expected:
no second node-password demand, the existing owner session and one-use
capability are accepted, and the app opens. Launch **Wildbloom** from the same
page and confirm its existing HTTPS gate. Launch **KithMoot Node**, choose the
linked identity, and approve its real Nostr sign-in event on the signer. Expected:
no node-password demand and no impossible Ed25519 request; the signer receives
the exact full event and the app opens. Repeat the linked sign-in on **Wildbloom**
and **Spry**. Confirm **Show application credentials** still requests fresh
password proof. Invalid sessions, local identities, raw hashes, CSRF and origins
must remain refused by automated boundaries. No visual styling is changed;
capture the identity chooser, signer consent and embedded apps after deployment.
Maintainer must review and approve UI work on **My Apps, the File Browser launch
interstitial and embedded app, and the KithMoot Node, Wildbloom and Spry identity
choosers, signing consent and embedded apps** before merging or approval. ZAT pending.

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
