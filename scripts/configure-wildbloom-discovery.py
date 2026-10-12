#!/usr/bin/env python3
"""Prepare private Wildbloom discovery files. No network, keys, deployment or automatic publication."""
import argparse
import copy
import ipaddress
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = "/service/service-profile.json"
SERVICE_VOLUME = {"type": "bind", "source": "/var/lib/archipelago/wildbloom-service",
                  "target": "/service", "options": ["rw"]}


def read_json(path):
    if path.stat().st_size > 65536:
        raise ValueError("Configuration must be at most 64 KiB")
    return json.loads(path.read_text())


def text(value, field, limit):
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f"{field} must be non-empty plain text (at most {limit} UTF-8 bytes)")
    return value


def public_ip(value):
    ip = ipaddress.ip_address(value)
    if (not ip.is_global or ip.is_multicast or getattr(ip, "ipv4_mapped", None)
            or getattr(ip, "sixtofour", None) or getattr(ip, "teredo", None)):
        raise ValueError("Address pins must be ordinary public IP addresses")
    return ip


def https_origin(value):
    text(value, "origin", 2048)
    u = urlsplit(value)
    if (u.scheme != "https" or not u.hostname or u.username is not None or u.password is not None
            or u.path not in ("", "/") or u.query or u.fragment or u.port == 0
            or not re.fullmatch(r"[A-Za-z0-9.\[\]:-]+", u.netloc)):
        raise ValueError("Use a public HTTPS origin without credentials, path, query or fragment")
    host = u.hostname.lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if ("." not in host or host.endswith((".onion", ".local", ".localhost", ".internal"))
                or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split("."))):
            raise ValueError("Use a public HTTPS hostname")
    else:
        public_ip(host)
    host = f"[{host}]" if ":" in host else host
    port = f":{u.port}" if u.port and u.port != 443 else ""
    return f"https://{host}{port}"


def service_key(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("service_pubkey must be a dedicated lowercase hex Nostr public key")
    x, p = int(value, 16), 2**256 - 2**32 - 977
    y2 = (x**3 + 7) % p
    if x >= p or pow(pow(y2, (p + 1) // 4, p), 2, p) != y2:
        raise ValueError("service_pubkey is not a secp256k1 public key")
    return value


def announcement(settings):
    if settings.get("publication_reviewed") is not True:
        raise ValueError("Review public metadata and relay transport, then set publication_reviewed to true")
    signer = settings.get("signer")
    if signer != "/service/signer":
        raise ValueError("Install the external signer at /service/signer; never put signing secrets in settings or arguments")
    relays = settings.get("relays")
    if not isinstance(relays, list) or not 1 <= len(relays) <= 8:
        raise ValueError("Choose 1–8 relays with explicit public socket-address pins")
    seen = set()
    for r in relays:
        if not isinstance(r, dict) or set(r) != {"url", "addresses"}:
            raise ValueError("Each relay requires only url and addresses")
        text(r["url"], "relay URL", 2048)
        u = urlsplit(r["url"])
        if (u.scheme != "wss" or not u.hostname or u.username is not None or u.password is not None
                or u.query or u.fragment or u.port == 0 or "\\" in r["url"] or u.hostname.endswith(".onion")):
            raise ValueError("Direct publication requires a public WSS relay without credentials, query or fragment")
        https_origin("https://" + u.netloc)
        if r["url"] in seen:
            raise ValueError("Duplicate relay")
        seen.add(r["url"])
        if not isinstance(r["addresses"], list) or not 1 <= len(r["addresses"]) <= 16:
            raise ValueError("Each relay requires 1–16 public address pins")
        for address in r["addresses"]:
            if not isinstance(address, str):
                raise ValueError("Relay address must be an IP:port socket address")
            a = urlsplit("socket://" + address)
            ip = public_ip(a.hostname)
            if a.username is not None or a.path or a.query or a.fragment or a.port != (u.port or 443):
                raise ValueError("Relay address pin must match its WSS port")
            canonical = f"[{ip}]:{a.port}" if ip.version == 6 else f"{ip}:{a.port}"
            if canonical != address:
                raise ValueError("Use canonical IP:port address pins")
            try:
                literal = ipaddress.ip_address(u.hostname)
            except ValueError:
                pass
            else:
                if literal != ip:
                    raise ValueError("Literal relay host must match its address pin")
    heartbeat, ttl = settings.get("heartbeat_seconds"), settings.get("ttl_seconds")
    if (type(heartbeat) is not int or type(ttl) is not int or not 300 <= heartbeat <= 3600
            or not 600 <= ttl <= 86400 or ttl < 2 * heartbeat):
        raise ValueError("Heartbeat must be 300–3600 seconds; TTL 600–86400 and at least twice heartbeat")
    return {"signer": signer, "signer_args": [], "state_dir": "/service/publisher",
            "transport": "direct", "relays": copy.deepcopy(relays),
            "heartbeat_seconds": heartbeat, "ttl_seconds": ttl}


def build(settings, manifest, inspection=False, publication=False, free=False):
    allowed = {"service_pubkey", "identifier", "name", "about", "node_origin", "browser_origins",
               "public_services", "withdrawn", "publication_reviewed", "signer", "relays",
               "heartbeat_seconds", "ttl_seconds"}
    if not isinstance(settings, dict) or set(settings) != allowed:
        raise ValueError("Use exactly the fields in the discovery settings example; secret keys are never accepted")
    manifest = copy.deepcopy(manifest)
    app = manifest["app"]
    if app["id"] != "wildbloom-node":
        raise ValueError("Use your existing Wildbloom Node manifest")
    expected = yaml.safe_load((ROOT / "apps/wildbloom-node/manifest.yml").read_text())["app"]["container"]["image"]
    if app["container"]["image"] != expected:
        raise ValueError("Upgrade the private manifest to the exact validated discovery image before preparing discovery")
    env = app.setdefault("environment", [])
    pairs = [entry.split("=", 1) for entry in env]
    if any(len(entry) != 2 for entry in pairs) or len({entry[0] for entry in pairs}) != len(pairs):
        raise ValueError("Manifest environment must use unique KEY=value entries")
    values = dict(pairs)
    if "WILDBLOOM_SERVICE_PROFILE" in values or any(v["target"] == "/service" for v in app.get("volumes", [])):
        raise ValueError("Existing discovery configuration must be reviewed manually; it is never replaced")
    if (values.get("WILDBLOOM_NO_TOR", "true") != "true"
            or values.get("WILDBLOOM_MIRROR_PROXY") or app.get("container", {}).get("command")):
        raise ValueError("This helper supports the direct HTTPS package; configure Tor using the native runbook")
    node = https_origin(settings["node_origin"])
    if urlsplit(node).port != 3742:
        raise ValueError("node_origin must be the Archipelago public HTTPS origin on port 3742")
    browsers = settings["browser_origins"]
    if not isinstance(browsers, list) or not 1 <= len(browsers) <= 16:
        raise ValueError("Choose 1–16 HTTPS browser origins")
    browsers = [https_origin(v) for v in browsers]
    if len(set(browsers)) != len(browsers):
        raise ValueError("Duplicate browser origin")
    selected = settings["public_services"]
    if (not isinstance(selected, list) or not selected or len(set(selected)) != len(selected)
            or any(v not in ("paid", "free") for v in selected)):
        raise ValueError("public_services must choose paid, free, or both")
    if type(settings["withdrawn"]) is not bool or type(settings["publication_reviewed"]) is not bool:
        raise ValueError("withdrawn and publication_reviewed must be booleans")
    identifier = text(settings["identifier"], "identifier", 128)
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", identifier):
        raise ValueError("identifier contains unsupported characters")
    if free and "free" not in selected:
        raise ValueError("--enable-free-shelter requires free in public_services")
    enabled = inspection or publication
    if enabled:
        actual = set()
        if values.get("WILDBLOOM_CHECKOUT_PROFILE"):
            actual.add("paid")
        if values.get("WILDBLOOM_OPEN_SHELTER") == "true" or free:
            actual.add("free")
        if set(selected) != actual:
            raise ValueError("Discovery lists all enabled services: prepare sales separately, or explicitly enable free shelter")
        # Preserve a deliberately fixed checkout/public origin. Resolve only the
        # default dashboard placeholder; never rewrite an existing operator origin.
        public = [v for v in app["container"].get("derived_env", []) if v["key"] == "WILDBLOOM_PUBLIC_URL"]
        existing = values.get("WILDBLOOM_PUBLIC_URL")
        if existing and https_origin(existing) != node:
            raise ValueError("Discovery origin must match existing WILDBLOOM_PUBLIC_URL")
        if not existing and len(public) != 1:
            raise ValueError("Manifest must supply exactly one public origin")
        if public:
            old = public[0]["template"]
            if old != "https://{{PUBLIC_HOST}}:3742" and https_origin(old) != node:
                raise ValueError("Discovery origin must match the existing fixed public origin")
            public[0]["template"] = node
        env.append(f"WILDBLOOM_SERVICE_PROFILE={PROFILE_PATH}")
        app.setdefault("volumes", []).append(copy.deepcopy(SERVICE_VOLUME))
    if free:
        if not enabled:
            raise ValueError("Free shelter requires explicit inspection or publication opt-in")
        for k in ("WILDBLOOM_OPEN_SHELTER", "WILDBLOOM_DIRECT_HTTPS_MIRRORS"):
            if k not in values:
                env.append(k + "=true")
            elif values[k] != "true":
                raise ValueError("Existing free-shelter settings must be reviewed manually")
    profile = {"service_pubkey": service_key(settings["service_pubkey"]), "identifier": identifier,
               "name": text(settings["name"], "name", 128), "about": text(settings["about"], "about", 2048),
               "origins": [node + "/"], "browser_origins": browsers, "withdrawn": settings["withdrawn"],
               "announcement": announcement(settings) if publication else None}
    return profile, manifest


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("settings", type=Path, nargs="?")
    p.add_argument("--init-settings", type=Path)
    p.add_argument("--manifest", type=Path, help="Current operator manifest, with the upgraded image tag")
    p.add_argument("--output", type=Path, help="New private directory; never overwritten")
    p.add_argument("--enable-inspection", action="store_true", help="Enable public HTTP listing, without relay publication")
    p.add_argument("--enable-publication", action="store_true", help="Enable listing and reviewed direct relay publication")
    p.add_argument("--enable-free-shelter", action="store_true", help="Explicitly allow signed best-effort guest mirrors")
    a = p.parse_args()
    if a.init_settings:
        if any((a.settings, a.manifest, a.output, a.enable_inspection, a.enable_publication, a.enable_free_shelter)):
            p.error("Use --init-settings alone")
    elif not a.settings or not a.manifest or not a.output:
        p.error("Supply settings, --manifest and --output, or use --init-settings")
    try:
        if a.init_settings:
            write_private(a.init_settings, read_json(ROOT / "docs/wildbloom-discovery.example.json"))
            print("Created private editable defaults. Replace the synthetic public key and origins; nothing enabled.")
            return
        if a.manifest.stat().st_size > 65536:
            raise ValueError("Manifest must be at most 64 KiB")
        profile, manifest = build(read_json(a.settings), yaml.safe_load(a.manifest.read_text()),
                                  a.enable_inspection, a.enable_publication, a.enable_free_shelter)
        a.output.mkdir(mode=0o700, parents=False, exist_ok=False)
        write_private(a.output / "service-profile.json", profile)
        write_private(a.output / "manifest.yml", manifest)
        print(f"Prepared private files in {a.output}. Publication {'enabled in manifest' if a.enable_publication else 'off'}.")
        print("Nothing deployed. Preserve checkout/storage and publisher state; install your dedicated external signer separately.")
    except (ValueError, OSError, TypeError, KeyError, yaml.YAMLError) as e:
        p.exit(1, f"Configuration refused: {e}\n")


if __name__ == "__main__":
    main()
