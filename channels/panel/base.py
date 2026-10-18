"""What the panel's parts share: the error they show, how they compare times, file contents and paths, and how
they start a process that outlives the panel."""
from __future__ import annotations

import hashlib
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class ControlError(RuntimeError):
    """An actionable message that contains no transport credentials."""


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def same_path(left, right) -> bool:
    return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(str(Path(right).resolve()))


def detached(argv, env, stdout: Path, stderr: Path, cwd: Path):
    """Start a process with no window that outlives the panel, its output appended to the two logs."""
    stdout.parent.mkdir(parents=True, exist_ok=True)
    startup = subprocess.STARTUPINFO() if os.name == "nt" else None
    if startup:
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
             | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    with stdout.open("ab") as out, stderr.open("ab") as err:
        return subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                close_fds=True, startupinfo=startup, creationflags=flags)
