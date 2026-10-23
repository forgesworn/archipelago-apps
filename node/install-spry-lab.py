#!/usr/bin/env python3
"""Install a verified local Spry lab image through an existing Archy dashboard.

Run on the node as root. No firewall, DNS, discovery or certificate changes.
The dashboard password is consumed on the node, never sent back to a caller.
"""
import argparse
import getpass
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import yaml

APP = "spry-turn-lab"
IMAGE = "localhost/spry-turn:0.1.0-a76496bbcb60-2"
MANIFEST_SHA256 = "02f28c27e033a193c2aa268d0a73ff4498ae74828c7ab698ed22a012679f82c1"
PASSWORD_FILE = Path("/root/archy-spry-dashboard-password")
RUNTIME = Path("/opt/archipelago/web-ui/archipelago-runtime/apps")
USER_ENV = {"XDG_RUNTIME_DIR": "/run/user/1000", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus"}


class Refused(ValueError):
    """A bounded diagnostic containing no password, cookie or response body."""


def command(args, user=False):
    if user:
        args = ["runuser", "-u", "archipelago", "--", "env"] + [f"{k}={v}" for k, v in USER_ENV.items()] + args
    return subprocess.check_output(args, cwd="/", stderr=subprocess.PIPE, timeout=120)


def private_password(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
            raise Refused("Dashboard password file must be a root-owned regular file with mode 0600")
        value = stream.read(4097)
    if not value or len(value) > 4096 or not value.rstrip(b"\r\n"):
        raise Refused("Dashboard password file is empty or too large")
    return value.rstrip(b"\r\n").decode()


def verified_manifest(path, expected_sha):
    body = path.read_bytes()
    if expected_sha != MANIFEST_SHA256 or hashlib.sha256(body).hexdigest() != expected_sha:
        raise Refused("Manifest checksum differs")
    app = yaml.safe_load(body)["app"]
    container = app["container"]
    args = container["custom_args"]
    # Refuse exposure changes disguised as a lab install. This helper supports
    # only the reviewed local experiment; public candidates need another path.
    expected_args = ["serve", "--listen", "127.0.0.1:3478", "--allow-loopback-peers",
                     "--relay-ports", "49160:49191", "--max-allocations", "32",
                     "--max-per-user", "8", "--max-connections", "32", "--bytes-per-second", "1000000"]
    if (app["id"] != APP or container["image"] != IMAGE or args != expected_args
            or container.get("network") != "host" or container.get("pull_policy") != "never"
            or container.get("entrypoint") or app.get("volumes")
            or app.get("environment") or container.get("derived_env")
            or container.get("generated_certs") or container.get("build")
            or app.get("hooks")):
        raise Refused("Expected the reviewed loopback-only lab manifest")
    return body, app


class Dashboard:
    def __init__(self, origin):
        parsed = urllib.parse.urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise Refused("Use a plain HTTPS dashboard origin")
        self.origin = origin.rstrip("/")
        self.cookies = http.cookiejar.CookieJar()
        self.client = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                                  urllib.request.HTTPCookieProcessor(self.cookies),
                                                  NoRedirect())

    def call(self, method, params=None):
        headers = {"Content-Type": "application/json", "Origin": self.origin}
        csrf = next((c.value for c in self.cookies if c.name == "csrf_token"), None)
        if csrf:
            headers["X-CSRF-Token"] = csrf
        request = urllib.request.Request(self.origin + "/rpc/v1", headers=headers,
            data=json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}).encode())
        with self.client.open(request, timeout=30) as response:
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise Refused("Oversized dashboard response")
        reply = json.loads(body)
        if reply.get("error"):
            # Response bodies can contain identity or runtime data: never echo.
            raise Refused("Dashboard RPC refused " + method)
        return reply.get("result")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise Refused("Dashboard redirect refused")


def authenticate(dashboard, password, code_prompt=None):
    result = dashboard.call("auth.login", {"password": password})
    requires_totp = isinstance(result, dict) and result.get("requires_totp") is True
    if requires_totp:
        if code_prompt is None:
            raise Refused("Archy requires 2FA; run this installer in your SSH terminal with --interactive-login")
        code = code_prompt("Current six-digit Archy authenticator code: ")
        if not re.fullmatch(r"[0-9]{6}", code):
            raise Refused("Enter the current six-digit code, not an authenticator seed or QR token")
        try:
            dashboard.call("auth.login.totp", {"code": code})
        finally:
            del code
    dashboard.call("server.get-state")  # Verify full authentication before mutation.
    return requires_totp


def install(args):
    if os.geteuid() != 0:
        raise Refused("Run on the Archy node as root")
    if args.interactive_login and not sys.stdin.isatty():
        raise Refused("Interactive login requires an SSH terminal; connect with ssh -t")
    body, app = verified_manifest(args.manifest, args.manifest_sha256)
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", args.image_id):
        raise Refused("Expected the local image's immutable ID")
    if command(["uname", "-m"]).strip() != b"x86_64":
        raise Refused("This archive is for an x86-64 node")
    image = json.loads(command(["podman", "image", "inspect", IMAGE], user=True))[0]
    if image["Id"].removeprefix("sha256:") != args.image_id.removeprefix("sha256:") or image["Architecture"] != "amd64":
        raise Refused("The node's loaded image differs from the reviewed image")
    secret = Path("/var/lib/archipelago/secrets/spry-turn-rest-secret")
    secret_preexisted = secret.exists()
    # Authenticate before staging/restarting anything. Credentials and cookies
    # stay in this process; the file is deleted after successful full login.
    dashboard = Dashboard(args.dashboard_origin)
    try:
        password = getpass.getpass("Archy dashboard password: ") if args.interactive_login else private_password(PASSWORD_FILE)
        try:
            used_totp = authenticate(dashboard, password, getpass.getpass if args.interactive_login else None)
        finally:
            del password
        PASSWORD_FILE.unlink(missing_ok=True)
        destination = RUNTIME / APP
        if destination.exists():
            if (destination / "manifest.yml").read_bytes() != body:
                raise Refused("An existing lab manifest differs; refusing overwrite")
        else:
            destination.mkdir(mode=0o755)
            os.chown(destination, 1000, 1000)
            target = destination / "manifest.yml"
            target.write_bytes(body)
            os.chmod(target, 0o644)
            os.chown(target, 1000, 1000)
        command(["systemctl", "restart", "archipelago"])
        for _ in range(30):
            try:
                dashboard.call("health")
                break
            except (OSError, ValueError):
                time.sleep(1)
        else:
            raise Refused("Archy did not return after manifest reload")
        dashboard.call("package.install", {"id": APP, "dockerImage": IMAGE})
        for _ in range(60):
            try:
                inspect = json.loads(command(["podman", "inspect", APP], user=True))[0]
                if inspect["State"]["Running"]:
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(1)
        else:
            raise Refused("Lab container did not start")
        if not inspect["HostConfig"]["ReadonlyRootfs"] or inspect["HostConfig"]["NetworkMode"] != "host":
            raise Refused("Container isolation differs from the reviewed manifest")
        pid = inspect["State"]["Pid"]
        cgroup = next(line.split(":", 2)[2] for line in Path(f"/proc/{pid}/cgroup").read_text().splitlines()
                      if line.startswith("0::"))
        controls = Path("/sys/fs/cgroup") / cgroup.lstrip("/")
        memory_max = (controls / "memory.max").read_text().strip()
        cpu_max = (controls / "cpu.max").read_text().strip()
        quota, period = cpu_max.split()
        if memory_max != "134217728" or quota == "max" or int(quota) != int(period):
            raise Refused("Kernel cgroup limits differ from the reviewed manifest")
        info = secret.stat()
        value = secret.read_text().strip()
        if info.st_uid != 1000 or stat.S_IMODE(info.st_mode) != 0o600 or len(value) < 32:
            raise Refused("Node-generated secret permissions or value invalid")
        hidden = value not in json.dumps(inspect)
        if not hidden:
            raise Refused("Node secret appeared in container inspection")
        print(json.dumps({"app": APP, "running": True, "image_id": args.image_id,
            "totp_challenge_completed": used_totp,
            "manifest_sha256": args.manifest_sha256, "node_generated_secret_mode": "0600",
            "secret_existed_before_install": secret_preexisted,
            "secret_owner_uid": info.st_uid, "secret_absent_from_container_inspect": hidden,
            "network_mode": inspect["HostConfig"]["NetworkMode"],
            "readonly_root": inspect["HostConfig"]["ReadonlyRootfs"],
            "kernel_memory_max": memory_max, "kernel_cpu_max": cpu_max,
            "log_driver": inspect["HostConfig"].get("LogConfig", {}).get("Type"),
            "public_exposure": False, "discovery": False}))
    finally:
        try:
            dashboard.call("auth.logout")
        except (OSError, ValueError):
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--dashboard-origin", required=True)
    parser.add_argument("--interactive-login", action="store_true",
                        help="Prompt privately for the dashboard password and any 2FA code on the node")
    args = parser.parse_args()
    try:
        install(args)
    except Refused as error:
        parser.exit(1, str(error) + "\n")
    except Exception as error:
        # No traceback, request/response body, cookies, password or inspect dump.
        parser.exit(1, "Lab installation stopped (" + type(error).__name__ + "); inspect the node locally.\n")


if __name__ == "__main__":
    main()
