// Settings never edit room authority, identities, endpoints, secrets or paths.
// The supervisor remains stopped for the complete guarded file transaction.
import { DatabaseSync } from 'node:sqlite'
import { existsSync, lstatSync } from 'node:fs'
import { readdir, lstat, statfs } from 'node:fs/promises'
import { join } from 'node:path'
import { Refused, readPrivate, savePrivate, configurationRevision } from './private-state.mjs'
import { pickLimits, validLimits } from './limits.mjs'

const backupName = 'ui-settings-backup.json'
const otherFields = value => JSON.stringify(Object.entries(value).filter(([key]) => !Object.hasOwn(pickLimits(value), key)).sort(([a], [b]) => a.localeCompare(b)))

function previousConfiguration(state, current) {
  if (!existsSync(join(state, backupName))) return null
  const saved = readPrivate(join(state, backupName)), revision = configurationRevision(current)
  if (saved?.v !== 1 || Object.keys(saved).sort().join() !== 'appliedRevision,previous,v'
    || !saved.previous || !validLimits(pickLimits(saved.previous)) || otherFields(current) !== otherFields(saved.previous)
    || !/^[a-f0-9]{64}$/.test(saved.appliedRevision ?? '')) throw new Refused(409, 'settings-review-required')
  if (saved.appliedRevision === revision) return saved.previous
  // A crash after restoring the atomic configuration but before clearing the
  // backup leaves this harmless record. It is not another rollback candidate.
  if (configurationRevision(saved.previous) === revision) return null
  throw new Refused(409, 'settings-review-required')
}

export function settingsInformation(state, current, running, paused, deleting) {
  const revision = configurationRevision(current)
  try {
    if (!validLimits(pickLimits(current))) throw Error('Unsupported saved limits')
    const previous = previousConfiguration(state, current)
    return { revision, editable: !running && paused && !deleting, previous: previous ? pickLimits(previous) : null }
  } catch { return { revision, editable: false, previous: null, issue: 'settings-review-required' } }
}

export function ledgerUsage(state) {
  const path = join(state, 'ledger.sqlite'), info = lstatSync(path)
  if (!info.isFile() || info.isSymbolicLink() || info.uid !== process.getuid() || info.mode & 0o077) throw new Refused(409, 'settings-usage-unavailable')
  const database = new DatabaseSync(path, { readOnly: true })
  try {
    database.exec('PRAGMA query_only=ON; PRAGMA busy_timeout=100;')
    if (database.prepare('PRAGMA user_version').get().user_version !== 1) throw new Refused(409, 'settings-review-required')
    if (database.prepare("SELECT value FROM meta WHERE key='deleting'").get()?.value === '1') throw new Refused(409, 'deletion-prepared')
    const rooms = database.prepare('SELECT count(*) AS count FROM rooms').get().count
    const pending = database.prepare("SELECT count(*) AS count FROM operations WHERE phase<>'done'").get().count
    if (![rooms, pending].every(value => Number.isSafeInteger(value) && value >= 0)) throw new Refused(409, 'settings-usage-unavailable')
    return { rooms, pending }
  } finally { database.close() }
}

async function storageFootprint(state) {
  let entries = 0, bytes = 0
  async function visit(path, depth) {
    if (++entries > 2048 || depth > 8) throw new Refused(409, 'settings-usage-unavailable')
    const info = await lstat(path)
    if (info.uid !== process.getuid() || info.isSymbolicLink()) throw new Refused(409, 'settings-usage-unavailable')
    if (info.isDirectory()) { for (const name of await readdir(path)) await visit(join(path, name), depth + 1) }
    else if (info.isFile()) { bytes += info.size; if (!Number.isSafeInteger(bytes)) throw new Refused(409, 'settings-usage-unavailable') }
    else throw new Refused(409, 'settings-usage-unavailable')
  }
  const rooms = join(state, 'rooms')
  // An absent runtime store is not evidence of an empty message store.
  await visit(rooms, 0)
  return bytes
}

export async function validateSavedUsage(state, limits, { filesystem = statfs } = {}) {
  try {
    const usage = ledgerUsage(state)
    if (usage.pending) throw new Refused(409, 'settings-operations-pending')
    if (limits.maxRooms < usage.rooms) throw new Refused(409, 'settings-room-limit-too-small')
    const [bytes, disk] = await Promise.all([storageFootprint(state), filesystem(state)])
    if (limits.maxBytes < bytes) throw new Refused(409, 'settings-storage-limit-too-small')
    const available = disk.bavail * disk.bsize
    if (!Number.isSafeInteger(available) || available < 0) throw new Refused(409, 'settings-usage-unavailable')
    if (available < limits.minFreeBytes) throw new Refused(409, 'settings-disk-reserve-unavailable')
  } catch (error) { if (error instanceof Refused) throw error; throw new Refused(409, 'settings-usage-unavailable') }
}

export async function changeSavedSettings(state, value, running, restore = false) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || Object.keys(value).sort().join() !== (restore ? 'revision' : 'limits,revision') || !/^[a-f0-9]{64}$/.test(value.revision ?? '')
    || (!restore && !validLimits(value.limits))) throw new Refused(422, 'invalid-settings')
  if (running || !existsSync(join(state, 'ui-paused'))) throw new Refused(409, 'pause-before-settings')
  if (readPrivate(join(state, 'ui-paused'))?.v !== 1) throw new Refused(409, 'settings-review-required')
  if (existsSync(join(state, 'initialising')) || existsSync(join(state, 'ui-delete-prepared'))) throw new Refused(409, 'settings-review-required')
  const path = join(state, 'node.json'), current = readPrivate(path), revision = configurationRevision(current)
  if (value.revision !== revision) throw new Refused(409, 'settings-changed')
  if (!validLimits(pickLimits(current))) throw new Refused(409, 'settings-review-required')
  const previous = previousConfiguration(state, current)
  if (restore && !previous) throw new Refused(409, 'no-previous-settings')
  const limits = restore ? pickLimits(previous) : value.limits
  await validateSavedUsage(state, limits)
  if (configurationRevision(readPrivate(path)) !== revision) throw new Refused(409, 'settings-changed')
  const next = { ...current, ...limits }, nextRevision = configurationRevision(next)
  if (nextRevision === revision) return { saved: true, paused: true, revision }
  // Backup is durable before the only authoritative settings file changes.
  if (!restore) savePrivate(join(state, backupName), { v: 1, appliedRevision: nextRevision, previous: current })
  savePrivate(path, next)
  return { saved: true, paused: true, revision: nextRevision }
}
