import importlib.util
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = load('migrate_node', ROOT / 'scripts/migrate-node.py')
guard = load('migration_guard', ROOT / 'scripts/migration-startup-guard.py')
APPS = ['app-a', 'app-b']
IMAGE = 'a' * 64


class FakeHost:
    def __init__(self, root):
        self.root = Path(root)
        self.states = {'manager.service': True, 'npm.timer': True, 'npm.service': False}
        self.calls = []
        self.version = '2.1.0-beta.2'

    def active(self, unit):
        return self.states.get(unit, False)

    def set_active(self, unit, active):
        self.calls.append((unit, active))
        self.states[unit] = active
        runtime = self.root / 'opt/archipelago/web-ui/archipelago-runtime/apps'
        if unit == 'manager.service' and active and runtime.is_dir():
            for source in runtime.iterdir():
                target = self.root / 'opt/archipelago/apps' / source.name
                if not target.exists():
                    shutil.copytree(source, target)

    def daemon_reload(self):
        self.calls.append(('daemon-reload', True))

    def inspect(self, apps):
        result = {}
        for app in apps:
            result[app] = {
                'Id': app[0] * 64,
                'Image': IMAGE,
                'ImageName': 'localhost/fixture:1',
                'Name': app,
                'Mounts': [{'Type': 'volume', 'Name': f'{app}-anonymous', 'Destination': '/data'}],
                'HostConfig': {'AutoRemove': True, 'NetworkMode': 'bridge', 'PortBindings': {}},
                'Config': {'Env': ['A=one'], 'Cmd': ['run'], 'Entrypoint': None, 'Labels': {}},
                'State': {'Running': True},
            }
        return result

    def image_id(self, reference):
        assert reference == 'localhost/fixture:1'
        return IMAGE

    def user(self, args, timeout=180, check=True):
        assert args[:2] == ['podman', 'volume']
        return SimpleNamespace(stdout='[]', returncode=0)

    def health(self):
        return {'status': 'ok', 'crash_recovery_complete': True, 'version': self.version}


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.host = FakeHost(self.root)
        self.migration = migration.Migration(self.root, self.host, os.getuid(), os.getgid())
        self.migration.backend.parent.mkdir(parents=True)
        self.migration.backend.write_bytes(b'alpha-backend')
        self.frontend = self.migration.frontend
        (self.frontend / 'archipelago-runtime').mkdir(parents=True)
        (self.frontend / 'index.html').write_text('alpha UI')
        for app in APPS:
            recipe = self.migration.opt / 'apps' / app
            recipe.mkdir(parents=True)
            (recipe / 'manifest.yml').write_text(f'installed:{app}\n')
            unit = self.migration.units / f'{app}.container'
            unit.parent.mkdir(parents=True, exist_ok=True)
            unit.write_text(f'[Container]\nImage=localhost/fixture:1\nContainerName={app}\n')
            os.chmod(unit, 0o644)
        self.candidate = self.root / 'input/backend'
        self.candidate.parent.mkdir()
        self.candidate.write_bytes(b'beta-backend')
        tree = self.root / 'input/frontend'
        (tree / 'archipelago-runtime/apps').mkdir(parents=True)
        (tree / 'index.html').write_text('beta UI')
        for app in APPS:
            (tree / f'archipelago-runtime/apps/{app}').mkdir()
            (tree / f'archipelago-runtime/apps/{app}/manifest.yml').write_text('incoming recipe')
        self.archive = self.root / 'input/frontend.tar.gz'
        with tarfile.open(self.archive, 'w:gz') as bundle:
            for path in tree.rglob('*'):
                bundle.add(path, path.relative_to(tree))
        self.args = SimpleNamespace(
            apps=APPS,
            service='manager.service',
            npm_unit='npm',
            version='2.1.0-beta.2',
            backend_sha256=migration.digest(self.candidate),
            frontend_sha256=migration.digest(self.archive),
            health_timeout=2,
            manager_stopped=False,
            old_backend_sha256=None,
            backend=self.candidate,
            frontend=self.archive,
        )

    def promote(self):
        with mock.patch.object(migration.time, 'sleep', return_value=None):
            return self.migration.promote(self.args)

    def test_pair_runtime_and_all_apps_survive_two_manager_starts(self):
        state = self.promote()
        self.assertEqual(state['phase'], 'active')
        self.assertEqual(self.migration.backend.read_bytes(), b'beta-backend')
        for app in APPS:
            self.assertEqual((self.migration.opt / f'apps/{app}/manifest.yml').read_text(), f'installed:{app}\n')
            self.assertEqual((self.frontend / f'archipelago-runtime/apps/{app}/manifest.yml').read_text(), f'installed:{app}\n')
            saved = json.loads((self.migration.data / f'update-transactions/installed-units/{app}.json').read_text())
            self.assertEqual(saved['operation'], state['operation'])
            self.assertIn('ContainerName=' + app, saved['body'])
        guard.check(self.migration.state_path, self.migration.backend, self.frontend, enforce_custody=False)
        self.assertEqual(self.host.states['manager.service'], True)
        self.assertEqual(self.host.states['npm.timer'], True)
        self.assertEqual(self.host.states['npm.service'], False)

    def test_stopped_manager_requires_and_binds_exact_old_backend(self):
        self.host.states['manager.service'] = False
        self.args.manager_stopped = True
        with self.assertRaisesRegex(RuntimeError, 'old backend hash'):
            self.promote()
        self.args.old_backend_sha256 = migration.digest(self.migration.backend)
        state = self.promote()
        self.assertEqual(state['old_backend_sha256'], self.args.old_backend_sha256)
        self.assertTrue(self.host.states['manager.service'])

    def test_missing_installed_recipe_is_introduced_without_container_recreation(self):
        shutil.rmtree(self.migration.opt / 'apps/app-b')
        state = self.promote()
        self.assertEqual(state['candidate_recipes'], ['app-b'])
        self.assertEqual((self.migration.opt / 'apps/app-b/manifest.yml').read_text(), 'incoming recipe')
        self.assertIn('app-b', state['candidate_recipe_hashes'])
        guard.check(self.migration.state_path, self.migration.backend, self.frontend, enforce_custody=False)

    def test_app_without_installed_or_candidate_recipe_remains_external(self):
        shutil.rmtree(self.migration.opt / 'apps/app-b')
        archive = self.root / 'input/frontend-external.tar.gz'
        source = self.root / 'input/frontend'
        with tarfile.open(archive, 'w:gz') as bundle:
            for path in source.rglob('*'):
                if 'archipelago-runtime/apps/app-b' not in path.as_posix():
                    bundle.add(path, path.relative_to(source), recursive=False)
        self.args.frontend = archive
        self.args.frontend_sha256 = migration.digest(archive)
        state = self.promote()
        self.assertEqual(state['external_apps'], ['app-b'], state)
        self.assertFalse((self.migration.opt / 'apps/app-b').exists())
        guard.check(self.migration.state_path, self.migration.backend, self.frontend, enforce_custody=False)

    def test_interruption_after_pair_rename_recovers_alpha_and_removes_new_ownership(self):
        original = self.migration.backend.read_bytes()
        with mock.patch.object(self.migration, 'start_candidate', side_effect=RuntimeError('interrupted')):
            with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                self.promote()
        self.assertEqual(self.migration.backend.read_bytes(), original)
        self.assertEqual(self.migration.load()['phase'], 'recovered')
        self.assertTrue(self.host.states['manager.service'])
        self.assertFalse(list((self.migration.data / 'update-transactions/installed-units').glob('*.json')))
        guard.check(self.migration.state_path, self.migration.backend, self.frontend, enforce_custody=False)

    def test_candidate_start_attempt_forbids_alpha_recovery(self):
        with mock.patch.object(self.migration, 'wait_health', side_effect=RuntimeError('candidate failed')):
            with self.assertRaisesRegex(RuntimeError, 'candidate failed'):
                self.promote()
        self.assertTrue(self.migration.load()['candidate_start_attempted'])
        self.assertFalse(self.host.states['manager.service'])
        with self.assertRaisesRegex(RuntimeError, 'rollback.*refused'):
            self.migration.recover()
        self.assertEqual(self.migration.backend.read_bytes(), b'beta-backend')
        guard.check(self.migration.state_path, self.migration.backend, self.frontend, enforce_custody=False)
        self.migration.backend.write_bytes(b'alpha-backend')
        with self.assertRaisesRegex(RuntimeError, 'Backend'):
            guard.check(self.migration.state_path, self.migration.backend, self.frontend, enforce_custody=False)

    def test_interrupted_candidate_start_resumes_without_alpha(self):
        start = self.migration.start_candidate
        with mock.patch.object(self.migration, 'start_candidate', side_effect=lambda: (start(), (_ for _ in ()).throw(RuntimeError('killed')))[1]):
            with self.assertRaisesRegex(RuntimeError, 'killed'):
                self.promote()
        self.assertFalse(self.host.states['manager.service'])
        state = self.promote()
        self.assertEqual(state['phase'], 'active')
        self.assertEqual(self.migration.backend.read_bytes(), b'beta-backend')

    def test_post_beta_mixed_pair_is_repaired_forward(self):
        self.promote()
        self.host.states['manager.service'] = False
        self.migration.backend.write_bytes(b'alpha-backend')
        (self.frontend / 'index.html').write_text('incomplete frontend')
        state = self.promote()
        self.assertEqual(state['phase'], 'active')
        self.assertEqual(self.migration.backend.read_bytes(), b'beta-backend')
        self.assertEqual((self.frontend / 'index.html').read_text(), 'beta UI')
        with self.assertRaisesRegex(RuntimeError, 'rollback.*refused'):
            self.migration.recover()

    def test_startup_guard_rejects_changed_backend_and_frontend(self):
        self.promote()
        original = self.migration.backend.read_bytes()
        try:
            self.migration.backend.write_bytes(b'alpha-backend')
            with self.assertRaisesRegex(RuntimeError, 'Backend'):
                guard.check(self.migration.state_path, self.migration.backend, self.frontend, enforce_custody=False)
        finally:
            self.migration.backend.write_bytes(original)
        (self.frontend / 'index.html').write_text('mixed frontend')
        with self.assertRaisesRegex(RuntimeError, 'Frontend/runtime'):
            guard.check(self.migration.state_path, self.migration.backend, self.frontend, enforce_custody=False)

    def test_installed_image_mismatch_refuses_before_pair_change(self):
        with mock.patch.object(self.host, 'image_id', return_value='b' * 64):
            with self.assertRaisesRegex(RuntimeError, 'image identity'):
                self.promote()
        self.assertEqual(self.migration.backend.read_bytes(), b'alpha-backend')
        self.assertEqual(self.migration.load()['phase'], 'recovered')

    def test_existing_different_runtime_record_is_not_overwritten(self):
        path = self.migration.data / 'update-transactions/installed-units/app-a.json'
        migration.write_json(path, {'schema': 1, 'operation': 'different'})
        with self.assertRaisesRegex(RuntimeError, 'preserved runtime differs'):
            self.promote()
        self.assertEqual(json.loads(path.read_text())['operation'], 'different')

    def test_resumption_uses_same_operation_and_candidate(self):
        first = self.promote()
        checked = lambda *args: guard.check(*args, enforce_custody=False)
        with mock.patch.object(migration.guard_module, 'check', side_effect=checked):
            second = self.promote()
        self.assertEqual(first['operation'], second['operation'])
        self.assertEqual(second['phase'], 'active')

    def test_lock_is_released_before_candidate_starts(self):
        observed = []

        def start():
            observed.append(not self.migration.locks)
            self.host.set_active(self.args.service, True)

        with mock.patch.object(self.migration, 'start_candidate', side_effect=start):
            with mock.patch.object(self.host, 'health', side_effect=RuntimeError('health unavailable')):
                with self.assertRaisesRegex(RuntimeError, 'health'):
                    self.promote()
        self.assertEqual(observed, [True])


if __name__ == '__main__':
    unittest.main()
