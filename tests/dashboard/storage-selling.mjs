// Browser acceptance for the real Vue settings component with synthetic RPC.
// Run against a Vite storage-preview.html fixture, never a live payment receiver.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';
const archy = resolve(process.argv[2] || '.cache/archy-selling');
const require = createRequire(resolve(archy, 'neode-ui/package.json'));
const { chromium } = require('@playwright/test');
const GiB = 2 ** 30;
const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined });
const page = await browser.newPage({ viewport: { width: 1280, height: 950 } });
const failures = [];
page.on('pageerror', e => failures.push(e.message));
const settings = { quota_bytes: 10*GiB, owner_reserved_bytes: 5*GiB, max_blob_bytes: GiB,
  offer_capacity_bytes: 5*GiB, price_sats: 500, duration_seconds: 30*86400, grace_seconds: 7*86400,
  delivery_bytes: 100*GiB, seller_name: 'My Archipelago node', refund_policy: '', moneyer_ips: [],
  additional_browser_origins: [], moneyer_terms_accepted: false, sales_enabled: false };
let state = { revision: 0, settings, active: null, applied: false, has_draft: false,
  runtime: { quota_bytes: 10*GiB, used_bytes: 0, committed_bytes: 0, settings_revision: null, checkout_started: false },
  disk: { free_bytes: 29*GiB, total_bytes: 38*GiB, headroom_bytes: 5*GiB },
  origin: 'https://demo.forgesworn.dev:3742', can_apply: true, external_configuration: false };
const calls = [];
let salesUnavailable = false;
const now = Math.floor(Date.now()/1000);
const allowance = { capacity_bytes: 5*GiB, starts_at: now-86400, writes_until: now+86400, retains_until: now+8*86400, status: 'active' };
const sales = { status: 'ready', checked_at: now, summary: { orders: 3, paid_orders: 2, needs_attention: 1, retained_customers: 1, allocated_bytes: 5*GiB }, next_after: null,
  orders: ['purchase','renewal','pending'].map((id,i) => ({ order_id: id+'-'.repeat(80), state: i===2?'lnurl_pending':'active', customer_pubkey: 'ab'.repeat(32), rail: 'lnurlcash', offer_id: 'storage-month', price_msat: 500000, ordered_capacity_bytes: 5*GiB, created_at: now-100, quote_expires_at: now+500, renews: i===1?'purchase':null, allowance: i===2?null:allowance })) };

await page.route('**/rpc/v1', async route => {
  const request = route.request().postDataJSON(); calls.push(request.method);
  let result;
  if (request.method === 'wildbloom.storage.get') result = state;
  else if (request.method === 'wildbloom.storage.orders') {
    if (salesUnavailable) return route.fulfill({ json: { error: { code: -32000, message: 'Unavailable' } } });
    result = request.params.state === 'attention' ? { ...sales, orders: [sales.orders[2]] } : sales;
  }
  else if (request.method === 'wildbloom.storage.record-refund') {
    assert.equal(request.params.confirm_received, true);
    const order = sales.orders.find(o => o.order_id === request.params.order_id);
    assert.equal(order.price_msat, request.params.amount_msat);
    assert.equal(request.params.payment_hash, 'cd'.repeat(32));
    order.refund = { amount_msat: order.price_msat, payment_hash: request.params.payment_hash, recorded_at: now };
    result = { status: 'recorded' };
  }
  else if (request.method === 'wildbloom.storage.save') {
    assert.equal(request.params.revision, state.revision);
    state = { ...state, revision: state.revision+1, settings: request.params.settings, has_draft: true };
    result = { revision: state.revision };
  } else if (request.method === 'wildbloom.storage.apply') {
    assert.equal(request.params.confirm_restart, true);
    assert.equal(request.params.revision, state.revision);
    state = { ...state, revision: state.revision+1, applied: true,
      active: { revision: state.revision+1, checkout_started: false, settings: state.settings } };
    result = { status: 'applied', revision: state.revision };
  } else throw new Error('Unexpected RPC: ' + request.method);
  await route.fulfill({ json: { result }, headers: { 'cache-control': 'no-store' } });
});
try {
  await page.goto(process.argv[3] || 'http://127.0.0.1:15173/storage-preview.html');
  await page.getByLabel('Total storage quota (GiB)').waitFor();
  assert.deepEqual(calls, ['wildbloom.storage.get']);
  assert.equal(await page.getByLabel('Accept new storage sales', { exact: true }).isChecked(), false);
  await page.screenshot({ path: '.cache/storage-selling-desktop.png', fullPage: true });
  await page.getByLabel('Price per term (sats)').fill('750');
  await page.getByLabel('Reserved for you (GiB)').fill('0');
  await page.getByLabel('Recovery grace (days)').fill('0');
  await page.getByRole('button', { name: 'Save draft', exact: true }).click();
  await page.getByText('Draft saved. Your running node has not changed.').waitFor();
  assert.equal(state.settings.owner_reserved_bytes, 0);
  assert.equal(state.settings.grace_seconds, 0);
  assert.equal(calls.includes('wildbloom.storage.apply'), false);
  await page.getByRole('button', { name: 'Review and apply', exact: true }).click();
  await page.getByLabel('I’m ready to apply these settings and briefly restart Wildbloom Node.').check();
  await page.getByRole('button', { name: 'Apply to node', exact: true }).click();
  await page.getByText('Settings applied. The node is healthy and running this configuration.').waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '.cache/storage-selling-mobile.png', fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'No mobile horizontal overflow');
  await page.setViewportSize({ width: 1280, height: 950 });
  await page.goto('http://127.0.0.1:15173/storage-preview.html?sales');
  await page.getByRole('heading', { name: 'Sales & customers' }).waitFor();
  await page.locator('section strong').filter({ hasText: /^Paid · allowance issued$/ }).first().waitFor();
  assert.equal(await page.getByText('Current write expiry', { exact: true }).count(), 2);
  await page.screenshot({ path: '.cache/storage-sales-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('details summary').first().click();
  await page.screenshot({ path: '.cache/storage-sales-mobile.png', fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Sales references fit mobile');
  await page.getByRole('button', { name: 'Record completed refund', exact: true }).first().click();
  await page.getByLabel('Refund payment hash', { exact: true }).fill('cd'.repeat(32));
  assert.equal(await page.getByRole('button', { name: 'Save refund record', exact: true }).isDisabled(), true);
  await page.getByLabel('I have confirmed that the customer received', { exact: false }).check();
  await page.screenshot({ path: '.cache/storage-refund-mobile.png', fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'Refund form fits mobile');
  await page.getByRole('button', { name: 'Save refund record', exact: true }).click();
  await page.getByRole('heading', { name: 'Full refund recorded by operator', exact: true }).waitFor();
  assert.equal(await page.getByText('Writes allowed', { exact: false }).count(), 2, 'Refund record preserves allowances');
  await page.getByLabel('Payment status', { exact: true }).selectOption('attention');
  await page.getByText('A pending payment may already have been received.', { exact: false }).waitFor();
  assert.equal(await page.getByText('Payment outcome pending', { exact: true }).count(), 1);
  assert.equal(await page.locator('section strong').filter({ hasText: /^Paid · allowance issued$/ }).count(), 0);
  await page.getByText('Recover this payment', { exact: true }).click();
  await page.locator('pre').filter({ hasText: 'recover-wildbloom-payment reconcile pending-' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Record completed refund', exact: true }).count(), 0);
  salesUnavailable = true;
  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await page.getByRole('alert').filter({ hasText: 'Sales records are unavailable' }).waitFor();
  assert.equal(await page.getByLabel('Sales summary', { exact: true }).count(), 0, 'Failed read never shows stale or zero sales');
  assert.deepEqual(failures, []);
  console.log('Browser acceptance passed: desktop/mobile, explicit draft/apply, operator overrides including zero, no issuer calls; private sales, renewal dates, pending payments and failed reads.');
} finally { await browser.close(); }
