#!/usr/bin/env python3
"""Checked, reversible 1.9.1 p1/p2/p3 -> backend p3 / catalogue p5 node update.

Run on the existing node as root. Without --apply this only inspects the node.
MIT; see LICENSE in the archipelago-apps repository.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import urllib.parse
import uuid


BASE = "https://github.com/forgesworn/archipelago-apps/releases/download/"
OLD_BACKEND = "d0bf29292bf36a2cafd6c455af2250e7d9af8cab63da84932f1b6ce857072cc9"
PREVIOUS_BACKEND = "7f24acff674ac077b1534fd11d56f28e72707480b95e9f7a53a2bb869bdd6546"
BACKEND = ("backend-v1.9.1-alpha-p3/archipelago",
           "e6158a4a34641562b77a1cbe754e60168caa07a6d558cb1fa9d7fdf1d3e7d94e", 84409856)
FRONTEND = ("frontend-v1.9.1-alpha-p5/frontend.tar.gz",
            "c7b8ad9bf2407cfcf2e83941d7360fca6ba0a4f309a989307b8d23e3c76bbfb3", 108023464)
IMAGE = "ghcr.io/forgesworn/spry:0.1.0-6b34f06-3"
INDEX_SHA = "d1de8b97ff0e0230befae2ae13b657328ff9be76f3d745911e7058ae2a410eef"
SPRY_SHA = "6092a8aeb68017b28530c1e33788da3dd2be6b0fed43af931f8898b0b554b7d6"
CATALOGUE_SHA = "d5229d7a8f1d3077e60c7876300a0d8bb07532c23a377b2338443857e05fa089"
DASHBOARD_ORIGINS = "https://{{HOST_IP}},https://{{HOST_MDNS}},https://{{HOST_IP}}:3744,https://{{HOST_MDNS}}:3744"
ORIGIN_TEMPLATE = re.compile(r"(key: SPRY_DASHBOARD_ORIGINS, template: ')" +
                             re.escape(DASHBOARD_ORIGINS) + r"([^'\n]*)(')")


class Refused(RuntimeError):
    pass


class Paths:
    def __init__(self, root=Path("/")):
        self.root = root
        self.binary = root / "usr/local/bin/archipelago"
        self.web = root / "opt/archipelago/web-ui"
        self.apps = root / "opt/archipelago/apps"
        self.lifecycle = root / "var/lib/archipelago/update-transactions/lock"
        self.ca = root / "etc/archipelago/ssl/ca.crt"
        self.mesh = root / "sys/class/net/fips0"


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def dashboard_origins(text):
    """Read only explicit HTTPS dashboard origins, never a wildcard or URL path."""
    matches = list(ORIGIN_TEMPLATE.finditer(text))
    if not matches:
        return []
    if len(matches) != 1:
        raise Refused("Expected one Spry dashboard-origin template")
    suffix = matches[0][2]
    if not suffix:
        return []
    origins = suffix.removeprefix(",").split(",")
    if not suffix.startswith(",") or len(origins) > 16 or len(suffix) > 4096:
        raise Refused("Invalid configured Spry dashboard origins")
    for origin in origins:
        try:
            url = urllib.parse.urlsplit(origin)
            valid = (url.scheme == "https" and url.hostname and
                     re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", url.hostname) and
                     url.username is None and url.password is None and
                     url.port in (None, 443, 3744) and
                     not (url.path or url.query or url.fragment) and
                     origin == urllib.parse.urlunsplit(url))
        except ValueError:
            valid = False
        if not valid:
            raise Refused("Invalid configured Spry dashboard origin")
    return list(dict.fromkeys(origins))


def spry_manifest_digest(path):
    text = path.read_text()
    if dashboard_origins(text):
        text = ORIGIN_TEMPLATE.sub(lambda m: m[1] + DASHBOARD_ORIGINS + m[3], text)
    return hashlib.sha256(text.encode()).hexdigest()


def preserve_dashboard_origins(existing, staged):
    if not existing.is_file() or existing.is_symlink():
        return
    origins = dashboard_origins(existing.read_text())
    if origins:
        text = staged.read_text()
        if len(ORIGIN_TEMPLATE.findall(text)) != 1:
            raise Refused("Updated Spry manifest cannot retain configured dashboard origins")
        staged.write_text(ORIGIN_TEMPLATE.sub(
            lambda m: m[1] + DASHBOARD_ORIGINS + "," + ",".join(origins) + m[3], text))


def inspect(paths):
    if paths.binary.is_symlink() or not paths.binary.is_file():
        raise Refused("Expected an existing, regular Archipelago backend file")
    if paths.web.is_symlink() or not paths.web.is_dir():
        raise Refused("This updater requires the existing directory-based web-ui layout")
    current = digest(paths.binary)
    if current not in (OLD_BACKEND, PREVIOUS_BACKEND, BACKEND[1]):
        raise Refused("Backend is not the published 1.9.1 p1, p2 or p3; refusing an unknown or cross-version update")
    if paths.lifecycle.is_symlink() or not paths.lifecycle.is_file():
        raise Refused("The existing node lifecycle lock is missing or symlinked")
    if shutil.disk_usage(paths.web.parent).free < 2 * 1024**3:
        raise Refused("At least 2 GiB free is required on the web-ui filesystem")
    expected = [(paths.web / "index.html", INDEX_SHA),
                (paths.web / "catalog.json", CATALOGUE_SHA),
                (paths.web / "archipelago-runtime/apps/spry/manifest.yml", SPRY_SHA),
                (paths.apps / "spry/manifest.yml", SPRY_SHA)]
    already_current = current == BACKEND[1] and all(
        path.is_file() and not path.is_symlink() and
        (spry_manifest_digest(path) if path.name == "manifest.yml" else digest(path)) == sha
        for path, sha in expected)
    return {"backendSha256": current, "targetBackend": "1.9.1-alpha-p3",
            "targetCatalogue": "1.9.1-alpha-p5", "meshRoutePresent": paths.mesh.exists(),
            "alreadyCurrent": already_current, "changesApplied": False}


@contextlib.contextmanager
def locked(path, create=False):
    flags = os.O_RDWR | os.O_NOFOLLOW | (os.O_CREAT if create else 0)
    fd = os.open(path, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Refused("Another node lifecycle operation is busy; retry when it finishes") from error
        yield
    finally:
        os.close(fd)


def download(spec, target):
    relative, sha, size = spec
    subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                    "--max-time", "600", "--max-filesize", str(size),
                    "--output", str(target), BASE + relative], check=True)
    if target.stat().st_size != size or digest(target) != sha:
        raise Refused("Release size or SHA-256 does not match the pinned public artefact")


def extract(archive, destination):
    destination.mkdir(mode=0o755)
    total = 0
    with tarfile.open(archive, "r:gz") as source:
        for number, member in enumerate(source):
            name = Path(member.name)
            total += member.size
            if (name.is_absolute() or ".." in name.parts or
                    not (member.isdir() or member.isfile()) or
                    total > 2 * 1024**3 or number >= 100000):
                raise Refused("Unsafe or oversized frontend archive")
            target = destination / name
            if member.isdir():
                target.mkdir(mode=0o755, parents=True, exist_ok=True)
            else:
                target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                with source.extractfile(member) as file, target.open("xb") as output:
                    shutil.copyfileobj(file, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
    if not (destination / "index.html").is_file():
        raise Refused("Frontend has no index.html")
    manifest = destination / "archipelago-runtime/apps/spry/manifest.yml"
    if not manifest.is_file() or IMAGE not in manifest.read_text():
        raise Refused("Frontend does not contain the expected Spry package")


def overlay(source, destination, excluded, relative=Path()):
    """Preserve existing runtime customisations; never follow their symlinks."""
    if source.is_symlink():
        raise Refused("Cannot automatically preserve a symlinked runtime root")
    if not source.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    for entry in source.iterdir():
        rel = relative / entry.name
        if rel.as_posix() in excluded:
            continue
        target = destination / entry.name
        if entry.is_symlink():
            if rel.as_posix() == "apps":
                raise Refused("Cannot automatically preserve a symlinked apps catalogue")
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            elif target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(os.readlink(entry))
        elif entry.is_dir():
            if target.is_symlink() or (target.exists() and not target.is_dir()):
                target.unlink()
            overlay(entry, target, excluded, rel)
        elif entry.is_file():
            if target.is_dir() and not target.is_symlink():
                shutil.rmtree(target)
            elif target.is_symlink():
                target.unlink()
            shutil.copy2(entry, target)
        else:
            raise Refused("Unsupported special file in the existing runtime")


def ownership(tree, uid, gid):
    os.chown(tree, uid, gid, follow_symlinks=False)
    for folder, dirs, files in os.walk(tree, followlinks=False):
        for name in dirs + files:
            os.chown(Path(folder) / name, uid, gid, follow_symlinks=False)


def service(action):
    subprocess.run(["systemctl", action, "archipelago"], check=True, timeout=90)


def healthy(paths):
    try:
        context = ssl.create_default_context(cafile=paths.ca)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                           urllib.request.HTTPSHandler(context=context))
        request = urllib.request.Request("https://127.0.0.1/rpc/v1",
            b'{"jsonrpc":"2.0","id":1,"method":"health"}',
            {"Content-Type": "application/json"})
        with opener.open(request, timeout=3) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            return False
        value = json.loads(raw)
        return (isinstance(value, dict) and value.get("error") is None and
                isinstance(value.get("result"), dict) and bool(value["result"].get("status")))
    except (OSError, ValueError):
        return False


def wait_healthy(check, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(1)
    raise Refused("Updated controller did not become healthy")


def install(paths, binary, web, uid, gid, control=service, check=None, timeout=90):
    """Swap only the backend and frontend, restoring both after failure."""
    if digest(binary) != BACKEND[1]:
        raise Refused("Staged backend SHA-256 does not match the pinned release")
    spry = web / "archipelago-runtime/apps/spry/manifest.yml"
    preserve_dashboard_origins(paths.apps / "spry/manifest.yml", spry)
    spry_sha = digest(spry)
    check = check or (lambda: healthy(paths))
    identifier = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
    backups = paths.web.parent / ".forgesworn-bundle-backups"
    backups.mkdir(mode=0o700, exist_ok=True)
    if backups.is_symlink() or backups.stat().st_uid != os.geteuid() or backups.stat().st_mode & 0o077:
        raise Refused("Backup directory must be private and owned by this administrator")
    backup = backups / identifier
    backup.mkdir(mode=0o700)
    old_binary = backup / "archipelago"
    old_web = backup / "web-ui"
    temporary_binary = paths.binary.parent / (".archipelago-" + identifier)
    attempted_stop = swapped = False
    previous_sha = digest(paths.binary)
    try:
        with locked(paths.lifecycle):
            attempted_stop = True
            control("stop")
            shutil.copy2(paths.binary, old_binary)
            if paths.apps.is_symlink():
                raise Refused("Cannot automatically back up a symlinked apps root")
            if paths.apps.exists():
                shutil.copytree(paths.apps, backup / "apps", symlinks=True)
            overlay(paths.web / "archipelago-runtime", web / "archipelago-runtime", {"apps/spry"})
            overlay(paths.apps, web / "archipelago-runtime/apps", {"spry"})
            if digest(spry) != spry_sha:
                raise Refused("Existing runtime overrides changed the staged Spry manifest")
            ownership(web, uid, gid)
            shutil.copy2(binary, temporary_binary)
            temporary_binary.chmod(0o755)
            os.replace(paths.web, old_web)
            swapped = True
            os.replace(web, paths.web)
            os.replace(temporary_binary, paths.binary)
        control("start")
        wait_healthy(check, timeout)
        promoted = paths.apps / "spry/manifest.yml"
        if digest(paths.binary) != BACKEND[1] or not promoted.is_file() or digest(promoted) != spry_sha:
            raise Refused("Running node did not promote the expected backend and Spry catalogue")
        receipt = {"updated": True, "previousBackendSha256": previous_sha,
                   "backendSha256": BACKEND[1], "catalogueArchiveSha256": FRONTEND[1],
                   "spryManifestSha256": spry_sha, "backup": str(backup),
                   "meshRoutePresent": paths.mesh.exists()}
        (backup / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
        return receipt
    except BaseException as error:
        if attempted_stop:
            try:
                with locked(paths.lifecycle):
                    control("stop")
                    if swapped:
                        if paths.web.exists():
                            os.replace(paths.web, backup / "failed-web-ui")
                        os.replace(old_web, paths.web)
                        shutil.copy2(old_binary, temporary_binary)
                        os.replace(temporary_binary, paths.binary)
                    # Bootstrap promotes this payload again on restart. Keep
                    # live private app definitions through rollback as well.
                    overlay(backup / "apps", paths.web / "archipelago-runtime/apps", set())
                control("start")
                wait_healthy(check, timeout)
            except BaseException as rollback_error:
                raise Refused(f"Update failed; rollback needs attention. Backup: {backup}") from rollback_error
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise Refused(f"Update failed; previous bundle restored. Backup: {backup}") from error
        raise
    finally:
        temporary_binary.unlink(missing_ok=True)
        if not attempted_stop:
            backup.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="back up, update and restart this existing node")
    mode.add_argument("--check", action="store_true", help="inspect this node without downloading or changing files (default)")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise Refused("Run on the node with sudo or as root")
    paths = Paths()
    plan = inspect(paths)
    plan["controllerHealthy"] = healthy(paths)
    if not plan["controllerHealthy"]:
        raise Refused("Existing controller health could not be verified using the node CA")
    if not args.apply or plan["alreadyCurrent"]:
        print(json.dumps(plan, indent=2))
        return
    owner = pwd.getpwnam("archipelago")
    with locked(Path("/run/lock/forgesworn-bundle-update.lock"), create=True):
        with tempfile.TemporaryDirectory(prefix=".forgesworn-update-", dir=paths.web.parent) as directory:
            stage = Path(directory)
            binary, archive, web = stage / "archipelago", stage / "frontend.tar.gz", stage / "web-ui"
            download(BACKEND, binary)
            download(FRONTEND, archive)
            extract(archive, web)
            inspect(paths)  # Refuse a concurrent version change before stopping.
            print(json.dumps(install(paths, binary, web, owner.pw_uid, owner.pw_gid), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (Refused, OSError, subprocess.SubprocessError) as error:
        raise SystemExit(str(error)) from error
