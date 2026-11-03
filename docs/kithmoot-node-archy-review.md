# KithMoot Node: Archy maintainer review

**Maintainer must review and approve UI work on the Archy install, launch,
pairing hand-off, delete-everything and status screens before merging or
approval. ZAT pending.**

No maintainer approval has been recorded. Do not merge this revision or treat
the checks below as ZAT. The owner can pass this pack to the maintainer; no
message has been sent on the owner's behalf.

## Exact candidate

- UI/controller source: `3d447f14b13ea8fa5d6f7703a3f2cb98017cb5cd`.
- Draft [PR 53](https://github.com/forgesworn/archipelago-apps/pull/53).
- Private ARM64 image: `localhost/kithmoot-node:0.1.0-rc.1-f6c9c23f04d3`.
- Image ID: `sha256:afcbfec16663a90bf079689a304e278ef380f3c7069d54a2e676f06a05670e55`.
- Private bundle inventory SHA-256:
  `3e7f78635f9c69e7e281fb943e707328857c492038f6e1c87b2995215dd54a65`.
- Patched Archy host source: `fa356d36c3910867dbea17c7494c90a984aa10c6`
  (patches 0035–0040); backend patch level 5.
- [Combined evidence](evidence/kithmoot-node-archy-20261103.json) records
  source/asset hashes, manifest checks, private image hardening and the actual
  offline host journey. [Component receipt](evidence/kithmoot-node-archy-20261103/component-review.json)
  records the browser checks and their fixture limits.

There is no deployed review URL. No live Archy node has been changed. The image
and private backend inputs remain local and have not been pushed to a registry.
Use this exact build for review; record a new reviewed revision after material
UI changes.

## Build and setup

The [private package instructions](../experimental/kithmoot-node/README.md)
provide build and manifest preparation commands. The verified output for this
run is `.cache/kithmoot-node-candidate-4-20261103/`; its manifest is
`apps/kithmoot-node/manifest.yml` within that private output directory. It is
outside the published app catalogue and uses `pull_policy: never`.

For a live review, the owner must authorise a particular rented-server or
away-from-home Archy target, privately load the image into its actual runtime,
and install that local manifest on this patched host. The host needs a current
public certificate covering its hostname and `turn.` plus that hostname, and
the documented port/firewall access. This pack does not authorise that live
installation. Host preflight must succeed before app startup. The UI opens
through Archy's HTTPS app gate on port 3753. An identity belonging to that Archy
node must sign in again inside the app.

The reproducible component check needs no live node or private backend. Run
the commands in the package README. It runs the actual signed controller with
a fixture signer and node adapter and writes the captures below. This proves
component behaviour, not integration with the real dashboard signer/app gate.

## Named screens and review steps

| Screen | Steps | Expected result |
| --- | --- | --- |
| Install | Privately install the local candidate manifest on the authorised patched host. Also test an unsupported TLS listener/configuration. | Three generated secrets and an owned data volume; no app TLS-key mount or root capability. Unsupported host preflight refuses before changing the application. |
| Launch/sign-in | Launch from Archy; choose a host identity. Repeat in standalone HTTPS and embedded dashboard views; test a denied identity and signer cancellation. | Host gate and signed app login both apply. No cookie alone grants management access. Errors leave a working sign-in/retry path. Embedded view adds no second dashboard navigation or wallpaper. |
| Setup | Leave the away-from-home checkbox clear and try setup; then confirm it and choose limits. Interrupt and retry a partial setup using its saved choices. | Confirmation is required. Only bounded limits are accepted. Private/local relay addresses are refused by the supervisor. Partial state remains recoverable and is not replaced with a fresh identity. |
| Status | Check ready, unpaired, paired, paused, failed-start, offline and expired-session states; refresh and retry. | Counts only; no room identifiers or keys. Start/pause works without deleting saved rooms. Pairing stays disabled until local readiness checks pass. An expired session requires a new signed login. |
| Pairing hand-off | Create a code, scan it on a keeper device, open the link on the same device, and copy it. Wait six minutes or reload. | Local QR, private one-use pairing link, explicit keeper-device instructions and expiry. No pairing link in logs or persistent browser storage. A reload requires signing in again. |
| Delete-everything | Before setup, prepare deletion, restart the container, confirm setup is frozen, then cancel. Repeat after interrupting first setup. With a live room, try preparing deletion. Close rooms in KithMoot, wait for completion, then prepare again. Cancel once; prepare again and use Archy's normal Delete app and data action. | Unused and partially initialised nodes can prepare deletion without starting a backend; unknown runtime files refuse deletion. Active rooms/devices/requests block deletion. Empty-state preparation durably blocks setup and new admission across restart. Cancel restores admission. The host repeats the deletion check before teardown and restores its original routing. The controller signs no room closure. |

Also review keyboard focus, touch targets, scrolling, safe areas and legibility
at 320/390/768/1440 CSS pixels, landscape, enlarged text, reduced motion and a
browser without blur support. Keep the pairing code fully visible and the
delete explanation readable before its action.

## Captures and completed checks

- [Launch/sign-in, 390 px](evidence/kithmoot-node-archy-20261103/01-sign-in-390.png)
- [Deletion before setup](evidence/kithmoot-node-archy-20261103/00-delete-before-setup.png)
- [Setup, 390 px](evidence/kithmoot-node-archy-20261103/02-setup-390.png),
  [320 px](evidence/kithmoot-node-archy-20261103/03-setup-320.png)
- [Status, 390 px](evidence/kithmoot-node-archy-20261103/04-status-390.png),
  [768 px](evidence/kithmoot-node-archy-20261103/05-status-768.png),
  [1440 px](evidence/kithmoot-node-archy-20261103/06-status-1440.png),
  [enlarged text](evidence/kithmoot-node-archy-20261103/07-status-large-text.png)
- [Pairing](evidence/kithmoot-node-archy-20261103/08-pairing-390.png),
  [paused](evidence/kithmoot-node-archy-20261103/09-paused-390.png),
  [delete confirmation](evidence/kithmoot-node-archy-20261103/10-delete-390.png),
  [deletion prepared](evidence/kithmoot-node-archy-20261103/11-delete-prepared-390.png)
- [Embedded styling](evidence/kithmoot-node-archy-20261103/12-embedded-390.png),
  [landscape](evidence/kithmoot-node-archy-20261103/13-landscape.png)

The browser journey passed required setup confirmation, signed setup, status,
pairing hand-off, pause/start, deletion preparation/cancellation and sign-out.
All fourteen captures passed the horizontal-overflow check. Six WCAG A/AA
accessibility scans reported no violations; no page errors occurred. The
enlarged-text run caught and fixed the initial status-grid overflow.

Fourteen controller security/recovery tests and five private packaging tests
passed. Both the canonical Rust manifest parser and the shell validator passed
(18 checks, no warnings). The local image ran as 1000:1000 with a read-only
root, no capabilities, no privilege escalation and a 256 MiB limit.

The separate offline Linux host fixture ran the real private controller,
supervisor, Spry, Shelter, nginx and source-sharing Rust TLS/native relay. Signed
setup/status, QR issuance, pause/restart and prepare/cancel-delete passed, along
with unused-node deletion across restart, partial-init deletion and cancellation
without changing the manifest secrets, manual room admission, encrypted chat, all four authenticated TURN
transports, revocation, room purge, signed completion and cold closure proof.
The exact hardened image also passed the host deletion command before setup
and retained its freeze across a container restart using its owned volume.
The application was denied access to the host's private TLS key. Its fixture
and the browser were stopped after the checks.

## Remaining acceptance

Real Archy install/launch/signing/app-gate UX and deletion UX remain maintainer
review work. The final full-daemon local cargo check exceeded the 3 GiB
build-container memory limit; final hosted backend CI is required. The offline host harness does not run the complete Archy daemon,
perform a real reboot or qualify FIPS. Public certificate trust, another-network
reachability, physical GrapheneOS and cross-client sustained media remain
separate acceptance gates. No public signed node/Shelter release or source
publication is authorised by these checks.

The web/desktop and Android node screens are held separately in KithMoot
[PR 675](https://github.com/forgesworn/kithmoot/pull/675) and
[PR 392](https://github.com/forgesworn/kithmoot-android/pull/392). The web/desktop pack identifies the final port-aware source and successful
local browser/Electron checks. The Android pack is being refreshed after its
final local matrix (4,014 passed tests, one opt-in skip). General ship
instructions and automated checks do not approve those screens either.
