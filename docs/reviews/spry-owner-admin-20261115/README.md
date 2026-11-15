# Spry live statistics and owner administration review

**Maintainer must review and approve UI work on the standalone and embedded
Spry screen before core Archipelago merging or approval. ZAT pending.**

The owner has scoped ZAT to acceptance into core Archipelago. This pack does
not claim maintainer approval, publication, deployment or physical-client
acceptance. No maintainer has been contacted.

## Candidate

- Archipelago app revision: `1ad8dec1fdba83872361e7e57d971bb5c5289d3d`, branch
  `feat/spry-owner-admin-20261115`.
- Spry library revision: `77fbf90e5f8ad8abd339d3a67701a8ad6f3a22cf`, branch
  `feat/spry-owner-admin-20261115`.
- Intended image tag: `ghcr.io/forgesworn/spry:0.1.0-77fbf90-6`.
- The library revision is public on [spry-turn PR45](https://github.com/forgesworn/spry-turn/pull/45);
  the app candidate is local. No image or frontend release has been published
  and demo remains unchanged. The app lockfile resolves all Spry crates to the
  exact library revision above; `cargo build --locked -p spry-node` passes.

## Screen changes

**Relay at a glance** adds active allocations/capacity, connected mesh peers,
aggregate throughput, relayed bytes and dropped packets. Private-mesh counters
update after signed-owner approval and every 15 seconds while visible. The
screen explains that throughput combines both directions and totals reset when
the embedded relay restarts. Public mode says live counters are unavailable.

**Manage call access** lists opaque grant identifiers, current access expiry
and recent credential devices. It does not expose room scopes, participant
keys or bearer grants. Revocation requires confirmation, reports cancellation,
persists across restart and warns that existing TURN allocations can take up
to five minutes to expire. Recent credential devices are not call attendance.

Captures use generated fixture data:

- [Desktop, 1440px](spry-admin-desktop.png)
- [Mobile, 390px](spry-admin-mobile.png)

## Review setup and steps

The browser fixture serves the real Spry HTML, CSS and JavaScript with a
generated signer and deterministic API responses. It needs an existing
KithMoot checkout containing `@playwright/test`; it adds no package dependency.

```sh
node tests/spry-admin-ui.mjs \
  --kithmoot /path/to/kithmoot \
  --output .cache/spry-admin-review
```

For an installed-candidate review after publication/deployment:

1. Open **My Apps → Spry** and approve the live-activity request.
2. Confirm readiness, control-link state, active allocations, mesh peers,
   relayed total and dropped packets appear. Leave the screen visible for two
   updates; throughput should change from **Measuring** to a rate.
3. Choose **Refresh live activity** and confirm the counters refresh without
   changing pairing state.
4. Open **Manage paired devices → Show paired devices**. Confirm the count and
   existing pairing rows still appear.
5. Open **Manage call access → Show call access**. Confirm only opaque access
   IDs, expiry and recent credential counts appear—no room or participant
   identities.
6. Choose **Revoke access**, then cancel. Confirm **Revocation cancelled** and
   that the grant remains. Repeat and confirm only a disposable test grant;
   expect the five-minute expiry warning and its removal from the list.
7. Check 320, 390, 768 and 1440px widths, keyboard focus and confirmation
   dialogs. There should be no horizontal overflow.

## Verification completed

- Spry Rust formatting, Clippy with warnings denied, all-feature tests,
  minimal-feature tests, release build and 33 UDP/TCP/TLS interoperability
  checks passed.
- Owner-grant API tests cover non-owner denial, secret-free responses,
  revocation and persistence across restart. Mesh and public-mode stats tests
  pass. Secret scans found no leaks.
- All 111 Archipelago app Python tests passed with the project-pinned upstream
  Archipelago source.
- The browser check passed live counters, changing throughput, pairing/grant
  counts, revocation cancellation and confirmation, public-mode unavailable
  metrics, and 320/390/768/1440px overflow checks with no browser errors. See
  the [browser receipt](browser-receipt.json).

## Limits

The public standalone relay remains a separate process with no metrics
connection, so the UI marks its live counters unavailable rather than
estimating them. Revoking a grant stops credential renewal but does not force
an existing TURN allocation offline immediately. No room-name, participant,
per-room traffic or media inspection was added.

There is no published multi-architecture image, deployed demo result,
physical-device evidence or real-call acceptance for this revision yet. Those
remain separate from the passing local checks and ZAT.
