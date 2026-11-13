import importlib.util
import json
import os
from pathlib import Path
import pwd
import stat
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("spry_relay", ROOT / "node/spry-relay.py")
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


class RelayTests(unittest.TestCase):
    def test_endpoint_refuses_private_injected_and_non_dns_inputs(self):
        for hostname, ip in (
            ("localhost", "8.8.8.8"), ("relay.local", "8.8.8.8"),
            ("relay.example.org;id", "8.8.8.8"), ("relay.example.org", "127.0.0.1"),
            ("relay.example.org", "0.0.0.0"), ("relay.example.org", "::1"),
            ("relay.example.org", "192.0.2.10"),
        ):
            with self.subTest(hostname=hostname, ip=ip), self.assertRaises(ValueError):
                relay.endpoint(hostname, ip)
        relay.endpoint("relay.example.org", "8.8.8.8")

    def test_unit_is_unlisted_bounded_and_contains_no_secret(self):
        for package in ("libpam-systemd", "dbus-user-session", "kmod", "fuse-overlayfs", "runc"):
            self.assertIn(package, relay.PACKAGES)
        unit = relay.render_unit({"hostname": "relay.example.org", "ip": "8.8.8.8"})
        self.assertIn(relay.IMAGE, unit)
        for expected in (
            "Network=host", "ReadOnly=true", "NoNewPrivileges=true", "DropCapability=ALL",
            "LogDriver=none", "--memory=128m", "--relay-ports 49160:49191",
            "--tls-listen 8.8.8.8:5349", "--max-allocations 32", "--max-connections 32",
        ):
            self.assertIn(expected, unit)
        self.assertIn('export SPRY_TURN_SECRET="$(cat /run/spry-relay/turn.secret)"', unit)
        for forbidden in (
            "SPRY_PUBLIC", "3744", "443/tcp", "--allow-loopback-peers", "network-online.target",
        ):
            self.assertNotIn(forbidden, unit)
        self.assertNotIn(relay.SECRET.read_text() if relay.SECRET.exists() else "not-a-secret", unit)

    def test_cgroup_fixture_mode_is_explicit_and_not_default(self):
        with mock.patch.dict(os.environ, {"SPRY_RELAY_TEST_NO_CGROUP": "1"}):
            unit = relay.render_unit({"hostname": "relay.example.org", "ip": "8.8.8.8"})
            self.assertNotIn("--memory", unit)
            self.assertNotIn("--cpus", unit)
            self.assertNotIn("--pids-limit", unit)
            self.assertIn("--cgroups=disabled", unit)
            self.assertIn("--runtime=crun", unit)
            self.assertIn("--storage-driver=vfs", unit)
            with mock.patch.object(relay, "run") as command, \
                    mock.patch.object(relay.os, "uname", return_value=SimpleNamespace(machine="aarch64")):
                command.side_effect = [b"", json.dumps([{
                    "Id": "sha256:image", "Architecture": "arm64",
                    "RepoDigests": ["ghcr.io/forgesworn/spry@" + relay.IMAGE.split("@", 1)[1]],
                }]).encode()]
                relay.pull_image()
            self.assertEqual(command.call_args_list[0].args[0][:3], ["podman", "--storage-driver=vfs", "pull"])
        self.assertIn("--memory=128m", relay.render_unit({"hostname": "relay.example.org", "ip": "8.8.8.8"}))
        self.assertIn("--pids-limit=128", relay.render_unit({"hostname": "relay.example.org", "ip": "8.8.8.8"}))

    def test_private_write_refuses_overwrite_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "profile.json"
            relay.private_write(target, b"first", replace=False)
            with self.assertRaises(FileExistsError):
                relay.private_write(target, b"second", replace=False)
            self.assertEqual(target.read_bytes(), b"first")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            link = Path(directory) / "link"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                relay.private_write(link, b"changed")

    def test_certificate_mismatch_is_refused_before_copy(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(relay, "TLS", Path(directory) / "tls"), \
                mock.patch.object(relay, "run", side_effect=[b"", b"", b"cert", b"different"]):
            with self.assertRaises(ValueError):
                relay.copy_certificate({"hostname": "relay.example.org"}, pwd.getpwnam("root"))
            self.assertFalse((Path(directory) / "tls/fullchain.pem").exists())

    def test_profile_is_opaque_expiring_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(relay, "STATE", Path(directory) / "state.json"), \
                mock.patch.object(relay, "run", return_value=b'{"username":"opaque","credential":"secret"}') as command:
            relay.STATE.write_text(json.dumps({
                "schema": 1, "app": relay.APP, "hostname": "relay.example.org", "ip": "8.8.8.8",
                "status": "active", "rules_added": [],
            }))
            output = Path(directory) / "device.json"
            relay.profile(SimpleNamespace(output=output, ttl=3600))
            value = json.loads(output.read_text())
            self.assertEqual(value["urls"], [
                "turn:relay.example.org:3478?transport=udp",
                "turn:relay.example.org:3478?transport=tcp",
                "turns:relay.example.org:5349?transport=tcp",
            ])
            args = command.call_args.args[0]
            label = args[args.index("--label") + 1]
            self.assertRegex(label, r"^[0-9a-f]{24}$")
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            with self.assertRaises(ValueError):
                relay.profile(SimpleNamespace(output=output, ttl=3600))

    def test_deactivate_removes_only_recorded_rules_and_preserves_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.json"
            secret = root / "turn.secret"
            secret.write_text("generated-transport-secret\n")
            state.write_text(json.dumps({
                "schema": 1, "app": relay.APP, "hostname": "relay.example.org", "ip": "8.8.8.8",
                "status": "active", "rules_added": ["80/tcp", "3478/udp"],
            }))
            with mock.patch.object(relay, "STATE", state), \
                    mock.patch.object(relay, "HOOK", root / "hook"), \
                    mock.patch.object(relay, "SECRET", secret), \
                    mock.patch.object(relay, "run") as command:
                relay.HOOK.write_text("fixture")
                relay.deactivate()
            self.assertEqual(secret.read_text(), "generated-transport-secret\n")
            self.assertFalse(relay.HOOK.exists())
            calls = [call.args[0] for call in command.call_args_list]
            self.assertEqual(calls[-2:], [
                ["ufw", "--force", "delete", "allow", "3478/udp"],
                ["ufw", "--force", "delete", "allow", "80/tcp"],
            ])
            self.assertEqual(json.loads(state.read_text())["status"], "rolled-back")

    def test_deactivate_continues_after_firewall_error(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            state.write_text(json.dumps({
                "schema": 1, "app": relay.APP, "hostname": "relay.example.org", "ip": "8.8.8.8",
                "status": "active", "rules_added": ["80/tcp", "3478/udp"],
            }))
            with mock.patch.object(relay, "STATE", state), \
                    mock.patch.object(relay, "HOOK", Path(directory) / "hook"), \
                    mock.patch.object(relay, "run", side_effect=[b"", RuntimeError("stop"), b"", RuntimeError("delete")]):
                with self.assertRaises(ValueError):
                    relay.deactivate()
            self.assertEqual(json.loads(state.read_text())["status"], "rollback-error")

    def test_runtime_verification_checks_arguments_isolation_and_secret(self):
        config = {"hostname": "relay.example.org", "ip": "8.8.8.8"}
        inspection = [{
            "State": {"Running": True},
            "Config": {
                "Entrypoint": ["/bin/sh"],
                "Cmd": ["-c", relay.SHELL_COMMAND, relay.APP, *relay.relay_args(config)],
            },
            "HostConfig": {
                "ReadonlyRootfs": True, "NetworkMode": "host", "LogConfig": {"Type": "none"},
                "CapDrop": ["CAP_CHOWN", "CAP_DAC_OVERRIDE"], "SecurityOpt": ["no-new-privileges"],
                "Memory": 134217728,
                "NanoCpus": 1000000000, "PidsLimit": 128,
            },
        }]
        process = "CapInh:\t0\nCapPrm:\t0\nCapEff:\t0\nCapBnd:\t0\nCapAmb:\t0\nNoNewPrivs:\t1\n"
        def execute(*args, **kwargs):
            return process.encode() if args[0][1] == "exec" else json.dumps(inspection).encode()
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(relay, "SECRET", Path(directory) / "secret"), \
                mock.patch.object(relay, "run", side_effect=execute):
            relay.SECRET.write_text("x" * 64 + "\n")
            for field in ("Memory", "NanoCpus", "PidsLimit"):
                expected = inspection[0]["HostConfig"].pop(field)
                with self.subTest(field=field), self.assertRaises(ValueError):
                    relay.verify_runtime(config)
                inspection[0]["HostConfig"][field] = expected
            result = relay.verify_runtime(config)
            process = process.replace("CapEff:\t0", "CapEff:\t1")
            with self.assertRaises(ValueError):
                relay.verify_runtime(config)
        self.assertTrue(result["capabilities_zero"])
        self.assertTrue(result["secret_absent_from_inspect"])
        self.assertFalse(result["public_credential_endpoint"])


if __name__ == "__main__":
    unittest.main()
