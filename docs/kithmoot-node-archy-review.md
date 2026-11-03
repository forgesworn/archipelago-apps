# KithMoot Node: Archy maintainer review

The owner clarified on 3 November that maintainer ZAT applies only when
submitting back to the official Archy repository. It does not block delivery
through ForgeSworn's repositories or the authorised demo installation.

For official Archy submission: **Maintainer must review and approve UI work on
the Archy install, launch, pairing hand-off, delete-everything and status screens
before merging or approval. ZAT pending.** No official submission or maintainer
approval has been recorded; no maintainer message has been sent.

## Exact candidate

- UI/controller source: `bd7d0c8f5077d1ceef6b26f4c768052a5ffe5066`.
- Draft [PR 53](https://github.com/forgesworn/archipelago-apps/pull/53).
- Live Linux x64 candidate: see the [demo review pack](kithmoot-node-demo-review.md)
  for the installed image, patched host revision, private access and rollback.
- The original [ARM64 fixture evidence](evidence/kithmoot-node-archy-20261103.json)
  and [component receipt](evidence/kithmoot-node-archy-20261103/component-review.json)
  remain historical evidence for the original operator UI/controller. The
  [current component receipt](evidence/kithmoot-node-copy-20261103/component-review.json)
  covers the revised wording, access count, connection errors and session policy.

The owner authorised the private demo installation on 3 November. Open
<https://demo.forgesworn.dev/dashboard> through the Archy SSH SOCKS browser
profile, launch KithMoot Node and approve its local sign-in proof using the
existing linked signer. The direct endpoint is <https://demo.forgesworn.dev:3753/>.
The app gate requires a dashboard session and private connection. The image
and private Shelter inputs have not been published to a registry.

## Build and setup

The [private package instructions](../experimental/kithmoot-node/README.md)
provide reproducible local preparation commands. Host preflight requires a
current public certificate covering the hostname and its `turn.` hostname.
The [live review pack](kithmoot-node-demo-review.md) identifies the current
candidate and full evidence; no additional live target is authorised by this
note. Record a new reviewed revision after material UI changes.

The reproducible component check needs no live node or private backend. Run
the commands in the package README. It runs the actual signed controller with
a fixture signer and node adapter and writes the captures below. This proves
component behaviour. The separate demo receipt records integration with the
real dashboard signer/app gate.

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
build-container memory limit. The same final patched source at `66f7573a`
passed hosted backend run `41578160185`, including full daemon build and
Docker host checks; all 13 qualifying checks passed, with three deliberate
image/publication skips. The offline host harness does not run the complete Archy daemon,
perform a real reboot or qualify FIPS. Public certificate trust, another-network
reachability, physical GrapheneOS and cross-client sustained media remain
separate acceptance gates. No public signed node/Shelter release or source
publication is authorised by these checks.

The web node screens shipped in KithMoot
[PR 675](https://github.com/forgesworn/kithmoot/pull/675), with browser media
recovery in [PR 686](https://github.com/forgesworn/kithmoot/pull/685). The live
release and controlled TLS443 call results are in the demo review pack.
The packaged desktop release and Android node UI
[PR 392](https://github.com/forgesworn/kithmoot-android/pull/392) remain separate;
no new native UI release is claimed. The Android candidate's local matrix
passed 4,014 tests with one opt-in skip. Official Archy UI acceptance remains
pending for this review revision.
