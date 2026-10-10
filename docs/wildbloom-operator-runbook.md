# Run a Wildbloom storage offer from Archipelago

This runbook takes one independent operator from a clean Archipelago test node
to a paid Wildbloom upload. It also covers restart, retrieval, renewal, refund
and the evidence worth keeping. Follow it in order for the first run.

ForgeSworn supplies the software. The operator supplies the machine, storage,
network access, offer, customer relationship and payment/refund handling.
ForgeSworn does not run the node, list the offer, set its terms, collect payment
or provide the storage service.

This is a public-preview acceptance run. Keep another copy of every test file
and use a small payment. Do not offer storage to the public until the operator
is satisfied with their backups, monitoring, capacity, terms and local legal or
tax obligations.

## What you need

- An x86_64 machine or server running Debian 13, with enough unused disk for the
  quota you intend to offer. The current clean-node path is the
  [lite Archipelago test node](../node/README.md); it deliberately omits the
  Bitcoin stack and several full-image services.
- Root SSH access to the node from an administration computer.
- On the administration computer: Git, GitHub CLI (`gh`), `ssh`, `rsync`,
  Python 3 and PyYAML.
- Two different Nostr identities: one owned by the node operator and one used
  by the buyer. Use separate browser profiles or devices for the clearest test.
- A small Lightning balance and an LNURLcash-aware wallet. The reference mint
  links to [LNURLwallet](https://wallet.lnurlcash.com/) as one compatible option.
- A Lightning Address for the buyer's refund destination.
- A node address the buyer can reach over trusted HTTPS. For a private
  evaluation, a LAN or VPN address plus the node CA is sufficient. For an
  internet-facing offer, use a DNS hostname, a publicly trusted certificate and
  expose the Blossom app port `3742`; the dashboard itself need not be public.

Use placeholders such as `NODE_IP` and `storage.example` below. Do not copy them
literally.

## 1. Install the clean evaluation node

If you already have the matching patched Archipelago backend and frontend,
continue at step 2. New operators can assemble the pinned lite-node bundle from
this repository:

```sh
git clone https://github.com/forgesworn/archipelago-apps.git
cd archipelago-apps
git switch main

BUNDLE="$(mktemp -d)"
. ./PINS
cp PINS node/install-lite.sh scripts/recover-wildbloom-payment.py "$BUNDLE/"
gh release download "backend-${ARCHY_RELEASE}-p${BACKEND_PATCH_LEVEL}" \
  --pattern archipelago --pattern archipelago.sha256 -D "$BUNDLE"
gh release download "frontend-${ARCHY_RELEASE}-p${FRONTEND_PATCH_LEVEL}" \
  --pattern frontend.tar.gz --pattern frontend.sha256 -D "$BUNDLE"
scripts/fetch-archy.sh "$BUNDLE/archy"
sed -n "/<<'SECRETSSCRIPT'/,/^SECRETSSCRIPT\$/p" \
  "$BUNDLE/archy/image-recipe/_archived/build-auto-installer-iso.sh" \
  | sed '1d;$d' > "$BUNDLE/first-boot-secrets.sh"
rsync -a --exclude .git "$BUNDLE/" root@NODE_IP:/root/archipelago-bundle/
ssh root@NODE_IP \
  'bash /root/archipelago-bundle/install-lite.sh /root/archipelago-bundle'
```

The installer replaces the SSH host keys. Remove the old local record, verify
the new fingerprint through the server console or provider, then reconnect:

```sh
ssh-keygen -R NODE_IP
ssh -o StrictHostKeyChecking=accept-new root@NODE_IP \
  'systemctl is-active archipelago nginx avahi-daemon'
```

All three services must report `active`. Follow the browser and node-CA steps in
the [lite-node guide](../node/README.md#reaching-the-node), then use the dashboard
to set an admin password, save the recovery seed offline and create the
operator's first identity. Do not use the appliance's internal node identity as
the operator identity.

Record the exact software inputs without recording keys or passwords:

```sh
git rev-parse HEAD
grep -E '^(ARCHY_RELEASE|ARCHY_REF|WILDBLOOM_REF|WILDBLOOM_NODE_REF|BACKEND_PATCH_LEVEL|FRONTEND_PATCH_LEVEL)=' PINS
```

## 2. Install Wildbloom Node and Wildbloom

From the repository on the administration computer, provide the node explicitly
and read the dashboard password without echoing it or putting it in shell
history:

```sh
export NODE=root@NODE_IP
printf 'Dashboard password: '
IFS= read -rs ARCHY_PASSWORD
printf '\n'
export ARCHY_PASSWORD
scripts/stage-to-node.sh wildbloom-node
scripts/stage-to-node.sh wildbloom
unset ARCHY_PASSWORD
```

Both commands must finish with `state=running`. In the dashboard, open
Wildbloom. Connect the operator identity, choose a small disposable file, and
confirm that **Use my Archipelago node** selects this node. Upload the file,
download it again and compare it with the original before enabling sales.

The separately hosted Wildbloom app cannot discover ownership automatically.
Its buyer must enter or select the operator's node address explicitly.

## 3. Make the node reachable by the buyer

The buyer must be able to load `https://YOUR_NODE:3742/healthz` with a trusted
certificate. A dashboard that works only on the operator's LAN does not prove
this.

For a private LAN or VPN test, import the node CA into the buyer's dedicated
browser profile after comparing its SHA-256 fingerprint over SSH. The
[lite-node guide](../node/README.md#trusting-the-node-ca) gives the exact steps.

For a public hostname:

1. Point its DNS record at the node.
2. Obtain a publicly trusted certificate for that exact hostname using the
   operator's chosen ACME method.
3. Make the certificate and key readable by the `archipelago` service without
   making the private key public.
4. Set the following in `/etc/archipelago/config.toml`, using the operator's
   actual certificate paths:

   ```toml
   public_host = "storage.example"
   public_cert = "/etc/archipelago/public-tls/fullchain.pem"
   public_key = "/etc/archipelago/public-tls/privkey.pem"
   ```

5. Restart Archipelago, restart both Wildbloom packages so their derived public
   origin is refreshed, and allow inbound TCP `3742` in the host and upstream
   firewalls. Keep the dashboard restricted to the operator's normal access
   path.

Check from the buyer's network, not from the node itself:

```sh
curl --fail --show-error https://storage.example:3742/healthz
openssl s_client -connect storage.example:3742 -servername storage.example </dev/null
```

The health request must succeed without `--insecure`, and the certificate must
cover the hostname. Do not continue while the buyer sees a certificate warning.

## 4. Configure a small first offer

Open **Settings → Storage & selling** in the operator's authenticated
Archipelago dashboard. The page checks the running package and available disk.
Use values that fit the actual machine. For a first reference-mint acceptance
run, these small values limit the commitment while exercising the real path:

| Setting | Suggested acceptance value |
| --- | ---: |
| Total storage quota | 2 GiB |
| Reserved for you | 1 GiB |
| Maximum file size | 0.0625 GiB |
| Storage per customer | 0.0625 GiB |
| Price per term | 10 sats |
| Term | 1 day |
| Recovery grace | 1 day |
| Delivery allowance per term | 0.25 GiB |
| Seller name | A name chosen by the operator |
| Sale and refund terms | The operator's actual fulfilment and full-refund conditions; see the example below |

The values are suggestions for this acceptance run, not a market price or a
capacity recommendation. Customer capacity is a promise for each active
allowance. The total customer ceiling is the quota minus the owner reserve.
Delivery is operator-managed and is not automatically metered.

Example acceptance terms, to edit if they do not describe what the operator
will actually do:

```text
Test offer. The storage allowance activates after payment and lasts for 1 day,
followed by 1 day of recovery grace. The full price is refunded if payment
settles but the allowance cannot be activated. Downloads are operator-managed.
```

If the buyer uses `https://wildbloom.forgesworn.dev`, add that exact origin
under **Other customer app origins**. Do not add a wildcard or a URL path.

Select **LNURLcash reference mint**. Before accepting it, compare the live
discovery key with the key pinned by this software:

```sh
curl --fail --silent --show-error \
  https://mint.lnurlcash.com/.well-known/lnurlw/mint | jq -r .mintPubkey
```

Expected pinned key:

```text
027f06257d0e9af2dbef2c1c64d03962a9240a65a987eb90b36000c64de34baa6d
```

Stop if it differs. Otherwise:

1. Open **Issuer connection** and press **Resolve issuer addresses**.
2. Review the issuer, its key, endpoints and risks, then tick the issuer-review
   checkbox.
3. Enter the operator's sale and refund terms. A public email, Nostr key or URL
   is optional.
4. Leave **Accept new storage sales** off and press **Save draft**.
5. Review the saved values once more.
6. Turn **Accept new storage sales** on, save the draft, press
   **Review and apply**, confirm the brief restart, then press
   **Apply to node**.

Continue only when the page says that the node is healthy and running the
applied revision. Open **View sales & customers**. A new node should show no
selling history yet, rather than an unavailable or corrupt ledger.

## 5. Buy the allowance as a separate customer

Use the buyer identity in a separate browser profile or device:

1. Open [Wildbloom](https://wildbloom.forgesworn.dev/#client), enter
   `https://YOUR_NODE:3742` as the Blossom server and connect the buyer's NIP-07
   signer. Never give the operator the buyer's private key.
2. Expand **Buy storage directly from this node** and press
   **Load this node's offers**.
3. Check the seller name, node origin, capacity, exact price, term, grace,
   delivery policy and refund terms.
4. Choose **LNURLcash**, select `lnurlcash-reference`, and enter the buyer's
   Lightning Address under **Lightning refund address**.
5. Press **Request a private quote**. Immediately download
   `wildbloom-order.json` and keep it private.
6. The quote is valid for ten minutes. Open
   [the reference mint](https://mint.lnurlcash.com/), use an LNURLcash-aware
   wallet to pay `mint@mint.lnurlcash.com` for the quote's exact sat amount,
   and save or copy the resulting bearer note. Anyone who sees the note can
   spend it.
7. Return to Wildbloom, recheck the quote, tick the payment-consent box, paste
   the exact-value note into **LNURLcash note**, and press
   **Create invoice / submit note** once.

If the browser times out or the outcome is unclear, press **Check this payment
once** or recover the saved order with the same buyer signer. Do not mint or
submit a second note to resolve uncertainty.

Success is `active` with an allowance identifier and write-expiry time. Save the
new `wildbloom-storage-receipt.json` privately. The bearer note must not appear
in either saved receipt.

## 6. Upload, retrieve and restart

Payment grants an allowance; it does not upload anything. Still as the buyer:

1. Choose a small test file whose original remains elsewhere.
2. Keep browser encryption enabled.
3. Inspect the file, approve the stated destination and upload it.
4. Save the signed file event or pool receipt and the separate recovery key.
   Keep the key separate from the receipt.
5. Retrieve the file from the saved receipt, decrypt it and compare it with the
   original.

The operator should now see one paid order and one retained customer allowance
under **View sales & customers**, with no item under **Needs attention**.

Restart Wildbloom Node from the dashboard. After it is healthy again, have the
buyer recover the order using `wildbloom-order.json`, retrieve the same file and
compare it again. This proves restart recovery for this node; it does not prove
continuous availability or an independent replica.

## 7. Renew the allowance

Before the first term expires:

1. Copy `allowance_id` from the buyer's saved storage receipt into
   **Renew allowance (optional)**.
2. Request a new quote, save its new order reference and mint one new
   exact-value reference-mint note.
3. Submit it once and wait for `active`.
4. Save the renewed storage receipt and confirm that the allowance identifier
   and capacity are unchanged while the write and recovery dates move forward.

The operator's sales page should show two paid orders but only one current
customer allocation for the renewed allowance.

## 8. Exercise the ordinary refund record

Do not deliberately corrupt live state to manufacture an automatic-refund
failure. For a routine first-run refund check, the operator can refund the
active purchase directly from their own Lightning wallet:

1. Reconcile the order ID, buyer public key, amount and original terms in the
   private sales page.
2. Send the full purchase price to the buyer's Lightning Address.
3. Ask the buyer to confirm receipt independently.
4. Record the completed refund from the matching order using
   **Record completed refund**. Enter the wallet's 64-character payment hash and
   confirm the exact original price. Never enter an invoice, preimage, bearer
   note or wallet credential.

This record is the operator's attestation; it is not independent settlement
proof and does not revoke an already active allowance. If a real order instead
shows `refund_required`, follow the exact bound command shown by the dashboard
and the [payment recovery guide](storage-payment-recovery.md). Never treat
`refund_required` as evidence that money has already been returned.

## 9. Make a paired private backup

The storage volume and checkout state must be backed up together while the
writer is stopped. The following example creates a root-only archive on the
node. Move it to encrypted offline storage afterwards:

```sh
ssh root@NODE_IP
install -d -m 0700 /root/wildbloom-backups
BACKUP="/root/wildbloom-backups/wildbloom-$(date -u +%Y%m%dT%H%M%SZ).tar"
runuser -u archipelago -- env \
  XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user mask --runtime --now wildbloom-node.service
tar --acls --xattrs --numeric-owner -C / -cpf \
  "$BACKUP" \
  var/lib/archipelago/wildbloom-node \
  var/lib/archipelago/data/settings/wildbloom-storage
sha256sum "$BACKUP" > "$BACKUP.sha256"
runuser -u archipelago -- env \
  XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user unmask --runtime wildbloom-node.service
runuser -u archipelago -- env \
  XDG_RUNTIME_DIR=/run/user/1000 \
  DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
  systemctl --user start wildbloom-node.service
```

Confirm the service is healthy before leaving the node. The archive contains
private receiving state and may contain spendable LNURLcash notes. Do not upload
it to an issue, repository or public cloud bucket. Never restore an older
checkout ledger over newer live state; follow an operator-led recovery plan.
If any backup command fails after the runtime mask is applied, still run the
final unmask and start commands, then investigate the failed backup.

## 10. Record the result

Keep a short acceptance record with:

- date, operator-controlled node type and Archipelago Apps commit;
- backend/frontend release tags and Wildbloom image names;
- whether buyer access used LAN, VPN or public trusted HTTPS;
- chosen quota, reserve, allowance, price, term and grace;
- reference-mint discovery key match;
- purchase state, upload size and hashes of the original and recovered file;
- restart result, renewal dates and refund amount/recipient confirmation;
- backup archive hash and restore-test status;
- every unexpected error and whether its outcome was reconciled.

Do **not** record or publish private keys, seed words, bearer notes, invoices,
preimages, full order references, customer public keys, refund destinations,
payment hashes, checkout databases, recovery journals or backup archives.

The run passes when the independent operator can install the software, choose
their own values, activate one reference-mint purchase, preserve and retrieve
the encrypted upload through restart, renew the same allowance, complete the
chosen refund check and retain a matched private backup. A pass is deployment
evidence for that operator and environment, not a promise that every node or
network will behave identically.

## Stop conditions

Pause new sales and investigate if any of these occurs:

- the reference mint's discovery key differs from the pinned key;
- the buyer sees a TLS warning or cannot reach `/healthz`;
- the applied settings revision is pending or unhealthy;
- a payment outcome is uncertain;
- **Needs attention** is non-zero and unexplained;
- the storage volume and checkout state cannot be backed up together;
- the buyer cannot retrieve and decrypt the exact uploaded bytes after restart.

Turning off **Accept new storage sales** blocks new quotes after already-issued
quotes expire. It does not cancel existing allowances, erase data, resolve
pending payments or refund customers.
