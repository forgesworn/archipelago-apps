from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SpryUiStatsTests(unittest.TestCase):
    def test_adapter_uses_reviewed_archipelago_assets(self):
        main = (ROOT / "apps/spry/runtime/src/main.rs").read_text()
        self.assertIn('script: include_str!("../../public/app.mjs")', main)
        self.assertIn('style: include_str!("../../public/style.css")', main)

    def test_stats_are_operational_not_fabricated_bandwidth_metrics(self):
        html = (ROOT / "apps/spry/public/index.html").read_text()
        script = (ROOT / "apps/spry/public/app.mjs").read_text()
        for label in ["Relay at a glance", "Control link", "Mode", "Paired devices", "Call capacity", "Per device"]:
            self.assertIn(label, html)
        self.assertIn("not live bandwidth counters", html)
        self.assertIn("32 allocations", html)
        self.assertIn("8 allocations", html)
        self.assertIn("state.controlReady === true ? 'Connected' : 'Connecting'", script)
        self.assertIn("privateRelay ? 'Private mesh' : 'Public endpoint'", script)
        self.assertNotIn("forwarded_bytes", script)
        self.assertNotIn("forwarded_packets", script)

    def test_pairing_count_tracks_list_and_removal(self):
        script = (ROOT / "apps/spry/public/app.mjs").read_text()
        self.assertIn("document.querySelector('#stat-devices').textContent = String(pairings.length)", script)
        self.assertIn("document.querySelector('#stat-devices').textContent = String(list.children.length)", script)

    def test_javascript_syntax(self):
        subprocess.run(["node", "--check", str(ROOT / "apps/spry/public/app.mjs")], check=True)


if __name__ == "__main__":
    unittest.main()
