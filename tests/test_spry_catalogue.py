import importlib.util
from pathlib import Path
import unittest

import yaml

spec = importlib.util.spec_from_file_location('bundle_app', Path(__file__).parents[1] / 'scripts/include-bundle-app.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.manifest = yaml.safe_load((Path(__file__).parents[1] / 'apps/spry/manifest.yml').read_text())
        self.original = {'version': 2, 'registry': 'fixture.invalid', 'featured': {'id': 'existing'},
                         'apps': [{'id': 'existing', 'dockerImage': 'fixture/existing:pinned'}]}

    def test_listing_has_the_actual_installable_manifest_image(self):
        result = bundle.include(self.original, self.manifest)
        app = result['apps'][-1]
        self.assertEqual(app['id'], 'spry')
        self.assertEqual(app['title'], 'Spry')
        self.assertEqual(app['dockerImage'], self.manifest['app']['container']['image'])
        self.assertEqual(app['source'], 'forgesworn-bundle')
        self.assertNotIn('webUrl', app)

    def test_existing_catalogue_and_pins_are_preserved_without_mutation(self):
        result = bundle.include(self.original, self.manifest)
        self.assertEqual(result['apps'][0], self.original['apps'][0])
        self.assertEqual(result['featured'], self.original['featured'])
        self.assertEqual(result['registry'], self.original['registry'])
        self.assertEqual(len(self.original['apps']), 1)

    def test_repeated_build_has_one_current_spry_entry(self):
        first = bundle.include(self.original, self.manifest)
        self.assertEqual(bundle.include(first, self.manifest), first)

    def test_independent_listing_is_not_silently_replaced(self):
        self.original['apps'].append({'id': 'spry', 'dockerImage': 'fixture/independent:pinned'})
        with self.assertRaisesRegex(ValueError, 'independently supplied'):
            bundle.include(self.original, self.manifest)

    def test_unknown_app_or_unpinned_image_is_refused(self):
        for field, value in [('id', 'different'), ('image', 'ghcr.io/forgesworn/spry:latest')]:
            with self.subTest(field=field):
                manifest = yaml.safe_load(yaml.safe_dump(self.manifest))
                if field == 'id': manifest['app']['id'] = value
                else: manifest['app']['container']['image'] = value
                with self.assertRaises(ValueError): bundle.include(self.original, manifest)

    def test_invalid_catalogue_is_refused(self):
        with self.assertRaises(ValueError): bundle.include({'apps': {}}, self.manifest)


if __name__ == '__main__':
    unittest.main()
