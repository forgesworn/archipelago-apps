"""Real filesystem swaps and refusal/rollback checks; generated fixtures only."""
import hashlib
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "node_bundle_update", Path(__file__).parents[1] / "scripts/update-node-bundle.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = update.Paths(self.root)
        self.write(self.paths.binary, b"generated old backend")
        self.write(self.paths.web / "index.html", b"old dashboard")
        self.write(self.paths.lifecycle, b"")
        runtime = self.paths.web / "archipelago-runtime"
        self.write(runtime / "apps/spry/manifest.yml", b"old spry")
        self.write(runtime / "apps/fixture/manifest.yml", b"older private configuration")
        self.write(runtime / "scripts/fixture-helper", b"private runtime customisation")
        self.write(self.paths.apps / "fixture/manifest.yml", b"current private configuration")
        self.write(self.paths.apps / "spry/manifest.yml", b"old live spry")
        self.sentinel = self.root / "var/lib/archipelago/identities/generated-fixture"
        self.write(self.sentinel, b"generated identity sentinel")
        self.stage = self.root / "stage"
        self.binary = self.stage / "archipelago"
        self.web = self.stage / "web-ui"
        self.write(self.binary, b"generated new backend")
        self.write(self.web / "index.html", b"new dashboard")
        self.write(self.web / "catalog.json", b"generated catalogue with spry")
        self.write(self.web / "archipelago-runtime/apps/spry/manifest.yml", update.IMAGE.encode())
        self.old_sha = update.digest(self.paths.binary)
        self.new_sha = update.digest(self.binary)
        self.addCleanup(patch.stopall)
        patch.object(update, "OLD_BACKEND", self.old_sha).start()
        patch.object(update, "BACKEND", ("fixture", self.new_sha, self.binary.stat().st_size)).start()
        self.actions = []

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def control(self, action):
        self.actions.append(action)
        if action == "start":
            # Like the real bootstrap, startup promotes the frontend payload.
            shutil.rmtree(self.paths.apps)
            shutil.copytree(self.paths.web / "archipelago-runtime/apps", self.paths.apps)
            # The installer must release the lifecycle lock before startup.
            with update.locked(self.paths.lifecycle):
                pass

    def apply(self, control=None, check=None):
        return update.install(self.paths, self.binary, self.web, os.getuid(), os.getgid(),
                              control=control or self.control,
                              check=check or (lambda: True), timeout=0.02)

    def test_success_preserves_private_configuration_and_identity(self):
        result = self.apply()
        self.assertEqual(self.actions, ["stop", "start"])
        self.assertEqual(update.digest(self.paths.binary), self.new_sha)
        self.assertEqual((self.paths.web / "index.html").read_bytes(), b"new dashboard")
        self.assertEqual((self.paths.apps / "fixture/manifest.yml").read_bytes(), b"current private configuration")
        self.assertEqual((self.paths.apps / "spry/manifest.yml").read_text(), update.IMAGE)
        self.assertEqual(self.sentinel.read_bytes(), b"generated identity sentinel")
        self.assertEqual((self.paths.web / "archipelago-runtime/scripts/fixture-helper").read_bytes(), b"private runtime customisation")
        backup = Path(result["backup"])
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual(update.digest(backup / "archipelago"), self.old_sha)
        self.assertTrue(json.loads((backup / "receipt.json").read_text())["updated"])

    def assert_restored(self):
        self.assertEqual(update.digest(self.paths.binary), self.old_sha)
        self.assertEqual((self.paths.web / "index.html").read_bytes(), b"old dashboard")
        self.assertEqual((self.paths.apps / "fixture/manifest.yml").read_bytes(), b"current private configuration")
        self.assertEqual((self.paths.apps / "spry/manifest.yml").read_bytes(), b"old live spry")
        self.assertEqual(self.sentinel.read_bytes(), b"generated identity sentinel")
        self.assertEqual(self.actions[-1], "start")

    def test_failed_health_restores_bundle_and_live_app_definitions(self):
        with self.assertRaisesRegex(update.Refused, "previous bundle restored"):
            self.apply(check=lambda: update.digest(self.paths.binary) == self.old_sha)
        self.assert_restored()

    def test_failed_service_start_restores_bundle(self):
        def control(action):
            if action == "start" and update.digest(self.paths.binary) == self.new_sha:
                raise RuntimeError("generated service-start failure")
            self.control(action)
        with self.assertRaisesRegex(update.Refused, "previous bundle restored"):
            self.apply(control=control)
        self.assert_restored()

    def test_failed_catalogue_promotion_rolls_back(self):
        def control(action):
            self.control(action)
            if action == "start" and update.digest(self.paths.binary) == self.new_sha:
                (self.paths.apps / "spry/manifest.yml").write_text("wrong package")
        with self.assertRaisesRegex(update.Refused, "previous bundle restored"):
            self.apply(control=control)
        self.assert_restored()

    def test_busy_lifecycle_refuses_before_service_stop(self):
        with update.locked(self.paths.lifecycle), self.assertRaisesRegex(update.Refused, "busy"):
            self.apply()
        self.assertEqual(self.actions, [])
        self.assertEqual(update.digest(self.paths.binary), self.old_sha)

    def test_unknown_backend_is_refused(self):
        self.paths.binary.write_bytes(b"unrecognised custom backend")
        with self.assertRaisesRegex(update.Refused, "unknown or cross-version"):
            update.inspect(self.paths)

    def test_repeating_current_update_neither_downloads_nor_restarts(self):
        self.paths.binary.write_bytes(self.binary.read_bytes())
        self.write(self.paths.web / "index.html", b"new dashboard")
        self.write(self.paths.web / "catalog.json", b"generated catalogue with spry")
        for path in [self.paths.apps / "spry/manifest.yml",
                     self.paths.web / "archipelago-runtime/apps/spry/manifest.yml"]:
            self.write(path, update.IMAGE.encode())
        with patch.object(update, "INDEX_SHA", hashlib.sha256(b"new dashboard").hexdigest()), \
             patch.object(update, "CATALOGUE_SHA", hashlib.sha256(b"generated catalogue with spry").hexdigest()), \
             patch.object(update, "SPRY_SHA", hashlib.sha256(update.IMAGE.encode()).hexdigest()), \
             patch.object(update, "Paths", return_value=self.paths), \
             patch.object(update.os, "geteuid", return_value=0), \
             patch.object(update, "healthy", return_value=True), \
             patch.object(update, "download") as download, \
             patch.object(update, "service") as service, \
             patch("sys.argv", ["updater", "--apply"]), patch("builtins.print"):
            update.main()
        download.assert_not_called()
        service.assert_not_called()

    def test_current_dashboard_without_expected_store_listing_needs_update(self):
        self.apply()
        with patch.object(update, "INDEX_SHA", update.digest(self.paths.web / "index.html")), \
             patch.object(update, "SPRY_SHA", update.digest(self.paths.apps / "spry/manifest.yml")), \
             patch.object(update, "CATALOGUE_SHA", update.digest(self.paths.web / "catalog.json")):
            self.assertTrue(update.inspect(self.paths)["alreadyCurrent"])
            (self.paths.web / "catalog.json").write_text("generated old catalogue")
            self.assertFalse(update.inspect(self.paths)["alreadyCurrent"])

    def test_symlinked_layout_is_refused(self):
        original = self.paths.web
        moved = original.with_name("other-web")
        original.rename(moved)
        original.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(update.Refused, "directory-based"):
            update.inspect(self.paths)

    def test_low_disk_is_refused(self):
        with patch.object(update.shutil, "disk_usage", return_value=shutil._ntuple_diskusage(100, 99, 1)):
            with self.assertRaisesRegex(update.Refused, "2 GiB"):
                update.inspect(self.paths)

    def test_damaged_download_is_refused(self):
        target = self.root / "download"
        target.write_bytes(b"generated damaged payload")
        with patch.object(update.subprocess, "run"), self.assertRaisesRegex(update.Refused, "SHA-256"):
            update.download(("fixture", hashlib.sha256(b"expected").hexdigest(), 8), target)
        self.assertEqual(self.actions, [])

    def test_damaged_staged_backend_refuses_before_stopping(self):
        self.binary.write_bytes(b"generated corrupt staged backend")
        with self.assertRaisesRegex(update.Refused, "Staged backend SHA-256"):
            self.apply()
        self.assertEqual(self.actions, [])
        self.assertEqual(update.digest(self.paths.binary), self.old_sha)

    def make_archive(self, extra=None):
        archive = self.root / "frontend.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name, body in [("./index.html", b"generated dashboard"),
                               ("./archipelago-runtime/apps/spry/manifest.yml", update.IMAGE.encode())]:
                info = tarfile.TarInfo(name)
                info.size = len(body)
                info.mode = 0o4755
                tar.addfile(info, io.BytesIO(body))
            if extra is not None:
                tar.addfile(extra)
        return archive

    def test_extract_accepts_fixture_and_strips_privileged_modes(self):
        destination = self.root / "extracted"
        update.extract(self.make_archive(), destination)
        self.assertEqual((destination / "index.html").stat().st_mode & 0o7777, 0o755)

    def test_archive_traversal_absolute_links_and_special_files_are_refused(self):
        cases = [("../escape", tarfile.REGTYPE), ("/escape", tarfile.REGTYPE),
                 ("link", tarfile.SYMTYPE), ("hard", tarfile.LNKTYPE), ("fifo", tarfile.FIFOTYPE)]
        for index, (name, kind) in enumerate(cases):
            with self.subTest(name=name):
                member = tarfile.TarInfo(name)
                member.type = kind
                member.linkname = "../../escape"
                with self.assertRaisesRegex(update.Refused, "Unsafe"):
                    update.extract(self.make_archive(member), self.root / f"refused-{index}")
        self.assertFalse((self.root.parent / "escape").exists())

    def test_oversized_archive_is_refused_before_reading_member_data(self):
        member = tarfile.TarInfo("huge")
        member.size = 3 * 1024**3
        archive = self.root / "oversized.tar.gz"
        with gzip.open(archive, "wb") as output:
            output.write(member.tobuf() + bytes(1024))
        with self.assertRaisesRegex(update.Refused, "oversized"):
            update.extract(archive, self.root / "oversized")

    def test_runtime_apps_symlink_cannot_redirect_the_new_spry(self):
        source = self.root / "malicious-runtime"
        source.mkdir()
        (source / "apps").symlink_to(self.paths.apps)
        with self.assertRaisesRegex(update.Refused, "symlinked apps"):
            update.overlay(source, self.web / "archipelago-runtime", {"apps/spry"})
        self.assertEqual((self.paths.apps / "spry/manifest.yml").read_bytes(), b"old live spry")


if __name__ == "__main__":
    unittest.main()
