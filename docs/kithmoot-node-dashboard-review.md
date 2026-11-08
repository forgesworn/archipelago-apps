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

## 8 November 2026: pairing copy under a blocked clipboard policy

Review candidate only; this fix is unmerged and not deployed to Archy. The affected screen is **KithMoot Node → Settings → Pair with KithMoot →
pairing hand-off**, also reachable from Overview. The Diagnostics copy button
is outside this change.

**Maintainer must review and approve UI work on the Archy KithMoot Node pairing
hand-off screen before merging or approval. ZAT pending.** No maintainer has
been contacted and no approval of this candidate is recorded.

### Candidate and setup

The source base is `acaa3ca88e97a8a17b39cd7800a2a57e786f8b9b` on local branch
`fix/kithmoot-node-clipboard-20261108`. Identify this exact UI
candidate with these source/build hashes, also present in the machine-readable
[focused receipt](evidence/kithmoot-node-clipboard-20261108/clipboard-policy/component-review.json):

| File | SHA-256 |
| --- | --- |
| `experimental/kithmoot-node/client.mjs` | `b89648fc82802b632b764d29f0b50f683891183780ba5c4c760fc202418368b6` |
| `experimental/kithmoot-node/public/style.css` | `c335dae786d6bf5f72d4da6bacbfd7954f4bacea1290f9af6a1f2bb30b65528f` |
| Built `dist/public/client.js` | `cddfd462ae87823432736f1db9ef0ec69bda4eaee362a66e242a7af7829bea6c` |

Use Node 24 and the pinned dependencies. Rebuild and reproduce the focused
fixture from the repository root:

```sh
npm ci --prefix experimental/kithmoot-node --ignore-scripts --no-audit --no-fund
npm ci --prefix tests/smoke --ignore-scripts --no-audit --no-fund
npm --prefix experimental/kithmoot-node run build
E2E_KITHMOOT_NODE_UI=component-review E2E_KITHMOOT_NODE_CLIPBOARD_ONLY=1 E2E_KITHMOOT_NODE_REVIEW_OUTPUT=/tmp/kithmoot-node-clipboard-review node experimental/kithmoot-node/browser-review.mjs
```

The harness opens `https://node.example:3753/review-host-no-clipboard` in an
actual iframe, with a real `Permissions-Policy: clipboard-write=()` response.
The signed controller is real; the signer, backend and host gate are fixtures.
This URL exists only inside the routed browser fixture; it is not a deployed
service. The live `https://demo.forgesworn.dev:3753/` still serves the old UI.
All captured pairing material is a non-functional fixture string.

### Review actions and expected results

1. Sign in to the fixture, choose Pair with KithMoot and Copy pairing link.
   With policy denying clipboard writes, a plain manual-copy instruction must
   appear. The read-only Private pairing link field must hold the exact link,
   have focus and select the complete value. No Chromium error is shown as
   the user-facing instruction and no false copied-success message appears.
2. Select/copy the field using keyboard or the touch menu. The Open KithMoot
   link and QR remain available. The app requests no broader host permissions.
3. Repeat without the Clipboard API. The same selected-field fallback applies.
   In the ordinary clipboard-enabled standalone case, Copy still succeeds and
   the system clipboard contains the exact fixture link.
4. Advance six minutes, including while a clipboard operation is pending.
   The field, QR and open link disappear. A late completion cannot restore the
   code or replace the expiry message with a copied-success message.
5. Inspect 320/390/768/1440 px, landscape and 200% text. The field follows the
   existing control tokens, is labelled and has no page-level horizontal
   overflow. The full host fixture and this changed screen remain distinct
   from physical-device and maintainer acceptance.

[390 px fallback](evidence/kithmoot-node-clipboard-20261108/clipboard-policy/pairing-copy-blocked-390.png),
[320 px fallback](evidence/kithmoot-node-clipboard-20261108/clipboard-policy/pairing-copy-blocked-320.png),
[200% text](evidence/kithmoot-node-clipboard-20261108/clipboard-policy/pairing-copy-blocked-large-text.png).

### Verification and scope

- Before the fix, the real policy-denied iframe reproduced the missing fallback:
  the regression timed out waiting for manual-copy guidance after Copy.
- Build, syntax checks and all 32 controller tests pass.
- The [full browser journey](evidence/kithmoot-node-clipboard-20261108/component-review.json)
  passed with 61 captures, 21 accessibility scans and no page errors.
- The final focused run passed with six full-frame captures, one accessibility
  scan and no page errors. Its harness adds full-height capture and 200% text
  coverage after the full journey; the product source/build hashes are unchanged.
- Pairing secrets remain transient in the current page and are cleared by the
  existing expiry/navigation/sign-out paths. No new service, stored data,
  recipient or authority is introduced. Clipboard policy is not relaxed.
- The live server, public TURN, room routing, settings and existing sessions
  were not changed. Desktop/Android/web account pairing and actual calls remain
  separate migration checks. No fixture server is left running.

## Exact build and access

- Controller source: `6c27156de8f4744c08cf7fefde76b41763c0910d`.
- Spry source: `31c728f947fda91b8500748edf5ff913452aec38`,
  [backend PR38](https://github.com/forgesworn/spry-turn/pull/38).
- Draft [app PR53](https://github.com/forgesworn/archipelago-apps/pull/53).
- Private image: `localhost/kithmoot-node:0.1.0-rc.1-capacity-8b815bbabe06`;
  image ID `2ccdc2b17784f9df107080279c112e565a5a1615f85336e92d6842c1ecf08ef5`.
- Open <https://demo.forgesworn.dev/dashboard> through the existing private
  connection and launch **KithMoot Node**. Refresh the app, choose the existing
  identity and approve its HTTP sign-in proof on the linked signer.
  Direct access is <https://demo.forgesworn.dev:3753/> behind the same app gate.
- Keep the [management tunnel](../scripts/node-management-tunnel.sh) running;
  see the [demo access instructions](kithmoot-node-demo-review.md).

The controller and all UI/static assets are unchanged. The backend retains
30-second renewable allocation leases and five-minute logins. It also reclaims
already-expired capacity before a new Allocate and exposes separate private
aggregate refusal counters. These additional counters do not add dashboard
fields: the existing projection and UI remain unchanged. The limits stay at
32 total allocations, eight per username and 64 streams.
The [guarded deployment receipt](evidence/kithmoot-node-recovery-live-20261105/deployment.json)
binds the current binary and inventory. Earlier captures identify the same UI
source; their image receipts remain historical.

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


## Earlier short-lease continuity qualification

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


## Current client and backend qualification

[Public release readback](evidence/kithmoot-node-recovery-live-20261105/public-web-assets.json)
records release `20261105T143709Z`, source `6b5147d7`, merged through
[KithMoot PR709](https://github.com/forgesworn/kithmoot/pull/709). The web app
now defers a generic native ICE restart and its offer until node credential
recovery can rebuild or resume that connection. The website and signed native
update feeds are unchanged; this is not a new desktop or Android package.

The [comparison record](evidence/kithmoot-node-recovery-live-20261105/sustained-media.json)
retains the backend-only run, isolated client candidate and unmodified public
run. The final public run passes 749 seconds, including 610 seconds after final
recovery, with advancing audio/video and displayed frames at 269 checked
steady samples per guest. VPN on/off and outage recover in
16.556/16.894/2.088 seconds. Both guests renew beyond old login expiry and
expose no TURN486/508 events. No new whole-server allocation refusals occur;
28 node-wide per-login refusals remain unattributed. Requests are not failed
calls. Limits are unchanged and wider capacity remains unqualified.

The owner reported updating the managing room tab before this run. Participant
activity outside the controlled pair is not fixed, so aggregate differences
are not a causal capacity comparison. Synthetic capture, a shared controlled
WireGuard/NAT carrier and browser UDP restrictions do not qualify physical
phones, independent NATs, commercial VPNs or perceptual smoothness. Maintainer
ZAT of the named screens and exact current UI remains pending.

[Final cleanup readback](evidence/kithmoot-node-recovery-live-20261105/cleanup.json)
records the test browsers, networking fixtures, carrier, observers and SSH11080
closed, with saved settings/keys and the other five apps unchanged. The node
remains paired and ready. Original admitted visitor files and owner1080 were
untouched; the previous private image and cold backup remain for rollback.
