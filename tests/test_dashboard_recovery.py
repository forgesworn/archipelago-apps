import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dashboard_recovery", ROOT / "node/reset-dashboard-login.py")
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
HASH = "$argon2id$v=19$m=65536,t=3,p=4$generated-salt$generated-fixture"


class DashboardRecoveryTests(unittest.TestCase):
    def fixture(self, root):
        root.mkdir()
        bodies = {"user.json": json.dumps({"password_hash": "generated-old-hash", "totp": {"generated": "encrypted fixture"},
                  "setup_complete": True, "onboarding_complete": True, "role": "viewer", "future_field": [1, 2]}).encode(),
                  "sessions.json": b'["generated-session-hash"]', "remember_secret": b"x" * 32,
                  "device-tokens.json": b'[{"name":"generated","hash":"generated"}]'}
        for name, body in bodies.items():
            (root / name).write_bytes(body)
        (root / "identity").mkdir()
        (root / "identity/nostr_secret").write_bytes(b"generated fixture identity")
        return bodies

    def test_recovery_preserves_keys_roles_unknown_fields_and_private_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "node"
            original = self.fixture(data)
            backup = Path(directory) / "backup"
            recovery.rewrite_auth(data, backup, hashlib.sha256(original["user.json"]).hexdigest(), HASH)
            updated = json.loads((data / "user.json").read_text())
            expected = json.loads(original["user.json"])
            expected.update(password_hash=HASH, totp=None)
            self.assertEqual(updated, expected)
            self.assertEqual((data / "identity/nostr_secret").read_bytes(), b"generated fixture identity")
            self.assertEqual((data / "sessions.json").read_bytes(), b"[]\n")
            self.assertEqual((data / "device-tokens.json").read_bytes(), b"[]\n")
            self.assertNotEqual((data / "remember_secret").read_bytes(), original["remember_secret"])
            self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
            for name, body in original.items():
                self.assertEqual((backup / name).read_bytes(), body)
                self.assertEqual((backup / name).stat().st_mode & 0o777, 0o600)
                self.assertEqual((data / name).stat().st_mode & 0o777, 0o600)

    def test_changed_account_is_refused_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "node"
            original = self.fixture(data)
            backup = Path(directory) / "backup"
            with self.assertRaisesRegex(ValueError, "changed since review"):
                recovery.rewrite_auth(data, backup, "0" * 64, HASH)
            self.assertFalse(backup.exists())
            for name, body in original.items():
                self.assertEqual((data / name).read_bytes(), body)

    def test_symlink_to_outside_file_is_refused_before_backup_or_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "node"
            original = self.fixture(data)
            outside = Path(directory) / "owner-file"
            outside.write_bytes(b"keep generated fixture")
            (data / "sessions.json").unlink()
            os.symlink(outside, data / "sessions.json")
            backup = Path(directory) / "backup"
            with self.assertRaises(OSError):
                recovery.rewrite_auth(data, backup, hashlib.sha256(original["user.json"]).hexdigest(), HASH)
            self.assertFalse(backup.exists())
            self.assertEqual(outside.read_bytes(), b"keep generated fixture")
            self.assertEqual((data / "user.json").read_bytes(), original["user.json"])

    def test_partial_write_failure_restores_every_original_auth_file(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "node"
            original = self.fixture(data)
            write = recovery.atomic_write
            calls = 0
            def fail_once(*args):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("generated write failure")
                return write(*args)
            with mock.patch.object(recovery, "atomic_write", side_effect=fail_once):
                with self.assertRaises(OSError):
                    recovery.rewrite_auth(data, Path(directory) / "backup", hashlib.sha256(original["user.json"]).hexdigest(), HASH)
            for name, body in original.items():
                self.assertEqual((data / name).read_bytes(), body)

    def test_password_policy_matches_dashboard_requirements(self):
        for value in ("short", "alllowercase123!", "ALLUPPERCASE123!", "NoDigitsHere!!", "NoSpecial1234"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                recovery.validate_password(value)
        recovery.validate_password("Generated-Valid-123!")


if __name__ == "__main__":
    unittest.main()
