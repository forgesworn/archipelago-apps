"""Security boundaries of the qualification-only public promotion."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


public = load("public", ROOT / "node/expose-spry-lab.py")
prepare = load("prepare", ROOT / "scripts/prepare-spry-turn.py")


class PublicQualification(unittest.TestCase):
    def test_only_pinned_lab_can_be_promoted(self):
        body = yaml.safe_dump(prepare.manifest(prepare.SPRY_REF), sort_keys=False).encode()
        app = yaml.safe_load(public.public_manifest(body, "8.8.8.8"))["app"]
        args = app["container"]["custom_args"]
        self.assertNotIn("--allow-loopback-peers", args)
        self.assertEqual(args[args.index("--relay-ports") + 1], "49160:49191")
        self.assertEqual(app["volumes"][0]["options"], ["ro"])
        self.assertEqual(app["resources"]["memory_limit"], "128m")
        # 'open' still installs an HTTP proxy; only 'none' leaves native
        # TURN/TLS sockets to Spry rather than racing it for their ports.
        self.assertTrue(all(port["auth"] == "none" and port["auth_rationale"] for port in app["ports"]))
        with self.assertRaises(ValueError):
            public.public_manifest(body + b"\n", "8.8.8.8")

    def test_refuse_private_or_injected_endpoint_inputs(self):
        for hostname, ip in (("host.invalid;id", "8.8.8.8"), ("host.invalid", "127.0.0.1"),
                             ("host.invalid", "0.0.0.0"), ("host.invalid", "::1"),
                             ("localhost", "8.8.8.8")):
            with self.subTest(hostname=hostname, ip=ip), self.assertRaises(ValueError):
                public.endpoint(hostname, ip)
        public.endpoint("calls.example.org", "8.8.8.8")

    def test_http_challenge_route_kept_and_dashboard_redirect_removed(self):
        body = (b"server { location / { return 444; } }\nserver { "
                b"location /.well-known/acme-challenge/ { root /var/www/letsencrypt; } "
                b"location / { return 301 https://$host$request_uri; } }\n"
                b"server { listen 443 ssl; location / { try_files $uri /index.html; } }")
        result = public.acme_site(body)
        self.assertIn(b"root /var/www/letsencrypt;", result)
        self.assertIn(b"location / { return 404; }", result)
        self.assertEqual(result.split(b"server {")[-1], body.split(b"server {")[-1])
        for bad in (body + body, body.replace(b"return 444", b"return 200"), b"other site"):
            with self.assertRaises(ValueError):
                public.acme_site(bad)

    def test_public_rules_exclude_dashboard_and_issuer(self):
        self.assertNotIn("443/tcp", public.RULES)
        self.assertNotIn("8443/tcp", public.RULES)
        self.assertIn("49160:49191/udp", public.RULES)

    def test_certificate_mismatch_refuses_before_copy(self):
        with patch.object(public, "run", side_effect=[b"", b"", b"cert-key", b"different-key"]), \
                patch.object(public, "private_write") as write:
            with self.assertRaises(ValueError):
                public.copy_certificate("calls.example.org")
            write.assert_not_called()

    def test_certificate_lineage_cannot_escape_lets_encrypt(self):
        for lineage in ("../private", "/etc/shadow", "a/b", "..", "name;command"):
            with self.subTest(lineage=lineage), patch.object(public, "run") as run:
                with self.assertRaises(ValueError):
                    public.copy_certificate("calls.example.org", lineage)
                run.assert_not_called()

    def test_renderer_timeout_refuses_before_spry_restart(self):
        with patch.object(public, "run", return_value=b'[{"State":{"Running":false},"Config":{"Cmd":[]}}]') as run, patch.object(public.time, "sleep"), \
                patch.object(public.Path, "exists", return_value=False):
            with self.assertRaises(ValueError):
                public.restart()
            self.assertEqual(run.call_args_list[0].args[0], ["systemctl", "restart", "archipelago"])
            self.assertFalse(any("--user" in call.args[0] for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
