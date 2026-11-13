import { createServer, connect } from 'node:net'
import { chmodSync, lstatSync, rmSync } from 'node:fs'
import { join } from 'node:path'

function directory(state) {
  const info = lstatSync(state)
  if (!info.isDirectory() || info.uid !== process.getuid() || info.mode & 0o077) throw Error('Unsafe controller data directory')
}
function socketInfo(path) {
  const info = lstatSync(path)
  if (!info.isSocket() || info.uid !== process.getuid() || info.mode & 0o077 || info.nlink !== 1) throw Error('Unsafe controller socket')
  return info
}
async function removeStale(path) {
  let old
  try { old = socketInfo(path) } catch (error) { if (error.code === 'ENOENT') return; throw error }
  await new Promise((resolve, reject) => {
    const socket = connect(path)
    socket.setTimeout(1000, () => { socket.destroy(); reject(Error('Controller socket needs attention')) })
    socket.once('connect', () => { socket.destroy(); reject(Error('Controller is already running')) })
    socket.once('error', error => { socket.destroy(); if (['ECONNREFUSED', 'ENOENT'].includes(error.code)) resolve(); else reject(Error('Controller socket needs attention')) })
  })
  let current
  try { current = socketInfo(path) } catch (error) { if (error.code === 'ENOENT') return; throw error }
  if (old.dev !== current.dev || old.ino !== current.ino) throw Error('Controller socket changed')
  rmSync(path)
}

/** Host teardown uses this private socket, on the same queue as browser setup.
 * Only the manifest user can traverse its directory. It offers no public API. */
export async function startControllerControl(state, node) {
  directory(state)
  const path = join(state, 'operator.sock'), sockets = new Set()
  await removeStale(path)
  const server = createServer({ allowHalfOpen: true }, socket => {
    sockets.add(socket); socket.once('close', () => sockets.delete(socket)); socket.on('error', () => {})
    socket.setTimeout(25000, () => socket.destroy())
    const chunks = []; let size = 0
    socket.on('data', bytes => { size += bytes.length; if (size > 128) socket.destroy(); else chunks.push(bytes) })
    socket.once('end', async () => {
      if (socket.destroyed) return
      try {
        const value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)))
        if (!value || Object.keys(value).length !== 1 || value.op !== 'prepare-delete') throw Error('Unknown local operation')
        const result = await node.prepareDelete()
        socket.end(JSON.stringify({ ok: true, result }))
      } catch { socket.end(JSON.stringify({ ok: false, error: 'close-rooms-first' })) }
    })
  })
  server.maxConnections = 8
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(path, resolve) })
  chmodSync(path, 0o600)
  return { close: async () => { for (const socket of sockets) socket.destroy(); await new Promise(resolve => server.close(resolve)) } }
}

export function requestControllerDeletion(state) {
  directory(state)
  const path = join(state, 'operator.sock'); socketInfo(path)
  return new Promise((resolve, reject) => {
    const socket = connect(path); const chunks = []; let size = 0
    const refuse = () => { socket.destroy(); reject(Error('Start the node app and close its rooms before deleting it')) }
    socket.setTimeout(25000, refuse); socket.once('error', refuse)
    socket.once('connect', () => socket.end(JSON.stringify({ op: 'prepare-delete' })))
    socket.on('data', bytes => { size += bytes.length; if (size > 4096) refuse(); else chunks.push(bytes) })
    socket.once('end', () => {
      socket.destroy()
      try {
        const value = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)))
        if (value?.ok !== true || value.result?.deleteReady !== true || Object.keys(value).length !== 2 || Object.keys(value.result).length !== 1) throw Error('Not prepared')
        resolve(value)
      } catch { refuse() }
    })
  })
}
