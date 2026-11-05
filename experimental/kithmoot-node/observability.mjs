// Private, read-only observations. Never return raw command output, paths,
// socket replies, certificate subjects, identities or participant addresses.
import { open, statfs, lstat } from 'node:fs/promises'
import { constants } from 'node:fs'
import { connect } from 'node:net'
import { connect as tlsConnect } from 'node:tls'
import { join } from 'node:path'
import { performance } from 'node:perf_hooks'
import metadata from './package.json' with { type: 'json' }

const integer = value => Number.isSafeInteger(value) && value >= 0 ? value : null
const version = value => typeof value === 'string' && /^[0-9][0-9A-Za-z.+-]{0,63}$/.test(value) ? value : null
export const checkNames = ['local-supervisor', 'HTTPS-profile-and-identity', 'WSS-authentication-challenge', 'local-DNS',
  'storage-reserve', 'STUN-UDP-34790', 'STUN-TCP-34790', 'STUN-TLS-53499', 'STUN-TLS-443']

export function healthReport(report, code, checkedAt) {
  const valid = report?.v === 1 && Array.isArray(report.checks) && report.checks.length <= 32
  const checks = checkNames.map(name => {
    const matches = valid ? report.checks.filter(check => check?.name === name) : []
    return { name, state: matches.length === 1 && typeof matches[0].ok === 'boolean' ? matches[0].ok ? 'passed' : 'failed' : 'unknown' }
  })
  return { checkedAt, version: version(valid ? report.version : null), checks,
    ready: valid && code === 0 && report.localReady === true && checks.every(check => check.state === 'passed') }
}

// Fixed files, bounded reads and no symlinks. This also bounds virtual files
// which report size zero. Failure to obtain a counter is unknown, never zero.
async function smallText(path) {
  const file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW)
  try {
    const buffer = Buffer.alloc(4097), { bytesRead } = await file.read(buffer, 0, buffer.length, 0)
    if (bytesRead > 4096) throw Error('Oversized observation')
    return buffer.subarray(0, bytesRead).toString('utf8').trim()
  } finally { await file.close() }
}
const counter = text => /^(0|[1-9][0-9]*)$/.test(text) ? integer(Number(text)) : null

export function resourceSampler(state, { read = smallText, filesystem = statfs, monotonic = () => performance.now() } = {}) {
  let previous
  return async () => {
    const result = { sampledAt: Date.now(), memoryBytes: null, memoryLimitBytes: null, cpuPercent: null, cpuLimitCores: null, freeBytes: null }
    // Only a private cgroup namespace root is used. On other layouts leave
    // container counters unavailable rather than accidentally reporting a host.
    const group = await read('/proc/self/cgroup').catch(() => '')
    if (group === '0::/') {
      const [memory, limit, cpu, quota] = await Promise.all([
        'memory.current', 'memory.max', 'cpu.stat', 'cpu.max'
      ].map(name => read('/sys/fs/cgroup/' + name).catch(() => '')))
      result.memoryBytes = counter(memory); result.memoryLimitBytes = counter(limit)
      const usage = cpu.match(/^usage_usec ([0-9]+)$/m), current = usage ? counter(usage[1]) : null, at = monotonic()
      if (current !== null && previous && at > previous.at && current >= previous.usage) {
        result.cpuPercent = Math.round((current - previous.usage) / ((at - previous.at) * 10) * 10) / 10
      }
      previous = current === null ? undefined : { usage: current, at }
      const parts = quota.split(' ')
      if (parts.length === 2 && counter(parts[0]) !== null && counter(parts[1]) > 0) result.cpuLimitCores = Number(parts[0]) / Number(parts[1])
    } else previous = undefined
    try { const info = await filesystem(state); result.freeBytes = integer(info.bavail * info.bsize) } catch {}
    return result
  }
}

export async function shelterObservation(state) {
  const path = join(state, 'shelter.sock'), info = await lstat(path)
  if (!info.isSocket() || info.uid !== process.getuid() || info.mode & 0o077) throw Error('Unavailable relay observation')
  return new Promise((resolve, reject) => {
    const socket = connect(path), chunks = []; let length = 0, done = false
    const finish = (error, value) => { if (done) return; done = true; clearTimeout(timer); socket.destroy(); error ? reject(Error('Unavailable relay observation')) : resolve(value) }
    const timer = setTimeout(() => finish(true), 2000)
    socket.once('error', () => finish(true))
    socket.once('connect', () => socket.end('{"v":1,"op":"status"}'))
    socket.on('data', bytes => { length += bytes.length; if (length > 65536) finish(true); else chunks.push(bytes) })
    socket.once('end', () => {
      try {
        const reply = JSON.parse(Buffer.concat(chunks).toString('utf8')), value = reply.result
        if (reply.v !== 1 || reply.ok !== true || typeof value?.leaseActive !== 'boolean' || integer(value.usedBytes) === null) return finish(true)
        finish(false, { responding: true, leaseActive: value.leaseActive, storeBytes: value.usedBytes })
      } catch { finish(true) }
    })
    socket.once('close', () => finish(true))
  })
}

export function certificateObservation(facts) {
  return new Promise(resolve => {
    let done = false
    const finish = validUntil => { if (done) return; done = true; clearTimeout(timer); socket.destroy(); resolve({ validUntil }) }
    const socket = tlsConnect({ host: facts.address, port: 443, servername: facts.host, minVersion: 'TLSv1.2' })
    const timer = setTimeout(() => finish(null), 2000)
    socket.once('error', () => finish(null))
    socket.once('close', () => finish(null))
    socket.once('secureConnect', () => {
      const expiry = Date.parse(socket.getPeerCertificate().valid_to)
      finish(socket.authorized && Number.isFinite(expiry) ? expiry : null)
    })
  })
}

export function dashboardSnapshot({ base, state, doctor, resources, shelter, certificate, startedAt, problem }) {
  const observedAt = Date.now(), configured = base.configured, running = base.running
  const checks = doctor?.checks ?? checkNames.map(name => ({ name, state: 'unknown' }))
  const check = name => checks.find(item => item.name === name)?.state ?? 'unknown'
  const service = (id, label, condition, detail) => ({ id, label, state: !running ? id === 'supervisor' || base.paused ? 'stopped' : 'unknown' : condition, detail })
  return { ...base, ready: running && state?.ready === true && doctor?.ready === true,
    ...(state ? { rooms: state.rooms, devices: state.devices, pending: state.pending, paired: state.paired === true, deleting: base.deleting || state.deleting === true } : {}),
    observedAt,
    services: [
      { id: 'controller', label: 'Archy controls', state: 'responding', version: metadata.version, uptimeSeconds: Math.floor(process.uptime()), detail: 'Private sign-in, setup and node controls.' },
      { ...service('supervisor', 'Room supervisor', state ? state.ready ? 'responding' : 'attention' : 'unknown', 'Admitted-device access and backend reconciliation.'), version: doctor?.version ?? null,
        uptimeSeconds: running && startedAt ? Math.max(0, Math.floor((performance.now() - startedAt) / 1000)) : null },
      service('spry', 'Spry call relay', check('STUN-UDP-34790') === 'passed' && check('STUN-TCP-34790') === 'passed' ? 'responding' : check('STUN-UDP-34790') === 'failed' || check('STUN-TCP-34790') === 'failed' ? 'attention' : 'unknown', 'Local STUN responses. This does not prove an authenticated call can connect.'),
      service('shelter', 'Shelter message relay', shelter?.responding ? 'responding' : 'unknown', 'Private relay control response. Room messages remain encrypted.')
    ],
    connections: { controlsPort: 3753, httpsPort: 443, turnUdpTcpPort: 34790, turnTlsPort: 53499, turnTls443Port: 443,
      checkedAt: doctor?.checkedAt ?? null, checks, certificateValidUntil: certificate?.validUntil ?? null, external: 'not-measured' },
    usage: { ...resources, storeBytes: running ? shelter?.storeBytes ?? null : null, bandwidthBytesPerSecond: null, allocations: null },
    diagnostics: { problem: problem ?? null, checkedAt: doctor?.checkedAt ?? null,
      // No arbitrary report strings, logs or raw exception messages cross this boundary.
      checks: configured && running ? checks : [], external: 'not-measured' }
  }
}
