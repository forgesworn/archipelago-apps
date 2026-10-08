#!/usr/bin/env python3
"""Prepare private Archipelago LNURLcash configuration; never deploy or pay.

Requires PyYAML, also used by Archipelago's manifest validator.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
MONEYER_KEY = "0218865ec3352afb85695bd1b6089323f802ecbf3ae2103bf8fd4d3e6fb571f0e4"
MAX = 9_007_199_254_740_991


def integer(settings, key, minimum=1):
    value = settings.get(key)
    if type(value) is not int or not minimum <= value <= MAX:
        raise ValueError(f"{key} must be an integer between {minimum} and {MAX}")
    return value


def text(settings, key, limit=2048):
    value = settings.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f"{key} must be non-empty plain text (at most {limit} characters)")
    return value


def origin(value):
    if not isinstance(value, str):
        raise ValueError("An HTTPS origin is required")
    url = urlsplit(value)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.path not in ("", "/") or url.query or url.fragment
            or url.hostname.endswith(".onion") or not re.fullmatch(r"[A-Za-z0-9.\[\]:-]+", url.netloc)):
        raise ValueError("Use an HTTPS origin without credentials, path, query or fragment")
    # Accessing port also rejects malformed port strings and out-of-range values.
    if url.port == 0:
        raise ValueError("Invalid HTTPS port")
    host = f"[{url.hostname}]" if ":" in url.hostname else url.hostname
    port = f":{url.port}" if url.port and url.port != 443 else ""
    return f"https://{host}{port}"


def build(settings, addresses, enable=False):
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a JSON object")
    node = origin(settings.get("node_origin"))
    if urlsplit(node).port != 3742:
        raise ValueError("node_origin must be the Archipelago public hostname on port 3742")
    quota = integer(settings, "quota_bytes")
    reserve = integer(settings, "owner_reserved_bytes", 0)
    capacity = integer(settings, "offer_capacity_bytes")
    blob = integer(settings, "max_blob_bytes")
    if reserve >= quota or capacity > quota - reserve or blob > quota:
        raise ValueError("Offer must fit sale capacity (quota minus owner reserve); blob limit must fit quota")
    price = integer(settings, "price_sats") * 1000
    if price > MAX:
        raise ValueError("price_sats is too large")
    seller_id = text(settings, "seller_id", 128)
    offer_id = text(settings, "offer_id", 128)
    if not all(re.fullmatch(r"[A-Za-z0-9_-]+", v) for v in (seller_id, offer_id)):
        raise ValueError("seller_id and offer_id allow only letters, digits, hyphens and underscores")
    pins = []
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("Moneyer address pins must be public IP addresses")
        pins.append(f"[{ip}]:443" if ip.version == 6 else f"{ip}:443")
    pins = sorted(set(pins))
    if not 1 <= len(pins) <= 16:
        raise ValueError("Supply 1–16 Moneyer IP pins, or explicitly resolve them with --resolve-moneyer")
    browsers = settings.get("browser_origins", [])
    if not isinstance(browsers, list) or not 1 <= len(browsers) <= 16:
        raise ValueError("Supply 1–16 browser_origins")
    browsers = [origin(item) for item in browsers]
    if enable and settings.get("moneyer_evaluation_accepted") is not True:
        raise ValueError("Moneyer is an evaluation mint. Set moneyer_evaluation_accepted only after reviewing its terms")
    if enable and text(settings, "refund_policy").startswith("REPLACE"):
        raise ValueError("Complete your operator refund/contact terms before enabling sales")
    offer = {
        "id": offer_id, "revision": integer(settings, "offer_revision"),
        "capacity_bytes": capacity,
        "duration_seconds": integer(settings, "duration_seconds"),
        "grace_seconds": integer(settings, "grace_seconds", 0),
        "price_msat": price, "delivery_bytes": integer(settings, "delivery_bytes"),
        "delivery_policy": text(settings, "delivery_policy"),
        "retention_policy": text(settings, "retention_policy"),
        "refund_policy": text(settings, "refund_policy"),
    }
    profile = {
        "checkout": {
            "origin": node + "/", "seller_id": seller_id,
            "seller_name": text(settings, "seller_name", 128), "network": "bitcoin",
            "quote_seconds": 600, "allow_loopback_http": False, "tor_only": False,
            "offers": [offer], "issuers": [{"id": "moneyer-dev",
                "note_endpoint": "https://moneyer.dev/w", "callback": "https://moneyer.dev/w/cb",
                "mint_pubkey": MONEYER_KEY}],
        },
        "state": "/data/operator/checkout", "max_paid_bytes": quota - reserve,
        "browser_origins": browsers, "phoenixd": None,
        "notes": [{"endpoint": endpoint, "destination": {
            "origin": "https://moneyer.dev/", "addresses": pins, "allow_loopback_http": False,
        }} for endpoint in ("https://moneyer.dev/w", "https://moneyer.dev/w/cb")],
    }
    manifest = yaml.safe_load((ROOT / "apps/wildbloom-node/manifest.yml").read_text())
    app = manifest["app"]
    app["environment"] += [f"WILDBLOOM_QUOTA_BYTES={quota}", f"WILDBLOOM_MAX_BLOB_BYTES={blob}"]
    # Avoid advertising a different checkout origin when the dashboard was opened
    # by LAN IP or mDNS. Server identity aliases remain derived from node facts.
    for entry in app["container"]["derived_env"]:
        if entry["key"] == "WILDBLOOM_PUBLIC_URL":
            entry["template"] = node
    app["dependencies"] = [{"storage": f"{(quota + 1073741823) // 1073741824}Gi"}]
    if enable:
        app["environment"].append("WILDBLOOM_CHECKOUT_PROFILE=/data/operator/checkout-profile.json")
        app["description"] = "Encrypted storage for your node identities and customers with paid allowances. Payments go directly to this operator."
        app["ports"][0]["auth_rationale"] = (
            "Blossom enforces its own Nostr authorisation. Owner identities and activated paid "
            "allowances can upload within their limits; unsigned and unpaid stranger writes are refused. "
            "Private checkout orders require the buyer's signature. Reads are by SHA-256; "
            "no dashboard or receiving credentials are exposed."
        )
    return profile, manifest


def write_private(path, value):
    # Never overwrite a previous operator configuration or follow a symlink.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path, nargs="?", help="Operator-edited settings JSON")
    parser.add_argument("--init-settings", type=Path, help="Create a private editable settings file with suggested defaults; no network access")
    parser.add_argument("--output", type=Path, help="New private output directory; never overwrites")
    parser.add_argument("--moneyer-ip", action="append", default=[])
    parser.add_argument("--resolve-moneyer", action="store_true", help="Explicitly resolve moneyer.dev now and pin its public IPs")
    parser.add_argument("--enable-sales", action="store_true", help="Include checkout opt-in in the prepared manifest; does not deploy")
    args = parser.parse_args()
    if args.init_settings:
        if args.settings or args.output or args.moneyer_ip or args.resolve_moneyer or args.enable_sales:
            parser.error("Use --init-settings on its own; edit the defaults before preparing a profile")
    elif not args.settings or not args.output:
        parser.error("Supply settings and --output, or use --init-settings to start")
    try:
        if args.init_settings:
            defaults = json.loads((ROOT / "docs/wildbloom-sales.example.json").read_text())
            write_private(args.init_settings, defaults)
            print(f"Created editable defaults at {args.init_settings}. Nothing was deployed or enabled.")
            print("Choose your own capacity, reserve, offer size, price, term and policies; check available disk space.")
            return
        if args.settings.stat().st_size > 65536:
            raise ValueError("Settings must be at most 64 KiB")
        settings = json.loads(args.settings.read_text())
        addresses = args.moneyer_ip
        if args.resolve_moneyer:
            addresses += [r[4][0] for r in socket.getaddrinfo("moneyer.dev", 443, type=socket.SOCK_STREAM)]
        profile, manifest = build(settings, addresses, args.enable_sales)
        # A new directory avoids mixing a new profile with an existing receiving ledger.
        args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
        write_private(args.output / "checkout-profile.json", profile)
        write_private(args.output / "manifest.yml", manifest)  # JSON is valid YAML.
        print(f"Prepared private files in {args.output}; sales {'enabled in manifest' if args.enable_sales else 'disabled'}.")
        print("Nothing was deployed. Keep checkout and storage backups together; never reset receiving state.")
    except (ValueError, OSError, TypeError) as error:
        parser.exit(1, f"Configuration refused: {error}\n")


if __name__ == "__main__":
    main()
