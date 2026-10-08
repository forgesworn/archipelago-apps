// Synthetic, authenticated full-read audit against the disposable smoke node.
import assert from 'node:assert/strict';
import { createHash, randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { finalizeEvent } from 'nostr-tools/pure';
import { hexToBytes } from 'nostr-tools/utils';
const [secret, file] = process.argv.slice(2);
const bytes = readFileSync(file);
const sha256 = createHash('sha256').update(bytes).digest('hex');
const nonce = randomBytes(32).toString('hex');
const body = JSON.stringify({ sha256, nonce });
const endpoint = 'http://localhost:3742/storage/v1/proof';
const auth = finalizeEvent({ kind: 27235, created_at: Math.floor(Date.now()/1000), content: '', tags: [
  ['u', endpoint], ['method', 'POST'], ['payload', createHash('sha256').update(body).digest('hex')],
]}, hexToBytes(secret));
const response = await fetch('http://127.0.0.1:3742/storage/v1/proof', {
  method: 'POST', body, headers: { 'content-type': 'application/json', authorization: `Nostr ${Buffer.from(JSON.stringify(auth)).toString('base64')}` },
});
assert.equal(response.status, 200, 'authenticated full-read audit');
const proof = await response.json();
const size = Buffer.alloc(8); size.writeBigUInt64BE(BigInt(bytes.length));
assert.deepEqual(proof, { version: 1, sha256, nonce, size: bytes.length,
  digest: createHash('sha256').update(Buffer.concat([Buffer.from('wildbloom.storage-proof.v1\n'), Buffer.from(nonce, 'hex'), size, bytes])).digest('hex') });
const denied = await fetch('http://127.0.0.1:3742/storage/v1/proof', {method:'POST',body,headers:{'content-type':'application/json'}});
assert.ok(denied.status >= 400 && denied.status < 500, 'unsigned audit must fail');
console.log('Full-read proof independently verified; unsigned audit refused.');
