#!/usr/bin/env python3
"""One explicit recovery of an existing payment on the packaged rootless node.

No invoice creation, new notes, spending, reset, restore, or arbitrary destinations.
Run as the archipelago service user. Output intentionally excludes backend errors.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path('/var/lib/archipelago/wildbloom-node')
SETTINGS = Path('/var/lib/archipelago/settings/wildbloom-storage/settings.json')
IMAGE = 'ghcr.io/forgesworn/wildbloom-node:0.3.5-2ea211e-2'
SERVICE = 'wildbloom-node.service'
CONTAINER = 'wildbloom-payment-recovery'
MAX = 9_007_199_254_740_991


class Refused(Exception):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def check_private_file(path, limit=65536):
    meta = path.lstat()
    require(stat.S_ISREG(meta.st_mode) and not meta.st_mode & 0o077 and meta.st_size <= limit,
            'Private operator file is unavailable or unsafe.')


def private_file(path, limit=65536):
    check_private_file(path, limit)
    return path.read_bytes()


def private_dir(path, create=False):
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    require(stat.S_ISDIR(path.lstat().st_mode) and not path.lstat().st_mode & 0o077,
            'Private operator directory is unavailable or unsafe.')


def save(path, value):
    temp = path.with_name(f'.{uuid.uuid4().hex}.tmp')
    with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as out:
        json.dump(value, out, separators=(',', ':'))
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def run(args, timeout=30):
    # No shell, inherited debug tracing, URL arguments or raw backend output.
    env = {k: v for k, v in os.environ.items() if k not in ('RUST_LOG', 'RUST_BACKTRACE')}
    result = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=timeout, env=env, check=False)
    require(result.returncode == 0 and len(result.stdout) <= 65536,
            'Operator command did not complete. Inspect local state before retrying.')
    return result.stdout.decode('utf-8')


def read_order(root, order):
    private_dir(root)
    private_dir(root / 'operator')
    private_dir(root / 'operator/checkout')
    path = root / 'operator/checkout/checkout.sqlite3'
    check_private_file(path, 256 * 1024 * 1024)
    for suffix in ('-wal', '-shm'):
        companion = Path(str(path) + suffix)
        if companion.exists() or companion.is_symlink():
            check_private_file(companion, 256 * 1024 * 1024)
    with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA trusted_schema=OFF')
        require(db.execute('PRAGMA user_version').fetchone()[0] == 1, 'Unsupported checkout schema.')
        row = db.execute('SELECT state,CASE WHEN length(quote)<=65536 THEN quote END FROM orders WHERE id=?',
                         (order,)).fetchone()
        require(row is not None and row[1] is not None, 'Order unavailable.')
        quote = json.loads(row[1])
        require(quote['order_id'] == order, 'Order does not match its quote.')
        return row[0], quote


def eligible(action, state, quote):
    if action == 'recover-invoice':
        require(state == 'invoice_pending' and quote['rail'] == 'lightning',
                'Original-invoice recovery requires a pending Lightning invoice.')
    else:
        require(state in ('awaiting_payment', 'lnurl_pending', 'settled'),
                'This order has no recoverable payment operation. Reservation retries are not permitted here.')


def configuration(root, settings_path, execute):
    settings = json.loads(private_file(settings_path))
    active = settings.get('active')
    require(active and active.get('checkout_started'), 'Dashboard-managed checkout has not started.')
    revision = active['revision']
    require(type(revision) is int and 0 < revision <= MAX, 'Invalid active settings revision.')
    info = json.loads(execute(['podman', 'inspect', 'wildbloom-node']))
    require(len(info) == 1 and info[0]['State']['Running'], 'Start the node before requesting recovery.')
    info = info[0]
    require(info['ImageName'] == IMAGE and re.fullmatch(r'(sha256:)?[0-9a-f]{64}', info['Image']),
            'Installed node image is incompatible with this recovery tool.')
    mounts = [m for m in info['Mounts'] if m['Destination'] == '/data']
    require(len(mounts) == 1 and mounts[0]['Source'] == str(root) and mounts[0]['RW'],
            'Node storage mount does not match the packaged volume.')
    env = dict(e.split('=', 1) for e in info['Config']['Env'] if '=' in e)
    name = f'dashboard-profile-{revision}.json'
    require(env.get('WILDBLOOM_CHECKOUT_PROFILE') == f'/data/operator/{name}'
            and env.get('WILDBLOOM_ARCHIPELAGO_SETTINGS_REVISION') == str(revision),
            'Apply or resolve pending dashboard settings before recovery.')
    s = active['settings']
    require(env.get('WILDBLOOM_QUOTA_BYTES') == str(s['quota_bytes'])
            and env.get('WILDBLOOM_MAX_BLOB_BYTES') == str(s['max_blob_bytes']), 'Storage limits do not match.')
    profile = json.loads(private_file(root / 'operator' / name))
    require(profile['state'] == '/data/operator/checkout'
            and profile['checkout']['origin'] == active['origin'].rstrip('/') + '/',
            'Recovery profile does not match this node.')
    # Preserve the exact reviewed issuer keys and address pins. Never resolve DNS,
    # rewrite an issuer, or infer a receiving endpoint during recovery.
    recovery = {k: profile.get(k) for k in ('checkout', 'phoenixd', 'notes')}
    recovery.update(storage_root='/data', quota_bytes=s['quota_bytes'], max_blob_bytes=s['max_blob_bytes'])
    return info['Image'], recovery


def backup(root, destination):
    # Offline full-volume copy: receipt state and blobs are retained together.
    size = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(directory) / name
            require(not p.is_symlink(), 'Backup refused a symlink in private storage.')
            require(p.is_dir() or p.is_file(), 'Backup refused a special file in private storage.')
            if p.is_file():
                size += p.stat().st_size
    require(shutil.disk_usage(root.parent).free >= size + 256 * 1024 * 1024,
            'Not enough free disk for the offline paired backup.')
    shutil.copytree(root, destination, copy_function=shutil.copy2)
    os.chmod(destination, 0o700)
    # Verify every copied byte before allowing a receiving operation.
    manifest = {}
    for p in destination.rglob('*'):
        if p.is_file():
            relative = p.relative_to(destination)
            def digest(path):
                with path.open('rb') as source:
                    return hashlib.file_digest(source, 'sha256').hexdigest()
            expected = digest(root / relative)
            require(digest(p) == expected, 'Backup verification failed.')
            manifest[str(relative)] = expected
            with p.open('rb') as file:
                os.fsync(file.fileno())
    for directory, _, _ in os.walk(destination, topdown=False):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    save(destination.parent / (destination.name + '-manifest.json'), manifest)


def recover(root, settings, action, order, execute=run, make_backup=backup):
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,128}', order), 'Invalid order ID.')
    state, quote = read_order(root, order)
    eligible(action, state, quote)
    image, profile = configuration(root, settings, execute)
    execute(['systemctl', '--user', 'is-active', '--quiet', SERVICE])
    require(execute(['systemctl', '--user', 'show', '--property=LoadState', '--value', SERVICE]).strip() == 'loaded',
            'Resolve the existing service mask before recovery.')
    directory = root / 'operator/recovery'
    private_dir(directory, create=True)
    lock_path = directory / 'operation.lock'
    if lock_path.exists() or lock_path.is_symlink():
        private_file(lock_path)
    lock = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        request_id = uuid.uuid4().hex
        journal = directory / f'{request_id}.json'
        value = dict(version=1, request_id=request_id, order_id=order, action=action,
                     started_at=int(time.time()), status='prepared')
        save(journal, value)
        profile_path = directory / f'{request_id}-profile.json'
        save(profile_path, profile)
        backups = root.parent / 'wildbloom-recovery-backups'
        private_dir(backups, create=True)
        destination = backups / request_id
        stopped = False
        masked = False
        outcome = None
        try:
            # A runtime mask prevents the management daemon or systemd from
            # restarting the storage writer while its offline backup is copied.
            masked = True
            execute(['systemctl', '--user', 'mask', '--runtime', SERVICE])
            # Always attempt restart if stop was requested, even on timeout.
            stopped = True
            execute(['systemctl', '--user', 'stop', SERVICE], timeout=120)
            # Ensure neither the daemon nor a previous recovery container is alive.
            running = execute(['podman', 'ps', '--format', '{{.Names}}']).splitlines()
            require('wildbloom-node' not in running and CONTAINER not in running,
                    'Storage writer is still running; recovery was not attempted.')
            state, quote = read_order(root, order)
            eligible(action, state, quote)
            make_backup(root, destination)
            value.update(status='backed_up', backup=str(destination))
            save(journal, value)
            value['status'] = 'running'
            save(journal, value)
            execute(['podman', 'run', '--rm', '--pull=never', '--name', CONTAINER,
                '--network=slirp4netns', '--timeout=60', '--volume', f'{root}:/data:rw',
                '--entrypoint', '/usr/local/bin/checkout-operator', image,
                '--state', '/data/operator/checkout', action, order,
                '--profile', f'/data/operator/recovery/{profile_path.name}'], timeout=90)
            # Read the durable result, never trust backend text or expose it.
            final, _ = read_order(root, order)
            require(final in ('awaiting_payment', 'lnurl_pending', 'settled', 'active', 'refund_required'),
                    'Unexpected durable result; inspect local state.')
            outcome = final
            value.update(status='completed', order_state=final)
        except BaseException:
            value['status'] = 'needs_review'
            raise
        finally:
            # A timeout may leave the container alive. Refuse overlapping writers.
            if stopped or masked:
                try:
                    running = execute(['podman', 'ps', '--format', '{{.Names}}']).splitlines()
                    if CONTAINER in running:
                        execute(['podman', 'stop', '--time', '15', CONTAINER], timeout=30)
                    execute(['systemctl', '--user', 'unmask', '--runtime', SERVICE])
                    execute(['systemctl', '--user', 'start', SERVICE], timeout=120)
                    execute(['systemctl', '--user', 'is-active', '--quiet', SERVICE])
                    healthy = False
                    for attempt in range(10):
                        try:
                            health = json.loads(execute(['curl', '--fail', '--silent', '--max-time', '3',
                                'http://127.0.0.1:3742/healthz'], timeout=5))
                            if health.get('status') == 'ok':
                                healthy = True
                                break
                        except Exception:
                            pass
                        time.sleep(1)
                    require(healthy, 'Storage health could not be verified after restart.')
                    value['node_restarted'] = True
                except BaseException:
                    value['node_restarted'] = False
                    value['status'] = 'restart_required'
                    save(journal, value)
                    raise Refused('Node restart could not be verified. Unmask and start wildbloom-node.service, then inspect the order. Do not send another payment.') from None
            value['finished_at'] = int(time.time())
            save(journal, value)
        return dict(status=value['status'], order_state=outcome, backup=str(destination))
    finally:
        os.close(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['reconcile', 'recover-invoice'])
    parser.add_argument('order')
    parser.add_argument('--confirm-restart', action='store_true', help='Allow a storage outage while a full offline backup is verified')
    args = parser.parse_args()
    require(args.confirm_restart, 'Recovery requires --confirm-restart for the offline backup and node restart.')
    require(sys.platform == 'linux' and os.geteuid() != 0, 'Run as the archipelago service user on the node.')
    os.umask(0o077)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    def interrupted(signum, frame):
        raise Refused('Recovery interrupted. Inspect the existing order before retrying.')
    signal.signal(signal.SIGTERM, interrupted)
    result = recover(ROOT, SETTINGS, args.action, args.order)
    print(json.dumps(result))


if __name__ == '__main__':
    try:
        main()
    except Refused as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except (Exception, KeyboardInterrupt):
        print('Recovery did not complete. Inspect the local recovery journal and node service before retrying. No new payment was created.', file=sys.stderr)
        sys.exit(1)
