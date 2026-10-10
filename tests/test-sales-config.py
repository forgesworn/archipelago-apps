import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sales", ROOT / "scripts/configure-wildbloom-sales.py")
sales = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sales)


class SalesConfigTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((ROOT / "docs/wildbloom-sales.example.json").read_text())

    def test_defaults_keep_sales_off_and_separate_customer_capacity(self):
        profile, manifest = sales.build(self.settings, ["1.1.1.1"])
        self.assertEqual(profile["max_paid_bytes"], 100 * 1024**3)
        self.assertEqual(profile["checkout"]["offers"][0]["price_msat"], 500_000)
        self.assertEqual(profile["checkout"]["issuers"][0]["id"], "lnurlcash-reference")
        self.assertEqual(profile["checkout"]["issuers"][0]["mint_pubkey"], sales.REFERENCE_KEY)
        self.assertEqual(profile["notes"][1]["endpoint"], "https://mint.lnurlcash.com/w/cb")
        self.assertFalse(any("CHECKOUT_PROFILE" in v for v in manifest["app"]["environment"]))
        self.assertEqual(manifest["app"]["container"]["derived_env"][0]["key"], "WILDBLOOM_ALLOW_PUBKEYS")

    def test_operator_values_are_preserved_in_profile_and_manifest(self):
        self.settings.update(quota_bytes=20 * 1024**3, owner_reserved_bytes=0,
                             offer_capacity_bytes=2 * 1024**3, price_sats=75,
                             duration_seconds=7 * 86400, grace_seconds=0,
                             delivery_bytes=3 * 1024**3,
                             retention_policy="Seven days; no additional grace")
        profile, manifest = sales.build(self.settings, ["1.1.1.1"])
        offer = profile["checkout"]["offers"][0]
        self.assertEqual(profile["max_paid_bytes"], 20 * 1024**3)
        self.assertEqual(offer["price_msat"], 75_000)
        self.assertEqual(offer["capacity_bytes"], 2 * 1024**3)
        self.assertEqual(offer["duration_seconds"], 7 * 86400)
        self.assertEqual(offer["grace_seconds"], 0)
        self.assertEqual(offer["delivery_bytes"], 3 * 1024**3)
        self.assertEqual(offer["retention_policy"], self.settings["retention_policy"])
        self.assertIn(f"WILDBLOOM_QUOTA_BYTES={20 * 1024**3}", manifest["app"]["environment"])
        self.assertEqual(manifest["app"]["dependencies"], [{"storage": "20Gi"}])

    def test_initialise_editable_defaults_without_enabling_or_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            command = [sys.executable, str(ROOT / "scripts/configure-wildbloom-sales.py"), "--init-settings", str(path)]
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(json.loads(path.read_text()), self.settings)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertNotEqual(subprocess.run(command + ["--enable-sales"], capture_output=True).returncode, 0)

    def test_enable_requires_issuer_review_and_completed_terms(self):
        with self.assertRaises(ValueError):
            sales.build(self.settings, ["1.1.1.1"], True)
        self.settings["issuer_reviewed"] = True
        with self.assertRaises(ValueError):
            sales.build(self.settings, ["1.1.1.1"], True)
        self.settings["refund_policy"] = "Contact this synthetic operator at operator@example.invalid"
        _, manifest = sales.build(self.settings, ["1.1.1.1"], True)
        self.assertIn("WILDBLOOM_CHECKOUT_PROFILE=/data/operator/checkout-profile.json", manifest["app"]["environment"])

    def test_moneyer_is_an_explicit_development_choice(self):
        self.settings.update(issuer_id="moneyer-dev", issuer_reviewed=True,
                             refund_policy="Development acceptance only")
        with self.assertRaises(ValueError):
            sales.build(self.settings, ["1.1.1.1"], True)
        self.settings["moneyer_evaluation_accepted"] = True
        profile, _ = sales.build(self.settings, ["1.1.1.1"], True)
        self.assertEqual(profile["checkout"]["issuers"][0]["id"], "moneyer-dev")
        self.assertEqual(profile["checkout"]["issuers"][0]["mint_pubkey"], sales.MONEYER_KEY)

    def test_old_settings_still_mean_moneyer(self):
        self.settings.pop("issuer_id")
        self.settings.pop("issuer_reviewed")
        self.settings["moneyer_evaluation_accepted"] = True
        self.settings["refund_policy"] = "Legacy Moneyer configuration"
        profile, _ = sales.build(self.settings, ["1.1.1.1"], True)
        self.assertEqual(profile["checkout"]["issuers"][0]["id"], "moneyer-dev")

    def test_invalid_origin_capacity_price_and_pins_are_refused(self):
        for key, value in [("node_origin", "https://user:secret@node.example:3742"),
                           ("node_origin", "https://node.example:3742/path"),
                           ("owner_reserved_bytes", self.settings["quota_bytes"]),
                           ("offer_capacity_bytes", self.settings["quota_bytes"]),
                           ("issuer_id", "https://attacker.example"),
                           ("price_sats", None), ("price_sats", True), ("price_sats", 1.5)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                sales.build({**self.settings, key: value}, ["1.1.1.1"])
        for pins in [[], ["127.0.0.1"], ["10.0.0.1"], ["::1"], ["garbage"]]:
            with self.subTest(pins=pins), self.assertRaises(ValueError):
                sales.build(self.settings, pins)

    def test_private_output_never_overwrites_or_follows_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "profile.json"
            sales.write_private(target, {"test": True})
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                sales.write_private(target, {})
            link = Path(tmp) / "link"
            os.symlink(target, link)
            with self.assertRaises(FileExistsError):
                sales.write_private(link, {})
            self.assertEqual(json.loads(target.read_text()), {"test": True})


if __name__ == "__main__":
    unittest.main()
