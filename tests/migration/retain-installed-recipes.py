#!/usr/bin/env python3
"""Offline rehearsal only: retain explicit installed recipes in a candidate tree.

No activation, service control, signature admission or live-node data access.
The output is a private derivative and must never be published as upstream OTA.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import tempfile


def inventory(root):
    if any(path.is_symlink() for path in [root, *root.parents]):
        raise ValueError('Symlink in recipe ancestry')
    result = {}
    for path in [root, *sorted(root.rglob('*'))]:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError(f'Unsupported recipe object: {path}')
        if stat.S_ISREG(mode):
            if mode & 0o6000 or path.stat().st_nlink != 1:
                raise ValueError(f'Privileged or hardlinked recipe: {path}')
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            result[path.relative_to(root).as_posix()] = {
                'sha256': digest,
                'mode': stat.S_IMODE(mode),
            }
    return result


def prepare(installed, candidate, destination, app_ids):
    paths = [Path(p).absolute() for p in (installed, candidate, destination)]
    for path in paths:
        if '..' in path.parts or any(p.is_symlink() for p in [path, *path.parents]):
            raise ValueError('Paths must have regular, canonical ancestry')
        if path == Path('/') or any(path == Path(p) or Path(p) in path.parents
                                    for p in ('/opt/archipelago', '/var/lib/archipelago', '/etc/archipelago')):
            raise ValueError('Offline snapshot paths required; live roots refused')
    installed, candidate, destination = paths
    if any(a == b or a in b.parents or b in a.parents
           for i, a in enumerate(paths) for b in paths[i+1:]):
        raise ValueError('Separate input and output trees required')
    if destination.exists():
        raise ValueError('Destination must not exist')
    if not app_ids or len(set(app_ids)) != len(app_ids) or any(
            not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}', app) for app in app_ids):
        raise ValueError('Explicit unique installed app IDs required')
    candidate_before = inventory(candidate)
    if 'index.html' not in candidate_before or not (candidate/'archipelago-runtime/apps').is_dir():
        raise ValueError('Complete unpublished frontend tree required')
    retained = {}
    for app in app_ids:
        recipe = installed/'apps'/app
        if not (recipe/'manifest.yml').is_file():
            raise ValueError(f'Missing installed recipe: {app}')
        # The fixture owns the ID mapping; no inferred deletion/empty inventory.
        for domain in ('apps', 'docker'):
            source = installed/domain/app
            if source.exists() or source.is_symlink():
                retained[f'{domain}/{app}'] = inventory(source)
    # Validate everything before creating output; inputs are offline snapshots.
    work = Path(tempfile.mkdtemp(prefix='.recipe-rehearsal-', dir=destination.parent))
    try:
        output = work/'frontend'
        shutil.copytree(candidate, output)
        for relative, before in retained.items():
            source, target = installed/relative, output/'archipelago-runtime'/relative
            if target.exists():
                shutil.rmtree(target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target)
            if inventory(target) != before or inventory(source) != before:
                raise ValueError('Installed recipe changed during preparation')
        if inventory(candidate) != candidate_before:
            raise ValueError('Candidate changed during preparation')
        report = {'schema': 1, 'scope': 'generated-installed-node-rehearsal',
                  'upstream_ota_authority': False, 'apps': sorted(app_ids),
                  'candidate_files': candidate_before, 'retained_recipes': retained}
        (output/'FORGESWORN-REHEARSAL.json').write_text(json.dumps(report, sort_keys=True, indent=2)+'\n')
        # Single final rename; interrupted preparation never changes an input.
        output.rename(destination)
        return report
    finally:
        shutil.rmtree(work)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installed', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('apps', nargs='+')
    args = parser.parse_args()
    prepare(args.installed, args.candidate, args.destination, args.apps)
