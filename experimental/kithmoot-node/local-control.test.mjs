import { test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { connect } from 'node:net'
import { NodeProcess } from './server.mjs'
import { startControllerControl, requestControllerDeletion } from './local-control.mjs'

test('private host command waits for the asynchronous deletion freeze before acknowledging', async t => {
  const state = mkdtempSync(join(tmpdir(), 'node-host-control-')); let frozen = false
  const control = await startControllerControl(state, { prepareDelete: async () => {
    await new Promise(resolve => setTimeout(resolve, 20)); frozen = true; return { deleteReady: true }
  } })
  t.after(async () => { await control.close(); rmSync(state, { recursive: true }) })
  assert.equal(statSync(join(state, 'operator.sock')).mode & 0o777, 0o600)
  assert.deepEqual(await requestControllerDeletion(state), { ok: true, result: { deleteReady: true } })
  assert.equal(frozen, true)
})

test('unconfigured deletion through the host socket blocks setup across a controller restart', async t => {
  const state = mkdtempSync(join(tmpdir(), 'node-host-empty-'))
  const node = new NodeProcess({ host: 'node.example', address: '1.2.3.4' }, {}, state)
  const control = await startControllerControl(state, node)
  t.after(async () => { await control.close(); rmSync(state, { recursive: true }) })
  assert.equal((await requestControllerDeletion(state)).ok, true)
  const restarted = new NodeProcess(node.facts, {}, state)
  assert.equal((await restarted.status()).deleting, true)
  await assert.rejects(restarted.setup({ hostedAwayFromHome: true, maxRooms: 4, maxBytes: 268435456, minFreeBytes: 1073741824, aggregateBytesPerSecond: 1000000 }), /deletion-prepared/)
})

test('a live controller and an unrelated file cannot be replaced by a second socket listener', async t => {
  const state = mkdtempSync(join(tmpdir(), 'node-host-exclusive-'))
  const control = await startControllerControl(state, { prepareDelete: async () => ({ deleteReady: true }) })
  t.after(() => rmSync(state, { recursive: true }))
  try {
    await assert.rejects(startControllerControl(state, {}), /already running/)
    assert.equal((await requestControllerDeletion(state)).result.deleteReady, true)
  } finally { await control.close() }
  writeFileSync(join(state, 'operator.sock'), 'preserve this file', { mode: 0o600 })
  await assert.rejects(startControllerControl(state, {}), /Unsafe controller socket/)
})

test('unknown local operations cannot prepare deletion', async t => {
  const state = mkdtempSync(join(tmpdir(), 'node-host-ops-')); let calls = 0
  const control = await startControllerControl(state, { prepareDelete: async () => { calls++; return { deleteReady: true } } })
  t.after(async () => { await control.close(); rmSync(state, { recursive: true }) })
  const answer = await new Promise((resolve, reject) => {
    const socket = connect(join(state, 'operator.sock')); let text = ''
    socket.on('error', reject); socket.once('connect', () => socket.end('{"op":"delete-files"}'))
    socket.on('data', bytes => { text += bytes }); socket.once('end', () => { socket.destroy(); resolve(JSON.parse(text)) })
  })
  assert.equal(answer.ok, false); assert.equal(calls, 0)
})
