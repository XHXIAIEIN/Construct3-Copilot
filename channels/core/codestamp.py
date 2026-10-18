"""Which code a channel process runs: one hash over the Python files under channels/ and copilot/. The channel puts
it in its receipt when it starts, and the panel compares it with the files now on disk to tell a process that
still runs the code from before a change. The panel's own files and channels/var are left out: the channel process
does not run them."""
from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOTS = ("channels", "copilot")
SKIP = ("channels/var", "channels/panel")


def python_files(repo: Path = REPO) -> list[Path]:
    found = []
    for root in ROOTS:
        for path in (repo / root).rglob("*.py"):
            relative = path.relative_to(repo).as_posix()
            if "__pycache__" in path.parts or any(relative == s or relative.startswith(s + "/") for s in SKIP):
                continue
            found.append(path)
    return sorted(found, key=lambda p: p.relative_to(repo).as_posix())


class CodeStamp:
    """Hashes each file once per change of its size and modification time, so the panel can ask on every refresh."""

    def __init__(self, repo: Path = REPO) -> None:
        self.repo = repo
        self._files: dict[Path, tuple[int, int, str]] = {}

    def stamp(self) -> str:
        total = hashlib.sha1()
        for path in python_files(self.repo):
            try:
                info = path.stat()
                known = self._files.get(path)
                if known is None or known[:2] != (info.st_mtime_ns, info.st_size):
                    known = (info.st_mtime_ns, info.st_size, hashlib.sha1(path.read_bytes()).hexdigest())
                    self._files[path] = known
            except OSError:
                continue  # removed while listing
            total.update(f"{path.relative_to(self.repo).as_posix()}\0{known[2]}\n".encode())
        return total.hexdigest()[:16]

    def changed_after(self, seconds: float) -> list[str]:
        """The files modified after a time (epoch seconds), newest first: which change a restart would pick up."""
        newer = []
        for path in python_files(self.repo):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > seconds:
                newer.append((mtime, path.relative_to(self.repo).as_posix()))
        return [name for _, name in sorted(newer, reverse=True)]
