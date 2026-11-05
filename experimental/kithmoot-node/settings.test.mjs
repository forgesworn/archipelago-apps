import { test } from 'node:test'
import assert from 'node:assert/strict'
import { DatabaseSync } from 'node:sqlite'
import { mkdtempSync, writeFileSync, readFileSync, rmSync, mkdirSync, truncateSync, symlinkSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { NodeProcess } from './server.mjs'
import { configurationRevision, readPrivate } from './private-state.mjs'
import { settingsInformation, validateSavedUsage, changeSavedSettings } from './settings.mjs'

const limits = { maxRooms: 4, aggregateBytesPerSecond: 2000000, maxBytes: 1073741824, minFreeBytes: 1073741824 }
function fixture(t, rooms = 2) {
  const state = mkdtempSync(join(tmpdir(), 'node-limits-'))
  t.after(() => rmSync(state, { recursive: true, force: true }))
  const configuration = { v: 1, host: 'node.example', hosting: 'archy', relayIp: '1.2.3.4', deskPort: 3750, spryPort: 3751, shelterPort: 3752,
    spryBinary: '/fixture/bin/spry-node', tlsGate: true, ...limits }
  writeFileSync(join(state, 'node.json'), JSON.stringify(configuration), { mode: 0o600 })
  writeFileSync(join(state, 'ui-paused'), '{"v":1}', { mode: 0o600 })
  writeFileSync(join(state, 'service.key'), 'PRIVATE-UNCHANGED', { mode: 0o600 })
  const ledger = new DatabaseSync(join(state, 'ledger.sqlite'))
  ledger.exec("PRAGMA user_version=1;CREATE TABLE meta(key TEXT,value TEXT);INSERT INTO meta VALUES('owner','PRIVATE-OWNER');CREATE TABLE rooms(room TEXT);CREATE TABLE operations(id TEXT,phase TEXT);")
  for (let n = 0; n < rooms; n++) ledger.prepare('INSERT INTO rooms VALUES(?)').run('PRIVATE-ROOM-' + n)
  ledger.exec("INSERT INTO operations VALUES('old','done')");ledger.close()
  // sqlite's default mode is made owner-only as in the real node volume.
  const { chmodSync } = process.getBuiltinModule('node:fs'); chmodSync(join(state, 'ledger.sqlite'), 0o600)
  mkdirSync(join(state, 'rooms'), { mode: 0o700 }); writeFileSync(join(state, 'rooms', 'events.sqlite'), 'ENCRYPTED-ROOM-DATA', { mode: 0o600 })
  const node = new NodeProcess({ host: 'node.example', address: '1.2.3.4' }, {}, state)
  return { state, node, configuration, revision: configurationRevision(configuration), saved: () => readPrivate(join(state, 'node.json')),
    ledger: sql => { const db = new DatabaseSync(join(state, 'ledger.sqlite')); try { db.exec(sql) } finally { db.close() } } }
}

test('paused limits save atomically, preserve other configuration/keys/rooms, and restore without starting services', async t => {
  const f = fixture(t), beforeLedger = readFileSync(join(f.state, 'ledger.sqlite')), next = { ...limits, maxRooms: 8, aggregateBytesPerSecond: 5000000 }
  const result = await f.node.changeSettings({ revision: f.revision, limits: next })
  assert.equal(result.paused, true); assert.notEqual(result.revision, f.revision)
  assert.deepEqual(f.saved(), { ...f.configuration, ...next })
  assert.equal(readFileSync(join(f.state, 'service.key'), 'utf8'), 'PRIVATE-UNCHANGED')
  assert.deepEqual(readFileSync(join(f.state, 'ledger.sqlite')), beforeLedger)
  assert.equal(readFileSync(join(f.state, 'rooms', 'events.sqlite'), 'utf8'), 'ENCRYPTED-ROOM-DATA')
  assert.equal(statSync(join(f.state, 'node.json')).mode & 0o777, 0o600)
  assert.equal(statSync(join(f.state, 'ui-settings-backup.json')).mode & 0o777, 0o600)
  const info = settingsInformation(f.state, f.saved(), false, true, false)
  assert.deepEqual(info.previous, limits); assert(info.editable); assert(!JSON.stringify(info).includes('PRIVATE'))
  const restored = await f.node.changeSettings({ revision: result.revision }, true)
  assert.equal(restored.revision, f.revision); assert.deepEqual(f.saved(), f.configuration)
  assert.equal(settingsInformation(f.state, f.saved(), false, true, false).previous, null)
  assert.equal((await f.node.status()).running, false)
})

test('two tabs cannot overwrite a changed revision; rejected or malformed changes preserve the last configuration', async t => {
  const f = fixture(t)
  for (const invalid of [{ revision: f.revision, limits: { ...limits, maxRooms: 64 } }, { revision: f.revision, limits: { ...limits, spryBinary: '/elsewhere' } },
    { revision: f.revision, limits, restart: true }, { revision: 'bad', limits }, { revision: f.revision, limits: [] }]) {
    await assert.rejects(f.node.changeSettings(invalid), /invalid-settings/); assert.deepEqual(f.saved(), f.configuration)
  }
  const next = { ...limits, maxRooms: 8 }
  const results = await Promise.allSettled([f.node.changeSettings({ revision: f.revision, limits: next }), f.node.changeSettings({ revision: f.revision, limits: { ...limits, maxRooms: 1 } })])
  assert.equal(results[0].status, 'fulfilled'); assert.equal(results[1].status, 'rejected'); assert.match(results[1].reason.message, /settings-changed/)
  assert.equal(f.saved().maxRooms, 8)
})

test('settings cannot change without a deliberate pause, during deletion or unfinished room operations', async t => {
  const f = fixture(t), request = { revision: f.revision, limits: { ...limits, maxRooms: 8 } }
  rmSync(join(f.state, 'ui-paused'))
  await assert.rejects(f.node.changeSettings(request), /pause-before-settings/)
  writeFileSync(join(f.state, 'ui-paused'), '{"v":1}', { mode: 0o600 })
  await assert.rejects(changeSavedSettings(f.state, request, true), /pause-before-settings/)
  f.ledger("INSERT INTO meta VALUES('deleting','1')")
  await assert.rejects(f.node.changeSettings(request), /deletion-prepared/)
  f.ledger("DELETE FROM meta WHERE key='deleting'; INSERT INTO operations VALUES('unfinished','teardown')")
  await assert.rejects(f.node.changeSettings(request), /settings-operations-pending/)
  assert.deepEqual(f.saved(), f.configuration)
})

test('room count, conservative message-file footprint and free disk reserve bound reductions', async t => {
  const f = fixture(t)
  await assert.rejects(f.node.changeSettings({ revision: f.revision, limits: { ...limits, maxRooms: 1 } }), /settings-room-limit-too-small/)
  const path = join(f.state, 'rooms', 'large.sqlite');writeFileSync(path, '', { mode: 0o600 });truncateSync(path, 268435457)
  await assert.rejects(f.node.changeSettings({ revision: f.revision, limits: { ...limits, maxBytes: 268435456 } }), /settings-storage-limit-too-small/)
  rmSync(path)
  await assert.rejects(validateSavedUsage(f.state, limits, { filesystem: async () => ({ bavail: 1, bsize: 4096 }) }), /settings-disk-reserve-unavailable/)
  assert.deepEqual(f.saved(), f.configuration)
})

test('unknown schema, missing storage and symlinked ledger or store fail closed without following host paths', async t => {
  const f = fixture(t), request = { revision: f.revision, limits }
  f.ledger('PRAGMA user_version=2')
  await assert.rejects(f.node.changeSettings(request), /settings-review-required/)
  f.ledger('PRAGMA user_version=1')
  rmSync(join(f.state, 'rooms'), { recursive: true })
  await assert.rejects(f.node.changeSettings(request), /settings-usage-unavailable/)
  symlinkSync(tmpdir(), join(f.state, 'rooms'))
  await assert.rejects(f.node.changeSettings(request), /settings-usage-unavailable/)
  rmSync(join(f.state, 'ledger.sqlite'));symlinkSync(join(f.state, 'service.key'), join(f.state, 'ledger.sqlite'))
  await assert.rejects(f.node.changeSettings(request), /settings-usage-unavailable/)
})

test('an interrupted atomic save/restore record is reconciled, but unrelated backup or host changes require review', t => {
  const f = fixture(t)
  writeFileSync(join(f.state, 'ui-settings-backup.json'), JSON.stringify({ v: 1, previous: f.configuration, appliedRevision: 'a'.repeat(64) }), { mode: 0o600 })
  assert(settingsInformation(f.state, f.configuration, false, true, false).editable)
  const changed = { ...f.configuration, host: 'other.example' }
  const info = settingsInformation(f.state, changed, false, true, false)
  assert.equal(info.editable, false); assert.equal(info.issue, 'settings-review-required')
  assert.equal(settingsInformation(f.state, f.configuration, true, true, false).editable, false)
})
