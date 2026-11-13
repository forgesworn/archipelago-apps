import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createHash, createHmac } from 'node:crypto'
import { generateSecretKey, getPublicKey, verifyEvent } from 'nostr-tools/pure'
import { readRelayMetrics, relayMetricsSampler } from './relay-metrics.mjs'

const metric = (extra = {}) => ({ v: 1, epoch: 'a'.repeat(64), elapsedMillis: 1000, ageMillis: 25,
  udpAllocations: 2, streamAllocations: 1, streamConnections: 2, udpForwardedBytes: 100, streamForwardedBytes: 200,
  forwardedPackets: 3, droppedPackets: 0, streamErrors: 0, refusedStreams: 0, ...extra })
const response = value => new Response(JSON.stringify({ v: 1, ready: true, metrics: value }), { headers: { 'Content-Type': 'application/json' } })
function secrets(t) {
  const key = generateSecretKey(); t.after(() => key.fill(0))
  return { key, values: { KITHMOOT_NODE_SERVICE_KEY: Buffer.from(key).toString('hex'), KITHMOOT_NODE_TURN_SECRET: 'b'.repeat(64) } }
}

test('metrics uses the existing signed pairing request on a fixed loopback path and exports no proof or identifiers', async t => {
  const { key, values } = secrets(t), nonces = []
  const fetchImpl = async (url, options) => {
    assert.equal(url, 'http://127.0.0.1:3751/v1/node/status'); assert.equal(options.method, 'POST')
    assert.equal(options.redirect, 'error'); assert.equal(options.credentials, 'omit')
    const event = JSON.parse(Buffer.from(options.headers.Authorization.slice(6), 'base64'))
    assert(verifyEvent(event)); assert.equal(event.pubkey, getPublicKey(key)); assert.equal(event.kind, 27235)
    const tags = new Map(event.tags)
    assert.equal(tags.get('u'), 'https://node.example/v1/node/status'); assert.equal(tags.get('method'), 'POST')
    assert.equal(tags.get('payload'), createHash('sha256').update(options.body).digest('hex'))
    nonces.push(tags.get('nonce'))
    assert.deepEqual(JSON.parse(options.body), { v: 1, pairing: createHmac('sha256', values.KITHMOOT_NODE_TURN_SECRET).update('spry-supervised-pairing-v1:' + getPublicKey(key)).digest('base64url') })
    return response(metric({ privateKey: 'PRIVATE', clientAddress: 'PRIVATE', username: 'PRIVATE' }))
  }
  const value = await readRelayMetrics({ host: 'node.example' }, values, { fetchImpl })
  await readRelayMetrics({ host: 'node.example' }, values, { fetchImpl })
  assert.notEqual(nonces[0], nonces[1]); assert.equal(value.udpAllocations, 2)
  assert(!JSON.stringify(value).includes('PRIVATE')); assert(!('pubkey' in value)); assert(!('proof' in value))
})

test('unsupported, stale, oversized, unsafe and malformed relay replies are unknown, never fabricated zero counters', async t => {
  const { values } = secrets(t)
  for (const value of [undefined, metric({ v: 2 }), metric({ epoch: '' }), metric({ ageMillis: 2001 }), metric({ streamErrors: -1 }),
    metric({ udpForwardedBytes: Number.MAX_SAFE_INTEGER, streamForwardedBytes: 1 }), metric({ elapsedMillis: null })]) {
    await assert.rejects(readRelayMetrics({ host: 'node.example' }, values, { fetchImpl: async () => response(value) }))
  }
  for (const reply of [() => new Response('x'.repeat(4097), { headers: { 'Content-Type': 'application/json' } }),
    () => new Response('{}', { status: 403, headers: { 'Content-Type': 'application/json' } }), () => new Response('{}')]) {
    await assert.rejects(readRelayMetrics({ host: 'node.example' }, values, { fetchImpl: async () => reply() }))
  }
  const sample = relayMetricsSampler({}, {}, { read: async () => { throw Error('PRIVATE') } })
  assert.equal(await sample(), null)
})

test('rates use coherent relay uptime deltas and reset after restart, counter rollback, outage or missing samples', async () => {
  let value = metric(), failure = false
  const sample = relayMetricsSampler({}, {}, { read: async () => { if (failure) throw Error('Unavailable'); return value } })
  const first = await sample(); assert.equal(first.bytesPerSecond, null); assert.equal(first.allocations, 3)
  assert(!('epoch' in first)); assert.equal(first.forwardedBytes, 300)
  value = metric({ elapsedMillis: 6000, udpForwardedBytes: 1100, streamForwardedBytes: 2200, forwardedPackets: 6 })
  const next = await sample(); assert.equal(next.bytesPerSecond, 600); assert.equal(next.udp.bytesPerSecond, 200); assert.equal(next.stream.bytesPerSecond, 400)
  assert.equal(next.intervalSeconds, 5)
  value = { ...value, elapsedMillis: 11000 }; assert.equal((await sample()).bytesPerSecond, 0)
  value = metric({ epoch: 'b'.repeat(64) }); assert.equal((await sample()).bytesPerSecond, null)
  value = metric({ epoch: 'b'.repeat(64), elapsedMillis: 2000, udpForwardedBytes: 50 }); assert.equal((await sample()).bytesPerSecond, null)
  failure = true; assert.equal(await sample(), null)
  failure = false; value = { ...value, elapsedMillis: 3000 }; assert.equal((await sample()).bytesPerSecond, null)
  assert.equal((await sample()).bytesPerSecond, null, 'same sample must not produce a false zero rate')
})
