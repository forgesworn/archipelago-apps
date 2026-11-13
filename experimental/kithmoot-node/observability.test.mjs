import { test } from 'node:test'
import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { createServer } from 'node:net'
import { mkdtemp, chmod, symlink, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { checkNames, healthReport, resourceSampler, shelterObservation, dashboardSnapshot } from './observability.mjs'
import { supportReport, dashboard } from './dashboard.mjs'
import { NodeProcess } from './server.mjs'

const goodDoctor = () => ({ v: 1, version: '0.1.0-rc.1', localReady: true, checks: checkNames.map(name => ({ name, ok: true })) })
const status = () => ({ v: 1, ready: true, rooms: 2, devices: 5, pending: 1, paired: true })
const base = { configured: true, running: true, host: 'node.example', limits: { maxRooms: 4, aggregateBytesPerSecond: 2000000, maxBytes: 1073741824, minFreeBytes: 2147483648 } }

test('health never trusts a summary bit over missing, duplicate, failed or unknown checks', () => {
  assert.equal(healthReport(goodDoctor(), 0, 1).ready, true)
  for (const report of [null, { ...goodDoctor(), v: 2 }, { ...goodDoctor(), checks: [] },
    { ...goodDoctor(), checks: [...goodDoctor().checks, { name: checkNames[0], ok: true }] },
    { ...goodDoctor(), checks: goodDoctor().checks.map((value, index) => index ? value : { ...value, ok: 'true' }) },
    { ...goodDoctor(), checks: goodDoctor().checks.map((value, index) => index ? value : { ...value, ok: false }) }]) {
    assert.equal(healthReport(report, 0, 1).ready, false)
  }
  assert.equal(healthReport(goodDoctor(), 1, 1).ready, false)
  const report = healthReport({ ...goodDoctor(), version: '/secret/key', note: 'token=PRIVATE', checks: [...goodDoctor().checks, { name: 'PRIVATE', ok: false }] }, 0, 1)
  assert.equal(report.version, null); assert(!JSON.stringify(report).includes('PRIVATE'))
})

test('container metrics distinguish first sample, cumulative CPU, unknown counters and host cgroups', async () => {
  let at = 1000, usage = 1000000, group = '0::/'
  const reads = []
  const sample = resourceSampler('/owned-state', {
    monotonic: () => at, filesystem: async path => { assert.equal(path, '/owned-state'); return { bavail: 100, bsize: 4096 } },
    read: async path => { reads.push(path); return ({ '/proc/self/cgroup': group, '/sys/fs/cgroup/memory.current': '1024',
      '/sys/fs/cgroup/memory.max': '268435456', '/sys/fs/cgroup/cpu.stat': 'usage_usec ' + usage, '/sys/fs/cgroup/cpu.max': '200000 100000' })[path] }
  })
  const first = await sample(); assert.equal(first.cpuPercent, null); assert.equal(first.memoryBytes, 1024); assert.equal(first.freeBytes, 409600); assert.equal(first.cpuLimitCores, 2)
  at += 1000; usage += 1500000
  assert.equal((await sample()).cpuPercent, 150)
  usage = 0; at += 1000; assert.equal((await sample()).cpuPercent, null)
  group = '0::/host/user.slice'; reads.length = 0
  const host = await sample(); assert.equal(host.memoryBytes, null); assert.equal(host.cpuPercent, null); assert.deepEqual(reads, ['/proc/self/cgroup'])
  const unavailable = await resourceSampler('/state', { read: async () => { throw Error('PRIVATE') }, filesystem: async () => { throw Error('PRIVATE') } })()
  assert.equal(unavailable.freeBytes, null); assert.equal(unavailable.memoryBytes, null); assert(!JSON.stringify(unavailable).includes('PRIVATE'))
})

test('private Shelter observation sends only status and exports only aggregate storage and lease state', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'node-dashboard-')), path = join(directory, 'shelter.sock')
  let reply = { v: 1, ok: true, result: { usedBytes: 1234, leaseActive: true, room: 'PRIVATE', key: 'PRIVATE' } }, requests = []
  const server = createServer({ allowHalfOpen: true }, socket => {
    let body = ''; socket.on('data', bytes => { body += bytes }); socket.on('end', () => { requests.push(JSON.parse(body)); socket.end(JSON.stringify(reply)) })
  })
  await new Promise(resolve => server.listen(path, resolve)); await chmod(path, 0o600)
  t.after(async () => { await new Promise(resolve => server.close(resolve)); await rm(directory, { recursive: true, force: true }) })
  assert.deepEqual(await shelterObservation(directory), { responding: true, leaseActive: true, storeBytes: 1234 })
  assert.deepEqual(requests, [{ v: 1, op: 'status' }])
  for (const invalid of [{ v: 1, ok: true, result: { usedBytes: -1, leaseActive: true } }, { v: 1, ok: false, result: reply.result }]) {
    reply = invalid; await assert.rejects(shelterObservation(directory), /Unavailable relay observation/)
  }
  await chmod(path, 0o666); await assert.rejects(shelterObservation(directory)); await chmod(path, 0o600)
  const alias = await mkdtemp(join(tmpdir(), 'node-dashboard-alias-')); t.after(() => rm(alias, { recursive: true, force: true }))
  await symlink(path, join(alias, 'shelter.sock')); await assert.rejects(shelterObservation(alias))
})

test('dashboard preserves local versus external evidence, access counts, limits and redacted export', () => {
  const snapshot = dashboardSnapshot({ base, state: { ...status(), roomKeys: 'PRIVATE' }, doctor: healthReport(goodDoctor(), 0, 1),
    resources: { memoryBytes: 0, freeBytes: 0 }, shelter: { responding: true, storeBytes: 0 } })
  assert.equal(snapshot.ready, true); assert.equal(snapshot.devices, 5); assert.equal(snapshot.usage.storeBytes, 0)
  assert.equal(snapshot.connections.external, 'not-measured'); assert.equal(snapshot.usage.allocations, null)
  assert(!supportReport({ ...snapshot, token: 'PRIVATE', pairing: 'PRIVATE' }).includes('PRIVATE'))
  assert.match(dashboard(snapshot, 'overview'), /offline devices/); assert.match(dashboard(snapshot, 'overview'), /Pending operations/)
  assert.match(dashboard(snapshot, 'usage'), /0 B/); assert.match(dashboard(snapshot, 'usage'), /Relay statistics are unavailable/)
  assert.match(dashboard(snapshot, 'settings'), /16 Mbit\/s/); assert.match(dashboard(snapshot, 'settings'), /Pause the node from Overview before changing limits/)
  assert.match(dashboard({ ...snapshot, host: '<img src=x onerror=alert(1)>' }, 'connections'), /&lt;img/)
  const paused = dashboardSnapshot({ base: { ...base, running: false, paused: true }, resources: {} })
  assert.equal(paused.ready, false); assert.equal(paused.usage.storeBytes, null); assert.equal(paused.devices, undefined)
  assert(paused.services.slice(1).every(service => service.state === 'stopped'))
})

async function processFixture(t, command) {
  const directory = await mkdtemp(join(tmpdir(), 'node-dashboard-process-'))
  await writeFile(join(directory, 'node.json'), JSON.stringify({ ...base.limits, host: 'node.example', relayIp: '1.2.3.4', tlsGate: true, deskPort: 3750, spryPort: 3751, shelterPort: 3752 }), { mode: 0o600 })
  const children = [], node = new NodeProcess({ host: 'node.example', address: '1.2.3.4' }, {}, directory, {
    command, observe: async () => [{ sampledAt: 1, memoryBytes: 1024 }, { responding: true, storeBytes: 42 }, { validUntil: 2000000000000 }],
    launch: () => { const child = new EventEmitter(); child.exitCode = null; children.push(child); return child }
  })
  t.after(async () => { for (const child of children) { child.exitCode = 0; child.emit('exit', 0) }; await rm(directory, { recursive: true, force: true }) })
  await node.start(); return { node, children }
}

test('concurrent status polls share one doctor and failures preserve recovery details without secrets', async t => {
  const calls = [], { node } = await processFixture(t, async op => {
    calls.push(op); return { code: 0, output: JSON.stringify(op === 'status' ? { ok: true, result: status() } : goodDoctor()) }
  })
  const first = node.status(), second = node.status(); assert.equal(first, second)
  const result = await first
  assert.equal(result.ready, true); assert.equal(result.usage.storeBytes, 42); assert.equal(result.services.length, 4)
  assert.deepEqual(calls, ['status', 'doctor'])
  await node.status(); assert.deepEqual(calls, ['status', 'doctor'])
  const failed = await processFixture(t, async () => { throw Error('PRIVATE SECRET /saved/path') })
  const degraded = await failed.node.status()
  assert.equal(degraded.ready, false); assert.equal(degraded.configured, true); assert.deepEqual(degraded.limits, base.limits)
  assert.equal(degraded.diagnostics.problem, 'supervisor-unavailable'); assert.equal(degraded.services[1].state, 'unknown')
  assert(!JSON.stringify(degraded).includes('PRIVATE')); assert.equal(degraded.rooms, undefined)
})

test('an in-flight doctor from an exited supervisor cannot make a replacement ready', async t => {
  let release, entered, doctors = 0
  const waiting = new Promise(resolve => { entered = resolve })
  const { node, children } = await processFixture(t, async op => {
    if (op === 'doctor' && ++doctors === 1) { entered(); await new Promise(resolve => { release = resolve }) }
    return { code: 0, output: JSON.stringify(op === 'status' ? { ok: true, result: status() } : goodDoctor()) }
  })
  const pending = node.status(); await waiting
  children[0].exitCode = 1; children[0].emit('exit', 1); await node.start(); release()
  assert.equal((await pending).ready, false)
  assert.equal((await node.status()).ready, true); assert.equal(doctors, 2)
})
