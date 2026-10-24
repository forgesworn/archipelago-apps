#!/usr/bin/env python3
"""Interactive owner recovery over SSH. Never accepts a password in argv.

Backs up authentication files, replaces the dashboard password, clears the
password-encrypted old TOTP enrolment, and revokes old sessions/device tokens.
Does not touch node identities, wallets, applications or SSH authentication.
"""
import datetime
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import tempfile

AUTH_FILES = ("user.json", "sessions.json", "remember_secret", "device-tokens.json")
CONFIRM = "RESET LOGIN AND RE-ENROL 2FA"


def read_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 2_000_000:
            raise ValueError("Expected a bounded regular authentication file")
        return stream.read(), info


def validate_password(value):
    if (len(value.encode()) < 12 or not re.search(r"[A-Z]", value)
            or not re.search(r"[a-z]", value) or not re.search(r"[0-9]", value)
            or not re.search(r"[^A-Za-z0-9]", value)):
        raise ValueError("Use at least 12 characters with uppercase, lowercase, a digit and a special character")


def new_auth_documents(current, encoded_hash, remember_secret):
    # Preserve roles, onboarding state, unknown fields and all unrelated state.
    user = json.loads(current)
    if not isinstance(user, dict) or not user.get("setup_complete") or not user.get("password_hash"):
        raise ValueError("This is not an existing configured dashboard account")
    if not encoded_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$") or len(remember_secret) != 32:
        raise ValueError("Expected the reviewed Argon2id parameters and a fresh remember secret")
    user["password_hash"] = encoded_hash
    user["totp"] = None
    return {"user.json": (json.dumps(user, indent=2) + "\n").encode(),
            "sessions.json": b"[]\n", "remember_secret": remember_secret,
            "device-tokens.json": b"[]\n"}


def atomic_write(path, body, uid, gid):
    fd, temporary = tempfile.mkstemp(prefix=".dashboard-recovery-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            os.fchown(stream.fileno(), uid, gid)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def rewrite_auth(data_dir, backup_dir, expected_user_sha, encoded_hash):
    # Caller stops the backend first to prevent concurrent authentication writes.
    current, user_info = read_regular(data_dir / "user.json")
    if hashlib.sha256(current).hexdigest() != expected_user_sha:
        raise ValueError("Authentication changed since review; nothing was reset")
    documents = new_auth_documents(current, encoded_hash, secrets.token_bytes(32))
    original = {}
    for name in AUTH_FILES:
        path = data_dir / name
        if path.exists() or path.is_symlink():
            original[name] = read_regular(path)
        else:
            original[name] = None
    backup_dir.mkdir(mode=0o700)  # Never overwrite another recovery snapshot.
    for name, record in original.items():
        if record is not None:
            body, _ = record
            fd = os.open(backup_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
    receipt = {"files": {name: None if record is None else
               {"uid": record[1].st_uid, "gid": record[1].st_gid,
                "sha256": hashlib.sha256(record[0]).hexdigest()} for name, record in original.items()},
               "identity_files_modified": False, "ssh_authentication_modified": False}
    (backup_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (backup_dir / "receipt.json").chmod(0o600)
    for directory in (backup_dir, backup_dir.parent):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    try:
        for name, body in documents.items():
            atomic_write(data_dir / name, body, user_info.st_uid, user_info.st_gid)
        fd = os.open(data_dir, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except Exception:
        for name, record in original.items():
            if record is None:
                (data_dir / name).unlink(missing_ok=True)
            else:
                atomic_write(data_dir / name, record[0], record[1].st_uid, record[1].st_gid)
        raise


def main():
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise ValueError("Run this interactively as root with ssh -t")
    from argon2 import PasswordHasher
    from argon2.low_level import Type
    data_dir = Path("/var/lib/archipelago")
    current, _ = read_regular(data_dir / "user.json")
    user = json.loads(current)
    print("This resets the dashboard login, signs out browsers and revokes paired-device tokens.")
    if user.get("totp") is not None:
        print("Your existing 2FA entry cannot be re-encrypted without the old password. Enrol 2FA again after login.")
    if (data_dir / "identity/master_seed.enc").exists():
        print("The encrypted recovery-phrase backup is preserved and still needs its ORIGINAL passphrase.")
    print("Node keys, wallets, installed apps, firewall and SSH authentication are preserved.")
    password = getpass.getpass("New dashboard password: ")
    validate_password(password)
    if password != getpass.getpass("Confirm new dashboard password: "):
        raise ValueError("Passwords differ; nothing changed")
    hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4,
                            hash_len=32, salt_len=16, type=Type.ID)
    encoded = hasher.hash(password)
    assert hasher.verify(encoded, password)
    del password
    if input("Type '" + CONFIRM + "' to apply: ") != CONFIRM:
        print("Cancelled; nothing changed.")
        return
    backup = Path("/root") / ("archy-login-backup-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    subprocess.run(["systemctl", "stop", "archipelago"], check=True, capture_output=True)
    try:
        rewrite_auth(data_dir, backup, hashlib.sha256(current).hexdigest(), encoded)
    finally:
        subprocess.run(["systemctl", "start", "archipelago"], check=True, capture_output=True)
    print("Dashboard login reset. Authentication backup: " + str(backup))
    print("Log in through your SSH tunnel, save the new password, then re-enrol 2FA and save its backup codes.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error))
    except Exception as error:
        raise SystemExit("Recovery stopped (" + type(error).__name__ + "); no password or key material printed.")
