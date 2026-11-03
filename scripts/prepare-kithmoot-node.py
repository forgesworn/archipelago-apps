#!/usr/bin/env python3
"""Prepare a local-only Archy candidate from an already built private bundle.

This neither downloads Shelter nor publishes images, manifests or source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "experimental/kithmoot-node"
BASE_IMAGE = "node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c"
REQUIRED = {"kithmoot-node", "runtime/bin/node", "lib/kithmoot-node.mjs", "bin/spry-node", "bin/bothyd",
            "deploy/kithmoot-node.service", "deploy/kithmoot-node-front.service", "licenses/NOTICE.txt",
            "licenses/Node-LICENSE.txt", "licenses/Spry-LICENSE.txt", "licenses/Shelter-LICENSE.txt"}


def safe_file(path, maximum=160_000_000):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022 or not 0 < info.st_size <= maximum:
        raise ValueError("Unsafe candidate input: " + path.name)
    return path.read_bytes()


def verified_bundle(bundle):
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError("Use a real private bundle directory")
    manifest = safe_file(bundle / "release.json", 65536)
    release = json.loads(manifest)
    if release.get("v") != 1 or release.get("name") != "kithmoot-node" or release.get("version") != "0.1.0-rc.1" \
            or release.get("platform") not in {"linux-arm64", "linux-x64"} or release.get("distribution") != "private-candidate":
        raise ValueError("A supported private node candidate is required")
    dependencies = release.get("dependencies", [])
    if not any(item.get("name") == "shelter" and item.get("visibility") == "private" for item in dependencies):
        raise ValueError("Shelter must remain an explicitly private input")
    files = release.get("files")
    if not isinstance(files, list) or not REQUIRED <= {item.get("path") for item in files} or len(files) > 64:
        raise ValueError("Incomplete candidate inventory")
    seen = set()
    for item in files:
        name = item.get("path", "")
        if not re.fullmatch(r"(?:kithmoot-node|(?:runtime/bin|lib|bin|deploy|licenses|provenance)/[A-Za-z0-9_.-]+)", name) or name in seen:
            raise ValueError("Unsafe or duplicate candidate path")
        seen.add(name)
        path = bundle / name
        for parent in path.parents:
            if parent == bundle:
                break
            if parent.is_symlink():
                raise ValueError("Symlink in candidate path")
        data = safe_file(path)
        if type(item.get("bytes")) is not int or len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item.get("sha256") \
                or type(item.get("executable")) is not bool or bool(path.stat().st_mode & 0o111) != item["executable"]:
            raise ValueError("Candidate file differs from its inventory: " + name)
    actual = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlinks are not candidate inputs")
        if path.is_file():
            actual.add(path.relative_to(bundle).as_posix())
    if actual != seen | {"release.json"}:
        raise ValueError("Unlisted candidate inputs")
    return release, hashlib.sha256(manifest).hexdigest()


def manifest(image):
    secrets = [("service-key", "SERVICE_KEY"), ("turn-secret", "TURN_SECRET"), ("state-salt", "STATE_SALT")]
    return f'''app:
  id: kithmoot-node
  name: KithMoot Node
  version: 0.1.0-rc.1
  description: Private candidate for rooms and calls hosted away from home. Maintainer UI review pending.
  category: networking
  container:
    image: {image}
    pull_policy: never
    network: host
    data_uid: "1000:1000"
    generated_secrets:
''' + ''.join(f'      - {{ name: kithmoot-node-{name}, kind: hex32 }}\n' for name, _ in secrets) + '''    secret_env:
''' + ''.join(f'      - {{ key: KITHMOOT_NODE_{key}, secret_file: kithmoot-node-{name} }}\n' for name, key in secrets) + '''    derived_env:
''' + ''.join(f"      - {{ key: {key}, template: '{{{{{key}}}}}' }}\n" for key in ["PUBLIC_HOST", "HOST_IP", "HOST_MDNS", "MESH_HOST", "NODE_IDENTITY_PUBKEYS"]) + '''  resources:
    memory_limit: 256m
    cpu_limit: 2
  security:
    capabilities: []
    readonly_root: true
    no_new_privileges: true
    network_policy: host
  volumes:
    - { type: bind, source: /var/lib/archipelago/kithmoot-node, target: /var/lib/kithmoot-node, options: [rw] }
    - { type: tmpfs, target: /tmp, tmpfs_options: 'rw,nosuid,nodev,noexec,size=16m,mode=1777' }
  ports:
    - { host: 3753, container: 3753, protocol: tcp, bind: 127.0.0.1, auth: gated }
    - { host: 34790, container: 34790, protocol: udp, auth: none, auth_rationale: 'Native TURN requires short-lived admitted-device credentials.' }
    - { host: 34790, container: 34790, protocol: tcp, auth: none, auth_rationale: 'Native TURN requires short-lived admitted-device credentials.' }
    - { host: 53499, container: 34790, protocol: tcp, bind: 127.0.0.1, auth: open, auth_rationale: 'Host TLS forwards only to the authenticated node TURN listener. No app access to host TLS keys.' }
''' + ''.join(f"    - {{ host: {port}, container: {port}, protocol: udp, auth: none, auth_rationale: 'Node TURN relay socket; allocation and peer permissions require admitted-device credentials.' }}\n" for port in range(49192, 49224)) + '''
  interfaces:
    main:
      name: Your KithMoot node
      description: Set up, pair and manage your private room node.
      type: ui
      port: 3753
      protocol: http
      path: /
  metadata:
    author: ForgeSworn
    repo: https://github.com/forgesworn/archipelago-apps
    license: MIT
    tags: [calls, rooms, kithmoot, private-candidate]
'''


def prepare(bundle, output):
    release, digest = verified_bundle(bundle)
    assets = [APP / "dist/controller.mjs", *(APP / ("dist/public/" + name) for name in ["index.html", "client.js", "style.css", "nostr-provider.js"])]
    for path in assets:
        safe_file(path, 2_000_000)
    if output.exists() or output.is_symlink():
        raise ValueError("Output already exists; choose a new private candidate directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".kithmoot-node-", dir=output.parent))
    try:
        os.chmod(stage, 0o700)
        shutil.copytree(bundle, stage / "bundle")
        if verified_bundle(stage / "bundle")[1] != digest:
            raise ValueError("Candidate changed while copying")
        shutil.copytree(APP / "dist", stage / "controller")
        shutil.copyfile(ROOT / "LICENSE", stage / "controller/LICENSE")
        image_digest = hashlib.sha256((BASE_IMAGE + digest + ''.join(hashlib.sha256(path.read_bytes()).hexdigest() for path in assets)).encode()).hexdigest()
        image = "localhost/kithmoot-node:0.1.0-rc.1-" + image_digest[:12]
        manifest_path = stage / "apps/kithmoot-node/manifest.yml"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(manifest(image))
        (stage / "Dockerfile").write_text(f'''FROM {BASE_IMAGE}
COPY --chown=0:0 bundle/ /opt/kithmoot-node/current/
COPY --chown=0:0 controller/ /opt/kithmoot-node/controller/
USER 1000:1000
ENV NODE_ENV=production
ENTRYPOINT ["/opt/kithmoot-node/current/runtime/bin/node", "/opt/kithmoot-node/controller/controller.mjs"]
''')
        (stage / ".dockerignore").write_text("*\n!Dockerfile\n!bundle/\n!bundle/**\n!controller/\n!controller/**\n")
        (stage / "candidate.json").write_text(json.dumps({"v": 1, "distribution": "private-candidate", "bundleSha256": digest,
            "platform": release["platform"], "image": image, "baseImage": BASE_IMAGE, "manifest": "apps/kithmoot-node/manifest.yml",
            "controllerFiles": [{"path": path.relative_to(APP / "dist").as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in assets],
            "uiReview": "ZAT pending", "publicationApproved": False}, indent=2) + "\n")
        stage.rename(output)
    except BaseException:
        shutil.rmtree(stage)
        raise
    return image


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest-template", action="store_true", help="Print private manifest metadata for schema checks; no bundle or image is built")
    args = parser.parse_args()
    if args.manifest_template:
        if args.bundle or args.output:
            parser.error("--manifest-template takes no private bundle or output")
        print(manifest("localhost/kithmoot-node:private-candidate"), end="")
        raise SystemExit(0)
    if not args.bundle or not args.output:
        parser.error("--bundle and --output are required for private packaging")
    try:
        image = prepare(args.bundle.absolute(), args.output.absolute())
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")
    print("Private candidate prepared. Local image: " + image)
    print("No image or manifest was published. Maintainer UI review remains pending.")
