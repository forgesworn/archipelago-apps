// Exercise the packaged HTTP boundary with an ephemeral owner's signed uploads.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { finalizeEvent } from 'nostr-tools/pure';
import { hexToBytes } from 'nostr-tools/utils';

const secret = hexToBytes(process.argv[2]);
const origin = 'http://127.0.0.1:3742';
const fixtures = [
  ['text/html', '<html><body>synthetic fixture</body></html>', true],
  ['image/svg+xml', '<svg xmlns="http://www.w3.org/2000/svg"/>', true],
  ['application/xml', '<fixture/>', true],
  ['application/xhtml+xml', '<html xmlns="http://www.w3.org/1999/xhtml"/>', true],
  ['image/avif', '<!--ftypavif--><svg xmlns="http://www.w3.org/2000/svg"/>', false],
  ['image/png', 'synthetic passive bytes', false],
  ['application/octet-stream', 'synthetic encrypted bytes', false],
];
for (const [type, body, active] of fixtures) {
  const bytes = Buffer.from(body);
  const hash = createHash('sha256').update(bytes).digest('hex');
  const now = Math.floor(Date.now() / 1000);
  const event = finalizeEvent({kind: 24242, created_at: now, content: `upload ${hash}`,
    tags: [['t', 'upload'], ['x', hash], ['expiration', String(now + 300)], ['server', 'localhost']]}, secret);
  const upload = await fetch(`${origin}/upload`, {method: 'PUT', body: bytes, headers: {
    Authorization: `Nostr ${Buffer.from(JSON.stringify(event)).toString('base64')}`,
    'X-SHA-256': hash, 'Content-Type': type,
  }});
  assert.equal(upload.status, 201, `${type} upload: ${await upload.text()}`);
  for (const [method, headers, status] of [['GET', {}, 200], ['HEAD', {}, 200], ['GET', {Range: 'bytes=0-2'}, 206]]) {
    const response = await fetch(`${origin}/${hash}`, {method, headers});
    assert.equal(response.status, status, `${type} ${method}`);
    assert.equal(response.headers.get('x-content-type-options'), 'nosniff');
    assert.equal(response.headers.get('content-type'), active ? 'application/octet-stream' : type);
    if (active) assert.match(response.headers.get('content-disposition'), /^attachment/);
    if (method !== 'HEAD') assert.deepEqual(Buffer.from(await response.arrayBuffer()), status === 206 ? bytes.subarray(0, 3) : bytes);
  }
}
const mirror = await fetch(`${origin}/mirror`, {method: 'PUT', body: JSON.stringify({url: 'http://169.254.169.254/'}), headers: {'Content-Type': 'application/json'}});
assert.equal(mirror.status, 403);
console.log('Packaged blob safety: active downloads, nosniff, passive media, exact bytes/ranges and mirror refusal passed.');
