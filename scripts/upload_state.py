#!/usr/bin/env python3
"""Batch uploader for AutoTeam state files."""

import os
import sys

from paramiko.client import AutoAddPolicy, SSHClient

HOST = os.environ["SSH_HOST"]
PORT = int(os.environ.get("SSH_PORT", "22"))
USER = os.environ["SSH_USER"]
PASSWORD = os.environ["SSH_PASSWORD"]
REMOTE_DIR = os.environ.get("REMOTE_DIR", "/root/AutoTeam-local-fork")

FILES = [
    (".env", ".env", 0o600),
    ("accounts.json", "accounts.json", 0o600),
    ("state.json", "state.json", 0o600),
]
AUTH_DIR = "auths"


def main() -> int:
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(
        HOST, port=PORT, username=USER, password=PASSWORD, timeout=20, allow_agent=False, look_for_keys=False
    )
    try:
        sftp = client.open_sftp()
        # ensure remote auths dir exists
        try:
            sftp.stat(f"{REMOTE_DIR}/{AUTH_DIR}")
        except FileNotFoundError:
            sftp.mkdir(f"{REMOTE_DIR}/{AUTH_DIR}")
            print(f"[mkdir] {REMOTE_DIR}/{AUTH_DIR}")

        for local_rel, remote_rel, mode in FILES:
            if not os.path.exists(local_rel):
                print(f"[skip] {local_rel} (missing)")
                continue
            remote_path = f"{REMOTE_DIR}/{remote_rel}"
            sftp.put(local_rel, remote_path)
            sftp.chmod(remote_path, mode)
            print(f"[put] {local_rel} -> {remote_path}")

        # upload auths/*
        for name in sorted(os.listdir(AUTH_DIR)):
            local = os.path.join(AUTH_DIR, name)
            if not os.path.isfile(local):
                continue
            remote = f"{REMOTE_DIR}/{AUTH_DIR}/{name}"
            sftp.put(local, remote)
            sftp.chmod(remote, 0o600)
            print(f"[put] {local} -> {remote}")

        # also tighten auths dir
        sftp.chmod(f"{REMOTE_DIR}/{AUTH_DIR}", 0o700)
        sftp.close()
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
