#!/usr/bin/env python3
"""Owner-only promotion of the installed, pinned lab to an invited TURN candidate.

Not a general package installer. No discovery, room service or HTTP issuer.
Run on the qualification node as root. Keep the backup for rollback.
"""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

import yaml

APP = "spry-turn-lab"
LAB_SHA = "d10a81f2b565c0f4e348f9b06cd3f5b637cc9a1f31683e4fb4f840ce5c079688"
IMAGE_ID = "a1eebc1872ead4c304cd53e746f93d39c019dda37cdbf95c031fce4d77b7b6b0"
MANIFESTS = [Path(p) / APP / "manifest.yml" for p in (
    "/opt/archipelago/web-ui/archipelago-runtime/apps", "/opt/archipelago/apps")]
TLS = Path("/var/lib/archipelago/spry-turn-lab/tls")
HOOK = Path("/etc/letsencrypt/renewal-hooks/deploy/spry-turn-certificate")
STATE = Path("/root/archy-spry-qualification/public-candidate")
RULES = ("3478/udp", "3478/tcp", "5349/tcp", "49160:49191/udp", "80/tcp")
USER_ENV = ("XDG_RUNTIME_DIR=/run/user/1000", "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus")


def run(args, user=False):
    if user:
        args = ["runuser", "-u", "archipelago", "--", "env", *USER_ENV, *args]
    return subprocess.check_output(args, cwd="/", stderr=subprocess.PIPE, timeout=120)


def endpoint(hostname, ip):
    if (not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", hostname)
            or "." not in hostname or len(hostname) > 253):
        raise ValueError("Expected an explicit DNS hostname")
    address = ipaddress.ip_address(ip)
    if address.version != 4 or not address.is_global:
        raise ValueError("This qualification helper requires a concrete public IPv4 address")


def public_manifest(body, ip):
    if hashlib.sha256(body).hexdigest() != LAB_SHA:
        raise ValueError("Installed lab manifest differs from the reviewed revision")
    value = yaml.safe_load(body)
    app = value["app"]
    app["name"] = "Spry TURN (invited qualification)"
    app["description"] = "Operator-controlled public transport candidate; offline expiring credentials, no room service or discovery."
    args = app["container"]["custom_args"]
    args.remove("--allow-loopback-peers")
    args[args.index("--listen") + 1] = f"{ip}:3478"
    args += ["--relay-ip", ip, "--tls-listen", f"{ip}:5349",
             "--tls-cert", "/tls/fullchain.pem", "--tls-key", "/tls/privkey.pem"]
    app["volumes"] = [{"type": "bind", "source": str(TLS), "target": "/tls", "options": ["ro"]}]
    app["ports"] = [{"host": port, "container": port, "protocol": proto,
                     "bind": ip, "auth": "none", "auth_rationale":
                     "TURN protocol authenticates short-lived node-issued credentials; no HTTP gate or anonymous credential issuer."}
                    for port, proto in ((3478, "udp"), (3478, "tcp"), (5349, "tcp"))]
    return yaml.safe_dump(value, sort_keys=False).encode()


def acme_site(body):
    # Preserve the existing, explicit public-address vhosts and TLS dashboard.
    # Only its public HTTP redirect is replaced. Unknown-host default is 444.
    old = b"location / { return 301 https://$host$request_uri; }"
    if body.count(old) != 1 or b"root /var/www/letsencrypt;" not in body:
        raise ValueError("Expected the inspected webroot challenge configuration")
    prefix = body.split(b"server {", 3)[:3]
    if b"location / { return 444; }" not in b"server {".join(prefix):
        raise ValueError("Expected a closed default HTTP vhost")
    return body.replace(old, b"location / { return 404; }")


def private_write(path, body, uid=0):
    if path.is_symlink():
        raise ValueError("Refusing symbolic-link destination")
    temporary = path.with_name(path.name + ".spry-new")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(body)
    os.chown(temporary, uid, uid)
    temporary.replace(path)


def copy_certificate(hostname):
    source = Path("/etc/letsencrypt/live") / hostname
    run(["openssl", "x509", "-in", str(source / "fullchain.pem"), "-noout", "-checkhost", hostname])
    run(["openssl", "x509", "-in", str(source / "fullchain.pem"), "-noout", "-checkend", "3600"])
    cert_public = run(["openssl", "x509", "-in", str(source / "fullchain.pem"), "-pubkey", "-noout"])
    key_public = run(["openssl", "pkey", "-in", str(source / "privkey.pem"), "-pubout"])
    if cert_public != key_public:
        raise ValueError("Certificate and private key differ")
    TLS.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chown(TLS, 1000, 1000)
    os.chmod(TLS, 0o700)
    for name in ("fullchain.pem", "privkey.pem"):
        private_write(TLS / name, (source / name).read_bytes(), 1000)


def restart(public=True):
    run(["systemctl", "restart", "archipelago"])
    # Archy's reconciler applies changed units itself. A second immediate
    # restart races that job; wait for both rendered and actual arguments.
    stable = 0
    for _ in range(60):
        unit = Path("/home/archipelago/.config/containers/systemd") / (APP + ".container")
        rendered = unit.exists() and (("--tls-listen" in unit.read_text()) == public)
        try:
            info = json.loads(run(["podman", "inspect", APP], user=True))[0]
            effective = info["State"]["Running"] and (("--tls-listen" in info["Config"]["Cmd"]) == public)
        except subprocess.CalledProcessError:
            effective = False
        stable = stable + 1 if rendered and effective else 0
        if stable >= 3:
            return
        time.sleep(1)
    raise ValueError("Archy did not converge rendered and running configuration")


def verify_runtime(ip):
    info = json.loads(run(["podman", "inspect", APP], user=True))[0]
    if (not info["State"]["Running"] or info["Image"].removeprefix("sha256:") != IMAGE_ID
            or info["HostConfig"]["LogConfig"]["Type"] != "none"
            or not info["HostConfig"]["ReadonlyRootfs"]):
        raise ValueError("Runtime differs from pinned isolation/logging settings")
    args = info["Config"]["Cmd"]
    if f"{ip}:5349" not in args or "--allow-loopback-peers" in args:
        raise ValueError("Public TURN arguments not effective")
    cgroup = next(x.split(":", 2)[2] for x in Path(f"/proc/{info['State']['Pid']}/cgroup").read_text().splitlines() if x.startswith("0::"))
    root = Path("/sys/fs/cgroup") / cgroup.lstrip("/")
    if (root / "memory.max").read_text().strip() != "134217728":
        raise ValueError("Kernel memory limit differs")
    quota, period = (root / "cpu.max").read_text().split()
    if quota != period:
        raise ValueError("Kernel CPU limit differs")
    return {"running": True, "image_id": IMAGE_ID, "memory_max": 134217728,
            "cpu_cores": 1, "log_driver": "none", "loopback_peers": False}


def activate(args):
    endpoint(args.hostname, args.ip)
    import socket
    if args.ip not in {item[4][0] for item in socket.getaddrinfo(args.hostname, None, socket.AF_INET)}:
        raise ValueError("Hostname does not resolve to the selected address")
    site = args.nginx_site
    original = site.read_bytes()
    if hashlib.sha256(original).hexdigest() != args.nginx_sha256 or site.is_symlink():
        raise ValueError("Nginx site differs from the inspected version")
    candidate_site = acme_site(original)
    originals = [p.read_bytes() for p in MANIFESTS]
    candidate = public_manifest(originals[0], args.ip)
    if originals[0] != originals[1] or HOOK.exists() or TLS.exists():
        raise ValueError("Expected unchanged lab manifests and no previous public TLS setup")
    firewall = run(["ufw", "status"]).decode()
    lines = [line for line in firewall.splitlines() if "ALLOW" in line]
    if "Status: active" not in firewall or not lines or any(not line.startswith("22/tcp") for line in lines):
        raise ValueError("Expected active, SSH-only UFW before qualification")
    info = json.loads(run(["podman", "inspect", APP], user=True))[0]
    if not info["State"]["Running"] or info["Image"].removeprefix("sha256:") != IMAGE_ID:
        raise ValueError("Pinned lab is not running")
    STATE.mkdir(mode=0o700)  # Refuse a second activation or overwritten backup.
    config = {"hostname": args.hostname, "ip": args.ip, "nginx_site": str(site),
              "rules_added": [], "status": "preparing"}
    private_write(STATE / "config.json", json.dumps(config).encode())
    for i, body in enumerate(originals):
        private_write(STATE / f"manifest-{i}.yml", body)
    private_write(STATE / "nginx-site", original)
    try:
        copy_certificate(args.hostname)
        for p in MANIFESTS:
            private_write(p, candidate, 1000)
        private_write(site, candidate_site)
        run(["nginx", "-t"])
        run(["systemctl", "reload", "nginx"])
        restart()
        runtime = verify_runtime(args.ip)
        hook = ("#!/bin/sh\nset -eu\nexec " + shlex.quote(str(Path(__file__).resolve())) + " renew\n").encode()
        private_write(HOOK, hook)
        os.chmod(HOOK, 0o700)
        for rule in RULES:
            # Record intent before mutation, so rollback can close a partially
            # applied rule even if a command response is interrupted.
            config["rules_added"].append(rule)
            private_write(STATE / "config.json", json.dumps(config).encode())
            run(["ufw", "allow", rule, "comment", "spry-invited-qualification"])
        config["status"] = "active"
        config["runtime"] = runtime
        config["manifest_sha256"] = hashlib.sha256(candidate).hexdigest()
        private_write(STATE / "config.json", json.dumps(config).encode())
        print(json.dumps({"status": "active", "runtime": runtime, "manifest_sha256": config["manifest_sha256"],
                          "dashboard_443_opened": False, "issuer": False, "discovery": False}))
    except BaseException as error:
        diagnostic = {"type": type(error).__name__}
        if isinstance(error, ValueError):
            diagnostic["reason"] = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            diagnostic.update(command=error.cmd, returncode=error.returncode,
                              stderr=error.stderr.decode(errors="replace")[-4096:])
        private_write(STATE / "activation-error.json", json.dumps(diagnostic).encode())
        rollback(config)
        raise


def rollback(config):
    for rule in reversed(config["rules_added"]):
        run(["ufw", "--force", "delete", "allow", rule])
    HOOK.unlink(missing_ok=True)
    for i, path in enumerate(MANIFESTS):
        private_write(path, (STATE / f"manifest-{i}.yml").read_bytes(), 1000)
    private_write(Path(config["nginx_site"]), (STATE / "nginx-site").read_bytes())
    run(["nginx", "-t"])
    run(["systemctl", "reload", "nginx"])
    restart(public=False)
    config["status"] = "rolled-back"
    private_write(STATE / "config.json", json.dumps(config).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    activate_parser = sub.add_parser("activate")
    activate_parser.add_argument("--hostname", required=True)
    activate_parser.add_argument("--ip", required=True)
    activate_parser.add_argument("--nginx-site", type=Path, required=True)
    activate_parser.add_argument("--nginx-sha256", required=True)
    sub.add_parser("renew")
    sub.add_parser("rollback")
    profile = sub.add_parser("profile")
    profile.add_argument("--output", type=Path, required=True)
    profile.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, "Run on the qualification node as root.\n")
    try:
        if args.action == "activate":
            activate(args)
        else:
            config = json.loads((STATE / "config.json").read_bytes())
            if args.action == "rollback":
                rollback(config)
            elif config["status"] != "active":
                raise ValueError("Public qualification is not active")
            elif args.action == "renew":
                lineage = os.environ.get("RENEWED_LINEAGE")
                if lineage and Path(lineage).name != config["hostname"]:
                    return
                copy_certificate(config["hostname"])
                run(["systemctl", "--user", "restart", APP + ".service"], user=True)
                verify_runtime(config["ip"])
                print("Certificate copied and Spry restarted; previous allocations are lost.")
            else:
                if not 60 <= args.ttl <= 86400:
                    raise ValueError("Credential TTL must be 60..86400 seconds")
                if args.output.exists() or args.output.is_symlink():
                    raise ValueError("Refusing to overwrite a credential profile")
                credential = json.loads(run(["podman", "exec", APP, "/usr/local/bin/spry-turn", "credential",
                                             "--ttl", str(args.ttl), "--label", os.urandom(12).hex()], user=True))
                credential["urls"] = [f"turn:{config['hostname']}:3478?transport=udp",
                                      f"turn:{config['hostname']}:3478?transport=tcp",
                                      f"turns:{config['hostname']}:5349?transport=tcp"]
                private_write(args.output, json.dumps(credential).encode())
                print("Private expiring profile written; no credential printed. Share privately with the intended recipient.")
    except Exception as error:
        parser.exit(1, f"Public candidate stopped ({type(error).__name__}); inspect private node state.\n")


if __name__ == "__main__":
    main()
