import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("discovery", ROOT / "scripts/configure-wildbloom-discovery.py")
discovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(discovery)


class DiscoveryConfigTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((ROOT / "docs/wildbloom-discovery.example.json").read_text())
        self.manifest = yaml.safe_load((ROOT / "apps/wildbloom-node/manifest.yml").read_text())

    def paid_manifest(self):
        m = copy.deepcopy(self.manifest)
        m["app"]["environment"] += ["WILDBLOOM_CHECKOUT_PROFILE=/data/operator/checkout-profile.json",
                                    "WILDBLOOM_QUOTA_BYTES=1000"]
        return m

    def test_default_preparation_preserves_manifest_and_enables_nothing(self):
        profile, manifest = discovery.build(self.settings, self.manifest)
        self.assertEqual(manifest, self.manifest)
        self.assertIsNone(profile["announcement"])
        self.assertEqual(profile["origins"], ["https://storage.example:3742/"])

    def test_inspection_preserves_sales_quota_and_adds_separate_private_volume(self):
        original = self.paid_manifest()
        profile, manifest = discovery.build(self.settings, original, inspection=True)
        self.assertIsNone(profile["announcement"])
        env = manifest["app"]["environment"]
        self.assertIn("WILDBLOOM_QUOTA_BYTES=1000", env)
        self.assertIn("WILDBLOOM_CHECKOUT_PROFILE=/data/operator/checkout-profile.json", env)
        self.assertIn("WILDBLOOM_SERVICE_PROFILE=/service/service-profile.json", env)
        self.assertEqual(manifest["app"]["volumes"][-1], discovery.SERVICE_VOLUME)
        self.assertNotIn("WILDBLOOM_SERVICE_PROFILE=/service/service-profile.json", original["app"]["environment"])

    def test_listing_does_not_enable_sales_or_free_shelter(self):
        with self.assertRaises(ValueError):
            discovery.build(self.settings, self.manifest, inspection=True)
        self.settings["public_services"] = ["free"]
        with self.assertRaises(ValueError):
            discovery.build(self.settings, self.manifest, inspection=True)
        profile, manifest = discovery.build(self.settings, self.manifest, inspection=True, free=True)
        env = manifest["app"]["environment"]
        self.assertIsNone(profile["announcement"])
        self.assertIn("WILDBLOOM_OPEN_SHELTER=true", env)
        self.assertIn("WILDBLOOM_DIRECT_HTTPS_MIRRORS=true", env)
        self.assertFalse(any("CHECKOUT_PROFILE" in v for v in env))

    def test_combined_profile_requires_explicit_free_enable_and_retains_sales(self):
        self.settings["public_services"] = ["paid", "free"]
        with self.assertRaises(ValueError):
            discovery.build(self.settings, self.paid_manifest(), inspection=True)
        _, manifest = discovery.build(self.settings, self.paid_manifest(), inspection=True, free=True)
        self.assertIn("WILDBLOOM_CHECKOUT_PROFILE=/data/operator/checkout-profile.json", manifest["app"]["environment"])

    def publish_settings(self):
        return {**self.settings, "publication_reviewed": True,
                "relays": [{"url": "wss://relay.example/", "addresses": ["1.1.1.1:443"]}]}

    def test_publication_requires_review_signer_and_pinned_relays(self):
        for change in ({}, {"publication_reviewed": True}, {"signer": "/data/signer"},
                       {"relays": [{"url": "wss://relay.example/", "addresses": []}]},
                       {"ttl_seconds": 600}, {"heartbeat_seconds": True}):
            settings = self.settings if not change else {**self.publish_settings(), **change}
            if change == {"publication_reviewed": True}:
                settings = {**self.settings, **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                discovery.build(settings, self.paid_manifest(), publication=True)
        profile, _ = discovery.build(self.publish_settings(), self.paid_manifest(), publication=True)
        self.assertEqual(profile["announcement"]["state_dir"], "/service/publisher")
        self.assertEqual(profile["announcement"]["signer_args"], [])
        self.assertEqual(profile["announcement"]["transport"], "direct")

    def test_refuses_private_redirectable_or_ambiguous_relay_destinations(self):
        invalid = [
            {"url": "ws://relay.example/", "addresses": ["1.1.1.1:80"]},
            {"url": "wss://user:secret@relay.example/", "addresses": ["1.1.1.1:443"]},
            {"url": "wss://relay.example/?token=secret", "addresses": ["1.1.1.1:443"]},
            {"url": "wss://relay.example/", "addresses": ["127.0.0.1:443"]},
            {"url": "wss://relay.example/", "addresses": ["[::1]:443"]},
            {"url": "wss://relay.example/", "addresses": ["[::ffff:1.1.1.1]:443"]},
            {"url": "wss://relay.example/", "addresses": ["1.1.1.1:8443"]},
            {"url": "wss://1.1.1.1/", "addresses": ["8.8.8.8:443"]},
            {"url": "wss://relay.example/", "addresses": ["other.example:443"]},
        ]
        for relay in invalid:
            with self.subTest(relay=relay), self.assertRaises(ValueError):
                discovery.build({**self.publish_settings(), "relays": [relay]}, self.paid_manifest(), publication=True)

    def test_refuses_existing_discovery_wrong_image_tor_and_fixed_origin_changes(self):
        cases = []
        for env in ("WILDBLOOM_SERVICE_PROFILE=/old/profile", "WILDBLOOM_NO_TOR=false",
                    "WILDBLOOM_MIRROR_PROXY=socks5h://127.0.0.1:9050", "WILDBLOOM_PUBLIC_URL=https://other.example:3742"):
            m = self.paid_manifest()
            m["app"]["environment"].append(env)
            cases.append(m)
        m = self.paid_manifest()
        m["app"]["container"]["image"] = "ghcr.io/forgesworn/wildbloom-node:old"
        cases.append(m)
        m = self.paid_manifest()
        m["app"]["volumes"].append(discovery.SERVICE_VOLUME)
        cases.append(m)
        for m in cases:
            with self.subTest(manifest=m), self.assertRaises(ValueError):
                discovery.build(self.settings, m, inspection=True)

    def test_secrets_unknown_fields_invalid_keys_origins_and_types_refused(self):
        for changes in ({"secret_key": "synthetic-secret"}, {"service_pubkey": "f" * 64},
                        {"service_pubkey": "nsec1synthetic"}, {"node_origin": "https://127.0.0.1:3742"},
                        {"node_origin": "https://10.0.0.1:3742"}, {"node_origin": "https://node.local:3742"},
                        {"node_origin": "https://user:secret@node.example:3742"}, {"withdrawn": "false"},
                        {"public_services": ["paid", "paid"]}, {"about": "bad\ntext"},
                        {"browser_origins": ["https://node.example/path"]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                discovery.build({**self.settings, **changes}, self.manifest)

    def test_private_cli_outputs_never_overwrite_or_follow_symlinks(self):
        scratch = ROOT / ".cache/discovery-config-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            directory = Path(directory)
            settings = directory / "settings.json"
            init = [sys.executable, str(ROOT / "scripts/configure-wildbloom-discovery.py"), "--init-settings", str(settings)]
            subprocess.run(init, check=True, capture_output=True)
            self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(subprocess.run(init, capture_output=True).returncode, 0)
            output = directory / "prepared"
            command = [sys.executable, str(ROOT / "scripts/configure-wildbloom-discovery.py"), str(settings),
                       "--manifest", str(ROOT / "apps/wildbloom-node/manifest.yml"), "--output", str(output)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertEqual((output / "service-profile.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual((output / "manifest.yml").stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            link = directory / "link"
            os.symlink(settings, link)
            with self.assertRaises(FileExistsError):
                discovery.write_private(link, {})


if __name__ == "__main__":
    unittest.main()
