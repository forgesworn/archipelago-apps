import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { finalizeEvent } from 'nostr-tools/pure';
import { chromium } from 'playwright-core';

// The actual packaged page is served by nginx; routing gives it a synthetic
// HTTPS node hostname without changing machine DNS or trusting a test CA.
const upstream = process.env.WILDBLOOM_TEST_ORIGIN || 'http://127.0.0.1:3743';
const origin = 'https://archipelago.example:3743';
const browser = await chromium.launch({
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
});
try {
  const context = await browser.newContext();
  const requests = [];
  const errors = [];
  let configOverride;
  const fixture = JSON.parse(readFileSync(new URL('./fixtures/storage-combined.json', import.meta.url)));
  const now = Math.floor(Date.now() / 1000) - 5;
  const description = { ...fixture.description, observed_at: now, expires_at: now + 7200 };
  const content = JSON.parse(fixture.event.content);
  content.storage = description;
  const event = finalizeEvent({ kind: fixture.event.kind, created_at: now,
    tags: fixture.event.tags.map(t => t[0] === 'expiration' ? ['expiration', String(description.expires_at)] : t),
    content: JSON.stringify(content) }, new Uint8Array(32).fill(1));
  let relayQueries = 0, inspections = 0;
  await context.routeWebSocket('wss://relay.example/', socket => {
    socket.onMessage(raw => {
      const message = JSON.parse(raw);
      if (message[0] !== 'REQ') return;
      relayQueries++;
      assert.deepEqual(message[2], { kinds: [31402], '#t': ['forgesworn-storage-service-v1'], limit: 64 });
      socket.send(JSON.stringify(['EVENT', message[1], event]));
      socket.send(JSON.stringify(['EOSE', message[1]]));
    });
  });
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    requests.push(url.href);
    if (url.href === 'https://storage.example/services/v1') {
      inspections++;
      assert.equal(route.request().method(), 'GET');
      assert.equal(route.request().headers().authorization, undefined);
      assert.equal(route.request().headers().cookie, undefined);
      return route.fulfill({ contentType: 'application/json', headers: { 'cache-control': 'no-store' }, body: JSON.stringify(description) });
    }
    if (url.origin !== origin) return route.abort();
    if (url.pathname === '/archipelago-config.js' && configOverride !== undefined) {
      return route.fulfill({ contentType: 'application/javascript', body: `window.ARCHIPELAGO_NODE_ORIGIN = ${JSON.stringify(configOverride)};` });
    }
    const response = await fetch(upstream + url.pathname + url.search);
    await route.fulfill({ status: response.status, headers: Object.fromEntries(response.headers), body: Buffer.from(await response.arrayBuffer()) });
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin + '/#client-setup');
  const input = page.locator('#blossom-server');
  await page.locator('#archipelago-use-node').waitFor();
  const home = process.env.WILDBLOOM_EXPECT_HOME || 'https://archipelago.example:3742';
  assert.equal(await input.inputValue(), home);
  assert.equal(await page.locator('#protect-file').isChecked(), true);
  assert.equal(await page.locator('#upload-consent').isChecked(), false);
  assert.equal(requests.every(value => new URL(value).origin === origin), true, 'No background storage/payment/discovery request');
  await input.fill('https://other.example');
  assert.equal(await input.inputValue(), 'https://other.example');
  // Selecting home is a normal endpoint change and must revoke stale consent.
  await page.locator('#upload-consent').evaluate(el => { el.checked = true; });
  await page.locator('#archipelago-use-node').click();
  assert.equal(await input.inputValue(), home);
  assert.equal(await page.locator('#upload-consent').isChecked(), false);
  await page.locator('input[name="network-profile"][value="tor"]').check();
  assert.equal(await input.inputValue(), '');
  assert.equal(await page.locator('#archipelago-use-node').isDisabled(), true);
  await page.locator('input[name="network-profile"][value="direct"]').check();
  assert.equal(await input.inputValue(), home);
  await page.locator('#storage-mode').selectOption('replicas');
  assert.equal(await page.locator('#archipelago-use-node').isDisabled(), true);
  assert.equal(await page.locator('#pool-nodes').inputValue(), '');
  await page.locator('#storage-mode').selectOption('single');
  assert.equal(await input.inputValue(), home);
  assert.equal(await page.locator('#archipelago-use-node').isDisabled(), false);
  await page.reload();
  assert.equal(await input.inputValue(), home);
  assert.deepEqual(errors, []);
  if (process.env.WILDBLOOM_SCREENSHOT) await page.screenshot({ path: process.env.WILDBLOOM_SCREENSHOT, fullPage: true });
  assert.equal(relayQueries, 0, 'Packaged browser opens no discovery relay on load');
  assert.equal(inspections, 0);
  const details = page.locator('#client-services details').filter({ has: page.locator('#discover-storage-services') });
  await details.locator('summary').click();
  await page.fill('#relay-urls', 'wss://relay.example/');
  await page.click('#discover-storage-services');
  await page.locator('#node-service-status').filter({ hasText: 'service listings for this network profile' }).waitFor();
  assert.equal(relayQueries, 1);
  assert.equal(inspections, 0, 'Relay lookup must not inspect operator HTTP');
  await page.locator('#storage-service-results button').first().click();
  assert.equal(inspections, 0, 'Selection must not inspect operator HTTP');
  await page.click('#inspect-storage-service');
  await page.locator('#node-service-status').filter({ hasText: 'Current service identity and terms checked' }).waitFor();
  assert.equal(inspections, 1);
  assert.match(await page.locator('#storage-service-description').textContent(), /best-effort/);
  await page.click('#use-storage-service');
  await page.locator('#node-service-status').filter({ hasText: 'Paid node selected' }).waitFor();
  assert.equal(await input.inputValue(), 'https://storage.example/');
  assert.equal(inspections, 1, 'Using checked paid node must not buy or load offers');
  assert.equal(await page.locator('#checkout-consent').isChecked(), false);
  await page.locator('#archipelago-use-node').click();
  assert.equal(await input.inputValue(), home);
  assert.equal(await page.locator('#storage-service-description').textContent(), '', 'Home selection clears discovered terms');
  assert.deepEqual(errors, []);
  configOverride = '';
  await page.reload();
  assert.equal(await input.inputValue(), 'https://archipelago.example:3742', 'Without configuration, use the current node hostname');
  configOverride = 'https://user:secret@other.example:3742';
  await page.reload();
  assert.equal(await input.inputValue(), '');
  assert.equal(await page.locator('#archipelago-use-node').count(), 0, 'Malformed configured destinations fail closed');
  await context.close();
  console.log('Own-node browser acceptance passed: default, override, consent reset, Tor isolation, pool selection, reload, explicit signed public discovery and no background requests.');
} finally {
  await browser.close();
}
