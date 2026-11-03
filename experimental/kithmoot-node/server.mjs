import { createServer } from 'node:http'
import { createHash, randomBytes } from 'node:crypto'
import { spawn } from 'node:child_process'
import { existsSync, lstatSync, fstatSync, chmodSync, openSync, closeSync, readFileSync, writeFileSync, renameSync, fsyncSync, constants, rmSync, readdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { performance } from 'node:perf_hooks'
import { connect } from 'node:net'
import { verifyEvent } from 'nostr-tools/pure'
import QRCode from 'qrcode'

const KEY = /^[a-f0-9]{64}$/
const STATE = '/var/lib/kithmoot-node'
const BASE = '/opt/kithmoot-node/current'
const SESSION_IDLE_MS = 30 * 60 * 1000
const SESSION_MAX_MS = 8 * 60 * 60 * 1000
const hash = value => createHash('sha256').update(value).digest('hex')
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))
class Refused extends Error { constructor(status, code) { super(code); this.status = status } }

export function ownerKeys(value) {
  const keys = String(value ?? '').split(',').map(key => key.trim()).filter(Boolean)
  if (!keys.length || keys.length > 64 || keys.some(key => !KEY.test(key))) throw Error('Host identities are unavailable')
  return new Set(keys)
}

export function choices(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).sort().join() !== 'aggregateBytesPerSecond,hostedAwayFromHome,maxBytes,maxRooms,minFreeBytes'
    || value.hostedAwayFromHome !== true || ![1, 4, 8].includes(value.maxRooms)
    || ![1_000_000, 2_000_000, 5_000_000].includes(value.aggregateBytesPerSecond)
    || ![268435456, 1073741824, 4294967296].includes(value.maxBytes)
    || ![1073741824, 2147483648].includes(value.minFreeBytes)) throw new Refused(422, 'invalid-setup')
  return structuredClone(value)
}

function readPrivate(path) {
  const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW)
  try {
    const info = fstatSync(fd)
    if (!info.isFile() || info.uid !== process.getuid() || info.mode & 0o077 || info.size > 65536) throw Error('Unsafe saved node settings')
    return JSON.parse(readFileSync(fd, 'utf8'))
  } finally { closeSync(fd) }
}
function savePrivate(path, value) {
  const temporary = path + '.new-' + randomBytes(8).toString('hex')
  const fd = openSync(temporary, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | constants.O_NOFOLLOW, 0o600)
  try { writeFileSync(fd, JSON.stringify(value) + '\n'); fsyncSync(fd) } finally { closeSync(fd) }
  try { renameSync(temporary, path) } finally { rmSync(temporary, { force: true }) }
  const parent = openSync(dirname(path), constants.O_RDONLY); try { fsyncSync(parent) } finally { closeSync(parent) }
}
function deletionPrepared(state) {
  let value
  try { value = readPrivate(join(state, 'ui-delete-prepared')) } catch (error) { if (error.code === 'ENOENT') return false; throw error }
  if (!value || value.v !== 1 || Object.keys(value).length !== 1) throw Error('Invalid saved deletion state')
  return true
}

function configuration(facts, limits) {
  return { v: 1, host: facts.host, hosting: 'archy', relayIp: facts.address,
    aggregateBytesPerSecond: limits.aggregateBytesPerSecond, maxBytes: limits.maxBytes, minFreeBytes: limits.minFreeBytes,
    maxRooms: limits.maxRooms, origins: ['https://kithmoot.app', 'https://www.kithmoot.app', 'https://kithmoot.forgesworn.dev'],
    spryBinary: BASE + '/bin/spry-node', shelterBinary: BASE + '/bin/bothyd',
    deskPort: 3750, spryPort: 3751, shelterPort: 3752, tlsGate: true,
    turnPorts: { udpTcp: 34790, tls: 53499 }, relayPortFirst: 49192 }
}

export class NodeProcess {
  #child
  #queue = Promise.resolve()
  #status
  #doctor
  constructor(facts, secrets, state = STATE) {
    this.facts = facts; this.secrets = secrets; this.state = state
    const info = lstatSync(state)
    if (!info.isDirectory() || info.uid !== process.getuid() || info.mode & 0o022) throw Error('Node data ownership needs attention')
    chmodSync(state, 0o700)
  }
  #serial(work) { const result = this.#queue.then(work); this.#queue = result.catch(() => {}); return result }
  #neverRan() {
    if (this.#child) return false
    const allowed = new Set(['node.json', 'initialising', 'service.key', 'turn.secret', 'state.salt', 'ui-configuration.json', 'ui-paused', 'ui-delete-prepared', 'operator.sock'])
    return readdirSync(this.state).every(name => {
      if (!allowed.has(name) && !/^(?:ui-configuration\.json|ui-paused|ui-delete-prepared)\.new-[a-f0-9]{16}$/.test(name)) return false
      const info = lstatSync(join(this.state, name))
      return info.uid === process.getuid() && !(info.mode & 0o077) && info.nlink === 1
        && (name === 'operator.sock' ? info.isSocket() : info.isFile() && info.size <= 65536)
    })
  }
  async #command(op, extra = [], timeout = 20000) {
    return new Promise((resolve, reject) => {
      const child = spawn(BASE + '/kithmoot-node', [op, '--state', this.state, ...extra], {
        env: { PATH: '/usr/bin:/bin', ...this.secrets }, detached: true, stdio: ['ignore', 'pipe', 'ignore'] })
      let output = ''; const kill = () => { try { process.kill(-child.pid, 'SIGKILL') } catch {} }
      const timer = setTimeout(() => { kill(); reject(new Refused(503, 'node-unavailable')) }, timeout)
      child.stdout.on('data', bytes => { output += bytes.toString(); if (output.length > 65536) { kill(); reject(new Refused(503, 'invalid-node-reply')) } })
      child.once('error', () => { clearTimeout(timer); reject(new Refused(503, 'node-unavailable')) })
      child.once('exit', code => { clearTimeout(timer); resolve({ code, output }) })
    })
  }
  async boot() {
    if (deletionPrepared(this.state)) return
    if (existsSync(join(this.state, 'node.json')) && !existsSync(join(this.state, 'initialising')) && !existsSync(join(this.state, 'ui-paused'))) await this.start()
  }
  start() {
    return this.#serial(async () => {
      if (deletionPrepared(this.state)) throw new Refused(409, 'deletion-prepared')
      if (this.#child && this.#child.exitCode === null) return
      if (!existsSync(join(this.state, 'node.json'))) throw new Refused(409, 'setup-required')
      const saved = readPrivate(join(this.state, 'node.json'))
      if (saved.host !== this.facts.host || saved.relayIp !== this.facts.address || !saved.tlsGate
        || saved.deskPort !== 3750 || saved.spryPort !== 3751 || saved.shelterPort !== 3752) throw new Refused(409, 'configuration-review-required')
      rmSync(join(this.state, 'ui-paused'), { force: true })
      this.#child = spawn(BASE + '/kithmoot-node', ['run', '--state', this.state], {
        env: { PATH: '/usr/bin:/bin', ...this.secrets }, detached: true, stdio: 'ignore' })
      const current = this.#child
      current.once('error', () => { if (this.#child === current) this.#child = undefined })
      current.once('exit', () => { if (this.#child === current) this.#child = undefined; this.#status = undefined; this.#doctor = undefined })
      await sleep(100)
      if (!this.#child || this.#child.exitCode !== null) throw new Refused(503, 'node-unavailable')
      this.#status = undefined; this.#doctor = undefined
    })
  }
  setup(value) {
    return this.#serial(async () => {
      if (deletionPrepared(this.state)) throw new Refused(409, 'deletion-prepared')
      if (existsSync(join(this.state, 'node.json')) && !existsSync(join(this.state, 'initialising'))) throw new Refused(409, 'already-configured')
      if (!this.#neverRan()) throw new Refused(409, 'configuration-review-required')
      const limits = choices(value), path = join(this.state, 'ui-configuration.json')
      const proposed = configuration(this.facts, limits)
      if (existsSync(path) && JSON.stringify(readPrivate(path)) !== JSON.stringify(proposed)) throw new Refused(409, 'retry-saved-setup')
      if (!existsSync(path)) savePrivate(path, proposed)
      const op = existsSync(join(this.state, 'initialising')) ? 'resume-init' : 'init'
      const reply = await this.#command(op, ['--configuration', path])
      if (reply.code !== 0) throw new Refused(503, 'setup-incomplete')
      return { configured: true }
    }).then(async value => { await this.start(); return value })
  }
  async status() {
    const configured = existsSync(join(this.state, 'node.json')) && !existsSync(join(this.state, 'initialising'))
    const setupPending = existsSync(join(this.state, 'ui-configuration.json')) && !configured
    const base = { v: 1, host: this.facts.host, configured, setupPending, running: !!this.#child, deleting: deletionPrepared(this.state),
      ...(configured || setupPending ? { limits: (() => { const value = readPrivate(join(this.state, configured ? 'node.json' : 'ui-configuration.json')); return {
        maxRooms: value.maxRooms, maxBytes: value.maxBytes, minFreeBytes: value.minFreeBytes, aggregateBytesPerSecond: value.aggregateBytesPerSecond } })() } : {}) }
    if (!configured || !this.#child) return { ...base, ready: false }
    if (!this.#status || this.#status.until < performance.now()) {
      const reply = await this.#command('status'); let result
      try { result = JSON.parse(reply.output) } catch { throw new Refused(503, 'node-unavailable') }
      if (result.ok !== true || !result.result || result.result.v !== 1) throw new Refused(503, 'node-unavailable')
      this.#status = { until: performance.now() + 2000, result: result.result }
    }
    const state = this.#status.result
    for (const field of ['rooms', 'devices', 'pending']) if (!Number.isSafeInteger(state[field]) || state[field] < 0) throw new Refused(503, 'invalid-node-reply')
    if (state.ready && (!this.#doctor || this.#doctor.until < performance.now())) {
      const reply = await this.#command('doctor', [], 45000); let report
      try { report = JSON.parse(reply.output) } catch { report = undefined }
      this.#doctor = { until: performance.now() + 15000, ready: reply.code === 0 && report?.localReady === true }
    }
    return { ...base, rooms: state.rooms, devices: state.devices, pending: state.pending, paired: state.paired === true,
      deleting: state.deleting === true, ready: state.ready === true && this.#doctor?.ready === true }
  }
  async pair() {
    return this.#serial(async () => {
      const status = await this.status()
      if (!status.ready || status.deleting) throw new Refused(409, 'node-not-ready')
      // The terminal command deliberately refuses pipes. The same private local
      // socket serves this authenticated UI without writing its secret to logs.
      const reply = await localControl(this.state, 'pair'), value = reply.result
      const now = Math.floor(Date.now() / 1000)
      if (reply.ok !== true || !value || typeof value.code !== 'string' || value.code.length > 256
        || !/^[A-Za-z0-9_-]+$/.test(value.code) || !Number.isSafeInteger(value.expiresAt)
        || value.expiresAt <= now || value.expiresAt > now + 360) throw new Refused(503, 'invalid-pairing-reply')
      const link = 'https://kithmoot.app/j/#kithmoot-node=' + Buffer.from(JSON.stringify({ v: 1, node: 'https://' + this.facts.host, code: value.code, expiresAt: value.expiresAt })).toString('base64url')
      return { link, expiresAt: value.expiresAt,
        qr: await QRCode.toString(link, { type: 'svg', errorCorrectionLevel: 'M', margin: 4, width: 256 }) }
    })
  }
  async prepareDelete() {
    return this.#serial(async () => {
      // Before the first runtime start there can be no admitted room. Freeze
      // setup on the same serial queue, including across controller restarts.
      // Any runtime database, unknown file or changed ownership refuses this
      // path; a previously started node must answer its normal durable check.
      if (!this.#child) {
        if (!this.#neverRan()) throw new Refused(409, 'close-rooms-first')
        savePrivate(join(this.state, 'ui-delete-prepared'), { v: 1 })
        return { deleteReady: true }
      }
      const reply = await this.#command('prepare-delete'); let value
      try { value = JSON.parse(reply.output) } catch {}
      if (reply.code !== 0 || value?.ok !== true || value.result?.deleteReady !== true) throw new Refused(409, 'close-rooms-first')
      this.#status = undefined
      return { deleteReady: true }
    })
  }
  async cancelDelete() {
    return this.#serial(async () => {
      if (deletionPrepared(this.state)) {
        if (!this.#neverRan()) throw new Refused(409, 'configuration-review-required')
        rmSync(join(this.state, 'ui-delete-prepared'))
        return { deleteReady: false }
      }
      const reply = await this.#command('cancel-delete'); let value
      try { value = JSON.parse(reply.output) } catch {}
      if (reply.code !== 0 || value?.ok !== true || value.result?.deleteReady !== false) throw new Refused(503, 'node-unavailable')
      this.#status = undefined
      return { deleteReady: false }
    })
  }
  stop(persist = true) {
    return this.#serial(async () => {
      if (persist) savePrivate(join(this.state, 'ui-paused'), { v: 1 })
      const child = this.#child
      if (child) {
        try { process.kill(-child.pid, 'SIGTERM') } catch {}
        for (let i = 0; i < 50 && child.exitCode === null; i++) await sleep(100)
        if (child.exitCode === null) { try { process.kill(-child.pid, 'SIGKILL') } catch {} }
        this.#child = undefined
      }
      this.#status = undefined; this.#doctor = undefined
      return { paused: true }
    })
  }
}

function localControl(state, op) {
  return new Promise((resolve, reject) => {
    const socket = connect(join(state, 'node.sock')); let output = ''
    const refuse = () => { socket.destroy(); reject(new Refused(503, 'node-unavailable')) }
    socket.setTimeout(4000, refuse); socket.once('error', refuse)
    socket.once('connect', () => socket.end(JSON.stringify({ op })))
    socket.on('data', bytes => { output += bytes.toString(); if (output.length > 65536) refuse() })
    socket.once('end', () => { socket.destroy(); try { resolve(JSON.parse(output)) } catch { reject(new Refused(503, 'invalid-node-reply')) } })
  })
}

export function createController({ owners, hosts, node, publicDirectory, now = () => Date.now(), monotonic = () => performance.now() }) {
  const nonces = new Map(), sessions = new Map()
  const allowedHosts = new Set(hosts.map(value => value.toLowerCase()))
  let requests = 0, rate = { until: 0, count: 0 }
  const json = (response, status, value) => { response.writeHead(status, { 'Content-Type': 'application/json' }); response.end(JSON.stringify(value)) }
  function proof(request, path, body) {
    const header = request.headers.authorization
    if (typeof header !== 'string' || header.length > 12000 || !/^Nostr [A-Za-z0-9+/]+={0,2}$/.test(header)) throw new Refused(401, 'sign-in-required')
    let event
    try { event = JSON.parse(Buffer.from(header.slice(6), 'base64').toString('utf8')) } catch { throw new Refused(401, 'invalid-proof') }
    const seconds = Math.floor(now() / 1000)
    if (!event || Object.keys(event).length !== 7 || !owners.has(event.pubkey) || event.kind !== 27235 || event.content !== ''
      || !Number.isSafeInteger(event.created_at) || event.created_at < seconds - 60 || event.created_at > seconds + 30
      || !Array.isArray(event.tags) || event.tags.length !== 4 || event.tags.some(tag => !Array.isArray(tag) || tag.length !== 2 || tag.some(value => typeof value !== 'string')))
      throw new Refused(403, 'host-identity-required')
    const tags = new Map(event.tags)
    if (tags.size !== 4 || tags.get('method') !== 'POST' || tags.get('payload') !== hash(body)) throw new Refused(401, 'invalid-proof')
    let audience, host
    try { audience = new URL(tags.get('u')); host = new URL('https://' + request.headers.host) } catch { throw new Refused(401, 'invalid-proof') }
    if (audience.protocol !== 'https:' || audience.username || audience.password || audience.search || audience.hash
      || host.username || host.password || host.search || host.hash || host.pathname !== '/'
      || audience.port !== '3753' || audience.pathname !== path || host.host !== audience.host || !allowedHosts.has(audience.hostname)) throw new Refused(401, 'invalid-proof')
    const nonce = tags.get('nonce'), deadline = nonces.get(nonce)
    if (!deadline || deadline.wall <= now() || deadline.mono <= monotonic() || !verifyEvent(event)) throw new Refused(401, 'invalid-proof')
    nonces.delete(nonce)
    return event.pubkey
  }
  function session(request) {
    const match = /^Bearer ([A-Za-z0-9_-]{43})$/.exec(request.headers.authorization ?? '')
    const value = match && sessions.get(match[1])
    if (!value || value.wall <= now() || value.mono <= monotonic() || !owners.has(value.owner)) throw new Refused(401, 'sign-in-required')
    if (request.headers['x-kithmoot-activity'] === 'user') {
      value.wall = Math.min(now() + SESSION_IDLE_MS, value.maxWall)
      value.mono = Math.min(monotonic() + SESSION_IDLE_MS, value.maxMono)
    }
    return value
  }
  async function handle(request, response) {
    const path = request.url
    if (typeof path !== 'string' || path.length > 128 || path.includes('?') || path.includes('#')) throw new Refused(404, 'not-found')
    if (request.method === 'GET' && path === '/api/challenge') {
      for (const [key, value] of nonces) if (value.wall <= now() || value.mono <= monotonic()) nonces.delete(key)
      if (nonces.size >= 128) throw new Refused(429, 'busy')
      const nonce = randomBytes(32).toString('base64url')
      nonces.set(nonce, { wall: now() + 60000, mono: monotonic() + 60000 })
      return json(response, 200, { v: 1, nonce })
    }
    if (request.method === 'GET') {
      const files = { '/': ['index.html', 'text/html; charset=utf-8'], '/client.js': ['client.js', 'text/javascript'],
        '/style.css': ['style.css', 'text/css'], '/nostr-provider.js': ['nostr-provider.js', 'text/javascript'] }
      if (!files[path]) throw new Refused(404, 'not-found')
      const [name, type] = files[path]
      response.writeHead(200, { 'Content-Type': type }); response.end(readFileSync(join(publicDirectory, name))); return
    }
    if (request.method !== 'POST' || !['/api/session', '/api/sign-out', '/api/status', '/api/setup', '/api/start', '/api/pause', '/api/pair', '/api/prepare-delete', '/api/cancel-delete'].includes(path)) throw new Refused(404, 'not-found')
    if (request.headers['content-type'] !== 'application/json') throw new Refused(415, 'json-required')
    const chunks = []; let length = 0
    for await (const chunk of request) { length += chunk.length; if (length > 4096) throw new Refused(413, 'too-large'); chunks.push(chunk) }
    const body = Buffer.concat(chunks); let value
    try { value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(body)) } catch { throw new Refused(400, 'invalid-input') }
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Refused(400, 'invalid-input')
    if (path === '/api/session') {
      if (Object.keys(value).length) throw new Refused(400, 'invalid-input')
      const owner = proof(request, path, body)
      for (const [key, value] of sessions) if (value.wall <= now() || value.mono <= monotonic()) sessions.delete(key)
      if (sessions.size >= 32) throw new Refused(429, 'busy')
      const token = randomBytes(32).toString('base64url')
      sessions.set(token, { owner, wall: now() + SESSION_IDLE_MS, mono: monotonic() + SESSION_IDLE_MS,
        maxWall: now() + SESSION_MAX_MS, maxMono: monotonic() + SESSION_MAX_MS })
      return json(response, 200, { v: 1, token, expiresAt: Math.floor((now() + SESSION_IDLE_MS) / 1000) })
    }
    session(request)
    if (path !== '/api/setup' && Object.keys(value).length) throw new Refused(400, 'invalid-input')
    if (path === '/api/sign-out') {
      sessions.delete(request.headers.authorization.slice(7))
      return json(response, 200, { v: 1, result: { signedOut: true } })
    }
    const actions = { '/api/status': () => node.status(), '/api/setup': () => node.setup(choices(value)), '/api/start': () => node.start(),
      '/api/pause': () => node.stop(), '/api/pair': () => node.pair(), '/api/prepare-delete': () => node.prepareDelete(), '/api/cancel-delete': () => node.cancelDelete() }
    const result = await actions[path]()
    return json(response, 200, { v: 1, result: result ?? { accepted: true } })
  }
  const server = createServer({ maxHeaderSize: 16384, requestTimeout: 15000, headersTimeout: 10000, maxRequestsPerSocket: 32 }, (request, response) => {
    response.setHeader('Cache-Control', 'no-store'); response.setHeader('Referrer-Policy', 'no-referrer')
    response.setHeader('X-Content-Type-Options', 'nosniff')
    response.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src https:; base-uri 'none'; object-src 'none'; form-action 'none'")
    if (rate.until <= monotonic()) rate = { until: monotonic() + 1000, count: 0 }
    if (requests >= 16 || ++rate.count > 32) { request.resume(); return json(response, 429, { error: 'busy' }) }
    requests++
    void handle(request, response).catch(error => { if (!response.headersSent) json(response, error instanceof Refused ? error.status : 503, { error: error instanceof Refused ? error.message : 'node-unavailable' }); else response.destroy() }).finally(() => { requests-- })
  })
  server.maxConnections = 32
  return server
}
