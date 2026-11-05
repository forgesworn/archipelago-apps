// The existing node service identity signs only this fixed, read-only HTTP
// request. Neither the proof nor the service key reaches the browser.
import { createHash, createHmac, randomBytes } from 'node:crypto'
import { finalizeEvent, getPublicKey } from 'nostr-tools/pure'

const fields = ['elapsedMillis', 'ageMillis', 'udpAllocations', 'streamAllocations', 'streamConnections',
  'udpForwardedBytes', 'streamForwardedBytes', 'forwardedPackets', 'droppedPackets', 'streamErrors', 'refusedStreams']
const cumulative = ['udpForwardedBytes', 'streamForwardedBytes', 'forwardedPackets', 'droppedPackets', 'streamErrors', 'refusedStreams']
const integer = value => Number.isSafeInteger(value) && value >= 0
const digest = value => createHash('sha256').update(value).digest('hex')

export async function readRelayMetrics(facts, secrets, { fetchImpl = fetch } = {}) {
  const seed = secrets.KITHMOOT_NODE_SERVICE_KEY, turn = secrets.KITHMOOT_NODE_TURN_SECRET
  if (!/^[a-f0-9]{64}$/.test(seed ?? '') || !/^[a-f0-9]{64}$/.test(turn ?? '')) throw Error('Relay metrics unavailable')
  const key = new Uint8Array(Buffer.from(seed, 'hex'))
  let body, proof
  try {
    const pairing = createHmac('sha256', turn).update('spry-supervised-pairing-v1:' + getPublicKey(key)).digest('base64url')
    body = JSON.stringify({ v: 1, pairing })
    proof = finalizeEvent({ kind: 27235, created_at: Math.floor(Date.now() / 1000), content: '',
      tags: [['u', 'https://' + facts.host + '/v1/node/status'], ['method', 'POST'], ['payload', digest(body)], ['nonce', randomBytes(32).toString('base64url')]] }, key)
  } finally { key.fill(0) }
  const response = await fetchImpl('http://127.0.0.1:3751/v1/node/status', {
    method: 'POST', body, headers: { 'Content-Type': 'application/json', Authorization: 'Nostr ' + Buffer.from(JSON.stringify(proof)).toString('base64') },
    redirect: 'error', credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer', signal: AbortSignal.timeout(2500)
  })
  if (!response.ok || !/^application\/json(?:;|$)/i.test(response.headers.get('content-type') ?? '') || !response.body) throw Error('Relay metrics unavailable')
  const reader = response.body.getReader(), chunks = []; let length = 0
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      length += value.length
      if (length > 4096) throw Error('Relay metrics unavailable')
      chunks.push(value)
    }
  } finally { await reader.cancel().catch(() => {}) }
  const answer = JSON.parse(Buffer.concat(chunks).toString('utf8')), metrics = answer.metrics
  if (answer.v !== 1 || answer.ready !== true || metrics?.v !== 1 || !/^[a-f0-9]{64}$/.test(metrics.epoch ?? '')
    || !fields.every(name => integer(metrics[name])) || metrics.ageMillis > 2000
    || !integer(metrics.udpForwardedBytes + metrics.streamForwardedBytes)
    || !integer(metrics.udpAllocations + metrics.streamAllocations)) throw Error('Relay metrics unavailable')
  // Explicit projection, including across future protocol extensions.
  return { epoch: metrics.epoch, ...Object.fromEntries(fields.map(name => [name, metrics[name]])) }
}

export function relayMetricsSampler(facts, secrets, { read = () => readRelayMetrics(facts, secrets) } = {}) {
  let previous
  return async () => {
    let value
    try { value = await read() } catch { previous = undefined; return null }
    const interval = previous && previous.epoch === value.epoch && value.elapsedMillis > previous.elapsedMillis
      && cumulative.every(name => value[name] >= previous[name]) ? (value.elapsedMillis - previous.elapsedMillis) / 1000 : null
    const rate = name => interval === null ? null : (value[name] - previous[name]) / interval
    const udp = rate('udpForwardedBytes'), stream = rate('streamForwardedBytes')
    previous = value
    return { sampledAt: Date.now() - value.ageMillis, uptimeSeconds: Math.floor(value.elapsedMillis / 1000),
      allocations: value.udpAllocations + value.streamAllocations, streamConnections: value.streamConnections,
      forwardedBytes: value.udpForwardedBytes + value.streamForwardedBytes,
      bytesPerSecond: interval === null ? null : udp + stream, intervalSeconds: interval,
      udp: { allocations: value.udpAllocations, forwardedBytes: value.udpForwardedBytes, bytesPerSecond: udp },
      stream: { allocations: value.streamAllocations, forwardedBytes: value.streamForwardedBytes, bytesPerSecond: stream },
      forwardedPackets: value.forwardedPackets, droppedPackets: value.droppedPackets,
      streamErrors: value.streamErrors, refusedStreams: value.refusedStreams }
  }
}
