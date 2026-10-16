"""Bridge the bot's named skill calls to a trusted local Copilot checkout."""
from __future__ import annotations

import hashlib
import importlib
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .config import COPILOT, DATA, RAG, SKILLS

_runtime = None
_initializing = threading.Lock()
_active: ContextVar[tuple | None] = ContextVar("copilot_session", default=None)


def temporary_directory():
    """Keep short-lived build inputs under the bot's data directory."""
    root = DATA / "scratch"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


def get_runtime():
    """Load Copilot only from the configured checkout."""
    global _runtime
    with _initializing:
        if _runtime is None:
            checkout = COPILOT.resolve()
            package = checkout / "copilot" / "__init__.py"
            if not package.is_file():
                raise ImportError(f"Copilot package missing at {package}; set C3BOT_COPILOT to its checkout")
            loaded = sys.modules.get("copilot")
            if loaded is not None and Path(loaded.__file__).resolve() != package:
                raise ImportError("a different copilot package is loaded; restart with the configured C3BOT_COPILOT")
            sys.path.insert(0, str(checkout))
            try:
                module = importlib.import_module("copilot")
            finally:
                sys.path.remove(str(checkout))
            if Path(module.__file__).resolve() != package:
                raise ImportError(f"Copilot resolved outside {checkout}")
            _runtime = module.Runtime(skills_root=SKILLS, data_dir=DATA / "copilot", python_executable=sys.executable)
        return _runtime


@contextmanager
def session(project: Path | None, folder: Path | None, group: bool = False):
    """Hold a runtime session for one answer and its skill calls."""
    identity = str((folder or project).resolve()) if folder or project else "cli"
    session_id = hashlib.sha256(identity.encode()).hexdigest()
    with get_runtime().session(source="qqbot", session_id=session_id, project=project,
                               metadata={"group": group}) as task:
        token = _active.set((task, session_id))
        try:
            yield task
        finally:
            _active.reset(token)


def child_environment() -> dict[str, str]:
    """Pass the current task to the bot's fixed spec builder."""
    runtime = get_runtime()
    env = os.environ.copy()
    env.update(C3BOT_COPILOT=str(COPILOT.resolve()), C3BOT_SKILLS=str(runtime.skills_root),
               C3BOT_DATA=str(DATA.resolve()), CONSTRUCT3_RAG=str(RAG.resolve()))
    active = _active.get()
    if active:
        env.update(C3BOT_COPILOT_PARENT=active[0].task_id, C3BOT_COPILOT_SESSION=active[1])
    return env


def run_script(name: str, args: list[str], project: Path | None = None, *, locale: str | None = None,
               limit: int | None = None, timeout: int = 90, rag: Path | None = RAG) -> subprocess.CompletedProcess:
    """Return real skill exit codes and make supervision failures visible."""
    runtime = get_runtime()
    args = list(args)
    if rag is not None and "--rag" not in args:
        args += ["--rag", str(runtime.skills_root if name == "search_guides" else rag)]
    context = {}
    if _active.get() is None and os.environ.get("C3BOT_COPILOT_PARENT"):
        context = {"parent_id": os.environ["C3BOT_COPILOT_PARENT"],
                   "session_id": os.environ.get("C3BOT_COPILOT_SESSION", "cli")}
    result = runtime.run_script(name, args, project=project, locale=locale, limit=limit, timeout=timeout,
                                source="qqbot", **context)
    code = result.get("exit_code")
    if code is None:
        code = 124 if result["status"] == "timed_out" else 75 if result["status"] == "busy" else 1
    stdout, stderr = result.get("stdout") or "", result.get("stderr") or ""
    if result["status"] != "completed":
        stdout = f"copilot {result['status']}: {result.get('reason') or 'skill execution failed'}\n{stdout}"
        if code == 0:
            code = 1
    return subprocess.CompletedProcess([name, *args], code, stdout, stderr)
