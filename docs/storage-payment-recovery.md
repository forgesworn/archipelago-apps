# Private refund records and payment recovery

The Sales & customers page can record a **full refund already completed directly
by the operator**. It cannot send a refund. Open **Record completed refund** only
after reconciling the purchase, sending the refund from your own wallet, and
confirming receipt. Enter that refund's 64-character Lightning payment hash and
confirm the exact original storage price. Fees are separate. Do not paste a
bearer note, invoice, preimage, wallet credential or customer address.

Only `active` and `refund_required` orders can receive a record. Uncertain
payments must be reconciled first. The same order/hash/amount is idempotent;
a different record for the order or a reused refund hash is refused. This is an
operator attestation, not independent settlement verification. Partial refunds,
corrections and automatic spending are not supported by this initial journal.
An operator still verifies the recipient and payment outside this software.

Records are private, mode 0600, atomically persisted and fsynced at
`wildbloom-node/operator/refunds.json`. Admin authentication, CSRF and dashboard
origin checks apply. The browser does not persist payment references. Journal
errors fail closed instead of hiding existing records. Back up this file with
the checkout and storage volume. Original checkout states and storage rights
are unchanged, so the Needs attention count still reflects checkout states,
including `refund_required` orders with an operator refund record. A recorded
refund is shown separately on its order.

## Recover an interrupted payment

The packaged node's existing `checkout-operator` is wrapped by
`scripts/recover-wildbloom-payment.py`. Install the reviewed script as root:

```sh
install -o root -g root -m 0755 scripts/recover-wildbloom-payment.py /usr/local/bin/recover-wildbloom-payment
```

The lite installer includes it in its bundle. The Sales page displays the exact
command for each eligible order. Run as the **archipelago service user**, from
an accessible working directory and with that user's systemd bus:

```sh
cd /
runuser -u archipelago -- env XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  /usr/local/bin/recover-wildbloom-payment reconcile ORDER_ID --confirm-restart
```

This is a deliberate storage outage. Keep dashboard settings unchanged during
recovery. The tool verifies the active dashboard revision, image and volume;
temporarily masks and stops the node to prevent an automatic restart; makes and byte-verifies a full offline backup; invokes exactly
one existing operator operation using the running image ID and original pinned
receiver configuration; then restarts the node. It never creates an invoice,
accepts a new note, resets state, spends a refund, resolves issuer DNS or restores
a backup. A failure can leave the payment pending. Refresh to read durable state.

`reconcile` accepts only `awaiting_payment`, `lnurl_pending` and `settled` orders.
LNURLcash recovery can replay the byte-identical journalled rotation after
checking its saved replacement. Do not redeem an uncertain note out of band.
Reservation retries are deliberately refused: the pinned standalone operator
has no packaged sales-capacity ceiling, so it must not reserve additional space.

For `invoice_pending` Lightning orders, use `recover-invoice` instead. It finds
and attaches the original invoice, then requires a separate `reconcile` command.
The current dashboard configures LNURLcash only; it does not provision Phoenixd.
The wrapper preserves the profile and refuses external/manual configurations.

Private operation journals are under `operator/recovery/`. A timeout or ordinary
termination records `needs_review`; a failed restart records `restart_required`.
No raw issuer response or bearer data is printed. Full backups and hash manifests
are kept under `/var/lib/archipelago/wildbloom-recovery-backups/`; they contain
private receiving assets and are never automatically restored or deleted.

After power loss or SIGKILL, inspect the journal and service before retrying.
Remove this tool's runtime mask and start the node if needed:
`systemctl --user unmask --runtime wildbloom-node.service`, then
`systemctl --user start wildbloom-node.service`. A `running` journal is an unknown outcome,
not permission for a new payment. Reconciliation of the same existing order is
the recovery path. Never restore a pre-recovery receiving backup over live state:
it may contain assets already spent or rotated.

## Evidence boundaries

Python tests exercise the wrapper with synthetic service commands: backup and
restart failures, uncertain recovery, terminal-state refusal and unsafe paths.
Rust/Vue tests cover refund record privacy, idempotency, amount/state checks and
explicit receipt confirmation. Packaged-service acceptance records a synthetic
refund against real packaged order databases and verifies unchanged allowances
and no extra issuer operation. None of these sends or proves a new real refund.
