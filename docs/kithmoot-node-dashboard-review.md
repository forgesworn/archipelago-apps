# KithMoot Node dashboard review, 5 November 2026

The node controls now explain what is running, which limits are saved, what
each local connection check established and which measurements are unavailable.
The previous single status view hid the saved settings and discarded the
doctor's individual results. Pending operations are now labelled accurately;
access grants remain distinct from people online and TURN allocations.

**Maintainer must review and approve UI work on the Archy KithMoot Node
Overview, Connections, Usage, Settings, Diagnostics, pairing hand-off and
delete-everything screens before merging or approval. ZAT pending.**
No maintainer decision or reviewed-revision approval is recorded. The existing
draft PR remains held; no maintainer has been contacted.

## Exact revision and access

- Dashboard source: `3d10482dd04bd163d44ff230bdb6ea71f61070c4`.
- Draft [PR 53](https://github.com/forgesworn/archipelago-apps/pull/53).
- [Component receipt](evidence/kithmoot-node-dashboard-20261105/component-review.json)
  records that source revision, source and compiled-asset SHA256 values,
  captures and accessibility results. Fixtures supply the signer, backend and
  host canvas; HTTP authentication uses the real controller.
- This revision is **not deployed**. The existing private demo at
  `https://demo.forgesworn.dev:3753/` still uses controller `bd7d0c8f5077d1ceef6b26f4c768052a5ffe5066`
  and image `localhost/kithmoot-node:0.1.0-rc.1-8961b322e310`.
  Its [access instructions](kithmoot-node-demo-review.md) are for that baseline.
  A running old demo is not acceptance of these new screens.

## Reproduce the component build

Use Node 24, check out the source revision above and install the pinned tools:

```sh
npm ci --prefix tests/smoke --ignore-scripts --no-audit --no-fund
npm ci --prefix experimental/kithmoot-node --ignore-scripts --no-audit --no-fund
cd experimental/kithmoot-node
npm test
npm run build
E2E_KITHMOOT_NODE_UI=component-review node browser-review.mjs
```

The browser runner uses loopback HTTP behind intercepted fixture HTTPS URLs;
it does not bypass the production HTTPS requirement, access the real signer,
start real backends or create room grants. It closes its browser and HTTP
listener even on failure. Playwright Chromium must be installed locally; the
existing pinned `playwright-core` install command can supply it if absent.
The private image preparation instructions remain in the
[package README](../experimental/kithmoot-node/README.md). This update neither
publishes Shelter nor changes the node's network routes or privileges.

## Screens and expected results

| Screen | Review steps | Expected result |
| --- | --- | --- |
| Overview | Sign in, inspect the four services and access summary. Switch views using only Tab and Enter. Pause/start. | Controls, room supervisor, Spry and Shelter have named evidence and explicit unknown states. Only reported versions and uptimes appear. Five access grants do not mean five people online. Pause warns that it ends calls, while preserving data. Background refresh retains keyboard focus. |
| Connections | Inspect private controls, public room service, both hostnames and certificate expiry. Examine all nine local checks, especially TLS 443. | Private management loss is distinct from room/call failure. Results and timestamps describe local observations. No outside-network call is marked passed automatically. Certificate trust remains enabled; no host key is mounted. |
| Usage | Read container memory/CPU, message storage, free disk and saved caps. Repeat with unknown counters and a stopped node. | CPU uses 100% per core and needs two samples. Unknown data remains unavailable; zero remains zero. Room storage has its separate configured cap. Bandwidth and allocation counts are explicitly unmeasured/unreported. No participant addresses or call content appear. |
| Settings | Compare the four saved limits with setup. Read the call-route, file and hosting explanations. | Actual saved values are visible after setup. This revision does not edit live limits or offer an unimplemented action. Pairing points to Overview; room closure and removal remain in KithMoot. |
| Diagnostics | Fail the TLS 443 check, refresh, then copy the report. Inspect it before sharing. | The failed check is named. Local success is not public media acceptance. Export contains the declared aggregate summary, no keys, pairing link, identity, room ID or token. Nothing is uploaded automatically. |
| Pairing | Pair from Overview, open/copy the private link, then choose Done. | Existing one-use link flow is retained. Returning restores focus to Pair. The code expires within six minutes and is not included in diagnostics. |
| Deletion | Open deletion from Settings. Keep the node once; prepare deletion, then cancel. | Keep restores focus to Delete. Preparation returns to Overview where Cancel deletion is immediately visible. Existing room/operation freeze and host teardown checks still govern destructive deletion. |
| Controls recovery | Drop one status fetch and retry. Expire the controls session. | A private-controls connection message appears and is cleared by a successful refresh. An expired session returns to sign-in and does not stop the node. |

## Captures and design decisions

- [Overview, 390px](evidence/kithmoot-node-dashboard-20261105/04-status-390.png)
- [Connections, 390px](evidence/kithmoot-node-dashboard-20261105/dashboard-connections-390.png)
- [Usage, 390px](evidence/kithmoot-node-dashboard-20261105/dashboard-usage-390.png)
- [Settings, 390px](evidence/kithmoot-node-dashboard-20261105/dashboard-settings-390.png)
- [Diagnostics, 390px](evidence/kithmoot-node-dashboard-20261105/dashboard-diagnostics-390.png)
- [Failed TLS 443 check](evidence/kithmoot-node-dashboard-20261105/dashboard-diagnostics-failed-443.png)
- [Unavailable counters](evidence/kithmoot-node-dashboard-20261105/dashboard-usage-unavailable.png)
- [Usage at enlarged text](evidence/kithmoot-node-dashboard-20261105/dashboard-usage-large-text.png)
- [Actual iframe, Overview](evidence/kithmoot-node-dashboard-20261105/dashboard-overview-embedded-390.png)
- [Actual iframe, Diagnostics without blur](evidence/kithmoot-node-dashboard-20261105/dashboard-diagnostics-embedded-390.png)
- [Expired controls session](evidence/kithmoot-node-dashboard-20261105/dashboard-session-expired.png)

The closest reference is this app's existing setup/status card and local
buttons. The small vanilla-JavaScript candidate reuses those controls and
semantic `--archy-*` tokens; it does not import dashboard CSS, a new UI kit,
fonts, wallpaper or outer navigation. The current upstream Archipelago design
skill and contract were read on 5 November. New navigation uses real buttons,
`aria-current`, 48px targets, visible focus and a wrapping 4px layout rhythm.

Embedded text needs a readable surface over host wallpaper. The existing
content surface uses a stronger dark scrim, with matching local header/footer
surfaces; the surrounding canvas remains transparent. Standalone and no-blur
fallbacks retain the existing dark baseline. This deliberate local treatment
needs maintainer review. The component test uses a real same-origin iframe
against a simulated dark host, rather than treating a CSS class on a standalone
page as a complete embedded test.

## Verification and remaining gates

The revision passes 23 controller, local-control and observation tests, the
production bundle build and five private packaging tests. The browser journey
passes 47 captures, 17 WCAG A/AA scans with zero reported violations and zero
page errors. Viewports include 320/390/768/1440px, landscape, enlarged text,
reduced motion, standalone, actual iframe and no-blur states. Source hashes in
the receipt bind those results to the build; these are component observations.

No new image has been deployed, no live node restarted and no infrastructure
changed. Real container observation on the demo, real host-gate integration
of this revision, Companion WebView, physical devices and outside-network
media remain separate checks. The private-host inspection confirmed the old
image remains running; its container-exec probe was unavailable, so no new
live statistics or runtime acceptance are claimed.

Live bandwidth, allocation counters, history, client call-quality diagnostics
and editing limits after setup remain future backend/UI work. This revision
shows those limits honestly and does not expose arbitrary configuration,
commands, host paths, logs or container administration to the browser.
