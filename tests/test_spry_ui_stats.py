from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SpryUiStatsTests(unittest.TestCase):
    def test_adapter_uses_reviewed_archipelago_assets(self):
        main = (ROOT / "apps/spry/runtime/src/main.rs").read_text()
        self.assertIn('script: include_str!("../../public/app.mjs")', main)
        self.assertIn('style: include_str!("../../public/style.css")', main)

    def test_live_stats_come_from_the_signed_owner_metrics_api(self):
        html = (ROOT / "apps/spry/public/index.html").read_text()
        script = (ROOT / "apps/spry/public/app.mjs").read_text()
        for label in ["Relay at a glance", "Control link", "Mode", "Active allocations", "Mesh peers", "Throughput", "Relayed total", "Dropped packets", "Paired devices", "Call access", "Per device"]:
            self.assertIn(label, html)
        self.assertIn("Counters reset when the relay restarts", html)
        self.assertIn("request('/v1/owner/stats')", script)
        self.assertIn("stats.forwardedBytes", script)
        self.assertIn("stats.droppedPackets", script)
        self.assertIn("stats.activeAllocations", script)
        self.assertIn("state.controlReady === true ? 'Connected' : 'Connecting'", script)
        self.assertIn("privateRelay ? 'Private mesh' : 'Public endpoint'", script)
        self.assertIn("Live relay counters are available on a private mesh relay", script)

    def test_pairing_count_tracks_list_and_removal(self):
        script = (ROOT / "apps/spry/public/app.mjs").read_text()
        self.assertIn("document.querySelector('#stat-devices').textContent = String(pairings.length)", script)
        self.assertIn("document.querySelector('#stat-devices').textContent = String(list.children.length)", script)

    def test_owner_can_manage_grants_without_room_or_participant_details(self):
        html = (ROOT / "apps/spry/public/index.html").read_text()
        script = (ROOT / "apps/spry/public/app.mjs").read_text()
        self.assertIn("Manage call access", html)
        self.assertIn("not a room name or participant list", html)
        self.assertIn("does not mean they are on a call", html)
        self.assertIn("request('/v1/owner/grants/list')", script)
        self.assertIn("request('/v1/owner/grants/remove', { id: grant.id })", script)
        self.assertIn("grant.recentDevices", script)
        self.assertNotIn("grant.scope", script)
        self.assertNotIn("grant.token", script)

    def test_javascript_syntax(self):
        subprocess.run(["node", "--check", str(ROOT / "apps/spry/public/app.mjs")], check=True)


if __name__ == "__main__":
    unittest.main()
