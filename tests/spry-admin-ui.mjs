import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { createRequire } from 'node:module';
import { dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { mkdir, readFile, writeFile } from 'node:fs/promises';

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, i, values) => i % 2 ? pairs : [...pairs, [value, values[i + 1]]], []));
const root = dirname(dirname(fileURLToPath(import.meta.url)));
const output = resolve(args['--output'] ?? root + '/.cache/spry-admin-ui');
assert(args['--kithmoot'], 'Pass --kithmoot with a checkout containing @playwright/test');
const require = createRequire(resolve(args['--kithmoot']) + '/package.json');
const { chromium } = require('@playwright/test');
await mkdir(output, { recursive: true });

let forwardedBytes = 2 * 1024 * 1024;
let statsAvailable = true;
let grants = [{ id: 'a'.repeat(64), pairing: 'p'.repeat(43), expiresAt: 1800000000 + 86400, recentDevices: 2 }];
const requests = [];
const server = createServer(async (request, response) => {
  const url = new URL(request.url, 'http://spry.fixture');
  if (request.method === 'GET' && url.pathname === '/v1/status') {
    response.writeHead(200, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ ready: true, controlReady: true, endpoint: 'https://spry.fixture:3744', audience: 'b'.repeat(64), privateRelay: true, message: 'Ready to pair with KithMoot.' }));
    return;
  }
  if (request.method === 'POST') {
    let body = '';
    for await (const chunk of request) body += chunk;
    requests.push({ path: url.pathname, body: JSON.parse(body || '{}') });
    let result;
    if (url.pathname === '/v1/owner/stats') result = statsAvailable ? { available: true, activeAllocations: 2, allocationLimit: 32, perDeviceAllocationLimit: 8, connectedPeers: 1, forwardedPackets: 1200, forwardedBytes, droppedPackets: 3, startedAt: 1800000000 } : { available: false };
    else if (url.pathname === '/v1/pairings/list') result = { pairings: [{ id: 'p'.repeat(43), createdAt: 1800000000 }] };
    else if (url.pathname === '/v1/owner/grants/list') result = { grants };
    else if (url.pathname === '/v1/owner/grants/remove') { grants = []; result = { removed: true }; }
    if (result) {
      response.writeHead(200, { 'Content-Type': 'application/json' });
      response.end(JSON.stringify(result));
      return;
    }
  }
  if (request.method === 'GET' && url.pathname === '/nostr-provider.js') {
    response.writeHead(200, { 'Content-Type': 'text/javascript' });
    response.end('');
    return;
  }
  if (request.method === 'GET') {
    const names = { '/': 'index.html', '/index.html': 'index.html', '/app.mjs': 'app.mjs', '/style.css': 'style.css' };
    if (names[url.pathname]) {
      const types = { '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript', '.css': 'text/css' };
      response.writeHead(200, { 'Content-Type': types[extname(names[url.pathname])] });
      response.end(await readFile(resolve(root, 'apps/spry/public', names[url.pathname])));
      return;
    }
  }
  response.writeHead(404, { 'Content-Type': 'application/json' });
  response.end(JSON.stringify({ error: 'Not found.' }));
});
server.listen(0, '127.0.0.1');
await once(server, 'listening');
const address = `http://127.0.0.1:${server.address().port}`;
let browser;
const errors = [];
try {
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.addInitScript(() => {
    window.nostr = { signEvent: async event => ({ ...event, id: '0'.repeat(64), pubkey: '1'.repeat(64), sig: '2'.repeat(64) }) };
  });
  await page.goto(address);
  await page.locator('#stat-allocations').filter({ hasText: '2 / 32' }).waitFor();
  assert.equal(await page.locator('#stat-throughput').textContent(), 'Measuring');
  assert.equal(await page.locator('#stat-bytes').textContent(), '2 MiB');
  assert.equal(await page.locator('#stat-dropped').textContent(), '3');
  assert.equal(await page.locator('#stat-peers').textContent(), '1');
  await page.waitForTimeout(1100);
  forwardedBytes += 2 * 1024 * 1024;
  await page.getByRole('button', { name: 'Refresh live activity', exact: true }).click();
  await page.locator('#stat-throughput').filter({ hasText: '/s' }).waitFor();

  await page.getByText('Manage paired devices', { exact: true }).click();
  await page.getByRole('button', { name: 'Show paired devices', exact: true }).click();
  await page.locator('#devices li').waitFor();
  assert.equal(await page.locator('#stat-devices').textContent(), '1');
  await page.getByText('Manage call access', { exact: true }).click();
  await page.getByRole('button', { name: 'Show call access', exact: true }).click();
  await page.locator('#grants li').waitFor();
  assert.equal(await page.locator('#stat-grants').textContent(), '1');
  assert.match(await page.locator('#grants').textContent(), /2 recent credential devices/);
  assert.doesNotMatch(await page.locator('#grants').textContent(), /synthetic-scope|room name|participant key/i);

  const responsive = [];
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1100 });
    const dimensions = await page.evaluate(() => ({ viewport: innerWidth, content: document.documentElement.scrollWidth }));
    assert.ok(dimensions.content <= dimensions.viewport, `Horizontal overflow at ${width}px: ${JSON.stringify(dimensions)}`);
    responsive.push({ width, ...dimensions });
    if (width === 1440 || width === 390) await page.screenshot({ path: `${output}/spry-admin-${width}.png`, fullPage: true });
  }
  page.once('dialog', dialog => dialog.dismiss());
  await page.getByRole('button', { name: 'Revoke call access aaaaaaaa', exact: true }).click();
  await page.locator('#status').filter({ hasText: 'Revocation cancelled.' }).waitFor();
  assert.equal(await page.locator('#grants li').count(), 1);
  assert.equal(requests.filter(request => request.path === '/v1/owner/grants/remove').length, 0);
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: 'Revoke call access aaaaaaaa', exact: true }).click();
  await page.locator('#grants li').waitFor({ state: 'detached' });
  assert.equal(await page.locator('#stat-grants').textContent(), '0');
  assert.match(await page.locator('#status').textContent(), /No remaining call access/);
  assert.equal(requests.filter(request => request.path === '/v1/owner/grants/remove').length, 1);
  assert.deepEqual(requests.find(request => request.path === '/v1/owner/grants/remove').body, { id: 'a'.repeat(64) });
  statsAvailable = false;
  await page.getByRole('button', { name: 'Refresh live activity', exact: true }).click();
  await page.locator('#stat-allocations').filter({ hasText: 'Unavailable' }).waitFor();
  assert.equal(await page.locator('#stat-throughput').textContent(), 'Unavailable');
  assert.match(await page.locator('#metrics-status').textContent(), /available on a private mesh relay/);
  assert.deepEqual(errors, []);
  await writeFile(`${output}/receipt.json`, JSON.stringify({ passed: true, liveCounters: true, throughputChanges: true, grantRevocationCancelled: true, grantRevoked: true, publicMetricsUnavailable: true, noRoomOrParticipantFields: true, responsive, browserErrors: errors }, null, 2) + '\n');
} finally {
  if (browser) await browser.close();
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}
