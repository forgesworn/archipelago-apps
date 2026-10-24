#!/usr/bin/env python3
"""Install the isolated public issuer on the explicit qualification node.

This adds only its own service, pool, nginx listener and TCP7443 firewall rule.
The operator's private dashboard and existing Spry binary remain unchanged.
Run only after inspecting the configuration and certificate; keep the receipt.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

DEST = Path('/opt/archipelago/spry-public-issuer')
DATA = Path('/var/lib/spry-public-issuer')
NGINX = Path('/etc/nginx/conf.d/spry-public-issuer.conf')
STATE = Path('/root/archy-spry-qualification/public-issuer')
UNITS = ('spry-public-issuer.service', 'spry-public-credentials.service', 'spry-public-credentials.timer')


def run(args):
    return subprocess.check_output(args, cwd='/', stderr=subprocess.PIPE, timeout=120)


def rollback():
    receipt = json.loads((STATE / 'receipt.json').read_text())
    subprocess.run(['systemctl', 'disable', '--now', 'spry-public-credentials.timer', 'spry-public-issuer.service'], cwd='/', capture_output=True, timeout=30)
    if receipt.get('firewall'):
        run(['ufw', '--force', 'delete', 'allow', '7443/tcp'])
    for name in UNITS:
        Path('/etc/systemd/system', name).unlink(missing_ok=True)
    NGINX.unlink(missing_ok=True)
    run(['nginx', '-t']); run(['systemctl', 'reload', 'nginx'])
    run(['systemctl', 'daemon-reload'])
    # These directories were created exclusively by this installation. The
    # node secret, Spry container and dashboard are outside both trees.
    shutil.rmtree(DEST, ignore_errors=True)
    shutil.rmtree(DATA, ignore_errors=True)
    receipt['status'] = 'rolled-back'
    (STATE / 'receipt.json').write_text(json.dumps(receipt, indent=2))


def install(source, binary):
    if any(path.exists() for path in (DEST, DATA, NGINX, STATE)):
        raise ValueError('Refusing to overwrite an existing public issuer')
    if any(Path('/etc/systemd/system', name).exists() for name in UNITS):
        raise ValueError('Issuer systemd unit already exists')
    if b':7443 ' in run(['ss', '-lnt']):
        raise ValueError('Issuer port already occupied')
    if b'7443/tcp' in run(['ufw', 'status']):
        raise ValueError('Firewall rule already exists')
    if binary.read_bytes()[:4] != b'\x7fELF':
        raise ValueError('Supply the reviewed native Linux binary')
    run(['openssl', 'x509', '-in', '/etc/letsencrypt/live/demo.forgesworn.dev/fullchain.pem', '-checkend', '86400', '-noout'])
    try:
        pwd.getpwnam('spry-issuer')
    except KeyError:
        run(['useradd', '--system', '--no-create-home', '--shell', '/usr/sbin/nologin', 'spry-issuer'])
    else:
        raise ValueError('Issuer user already exists; inspect before installing')
    user = pwd.getpwnam('spry-issuer')
    STATE.mkdir(mode=0o700)
    receipt = {'status': 'preparing', 'firewall': False,
               'binarySha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
               'secretsRead': False, 'privateDashboardOpened': False}
    def save():
        path = STATE / 'receipt.json'; path.write_text(json.dumps(receipt, indent=2)); path.chmod(0o600)
    save()
    try:
        DEST.mkdir(mode=0o755)
        shutil.copyfile(binary, DEST / 'spry-public-issuer')
        (DEST / 'spry-public-issuer').chmod(0o755)
        shutil.copyfile(source / 'refill.py', DEST / 'refill.py')
        DATA.mkdir(mode=0o750); os.chown(DATA, 0, user.pw_gid)
        runtime = DATA / 'runtime'; runtime.mkdir(mode=0o700); os.chown(runtime, user.pw_uid, user.pw_gid)
        for name in UNITS:
            shutil.copyfile(source / name, Path('/etc/systemd/system', name))
        shutil.copyfile(source / 'nginx.conf', NGINX)
        run(['nginx', '-t'])
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', 'spry-public-credentials.service'])
        run(['systemctl', 'enable', '--now', 'spry-public-issuer.service', 'spry-public-credentials.timer'])
        run(['systemctl', 'reload', 'nginx'])
        receipt['firewall'] = True; save()
        run(['ufw', 'allow', '7443/tcp', 'comment', 'spry-public-credentials'])
        receipt['status'] = 'active'; save()
        print(json.dumps(receipt))
    except BaseException:
        rollback()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'rollback'))
    parser.add_argument('--binary', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, 'Run as the node owner.\n')
    try:
        if args.action == 'rollback':
            rollback()
        elif args.binary:
            install(Path(__file__).resolve().parent, args.binary)
        else:
            raise ValueError('Supply the reviewed native Linux binary')
    except Exception as error:
        parser.exit(1, f'Issuer operation failed ({type(error).__name__}); inspect private node receipt.\n')
