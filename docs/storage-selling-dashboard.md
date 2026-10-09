# Storage & selling in the dashboard

The patched Archipelago dashboard adds **Settings → Storage & selling** at
`/dashboard/settings/storage`. Requires matching backend and frontend
`v1.9.0-alpha-p2` assets and Wildbloom Node `0.3.5-2ea211e-2`, installed using
the packaged rootless Quadlet and `/var/lib/archipelago/wildbloom-node` volume.
This is a targeted test-node package, not a new upstream OTA or ISO.

## Operator flow

1. Open the page. It reads local node health and available space on the storage
   filesystem. An existing installation starts with its current quota, with
   a suggested reserve of half that quota (up to 100 GiB) and an offer of up to
   10 GiB that fits the remaining capacity. With no running node the draft
   suggestions are 200 GiB total and 100 GiB reserved, and applying is blocked.
2. Choose total quota, owner reserve, file size limit, customer capacity, price,
   term, recovery grace, delivery allowance, seller name and contact/refund terms.
   Every offered value is editable; zero reserve and zero grace are supported.
   Delivery remains operator-managed, not an enforced bandwidth meter.
   Add exact HTTPS origins under **Other customer app origins** to accept
   customers using a separately hosted Wildbloom web app. Your own packaged
   app stays allowed; wildcards, credentials and URL paths are refused.
3. For selling, open **Moneyer connection** and explicitly resolve its public IP
   addresses, or enter verified public IPs. This one action makes a DNS lookup;
   reading and saving settings never contacts an issuer. The issuer host,
   endpoints and signing key remain pinned to the reviewed Moneyer integration.
   Review its terms before accepting it and enabling new sales.
4. **Save draft** stores private settings without changing the running service.
5. **Review and apply** shows the saved offer and restart notice. Applying
   rechecks capacity and the running package, prepares an immutable private
   profile, publishes the desired configuration, and restarts Wildbloom Node
   through the existing orchestrator. It reports success only after the running
   configuration revision and healthy quota match. A failed or unverified
   restart is shown as pending; reload status and retry after resolving it.

The usable quota leaves at least 5 GiB or 5% of disk capacity for the OS and
other apps. This is a point-in-time capacity check, not a filesystem reservation;
other applications may subsequently use disk space. Unavailable health/disk
information blocks apply rather than being treated as zero usage.

## Existing customers and state

Turning off **Accept new storage sales** after selling has begun sets the new
sales ceiling to zero while leaving checkout, receiving state and paid
allowances intact. Previously issued quotes can still settle within their
10-minute lifetime. Existing quotes keep their original price and terms.
This pauses new quotes; it does not revoke purchases or refund customers.

After checkout is activated this screen refuses quota reductions, increases to
the owner reserve, or a public-hostname change. These require an operator-led
migration that accounts for outstanding customer promises and payment recovery.
Changing prices or durations creates a new offer revision. A manually provisioned
external checkout profile or inactive receiving ledger is detected and cannot be silently replaced by this UI.

Private draft/active settings live under the backend data directory at
`settings/wildbloom-storage/settings.json` (directory 0700, file 0600).
Immutable runtime profiles live at
`/var/lib/archipelago/wildbloom-node/operator/dashboard-profile-<revision>.json`.
All revisions use `/data/operator/checkout` for the receiving ledger. No operation
resets, removes, or changes the ledger location. Back up dashboard settings and
the complete Wildbloom storage/checkout directory together; do not restore an
old receiving ledger over newer payment state.

RPC methods are `wildbloom.storage.get`, `.save`, `.resolve-moneyer`, and `.apply`.
All require the dashboard admin session and CSRF protection; browser calls must
come from this node's dashboard origin, not a high-port app or another site. None are available
to unauthenticated users, viewers or app users. Revision checks prevent a stale
tab overwriting newer settings. Mutations are serialized, and an apply completes
even if the HTTP client disconnects. A pending desired configuration may also be
picked up by the normal app reconciliation/restart path.

## Acceptance evidence

Local checks on 9 October 2026:

- Thirteen native Rust tests: defaults and zero values, disk headroom and existing
  promises, receiver validation, private persistence, immutable profiles,
  pause semantics, stale revisions, admin/CSRF requirements, and actual
  orchestrator environment resolution (drafts inert, owner authorisation kept).
- Sixteen targeted Vue/router tests including save/apply separation, invalid
  capacity, failed status, pending restart and explicit DNS lookup.
- Production frontend build and desktop/390px browser acceptance of the real
  Vue component using synthetic RPC responses. Screenshots visually inspected;
  no horizontal overflow or browser exceptions. This is not live RPC proof.
- The real Rust profile generator loaded by the packaged Node container:
  bounded quotes, unpaid upload refusal, owner reserve, exact file retrieval,
  restart, and pause preserving old quotes while refusing new ones. No issuer
  notes or real payments were submitted.

CI repeats these checks alongside the existing backend suite and release build.
Real Moneyer settlement, renewal/refund and paired-backup restore acceptance
remain separate work before public sales. Live deployment evidence is recorded
in the release PR rather than inferred from local tests.
