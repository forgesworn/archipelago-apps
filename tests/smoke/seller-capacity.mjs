import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { finalizeEvent, getPublicKey } from 'nostr-tools/pure';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const image = process.argv[2];
assert.ok(image, 'Pass the Node image');
const docker = (...args) => execFileSync('docker', args, { encoding: 'utf8' }).trim();
mkdirSync(join(root, '.cache'), { recursive: true });
const tmp = mkdtempSync(join(root, '.cache/archy-seller-'));
const volume = `archy-seller-test-${randomUUID()}`;
const serviceVolume = `${volume}-service`;
const owner = new Uint8Array(32).fill(31);
const buyer = new Uint8Array(32).fill(32);
const stranger = new Uint8Array(32).fill(33);
const hash = value => createHash('sha256').update(value).digest('hex');
const auth = (event, key) => 'Nostr ' + Buffer.from(JSON.stringify(finalizeEvent(event, key))).toString('base64');
let cid;
try {
  const settings = JSON.parse(readFileSync(join(root, 'docs/wildbloom-sales.example.json')));
  Object.assign(settings, { quota_bytes: 100, owner_reserved_bytes: 40, offer_capacity_bytes: 60,
    max_blob_bytes: 100, price_sats: 1, issuer_reviewed: true,
    refund_policy: 'Synthetic local acceptance only; no real payment.' });
  const input = join(tmp, 'settings.json');
  const output = join(tmp, 'prepared');
  writeFileSync(input, JSON.stringify(settings), { mode: 0o600 });
  execFileSync('python3', [join(root, 'scripts/configure-wildbloom-sales.py'), input,
    '--output', output, '--issuer-ip', '1.1.1.1', '--enable-sales']);
  const discoverySettings = JSON.parse(readFileSync(join(root, 'docs/wildbloom-discovery.example.json')));
  discoverySettings.service_pubkey = getPublicKey(new Uint8Array(32).fill(34));
  const discoveryInput = join(tmp, 'discovery-settings.json');
  const discoveryOutput = join(tmp, 'discovery');
  writeFileSync(discoveryInput, JSON.stringify(discoverySettings), { mode: 0o600 });
  execFileSync('python3', [join(root, 'scripts/configure-wildbloom-discovery.py'), discoveryInput,
    '--manifest', join(output, 'manifest.yml'), '--output', discoveryOutput, '--enable-inspection']);
  const serviceProfile = readFileSync(join(discoveryOutput, 'service-profile.json'));
  const profile = readFileSync(process.argv[3] || join(output, 'checkout-profile.json'));
  const parsedProfile = JSON.parse(profile);
  const manifest = JSON.parse(readFileSync(join(discoveryOutput, 'manifest.yml'))).app;
  docker('volume', 'create', volume);
  docker('volume', 'create', serviceVolume);
  execFileSync('docker', ['run', '--rm', '-i', '--network', 'none', '-v', `${serviceVolume}:/service`,
    '--entrypoint', 'sh', image, '-c', 'umask 077; chmod 700 /service; cat > /service/service-profile.json'], { input: serviceProfile });
  execFileSync('docker', ['run', '--rm', '-i', '--network', 'none', '-v', `${volume}:/data`,
    '--entrypoint', 'sh', image, '-c', 'umask 077; mkdir -p /data/operator; cat > /data/operator/checkout-profile.json'], { input: profile });
  const env = manifest.environment.flatMap(value => ['-e', value]);
  cid = docker('run', '-d', '--cap-drop=ALL', '--security-opt', 'no-new-privileges', '--read-only',
    '--tmpfs', '/tmp', '-p', '127.0.0.1::3742', '-v', `${volume}:/data`, '-v', `${serviceVolume}:/service`, ...env,
    '-e', `WILDBLOOM_ALLOW_PUBKEYS=${getPublicKey(owner)}`, '-e', 'WILDBLOOM_PUBLIC_URL=https://storage.example:3742',
    '-e', 'WILDBLOOM_SERVER_NAME=storage.example', image);
  const port = docker('port', cid, '3742/tcp').split(':').at(-1);
  let base = `http://127.0.0.1:${port}`;
  async function ready() {
    for (let n = 0; n < 60; n++) {
      try { if ((await fetch(base + '/healthz')).ok) return; } catch {}
      await new Promise(r => setTimeout(r, 250));
    }
    throw new Error('Node did not become ready');
  }
  await ready();
  async function availability(expected) {
    const response = await fetch(base + '/services/v1', { headers: { origin: 'https://storage.example:3743' } });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('cache-control'), 'no-store');
    assert.equal(response.headers.get('access-control-allow-origin'), 'https://storage.example:3743');
    const listing = await response.json();
    assert.equal(listing.service_pubkey, discoverySettings.service_pubkey);
    assert.equal(listing.identifier, discoverySettings.identifier);
    assert.deepEqual(listing.origins, ['https://storage.example:3742/']);
    assert.equal(listing.services.length, 1);
    assert.equal(listing.services[0].type, 'paid-storage');
    assert.equal(listing.services[0].availability, expected);
    for (const privateField of ['max_paid_bytes', 'owner_reserved_bytes', 'committed_bytes', 'quota_bytes', getPublicKey(owner), getPublicKey(buyer)]) {
      assert.equal(JSON.stringify(listing).includes(privateField), false, 'No private capacity or identities in public snapshot');
    }
  }
  await availability('accepting');
  const offers = await (await fetch(base + '/checkout/v1/offers')).json();
  assert.match(JSON.stringify(offers), /lnurlcash-reference/);
  const customerOrigin = parsedProfile.browser_origins.at(-1);
  const preflight = await fetch(base + '/checkout/v1/orders', { method: 'OPTIONS', headers: {
    origin: customerOrigin, 'access-control-request-method': 'POST',
    'access-control-request-headers': 'authorization,content-type',
  } });
  assert.equal(preflight.headers.get('access-control-allow-origin'), customerOrigin, 'Chosen customer app can use checkout');
  const unknownOrigin = await fetch(base + '/checkout/v1/offers', { headers: { origin: 'https://unselected.example' } });
  assert.equal(unknownOrigin.headers.get('access-control-allow-origin'), null, 'Unselected customer origins stay blocked');
  async function quote(key, requestId) {
    const path = '/checkout/v1/orders';
    const body = JSON.stringify({ request_id: requestId, offer_id: settings.offer_id, rail: 'lnurlcash', issuer_id: 'lnurlcash-reference', renews: null });
    const authorization = auth({ kind: 27235, created_at: Math.floor(Date.now() / 1000), content: '',
      tags: [['u', 'https://storage.example:3742' + path], ['method', 'POST'], ['payload', hash(body)]] }, key);
    return fetch(base + path, { method: 'POST', headers: { authorization, 'content-type': 'application/json' }, body });
  }
  const firstResponse = await quote(buyer, 'first');
  assert.equal(firstResponse.status, 200);
  const first = await firstResponse.json();
  await availability('full'); // 40 bytes physically free, but no paid allocation remains.
  assert.equal((await quote(stranger, 'second')).status, 503, 'Customer ceiling applies before payment');
  const bytes = Buffer.alloc(40, 7);
  const sha = hash(bytes);
  async function upload(key) {
    const now = Math.floor(Date.now() / 1000);
    return fetch(base + '/upload', { method: 'PUT', body: bytes, headers: {
      'content-type': 'application/octet-stream', 'x-sha-256': sha,
      authorization: auth({ kind: 24242, created_at: now, content: 'upload ' + sha,
        tags: [['t', 'upload'], ['x', sha], ['expiration', String(now + 300)], ['server', 'storage.example']] }, key),
    } });
  }
  assert.ok([401, 403].includes((await upload(buyer)).status), 'An unpaid quote gives no write access');
  assert.equal((await upload(owner)).status, 201, 'Owner can use the reserved portion');
  assert.deepEqual(Buffer.from(await (await fetch(base + '/' + sha)).arrayBuffer()), bytes);
  docker('restart', cid);
  base = `http://127.0.0.1:${docker('port', cid, '3742/tcp').split(':').at(-1)}`;
  await ready();
  await availability('full');
  assert.deepEqual(await (await quote(buyer, 'first')).json(), first, 'Quote and capacity survive restart');
  assert.equal((await quote(stranger, 'second')).status, 503);
  assert.deepEqual(Buffer.from(await (await fetch(base + '/' + sha)).arrayBuffer()), bytes);
  // Pausing keeps the profile and ledger present but sets the aggregate
  // ceiling to zero. Existing immutable quotes still resolve after restart.
  parsedProfile.max_paid_bytes = 0;
  execFileSync('docker', ['exec', '-i', cid, 'sh', '-c', 'cat > /data/operator/checkout-profile.json'], { input: JSON.stringify(parsedProfile) });
  docker('restart', cid);
  base = `http://127.0.0.1:${docker('port', cid, '3742/tcp').split(':').at(-1)}`;
  await ready();
  await availability('full');
  assert.deepEqual(await (await quote(buyer, 'first')).json(), first, 'Pause preserves existing quotes');
  assert.equal((await quote(stranger, 'paused-new')).status, 503, 'Pause refuses new quotes');
  assert.deepEqual(Buffer.from(await (await fetch(base + '/' + sha)).arrayBuffer()), bytes);
  console.log('Packaged seller/discovery acceptance passed: generated reference-mint profile, bounded quotes, owner reserve, public accepting/full terms without private metadata, unpaid refusal, restart and pause. No issuer payment calls.');
} catch (error) {
  if (cid) console.error(docker('logs', '--tail', '20', cid));
  throw error;
} finally {
  if (cid) docker('rm', '-f', cid);
  docker('volume', 'rm', '-f', volume);
  docker('volume', 'rm', '-f', serviceVolume);
  rmSync(tmp, { recursive: true, force: true });
}
