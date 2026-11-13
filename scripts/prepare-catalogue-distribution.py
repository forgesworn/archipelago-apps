#!/usr/bin/env python3
"""Prepare, but never invent authority for, a signed app catalogue candidate."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_APPS = ('spry', 'wildbloom', 'wildbloom-node')
KITHMOOT_IMAGE = 'localhost/kithmoot-node:group-headroom-20261110-db34017b49e3'
ACCEPT = ', '.join((
    'application/vnd.oci.image.index.v1+json',
    'application/vnd.docker.distribution.manifest.list.v2+json',
))
MANIFEST_LIMIT = 4 * 1024 * 1024


class DistributionError(ValueError):
    pass


def registry_json(repository, reference):
    token_url = f'https://ghcr.io/token?scope=repository:{repository}:pull'
    with urllib.request.urlopen(token_url, timeout=20) as response:
        token = json.load(response)['token']
    request = urllib.request.Request(
        f'https://ghcr.io/v2/{repository}/manifests/{reference}',
        headers={'Authorization': f'Bearer {token}', 'Accept': ACCEPT})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(MANIFEST_LIMIT + 1)
        if len(body) > MANIFEST_LIMIT:
            raise DistributionError(f'{repository}:{reference}: manifest is too large')
        declared = response.headers.get('Docker-Content-Digest')
    actual = 'sha256:' + hashlib.sha256(body).hexdigest()
    if declared and declared != actual:
        raise DistributionError(f'{repository}:{reference}: registry digest mismatch')
    return json.loads(body), actual


def resolve_image(image, platforms, cosign_pubkey):
    repository, reference = image.split(':', 1)
    try:
        document, digest = registry_json(repository, reference)
    except urllib.error.HTTPError as error:
        raise DistributionError(f'{image}: registry manifest unavailable (HTTP {error.code})') from error
    manifests = document.get('manifests')
    if not isinstance(manifests, list) or not manifests:
        raise DistributionError(f'{image}: expected a multi-platform image index')
    available = {item.get('platform', {}).get('os') + '/' + item.get('platform', {}).get('architecture')
                 for item in manifests if isinstance(item, dict)}
    missing = sorted(set(platforms) - available)
    if missing:
        raise DistributionError(f'{image}: missing platforms: {", ".join(missing)}')
    resolved = f'{repository}@{digest}'
    verify_image_signature(resolved, cosign_pubkey)
    return resolved


def verify_image_signature(image, cosign_pubkey):
    result = subprocess.run([
        'cosign', 'verify', '--key', str(cosign_pubkey), '--insecure-ignore-tlog=true', image,
    ], capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise DistributionError(f'{image}: cosign verification failed: {result.stderr[-1000:]}')


def image_version(image):
    tail = image.rsplit('/', 1)[-1]
    if ':' not in tail:
        raise DistributionError(f'{image}: expected an immutable version tag')
    return tail.rsplit(':', 1)[1]


def public_entries(platforms, cosign_pubkey):
    entries = {}
    for app_id in PUBLIC_APPS:
        path = ROOT / 'apps' / app_id / 'manifest.yml'
        manifest = yaml.safe_load(path.read_text())
        app = manifest['app']
        if app['id'] != app_id:
            raise DistributionError(f'{path}: application ID mismatch')
        image = app['container']['image']
        expected_repository = f'ghcr.io/forgesworn/{app_id}'
        if not image.startswith(expected_repository + ':'):
            raise DistributionError(f'{path}: unexpected image repository')
        version = image_version(image)
        if app.get('version') != version.split('-', 1)[0]:
            raise DistributionError(f'{path}: manifest/image version mismatch')
        manifest = json.loads(json.dumps(manifest))
        resolved = resolve_image(image, platforms, cosign_pubkey)
        digest = resolved.rsplit('@sha256:', 1)[1]
        manifest['app']['container']['image'] = resolved
        manifest['app']['container']['image_signature'] = f'cosign://sha256-{digest.replace(":", "_")}.sig'
        entries[app_id] = {'version': version, 'image': resolved, 'manifest': manifest}
    return entries


def kithmoot_entry(oci, allow_private):
    if not allow_private:
        raise DistributionError('KithMoot requires an explicit private-OCI distribution decision')
    manifest = yaml.safe_load(subprocess.check_output([
        'python3', str(ROOT / 'scripts/prepare-kithmoot-node.py'), '--manifest-template'], text=True))
    manifest['app']['container']['image'] = KITHMOOT_IMAGE
    if manifest['app']['container'].get('pull_policy') != 'never':
        raise DistributionError('KithMoot private image must use pull_policy: never')
    data = oci.read_bytes()
    return 'kithmoot-node', {
        'version': manifest['app']['version'],
        'image': KITHMOOT_IMAGE,
        'manifest': manifest,
        'delivery': {'type': 'private-oci', 'sha256': hashlib.sha256(data).hexdigest()},
    }


def prepare(output, platforms, cosign_pubkey, kithmoot_oci=None, allow_private=False):
    if output.exists() or output.is_symlink():
        raise DistributionError(f'Refusing to replace existing output: {output}')
    entries = public_entries(platforms, cosign_pubkey)
    if kithmoot_oci is not None:
        app_id, entry = kithmoot_entry(kithmoot_oci, allow_private)
        entries[app_id] = entry
    catalogue = {
        'schema': 1,
        'updated': datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        'apps': dict(sorted(entries.items())),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalogue, indent=2, ensure_ascii=False) + '\n')
    output.chmod(0o644)
    return catalogue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cosign-pubkey', type=Path, required=True)
    parser.add_argument('--platform', action='append', required=True,
                        help='Required OS/architecture; repeat for every supported target')
    parser.add_argument('--kithmoot-oci', type=Path,
                        help='Private KithMoot OCI archive; never uploaded by this tool')
    parser.add_argument('--allow-private-kithmoot', action='store_true',
                        help='Confirm the owner/upstream private-OCI distribution decision')
    args = parser.parse_args()
    if args.kithmoot_oci is None and args.allow_private_kithmoot:
        parser.error('--allow-private-kithmoot requires --kithmoot-oci')
    try:
        prepare(args.output.absolute(), args.platform, args.cosign_pubkey,
                args.kithmoot_oci, args.allow_private_kithmoot)
    except (DistributionError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + '\n')
    print('Unsigned candidate prepared. Cosign verification passed for every public image.')
    print('The authorised release-root holder must sign this file before installation or publication.')
    if args.kithmoot_oci:
        print('KithMoot remains private OCI delivery; its archive was not uploaded.')


if __name__ == '__main__':
    main()
