# KithMoot Node dashboard review, 5 November 2026

The private demo now adds editable paused-node limits and actual aggregate
relay statistics to Overview, Connections, Usage, Settings and Diagnostics.
Settings never edit authority, endpoints or keys. Usage separates access grants,
active TURN allocations and stream connections; none is a count of people.

**Maintainer must review and approve UI work on the Archy KithMoot Node
Overview, Connections, Usage, Settings and Change node limits, Diagnostics,
pairing hand-off and delete-everything screens before merging or approval.
ZAT pending.** No reviewed-revision approval is recorded. PR53 remains draft;
no maintainer has been contacted.

## Exact build and access

- Controller source: `6c27156de8f4744c08cf7fefde76b41763c0910d`.
- Spry source: `61b6398da372898dcd684acecde12deb32cea621`,
  [backend PR37](https://github.com/forgesworn/spry-turn/pull/37).
- Draft [app PR53](https://github.com/forgesworn/archipelago-apps/pull/53).
- Private image: `localhost/kithmoot-node:0.1.0-rc.1-leases-282bce1f6b2d`;
  image ID `f3ceaf005904fcbd0e207cddec09dda7d2701d734f9cbd33b343e21ded2b16cc`.
- Open <https://demo.forgesworn.dev/dashboard> through the existing private
  connection and launch **KithMoot Node**. Refresh the app, choose the existing
  identity and approve its HTTP sign-in proof on the linked signer.
  Direct access is <https://demo.forgesworn.dev:3753/> behind the same app gate.
- Keep the [management tunnel](../scripts/node-management-tunnel.sh) running;
  see the [demo access instructions](kithmoot-node-demo-review.md).

The controller and all UI/static assets are unchanged. This backend-only layer
shortens renewable TURN allocation leases to 30 seconds; the separate login
still lasts at most five minutes. Orphaned VPN/NAT routes can release relay
ports before that login expires. The allocation and stream limits are unchanged.
The [guarded deployment receipt](evidence/kithmoot-node-short-leases-live-20261105/deployment.json)
binds the current binary and bundle inventory. Earlier captures below identify
the unchanged UI source; their image receipts remain historical. Sustained
media qualification is recorded below.

## Review steps and expected results

Use an idle node for pause/settings checks. Pausing ends calls and makes rooms
unavailable while preserving saved rooms and messages.

| Screen | Steps | Expected result |
| --- | --- | --- |
| Overview | Sign in, inspect services, room/access/pending counts; use keyboard navigation. | Named observations and explicit unknown states. Offline access grants are not people online. Private controls expiry does not stop calls. |
| Connections | Check both public hostnames, certificate expiry and all nine local checks, including TLS443. | Local evidence is distinguished from an outside-network call. Certificate verification stays enabled. No host certificate key is mounted. |
| Usage | Observe two refresh samples; inspect UDP and TCP/TLS cards, gauges, payload totals, rate, drops and errors. Pause and inspect again. | Real aggregate observations, no participant addresses or room content. First/restarted/stale samples have unavailable rates. Zero remains zero. Paused relay counters are unavailable. |
| Settings | While running, inspect saved limits and disabled Change limits. Pause on Overview, return and open Change limits. | The four setup limits are editable only when explicitly paused. Paths, endpoints, identities and room policy are fixed. |
| Change node limits | Change Hosted rooms from4 to8 and Save settings. Inspect previous limits. Start explicitly from Overview. Pause and Restore previous limits, then Start explicitly. | Save and restore keep paused. Each start uses the saved values. Previous limits restore4 without changing room data or keys. |
| Change node limits rejection | Try a room cap below saved rooms or storage below message-file footprint. Keep a second stale tab and save from the first. Switch the network with an unsaved form. | Unsafe reductions fail without deleting data. A stale tab cannot overwrite newer settings. Errors and connection changes preserve the draft; Cancel/refresh reloads current values. |
| Diagnostics | Inspect checks, copy support report, exercise unavailable backend fixture. | Fixed aggregate summary excludes secrets, identities, room IDs and participant addresses. No automatic upload, history or external-call pass. |
| Pairing/deletion | Open pairing and return. Prepare/cancel deletion only with an empty test node. | Single-use pairing expiry and existing durable deletion freeze remain. Never delete the occupied demo room. |

## Measurement meanings

Forwarded bytes are accepted relay payload in both directions, excluding
STUN/TURN/TLS headers. Stream output counts when queued and does not prove
remote delivery or billable WAN usage. TCP and TLS share one bucket, including
host-terminated TLS; individual listener ports cannot be inferred. Stream
errors cover fatal relay framing, queue and socket errors; ordinary EOF and
revocation are excluded. These are not a count of failed calls or host TLS
handshake failures. Refused streams are connection-capacity refusals.

The controller signs only the fixed read-only loopback status request using
its existing service identity/pairing. New detailed metrics are not exposed by
the public status route. Samples contain an internal per-start epoch and
monotonic age; the browser gets only projected aggregates. No history is stored.
Rates reset on outage/restart/counter rollback; unknown is never fabricated zero.

## Component verification

[Component receipt](evidence/kithmoot-node-settings-metrics-20261105/component-review.json):
32 controller/control-socket/observation/settings tests; five private packaging
tests; production build;
56 browser captures;20 WCAG A/AA scans with no reported violations or page
errors. Captures cover320/390/768/1440px, landscape,200% text, reduced motion,
no-blur, actual fixture iframe, settings rejection/conflict and manual restore.
The receipt binds source and compiled assets to SHA256 values. Fixture signer,
backend and host observations are distinguished from the real private demo.

Reproduce with Node24 and pinned dependencies:

```sh
npm ci --prefix experimental/kithmoot-node --ignore-scripts --no-audit --no-fund
npm ci --prefix tests/smoke --ignore-scripts --no-audit --no-fund
npm --prefix experimental/kithmoot-node test
npm --prefix experimental/kithmoot-node run build
E2E_KITHMOOT_NODE_UI=component-review node experimental/kithmoot-node/browser-review.mjs
```

Review captures:

- [Settings editor, narrow](evidence/kithmoot-node-settings-metrics-20261105/settings-editor-390.png)
- [Settings editor, enlarged text](evidence/kithmoot-node-settings-metrics-20261105/settings-editor-large-text.png)
- [Unsafe reduction](evidence/kithmoot-node-settings-metrics-20261105/settings-editor-room-rejected.png)
- [Stale revision](evidence/kithmoot-node-settings-metrics-20261105/settings-editor-conflict.png)
- [Saved, paused and previous limits](evidence/kithmoot-node-settings-metrics-20261105/settings-saved-paused.png)
- [Transport stats](evidence/kithmoot-node-settings-metrics-20261105/dashboard-usage-390.png)

The app retains its existing semantic Archy tokens, dark/glass/orange baseline,
4px layout,48px controls, visible focus and transparent embedded canvas with
local readable surfaces. No host shell, fonts, wallpaper or UI kit is added.
The current official Archy design skill/contract and local maintainer feedback
were checked. The composed host still has its pre-existing viewport zoom
restriction; do not describe fixture accessibility results as whole-host proof.

## Private delivery and remaining gates

The guarded image update preserved room/account custody, settings/secrets,
Shelter/supervisor bytes, host binary/nginx and the other five containers.
The Spry binary and its bundle inventory changed together. No active node relay
sockets existed before switching. The previous image and a root-only cold data
backup are retained; rollback restores image references without overwriting
new room data. No source, private image or installer was published for Shelter.

[Live deployment](evidence/kithmoot-node-settings-metrics-live-20261105/deployment.json),
[browser receipt](evidence/kithmoot-node-settings-metrics-live-20261105/browser.json),
[settings transaction](evidence/kithmoot-node-settings-metrics-live-20261105/settings.json)
and [actual status](evidence/kithmoot-node-settings-metrics-live-20261105/status.json)
record the real dashboard gate, linked signer,24 captures and exact static
asset readback. Saving4 to8 rooms kept paused, Start applied8, manual Restore
kept paused and a final explicit Start returned to4. Room and access counts
were preserved. Live relay payload/rate were zero while idle, rather than a
synthetic call result. Gauges and counters were present; socket regressions
separately verify nonzero UDP/stream forwarding, drops and errors.

Five actual composed-host scans retain only the existing viewport zoom
restriction; no violation was reported inside the node iframe. There were no
page errors. Actual narrow captures are desktop Chromium, not a physical phone.

Live maintainer captures:

- [Editor](evidence/kithmoot-node-settings-metrics-live-20261105/settings-editor-390.png)
- [Saved and paused](evidence/kithmoot-node-settings-metrics-live-20261105/settings-saved-paused-390.png)
- [Restored and paused](evidence/kithmoot-node-settings-metrics-live-20261105/settings-restored-paused-390.png)
- [Actual relay stats](evidence/kithmoot-node-settings-metrics-live-20261105/usage-390.png)

Actual dashboard, linked-signer, metrics and save/start/restore/start evidence
is separate from component results. The separate browser run below adds
controlled public-network media evidence. Physical-phone, commercial-VPN and
Companion WebView acceptance remain unclaimed. Maintainer review of this
material UI revision remains pending.


## Sustained browser continuity on the current backend

The [actual browser record](evidence/kithmoot-node-short-leases-live-20261105/sustained-media.json)
passes 736 seconds with 611 seconds after final confirmed recovery. VPN-on,
VPN-off and a 12-second outage recovered in 13.859/11.687/2.340 seconds.
Both guests advanced received audio/video and visible frames at all 264
checked steady samples, renewed 300-second logins and continued beyond the
previous expiry. [Normal TLS readback](evidence/kithmoot-node-short-leases-live-20261105/public-web-assets.json)
confirms the public renderer was unchanged. The test uses native desktop
Chromium 151, synthetic capture and controlled shared WireGuard/NAT through
an opaque port 443 proxy; it does not qualify a physical phone or commercial VPN.

This is one continuity pass. Earlier post-update attempts missed the 20-second
recovery gate. The passing run still observed five transient TURN486 errors;
one-second port counts reached 32, while the ten-second statistics peaked at 26.
The distinct stream-connection refusal counter stayed at zero. RTP freeze
counters include inactive slots and retiring generations; they are recorded,
not interpreted as a visible playback score. Smoothness, all-attempt recovery,
independent NATs and capacity remain unqualified. The existing quota stays in
force; short leases bound abandoned occupancy rather than remove the ceiling.

[Cleanup readback](evidence/kithmoot-node-short-leases-live-20261105/cleanup.json)
confirms the task's VPN, carrier, observer, build source/target and temporary
context were removed, with the node ready and unrelated apps unchanged.
Maintainer ZAT of the named screens and exact current candidate remains pending.
