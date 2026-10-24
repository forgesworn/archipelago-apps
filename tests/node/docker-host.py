"""Actual installed controller -> Docker runtime -> Spry, disposable host only."""
import http.cookiejar
import json
from pathlib import Path
import secrets
import ssl
import subprocess
import time
import urllib.request

context = ssl.create_default_context(cafile='/etc/archipelago/ssl/ca.crt')
cookies = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
                                   urllib.request.HTTPCookieProcessor(cookies))


def rpc(method, params=None):
    headers = {'Content-Type': 'application/json'}
    for cookie in cookies:
        if cookie.name == 'csrf_token':
            headers['X-CSRF-Token'] = cookie.value
    request = urllib.request.Request('https://127.0.0.1/rpc/v1',
        json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(), headers)
    with client.open(request, timeout=30) as response:
        value = json.load(response)
    if 'error' in value:
        raise RuntimeError(f'{method} failed: {value["error"].get("message", "RPC error")}')
    return value.get('result')


def wait(check, description):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(description)


assert rpc('health')['status']
rpc('seed.generate')  # Never print generated recovery material.
password = secrets.token_urlsafe(32)
rpc('auth.setup', {'password': password})
rpc('auth.login', {'password': password})
identity = rpc('identity.create', {'name': 'Generated Docker owner', 'purpose': 'personal'})
assert identity['nostr_pubkey']
wait(lambda: subprocess.run(['systemctl', 'is-active', '--quiet', 'archipelago-fips'],
                           check=False).returncode == 0, 'Seeded FIPS did not start')
rpc('package.install', {'id': 'spry'})


def running():
    value = subprocess.check_output(['docker', 'inspect', 'spry'], stderr=subprocess.DEVNULL)
    return json.loads(value)[0]['State']['Running'] is True


wait(running, 'Archipelago did not install Spry through Docker')
inspection = json.loads(subprocess.check_output(['docker', 'inspect', 'spry']))[0]
assert inspection['HostConfig']['NetworkMode'] == 'host'
assert inspection['HostConfig']['Privileged'] is False
assert inspection['HostConfig']['ReadonlyRootfs'] is True
assert not inspection['HostConfig']['CapAdd']
assert inspection['HostConfig']['Memory'] == 128 * 1024 * 1024


def ready():
    with client.open('https://127.0.0.1:3744/v1/status', timeout=5) as response:
        state = json.load(response)
    return state.get('ready') is True and state.get('privateRelay') is True


wait(ready, 'Installed Spry did not become ready on the seeded mesh')
with client.open('https://127.0.0.1:3744/', timeout=5) as response:
    assert 'Pair with KithMoot' in response.read().decode()
dropin = Path('/etc/fips/fips.d/86-spry.nft')
assert dropin.is_file()
rpc('package.uninstall', {'id': 'spry'})
wait(lambda: not dropin.exists() and subprocess.run(
    ['docker', 'inspect', 'spry'], stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL).returncode != 0, 'Spry uninstall left its container or rule')
print(json.dumps({'passed': True, 'scope': 'fresh-debian-docker-host-install',
    'realRustController': True, 'existingDockerRuntime': True, 'seededFips': True,
    'spryReady': True, 'ownerPairingScreen': True, 'spryUninstall': True,
    'physicalHomeNetwork': False, 'dockerDesktopQualified': False}))
