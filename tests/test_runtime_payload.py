import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage_runtime', ROOT / 'scripts/stage-runtime-payload.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimePayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source, self.dest = root / 'source', root / 'frontend'
        (self.source / 'scripts').mkdir(parents=True)
        upstream = Path(os.environ['ARCHY_SOURCE']) / 'scripts/release_payload.py'
        shutil.copyfile(upstream, self.source / 'scripts/release_payload.py')
        (self.source / 'scripts/helper.py').write_text('patched-helper\n')
        (self.source / 'image-recipe/configs').mkdir(parents=True)
        (self.source / 'image-recipe/configs/service.conf').write_text('patched-config\n')
        (self.dest / 'archipelago-runtime/scripts').mkdir(parents=True)
        (self.dest / 'archipelago-runtime/scripts/obsolete.py').write_text('obsolete')
        (self.dest / 'index.html').write_text('dashboard')
        (self.dest / 'archipelago-runtime/radio.bin').write_bytes(b'upstream-binary')

    def stage(self):
        module.stage(self.source, self.dest, '2.1.0-beta.2', 'a' * 40, 'b' * 64)

    def test_stages_patched_helpers_and_exact_declaration_preserving_binaries(self):
        self.stage()
        runtime = self.dest / 'archipelago-runtime'
        self.assertFalse((runtime / 'scripts/obsolete.py').exists())
        self.assertEqual((runtime / 'scripts/helper.py').read_text(), 'patched-helper\n')
        self.assertEqual((runtime / 'radio.bin').read_bytes(), b'upstream-binary')
        first = (runtime / 'RELEASE-PAYLOAD.json').read_bytes()
        self.stage()
        self.assertEqual(first, (runtime / 'RELEASE-PAYLOAD.json').read_bytes())
        (self.source / 'scripts/helper.py').write_text('new-helper\n')
        self.stage()
        self.assertNotEqual(first, (runtime / 'RELEASE-PAYLOAD.json').read_bytes())
        provenance = json.loads((runtime / 'FORGESWORN-BUNDLE.json').read_text())
        self.assertEqual(provenance['patches_sha256'], 'b' * 64)

    def test_symlink_source_is_rejected_before_replacing_payload(self):
        (self.source / 'scripts/escape').symlink_to(self.dest / 'index.html')
        with self.assertRaises(ValueError):
            self.stage()
        self.assertTrue((self.dest / 'archipelago-runtime/scripts/obsolete.py').exists())

    def test_symlink_destination_cannot_replace_external_directory(self):
        runtime = self.dest / 'archipelago-runtime'
        shutil.rmtree(runtime / 'scripts')
        (runtime / 'scripts').symlink_to(self.source / 'scripts', target_is_directory=True)
        with self.assertRaises(ValueError):
            self.stage()
        self.assertEqual((self.source / 'scripts/helper.py').read_text(), 'patched-helper\n')


if __name__ == '__main__':
    unittest.main()
