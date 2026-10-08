import assert from 'node:assert/strict';
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
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    requests.push(url.href);
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
  configOverride = '';
  await page.reload();
  assert.equal(await input.inputValue(), 'https://archipelago.example:3742', 'Without configuration, use the current node hostname');
  configOverride = 'https://user:secret@other.example:3742';
  await page.reload();
  assert.equal(await input.inputValue(), '');
  assert.equal(await page.locator('#archipelago-use-node').count(), 0, 'Malformed configured destinations fail closed');
  await context.close();
  console.log('Own-node browser acceptance passed: default, override, consent reset, Tor isolation, pool selection, reload and no background requests.');
} finally {
  await browser.close();
}
