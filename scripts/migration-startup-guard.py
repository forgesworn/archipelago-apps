#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

STATE = Path('/etc/archipelago/node-migration.json')
BACKEND = Path('/usr/local/bin/archipelago')
FRONTEND = Path('/opt/archipelago/web-ui')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree_digest(root):
    root = Path(root)
    entries = []
    for path in [root, *sorted(root.rglob('*'))]:
        metadata = path.lstat()
        mode = metadata.st_mode
        relative = path.relative_to(root).as_posix()
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise RuntimeError(f'Unsupported frontend object: {relative}')
        if stat.S_ISREG(mode):
            if mode & 0o6000 or metadata.st_nlink != 1:
                raise RuntimeError(f'Privileged or hardlinked frontend file: {relative}')
            entries.append((relative, 'file', stat.S_IMODE(mode), digest(path)))
        else:
            entries.append((relative, 'directory', stat.S_IMODE(mode), ''))
    serialized = json.dumps(entries, separators=(',', ':'), ensure_ascii=True).encode()
    return hashlib.sha256(serialized).hexdigest()


def check(state=STATE, backend=BACKEND, frontend=FRONTEND, enforce_custody=True):
    state = Path(state)
    if enforce_custody:
        for directory in (state.parent, *state.parent.parents):
            metadata = directory.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
                raise RuntimeError('Migration state ancestry is not root-owned and immutable to other users')
            if directory == directory.parent:
                break
        metadata = state.lstat()
        if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_mode & 0o022:
            raise RuntimeError('Migration state is not a root-owned regular file')
    with state.open() as stream:
        record = json.load(stream)
    if record.get('schema') != 1 or record.get('phase') not in ('active', 'candidate-starting', 'recovered'):
        raise RuntimeError('Node migration is incomplete; manager startup refused')
    if digest(backend) != record.get('active_backend_sha256'):
        raise RuntimeError('Backend does not match the completed node migration')
    if tree_digest(frontend) != record.get('active_frontend_tree_sha256'):
        raise RuntimeError('Frontend/runtime does not match the completed node migration')
    return record


if __name__ == '__main__':
    try:
        check()
    except Exception as error:
        print(f'archy migration startup guard: {error}', file=sys.stderr)
        sys.exit(1)
