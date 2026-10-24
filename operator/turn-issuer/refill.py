#!/usr/bin/env python3
"""Root-only, offline pool refill using the installed Spry credential command.

The public HTTP process receives only these short-lived passwords. Neither
this helper nor the HTTP process reads the node's root TURN secret.
"""
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import tempfile
import time


def refill(destination=Path('/var/lib/spry-public-issuer/credentials'), count=64):
    if os.geteuid() != 0 or not 1 <= count <= 128:
        raise ValueError('Root and a bounded credential pool are required')
    gid = pwd.getpwnam('spry-issuer').pw_gid
    generation = secrets.token_hex(16)
    lines = [f'SPRYP1\t{generation}\n']
    for _ in range(count):
        result = subprocess.run([
            'runuser', '-u', 'archipelago', '--', 'env',
            'XDG_RUNTIME_DIR=/run/user/1000',
            'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus',
            'podman', 'exec', 'spry-turn-lab', '/usr/local/bin/spry-turn',
            'credential', '--ttl', '1200', '--label', secrets.token_hex(16)
        ], check=True, capture_output=True, timeout=15, cwd='/')
        value = json.loads(result.stdout)
        if set(value) != {'username', 'credential'}:
            raise ValueError('Unexpected credential output')
        expiry, label = value['username'].split(':', 1)
        if not label.isalnum() or not 1100 <= int(expiry) - time.time() <= 1250:
            raise ValueError('Unexpected credential lifetime')
        if len(value['credential']) != 28 or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in value['credential']):
            raise ValueError('Unexpected credential encoding')
        lines.append(f"{value['username']}\t{value['credential']}\n")
    fd, temporary = tempfile.mkstemp(prefix='.credentials-', dir=destination.parent)
    try:
        with os.fdopen(fd, 'w') as file:
            os.fchmod(file.fileno(), 0o640)
            os.fchown(file.fileno(), 0, gid)
            file.write(''.join(lines))
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        refill()
    except Exception as error:
        # Never include subprocess output or a credential in the journal.
        raise SystemExit(f'Credential pool unavailable ({type(error).__name__})')
