"""Process-owned resource locks, released by the OS after a crash."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone


class BusyError(RuntimeError):
    pass


class ResourceLock:
    def __init__(self, directory: Path, resource: str):
        self.path = directory / (hashlib.sha256(resource.encode()).hexdigest() + ".lock")
        self.resource = resource
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        self.file.seek(0, os.SEEK_END)
        if self.file.tell() == 0:
            self.file.write(b"\0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.seek(1)
            holder = self.file.read().decode("utf-8", errors="replace")
            self.file.close()
            self.file = None
            raise BusyError(f"Resource is in use: {self.resource}. Holder: {holder or 'unknown'}") from None
        self.file.seek(1)
        self.file.truncate()
        self.file.write(json.dumps({"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()}).encode())
        self.file.flush()
        return self

    def __exit__(self, *_):
        if self.file:
            self.file.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None
