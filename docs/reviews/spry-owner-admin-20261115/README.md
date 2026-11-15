# Spry live statistics and owner administration review

**Maintainer must review and approve UI work on the standalone and embedded
Spry screen before core Archipelago merging or approval. ZAT pending.**

The owner has scoped ZAT to acceptance into core Archipelago. This pack does
not claim maintainer approval or physical-client acceptance. No maintainer has
been contacted.

## Candidate

- [Archipelago app PR66](https://github.com/forgesworn/archipelago-apps/pull/66)
  merged as `441ab404855f8012d072235a1f1e302190ce90c3`.
- [Spry library PR45](https://github.com/forgesworn/spry-turn/pull/45) merged
  as `726a919c54d19395f794af0761464b1396dbece4`; the app pins immutable
  source revision `77fbf90e5f8ad8abd339d3a67701a8ad6f3a22cf`.
- Published image: `ghcr.io/forgesworn/spry:0.1.0-77fbf90-6`, manifest digest
  `sha256:95331fec7f3abbe2f4db9e23c2bb2cfa3fdd6f18d57bef0207f41c92d903e977`,
  with native amd64 and arm64 manifests.
- [Frontend p13](https://github.com/forgesworn/archipelago-apps/releases/tag/frontend-v2.1.0-beta.2-p13)
  has archive SHA-256 `b0ec7c46e99f5aa289a4af1caa2684bd7981e6689abd17318e35ac06faf389e4`
  and input receipt `97f9ab6cb06d675c215abc54f69802c5cb74a776c5f5a585d630344fce33419e`.
  Its packaged Spry manifest names the image above. The app lockfile resolves
  all Spry crates to the exact library revision; `cargo build --locked -p spry-node` passes.

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

## Live delivery, 15 November

Operation `05ec7f68-2683-4e13-a213-d16000eb95f7` is active on
`demo.forgesworn.dev`. Spry runs image `ee006041b72d54275c59c325792c8c078752458319a2440df4804094ea7d2bcd`
in container `d28026612c1d`; its registry digest matches the published amd64
manifest. The backend remains unchanged and the frontend tree is
`d8167e7ee0449cb8bf5f110345c4d1b8353ad8e596e6ec8023351edbdecfb2e9`.
Only Spry was recreated. The other five container IDs/images and Spry pairing
data are preserved; the pairing file is byte-identical to its recovery copy.
Manager health, the migration guard, dashboard HTTP 200 and live UI assets pass.
Anonymous stats/grant/pairing requests return 401. A separate real-HTTP fixture
with generated keys passed signed-owner responses and non-owner 403s. No live
owner-signed metrics or grant action was attempted; physical acceptance remains
pending. Control-link readiness was false before and after this update and is
not presented as a new regression.

Recovery verified 116,521 entries, zero unexpected paths, GNU tar
xattr/ACL/content comparison and 12 SQLite databases. An earlier Spry manifest
had left the migration tree hash stale; the snapshot restart exposed it. The
manager was restored and the new manifest/hash update was applied atomically.
See the [live verification receipt](live-verification.json).

## Limits

The public standalone relay remains a separate process with no metrics
connection, so the UI marks its live counters unavailable rather than
estimating them. Revoking a grant stops credential renewal but does not force
an existing TURN allocation offline immediately. No room-name, participant,
per-room traffic or media inspection was added.

The image, frontend and demo deployment are verified as described above.
Physical-device evidence, live owner-signed actions and real-call acceptance
remain separate from the passing local, hosted and deployment checks and ZAT.
