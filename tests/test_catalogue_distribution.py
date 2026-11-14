import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'catalogue_distribution', ROOT / 'scripts/prepare-catalogue-distribution.py')
distribution = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distribution)


class CatalogueDistributionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.output = self.root / 'app-catalog.json'
        self.key = self.root / 'cosign.pub'
        self.key.write_text('generated public fixture')
        self.digest = 'a' * 64

    def tearDown(self):
        self.directory.cleanup()

    def resolved(self, image, platforms, cosign_pubkey):
        return image.split(':', 1)[0] + '@sha256:' + self.digest

    def public_fixture(self):
        return {'spry': {
            'version': '0.1.0-6b34f06-4',
            'image': f'ghcr.io/forgesworn/spry@sha256:{self.digest}',
            'manifest': {'app': {'id': 'spry', 'container': {
                'image': f'ghcr.io/forgesworn/spry@sha256:{self.digest}',
                'image_signature': f'cosign://sha256-{self.digest}.sig',
            }}},
        }}

    def test_public_manifests_are_rewritten_to_verified_digests(self):
        before = {app: (ROOT / 'apps' / app / 'manifest.yml').read_bytes()
                  for app in distribution.PUBLIC_APPS}
        with mock.patch.object(distribution, 'resolve_image', side_effect=self.resolved) as resolve:
            entries = distribution.public_entries(['linux/amd64', 'linux/arm64'], self.key)
        self.assertEqual(set(entries), set(distribution.PUBLIC_APPS))
        self.assertEqual(resolve.call_count, 3)
        for app_id, entry in entries.items():
            self.assertEqual(entry['image'], f'ghcr.io/forgesworn/{app_id}@sha256:{self.digest}')
            container = entry['manifest']['app']['container']
            self.assertEqual(container['image'], entry['image'])
            self.assertEqual(container['image_signature'], f'cosign://sha256-{self.digest}.sig')
        after = {app: (ROOT / 'apps' / app / 'manifest.yml').read_bytes()
                 for app in distribution.PUBLIC_APPS}
        self.assertEqual(before, after)

    def test_complete_candidate_has_no_install_signature_or_private_upload(self):
        oci = self.root / 'private.oci.tar.gz'
        oci.write_bytes(b'generated private OCI')
        with mock.patch.object(distribution, 'public_entries', return_value=self.public_fixture()):
            catalogue = distribution.prepare(
                self.output, ['linux/amd64'], self.key, oci, allow_private=True)
        self.assertEqual(set(catalogue['apps']), {'spry', 'kithmoot-node'})
        self.assertNotIn('signature', catalogue)
        self.assertNotIn('signed_by', catalogue)
        delivery = catalogue['apps']['kithmoot-node']['delivery']
        self.assertEqual(delivery, {
            'type': 'private-oci', 'sha256': hashlib.sha256(b'generated private OCI').hexdigest()})
        self.assertEqual(catalogue['apps']['kithmoot-node']['manifest']['app']['container']['image'],
                         distribution.KITHMOOT_IMAGE)
        self.assertEqual(json.loads(self.output.read_text()), catalogue)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o644)

    def test_private_kithmoot_requires_an_explicit_decision(self):
        oci = self.root / 'private.oci.tar.gz'
        oci.write_bytes(b'generated private OCI')
        with self.assertRaisesRegex(distribution.DistributionError, 'explicit private-OCI'):
            distribution.kithmoot_entry(oci, allow_private=False)

    def test_existing_output_is_refused_before_resolution(self):
        self.output.write_text('retain existing candidate')
        with mock.patch.object(distribution, 'public_entries') as public:
            with self.assertRaisesRegex(distribution.DistributionError, 'Refusing to replace'):
                distribution.prepare(self.output, ['linux/amd64'], self.key)
            public.assert_not_called()
        self.assertEqual(self.output.read_text(), 'retain existing candidate')

    def test_resolution_requires_every_platform_and_verified_cosign(self):
        repository = 'ghcr.io/forgesworn/spry:0.1.0-6b34f06-4'
        document = {'manifests': [
            {'platform': {'os': 'linux', 'architecture': 'amd64'}},
            {'platform': {'os': 'linux', 'architecture': 'arm64'}},
        ]}
        with mock.patch.object(distribution, 'registry_json', return_value=(document, 'sha256:' + self.digest)), \
                mock.patch.object(distribution, 'verify_image_signature') as verify:
            resolved = distribution.resolve_image(repository, ['linux/amd64', 'linux/arm64'], self.key)
        self.assertEqual(resolved, f'ghcr.io/forgesworn/spry@sha256:{self.digest}')
        verify.assert_called_once_with(resolved, self.key)
        with mock.patch.object(distribution, 'registry_json', return_value=(document, 'sha256:' + self.digest)), \
                self.assertRaisesRegex(distribution.DistributionError, 'missing platforms'):
            distribution.resolve_image(repository, ['linux/arm64', 'linux/s390x'], self.key)
        with mock.patch.object(distribution, 'registry_json', return_value=(document, 'sha256:' + self.digest)), \
                mock.patch.object(distribution, 'verify_image_signature',
                                  side_effect=distribution.DistributionError('cosign failed')):
            with self.assertRaisesRegex(distribution.DistributionError, 'cosign failed'):
                distribution.resolve_image(repository, ['linux/amd64'], self.key)

    def test_single_platform_manifest_is_not_accepted_as_multiplatform(self):
        with mock.patch.object(distribution, 'registry_json', return_value=({'config': {}}, 'sha256:' + self.digest)):
            with self.assertRaisesRegex(distribution.DistributionError, 'multi-platform'):
                distribution.resolve_image('ghcr.io/forgesworn/spry:tag', ['linux/amd64'], self.key)


if __name__ == '__main__':
    unittest.main()
