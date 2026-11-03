"""Private packaging boundaries; no private backend input is needed in CI."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('prepare_node', ROOT / 'scripts/prepare-kithmoot-node.py')
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class PrivatePackaging(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='kithmoot-private-package-')
        self.addCleanup(self.temporary.cleanup)
        self.bundle = Path(self.temporary.name) / 'bundle'
        self.bundle.mkdir()
        files = []
        for name in sorted(prepare.REQUIRED):
            path = self.bundle / name
            path.parent.mkdir(parents=True, exist_ok=True)
            data = ('Private fixture ' + name).encode()
            executable = name in {'kithmoot-node', 'runtime/bin/node', 'lib/kithmoot-node.mjs', 'bin/bothyd', 'bin/spry-node'}
            path.write_bytes(data); path.chmod(0o755 if executable else 0o644)
            files.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'executable': executable})
        self.release = {'v': 1, 'name': 'kithmoot-node', 'version': '0.1.0-rc.1', 'platform': 'linux-arm64',
                        'distribution': 'private-candidate', 'dependencies': [{'name': 'shelter', 'visibility': 'private'}], 'files': files}
        self.save()

    def save(self):
        (self.bundle / 'release.json').write_text(json.dumps(self.release))

    def test_inventory_detects_tampering_and_undeclared_inputs(self):
        prepare.verified_bundle(self.bundle)
        path = self.bundle / 'bin/bothyd'
        original = path.read_bytes(); path.write_bytes(b'tampered')
        with self.assertRaises(ValueError): prepare.verified_bundle(self.bundle)
        path.write_bytes(original)
        (self.bundle / 'private.key').write_bytes(b'not a release input')
        with self.assertRaises(ValueError): prepare.verified_bundle(self.bundle)

    def test_symlinks_and_writable_executables_are_refused(self):
        path = self.bundle / 'bin/bothyd'
        data = path.read_bytes(); path.unlink()
        outside = Path(self.temporary.name) / 'outside'; outside.write_bytes(data)
        path.symlink_to(outside)
        with self.assertRaises(ValueError): prepare.verified_bundle(self.bundle)
        path.unlink(); path.write_bytes(data); path.chmod(0o777)
        with self.assertRaises(ValueError): prepare.verified_bundle(self.bundle)

    def test_private_input_cannot_silently_become_public(self):
        self.release['distribution'] = 'public'; self.save()
        with self.assertRaises(ValueError): prepare.verified_bundle(self.bundle)
        self.release['distribution'] = 'private-candidate'
        self.release['dependencies'][0]['visibility'] = 'public'; self.save()
        with self.assertRaises(ValueError): prepare.verified_bundle(self.bundle)

    def test_duplicate_or_traversal_inventory_paths_are_refused(self):
        self.release['files'].append(self.release['files'][0]); self.save()
        with self.assertRaises(ValueError): prepare.verified_bundle(self.bundle)
        self.release['files'][-1] = {'path': '../outside'}; self.save()
        with self.assertRaises(ValueError): prepare.verified_bundle(self.bundle)

    def test_manifest_keeps_operator_gate_and_device_turn_auth_separate(self):
        import yaml
        app = yaml.safe_load(prepare.manifest('localhost/private-candidate:test'))['app']
        self.assertEqual(app['container']['pull_policy'], 'never')
        self.assertEqual(len(app['container']['generated_secrets']), 3)
        ports = {port['host']: port for port in app['ports']}
        self.assertEqual(ports[3753]['auth'], 'gated')
        self.assertEqual(ports[53499]['container'], 34790)
        self.assertEqual({port['host'] for port in app['ports'] if port['protocol'] == 'udp' and port['host'] != 34790}, set(range(49192, 49224)))
        self.assertFalse(any('ssl' in volume.get('source', '') for volume in app['volumes']))
        self.assertEqual(app['interfaces']['main']['protocol'], 'https')


if __name__ == '__main__': unittest.main()
