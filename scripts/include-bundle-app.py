#!/usr/bin/env python3
"""Include the bundle's pinned Spry manifest in the existing community listing.

The daemon's signed catalogue and its launch-authority checks are untouched.
"""
import argparse
import json
from pathlib import Path
import re

import yaml


def include(catalogue, manifest):
    app = manifest.get('app', {})
    image = app.get('container', {}).get('image', '')
    if app.get('id') != 'spry' or not isinstance(image, str) or not re.fullmatch(
            r'ghcr\.io/forgesworn/spry:\d+\.\d+\.\d+-[0-9a-f]{7}-\d+', image):
        raise ValueError('Expected the pinned Spry bundle manifest')
    apps = catalogue.get('apps')
    if not isinstance(apps, list) or not all(isinstance(item, dict) for item in apps):
        raise ValueError('Expected an existing community apps list')
    old = [item for item in apps if item.get('id') == 'spry']
    if any(item.get('source') != 'forgesworn-bundle' for item in old):
        raise ValueError('An independently supplied Spry listing needs review')
    metadata = app.get('metadata', {})
    entry = {'id': 'spry', 'title': app.get('name', 'Spry'),
             'version': str(app.get('version', '')), 'description': app.get('description', ''),
             'category': app.get('category', 'networking'), 'dockerImage': image,
             'author': metadata.get('author', 'ForgeSworn'), 'source': 'forgesworn-bundle',
             'repoUrl': 'https://github.com/forgesworn/spry-turn',
             'icon': metadata.get('icon', '/assets/icon/favico-black-v2.svg')}
    return {**catalogue, 'apps': [item for item in apps if item.get('id') != 'spry'] + [entry]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    result = include(json.loads(args.catalogue.read_text()), yaml.safe_load(args.manifest.read_text()))
    args.catalogue.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
