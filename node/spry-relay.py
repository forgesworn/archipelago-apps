#!/usr/bin/env python3
"""Install an unlisted standalone Spry STUN/TURN relay on a dedicated VPS."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import stat
import subprocess

APP = "spry-relay"
ACCOUNT = "spry-relay"
IMAGE = "ghcr.io/forgesworn/spry@sha256:15dd7a0aa83c2d9ed9a439af264e79062cecaf1cab5902910a914d4526e30ee8"
ETC = Path("/etc/spry-relay")
HOME = Path("/var/lib/spry-relay")
STATE = ETC / "state.json"
SECRET = ETC / "turn.secret"
UNIT = HOME / ".config/containers/systemd/spry-relay.container"
TLS = HOME / "tls"
HOOK = Path("/etc/letsencrypt/renewal-hooks/deploy/spry-relay")
RULES = ("80/tcp", "3478/udp", "3478/tcp", "5349/tcp", "49160:49191/udp")
ARCHY_MARKERS = (
    Path("/var/lib/archipelago"), Path("/opt/archipelago"),
    Path("/etc/systemd/system/archipelago.service"),
)
PACKAGES = (
    "ca-certificates", "certbot", "curl", "dbus-user-session", "fuse-overlayfs", "iproute2", "kmod",
    "libpam-systemd", "openssl", "podman", "python3", "runc", "uidmap", "ufw",
)
SHELL_COMMAND = 'export SPRY_TURN_SECRET="$(cat /run/spry-relay/turn.secret)"; exec /usr/local/bin/spry-turn "$@"'


class Refused(ValueError):
    pass


def run(args, user=False, timeout=300):
    if user:
        account = pwd.getpwnam(ACCOUNT)
        args = [
            "runuser", "-u", ACCOUNT, "--", "env",
            f"HOME={HOME}", f"XDG_RUNTIME_DIR=/run/user/{account.pw_uid}",
            f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{account.pw_uid}/bus",
            *args,
        ]
    return subprocess.check_output(args, cwd="/var/tmp", stderr=subprocess.PIPE, timeout=timeout)


def private_write(path, body, uid=None, gid=None, mode=0o600, replace=True):
    if path.is_symlink():
        raise Refused(f"Refusing symbolic-link destination: {path}")
    uid = os.geteuid() if uid is None else uid
    gid = os.getegid() if gid is None else gid
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if not replace else 0)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    fd = os.open(temporary, flags, mode)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            os.fchown(stream.fileno(), uid, gid)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
            temporary.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()


def endpoint(hostname, ip):
    if (not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", hostname)
            or "." not in hostname or len(hostname) > 253
            or hostname.split(".")[-1] == "local"):
        raise Refused("Use a public DNS hostname with at least two labels")
    address = ipaddress.ip_address(ip)
    if address.version != 4 or not address.is_global:
        raise Refused("Use the VPS's concrete public IPv4 address")


def load_state():
    try:
        value = json.loads(STATE.read_text())
    except FileNotFoundError:
        return None
    if value.get("schema") != 1 or value.get("app") != APP:
        raise Refused("Existing relay state has an unsupported schema")
    endpoint(value["hostname"], value["ip"])
    if value.get("status") not in ("preparing", "active", "rolled-back", "rollback-error"):
        raise Refused("Existing relay state has an invalid status")
    if not isinstance(value.get("rules_added"), list):
        raise Refused("Existing relay state has invalid firewall records")
    return value


def save_state(config):
    private_write(STATE, (json.dumps(config, indent=2, sort_keys=True) + "\n").encode())


def refuse_existing_archy():
    if any(path.exists() or path.is_symlink() for path in ARCHY_MARKERS):
        raise Refused("Use a dedicated VPS without an existing Archipelago installation")


def ensure_account():
    try:
        account = pwd.getpwnam(ACCOUNT)
    except KeyError:
        run(["useradd", "--system", "--home", str(HOME), "--shell", "/usr/sbin/nologin", "--user-group", ACCOUNT])
        account = pwd.getpwnam(ACCOUNT)
    for name, option in (("/etc/subuid", "--add-subuids"), ("/etc/subgid", "--add-subgids")):
        entries = Path(name).read_text().splitlines()
        if not any(line.startswith(f"{ACCOUNT}:") for line in entries):
            run(["usermod", option, "100000-165535", ACCOUNT])
    ETC.mkdir(mode=0o700, exist_ok=True)
    HOME.mkdir(mode=0o700, exist_ok=True)
    for directory in (ETC, HOME):
        os.chown(directory, account.pw_uid, account.pw_gid)
        os.chmod(directory, 0o700)
    run(["loginctl", "enable-linger", ACCOUNT])
    run(["systemctl", "start", f"user@{account.pw_uid}.service"])
    if not SECRET.exists():
        private_write(SECRET, (secrets.token_hex(32) + "\n").encode(), account.pw_uid, account.pw_gid)
    info = SECRET.stat()
    if info.st_uid != account.pw_uid or stat.S_IMODE(info.st_mode) != 0o600:
        raise Refused("Existing transport secret has incorrect ownership or mode")
    return account


def install_packages():
    run(["apt-get", "update"], timeout=600)
    run(["apt-get", "install", "-y", "--no-install-recommends", *PACKAGES], timeout=600)


def firewall_preflight(config):
    status = run(["ufw", "status"]).decode()
    if "Status: active" not in status:
        raise Refused("Enable UFW with SSH allowed before installing the relay")
    if config is None:
        rules = [line for line in status.splitlines() if "ALLOW" in line]
        if not rules or any(not line.startswith("22/tcp") for line in rules):
            raise Refused("A fresh relay requires an SSH-only UFW baseline; no rules are reset")


def add_rules(config):
    for rule in RULES:
        config["rules_added"].append(rule)
        save_state(config)
        run(["ufw", "allow", rule, "comment", APP])


def copy_certificate(config, account):
    hostname = config["hostname"]
    source = Path("/etc/letsencrypt/live") / hostname
    run(["openssl", "x509", "-in", str(source / "fullchain.pem"), "-noout", "-checkhost", hostname])
    run(["openssl", "x509", "-in", str(source / "fullchain.pem"), "-noout", "-checkend", "3600"])
    cert_public = run(["openssl", "x509", "-in", str(source / "fullchain.pem"), "-pubkey", "-noout"])
    key_public = run(["openssl", "pkey", "-in", str(source / "privkey.pem"), "-pubout"])
    if cert_public != key_public:
        raise Refused("Certificate and private key do not match")
    TLS.mkdir(mode=0o700, exist_ok=True)
    os.chown(TLS, account.pw_uid, account.pw_gid)
    os.chmod(TLS, 0o700)
    for name in ("fullchain.pem", "privkey.pem"):
        private_write(TLS / name, (source / name).read_bytes(), account.pw_uid, account.pw_gid)


def issue_certificate(config):
    lineage = Path("/etc/letsencrypt/live") / config["hostname"]
    if lineage.is_dir():
        return
    run([
        "certbot", "certonly", "--standalone", "--non-interactive", "--agree-tos",
        "--no-eff-email", "--preferred-challenges", "http", "-d", config["hostname"],
    ], timeout=600)


def relay_args(config):
    ip = config["ip"]
    return [
        "serve", "--listen", f"{ip}:3478", "--relay-ip", ip,
        "--relay-ports", "49160:49191", "--max-allocations", "32",
        "--max-per-user", "8", "--max-connections", "32",
        "--bytes-per-second", "1000000", "--tls-listen", f"{ip}:5349",
        "--tls-cert", "/tls/fullchain.pem", "--tls-key", "/tls/privkey.pem",
    ]


def cgroups_disabled_for_test():
    return os.environ.get("SPRY_RELAY_TEST_NO_CGROUP") == "1"


def render_unit(config):
    resource_args = ("PodmanArgs=--cgroups=disabled --runtime=crun --storage-driver=vfs" if cgroups_disabled_for_test()
                     else "PodmanArgs=--cpus=1 --memory=128m --pids-limit=128")
    return f"""[Unit]
Description=Standalone Spry STUN/TURN relay

[Quadlet]
DefaultDependencies=false

[Container]
ContainerName={APP}
Image={IMAGE}
Pull=never
Network=host
Entrypoint=/bin/sh
Exec=-c '{SHELL_COMMAND}' spry-relay {' '.join(relay_args(config))}
Volume=/etc/spry-relay/turn.secret:/run/spry-relay/turn.secret:ro
Volume=/var/lib/spry-relay/tls:/tls:ro
ReadOnly=true
NoNewPrivileges=true
DropCapability=ALL
LogDriver=none
{resource_args}

[Service]
Restart=always
RestartSec=10
TimeoutStartSec=120
TimeoutStopSec=30
LimitCORE=0
StandardOutput=null
StandardError=null

[Install]
WantedBy=default.target
"""


def install_unit(config, account):
    UNIT.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chown(UNIT.parent, account.pw_uid, account.pw_gid)
    private_write(UNIT, render_unit(config).encode(), account.pw_uid, account.pw_gid, mode=0o644)


def pull_image():
    storage = ["--storage-driver=vfs"] if cgroups_disabled_for_test() else []
    run(["podman", *storage, "pull", IMAGE], user=True, timeout=600)
    image = json.loads(run(["podman", "image", "inspect", IMAGE], user=True))[0]
    reference = "ghcr.io/forgesworn/spry@" + IMAGE.split("@", 1)[1]
    if reference not in image.get("RepoDigests", []):
        raise Refused("Pulled image does not retain the required immutable digest")
    expected = {"x86_64": "amd64", "aarch64": "arm64"}.get(os.uname().machine)
    if image.get("Architecture") != expected:
        raise Refused("Pulled image architecture differs from this VPS")
    return image["Id"].removeprefix("sha256:")


def restart(account):
    run(["systemctl", "--user", "daemon-reload"], user=True)
    run(["systemctl", "--user", "restart", APP + ".service"], user=True)


def verify_runtime(config):
    info = json.loads(run(["podman", "inspect", APP], user=True))[0]
    host = info["HostConfig"]
    checks = [
        (info["State"]["Running"], "Relay is not running"),
        (host.get("ReadonlyRootfs") is True, "Relay root filesystem is not read-only"),
        (host.get("NetworkMode") == "host", "Relay is not using the reviewed host network"),
        (host.get("LogConfig", {}).get("Type") == "none", "Relay application logging is not disabled"),
        ("no-new-privileges" in (host.get("SecurityOpt") or []), "Relay no-new-privileges is not enabled"),
        (cgroups_disabled_for_test() or host.get("Memory") == 134217728,
         "Relay memory limit differs from 128 MiB"),
        (cgroups_disabled_for_test() or host.get("NanoCpus") == 1000000000,
         "Relay CPU limit differs from one CPU"),
        (cgroups_disabled_for_test() or host.get("PidsLimit") == 128,
         "Relay PID limit differs from 128"),
    ]
    for passed, message in checks:
        if not passed:
            raise Refused(message)
    args = info["Config"].get("Cmd", [])
    expected = ["-c", SHELL_COMMAND, APP, *relay_args(config)]
    if info["Config"].get("Entrypoint") != ["/bin/sh"] or args != expected or "--allow-loopback-peers" in args:
        raise Refused("Running relay arguments differ from the reviewed public transport contract")
    if SECRET.read_text().strip() in json.dumps(info):
        raise Refused("Transport secret appeared in container inspection")
    process = run(["podman", "exec", APP, "/bin/sh", "-c", "cat /proc/self/status"], user=True).decode()
    for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        value = re.search(rf"^{name}:\s*([0-9a-fA-F]+)$", process, re.MULTILINE)
        if value is None or int(value.group(1), 16) != 0:
            raise Refused(f"Relay process capability set {name} is not empty")
    if not re.search(r"^NoNewPrivs:\s*1$", process, re.MULTILINE):
        raise Refused("Relay process does not enforce no-new-privileges")
    return {
        "running": True, "image": IMAGE, "readonly_root": True,
        "capabilities_zero": True,
        "log_driver": "none", "network": "host", "memory_bytes": 134217728,
        "cpu_cores": 1, "secret_absent_from_inspect": True,
        "udp_relay_ports": "49160-49191", "public_credential_endpoint": False,
        "cgroup_limits": "disabled-test-fixture" if cgroups_disabled_for_test() else "enforced",
        "discovery": False,
    }


def deactivate():
    config = load_state()
    if config is None:
        raise Refused("No relay activation state exists")
    errors = []
    try:
        run(["systemctl", "--user", "stop", APP + ".service"], user=True)
    except Exception as error:
        errors.append(type(error).__name__)
    HOOK.unlink(missing_ok=True)
    for rule in reversed(config["rules_added"]):
        try:
            run(["ufw", "--force", "delete", "allow", rule])
        except Exception as error:
            errors.append(type(error).__name__)
    config["status"] = "rollback-error" if errors else "rolled-back"
    config["recovery_errors"] = errors
    save_state(config)
    if errors:
        raise Refused("Relay stopped, but some recovery steps need inspection")


def activate(args):
    endpoint(args.hostname, args.ip)
    config = load_state()
    if config is not None and (config["hostname"], config["ip"]) != (args.hostname, args.ip):
        raise Refused("Existing relay state belongs to another endpoint")
    if config is None:
        refuse_existing_archy()
    if config is not None and config["status"] == "active":
        print(json.dumps(verify_runtime(config), sort_keys=True))
        return
    import socket
    addresses = {item[4][0] for item in socket.getaddrinfo(args.hostname, None, socket.AF_INET)}
    if args.ip not in addresses:
        raise Refused("Hostname does not resolve to the selected public IPv4 address")
    firewall_preflight(config)
    install_packages()
    account = ensure_account()
    if config is None:
        config = {"schema": 1, "app": APP, "hostname": args.hostname, "ip": args.ip,
                  "status": "preparing", "rules_added": []}
        save_state(config)
    try:
        config["rules_added"] = []
        save_state(config)
        add_rules(config)
        issue_certificate(config)
        copy_certificate(config, account)
        image_id = pull_image()
        install_unit(config, account)
        restart(account)
        config["runtime"] = verify_runtime(config)
        config["image_id"] = image_id
        config["status"] = "active"
        save_state(config)
        HOOK.parent.mkdir(parents=True, exist_ok=True)
        private_write(HOOK, ("#!/bin/sh\nset -eu\nexec /usr/local/sbin/spry-relay renew\n").encode(), mode=0o700)
        print(json.dumps(config["runtime"], sort_keys=True))
    except BaseException:
        try:
            deactivate()
        except Exception:
            pass
        raise


def renew():
    config = load_state()
    if config is None or config["status"] != "active":
        raise Refused("Certificate renewal requires an active relay")
    selected = os.environ.get("RENEWED_LINEAGE")
    if selected and Path(selected).name != config["hostname"]:
        return
    account = pwd.getpwnam(ACCOUNT)
    copy_certificate(config, account)
    restart(account)
    config["runtime"] = verify_runtime(config)
    save_state(config)
    print("Certificate copied and relay restarted; previous allocations were closed.")


def profile(args):
    config = load_state()
    if config is None or config["status"] != "active":
        raise Refused("Credential profiles require an active relay")
    if not 60 <= args.ttl <= 86400:
        raise Refused("Credential TTL must be 60..86400 seconds")
    if args.output.exists() or args.output.is_symlink():
        raise Refused("Refusing to overwrite a credential profile")
    credential = json.loads(run([
        "podman", "exec", APP, "/bin/sh", "-c", SHELL_COMMAND, "spry-relay", "credential",
        "--ttl", str(args.ttl), "--label", secrets.token_hex(12),
    ], user=True))
    credential["urls"] = [
        f"turn:{config['hostname']}:3478?transport=udp",
        f"turn:{config['hostname']}:3478?transport=tcp",
        f"turns:{config['hostname']}:5349?transport=tcp",
    ]
    private_write(args.output, (json.dumps(credential, indent=2) + "\n").encode(), replace=False)
    print("Private expiring profile written; no credential was printed. Share it privately with one device.")


def status():
    config = load_state()
    if config is None:
        raise Refused("No relay activation state exists")
    result = {"status": config["status"], "hostname": config["hostname"], "ip": config["ip"]}
    if config["status"] == "active":
        result["runtime"] = verify_runtime(config)
    print(json.dumps(result, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    activation = sub.add_parser("activate")
    activation.add_argument("--hostname", required=True)
    activation.add_argument("--ip", required=True)
    sub.add_parser("deactivate")
    sub.add_parser("renew")
    sub.add_parser("status")
    credential = sub.add_parser("profile")
    credential.add_argument("--output", type=Path, required=True)
    credential.add_argument("--ttl", type=int, default=3600)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.exit(1, "Run the relay installer as root on the dedicated VPS.\n")
    try:
        if args.action == "activate":
            activate(args)
        elif args.action == "deactivate":
            deactivate()
        elif args.action == "renew":
            renew()
        elif args.action == "profile":
            profile(args)
        else:
            status()
    except Refused as error:
        parser.exit(1, str(error) + "\n")
    except subprocess.CalledProcessError as error:
        detail = error.stderr.decode(errors="replace")[-2000:]
        parser.exit(1, f"Command failed: {error.cmd}\n{detail}\n")
    except Exception as error:
        parser.exit(1, f"Relay operation stopped ({type(error).__name__}); inspect private VPS state.\n")


if __name__ == "__main__":
    main()
