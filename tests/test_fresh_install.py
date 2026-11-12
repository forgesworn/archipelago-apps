"""Exercise the installer refusal before it can read executable bundle input."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


INSTALLER = Path(__file__).parents[1] / "node/install-lite.sh"
MARKERS = (
    "/var/lib/archipelago", "/etc/archipelago", "/opt/archipelago",
    "/usr/local/bin/archipelago", "/etc/systemd/system/archipelago.service",
)


class FreshInstallTests(unittest.TestCase):
    def run_fixture(self, marker=None, dangling=False, runtime="podman"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = INSTALLER.read_text()
            # Redirect fixed host paths only in this generated test copy.
            # Nothing runs with root authority or against host installation paths.
            for path in sorted(MARKERS, key=len, reverse=True):
                script = script.replace(path, str(root / path.lstrip("/")))
            installer = root / "install.sh"
            installer.write_text(script)
            commands = root / "commands"
            commands.mkdir()
            identity = commands / "id"
            identity.write_text("#!/bin/sh\necho 0\n")
            identity.chmod(0o755)
            bundle = root / "bundle"
            bundle.mkdir()
            sentinel = root / "bundle-read"
            (bundle / "PINS").write_text(f"touch '{sentinel}'\nexit 23\n")
            if marker:
                existing = root / marker.lstrip("/")
                existing.parent.mkdir(parents=True, exist_ok=True)
                if dangling:
                    existing.symlink_to(root / "missing")
                else:
                    existing.mkdir()
            result = subprocess.run(
                ["bash", str(installer), str(bundle), runtime],
                env=dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"]),
                capture_output=True, text=True, timeout=5,
            )
            return result, sentinel.exists()

    def test_each_existing_state_marker_refuses_both_runtimes_before_bundle(self):
        for runtime in ("podman", "docker"):
            for marker in MARKERS:
                with self.subTest(runtime=runtime, marker=marker):
                    result, read = self.run_fixture(marker, runtime=runtime)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("Fresh installation only", result.stderr)
                    self.assertFalse(read)

    def test_dangling_state_symlink_also_refuses(self):
        result, read = self.run_fixture("/var/lib/archipelago", dangling=True)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(read)

    def test_fresh_host_reaches_bundle_validation(self):
        result, read = self.run_fixture()
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertTrue(read)


if __name__ == "__main__":
    unittest.main()
