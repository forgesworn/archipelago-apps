# KithMoot Node review on demo

The private dashboard was updated on 5 November 2026 with editable paused-node
limits and real aggregate UDP/TCP-TLS relay statistics. The actual dashboard
gate and linked signer passed save/start/restore/start checks: settings returned
to their original values and the node is running and ready. The
[dashboard review pack](kithmoot-node-dashboard-review.md) and
[live deployment receipt](evidence/kithmoot-node-settings-metrics-live-20261105/deployment.json)
identify the UI source, test steps, captures, limits and pending ZAT.
A later backend-only short-lease image is the current candidate; its
[guarded deployment](evidence/kithmoot-node-short-leases-live-20261105/deployment.json)
records unchanged UI/static assets, saved room/admissions and other apps.
The [sustained browser record](evidence/kithmoot-node-short-leases-live-20261105/sustained-media.json)
passes a 736-second controlled continuity run, including 611 seconds after
recovery. Earlier recovery failures, transient quota errors and remaining
quality/device limits are retained in that record and the dashboard pack.

The earlier setup, pairing hand-off, pause/start and deletion
preparation/cancellation checks remain historical baseline evidence in the
[3 November receipt](evidence/kithmoot-node-demo-20261103/qualification.json).
The owner confirmed that baseline as “Paired and ready”. This dashboard update
preserved the paired account and saved room; it did not exercise destructive
room controls again.

The owner authorised this private installation on 3 November 2026. It is a
review candidate, outside the published app catalogue. No Shelter source,
private image or public node release has been published.

## Access

Keep an SSH SOCKS tunnel open:

```sh
scripts/node-management-tunnel.sh root@95.216.164.146 1080
```

The [tunnel helper](../scripts/node-management-tunnel.sh) reconnects after a VPN
or Wi-Fi change. Keep it running. It binds only local loopback.

Use an Archy browser profile with SOCKS5 `127.0.0.1:1080` and DNS through the
proxy. Open <https://demo.forgesworn.dev/dashboard>, log in with the existing
dashboard account, then launch **KithMoot Node**. The app endpoint is
<https://demo.forgesworn.dev:3753/>; its outer gate requires the dashboard
session. Inside the app, choose the existing linked identity and approve
the local sign-in proof on its signer. This is separate from pairing your KithMoot account in its app.

The public certificate covers `demo.forgesworn.dev` and
`turn.demo.forgesworn.dev`. The dashboard and operator app remain private.
External callers receive only the room node's explicit API and authenticated
TURN transports. Existing Spry ports and app data are retained.

## Controls sessions

The controls sign out after 30 minutes without user activity, with an absolute
eight-hour limit. Tokens stay in this tab’s memory. Automatic status polling
does not extend the timeout; explicit use does. Signing out revokes the controls
token. Session expiry and sign-out do not stop rooms or calls. TURN logins retain
their separate maximum five-minute lifetime. The session policy passes 17
controller/control-socket checks, including clock rollback and the hard limit.

The status label is **Devices with access**. It includes offline devices and
counts a device separately in each room. It is not a live people count. The
KithMoot room shows current participants. Temporary test-browser permissions
remain until the room manager removes them or closes the test room.

## Devices and connections

“Your KithMoot account” replaces “keeper device” in the controls. Open the
pairing link in the browser, computer or phone you want to use; sign in to the
same KithMoot account on each device. No special hardware is required.
The [updated component review](evidence/kithmoot-node-copy-20261103/component-review.json)
contains 15 captures and six clean accessibility scans, including a failed
management fetch and retry. A lost management connection is now named as an
Archy controls connection error instead of “The node is unreachable” or the
browser’s raw “Failed to fetch”.

KithMoot room HTTPS, relay and TURN traffic use the public node routes. Private
Archy management uses its private connection. Keep those two access paths
separate when diagnosing VPN changes.

## Revision

- Operator UI/controller source: `6c27156de8f4744c08cf7fefde76b41763c0910d`.
- Patched host source: `f389e68b904e21dbd54343d4b71a61bac78efd11`, patches
  0035–0045, backend patch level 10.
- Native private image: `localhost/kithmoot-node:0.1.0-rc.1-leases-282bce1f6b2d`.
  Its image ID is `f3ceaf005904fcbd0e207cddec09dda7d2701d734f9cbd33b343e21ded2b16cc`.
  This private app layer adds the short-lease Spry binary over the exact
  `a4d0e41dc7de` settings/metrics image. Supervisor and Shelter bytes are unchanged;
  the Spry binary and its bundle inventory are updated together.
- Bundle inventory SHA-256:
  `b5b20be14a391fd0888afe7e6180212bc73e3ba85ea9348b0f0c9a785ca25abc`.
- Spry source: `61b6398da372898dcd684acecde12deb32cea621`,
  [PR37](https://github.com/forgesworn/spry-turn/pull/37), merged as
  `b7c291beff42ef970d6f536f0fe8ae3df3a76134` with the identical source tree, based on the
  metrics implementation merged in PR36. Private allocation leases are 30
  seconds and refreshable; TURN logins remain bounded at five minutes.
  The independent TCP/TLS handshake limit remains 64 and allocations remain
  32, eight per username. Controller, host and other bundle bytes are unchanged.
  The prior `a4d0e41dc7de` image and a cold data backup are retained for rollback.
- The existing dashboard frontend is retained. The real host supplies its
  session gate, identity picker and Nostr signer.

The native daemon uses release-built dependencies with the daemon crate at
opt-level 0 and 256 codegen units to fit the review host. Normal full-release
builds run separately in CI. This candidate establishes functionality, with no
capacity or performance claim. The current UI/controller adds the five-view operational dashboard; the account wording, access-count explanation, private connection errors and controls session policy remain in place.

## Review

Use the named-screen actions and expected results in the
[Archy review pack](kithmoot-node-archy-review.md#named-screens-and-review-steps).
In particular:

1. Launch from the authenticated dashboard. Check sign-in, denied identity,
   cancellation, expiry and retry in standalone and embedded views.
2. Confirm the away-from-home setting before setup. Check unconfigured,
   ready, paused, restarting and failed-start status, including recovery.
3. Create a pairing code. Check its QR, copy and same-device link, explicit
   account instructions, one-use behaviour and expiry. The public web client
   includes pairing; identify any native client candidate separately.
4. With no rooms, prepare deletion, cancel it and check admission is restored.
   Review Archy's normal **Delete app and data** hand-off. Do not delete any
   room that another reviewer is using.
5. Check keyboard, focus, 320/390/768/1440 widths, landscape, enlarged text,
   reduced motion and standalone/embedded appearance.

The owner clarified on 3 November that ZAT is required only when submitting
back to the official Archy repository. It does not gate ForgeSworn's KithMoot
or private node delivery. No official upstream submission or approval is claimed.
For that official submission: **Maintainer must review and approve UI work on
the Archy install, launch, pairing hand-off, delete-everything and status screens
before merging or approval. ZAT pending.** No maintainer message has been sent.

## Pair from the web

Web pairing was first verified from merge `2c1977dacad883d730bd7ec6cfc9c66dbfe99486`
in release `20261103T101924Z`. The current web deployment is
`0102c468d663ec80aa8da3260bbb1d4295e18f1d`, release `20261104T061508Z`.
Its public index, entry script and main script match the qualified local build
byte for byte. It includes authenticated socket probes, bounded subscription
recovery, fixed media slots and fresh TURN allocations. An established remote
participant's route failure now rebuilds only that pair; healthy participants
keep their native connections. The original global credential rotation remains
in force. A real three-browser native regression verifies healthy audio/video
keeps advancing during another pair's recovery; the prior source fails it.

The [scoped recovery receipt](https://github.com/forgesworn/kithmoot/blob/01b154eec2e650e3ee83889faaa9f59935be8f25/docs/evidence/kithmoot-node-scoped-recovery-tls443-20261103.json)
records the historical 459-second matched-pair audio/video run over TURN TLS443, including
VPN on/off, a 12-second outage and credential renewal. It continued 312 seconds
after final recovery across the prior login expiry. Recovery took 13 seconds
on VPN, 36 seconds off VPN and 8 seconds after the outage. The 25-second steady
media-gap limit remained in force; there were no browser errors or subscription
overflows (peak 13). Candidate source `44a923c9` ran against the real public node
under production headers; historical release `20261103T221208Z` (`d7ce79ef`)
has identical main script bytes.
A separate 24-second direct production-browser smoke received 420/443 decoded
frames and 1,240/1,332 audio packets without candidate interception or manual
retry. One earlier repeated startup timed out before joining; its cause is not
established and is recorded separately. No claim that every initial join or
network transition is seamless follows from these tests.

The earlier 503-second run counted aggregate room media, which could hide a
frozen pair. The previous production and rotation-grace builds failed that
stricter renewal gate. A later cached-login-only candidate failed VPN-off
recovery and was replaced with fresh per-peer logins before merge. Independent
VPNs, physical mobile handoff, GrapheneOS and capacity remain separate gates.

The earlier [startup and allocation receipt](https://github.com/forgesworn/kithmoot/blob/a6783526290538ef5d631353cdd8df5ca213e1ff/docs/evidence/kithmoot-node-startup-allocation-20261103.json)
records bounded startup retries and `max-bundle` allocation gathering without
raising the node quota. Eighty-nine focused tests pass (two skip), three native
journeys pass, and all five applicable hosted checks pass. The deployed renderer
passes a separate sixty-second room lifecycle with real isolated Spry/Shelter,
including initial HTTP503 recovery, moving audio/video, signalling recovery,
removal and purge. Private fixture HTTP forwarding and WebSocket bridges are
used; the renderer is loaded directly from production without interception.
This is not a run against the owner's public node. Public asset readback uses
normal certificate validation; the private fixture accepts its self-signed TLS.

The [4 November public recovery receipt](https://github.com/forgesworn/kithmoot/blob/e83e51f07721b672ccd13fc5017bf9853c0f7e9b/docs/evidence/kithmoot-node-public-vpn-recovery-20261104.json)
qualifies the tighter gate for web `9e8d547a`: 430 seconds of actual production
media, including 310 seconds after final recovery. VPN-on/off and outage
recovery take 13.162/10.860/8.447 seconds, all below twenty seconds. A sampled
seven-second pause during routine login renewal prompted the later handover fix.

PR694 retains one connected media generation until its replacement connects
plus one second, with a twenty-second bound. Mute/audience changes affect both;
closing a peer or withdrawing access still closes retained transports. Its
candidate passes 429 seconds, 311 after recovery, with zero received or visible
media stalls in 133 checked steady samples per guest. Both logins renew and
the previous expiries are crossed. The later actual production run of `074dbb8f` failed VPN-on recovery: writes
reconnected before the persistent room readers. PR695 fixes that reader
cooldown; PR696 also fixes delayed legacy answers and early redial timers.
The five applicable hosted checks, 174 focused tests (three skips), typecheck,
build and three real Spry/Shelter browser journeys pass. No new admission is
created. No owner keys are accessed or admission bypassed. Physical phones,
commercial VPNs, GrapheneOS and capacity remain separate checks.

The [final production proof](https://github.com/forgesworn/kithmoot/blob/4fbb03f5a049efb8328c63cb1b998278bee054a2/docs/evidence/kithmoot-node-renewal-continuity-20261104.json)
records 442 seconds of actual deployed browser audio/video, including 310
seconds after final confirmed recovery. VPN-on, VPN-off and outage recovery
take 18.006/16.736/2.100 seconds. Both browsers renew logins and continue beyond
the previous expiry. All 132 steady samples per guest advance received
audio/video and displayed frames, without page errors, authentication refusals
or subscription overflow (peak 13). All five applicable source PR checks pass;
Node24 passes 8,861 tests with eight skips. This qualifies the controlled
Chromium case at roughly two-second sampling, not physical Wi-Fi/cellular,
commercial VPNs, GrapheneOS or capacity. Test networking fixtures have been
removed; the private demo and owner management connection remain running.

Open KithMoot and accept **Update now** if an older
installed web app is still running. Refreshing alone can retain the previous
service worker. Generate a fresh code in Archy, open its link, sign in to the
KithMoot account and choose **Pair node**. **Check status** should show
`demo.forgesworn.dev` ready. No native app is required. The owner completed this
journey successfully. No site data, saved room or identity was cleared.

## Completed live checks

- Normal public certificate validation and actual dashboard identity picker.
  The owner approved the linked signer authentication proof. No local identity
  or signing key was created.
- Initial setup on the rented host; ready, unpaired, zero rooms/devices/requests.
  Local pairing QR and link presence checked without recording a live secret.
- Pause/start and empty-state deletion preparation/cancellation. No room created
  by the automated review. The owner subsequently paired their own account.
- Actual dashboard embedded launcher and HTTPS app gate. The local controller
  interface declares HTTP for readiness; the browser gate remains authenticated
  HTTPS. No container restart or node data change was needed for that correction.
- Effective kernel memory limit 268435456 bytes; `/tmp` is a 16 MiB tmpfs with
  noexec/nosuid/nodev. UID 1000, read-only root, no capabilities and no-new-privileges
  confirmed. Existing five app containers retained their IDs and images.
- Public TURN TLS443 STUN binding response; external dashboard and signer
  denied, including spoofed forwarding headers. This is not a media-call test.
- Ingress install/remove/recovery on Debian 13 with Python 3.13 and the real
  certificate. Certificate regression tests: 8 passed; dashboard guard: 13
  passed; Nginx Proxy Manager bridge: 24 passed.
- Existing dashboard frontend, original app manifests and session secret
  retained. Maintenance and manager restart preserved ingress and running apps.

[Live sign-in](evidence/kithmoot-node-demo-20261103/01-sign-in.png),
[setup at 390 px](evidence/kithmoot-node-demo-20261103/02-setup-390.png),
[ready](evidence/kithmoot-node-demo-20261103/03-ready.png) and
[deletion prepared](evidence/kithmoot-node-demo-20261103/04-prepared-delete.png),
[embedded launch](evidence/kithmoot-node-demo-20261103/05-embedded.png) and
[web pairing at 390 px](evidence/kithmoot-node-demo-20261103/pairing-phone.png).

## Recovery

The host's private review directory is
`/root/kithmoot-node-review-20261103`. It retains build/deployment receipts,
the previous daemon and a private control-plane rollback archive. It contains
private material and must not be uploaded to a PR.

To roll back, close any review rooms in their keeper's app, then uninstall only
`kithmoot-node` through Archy's normal lifecycle with `preserve_data: true`.
Wait for removal and the node ingress transaction to restore its original
configuration. The node helper restores the normalised managed base profile;
the legacy custom demo TLS profile requires the saved full control-plane
rollback. Restore the saved daemon/runtime/nginx control plane, reload
systemd and nginx, and verify the dashboard and original apps. Remove only UFW
rules labelled `kithmoot-node-review-20261103`. Retain the app's data and the
expanded certificate; neither needs to be destroyed for rollback.

Controlled public TLS443 media and route recovery are recorded separately from
UI acceptance. Independent networks, capacity and physical GrapheneOS remain
separate acceptance gates.

## 5 November guarded dashboard update

The update changed only the app image reference in its two manifest copies and
Quadlet. Host binary/nginx hashes and the other five container identities were
verified unchanged. There were no active node TURN relay sockets before the
switch. The account, saved room, settings and secrets were preserved. The
[receipt](evidence/kithmoot-node-dashboard-live-20261105/deployment.json) records
exact image IDs and runtime/static-asset verification.

Container inspection must run through the delegated Archy user service, for
example `systemd-run --user --pipe --wait --collect` around `podman exec` under
that user. Direct `runuser` from a root SSH cgroup lacks the required delegated
cgroup access. The node runtime is
`/opt/kithmoot-node/current/runtime/bin/node`, not `/usr/bin/node`. No persistent
cgroup, user-session or host configuration change was required.

The first live SQLite backup attempt waited on an exclusive runtime lock. It
was stopped before changing services. A complete cold copy was then taken
while the node was stopped for the guarded switch. The root-only rollback
folder is `/root/kithmoot-node-dashboard-20261105/`; it retains the old manifest
copies, full data backup, parent image ID, before/after receipts and
`rollback.py`. That guarded rollback script refuses a newer image or active
node relay sockets and restores only the prior image references. It does not
overwrite current room databases. Do not restore the cold data copy over newer
messages as part of a normal UI rollback.

The actual embedded journey passed all five views at 1440px and 390px, live
metrics, exact assets, scrolling to footer actions, and standalone sign-in.
It retained 21 captures and no page errors. Each of five live accessibility
scans reported the host's pre-existing viewport zoom restriction, with no
reported node-frame violation. Physical mobile browsers, Companion WebViews
and new outside-network media are separate gates. No new room, grant, pairing
code, pause or deletion was issued by this live UI journey.
