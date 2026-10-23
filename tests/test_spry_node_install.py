import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("spry_install", ROOT / "node/install-spry-lab.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallBoundaryTests(unittest.TestCase):
    def test_password_symlink_is_refused_without_reading_target(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            target = path / "owner-file"
            target.write_text("generated fixture")
            os.symlink(target, path / "password")
            with self.assertRaises(OSError):
                installer.private_password(path / "password")
            self.assertEqual(target.read_text(), "generated fixture")

    def test_password_requires_root_ownership_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            path.write_text("generated fixture")
            for uid, mode in [(1000, 0o100600), (0, 0o100644), (0, 0o100666)]:
                with self.subTest(uid=uid, mode=mode), mock.patch.object(installer.os, "fstat",
                        return_value=SimpleNamespace(st_uid=uid, st_mode=mode)):
                    with self.assertRaises(ValueError):
                        installer.private_password(path)

    def test_password_bounds_and_whitespace_preservation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "password"
            with mock.patch.object(installer.os, "fstat", return_value=SimpleNamespace(st_uid=0, st_mode=0o100600)):
                for body in ("", "\n", "x" * 4097):
                    path.write_text(body)
                    with self.assertRaises(ValueError):
                        installer.private_password(path)
                path.write_text("  generated fixture  \n")
                self.assertEqual(installer.private_password(path), "  generated fixture  ")

    def test_only_reviewed_manifest_bytes_are_accepted(self):
        spec = importlib.util.spec_from_file_location("spry_prepare", ROOT / "scripts/prepare-spry-turn.py")
        package = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(package)
        body = installer.yaml.safe_dump(package.manifest(package.SPRY_REF), sort_keys=False).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.yml"
            path.write_bytes(body)
            self.assertEqual(hashlib.sha256(body).hexdigest(), installer.MANIFEST_SHA256)
            installer.verified_manifest(path, installer.MANIFEST_SHA256)
            for changed in (body.replace(b"127.0.0.1", b"0.0.0.0"),
                            body.replace(b"readonly_root: true", b"readonly_root: false"),
                            body.replace(b"kind: hex32", b"kind: hex16")):
                path.write_bytes(changed)
                # Supplying the altered file's own checksum cannot authorise it.
                with self.assertRaises(ValueError):
                    installer.verified_manifest(path, hashlib.sha256(changed).hexdigest())

    def test_dashboard_origin_refuses_insecure_or_credential_bearing_urls(self):
        for origin in ("http://node.example", "https://owner:secret@node.example", "https://node.example/rpc",
                       "https://node.example/?token=generated", "https://node.example/#generated"):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                installer.Dashboard(origin)


if __name__ == "__main__":
    unittest.main()
