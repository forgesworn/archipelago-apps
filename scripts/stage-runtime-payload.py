#!/usr/bin/env python3
"""Stage patched beta runtime helpers into an unpublished frontend tree."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


def stage(source, destination, version, commit, patch_digest):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Source and packaging destination must be separate trees')
    if not (destination / 'index.html').is_file():
        raise ValueError('Expected an unpublished frontend packaging tree')
    runtime = destination / 'archipelago-runtime'
    if runtime.is_symlink() or not runtime.is_dir():
        raise ValueError('Missing regular runtime directory')
    spec = importlib.util.spec_from_file_location('archy_release_payload', source / 'scripts/release_payload.py')
    payload = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(payload)
    # Validate the entire source domain before replacing either directory.
    expected = payload.runtime_sources(source)
    for domain in ('scripts', 'image-recipe/configs'):
        target = runtime / domain
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != destination.parent):
            raise ValueError('Symlink in runtime destination')
        if target.exists():
            shutil.rmtree(target)
    payload.stage(source, destination, version, commit)
    for name, raw in expected.items():
        if (destination / name).read_bytes() != raw:
            raise ValueError(f'Runtime payload differs from patched source: {name}')
    declaration = json.loads((runtime / 'RELEASE-PAYLOAD.json').read_text())
    if declaration != payload.declaration(source, version, commit):
        raise ValueError('Runtime declaration mismatch')
    # This is a ForgeSworn derivative, not the upstream signed release.
    (runtime / 'FORGESWORN-BUNDLE.json').write_text(json.dumps({
        'schema_version': 1, 'upstream_version': version,
        'patched_source_commit': commit, 'patches_sha256': patch_digest,
        'runtime_declaration_sha256': hashlib.sha256(
            (runtime / 'RELEASE-PAYLOAD.json').read_bytes()).hexdigest(),
    }, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--patches-sha256', required=True)
    args = parser.parse_args()
    stage(args.source, args.destination, args.version, args.commit, args.patches_sha256)
