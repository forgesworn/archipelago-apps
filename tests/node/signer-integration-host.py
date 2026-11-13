"""Real NIP-46 signer against the exact candidate in a disposable Linux guest."""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import time
import urllib.request

assert os.environ.get('ARCHY_SIGNER_INTEGRATION_FIXTURE') == '1'
assert Path('/run/.containerenv').is_file()
assert Path('/signer/bunker.log').is_file()
os.environ.pop('SSL_CERT_FILE', None)
os.environ.pop('SSL_CERT_DIR', None)
DATA = Path('/var/lib/archipelago')


def run(*args):
    import subprocess
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE)


run('sh', '-c', 'ip -4 route del default; ip -6 route del default 2>/dev/null || true')
assert not run('ip', '-4', 'route', 'show', 'default').strip()
client_ip = run('hostname', '-I').split()[0]
context = ssl.create_default_context(cafile='/etc/archipelago/ssl/ca.crt')
cookies = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
    urllib.request.HTTPCookieProcessor(cookies))
BASE = f'https://{client_ip}'


def raw(method, params=None):
    headers = {'Content-Type': 'application/json'}
    for cookie in cookies:
        if cookie.name == 'csrf_token':
            headers['X-CSRF-Token'] = cookie.value
    request = urllib.request.Request(BASE + '/rpc/v1',
        json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(), headers)
    with client.open(request, timeout=90) as response:
        return json.load(response)


def rpc(method, params=None):
    value = raw(method, params)
    assert not value.get('error'), f'{method}: {value.get("error", {})}'
    return value.get('result')


def wait_result(method, params, terminal, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = rpc(method, params)
        if result.get('status') == terminal:
            return result
        assert result.get('status') == 'pending', result
        time.sleep(0.25)
    raise AssertionError(f'{method} did not reach {terminal}')


def healthy():
    try:
        value = rpc('health')
        return value['status'] == 'ok' and value['crash_recovery_complete'] and \
            value['version'] == '2.1.0-beta.2-dev'
    except Exception:
        return False


deadline = time.monotonic() + 180
while not healthy():
    assert time.monotonic() < deadline, 'Candidate did not become healthy'
    time.sleep(1)
credential = Path('/signer/generated-password')
if credential.exists():
    password = credential.read_text()
else:
    rpc('seed.generate')
    password = secrets.token_urlsafe(32)
    rpc('auth.setup', {'password': password})
    credential.write_text(password)
    credential.chmod(0o600)
rpc('auth.login', {'password': password})

body = Path('/signer/bunker.log').read_text()
match = re.search(r'bunker://[^\s]+', body)
assert match, 'Bunker did not publish its generated connection URI'
identity_list = rpc('identity.list')
identity_items = identity_list.get('identities', identity_list if isinstance(identity_list, list) else [])
linked = next((item for item in identity_items
               if item.get('name') == 'Generated nak integration signer run3' and item.get('origin') == 'linked'), None)
if linked is None:
    linked = rpc('identity.link-nip46', {
        'bunker_uri': match.group(0), 'name': 'Generated nak integration signer run3', 'purpose': 'personal'})
assert linked['origin'] == 'linked' and linked['nostr_pubkey']
export_params = {'id': linked['id'], 'password': password}
export_grant = rpc('auth.reauthenticate', {
    'method': 'identity.export-keys', 'params': export_params, 'password': password, 'code': ''})
exported = rpc('identity.export-keys', dict(export_params, reauth_token=export_grant['reauth_token']))


def key_names(value):
    if isinstance(value, dict):
        return {key for key, item in value.items() for key in [key, *key_names(item)]}
    if isinstance(value, list):
        return {key for item in value for key in key_names(item)}
    return set()


assert not key_names(exported) & {
    'nostr_secret', 'bunker_secret', 'pairing_key', 'client_secret', 'secret', 'private_key'}
assert exported.get('nostr_secret_hex') is None and exported.get('nostr_nsec') is None

created_at = int(time.time())
event = {'kind': 1, 'created_at': created_at,
         'content': 'Synthetic linked-signer integration event; not for publication',
         'tags': [['integration', 'linked-signer-20261113']]}
signing = {'id': linked['id'], 'event': event}
grant = rpc('auth.reauthenticate', {
    'method': 'identity.nostr-sign', 'params': signing, 'password': password, 'code': ''})
signed = rpc('identity.nostr-sign', dict(signing, reauth_token=grant['reauth_token']))
assert signed['pubkey'] == linked['nostr_pubkey'] and signed['kind'] == 1
assert signed['created_at'] == created_at and signed['content'] == event['content']
assert re.fullmatch(r'[0-9a-f]{64}', signed['id'])
assert re.fullmatch(r'[0-9a-f]{128}', signed['sig'])
replay = raw('identity.nostr-sign', dict(signing, reauth_token=grant['reauth_token']))
assert replay.get('error'), 'Fresh-authorisation token was reusable'
Path('/signer/signed-event.json').write_text(json.dumps(signed) + '\n')

if not any(item['identity_id'] == linked['id'] for item in rpc('auth.signer.list')):
    enrol_params = {'identity_id': linked['id'], 'password': password}
    enrol_grant = rpc('auth.reauthenticate', {
        'method': 'auth.signer.enrol.start', 'params': enrol_params, 'password': password, 'code': ''})
    enrol = rpc('auth.signer.enrol.start', dict(enrol_params, reauth_token=enrol_grant['reauth_token']))
    assert re.fullmatch(r'[0-9]{4}', enrol['code'])
    enrolled = wait_result('auth.signer.enrol.finish', {'attempt_id': enrol['attempt_id']}, 'enrolled')
    assert enrolled['identity_id'] == linked['id']
assert any(item['identity_id'] == linked['id'] for item in rpc('auth.signer.list'))

cookies.clear()
assert rpc('auth.login.signer.available', {}) is True
login = rpc('auth.login.signer.start', {})
assert re.fullmatch(r'[0-9]{4}', login['code'])
approved = wait_result('auth.login.signer.finish', {'attempt_id': login['attempt_id']}, 'approved')
assert approved['status'] == 'approved'
assert any(item['identity_id'] == linked['id'] for item in rpc('auth.signer.list'))
login_replay = raw('auth.login.signer.finish', {'attempt_id': login['attempt_id']})
assert login_replay.get('error'), 'Completed signer-login attempt was reusable'
credential.unlink()

print(json.dumps({
    'passed': True,
    'scope': 'real-nak-nip46-linked-identity-and-signer-login',
    'backendSha256': hashlib.sha256(Path('/usr/local/bin/archipelago').read_bytes()).hexdigest(),
    'externalNetwork': False,
    'publicRelay': False,
    'linkedIdentity': True,
    'secretFreeExport': True,
    'freshSigning': True,
    'freshGrantReplayRefused': True,
    'loginEnrolment': True,
    'signerLogin': True,
    'loginReplayRefused': True,
    'automaticSignerApproval': True,
    'humanOrPhysicalSignerApproval': False,
    'browserUIAcceptance': False,
    'publication': False,
}, indent=2))
