"""Bridge the bot's named skill calls to a trusted local Copilot checkout."""
from __future__ import annotations

import hashlib
import importlib
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from .config import COPILOT, DATA, RAG, SKILLS

_runtime = None
_initializing = threading.Lock()


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
        yield task
