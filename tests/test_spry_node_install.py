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
    def test_private_logging_refuses_operator_policy_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "10-private-transport.conf"
            target.write_text("generated existing operator policy")
            with mock.patch.object(installer, "LOGGING_DROPIN", root), mock.patch.object(installer, "command") as command:
                with self.assertRaisesRegex(installer.Refused, "refusing overwrite"):
                    installer.configure_private_logging()
                command.assert_not_called()
            self.assertEqual(target.read_text(), "generated existing operator policy")

    def test_private_logging_refuses_symlink_without_changing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "owner-file"
            outside.write_text("generated existing owner data")
            (root / "dropin").mkdir()
            os.symlink(outside, root / "dropin/10-private-transport.conf")
            with mock.patch.object(installer, "LOGGING_DROPIN", root / "dropin"), mock.patch.object(installer, "command") as command:
                with self.assertRaises(installer.Refused):
                    installer.configure_private_logging()
                command.assert_not_called()
            self.assertEqual(outside.read_text(), "generated existing owner data")

    def test_signer_approval_verifies_full_session_without_password_login(self):
        dashboard = mock.Mock()
        challenge = {"attempt_id": "a" * 32, "code": "1234"}
        dashboard.call.side_effect = [True, challenge, {"status": "pending"}, {"status": "approved"}, {}]
        notify = mock.Mock()
        installer.authenticate_signer(dashboard, notify, pause=lambda _: None)
        notify.assert_called_once_with("1234")
        self.assertEqual(dashboard.call.call_args_list, [
            mock.call("auth.login.signer.available"), mock.call("auth.login.signer.start"),
            mock.call("auth.login.signer.finish", {"attempt_id": "a" * 32}),
            mock.call("auth.login.signer.finish", {"attempt_id": "a" * 32}),
            mock.call("server.get-state")])

    def test_signer_unavailable_or_denied_never_falls_back_or_restarts(self):
        for replies in ([False], [True, {"attempt_id": "a" * 32, "code": "1234"}, installer.Refused("denied")]):
            dashboard = mock.Mock()
            dashboard.call.side_effect = replies
            with self.assertRaises(installer.Refused):
                installer.authenticate_signer(dashboard, mock.Mock(), pause=lambda _: None)
            methods = [args.args[0] for args in dashboard.call.call_args_list]
            self.assertNotIn("auth.login", methods)
            self.assertNotIn("server.get-state", methods)
            self.assertLessEqual(methods.count("auth.login.signer.start"), 1)

    def test_signer_pending_poll_is_bounded_and_does_not_confirm_session(self):
        dashboard = mock.Mock()
        dashboard.call.side_effect = [True, {"attempt_id": "a" * 32, "code": "1234"}, {"status": "pending"}, {"status": "pending"}]
        with self.assertRaisesRegex(installer.Refused, "timed out"):
            installer.authenticate_signer(dashboard, mock.Mock(), max_polls=2, pause=lambda _: None)
        self.assertEqual(dashboard.call.call_count, 4)

    def test_malformed_signer_challenge_refuses_before_poll_or_display(self):
        for challenge in ({"attempt_id": "bad;cookie", "code": "1234"}, {"attempt_id": "a" * 32, "code": "123456"}, None):
            dashboard = mock.Mock()
            dashboard.call.side_effect = [True, challenge]
            notify = mock.Mock()
            with self.assertRaisesRegex(installer.Refused, "Unexpected"):
                installer.authenticate_signer(dashboard, notify)
            notify.assert_not_called()
            self.assertEqual(dashboard.call.call_count, 2)

    def test_existing_full_login_does_not_prompt_for_a_code(self):
        dashboard = mock.Mock()
        dashboard.call.side_effect = [None, {}]
        prompt = mock.Mock()
        self.assertFalse(installer.authenticate(dashboard, "generated fixture", prompt))
        prompt.assert_not_called()
        self.assertEqual(dashboard.call.call_args_list, [
            mock.call("auth.login", {"password": "generated fixture"}), mock.call("server.get-state")])

    def test_password_rejection_does_not_request_or_send_a_2fa_code(self):
        dashboard = mock.Mock()
        dashboard.call.side_effect = installer.Refused("Dashboard RPC refused auth.login")
        prompt = mock.Mock(return_value="123456")
        with self.assertRaises(installer.Refused):
            installer.authenticate(dashboard, "generated fixture", prompt)
        prompt.assert_not_called()
        dashboard.call.assert_called_once_with("auth.login", {"password": "generated fixture"})

    def test_pending_2fa_session_cannot_continue_without_code(self):
        dashboard = mock.Mock()
        dashboard.call.return_value = {"requires_totp": True}
        with self.assertRaisesRegex(installer.Refused, "requires 2FA"):
            installer.authenticate(dashboard, "generated fixture")
        dashboard.call.assert_called_once_with("auth.login", {"password": "generated fixture"})

    def test_2fa_requires_current_code_and_confirms_full_session(self):
        for code in ("123456", "long-generated-authenticator-seed", "12345", "１２３４５６"):
            dashboard = mock.Mock()
            dashboard.call.side_effect = [{"requires_totp": True}, {}, {}]
            prompt = mock.Mock(return_value=code)
            with self.subTest(valid=code == "123456"):
                if code == "123456":
                    self.assertTrue(installer.authenticate(dashboard, "generated fixture", prompt))
                    self.assertEqual(dashboard.call.call_args_list, [
                        mock.call("auth.login", {"password": "generated fixture"}),
                        mock.call("auth.login.totp", {"code": "123456"}),
                        mock.call("server.get-state")])
                else:
                    with self.assertRaisesRegex(installer.Refused, "six-digit"):
                        installer.authenticate(dashboard, "generated fixture", prompt)
                    self.assertEqual(dashboard.call.call_count, 1)

    def test_2fa_refusal_does_not_confirm_a_full_session(self):
        dashboard = mock.Mock()
        dashboard.call.side_effect = [{"requires_totp": True}, installer.Refused("Dashboard RPC refused auth.login.totp")]
        with self.assertRaises(installer.Refused):
            installer.authenticate(dashboard, "generated fixture", lambda _: "123456")
        self.assertEqual(dashboard.call.call_count, 2)

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
