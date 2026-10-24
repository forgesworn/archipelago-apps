import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from unittest import mock
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("spry_package", ROOT / "scripts/prepare-spry-turn.py")
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class SpryPackageTests(unittest.TestCase):
    def committed_fixture(self, root, symlink=False):
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "src").mkdir()
        if symlink:
            os.symlink("../../outside-private-key", root / "src/lib.rs")
        else:
            (root / "src/lib.rs").write_text("committed source")
        subprocess.run(["git", "-C", str(root), "add", "src/lib.rs"], check=True)
        subprocess.run(["git", "-C", str(root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "synthetic source"], check=True)
        return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

    def test_git_snapshot_ignores_dirty_source_and_untracked_operator_file(self):
        with tempfile.TemporaryDirectory(prefix="archy-spry-package-") as directory:
            root = Path(directory)
            ref = self.committed_fixture(root)
            (root / "src/lib.rs").write_text("synthetic private dirty state")
            (root / "owner-secret").write_text("synthetic private secret")
            self.assertEqual(package.git_file(root, ref, "src/lib.rs"), b"committed source")
            with self.assertRaisesRegex(ValueError, "committed regular file"):
                package.git_file(root, ref, "owner-secret")

    def test_git_snapshot_refuses_committed_symlink(self):
        with tempfile.TemporaryDirectory(prefix="archy-spry-package-") as directory:
            root = Path(directory)
            ref = self.committed_fixture(root, symlink=True)
            with self.assertRaisesRegex(ValueError, "committed regular file"):
                package.git_file(root, ref, "src/lib.rs")

    def test_local_git_replacement_cannot_change_pinned_source(self):
        with tempfile.TemporaryDirectory(prefix="archy-spry-package-") as directory:
            root = Path(directory)
            ref = self.committed_fixture(root)
            blob = subprocess.check_output(["git", "-C", str(root), "rev-parse", f"{ref}:src/lib.rs"], text=True).strip()
            replacement = subprocess.check_output(["git", "-C", str(root), "hash-object", "-w", "--stdin"], input=b"replacement source").decode().strip()
            subprocess.run(["git", "-C", str(root), "replace", blob, replacement], check=True)
            control_env = {key: value for key, value in os.environ.items() if key != "GIT_NO_REPLACE_OBJECTS"}
            self.assertEqual(subprocess.check_output(["git", "-C", str(root), "show", f"{ref}:src/lib.rs"], env=control_env), b"replacement source")
            self.assertEqual(package.git_file(root, ref, "src/lib.rs"), b"committed source")

    def test_manifest_keeps_exposure_local_and_secret_owned_by_node(self):
        app = package.manifest(package.SPRY_REF)["app"]
        self.assertEqual(app["container"]["pull_policy"], "never")
        self.assertEqual(app["container"]["custom_args"][2], "127.0.0.1:3478")
        self.assertTrue(all(port["auth"] == "local" and port["bind"] == "127.0.0.1" for port in app["ports"]))
        self.assertEqual(app["container"]["generated_secrets"], [{"name": "spry-turn-rest-secret", "kind": "hex32"}])
        self.assertEqual(app["container"]["secret_env"][0]["key"], "SPRY_TURN_SECRET")
        self.assertNotIn("derived_env", app["container"])
        self.assertNotIn("volumes", app)
        self.assertNotIn("interfaces", app)

    def test_lab_uses_bounded_peer_ports_without_enabling_public_exposure(self):
        app = package.manifest(package.SPRY_REF)["app"]
        self.assertEqual(app["resources"]["memory_limit"], "128m")
        args = app["container"]["custom_args"]
        self.assertEqual(args[args.index("--relay-ports") + 1], "49160:49191")
        self.assertNotIn("--public-ip", args)
        self.assertNotIn("--tls-listen", args)
        self.assertEqual(args[args.index("--listen") + 1], "127.0.0.1:3478")

    def test_mutable_or_unreviewed_refs_fail_before_reading_source(self):
        for ref in ("main", "v0.1.0", "a" * 40, "--help"):
            with self.subTest(ref=ref), mock.patch.object(package, "git_file") as read:
                with self.assertRaises(ValueError):
                    package.committed_source(Path("unused"), ref)
                read.assert_not_called()

    def source(self, changed=None):
        data = {name: f"synthetic file {name}\n".encode() for name in package.SOURCE_FILES + package.NOTICE_FILES}
        hashes = [{"path": name, "sha256": hashlib.sha256(data[name]).hexdigest()} for name in package.SOURCE_FILES]
        data["docs/evidence/source-manifest.json"] = json.dumps({"files": hashes}).encode()
        if changed:
            data[changed] += b"unreviewed change"
        return data

    def test_source_hash_mismatch_refuses_preparation(self):
        data = self.source("src/turn.rs")
        with mock.patch.object(package, "git_file", side_effect=lambda _source, _ref, name: data[name]):
            with self.assertRaisesRegex(ValueError, "source hash differs"):
                package.committed_source(Path("unused"), package.SPRY_REF)

    def test_private_snapshot_contains_only_allowlisted_sources_and_no_operator_secrets(self):
        data = self.source()
        with tempfile.TemporaryDirectory(prefix="archy-spry-package-") as root:
            output = Path(root) / "spry-turn-lab"
            with mock.patch.object(package, "git_file", side_effect=lambda _source, _ref, name: data[name]):
                package.prepare(Path("unused"), output)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            for file in output.rglob("*"):
                if file.is_file():
                    self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            snapshot = {str(file.relative_to(output / "source")) for file in (output / "source").rglob("*") if file.is_file()}
            self.assertEqual(snapshot, set(package.SOURCE_FILES + package.NOTICE_FILES))
            self.assertEqual(yaml.safe_load((output / "manifest.yml").read_text()), package.manifest(package.SPRY_REF))
            receipt = json.loads((output / "prepared.json").read_text())
            self.assertEqual(receipt["discovery"], "disabled")
            self.assertFalse(receipt["built"] or receipt["deployed"])
            self.assertEqual(receipt["udp_relay_ports"], {"first": 49160, "last": 49191})
            self.assertEqual(receipt["public_tls"], "unconfigured")
            with mock.patch.object(package, "committed_source", return_value=data), self.assertRaises(FileExistsError):
                package.prepare(Path("unused"), output)

    def test_refuses_output_symlink_and_never_truncates_target(self):
        with tempfile.TemporaryDirectory(prefix="archy-spry-package-") as root:
            root = Path(root)
            target = root / "keep"
            target.write_text("keep me")
            link = root / "spry-turn-lab"
            os.symlink(target, link)
            with mock.patch.object(package, "committed_source", return_value=self.source()), self.assertRaises(FileExistsError):
                package.prepare(Path("unused"), link)
            self.assertEqual(target.read_text(), "keep me")

    def test_partial_preparation_is_removed_without_touching_siblings(self):
        with tempfile.TemporaryDirectory(prefix="archy-spry-package-") as root:
            root = Path(root)
            keep = root / "keep"
            keep.write_text("keep me")
            output = root / "spry-turn-lab"
            with mock.patch.object(package, "committed_source", return_value=self.source()), mock.patch.object(package, "write_private", side_effect=OSError("full")):
                with self.assertRaises(OSError):
                    package.prepare(Path("unused"), output)
            self.assertFalse(output.exists())
            self.assertEqual(keep.read_text(), "keep me")

    def test_output_directory_must_match_archy_app_id(self):
        with tempfile.TemporaryDirectory(prefix="archy-spry-package-") as root:
            output = Path(root) / "wrong-app-id"
            with self.assertRaisesRegex(ValueError, "match app.id"):
                package.prepare(Path("unused"), output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
