"""Run only in the privileged disposable CI guest, with generated state."""
import fcntl
import hashlib
import http.cookiejar
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import ssl
import subprocess
import tarfile
import time
import urllib.request
import yaml

assert Path('/rehearsal/installed-node.py').is_file()
assert not subprocess.check_output(['ip','-4','route','show','default']).strip()
DATA = Path('/var/lib/archipelago')
APPS = [f'migration-{name}' for name in ('room','wallet','blob','files','overlap','stopped')]
USER = ['runuser','-u','archipelago','--','env','XDG_RUNTIME_DIR=/run/user/1000',
        'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus']


def run(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE)


def user(*args):
    return run(*USER,*args)


def wait(check, message, seconds=180):
    deadline=time.monotonic()+seconds
    last=None
    while time.monotonic()<deadline:
        try:
            if check(): return
        except Exception as error: last=type(error).__name__
        time.sleep(1)
    raise AssertionError(f'{message}; last error class: {last}')


cookies=http.cookiejar.CookieJar()
context=ssl.create_default_context(cafile='/etc/archipelago/ssl/ca.crt')
client=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),
    urllib.request.HTTPCookieProcessor(cookies))


def rpc(method, params=None):
    headers={'Content-Type':'application/json'}
    for cookie in cookies:
        if cookie.name=='csrf_token': headers['X-CSRF-Token']=cookie.value
    request=urllib.request.Request('https://127.0.0.1/rpc/v1',
        json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode(),headers)
    with client.open(request,timeout=30) as response: value=json.load(response)
    assert not value.get('error'), f'{method}: {value.get("error",{}).get("message", "refused")}'
    return value.get('result')


def healthy(version):
    value=rpc('health')
    return value['status']=='ok' and value['crash_recovery_complete'] and value['version'].startswith(version)


def idle():
    path=DATA/'update-transactions/lock'
    if not path.exists(): return True  # Older alpha has no transaction lock.
    with path.open() as stream:
        try: fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return False
        fcntl.flock(stream,fcntl.LOCK_UN)
    return True


def inspect(app):
    return json.loads(user('podman','inspect',app))[0]


def running(app):
    return inspect(app)['State']['Running']


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


wait(lambda: healthy('1.9.1'), 'Alpha baseline did not recover')
rpc('seed.generate')
password=secrets.token_urlsafe(32)
rpc('auth.setup',{'password':password})
rpc('auth.login',{'password':password})
identity=rpc('identity.create',{'name':'Generated migration owner','purpose':'personal'})
assert identity['nostr_pubkey']
# A local immutable image supplies anonymous config/database volumes, just as
# a volume-declaring installed application does. It is not a real wallet/app.
context_dir=Path('/tmp/migration-image');context_dir.mkdir()
(context_dir/'Dockerfile').write_text('FROM docker.io/library/busybox:1.37.0\nVOLUME ["/config", "/database"]\nCMD ["sleep", "86400"]\n')
os.chmod(context_dir,0o755)
user('podman','build','--pull=never','--network=none','-t','localhost/migration-fixture:1',str(context_dir))
for app in APPS:
    data=DATA/app;data.mkdir()
    with sqlite3.connect(data/'records.sqlite') as db:
        db.execute('create table records (id text primary key, value text)')
        db.execute('insert into records values (?, ?)',('existing-room','generated history'))
    (data/'blob').write_bytes(secrets.token_bytes(4096))
    os.chmod(data/'blob',0o600)
    os.setxattr(data/'blob','user.migration',b'preserve')
    run('chown','-R','1000:1000',str(data))
    manifest={'app':{'id':app,'name':app,'version':'1.0.0',
        'description':'Generated preservation fixture; no real application or funds',
        'container':{'image':'localhost/migration-fixture:1','pull_policy':'if-not-present','network':'none'},
        'resources':{'memory_limit':'64Mi','disk_limit':'1Gi'},
        'security':{'capabilities':[],'readonly_root':True,'network_policy':'isolated'},
        'ports':[],'volumes':[{'type':'bind','source':str(data),'target':'/data','options':['rw']}],
        'environment':[]}}
    for base in [Path('/opt/archipelago/apps'),Path('/opt/archipelago/web-ui/archipelago-runtime/apps')]:
        directory=base/app;directory.mkdir(parents=True,exist_ok=True)
        (directory/'manifest.yml').write_text(yaml.safe_dump(manifest))
run('chown','-R','1000:1000','/opt/archipelago')
run('systemctl','restart','archipelago')
wait(lambda: healthy('1.9.1'), 'Alpha restart failed')
rpc('auth.login',{'password':password})
for app in APPS:
    wait(idle,'Alpha lifecycle busy')
    rpc('package.install',{'id':app,'dockerImage':'localhost/migration-fixture:1'})
    wait(lambda: running(app),f'Alpha did not install {app}')
wait(idle,'Final alpha install busy')
rpc('package.stop',{'id':APPS[-1]})
wait(lambda: not running(APPS[-1]),'Stopped app did not stop')
# Write sentinels to the real anonymous volume mountpoints after installation.
volumes={}
for app in APPS:
    mounts=inspect(app)['Mounts']
    for mount in mounts:
        if mount['Destination'] in ('/config','/database'):
            path=Path(mount['Source'])/'migration-sentinel'
            path.write_text(f'generated:{app}:{mount["Destination"]}')
            volumes[str(path)]=digest(path)
assert len(volumes)==12, 'Image anonymous volumes were not created'
# Snapshot after alpha itself has performed its normal reconciliation.
run('systemctl','restart','archipelago')
wait(lambda: healthy('1.9.1'),'Alpha second baseline startup failed')
wait(idle,'Alpha baseline lifecycle busy')
before={app:inspect(app) for app in APPS}
files={str(DATA/app/name):digest(DATA/app/name) for app in APPS for name in ('records.sqlite','blob')}
recipes={app:digest(Path('/opt/archipelago/apps')/app/'manifest.yml') for app in APPS}
# Quiesce all generated writers before the backup. Never perform this on live data.
run('systemctl','stop','archipelago')
for app in APPS:
    user('systemctl','--user','stop',f'{app}.service')
wait(lambda: all(not running(app) for app in APPS),'Fixture writers did not stop')
backup=Path('/tmp/generated-pre-beta.tar')
roots=['var/lib/archipelago','opt/archipelago','etc/archipelago','etc/nginx','etc/ufw',
       'etc/ssh','etc/systemd/system/archipelago.service','home/archipelago/.config/containers',
       'usr/local/bin/archipelago']
run('tar','--xattrs','--acls','--numeric-owner','-cpf',str(backup),'-C','/',*roots)
restore=Path('/tmp/generated-restore');restore.mkdir()
run('tar','--xattrs','--acls','--numeric-owner','-xpf',str(backup),'-C',str(restore))
run('tar','--xattrs','--acls','--compare','-f',str(backup),'-C',str(restore))
for path, expected in {**files,**volumes}.items():
    restored=restore/path.lstrip('/')
    assert digest(restored)==expected
    original=Path(path)
    assert (restored.stat().st_uid,restored.stat().st_gid,restored.stat().st_mode)==(
        original.stat().st_uid,original.stat().st_gid,original.stat().st_mode)
for app in APPS:
    blob=restore/str(DATA/app/'blob').lstrip('/')
    assert os.getxattr(blob,'user.migration')==b'preserve'
    with sqlite3.connect(restore/str(DATA/app/'records.sqlite').lstrip('/')) as db:
        assert db.execute('pragma integrity_check').fetchone()==('ok',)
        assert db.execute('select value from records where id=?',('existing-room',)).fetchone()==('generated history',)
# Prepare an offline derivative. The installed tree itself is never the input.
snapshot=Path('/tmp/installed-recipes');snapshot.mkdir()
shutil.copytree('/opt/archipelago/apps',snapshot/'apps')
shutil.copytree('/opt/archipelago/docker',snapshot/'docker')
candidate=Path('/tmp/beta-candidate');candidate.mkdir()
with tarfile.open('/beta/docker-host-frontend/frontend.tar.gz') as archive:
    archive.extractall(candidate,filter='data')
# An overlapping new recipe must not supersede the accepted installed recipe.
overlap=candidate/'archipelago-runtime/apps'/APPS[-2]
overlap.mkdir(parents=True,exist_ok=True)
(overlap/'manifest.yml').write_text('incoming recipe must not replace installed recipe\n')
spec=importlib.util.spec_from_file_location('retain','/rehearsal/retain-installed-recipes.py')
retain=importlib.util.module_from_spec(spec);spec.loader.exec_module(retain)
prepared=Path('/tmp/beta-retained')
retain.prepare(snapshot,candidate,prepared,APPS)
# Rehearse interrupted pair replacement: persistent service guard refuses a
# mixed pair, then recovery restores only code before any beta process starts.
guard=Path('/etc/systemd/system/archipelago.service.d/99-migration-fixture.conf')
guard.parent.mkdir(exist_ok=True)
guard.write_text('[Service]\nExecStartPre=/usr/bin/test ! -e /etc/archipelago/migration-fixture-pending\n')
marker=Path('/etc/archipelago/migration-fixture-pending');marker.touch()
run('systemctl','daemon-reload')
shutil.copy2('/usr/local/bin/archipelago','/tmp/alpha-backend')
shutil.copy2('/beta/backend-review/archipelago','/usr/local/bin/archipelago')
os.chmod('/usr/local/bin/archipelago',0o755)
refused=subprocess.run(['systemctl','start','archipelago'],capture_output=True).returncode
assert refused!=0 and run('systemctl','show','archipelago','-p','MainPID','--value').strip()=='0'
shutil.copy2('/tmp/alpha-backend','/usr/local/bin/archipelago')
marker.unlink();run('systemctl','reset-failed','archipelago');run('systemctl','start','archipelago')
wait(lambda: healthy('1.9.1'),'Interrupted-pair code recovery failed')
rpc('auth.login',{'password':password})
run('systemctl','stop','archipelago');marker.touch()
# Complete pair installation only inside this disposable guest. No public OTA
# record is written, no signature is bypassed and no database is rolled back.
shutil.copy2('/beta/backend-review/archipelago','/usr/local/bin/archipelago')
os.chmod('/usr/local/bin/archipelago',0o755)
Path('/opt/archipelago/web-ui').rename('/opt/archipelago/web-ui.alpha-fixture')
shutil.copytree(prepared,'/opt/archipelago/web-ui')
run('chown','-R','1000:1000','/opt/archipelago/web-ui')
marker.unlink();run('systemctl','start','archipelago')
for iteration in range(2):
    wait(lambda: healthy('2.1.0-beta.2'),'Beta startup/recovery failed',300)
    rpc('auth.login',{'password':password})
    identities=rpc('identity.list')['identities']
    assert any(item['id']==identity['id'] and item['nostr_pubkey']==identity['nostr_pubkey'] for item in identities)
    wait(idle,'Beta lifecycle busy')
    for app in APPS:
        actual=inspect(app)
        assert actual['Image']==before[app]['Image'],f'Image changed: {app}'
        assert actual['Id']==before[app]['Id'],f'Container replaced: {app}'
        assert actual['Mounts']==before[app]['Mounts'],f'Mounts changed: {app}'
        assert running(app)==(app!=APPS[-1]),f'Running/stopped choice changed: {app}'
        assert digest(Path('/opt/archipelago/apps')/app/'manifest.yml')==recipes[app]
    for path,expected in {**files,**volumes}.items(): assert digest(Path(path))==expected
    if iteration==0: run('systemctl','restart','archipelago')
assert not Path('/etc/archipelago/public-update-runtime.json').exists()
print(json.dumps({'passed':True,'scope':'generated-alpha-1.9.1-to-beta2-rootless-podman',
    'baselineBackendSha256':digest(Path('/tmp/alpha-backend')),
    'betaBackendSha256':digest(Path('/usr/local/bin/archipelago')),
    'fixtureAppCount':6,'anonymousVolumeCount':len(volumes),'secondBetaRestart':True,
    'imagesContainersMountsRetained':True,'stoppedAppRetained':True,
    'existingPasswordLogin':True,'existingIdentityRetained':True,'privateAndOverlappingRecipesRetained':True,
    'generatedDatabaseBlobAndVolumeRestore':True,'numericOwnershipModesAndXattrs':True,
    'interruptedPairRefusedBeforeBetaStart':True,'prestartCodeRecovery':True,
    'liveNodeDataUsed':False,'exactPrivateAlphaBuildQualified':False,
    'actualSixApplicationsQualified':False,'postBetaWritesRollbackQualified':False}))
