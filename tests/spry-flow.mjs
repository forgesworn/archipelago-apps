// Actual pairing UI -> actual KithMoot -> Rust control service -> standalone Rust TURN.
// Only generated identities/media and loopback fixtures. Never prints capability material.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve, join, extname, sep } from 'node:path';
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { randomBytes, createHash } from 'node:crypto';

const args = Object.fromEntries(process.argv.slice(2).reduce((pairs, value, i, values) => i % 2 ? pairs : [...pairs, [value, values[i + 1]]], []));
const root = resolve(args['--kithmoot']), binary = resolve(args['--node-binary']), relayBinary = resolve(args['--turn-binary']);
const output = resolve(args['--output']);
const standingSeconds = Number(args['--standing-seconds'] ?? 330);
assert(standingSeconds >= 0 && standingSeconds <= 420);
const require = createRequire(join(root, 'package.json'));
const { chromium } = require('@playwright/test');
const { finalizeEvent, generateSecretKey, getPublicKey } = require('nostr-tools/pure');
const scratch = await mkdtemp(join(tmpdir(), 'spry-pairing-'));
const children = [], contexts = [], usernames = new Set(), credentials = new Set(), counts = {};
const diagnostics = [];
let browser, appServer, phase = 'starting';
function mark(value) { phase = value; process.stdout.write(`Spry acceptance: ${value}\n`); }
async function port() { const server = createServer(); server.listen(0, '127.0.0.1'); await once(server, 'listening'); const port = server.address().port; await new Promise(resolve => server.close(resolve)); return port; }
async function wait(read, test, label, ms = 60000) {
  const until = Date.now() + ms;
  while (Date.now() < until) { try { const value = await read(); if (test(value)) return value; } catch {} await new Promise(resolve => setTimeout(resolve, 100)); }
  throw new Error(label);
}
function child(command, args, env = {}) { const process = spawn(command, args, { cwd: root, env: { ...globalThis.process.env, ...env }, stdio: 'ignore' }); children.push(process); return process; }
async function stop(process) { if (process.exitCode !== null || process.signalCode !== null) return; process.kill('SIGTERM'); await Promise.race([once(process, 'exit'), new Promise(resolve => setTimeout(resolve, 2500))]); if (process.exitCode === null && process.signalCode === null) { process.kill('SIGKILL'); await once(process, 'exit'); } }
async function media(page) {
  await page.locator('#callToggle').waitFor({ state: 'visible' });
  if (await page.locator('#deviceControls').isHidden()) await page.locator('#callToggle').click();
  await page.locator('#deviceControls').waitFor({ state: 'visible' });
  for (const id of ['#toggleCamera', '#toggleMic']) { if (await page.locator(id).getAttribute('data-on') !== 'true') await page.locator(id).click(); }
}
async function evidence(page) {
  return page.evaluate(async () => {
    const pairs = [], media = { frames: 0, audioBytes: 0, audioEnergy: 0 };
    for (const pc of window.__spryPcs ?? []) {
      const stats = await pc.getStats();
      stats.forEach(stat => {
        if (stat.type === 'candidate-pair' && stat.state === 'succeeded' && stat.nominated) pairs.push({ local: stats.get(stat.localCandidateId)?.candidateType, remote: stats.get(stat.remoteCandidateId)?.candidateType });
        if (stat.type === 'inbound-rtp' && stat.kind === 'video') media.frames += stat.framesDecoded ?? 0;
        if (stat.type === 'inbound-rtp' && stat.kind === 'audio') { media.audioBytes += stat.bytesReceived ?? 0; media.audioEnergy += stat.totalAudioEnergy ?? 0; }
      });
    }
    return { ...media, pairs, relayOnly: (window.__spryPcs ?? []).every(pc => pc.getConfiguration().iceTransportPolicy === 'relay'),
      videos: [...document.querySelectorAll('#room .participant video')].filter(video => video.videoWidth > 0 && !video.paused).length };
  });
}
async function joined(page, link, name) {
  await page.goto(link);
  await page.locator('#roomArea:visible, #join:visible, #displayName:visible').first().waitFor({ state: 'visible', timeout: 60000 });
  if (await page.locator('#displayName').isVisible()) await page.locator('#displayName').fill(name);
  if (await page.locator('#join').isVisible()) await page.locator('#join').click();
  await page.locator('#roomArea').waitFor({ state: 'visible', timeout: 60000 });
}
try {
  const controlPort = await port(), relayPort = await port();
  const endpoint = `https://relay.example:${controlPort}`, appOrigin = `https://localhost:${await port()}`;
  const owner = generateSecretKey(), secret = randomBytes(32).toString('hex');
  const control = child(binary, [], { SPRY_PUBLIC_URL: endpoint, SPRY_OWNER_KEYS: getPublicKey(owner), SPRY_TURN_SECRET: secret,
    SPRY_KITHMOOT_URL: appOrigin + '/j/', SPRY_STATE_FILE: join(scratch, 'pairings.json'), SPRY_HTTP_PORT: String(controlPort),
    SPRY_RELAY_IP: '127.0.0.1', SPRY_LOCAL_TEST: 'true', SPRY_RELAY_BINARY: relayBinary });
  mark('waiting for Rust service');
  await wait(() => fetch(`http://127.0.0.1:${controlPort}/v1/status`).then(r => r.json()), value => value.ready === true, 'Rust service not ready', 15000);
  mark('Rust service ready');
  child(process.execPath, [join(root, 'test/ws-relay.mjs')], { RELAY_PORT: String(relayPort) });
  await wait(() => fetch(`http://127.0.0.1:${relayPort}/`), response => response.ok, 'Signalling not ready', 15000);
  const dist = join(root, 'app/dist');
  appServer = createServer(async (request, response) => {
    try {
      const path = new URL(request.url, 'http://localhost').pathname.replace(/^\/j\//, '');
      const file = resolve(dist, path || 'index.html');
      if (!file.startsWith(dist + sep)) { response.writeHead(404).end(); return; }
      const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.wasm': 'application/wasm', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
      const bytes = await readFile(file); response.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream' }); response.end(bytes);
    } catch { response.writeHead(404).end(); }
  });
  appServer.listen(0, '127.0.0.1'); await once(appServer, 'listening');
  const appPort = appServer.address().port;
  browser = await chromium.launch({ headless: true, args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream', '--autoplay-policy=no-user-gesture-required', '--disable-audio-output', '--disable-features=LocalNetworkAccessChecks', '--host-resolver-rules=MAP relay.example 127.0.0.1'] });
  async function device() {
    const context = await browser.newContext({ permissions: ['camera', 'microphone'], serviceWorkers: 'block' }); contexts.push(context);
    await context.exposeFunction('__sprySign', event => finalizeEvent(event, owner));
    await context.addInitScript(({ relay }) => {
      if (location.hostname === 'relay.example') window.nostr = { signEvent: event => window.__sprySign(event) };
      if (location.hostname === 'localhost') {
        localStorage.setItem('kithmoot.relays.v1', JSON.stringify({ default: [{ url: relay, read: true, write: true }] }));
        localStorage.setItem('kithmoot.hide-ip.v1', '1');
      }
      const Native = window.RTCPeerConnection; window.__spryPcs = [];
      window.RTCPeerConnection = class extends Native { constructor(config) { super(config); window.__spryPcs.push(this); } };
      const gum = navigator.mediaDevices?.getUserMedia.bind(navigator.mediaDevices);
      if (gum) navigator.mediaDevices.getUserMedia = async config => {
        const stream = await gum(config);
        if (config.audio) {
          for (const track of stream.getAudioTracks()) { stream.removeTrack(track); track.stop(); }
          const audio = new AudioContext(), oscillator = audio.createOscillator(), output = audio.createMediaStreamDestination();
          oscillator.frequency.value = 440; oscillator.connect(output); oscillator.start(); await audio.resume();
          for (const track of output.stream.getAudioTracks()) stream.addTrack(track);
        }
        return stream;
      };
      const NativeSocket = window.WebSocket;
      window.WebSocket = class extends NativeSocket { constructor(url, protocols) {
        if (new URL(url).hostname !== '127.0.0.1') throw new Error('External signalling refused by local fixture');
        super(url, protocols);
      } };
    }, { relay: `ws://127.0.0.1:${relayPort}` });
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin === endpoint) {
        if (url.pathname === '/nostr-provider.js') { await route.fulfill({ status: 200, contentType: 'text/javascript', body: '' }); return; }
        counts[url.pathname] = (counts[url.pathname] ?? 0) + 1;
        const headers = { ...request.headers() }; delete headers.host; delete headers['content-length'];
        const response = await fetch(`http://127.0.0.1:${controlPort}${url.pathname}`, { method: request.method(), headers, body: request.postDataBuffer() ?? undefined });
        const body = await response.text();
        if (url.pathname === '/v1/credentials' && response.ok) { const value = JSON.parse(body); usernames.add(value.username); credentials.add(value.credential); }
        await route.fulfill({ status: response.status, headers: Object.fromEntries(response.headers), body }); return;
      }
      if (url.origin === appOrigin) {
        const response = await fetch(`http://127.0.0.1:${appPort}${url.pathname}`);
        await route.fulfill({ status: response.status, headers: Object.fromEntries(response.headers), body: Buffer.from(await response.arrayBuffer()) }); return;
      }
      if (url.hostname === '127.0.0.1') { await route.continue(); return; }
      await route.abort();
    });
    const page = await context.newPage();
    const wire = { sent: 0, received: 0 }; diagnostics.push(wire);
    page.on('websocket', socket => {
      socket.on('framesent', frame => { try { const value=JSON.parse(String(frame.payload)); if (value[0]==='EVENT' && value[1]?.kind===20465) wire.sent++; } catch {} });
      socket.on('framereceived', frame => { try { const value=JSON.parse(String(frame.payload)); if (value[0]==='EVENT' && value[2]?.kind===20465) wire.received++; } catch {} });
    });
    page.on('console', message => { if (message.type() === 'error') diagnostics.push(message.text().slice(0, 2000)); });
    page.on('pageerror', error => diagnostics.push(error.stack));
    return page;
  }
  const a = await device();
  mark('opening pairing UI');
  await a.goto(endpoint + '/');
  await wait(() => a.locator('#pair').isEnabled(), Boolean, 'Pair button not ready');
  await a.getByRole('button', { name: 'Pair with KithMoot', exact: true }).click();
  await a.getByRole('button', { name: 'Pair Spry', exact: true }).click({ timeout: 30000 });
  await wait(() => a.locator('#spryPairingStatus').textContent(), text => text.includes('Paired with'), 'Pairing not saved');
  assert.equal(new URL(a.url()).hash, '');
  mark('paired');
  await a.locator('#newRoom:visible, #newMenuButton:visible').first().waitFor({ state: 'visible' });
  if (await a.locator('#newRoom').isVisible()) await a.locator('#newRoom').click();
  else { await a.locator('#newMenuButton').click(); await a.locator('#newMenuRoom').click(); }
  await a.locator('#roomName').waitFor({ state: 'visible' });
  await a.locator('#roomName').fill('Generated Spry call');
  if (await a.locator('#newRoomYourName').isVisible()) await a.locator('#newRoomYourName').fill('Generated A');
  mark('creating room');
  await a.locator('#create').click(); await a.locator('#roomArea').waitFor({ state: 'visible', timeout: 60000 });
  const link = await wait(() => a.locator('#shareUrl').inputValue(), value => value.includes('#'), 'Room link missing');
  const b = await device(); await joined(b, link, 'Generated B');
  mark('joining first call');
  await media(a); await media(b);
  const valid = value => value.frames > 0 && value.audioBytes > 0 && value.audioEnergy > 0 && value.videos >= 2 && value.pairs.length > 0 && value.pairs.every(pair => pair.local === 'relay' && pair.remote === 'relay') && value.relayOnly;
  const two = await Promise.all([a,b].map(page => wait(() => evidence(page), valid, 'Two-person media missing', 90000)));
  mark('two-person call passed');
  const c = await device(); await joined(c, link, 'Generated C'); await media(c);
  const group = await Promise.all([a,b,c].map(page => wait(() => evidence(page), value => valid(value) && value.pairs.length >= 2 && value.videos >= 3, 'Group media missing', 90000)));
  assert.equal(counts['/v1/pairings/claim'], 1);
  assert.ok(usernames.size >= 3);
  for (const page of [b,c]) assert.equal(await page.evaluate(() => localStorage.getItem('kithmoot.call-relay.v1')), null);
  const invitation = Buffer.from(new URL(link).hash.slice(1), 'base64url').toString();
  for (const value of [...credentials, secret]) assert.ok(!invitation.includes(value));
  mark('automatic group access passed');
  const rss = [];
  for (let elapsed = 0; elapsed < standingSeconds; elapsed += 15) {
    rss.push(Number(execFileSync('ps', ['-o','rss=','-p',String(control.pid)], { encoding:'utf8' }).trim()));
    await new Promise(resolve => setTimeout(resolve, Math.min(15, standingSeconds - elapsed) * 1000));
  }
  const standing = await Promise.all([a,b,c].map((page, index) => wait(() => evidence(page), value => valid(value) && value.frames > group[index].frames && value.audioBytes > group[index].audioBytes, 'Standing media stopped', 60000)));
  if (standingSeconds >= 300) assert.ok(usernames.size >= 6, 'Credentials did not renew');
  mark('standing call passed');
  const receipt = { schema: 1, passed: true, scope: 'local-generated-media-pair-once-and-automatic-call-access',
    runtime: 'Rust relay and Rust control service', nodeBinarySha256: createHash('sha256').update(await readFile(binary)).digest('hex'),
    nodeBinaryBytes: (await readFile(binary)).length, relayBinarySha256: createHash('sha256').update(await readFile(relayBinary)).digest('hex'),
    pairingClaims: counts['/v1/pairings/claim'], distinctCredentialUsernames: usernames.size, standingSeconds,
    controlProcessRssKiB: rss.length ? { maximum: Math.max(...rss), samples: rss.length } : undefined,
    configuredThroughPairingUi: true, guestRelaySettingsRequired: false, injectedIceServers: false, invitationOmitsCredentials: true,
    twoPerson: two, group, standing,
    limits: ['Same-host Chromium with generated media and loopback TURN; local-network checks disabled for this fixture', 'HTTPS control requests routed to the local Rust HTTP service; no public TLS or NAT proof', 'No physical Android or independent-node installation proof'] };
  await writeFile(output, JSON.stringify(receipt, null, 2) + '\n');
  mark('receipt saved');
} catch (error) {
  await writeFile(output + '.failure.txt', error instanceof Error ? error.stack : String(error), { mode: 0o600 });
  await writeFile(output + '.console.json', JSON.stringify(diagnostics, null, 2), { mode: 0o600 });
  await writeFile(output + '.api.json', JSON.stringify({counts, distinctCredentialUsernames:usernames.size}, null,2), {mode:0o600});
  await writeFile(output + '.media.json', JSON.stringify(await Promise.all(contexts.flatMap(context => context.pages()).map(page => evidence(page).catch(() => ({})))), null, 2), { mode: 0o600 });
  if (contexts.length) await writeFile(output + '.state.json', JSON.stringify(await Promise.all(contexts.flatMap(context => context.pages()).map(page => page.evaluate(() => ({
    status: document.getElementById('status')?.textContent, text: document.body.innerText.slice(0, 4000),
    savedOffers: Object.keys(JSON.parse(localStorage.getItem('kithmoot.spry-rooms.v1') || '{}')).length,
  })).catch(() => ({})))), null, 2), { mode: 0o600 });
  process.stderr.write(`Spry acceptance failed during ${phase}: ${error instanceof Error ? error.name : 'failure'}\n`);
  process.exitCode = 1;
} finally {
  await Promise.allSettled(contexts.map(context => context.close()));
  if (browser) await browser.close();
  if (appServer) { appServer.closeAllConnections(); await new Promise(resolve => appServer.close(resolve)); }
  await Promise.allSettled(children.map(stop));
  await rm(scratch, { recursive:true, force:true });
}
