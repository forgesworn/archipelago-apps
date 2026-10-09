# Private sales and customer allowances

Open **Settings → Storage & selling → View sales & customers** at
`/dashboard/settings/storage/sales`. The view is included in the patched
`v1.9.0-alpha-p4` backend and frontend. It reads the existing packaged Node
`0.3.5-2ea211e-2`; no Node image change or sales enablement is needed.

The summary separates historical activated orders from current customer
allowances. Renewals count as orders but share an allowance, so allocated
capacity is counted once. Allocation includes recovery grace and is promised
space, not bytes uploaded. The page shows the current write expiry and recovery
deadline from the storage ledger, including extensions from later renewals.
Payment state and storage-term state are separate: an expired term does not
mean its payment failed or was refunded.

Orders show the quoted price, capacity, payment rail, creation/quote dates and
current allowance. Order IDs, customer public keys, offer IDs and renewal
references are available in expandable details. They stay in the authenticated
dashboard; no customer data is published to Nostr or sent to the issuer.

**Needs attention** includes incomplete reservations, uncertain invoice/note
outcomes, payments awaiting activation and refund-required records. It is a
review queue, not a claim that those payments failed. Refreshing this page never
retries or checks a payment with the issuer. The original read-only release left refunds and payment recovery
separate operator operations; this release adds no spending controls. An
out-of-band manual refund is not automatically recorded in checkout history.

## Read boundary

`wildbloom.storage.orders` accepts only an optional `after` order-ID cursor and
an allowlisted `state` filter. It returns up to 50 records in order-ID order.
Summary figures cover the whole ledger; filtering/pagination affects the order
list only. Reads use short SQLite snapshots. The checkout and storage databases
are separate, so an activation in progress can appear on a subsequent refresh.
There is no automatic polling or browser persistence of sales records.

The endpoint requires the admin session, CSRF protection and the dashboard
origin, including when installed apps share the host's cookies. It is excluded
from the RPC cache and is unavailable to viewers, app users and anonymous
requests. Paths come from the validated packaged data volume, never RPC input.

The backend uses SQLite read-only connections with query-only mode, bounded
pages, validated fields and a short lock timeout. It does not open the Node's
writer/migration code or take its exclusive ledger lock. Active WAL records
remain visible while the daemon runs. Only order metadata and current allowance
columns are read; invoices, preimages, bearer notes, rotation records and
receiving secrets are never projected into the response. Private file modes,
non-symlink paths and the checkout schema version are checked.

Never-enabled selling has its own empty state. An expected ledger that is
missing, corrupt, unreadable or incompatible produces an unavailable state;
it is never displayed as zero customers. Failed refreshes clear stale figures.

## Validation

- Six added Rust tests cover live WAL reads without changing the database or
  WAL, rejected writes, secret exclusion, renewal accounting and deadlines,
  cursor/filter bounds, missing/corrupt/future state, file privacy and mismatched
  allowances. The existing authentication test also covers the new RPC.
- Six added Vue tests cover local reads, empty/error states, pagination and
  filters, safe rendering, payment/access separation and cancellation on exit.
- Desktop and 390px browser checks exercise the real component with synthetic
  RPC data, including expanded references, renewal dates, pending payments and
  failed refreshes. Screenshots were visually inspected with no horizontal
  overflow.
- Packaged customer-flow CI compiles this same reader and inspects the real
  running Node ledger after a synthetic purchase and renewal. It requires two
  activated orders, one current allowance, matching renewed dates, no secret
  fields and no additional receiving mutation. This is synthetic acceptance,
  not a real-money refund or issuer-recovery test.

The subsequent [refund and recovery workflow](storage-payment-recovery.md) adds private operator refund records and an explicit local recovery tool. The original checkout state remains visible.
