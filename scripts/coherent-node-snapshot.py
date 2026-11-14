#!/usr/bin/env python3
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import select
import signal
import subprocess
import sys
import time
import uuid

ROOTS = [
    'var/lib/archipelago', 'opt/archipelago', 'etc', 'usr/local', 'usr/bin/fips',
    'home/archipelago/.config', 'home/archipelago/.local', 'root/.ssh', 'var/spool',
    'var/lib/systemd', 'var/lib/dpkg/status',
]
EXCLUDES = ['var/lib/archipelago/snapshot-recovery']


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + '.partial')
    with temporary.open('w') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class Commands:
    def __init__(self, user='archipelago', uid=1000):
        self.user = user
        self.uid = uid

    def run(self, args, check=True, timeout=120, stdout=subprocess.PIPE):
        result = subprocess.run(args, text=True, stdout=stdout, stderr=subprocess.PIPE, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError(f"Command failed ({result.returncode}): {shlex.join(args)}: {result.stderr[-2000:]}")
        return result

    def user_command(self, args, check=True, timeout=120, stdout=subprocess.PIPE):
        command = [
            'runuser', '-u', self.user, '--', 'env', f'HOME=/home/{self.user}',
            f'XDG_RUNTIME_DIR=/run/user/{self.uid}',
            f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{self.uid}/bus', *args,
        ]
        return self.run(command, check=check, timeout=timeout, stdout=stdout)

    def active(self, unit, user=False):
        command = ['systemctl']
        if user:
            command.append('--user')
        command.extend(['is-active', '--quiet', unit])
        result = self.user_command(command, check=False) if user else self.run(command, check=False)
        return result.returncode == 0

    def set_active(self, unit, active, user=False):
        if active == self.active(unit, user=user):
            return
        command = ['systemctl']
        if user:
            command.append('--user')
        command.extend(['start' if active else 'stop', unit])
        if user:
            self.user_command(command, timeout=180)
        else:
            self.run(command, timeout=180)

    def containers(self):
        result = self.user_command(['podman', 'ps', '-a', '--no-trunc', '--format', 'json'])
        return json.loads(result.stdout)

    def container(self, container_id):
        result = self.user_command(['podman', 'inspect', container_id])
        return json.loads(result.stdout)[0]

    def health_units(self, container_ids):
        result = self.user_command([
            'systemctl', '--user', 'list-units', '--all', '--no-legend', '--no-pager', '--type=timer',
        ])
        units = {}
        for line in result.stdout.splitlines():
            fields = line.split()
            timer = next((field for field in fields if field.endswith('.timer')), None)
            if not timer:
                continue
            if any(container_id.startswith(timer.split('-', 1)[0]) or timer.startswith(container_id[:12])
                   for container_id in container_ids):
                for unit in (timer, timer[:-6] + '.service'):
                    units[unit] = self.active(unit, user=True)
        return units

    def recreate_health_timer(self, timer, container_id, interval_seconds):
        existing = self.health_units([container_id])
        if any(active and unit.endswith('.timer') for unit, active in existing.items()):
            return
        service = timer[:-6] + '.service'
        self.user_command(['systemctl', '--user', 'reset-failed', service], check=False)
        command = [
            'systemd-run', '--user', '--unit', timer[:-6],
            '--timer-property=AccuracySec=1s', '--timer-property=RemainAfterElapse=no',
            f'--on-active={interval_seconds}s', f'--on-unit-inactive={interval_seconds}s',
            '/usr/bin/podman', 'healthcheck', 'run', container_id,
        ]
        self.user_command(command)
        self.user_command(['systemctl', '--user', 'start', service], check=False)
        if not self.active(timer, user=True):
            raise RuntimeError(f'Recreated health timer did not become active: {timer}')


def container_state(containers):
    result = {}
    for container in containers:
        names = container.get('Names') or []
        name = names[0] if isinstance(names, list) else names
        result[container['Id']] = {'name': name, 'status': container.get('Status', '')}
    return result


def acquire_locks(data_root):
    locks = []
    paths = [data_root / 'snapshot.lock']
    update_lock = data_root / 'update-transactions' / 'lock'
    if update_lock.exists():
        paths.append(update_lock)
    try:
        for path in paths:
            stream = path.open('a+')
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                stream.close()
                raise RuntimeError(f'Another lifecycle operation holds {path}')
            if path.name == 'snapshot.lock':
                stream.seek(0)
                stream.truncate()
                stream.write(str(os.getpid()))
                stream.flush()
                os.fsync(stream.fileno())
            locks.append(stream)
    except Exception:
        for stream in locks:
            stream.close()
        raise
    return locks


def stop_units(commands, state):
    system = state['systemUnits']
    for unit in (state['npmUnit'] + '.timer', state['npmUnit'] + '.service', state['managerUnit']):
        commands.set_active(unit, False)
    containers = commands.containers()
    state['containersBefore'] = container_state(containers)
    running = [container['Id'] for container in containers if container.get('State') == 'running'
               or container.get('Status', '').startswith('Up ')]
    state['runningContainers'] = running
    state['userUnits'] = commands.health_units(running)
    state['healthTimers'] = {}
    for timer, active in state['userUnits'].items():
        if not timer.endswith('.timer') or not active:
            continue
        container_id = next(item for item in running if timer.startswith(item[:12]))
        container = commands.container(container_id)
        healthcheck = container.get('Config', {}).get('Healthcheck') or {}
        interval_ns = healthcheck.get('Interval') or 30_000_000_000
        state['healthTimers'][timer] = {'containerId': container_id,
                                        'intervalSeconds': max(1, round(interval_ns / 1_000_000_000))}
    write_json(state['statePath'], state)
    for unit, active in state['userUnits'].items():
        if active:
            commands.set_active(unit, False, user=True)
    for container_id in running:
        state['pausedContainers'].append(container_id)
        write_json(state['statePath'], state)
        commands.user_command(['podman', 'pause', container_id], timeout=60)
    state['allWritersPaused'] = True
    state['pauseStartedMonotonic'] = time.monotonic()
    state['pauseStartedAt'] = utcnow()
    write_json(state['statePath'], state)


def restore_units(commands, state):
    errors = []
    for container_id in state.get('pausedContainers', []):
        try:
            container = commands.container(container_id)
            if container['State'].get('Paused'):
                commands.user_command(['podman', 'unpause', container_id], timeout=60)
        except Exception as error:
            errors.append(f'unpause {container_id}: {error}')
    try:
        commands.set_active(state['managerUnit'], state['systemUnits'][state['managerUnit']])
    except Exception as error:
        errors.append(f"restore {state['managerUnit']}: {error}")
    for unit, active in state.get('userUnits', {}).items():
        try:
            commands.set_active(unit, active, user=True)
        except Exception as error:
            timer = state.get('healthTimers', {}).get(unit)
            if not timer:
                errors.append(f'restore {unit}: {error}')
                continue
            try:
                commands.recreate_health_timer(unit, timer['containerId'], timer['intervalSeconds'])
            except Exception as recreation_error:
                errors.append(f'restore {unit}: {error}; recreate: {recreation_error}')
    for suffix in ('.service', '.timer'):
        unit = state['npmUnit'] + suffix
        try:
            commands.set_active(unit, state['systemUnits'][unit])
        except Exception as error:
            errors.append(f'restore {unit}: {error}')
    return errors


def recover(state_path):
    state_path = Path(state_path)
    if not state_path.exists():
        return
    state = json.loads(state_path.read_text())
    if state.get('recoveryComplete'):
        return
    tar_pid = state.get('tarPid')
    if tar_pid and not state.get('archiveComplete'):
        try:
            command = Path(f'/proc/{tar_pid}/cmdline').read_bytes().split(b'\0')[0]
            if command.endswith(b'tar'):
                os.killpg(tar_pid, signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    commands = Commands(state['user'], state['uid'])
    errors = restore_units(commands, state)
    state['recoveryComplete'] = not errors
    state['recoveryErrors'] = errors
    state['recoveredAt'] = utcnow()
    if state.get('pauseStartedMonotonic'):
        state['pauseSeconds'] = round(time.monotonic() - state['pauseStartedMonotonic'], 3)
    write_json(state_path, state)
    manifest_path = Path(state['manifestPath'])
    archive_path = Path(str(manifest_path).removesuffix('.json'))
    if not state.get('archiveComplete'):
        archive_path.with_name(archive_path.name + '.partial').unlink(missing_ok=True)
        archive_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest['recoveryComplete'] = not errors
        manifest['recoveryErrors'] = errors
        manifest['pauseSeconds'] = state.get('pauseSeconds')
        manifest['recoveredAt'] = state['recoveredAt']
        write_json(manifest_path, manifest)
    if errors:
        raise RuntimeError('; '.join(errors))


def write_archive(commands, state, output, pause_budget, roots=None):
    partial = output.with_name(output.name + '.partial')
    log = output.with_name(output.name + '.capture.log')
    if output.exists() or partial.exists() or log.exists():
        raise RuntimeError(f'Refusing to overwrite snapshot files for {output}')
    args = [
        'tar', '--one-file-system', '--xattrs', '--acls', '--numeric-owner', '--sparse',
        *(f'--exclude={path}' for path in EXCLUDES), '-cpf', '-', '-C', '/', *(roots or ROOTS),
    ]
    digest = hashlib.sha256()
    total = 0
    deadline = time.monotonic() + pause_budget
    try:
        with partial.open('xb') as destination, log.open('xb') as errors:
            os.chmod(partial, 0o600)
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors, start_new_session=True)
            if state.get('statePath'):
                state['tarPid'] = process.pid
                write_json(state['statePath'], state)
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError(f'Pause budget exceeded ({pause_budget} seconds)')
                    readable, _, _ = select.select([process.stdout], [], [], remaining)
                    if not readable:
                        raise TimeoutError(f'Pause budget exceeded ({pause_budget} seconds)')
                    chunk = os.read(process.stdout.fileno(), 1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
                    digest.update(chunk)
                    total += len(chunk)
                status = process.wait(timeout=max(0.1, deadline - time.monotonic()))
                if status:
                    raise RuntimeError(f'tar failed with status {status}; see {log}')
                destination.flush()
                os.fsync(destination.fileno())
            except Exception:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise
            finally:
                process.stdout.close()
        os.replace(partial, output)
        if state.get('statePath'):
            state['tarPid'] = None
            write_json(state['statePath'], state)
        directory = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return {'sha256': digest.hexdigest(), 'bytes': total, 'captureLog': str(log)}
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def capture(args):
    if os.geteuid() != 0 or not os.environ.get('INVOCATION_ID'):
        raise RuntimeError('Capture must run as root through its recovery-enabled systemd unit')
    output = Path(args.output).absolute()
    protected_roots = [Path('/var/lib/archipelago'), Path('/opt/archipelago'), Path('/etc'),
                       Path('/usr/local'), Path('/home/archipelago'), Path('/var/spool'),
                       Path('/var/lib/systemd')]
    if any(output == root or root in output.parents for root in protected_roots):
        raise RuntimeError('Snapshot output must be outside the captured roots')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    roots = ROOTS + args.additional_root
    data_root = Path('/var/lib/archipelago')
    locks = acquire_locks(data_root)
    try:
        commands = Commands(args.user, args.uid)
        manager = args.manager_unit
        npm = args.npm_unit
        system_units = {
            manager: commands.active(manager),
            npm + '.service': commands.active(npm + '.service'),
            npm + '.timer': commands.active(npm + '.timer'),
        }
        state = {
            'schema': 1,
            'statePath': str(Path(args.state).absolute()),
            'manifestPath': str(output) + '.json',
            'managerUnit': manager,
            'npmUnit': npm,
            'user': args.user,
            'uid': args.uid,
            'systemUnits': system_units,
            'userUnits': {},
            'pausedContainers': [],
            'createdAt': utcnow(),
            'recoveryComplete': False,
            'roots': roots,
        }
        write_json(state['statePath'], state)
        stop_units(commands, state)
        commands.run(['sync'], timeout=60)
        archive = write_archive(commands, state, output, args.pause_budget, roots)
        manifest = {
            'schema': 1,
            'archive': str(output),
            **archive,
            'createdAt': state['createdAt'],
            'completedAt': utcnow(),
            'roots': roots,
            'excludes': EXCLUDES,
            'systemUnits': system_units,
            'userUnits': state['userUnits'],
            'healthTimers': state['healthTimers'],
            'containersBefore': state['containersBefore'],
            'pausedContainers': state['pausedContainers'],
            'consistency': 'manager-and-root-bridge-stopped; health-timers-stopped; running-containers-paused; sync-before-tar',
            'recoveryComplete': False,
        }
        write_json(manifest['archive'] + '.json', manifest)
        state['archiveComplete'] = True
        write_json(state['statePath'], state)
    finally:
        for stream in locks:
            stream.close()


def wrapper(args):
    script = Path(__file__).absolute()
    unit = args.unit_name or 'archy-coherent-snapshot-' + uuid.uuid4().hex[:12]
    state = Path(args.state).absolute() if args.state else Path('/var/lib/archipelago/snapshot-recovery') / (unit + '.json')
    capture_command = [sys.executable, str(script), '--capture', '--output', str(Path(args.output).absolute()),
                       '--state', str(state), '--manager-unit', args.manager_unit, '--npm-unit', args.npm_unit,
                       '--user', args.user, '--uid', str(args.uid), '--pause-budget', str(args.pause_budget),
                       *(item for root in args.additional_root for item in ('--additional-root', root))]
    recovery_command = [sys.executable, str(script), '--recover', str(state)]
    command = [
        'systemd-run', '--wait', '--collect', '--unit', unit,
        '--property', 'KillMode=mixed',
        '--property', f'RuntimeMaxSec={args.pause_budget + 180}',
        '--property', 'TimeoutStopSec=180',
        '--property', 'ExecStopPost=' + shlex.join(recovery_command), *capture_command,
    ]
    result = subprocess.run(command)
    if result.returncode:
        raise RuntimeError(f'Snapshot unit {unit} failed with status {result.returncode}; recovery state: {state}')
    print(json.dumps({'archive': str(Path(args.output).absolute()), 'manifest': str(Path(args.output).absolute()) + '.json',
                      'state': str(state), 'unit': unit}))


def main():
    parser = argparse.ArgumentParser(description='Bounded coherent Archy node snapshot with automatic recovery')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--recover', metavar='STATE')
    parser.add_argument('--output')
    parser.add_argument('--state')
    parser.add_argument('--manager-unit', default='archipelago.service')
    parser.add_argument('--npm-unit', default='archipelago-npm-bridge')
    parser.add_argument('--user', default='archipelago')
    parser.add_argument('--uid', type=int, default=1000)
    parser.add_argument('--pause-budget', type=int, default=120)
    parser.add_argument('--additional-root', action='append', default=[])
    parser.add_argument('--unit-name')
    args = parser.parse_args()
    if args.recover:
        recover(args.recover)
        return
    if args.capture:
        if not args.output or not args.state or args.pause_budget < 1:
            parser.error('--capture requires --output, --state and a positive --pause-budget')
        capture(args)
        return
    if not args.output or args.pause_budget < 1:
        parser.error('--output and a positive --pause-budget are required')
    wrapper(args)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'coherent-node-snapshot: {error}', file=sys.stderr)
        raise SystemExit(1)
