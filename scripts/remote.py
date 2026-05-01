#!/usr/bin/env python3
"""Ad-hoc SSH/SCP helper for AutoTeam deployment (paramiko-based).

Usage:
  uv run --with paramiko python scripts/remote.py run '<shell cmd>'
  uv run --with paramiko python scripts/remote.py put <local> <remote>
  uv run --with paramiko python scripts/remote.py get <remote> <local>

Credentials read from env: SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD.
"""

import os
import sys

from paramiko.client import AutoAddPolicy, SSHClient

HOST = os.environ["SSH_HOST"]
PORT = int(os.environ.get("SSH_PORT", "22"))
USER = os.environ["SSH_USER"]
PASSWORD = os.environ["SSH_PASSWORD"]


def _connect() -> SSHClient:
    client = SSHClient()
    client.set_missing_host_key_policy(AutoAddPolicy())
    client.connect(
        HOST,
        port=PORT,
        username=USER,
        password=PASSWORD,
        timeout=20,
        allow_agent=False,
        look_for_keys=False,
    )
    return client


def run(cmd: str) -> int:
    client = _connect()
    try:
        _, stdout, stderr = client.exec_command(cmd, get_pty=False, timeout=None)
        # stream output line by line; reconfigure stdout to utf-8 if possible so
        # non-ascii shell output from Linux doesn't trip Windows' default cp/gbk.
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        out_buf = sys.stdout.buffer if hasattr(sys.stdout, "buffer") else None
        for chunk in iter(lambda: stdout.channel.recv(4096), b""):
            if out_buf is not None:
                out_buf.write(chunk)
                out_buf.flush()
            else:
                sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                sys.stdout.flush()
        err = stderr.read()
        if err:
            try:
                sys.stderr.buffer.write(err)
            except Exception:
                sys.stderr.write(err.decode("utf-8", errors="replace"))
        return stdout.channel.recv_exit_status()
    finally:
        client.close()


def put(local: str, remote: str) -> int:
    client = _connect()
    try:
        sftp = client.open_sftp()
        sftp.put(local, remote)
        sftp.close()
        print(f"[put] {local} -> {remote}")
        return 0
    finally:
        client.close()


def get(remote: str, local: str) -> int:
    client = _connect()
    try:
        sftp = client.open_sftp()
        sftp.get(remote, local)
        sftp.close()
        print(f"[get] {remote} -> {local}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    action = sys.argv[1]
    if action == "run":
        sys.exit(run(" ".join(sys.argv[2:])))
    elif action == "put":
        sys.exit(put(sys.argv[2], sys.argv[3]))
    elif action == "get":
        sys.exit(get(sys.argv[2], sys.argv[3]))
    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(2)
