import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('retain', Path(__file__).with_name('retain-installed-recipes.py'))
retain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retain)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.old, self.new, self.out = [self.root/p for p in ('old','new','out')]
        for root in (self.old, self.new/'archipelago-runtime'):
            for app in ('private-room','overlap'):
                path=root/'apps'/app/'manifest.yml';path.parent.mkdir(parents=True)
                path.write_text(f'{root.name}:{app}')
        (self.new/'index.html').write_text('beta UI')
        (self.new/'archipelago-runtime/apps/private-room/manifest.yml').unlink()
        (self.new/'archipelago-runtime/apps/private-room').rmdir()

    def prepare(self, ids=None):
        return retain.prepare(self.old,self.new,self.out,ids or ['private-room','overlap'])

    def test_private_and_overlapping_apps_preserved_without_changing_inputs(self):
        before = retain.inventory(self.new)
        self.prepare()
        for app in ('private-room','overlap'):
            self.assertEqual((self.old/'apps'/app/'manifest.yml').read_bytes(),
                (self.out/'archipelago-runtime/apps'/app/'manifest.yml').read_bytes())
        self.assertEqual(retain.inventory(self.new), before)
        self.assertEqual((self.out/'index.html').read_text(),'beta UI')

    def test_missing_recipe_refuses_before_output(self):
        with self.assertRaises(ValueError): self.prepare(['absent'])
        self.assertFalse(self.out.exists())

    def test_symlink_refuses_before_output(self):
        (self.old/'apps/private-room/key').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.out.exists())

    def test_symlink_parent_refuses_before_output(self):
        (self.old/'apps').rename(self.old/'actual-apps')
        (self.old/'apps').symlink_to(self.old/'actual-apps', target_is_directory=True)
        with self.assertRaises(ValueError): self.prepare()
        self.assertFalse(self.out.exists())

    def test_existing_output_preserved(self):
        self.out.mkdir();(self.out/'sentinel').write_text('keep')
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual((self.out/'sentinel').read_text(),'keep')

    def test_overlapping_roots_refused(self):
        with self.assertRaises(ValueError): retain.prepare(self.old,self.new,self.new/'nested',['overlap'])

    def test_path_traversal_and_duplicate_ids_refused(self):
        for ids in [['../old'],['overlap','overlap']]:
            with self.assertRaises(ValueError): self.prepare(ids)

    def test_live_roots_refused(self):
        with self.assertRaises(ValueError): retain.prepare('/opt/archipelago',self.new,self.out,['overlap'])

    def test_private_build_context_preserved(self):
        path=self.old/'docker/private-room/Dockerfile';path.parent.mkdir(parents=True);path.write_text('FROM fixture')
        self.prepare()
        self.assertEqual((self.out/'archipelago-runtime/docker/private-room/Dockerfile').read_text(),'FROM fixture')


if __name__ == '__main__': unittest.main()
