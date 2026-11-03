import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { request } from 'node:http'
import { mkdtempSync, writeFileSync, rmSync, chmodSync, symlinkSync, statSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { finalizeEvent, generateSecretKey, getPublicKey } from 'nostr-tools/pure'
import { createController, ownerKeys, choices, NodeProcess } from './server.mjs'

async function fixture(t) {
  const key = generateSecretKey(), pubkey = getPublicKey(key), directory = mkdtempSync(join(tmpdir(), 'node-companion-'))
  writeFileSync(join(directory, 'index.html'), 'Fixture companion')
  let wall = Date.now(), mono = 1, calls = 0
  const node = { status: async () => { calls++; return { ready: true, rooms: 0 } }, setup: async value => { calls++; return value },
    start: async () => {}, stop: async () => ({}), pair: async () => { calls++; return { link: 'kithmoot://fixture' } }, prepareDelete: async () => ({ deleteReady: true }), cancelDelete: async () => ({ deleteReady: false }) }
  const server = createController({ owners: ownerKeys(pubkey), hosts: ['node.example'], node, publicDirectory: directory, now: () => wall, monotonic: () => mono })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const base = 'http://127.0.0.1:' + server.address().port
  t.after(async () => { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); rmSync(directory, { recursive: true }); key.fill(0) })
  const post = (path, body, authorization, extra = {}) => new Promise((resolve, reject) => {
    const req = request(base + path, { method: 'POST', headers: { Host: 'node.example:3753', 'Content-Type': 'application/json', ...(authorization ? { Authorization: authorization } : {}), ...extra } }, response => {
      const chunks = []
      response.on('data', chunk => chunks.push(chunk))
      response.on('end', () => resolve(new Response(Buffer.concat(chunks), { status: response.statusCode })))
      response.on('error', reject)
    })
    req.on('error', reject); req.end(body)
  })
  async function signed({ body = '{}', signer = key, url = 'https://node.example:3753/api/session', payload = body } = {}) {
    const challenge = await (await fetch(base + '/api/challenge')).json()
    const event = finalizeEvent({ kind: 27235, created_at: Math.floor(wall / 1000), content: '', tags: [['u', url], ['method', 'POST'], ['payload', createHash('sha256').update(payload).digest('hex')], ['nonce', challenge.nonce]] }, signer)
    return 'Nostr ' + Buffer.from(JSON.stringify(event)).toString('base64')
  }
  async function session() { const reply = await post('/api/session', '{}', await signed()); assert.equal(reply.status, 200); return (await reply.json()).token }
  return { base, post, signed, session, get calls() { return calls }, advance: value => { wall += value; mono += value }, rollbackWall: value => { wall -= value }, advanceMono: value => { mono += value } }
}

test('host cookies and arbitrary signers cannot inspect status or obtain a pairing code', async t => {
  const f = await fixture(t)
  assert.equal((await f.post('/api/status', '{}', undefined, { Cookie: 'archipelago_session=fixture' })).status, 401)
  assert.equal((await f.post('/api/pair', '{}', 'Bearer ' + 'A'.repeat(43))).status, 401)
  const foreign = generateSecretKey()
  try { assert.equal((await f.post('/api/session', '{}', await f.signed({ signer: foreign }))).status, 403) } finally { foreign.fill(0) }
  assert.equal(f.calls, 0)
  const token = await f.session()
  assert.equal((await f.post('/api/status', '{}', 'Bearer ' + token)).status, 200)
  assert.equal(f.calls, 1)
})

test('owner proof is bound to HTTPS audience, exact body and one-use challenge', async t => {
  const f = await fixture(t)
  for (const url of ['http://node.example:3753/api/session', 'https://evil.example:3753/api/session', 'https://node.example:3754/api/session', 'https://node.example:3753/api/status']) {
    assert.equal((await f.post('/api/session', '{}', await f.signed({ url }))).status, 401)
  }
  assert.equal((await f.post('/api/session', '{}', await f.signed({ payload: '{"changed":true}' }))).status, 401)
  const proof = await f.signed()
  assert.equal((await f.post('/api/session', '{}', proof)).status, 200)
  assert.equal((await f.post('/api/session', '{}', proof)).status, 401)
})

test('session lifetime cannot be extended by wall clock rollback', async t => {
  const f = await fixture(t), token = await f.session()
  f.rollbackWall(3600000); f.advanceMono(300001)
  assert.equal((await f.post('/api/status', '{}', 'Bearer ' + token)).status, 401)
  assert.equal(f.calls, 0)
})

test('setup requires explicit away-from-home confirmation and bounded choices, never host paths', async t => {
  const f = await fixture(t), token = await f.session()
  const value = { hostedAwayFromHome: true, maxRooms: 4, maxBytes: 268435456, minFreeBytes: 1073741824, aggregateBytesPerSecond: 1000000 }
  for (const invalid of [{ ...value, hostedAwayFromHome: false }, { ...value, maxRooms: 1000 }, { ...value, spryBinary: '/other' }, { ...value, maxBytes: -1 }]) {
    assert.equal((await f.post('/api/setup', JSON.stringify(invalid), 'Bearer ' + token)).status, 422)
  }
  assert.equal(f.calls, 0)
  assert.equal((await f.post('/api/setup', JSON.stringify(value), 'Bearer ' + token)).status, 200)
  assert.equal(f.calls, 1)
  assert.deepEqual(choices(value), value)
})

test('unknown routes, queries and oversized inputs cannot reach node controls', async t => {
  const f = await fixture(t), token = await f.session()
  assert.equal((await fetch(f.base + '/api/status?room=fixture')).status, 404)
  assert.equal((await fetch(f.base + '/../node.json')).status, 404)
  assert.equal((await f.post('/api/unknown', '{}', 'Bearer ' + token)).status, 404)
  assert.equal((await f.post('/api/setup', 'x'.repeat(5000), 'Bearer ' + token)).status, 413)
  assert.equal(f.calls, 0)
})

test('interrupted initialisation remains recoverable even after node.json was written', async t => {
  const directory = mkdtempSync(join(tmpdir(), 'node-companion-recovery-'))
  t.after(() => rmSync(directory, { recursive: true }))
  const limits = { maxRooms: 4, maxBytes: 268435456, minFreeBytes: 1073741824, aggregateBytesPerSecond: 1000000 }
  for (const name of ['node.json', 'ui-configuration.json']) writeFileSync(join(directory, name), JSON.stringify(limits), { mode: 0o600 })
  writeFileSync(join(directory, 'initialising'), '', { mode: 0o600 })
  const node = new NodeProcess({ host: 'node.example', address: '1.2.3.4' }, {}, directory)
  await node.boot()
  const status = await node.status()
  assert.equal(status.configured, false); assert.equal(status.setupPending, true); assert.equal(status.running, false)
  assert.deepEqual(status.limits, limits)
})

test('data directory ownership is enforced and pausing preserves saved state privately', async t => {
  const directory = mkdtempSync(join(tmpdir(), 'node-companion-state-')), alias = directory + '-alias'
  t.after(() => { rmSync(alias, { force: true }); rmSync(directory, { recursive: true }) })
  chmodSync(directory, 0o777)
  assert.throws(() => new NodeProcess({}, {}, directory), /ownership/)
  chmodSync(directory, 0o755)
  symlinkSync(directory, alias)
  assert.throws(() => new NodeProcess({}, {}, alias), /ownership/)
  const node = new NodeProcess({}, {}, directory)
  assert.equal(statSync(directory).mode & 0o777, 0o700)
  writeFileSync(join(directory, 'saved-room'), 'preserved', { mode: 0o600 })
  await node.stop()
  assert.equal(readFileSync(join(directory, 'saved-room'), 'utf8'), 'preserved')
  assert.equal(statSync(join(directory, 'ui-paused')).mode & 0o777, 0o600)
})

test('deletion before setup freezes setup durably and can be cancelled after restart', async t => {
  const directory = mkdtempSync(join(tmpdir(), 'node-companion-unconfigured-'))
  t.after(() => rmSync(directory, { recursive: true }))
  const facts = { host: 'node.example', address: '1.2.3.4' }, node = new NodeProcess(facts, {}, directory)
  assert.deepEqual(await node.prepareDelete(), { deleteReady: true })
  const restarted = new NodeProcess(facts, {}, directory)
  assert.equal((await restarted.status()).deleting, true)
  await assert.rejects(restarted.setup({ hostedAwayFromHome: true, maxRooms: 4, maxBytes: 268435456, minFreeBytes: 1073741824, aggregateBytesPerSecond: 1000000 }), /deletion-prepared/)
  assert.deepEqual(await restarted.cancelDelete(), { deleteReady: false })
  assert.equal((await restarted.status()).deleting, false)
})

test('a partial first setup can be prepared for deletion without starting any backend', async t => {
  const directory = mkdtempSync(join(tmpdir(), 'node-companion-partial-delete-'))
  t.after(() => rmSync(directory, { recursive: true }))
  writeFileSync(join(directory, 'node.json'), '{partial', { mode: 0o600 })
  writeFileSync(join(directory, 'initialising'), '', { mode: 0o600 })
  const node = new NodeProcess({ host: 'node.example', address: '1.2.3.4' }, {}, directory)
  assert.deepEqual(await node.prepareDelete(), { deleteReady: true })
  await assert.rejects(node.start(), /deletion-prepared/)
})

test('unknown room data cannot be declared empty merely because configuration is absent', async t => {
  const directory = mkdtempSync(join(tmpdir(), 'node-companion-lost-config-'))
  t.after(() => rmSync(directory, { recursive: true }))
  writeFileSync(join(directory, 'ledger.sqlite'), 'preserve unknown room data', { mode: 0o600 })
  const node = new NodeProcess({}, {}, directory)
  await assert.rejects(node.prepareDelete())
  assert.equal(readFileSync(join(directory, 'ledger.sqlite'), 'utf8'), 'preserve unknown room data')
  assert.equal(statSync(join(directory, 'ledger.sqlite')).mode & 0o777, 0o600)
})
