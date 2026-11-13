// Disposable offline fixture only. This well-known test key has no authority
// outside the fixture. The signed audience models the host's HTTPS app gate;
// this loopback driver does not qualify that gate's HTTP session handling.
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { request } from 'node:http'
import { createHash } from 'node:crypto'
import { finalizeEvent } from 'nostr-tools/pure'
assert.equal(process.env.E2E_ARCHY_NODE_INGRESS, 'disposable-offline-nginx')
assert(existsSync('/fixture/disposable-archy-node-ingress'))
const key = new Uint8Array(32); key[31] = 1
const post = (path, value, authorization) => new Promise((resolve, reject) => {
  const req = request('http://127.0.0.1:3753/api/' + path, { method: 'POST', headers: { Host: 'node.example:3753', 'Content-Type': 'application/json', ...(authorization ? { Authorization: authorization } : {}) } }, response => {
    let text = ''; response.on('data', bytes => { text += bytes; if (text.length > 65536) req.destroy(Error('Oversized reply')) })
    response.on('end', () => { try { resolve({ status: response.statusCode, body: JSON.parse(text) }) } catch (error) { reject(error) } })
    response.on('error', reject)
  })
  req.setTimeout(60000, () => req.destroy(Error('Fixture API timeout'))); req.on('error', reject); req.end(JSON.stringify(value))
})
assert.equal((await post('status', {})).status, 401)
const challenge = await (await fetch('http://127.0.0.1:3753/api/challenge')).json()
const event = finalizeEvent({ kind: 27235, created_at: Math.floor(Date.now() / 1000), content: '', tags: [['u', 'https://node.example:3753/api/session'], ['method', 'POST'], ['payload', createHash('sha256').update('{}').digest('hex')], ['nonce', challenge.nonce]] }, key)
const login = await post('session', {}, 'Nostr ' + Buffer.from(JSON.stringify(event)).toString('base64'))
assert.equal(login.status, 200); const token = login.body.token
const api = async (action, value = {}) => { const reply = await post(action, value, 'Bearer ' + token); assert.equal(reply.status, 200, JSON.stringify(reply.body)); return reply.body.result }
const setupChoices = { hostedAwayFromHome: true, maxRooms: 8, aggregateBytesPerSecond: 1000000, maxBytes: 268435456, minFreeBytes: 1073741824 }
const ready = async () => {
  let result
  for (let attempt = 0; attempt < 30; attempt++) {
    result = await api('status')
    if (result.ready) return result
    await new Promise(resolve => setTimeout(resolve, 1000))
  }
  assert.fail('Controller not ready: ' + JSON.stringify(result))
}
switch (process.argv[2]) {
  case 'cancel-empty-delete': {
    const status = await api('status')
    assert.equal(status.configured, false); assert.equal(status.deleting, true)
    const refused = await post('setup', setupChoices, 'Bearer ' + token)
    assert.equal(refused.status, 409); assert.equal(refused.body.error, 'deletion-prepared')
    assert.deepEqual(await api('cancel-delete'), { deleteReady: false })
    assert.equal((await api('status')).deleting, false)
    break
  }
  case 'setup': {
    assert.equal((await api('status')).configured, false)
    await api('setup', setupChoices)
    break
  }
  case 'pair-restart': {
    const before = await ready(); assert.equal(before.rooms, 0)
    const pair = await api('pair')
    assert(pair.qr.includes('<svg')); assert.equal(new URL(pair.link).origin, 'https://kithmoot.app')
    const value = JSON.parse(Buffer.from(new URL(pair.link).hash.split('=')[1], 'base64url'))
    assert.equal(value.node, 'https://node.example'); assert.equal(value.expiresAt, pair.expiresAt); assert(value.code.length > 16)
    await api('pause'); assert.equal((await api('status')).running, false)
    await api('start'); assert.equal((await ready()).rooms, 0)
    break
  }
  case 'delete': {
    assert.deepEqual(await api('prepare-delete'), { deleteReady: true })
    assert.equal((await api('status')).deleting, true)
    assert.deepEqual(await api('cancel-delete'), { deleteReady: false })
    assert.equal((await ready()).deleting, false)
    assert.deepEqual(await api('prepare-delete'), { deleteReady: true })
    break
  }
  default: throw Error('Unknown fixture phase')
}
key.fill(0)
console.log('Private controller fixture phase passed: ' + process.argv[2])
