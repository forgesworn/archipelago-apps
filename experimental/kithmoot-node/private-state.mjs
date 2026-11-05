import { createHash, randomBytes } from 'node:crypto'
import { openSync, constants, fstatSync, readFileSync, closeSync, writeFileSync, fsyncSync, renameSync, rmSync } from 'node:fs'
import { dirname } from 'node:path'

export class Refused extends Error { constructor(status, code) { super(code); this.status = status } }
export const configurationRevision = value => createHash('sha256').update(JSON.stringify(value)).digest('hex')
export function readPrivate(path) {
  const fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW)
  try {
    const info = fstatSync(fd)
    if (!info.isFile() || info.uid !== process.getuid() || info.mode & 0o077 || info.size > 65536) throw Error('Unsafe saved node settings')
    return JSON.parse(readFileSync(fd, 'utf8'))
  } finally { closeSync(fd) }
}
export function savePrivate(path, value) {
  const temporary = path + '.new-' + randomBytes(8).toString('hex')
  const fd = openSync(temporary, constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | constants.O_NOFOLLOW, 0o600)
  try {
    try { writeFileSync(fd, JSON.stringify(value) + '\n'); fsyncSync(fd) } finally { closeSync(fd) }
    renameSync(temporary, path)
    const parent = openSync(dirname(path), constants.O_RDONLY)
    try { fsyncSync(parent) } finally { closeSync(parent) }
  } finally { rmSync(temporary, { force: true }) }
}
