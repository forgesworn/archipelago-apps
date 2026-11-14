#!/usr/bin/env python3
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import uuid

APP_ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}')
UNIT = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.@-]{0,200}\.service')
GUARD_PATH = Path('/usr/local/libexec/archy-migration-startup-guard')


def load_guard():
    spec = importlib.util.spec_from_file_location('migration_guard', Path(__file__).with_name('migration-startup-guard.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard_module = load_guard()


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json(path, value, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x') as stream:
        os.chmod(temporary, mode)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fsync_directory(path.parent)


def atomic_copy(source, destination, mode=0o755):
    source, destination = Path(source), Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    temporary = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex + '.tmp')
    shutil.copy2(source, temporary)
    os.chmod(temporary, mode)
    with temporary.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, destination)
    fsync_directory(destination.parent)


def regular_file(path, owner=None):
    metadata = Path(path).lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_nlink != 1:
        raise RuntimeError(f'Not an unlinked regular file: {path}')
    if metadata.st_mode & 0o6000:
        raise RuntimeError(f'Privileged file refused: {path}')
    if owner is not None and metadata.st_uid != owner:
        raise RuntimeError(f'Unexpected file owner: {path}')
    return metadata


def parse_quadlet(path, name, owner):
    metadata = regular_file(path, owner)
    if metadata.st_mode & 0o022 or metadata.st_size > 1024 * 1024:
        raise RuntimeError(f'Unsafe Quadlet mode or size: {path}')
    body = Path(path).read_text()
    section = ''
    images = []
    names = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.endswith('\\') or stripped.startswith(('.include', 'EnvironmentFile=', 'EnvFile=')):
            raise RuntimeError(f'External or continued Quadlet configuration refused: {path}')
        if stripped.startswith('['):
            section = stripped
        elif section == '[Container]' and stripped.startswith('Image='):
            images.append(stripped.removeprefix('Image='))
        elif section == '[Container]' and stripped.startswith('ContainerName='):
            names.append(stripped.removeprefix('ContainerName='))
    if len(images) != 1 or names != [name] or not images[0]:
        raise RuntimeError(f'Quadlet does not bind exactly one named container and image: {path}')
    if not re.fullmatch(r'[a-zA-Z0-9/:._@-]+', images[0]):
        raise RuntimeError(f'Invalid installed image reference: {path}')
    return body, stat.S_IMODE(metadata.st_mode), images[0]


def app_fingerprint(container, unit_body, unit_mode, recipe_hash):
    return {
        'id': container.get('Id'),
        'image': container.get('Image'),
        'image_name': container.get('ImageName'),
        'mounts': container.get('Mounts'),
        'auto_remove': container.get('HostConfig', {}).get('AutoRemove'),
        'network_mode': container.get('HostConfig', {}).get('NetworkMode'),
        'port_bindings': container.get('HostConfig', {}).get('PortBindings'),
        'environment': container.get('Config', {}).get('Env'),
        'command': container.get('Config', {}).get('Cmd'),
        'entrypoint': container.get('Config', {}).get('Entrypoint'),
        'labels': container.get('Config', {}).get('Labels'),
        'running': container.get('State', {}).get('Running'),
        'quadlet_sha256': hashlib.sha256(unit_body.encode()).hexdigest(),
        'quadlet_mode': unit_mode,
        'recipe_tree_sha256': recipe_hash,
    }


class Host:
    def __init__(self, user='archipelago', uid=1000):
        self.username = user
        self.uid = uid

    def run(self, args, timeout=180, check=True):
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, cwd='/var/tmp')
        if check and result.returncode:
            raise RuntimeError(f"Command failed ({result.returncode}): {args[0]}: {result.stderr[-2000:]}")
        return result

    def user(self, args, timeout=180, check=True):
        return self.run([
            'runuser', '-u', self.username, '--', 'env', f'HOME=/home/{self.username}',
            f'XDG_RUNTIME_DIR=/run/user/{self.uid}',
            f'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{self.uid}/bus', *args,
        ], timeout, check)

    def active(self, unit):
        return self.run(['systemctl', 'is-active', '--quiet', unit], check=False).returncode == 0

    def set_active(self, unit, active):
        self.run(['systemctl', 'start' if active else 'stop', unit], timeout=600)

    def inspect(self, apps):
        rows = json.loads(self.user(['podman', 'inspect', *apps]).stdout)
        if len(rows) != len(apps):
            raise RuntimeError('Incomplete installed-container inventory')
        return {row.get('Name', '').lstrip('/'): row for row in rows}

    def image_id(self, reference):
        rows = json.loads(self.user(['podman', 'image', 'inspect', reference]).stdout)
        if len(rows) != 1:
            raise RuntimeError('Installed image is not uniquely available')
        return rows[0].get('Id', '').removeprefix('sha256:')

    def health(self):
        request = urllib.request.Request(
            'http://127.0.0.1:5678/rpc/v1',
            json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'health'}).encode(),
            {'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            value = json.load(response)
        if value.get('error'):
            raise RuntimeError('Manager health RPC returned an error')
        return value['result']

    def daemon_reload(self):
        self.run(['systemctl', 'daemon-reload'])


class Migration:
    def __init__(self, root='/', host=None, node_uid=None, node_gid=None):
        self.root = Path(root).resolve()
        self.host = host or Host()
        account = pwd.getpwnam('archipelago') if node_uid is None else None
        self.node_uid = account.pw_uid if account else node_uid
        self.node_gid = account.pw_gid if account else node_gid
        self.data = self.path('var/lib/archipelago')
        self.opt = self.path('opt/archipelago')
        self.frontend = self.opt / 'web-ui'
        self.backend = self.path('usr/local/bin/archipelago')
        self.state_path = self.path('etc/archipelago/node-migration.json')
        self.units = self.path('home/archipelago/.config/containers/systemd')
        self.state = None
        self.locks = []

    def path(self, value):
        return self.root / value

    def operation_path(self, value):
        return Path(self.state['operation_root']) / value

    def save(self):
        self.state['updated_at'] = utcnow()
        write_json(self.state_path, self.state, 0o644)

    def load(self):
        with self.state_path.open() as stream:
            self.state = json.load(stream)
        if self.state.get('schema') != 1 or not self.state.get('operation'):
            raise RuntimeError('Invalid node migration state')
        for key in ('operation_root', 'private_root'):
            path = Path(self.state[key])
            if not path.is_absolute() or '..' in path.parts:
                raise RuntimeError('Invalid node migration operation path')
        return self.state

    def acquire_locks(self):
        for path in (self.data / 'snapshot.lock', self.data / 'update-transactions/lock'):
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            stream = path.open('a+')
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                stream.close()
                self.release_locks()
                raise RuntimeError(f'Another lifecycle operation holds {path}')
            self.locks.append(stream)

    def release_locks(self):
        for stream in self.locks:
            stream.close()
        self.locks.clear()

    def install_guard(self):
        source = Path(__file__).with_name('migration-startup-guard.py')
        destination = self.path(str(GUARD_PATH).lstrip('/'))
        if not destination.exists() or digest(source) != digest(destination):
            atomic_copy(source, destination, 0o755)
        enforcing = Path('/sys/fs/selinux/enforce')
        if enforcing.exists() and enforcing.read_text().strip() == '1':
            subprocess.run(['chcon', '-t', 'bin_t', destination], check=True)
        service = self.state['service']
        dropin = self.path(f'etc/systemd/system/{service}.d/99-node-migration.conf')
        dropin.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        temporary = dropin.with_name('.migration.conf.tmp')
        temporary.write_text(f'[Service]\nExecStartPre={GUARD_PATH}\n')
        os.chmod(temporary, 0o644)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, dropin)
        fsync_directory(dropin.parent)
        self.host.daemon_reload()

    def inspect_apps(self):
        containers = self.host.inspect(self.state['apps'])
        if set(containers) != set(self.state['apps']):
            raise RuntimeError('Installed application set changed')
        result = {}
        for app in self.state['apps']:
            container = containers[app]
            body, mode, image = parse_quadlet(self.units / f'{app}.container', app, self.node_uid)
            if self.host.image_id(image) != container.get('Image', '').removeprefix('sha256:'):
                raise RuntimeError(f'Installed image identity differs from its Quadlet: {app}')
            recipe = self.opt / 'apps' / app
            recipe_hash = guard_module.tree_digest(recipe) if (recipe / 'manifest.yml').is_file() else None
            result[app] = {
                'container': container,
                'fingerprint': app_fingerprint(container, body, mode, recipe_hash),
                'unit_body': body,
                'unit_mode': mode,
                'image_reference': image,
            }
        return result

    def verify_apps(self, phase):
        current = self.inspect_apps()
        private = Path(self.state['private_root'])
        with (private / 'inventory-before.json').open() as stream:
            before = json.load(stream)
        failures = [app for app in self.state['apps'] if current[app]['fingerprint'] != before[app]['fingerprint']]
        if failures:
            raise RuntimeError(f"Installed application state changed during {phase}: {', '.join(sorted(failures))}")
        volumes = sorted({mount.get('Name') for app in current.values() for mount in app['container'].get('Mounts', [])
                          if mount.get('Type') == 'volume' and mount.get('Name')})
        expected = self.state.get('anonymous_volumes', [])
        if volumes != expected:
            raise RuntimeError('Anonymous volume set changed')
        self.host.user(['podman', 'volume', 'inspect', *volumes]) if volumes else None
        write_json(private / f'inventory-{phase}.json', {app: value['container'] for app, value in current.items()})
        return current

    def prepare_candidate(self, backend, archive):
        operation = self.operation_path('candidate')
        if operation.exists():
            if digest(operation / 'backend') != self.state['backend_sha256']:
                raise RuntimeError('Staged candidate backend changed')
            if (operation / 'frontend').exists():
                if guard_module.tree_digest(operation / 'frontend') != self.state['frontend_tree_sha256']:
                    raise RuntimeError('Staged candidate frontend changed')
                return
        work = Path(tempfile.mkdtemp(prefix='.candidate-', dir=operation.parent))
        try:
            shutil.copy2(backend, work / 'backend')
            os.chmod(work / 'backend', 0o755)
            if digest(work / 'backend') != self.state['backend_sha256']:
                raise RuntimeError('Candidate backend hash mismatch')
            frontend = work / 'frontend'
            frontend.mkdir()
            with tarfile.open(archive) as bundle:
                bundle.extractall(frontend, filter='data')
            if not (frontend / 'index.html').is_file() or not (frontend / 'archipelago-runtime/apps').is_dir():
                raise RuntimeError('Complete frontend/runtime archive required')
            for app in self.state['apps']:
                for domain in ('apps', 'docker'):
                    source = self.opt / domain / app
                    target = frontend / 'archipelago-runtime' / domain / app
                    if source.exists():
                        if target.exists():
                            shutil.rmtree(target)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(source, target)
                    elif domain == 'apps':
                        if (target / 'manifest.yml').is_file():
                            self.state['candidate_recipes'].append(app)
                        else:
                            self.state['external_apps'].append(app)
            self.state['candidate_recipes'] = sorted(set(self.state['candidate_recipes']))
            self.state['external_apps'] = sorted(set(self.state['external_apps']))
            tree_hash = guard_module.tree_digest(frontend)
            if 'frontend_tree_sha256' in self.state and tree_hash != self.state['frontend_tree_sha256']:
                raise RuntimeError('Retained candidate frontend tree changed')
            self.state['frontend_tree_sha256'] = tree_hash
            operation.mkdir(exist_ok=True)
            if not (operation / 'backend').exists():
                (work / 'backend').rename(operation / 'backend')
            frontend.rename(operation / 'frontend')
            self.save()
        finally:
            shutil.rmtree(work, ignore_errors=True)

    def preserve_units(self):
        current = self.inspect_apps()
        directory = self.data / 'update-transactions/installed-units'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chown(directory, self.node_uid, self.node_gid)
        os.chmod(directory, 0o700)
        for app, value in current.items():
            saved = {
                'schema': 1,
                'operation': self.state['operation'],
                'name': app,
                'body': value['unit_body'],
                'mode': value['unit_mode'],
            }
            path = directory / f'{app}.json'
            if path.exists():
                with path.open() as stream:
                    existing = json.load(stream)
                if existing != saved:
                    raise RuntimeError(f'Existing preserved runtime differs: {app}')
                continue
            write_json(path, saved, 0o600)
            os.chown(path, self.node_uid, self.node_gid)
            self.state['installed_units_created'].append(app)
        fsync_directory(directory)
        self.state['anonymous_volumes'] = sorted({mount.get('Name') for app in current.values()
            for mount in app['container'].get('Mounts', []) if mount.get('Type') == 'volume' and mount.get('Name')})
        private = Path(self.state['private_root'])
        write_json(private / 'inventory-before.json', {app: {'fingerprint': value['fingerprint']} for app, value in current.items()})
        self.save()

    def stop_writers(self):
        for unit in (self.state['npm_unit'] + '.timer', self.state['npm_unit'] + '.service', self.state['service']):
            self.host.set_active(unit, False)
        if self.host.active(self.state['service']):
            raise RuntimeError('Manager did not stop')
        self.state['manager_stopped'] = True
        self.save()

    def restore_writers(self, include_manager=True):
        for unit, active in self.state.get('unit_choices', {}).items():
            if include_manager or unit != self.state['service']:
                self.host.set_active(unit, active)

    def accept_candidate_recipes(self):
        if not self.state['candidate_recipes']:
            return
        private = Path(self.state['private_root'])
        with (private / 'inventory-before.json').open() as stream:
            before = json.load(stream)
        for app in self.state['candidate_recipes']:
            recipe = self.frontend / 'archipelago-runtime/apps' / app
            recipe_hash = guard_module.tree_digest(recipe)
            self.state['candidate_recipe_hashes'][app] = recipe_hash
            before[app]['fingerprint']['recipe_tree_sha256'] = recipe_hash
        write_json(private / 'inventory-before.json', before)
        self.save()

    def activate_pair(self):
        original_frontend = self.operation_path('frontend-original')
        if not original_frontend.exists():
            self.state['old_frontend_tree_sha256'] = guard_module.tree_digest(self.frontend)
            self.save()
            atomic_copy(self.backend, self.operation_path('backend-original'), 0o755)
            self.frontend.rename(original_frontend)
            self.operation_path('candidate/frontend').rename(self.frontend)
        atomic_copy(self.operation_path('candidate/backend'), self.backend, 0o755)
        if digest(self.backend) != self.state['backend_sha256']:
            raise RuntimeError('Activated backend hash mismatch')
        if guard_module.tree_digest(self.frontend) != self.state['frontend_tree_sha256']:
            raise RuntimeError('Activated frontend is incomplete; run recover before candidate startup')
        self.accept_candidate_recipes()
        self.state['phase'] = 'pair-replaced'
        self.save()

    def start_candidate(self):
        self.state['candidate_start_attempted'] = True
        self.state['phase'] = 'candidate-starting'
        self.state['active_backend_sha256'] = self.state['backend_sha256']
        self.state['active_frontend_tree_sha256'] = self.state['frontend_tree_sha256']
        self.save()
        self.host.set_active(self.state['service'], True)

    def repair_active_pair(self):
        self.state['phase'] = 'repairing'
        self.save()
        atomic_copy(self.operation_path('candidate/backend'), self.backend, 0o755)
        replaced = self.operation_path('frontend-replaced-' + uuid.uuid4().hex)
        self.frontend.rename(replaced)
        self.operation_path('candidate/frontend').rename(self.frontend)
        if digest(self.backend) != self.state['backend_sha256'] or guard_module.tree_digest(self.frontend) != self.state['frontend_tree_sha256']:
            raise RuntimeError('Forward pair repair did not restore the reviewed candidate')
        self.start_candidate()

    def wait_health(self):
        deadline = time.monotonic() + self.state.get('health_timeout', 600)
        last = None
        while time.monotonic() < deadline:
            try:
                health = self.host.health()
                if health.get('version') != self.state['version']:
                    last = f"unexpected version {health.get('version')}; expected {self.state['version']}"
                    break
                if health.get('status') == 'ok' and health.get('crash_recovery_complete') is True:
                    return health
                last = 'recovery incomplete'
            except Exception as error:
                last = type(error).__name__
            time.sleep(2)
        raise RuntimeError(f'Candidate health did not pass: {last}')

    def complete_pair(self):
        self.state['phase'] = 'active'
        self.state['active_backend_sha256'] = self.state['backend_sha256']
        self.state['active_frontend_tree_sha256'] = self.state['frontend_tree_sha256']
        self.save()
        self.host.daemon_reload()
        self.restore_writers(include_manager=False)
        self.host.set_active(self.state['service'], True)

    def promote(self, args):
        new = not self.state_path.exists()
        if new:
            apps = args.apps
            if not apps or len(apps) != len(set(apps)) or any(not APP_ID.fullmatch(app) for app in apps):
                raise RuntimeError('Explicit unique installed application IDs required')
            if not UNIT.fullmatch(args.service):
                raise RuntimeError('Invalid manager unit')
            manager_active = self.host.active(args.service)
            if args.manager_stopped == manager_active:
                raise RuntimeError('Manager state does not match the explicit migration precondition')
            if args.manager_stopped and not args.old_backend_sha256:
                raise RuntimeError('Stopped-manager migration requires the exact old backend hash')
            if args.old_backend_sha256 and digest(self.backend) != args.old_backend_sha256:
                raise RuntimeError('Installed old backend hash mismatch')
            operation = str(uuid.uuid4())
            self.state = {
                'schema': 1,
                'operation': operation,
                'old_backend_sha256': digest(self.backend),
                'version': args.version,
                'phase': 'prepared',
                'created_at': utcnow(),
                'service': args.service,
                'npm_unit': args.npm_unit,
                'apps': apps,
                'backend_sha256': args.backend_sha256,
                'frontend_archive_sha256': args.frontend_sha256,
                'candidate_start_attempted': False,
                'installed_units_created': [],
                'candidate_recipes': [],
                'candidate_recipe_hashes': {},
                'external_apps': [],
                'health_timeout': args.health_timeout,
                'operation_root': str(self.opt / '.node-migration' / operation),
                'private_root': str(self.data / 'node-migration' / operation),
                'unit_choices': {},
            }
            for unit in (args.service, args.npm_unit + '.timer', args.npm_unit + '.service'):
                self.state['unit_choices'][unit] = self.host.active(unit)
            Path(self.state['operation_root']).mkdir(parents=True, mode=0o700)
            Path(self.state['private_root']).mkdir(parents=True, mode=0o700)
            self.save()
        else:
            self.load()
            for key, expected in (('backend_sha256', args.backend_sha256),
                                  ('frontend_archive_sha256', args.frontend_sha256),
                                  ('apps', args.apps), ('service', args.service), ('version', args.version)):
                if self.state[key] != expected:
                    raise RuntimeError(f'Resumed migration argument differs: {key}')
        if self.state['phase'] == 'recovered':
            raise RuntimeError('Recovered alpha state needs a new reviewed migration state; automatic re-promotion refused')
        self.install_guard()
        try:
            if self.state['phase'] == 'active':
                if digest(self.backend) == self.state['active_backend_sha256'] and guard_module.tree_digest(self.frontend) == self.state['active_frontend_tree_sha256']:
                    guard_module.check(self.state_path, self.backend, self.frontend)
                    self.restore_writers(include_manager=False)
                    self.host.set_active(self.state['service'], True)
                    self.verify_apps('active')
                    return self.state
                self.stop_writers()
                self.acquire_locks()
                self.prepare_candidate(args.backend, args.frontend)
                self.repair_active_pair()
                self.release_locks()
            if not self.state['candidate_start_attempted']:
                self.stop_writers()
                self.acquire_locks()
                self.preserve_units()
                self.prepare_candidate(args.backend, args.frontend)
                self.activate_pair()
                self.release_locks()
                self.start_candidate()
            elif not self.host.active(self.state['service']):
                self.host.set_active(self.state['service'], True)
            self.wait_health()
            time.sleep(self.state.get('settle_seconds', 45))
            self.verify_apps('first-start')
            self.host.set_active(self.state['service'], False)
            self.host.set_active(self.state['service'], True)
            self.wait_health()
            time.sleep(self.state.get('settle_seconds', 45))
            self.verify_apps('second-start')
            self.complete_pair()
            return self.state
        except Exception:
            if not self.state['candidate_start_attempted']:
                self.recover()
            else:
                self.host.set_active(self.state['service'], False)
            raise
        finally:
            self.release_locks()

    def recover(self):
        self.load()
        if self.state['candidate_start_attempted']:
            raise RuntimeError('Beta startup was attempted; alpha rollback and stale application-data restoration refused')
        self.host.set_active(self.state['service'], False)
        original_backend = self.operation_path('backend-original')
        if original_backend.exists():
            atomic_copy(original_backend, self.backend, 0o755)
        original_frontend = self.operation_path('frontend-original')
        if original_frontend.exists():
            if self.frontend.exists():
                self.frontend.rename(self.operation_path('frontend-interrupted'))
            original_frontend.rename(self.frontend)
        for app in self.state.get('installed_units_created', []):
            (self.data / 'update-transactions/installed-units' / f'{app}.json').unlink(missing_ok=True)
        self.state['phase'] = 'recovered'
        self.state['active_backend_sha256'] = digest(self.backend)
        self.state['active_frontend_tree_sha256'] = guard_module.tree_digest(self.frontend)
        self.save()
        self.host.daemon_reload()
        self.restore_writers()
        return self.state


def arguments():
    parser = argparse.ArgumentParser(description='Qualified existing-node Archy pair/runtime migration')
    parser.add_argument('command', choices=['promote', 'recover', 'status'])
    parser.add_argument('--backend', type=Path)
    parser.add_argument('--frontend', type=Path)
    parser.add_argument('--backend-sha256')
    parser.add_argument('--old-backend-sha256')
    parser.add_argument('--manager-stopped', action='store_true')
    parser.add_argument('--frontend-sha256')
    parser.add_argument('--version', default='2.1.0-beta.2-dev')
    parser.add_argument('--app', dest='apps', action='append')
    parser.add_argument('--service', default='archipelago.service')
    parser.add_argument('--npm-unit', default='archipelago-npm-bridge')
    parser.add_argument('--health-timeout', type=int, default=600)
    args = parser.parse_args()
    if args.command == 'promote':
        for name in ('backend', 'frontend', 'backend_sha256', 'frontend_sha256', 'apps'):
            if getattr(args, name) is None:
                parser.error(f'--{name.replace("_", "-")} is required for promote')
        if args.apps != sorted(args.apps):
            parser.error('--app values must be sorted to make resumption unambiguous')
        if args.health_timeout < 1:
            parser.error('--health-timeout must be positive')
    return args


def main():
    args = arguments()
    if os.geteuid() != 0:
        raise RuntimeError('Run the operator migration as root')
    migration = Migration()
    if args.command == 'status':
        state = migration.load()
        print(json.dumps(state, indent=2, sort_keys=True))
        return
    if args.command == 'recover':
        state = migration.recover()
    else:
        if digest(args.backend) != args.backend_sha256 or digest(args.frontend) != args.frontend_sha256:
            raise RuntimeError('Candidate input digest does not match its reviewed hash')
        state = migration.promote(args)
    print(json.dumps({key: state[key] for key in ('operation', 'phase', 'candidate_start_attempted')}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'archy node migration: {error}', file=sys.stderr)
        sys.exit(1)
