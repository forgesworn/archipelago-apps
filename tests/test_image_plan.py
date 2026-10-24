"""Exercise immutable image decisions against real, generated Git histories."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ImagePlanTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='archy-image-plan-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        self.env.pop('GITHUB_OUTPUT', None)
        for name in ['scripts/lib', 'apps/wildbloom', 'bin']:
            (self.root / name).mkdir(parents=True)
        for name in ['scripts/image-plan.sh', 'scripts/lib/app-image.bash']:
            shutil.copy2(ROOT / name, self.root / name)
        docker = self.root / 'bin/docker'
        docker.write_text('''#!/bin/sh
[ "$1" = manifest ] && [ "$2" = inspect ] || exit 2
if [ "${FIXTURE_REGISTRY_MODE:-found}" = error ]; then
  echo 'TLS verification failed' >&2
  exit 1
fi
echo '{}'
''')
        docker.chmod(0o700)
        self.env['PATH'] = str(self.root / 'bin') + os.pathsep + self.env['PATH']
        self.git('init', '-q')
        self.git('checkout', '-qb', 'main')
        self.inputs('1', 1)
        self.base = self.commit('initial generated inputs')
        self.git('update-ref', 'refs/remotes/origin/main', self.base)

    def git(self, *args):
        return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null',
            '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
            *args], cwd=self.root, env=self.env, stderr=subprocess.PIPE, text=True).strip()

    def inputs(self, marker, revision):
        (self.root / 'PINS').write_text(f'WILDBLOOM_REF={marker * 40}\nWILDBLOOM_PKG_REV={revision}\n')
        (self.root / 'apps/wildbloom/Dockerfile').write_text(f'FROM scratch\n# generated {marker}\n')

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def plan(self, before):
        return subprocess.run(['bash', 'scripts/image-plan.sh', 'wildbloom', before, 'push'],
            cwd=self.root, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def merge_published_main(self):
        self.git('checkout', '-qb', 'feature')
        (self.root / 'feature.txt').write_text('unrelated generated work\n')
        before = self.commit('feature work')
        self.git('checkout', '-q', 'main')
        self.inputs('2', 2)
        published = self.commit('published main inputs')
        self.git('update-ref', 'refs/remotes/origin/main', published)
        self.git('checkout', '-q', 'feature')
        self.git('merge', '--no-edit', 'main')
        return before

    def test_incoming_published_main_is_retested_without_replacing_its_tag(self):
        result = self.plan(self.merge_published_main())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('build=true\n', result.stdout)
        self.assertIn('push=false\n', result.stdout)

    def test_changed_published_main_still_requires_a_new_revision(self):
        self.inputs('2', 1)
        head = self.commit('changed main inputs')
        self.git('update-ref', 'refs/remotes/origin/main', head)
        result = self.plan(self.base)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('bump', result.stdout)

    def test_a_branch_cannot_change_the_inherited_published_inputs(self):
        before = self.merge_published_main()
        (self.root / 'apps/wildbloom/Dockerfile').write_text('FROM scratch\n# changed on branch\n')
        self.commit('change inherited image')
        self.assertNotEqual(self.plan(before).returncode, 0)

    def test_an_unchanged_published_image_is_not_rebuilt(self):
        self.git('checkout', '-qb', 'feature')
        (self.root / 'feature.txt').write_text('unrelated generated work\n')
        self.commit('feature work')
        result = self.plan(self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('build=false\n', result.stdout)
        self.assertIn('push=false\n', result.stdout)

    def test_registry_uncertainty_never_authorises_publishing(self):
        self.env['FIXTURE_REGISTRY_MODE'] = 'error'
        result = self.plan(self.base)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('push=true', result.stdout)


if __name__ == '__main__':
    unittest.main()
