#!/usr/bin/env python3
"""Prepare a private, loopback-only Archy experiment. Never build or deploy it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPRY_REF = "a76496bbcb60e637c0606c8da5919b5a3b2b3cf3"
PACKAGE_REV = 2
RELAY_PORT_FIRST, RELAY_PORT_LAST = 49160, 49191
SOURCE_FILES = ("Cargo.toml", "Cargo.lock", "examples/load.rs", "src/auth.rs", "src/lib.rs",
                "src/limits.rs", "src/main.rs", "src/turn.rs", "src/wasm.rs", "src/wire.rs")
NOTICE_FILES = ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES.txt")


def git_file(source, ref, name):
    """Read committed regular files, never a dirty checkout or symbolic link."""
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1"}
    entry = subprocess.run(["git", "-C", str(source), "ls-tree", ref, "--", name],
                           check=True, capture_output=True, env=env, timeout=10).stdout
    if not entry.startswith((b"100644 blob ", b"100755 blob ")):
        raise ValueError(f"Expected a committed regular file: {name}")
    return subprocess.run(["git", "-C", str(source), "show", f"{ref}:{name}"],
                          check=True, capture_output=True, env=env, timeout=10).stdout


def committed_source(source, ref):
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise ValueError("Use a full immutable source commit, not a branch or tag")
    # This is a reviewed recipe for one version, not an arbitrary-source builder.
    if ref != SPRY_REF:
        raise ValueError("This experiment supports only the reviewed Spry commit")
    manifest = json.loads(git_file(source, ref, "docs/evidence/source-manifest.json"))
    recorded = manifest.get("files")
    if not isinstance(recorded, list):
        raise ValueError("Expected the reviewed source hash manifest")
    hashes = {}
    for item in recorded:
        if (not isinstance(item, dict) or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str)
                or item["path"] in hashes
                or not isinstance(item["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            raise ValueError("Invalid reviewed source hash entry")
        hashes[item["path"]] = item["sha256"]
    files = {name: git_file(source, ref, name) for name in SOURCE_FILES + NOTICE_FILES}
    for name in SOURCE_FILES:
        if hashlib.sha256(files[name]).hexdigest() != hashes.get(name):
            raise ValueError(f"Reviewed source hash differs: {name}")
    return files


def manifest(ref):
    # Host networking avoids pretending TURN's bounded UDP relay sockets
    # work through an HTTP app gate. The process itself binds ONLY loopback.
    # Public operation requires bounded ports/firewall/TLS work, not this recipe.
    return {"app": {
        "id": "spry-turn-lab", "name": "Spry TURN (local experiment)", "version": "0.1.0",
        "description": "Loopback-only packet relay experiment, owned by this node. No public discovery or credential issuer.",
        "category": "networking",
        "container": {
            "image": f"localhost/spry-turn:0.1.0-{ref[:12]}-{PACKAGE_REV}", "pull_policy": "never", "network": "host",
            "custom_args": ["serve", "--listen", "127.0.0.1:3478", "--allow-loopback-peers",
                            "--relay-ports", f"{RELAY_PORT_FIRST}:{RELAY_PORT_LAST}",
                            "--max-allocations", "32", "--max-per-user", "8", "--max-connections", "32",
                            "--bytes-per-second", "1000000"],
            "generated_secrets": [{"name": "spry-turn-rest-secret", "kind": "hex32"}],
            "secret_env": [{"key": "SPRY_TURN_SECRET", "secret_file": "spry-turn-rest-secret"}],
        },
        "resources": {"memory_limit": "128Mi", "cpu_limit": 1},
        "security": {"capabilities": [], "readonly_root": True, "no_new_privileges": True, "network_policy": "host"},
        "ports": [{"host": 3478, "container": 3478, "protocol": protocol,
                   "bind": "127.0.0.1", "auth": "local"} for protocol in ("udp", "tcp")],
        "metadata": {"author": "ForgeSworn", "license": "MIT", "tags": ["turn", "transport", "experimental"]},
    }}


def write_private(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(content)


def prepare(source, output, ref=SPRY_REF):
    if output.name != "spry-turn-lab":
        raise ValueError("Archy requires the output directory name spry-turn-lab to match app.id")
    files = committed_source(source, ref)
    # An existing directory or symlink is never overwritten, even if empty.
    output.mkdir(mode=0o700)
    try:
        destination = output / "source"
        destination.mkdir(mode=0o700)
        (destination / "src").mkdir(mode=0o700)
        (destination / "examples").mkdir(mode=0o700)
        for name, content in files.items():
            write_private(destination / name, content)
        recipe = (ROOT / "experimental/spry-turn/Dockerfile").read_bytes()
        write_private(output / "Dockerfile", recipe)
        write_private(output / "manifest.yml", yaml.safe_dump(manifest(ref), sort_keys=False).encode())
        receipt = {"source_ref": ref, "mode": "loopback-only-experiment", "built": False,
                   "deployed": False, "discovery": "disabled", "operator_secrets_in_context": False,
                   "udp_relay_ports": {"first": RELAY_PORT_FIRST, "last": RELAY_PORT_LAST},
                   "public_tls": "unconfigured",
                   "package_revision": PACKAGE_REV, "recipe_sha256": hashlib.sha256(recipe).hexdigest(),
                   "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
        write_private(output / "prepared.json", (json.dumps(receipt, indent=2) + "\n").encode())
    except BaseException:
        shutil.rmtree(output)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Local Spry git repository; no network fetch")
    parser.add_argument("--ref", default=SPRY_REF)
    parser.add_argument("--output", type=Path, required=True, help="New private directory in an existing parent")
    args = parser.parse_args()
    try:
        prepare(args.source, args.output, args.ref)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # git errors may contain paths. Never echo a captured source file/body.
        parser.exit(1, f"Preparation refused ({type(error).__name__}); no build or deployment performed.\n")
    print("Prepared private loopback-only experiment; nothing built, deployed or published.")


if __name__ == "__main__":
    main()
