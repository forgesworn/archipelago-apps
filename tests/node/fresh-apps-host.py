"""Actual fresh controller and four apps in the disposable Linux guest only."""
import fcntl
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import ssl
import subprocess
import sys
import time
import urllib.request

assert os.environ.get('ARCHY_FRESH_APPS_FIXTURE') == '1'
assert Path('/run/.containerenv').is_file()
assert Path('/bundle/local-apps/kithmoot-node/manifest.yml').is_file()
DATA = Path('/var/lib/archipelago')
HOST_IP = '8.8.8.8'
PUBLIC_HOST = 'fresh.archipelago.test'
IMAGES = {
    'spry': 'ghcr.io/forgesworn/spry:0.1.0-6b34f06-4',
    'wildbloom': 'ghcr.io/forgesworn/wildbloom:0.0.1-ee21ed5-5',
    'wildbloom-node': 'ghcr.io/forgesworn/wildbloom-node:0.3.5-b9a7cf4-2',
    'kithmoot-node': 'localhost/kithmoot-node:group-headroom-20261110-db34017b49e3',
}


def run(*args, env=None):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, env=env)
    except subprocess.CalledProcessError as error:
        print(error.stderr[-4000:], file=sys.stderr, flush=True)
        raise


def user(*args):
    return run('runuser', '-u', 'archipelago', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000',
               'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus', *args)


def wait(check, description, seconds=300):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except Exception as error:
            last = f'{type(error).__name__}: {error}'
        time.sleep(1)
    raise AssertionError(f'{description}; last error: {last}')


def lifecycle_idle():
    path = DATA / 'update-transactions/lock'
    if not path.exists():
        return False
    with path.open() as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(stream, fcntl.LOCK_UN)
    return True


def inspect(app):
    return json.loads(user('podman', 'inspect', app))[0]


def running(app):
    result = subprocess.run(['runuser', '-u', 'archipelago', '--', 'env',
        'XDG_RUNTIME_DIR=/run/user/1000', 'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus',
        'podman', 'container', 'exists', app], capture_output=True)
    assert result.returncode in (0, 1), result.stderr.decode()
    return result.returncode == 0 and inspect(app)['State']['Running'] is True


assert hashlib.sha256(Path('/bundle/fips-arm64.deb').read_bytes()).hexdigest() == \
    '4ae68e48378e2cdc500d829e7222e260bec4515a462edeb3110d8b733c93b3e8'
run('systemctl', 'mask', 'fips.service')
run('apt-get', '-o', 'DPkg::Lock::Timeout=600', 'install', '-y', '--no-install-recommends',
    'libnginx-mod-stream', '/bundle/fips-arm64.deb')
run('install', '-m', '0644', '/bundle/archy/image-recipe/configs/archipelago-fips.service',
    '/etc/systemd/system/archipelago-fips.service')
run('ip', 'address', 'add', f'{HOST_IP}/32', 'dev', 'lo')
run('install', '-d', '-m', '0750', '-o', 'root', '-g', 'archipelago', '/etc/archipelago/ssl/public')
run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
    '-subj', f'/CN={PUBLIC_HOST}', '-addext', f'subjectAltName=DNS:{PUBLIC_HOST},DNS:turn.{PUBLIC_HOST}',
    '-keyout', '/etc/archipelago/ssl/public/privkey.pem',
    '-out', '/etc/archipelago/ssl/public/fullchain.pem')
run('chown', 'root:archipelago', '/etc/archipelago/ssl/public/privkey.pem',
    '/etc/archipelago/ssl/public/fullchain.pem')
run('chmod', '0640', '/etc/archipelago/ssl/public/privkey.pem',
    '/etc/archipelago/ssl/public/fullchain.pem')
run('/opt/archipelago/scripts/setup-node-ca.sh')
for app in IMAGES:
    for root in (Path('/opt/archipelago/apps'), Path('/opt/archipelago/web-ui/archipelago-runtime/apps')):
        destination = root / app
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path('/bundle/local-apps') / app / 'manifest.yml', destination / 'manifest.yml')
run('chown', '-R', 'archipelago:archipelago', '/opt/archipelago/apps',
    '/opt/archipelago/web-ui/archipelago-runtime/apps')
run('install', '-d', '/etc/systemd/system/archipelago.service.d')
Path('/etc/systemd/system/archipelago.service.d/20-fresh-apps-fixture.conf').write_text(
    '[Service]\n'
    f'Environment="ARCHIPELAGO_HOST_IP={HOST_IP}"\n'
    f'Environment="ARCHIPELAGO_PUBLIC_HOST={PUBLIC_HOST}"\n'
    'Environment="ARCHIPELAGO_PUBLIC_CERT=/etc/archipelago/ssl/public/fullchain.pem"\n'
    'Environment="ARCHIPELAGO_PUBLIC_KEY=/etc/archipelago/ssl/public/privkey.pem"\n')
run('systemctl', 'daemon-reload')
run('systemctl', 'restart', 'archipelago')
run('sh', '-c', 'ip -4 route del default; ip -6 route del default 2>/dev/null || true')
assert not run('ip', '-4', 'route', 'show', 'default').strip()

context = ssl.create_default_context(cafile='/etc/archipelago/ssl/ca.crt')
cookies = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
    urllib.request.HTTPCookieProcessor(cookies))
CLIENT_IP = run('hostname', '-I').split()[0]
BASE = f'https://{CLIENT_IP}'


def rpc(method, params=None):
    headers = {'Content-Type': 'application/json'}
    for cookie in cookies:
        if cookie.name == 'csrf_token':
            headers['X-CSRF-Token'] = cookie.value
    request = urllib.request.Request(BASE + '/rpc/v1',
        json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(), headers)
    with client.open(request, timeout=120) as response:
        value = json.load(response)
    assert not value.get('error'), f'{method}: {value.get("error", {})}'
    return value.get('result')


def healthy():
    value = rpc('health')
    return value['status'] == 'ok' and value['crash_recovery_complete'] and value['version'] == '2.1.0-beta.2-dev'


wait(healthy, 'Exact candidate did not become healthy')
rpc('seed.generate')
password = secrets.token_urlsafe(32)
rpc('auth.setup', {'password': password})
rpc('auth.login', {'password': password})
identity = rpc('identity.create', {'name': 'Generated fresh install owner', 'purpose': 'personal'})
assert identity['nostr_pubkey']
wait(lambda: subprocess.run(['systemctl', 'is-active', '--quiet', 'archipelago-fips'],
    check=False).returncode == 0, 'Generated FIPS identity did not activate')

checks = {}
for app in ('wildbloom-node', 'wildbloom', 'spry', 'kithmoot-node'):
    wait(lifecycle_idle, f'Lifecycle busy before {app}')
    rpc('package.install', {'id': app, 'dockerImage': IMAGES[app]})
    wait(lambda app=app: running(app), f'{app} did not remain running')
    inspection = inspect(app)
    assert inspection['Config']['Image'] == IMAGES[app]
    checks[app] = {'installed': True, 'running': True, 'image': IMAGES[app],
                   'imageId': inspection['Image']}

def app_ready(app, port, path, marker=None):
    def check():
        with client.open(f'https://{CLIENT_IP}:{port}{path}', timeout=15) as response:
            body = response.read().decode(errors='replace')
            if app == 'spry':
                state = json.loads(body)
                return state.get('ready') is True and state.get('privateRelay') is True
            return response.status == 200 and (marker is None or marker in body)
    wait(check, f'{app} did not become ready')
    checks[app]['ready'] = True


app_ready('wildbloom-node', 3742, '/healthz')
app_ready('wildbloom', 3743, '/')
app_ready('spry', 3744, '/v1/status')
app_ready('kithmoot-node', 3753, '/', 'KithMoot')
wait(lifecycle_idle, 'Lifecycle did not settle after four installs')

expected_kithmoot_id = 'bc57a79baf111d3e2bc4a5c2c15bebb91c96469bca96dda49ceb32d51461cd86'
assert inspect('kithmoot-node')['Image'] == expected_kithmoot_id
assert not run('ip', '-4', 'route', 'show', 'default').strip()
print(json.dumps({
    'passed': True,
    'scope': 'fresh-debian-rootless-podman-local-image-install',
    'backendSha256': hashlib.sha256(Path('/usr/local/bin/archipelago').read_bytes()).hexdigest(),
    'frontendSha256': hashlib.sha256(Path('/bundle/frontend.tar.gz').read_bytes()).hexdigest(),
    'generatedIdentity': True,
    'externalNetwork': False,
    'localImageTransport': True,
    'signedCatalogueDistribution': False,
    'registryPullQualification': False,
    'physicalClients': False,
    'payments': False,
    'apps': checks,
}, indent=2))
