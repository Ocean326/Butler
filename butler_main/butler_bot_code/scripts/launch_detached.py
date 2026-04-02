from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


def _windows_creation_flags() -> int:
    flags = 0
    for name in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_BREAKAWAY_FROM_JOB", "CREATE_NO_WINDOW"):
        flags |= int(getattr(subprocess, name, 0))
    return flags


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--stdout", required=True)
    parser.add_argument("--stderr", required=True)
    parser.add_argument("--pid-file", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = list(args.command or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("missing command")

    cwd = Path(args.cwd).resolve()
    stdout_path = Path(args.stdout).resolve()
    stderr_path = Path(args.stderr).resolve()
    pid_file = Path(args.pid_file).resolve()

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["HTTP_PROXY"] = ""
    env["HTTPS_PROXY"] = ""
    env["ALL_PROXY"] = ""
    env["GIT_HTTP_PROXY"] = ""
    env["GIT_HTTPS_PROXY"] = ""
    env["NO_PROXY"] = "localhost,127.0.0.1,::1"
    env.pop("CODEX_SANDBOX_NETWORK_DISABLED", None)
    env.pop("CODEX_THREAD_ID", None)

    creationflags = _windows_creation_flags()
    with stdout_path.open("a", encoding="utf-8") as stdout_handle, stderr_path.open("a", encoding="utf-8") as stderr_handle:
        proc = subprocess.Popen(
            command,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=creationflags,
            close_fds=True,
        )
    pid_file.write_text(str(int(proc.pid)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
