import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import textwrap
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).parents[2] / 'scripts' / 'coherent-node-snapshot.py'
SPEC = importlib.util.spec_from_file_location('coherent_node_snapshot', MODULE_PATH)
snapshot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(snapshot)


class FakeCommands:
    def __init__(self, active=None, containers=None):
        self.active_values = active or {}
        self.containers = containers or {}
        self.calls = []

    def active(self, unit, user=False):
        return self.active_values.get((user, unit), False)

    def set_active(self, unit, active, user=False):
        self.calls.append(('set_active', unit, active, user))
        self.active_values[(user, unit)] = active

    def container(self, container_id):
        return self.containers[container_id]

    def user_command(self, args, **kwargs):
        self.calls.append(('user_command', *args))
        container_id = args[-1]
        self.containers[container_id]['State']['Paused'] = args[-2] == 'pause'


class RecoveryTests(unittest.TestCase):
    def test_recovery_restores_recorded_choices_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_path = root / 'state.json'
            manifest_path = root / 'archive.json'
            manager = 'archy-alpha-recovery.service'
            state = {
                'statePath': str(state_path), 'manifestPath': str(manifest_path),
                'managerUnit': manager, 'npmUnit': 'archy-npm-fixture',
                'user': 'archipelago', 'uid': 1000,
                'systemUnits': {manager: True, 'archy-npm-fixture.service': False,
                                'archy-npm-fixture.timer': True},
                'userUnits': {'abc-health.timer': True, 'abc-health.service': False},
                'pausedContainers': ['abc'], 'pauseStartedMonotonic': 1, 'archiveComplete': True,
            }
            snapshot.write_json(state_path, state)
            snapshot.write_json(manifest_path, {'recoveryComplete': False})
            commands = FakeCommands(active={(True, 'abc-health.timer'): True},
                                    containers={'abc': {'State': {'Paused': True}}})
            with mock.patch.object(snapshot, 'Commands', return_value=commands), \
                    mock.patch.object(snapshot.time, 'monotonic', return_value=3.25):
                snapshot.recover(state_path)
                snapshot.recover(state_path)
            self.assertIn(('user_command', 'podman', 'unpause', 'abc'), commands.calls)
            self.assertEqual(commands.calls.count(('user_command', 'podman', 'unpause', 'abc')), 1)
            self.assertIn(('set_active', manager, True, False), commands.calls)
            self.assertIn(('set_active', 'abc-health.service', False, True), commands.calls)
            self.assertIn(('set_active', 'archy-npm-fixture.timer', True, False), commands.calls)
            result = json.loads(state_path.read_text())
            self.assertTrue(result['recoveryComplete'])
            self.assertEqual(result['pauseSeconds'], 2.25)
            self.assertTrue(json.loads(manifest_path.read_text())['recoveryComplete'])

    def test_interrupted_capture_removes_uncommitted_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_path = root / 'state.json'
            archive = root / 'archive.tar'
            manifest = root / 'archive.tar.json'
            state = {
                'manifestPath': str(manifest), 'managerUnit': 'manager.service',
                'npmUnit': 'npm', 'user': 'archipelago', 'uid': 1000,
                'systemUnits': {'manager.service': True, 'npm.service': False, 'npm.timer': True},
                'userUnits': {}, 'pausedContainers': [], 'archiveComplete': False,
            }
            snapshot.write_json(state_path, state)
            archive.write_bytes(b'incomplete')
            manifest.write_text('{}\n')
            Path(str(archive) + '.partial').write_bytes(b'partial')
            with mock.patch.object(snapshot, 'Commands', return_value=FakeCommands()):
                snapshot.recover(state_path)
            self.assertFalse(archive.exists())
            self.assertFalse(manifest.exists())
            self.assertFalse(Path(str(archive) + '.partial').exists())

    def test_health_units_match_only_container_ids(self):
        container_id = 'abcdef1234567890'
        commands = FakeCommands(active={(True, container_id + '-health.timer'): True,
                                        (True, 'unrelated.timer'): True})
        result = mock.Mock(stdout=(
            f'  {container_id}-health.timer loaded active waiting Health\n'
            '  unrelated.timer loaded active waiting Other\n'
        ))
        commands.user_command = mock.Mock(return_value=result)
        with mock.patch.object(snapshot.Commands, 'active', side_effect=lambda unit, user=False: commands.active(unit, user)):
            units = snapshot.Commands.health_units(commands, [container_id])
        self.assertEqual(set(units), {container_id + '-health.timer', container_id + '-health.service'})
        self.assertTrue(units[container_id + '-health.timer'])
        self.assertFalse(units[container_id + '-health.service'])

    def test_missing_health_timer_is_recreated_without_container_restart(self):
        commands = FakeCommands()
        commands.health_units = mock.Mock(return_value={})
        commands.user_command = mock.Mock()
        commands.active = mock.Mock(return_value=True)
        snapshot.Commands.recreate_health_timer(commands, 'abc-health.timer', 'abc', 30)
        args = commands.user_command.call_args_list[-2].args[0]
        self.assertEqual(args[:4], ['systemd-run', '--user', '--unit', 'abc-health'])
        self.assertIn('--on-unit-inactive=30s', args)
        self.assertEqual(args[-4:], ['/usr/bin/podman', 'healthcheck', 'run', 'abc'])
        self.assertNotIn('restart', args)
        self.assertEqual(commands.user_command.call_args.args[0],
                         ['systemctl', '--user', 'start', 'abc-health.service'])

    def test_equivalent_health_timer_avoids_duplicate_recreation(self):
        commands = FakeCommands()
        commands.health_units = mock.Mock(return_value={'different-health.timer': True})
        commands.user_command = mock.Mock()
        snapshot.Commands.recreate_health_timer(commands, 'old-health.timer', 'abc', 30)
        commands.user_command.assert_not_called()


class LockTests(unittest.TestCase):
    def test_snapshot_and_update_locks_reject_concurrent_lifecycle_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'update-transactions').mkdir()
            (root / 'update-transactions' / 'lock').touch()
            locks = snapshot.acquire_locks(root)
            self.assertEqual(len(locks), 2)
            with self.assertRaisesRegex(RuntimeError, 'Another lifecycle operation'):
                snapshot.acquire_locks(root)
            for stream in locks:
                stream.close()
            replacement = snapshot.acquire_locks(root)
            for stream in replacement:
                stream.close()


class ArchiveTests(unittest.TestCase):
    def fake_tar(self, source):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tar = root / 'tar'
            tar.write_text('#!/usr/bin/env python3\n' + textwrap.dedent(source))
            tar.chmod(0o755)
            output = root / 'snapshot.tar'
            with mock.patch.dict(os.environ, {'PATH': str(root) + os.pathsep + os.defpath}):
                yield root, output

    def test_archive_hash_and_overwrite_refusal(self):
        for root, output in self.fake_tar('import sys\nsys.stdout.buffer.write(b"snapshot bytes")\n'):
            result = snapshot.write_archive(None, {}, output, 10)
            self.assertEqual(output.read_bytes(), b'snapshot bytes')
            self.assertEqual(result['sha256'], hashlib.sha256(b'snapshot bytes').hexdigest())
            with self.assertRaisesRegex(RuntimeError, 'Refusing to overwrite'):
                snapshot.write_archive(None, {}, output, 10)

    def test_pause_budget_removes_partial_archive(self):
        source = 'import sys,time\nsys.stdout.buffer.write(b"x"*1048576)\nsys.stdout.flush()\ntime.sleep(5)\n'
        for root, output in self.fake_tar(source):
            with self.assertRaisesRegex(TimeoutError, 'Pause budget exceeded'):
                snapshot.write_archive(None, {}, output, 1)
            self.assertFalse(output.exists())
            self.assertFalse(Path(str(output) + '.partial').exists())


if __name__ == '__main__':
    unittest.main()
