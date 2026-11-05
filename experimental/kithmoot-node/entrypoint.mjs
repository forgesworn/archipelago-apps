import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { isIP } from 'node:net'
import { NodeProcess, createController, ownerKeys } from './server.mjs'
import { startControllerControl, requestControllerDeletion } from './local-control.mjs'

if (process.platform !== 'linux' || process.getuid() !== 1000) throw Error('Run the private node image as its declared user')
if (process.argv.length > 2) {
  if (process.argv.length !== 3 || process.argv[2] !== 'prepare-delete') throw Error('Unknown controller command')
  try { console.log(JSON.stringify(await requestControllerDeletion('/var/lib/kithmoot-node'))) }
  catch { console.log(JSON.stringify({ ok: false, error: 'close-rooms-first' })); process.exitCode = 1 }
} else await serve()

async function serve() {
const host = process.env.PUBLIC_HOST?.toLowerCase()
if (!host || host.length > 253 || !/^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(host) || isIP(host)) throw Error('A public node hostname is required')
const address = process.env.HOST_IP
if (isIP(address ?? '') !== 4) throw Error('The node needs its configured public IPv4 address')
const secrets = {}
for (const key of ['KITHMOOT_NODE_SERVICE_KEY', 'KITHMOOT_NODE_TURN_SECRET', 'KITHMOOT_NODE_STATE_SALT']) {
  const value = process.env[key]
  if (!/^[a-f0-9]{64}$/.test(value ?? '')) throw Error('The generated node secrets are unavailable')
  secrets[key] = value
}
if (new Set(Object.values(secrets)).size !== 3) throw Error('Three independent node secrets are required')
// An operator may install an additional CA in a read-only image. Never take a
// trust setting from the browser, and retain normal certificate verification.
if (process.env.NODE_EXTRA_CA_CERTS) secrets.NODE_EXTRA_CA_CERTS = process.env.NODE_EXTRA_CA_CERTS
const owners = ownerKeys(process.env.NODE_IDENTITY_PUBKEYS)
const hosts = [host, address, process.env.HOST_MDNS, process.env.MESH_HOST].filter(Boolean)
const node = new NodeProcess({ host, address }, secrets)
const server = createController({ owners, hosts, node, publicDirectory: join(dirname(fileURLToPath(import.meta.url)), 'public') })
let control, stopping = false
async function stop() {
  if (stopping) return
  stopping = true
  server.closeAllConnections(); await new Promise(resolve => server.close(() => resolve()))
  await control?.close(); await node.stop(false)
}
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, async () => { await stop(); process.exit(0) })
try {
  // Claim management listeners before launching any detached node process.
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(3753, '127.0.0.1', resolve) })
  control = await startControllerControl('/var/lib/kithmoot-node', node)
  // An unavailable relay must leave its local recovery screen reachable.
  try { await node.boot() } catch { console.error('Saved node could not start; use its status screen to retry.') }
} catch {
  await stop(); throw Error('The private node management listeners could not start')
}
}
