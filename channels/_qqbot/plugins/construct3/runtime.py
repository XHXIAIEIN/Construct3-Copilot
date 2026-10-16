"""Bridge the bot's named skill calls to a trusted local Copilot checkout."""
from __future__ import annotations

import importlib
import os
import sys
import threading
from pathlib import Path


_runtime = None
_initializing = threading.Lock()


def get_runtime(*, home, data_dir, settings):
    """Load Copilot only from the configured checkout."""
    global _runtime
    with _initializing:
        if _runtime is None:
            checkout = Path(settings.get("C3BOT_COPILOT") or home.parent / "Construct3-Copilot").resolve()
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
            _runtime = module.Runtime(skills_root=Path(settings.get("C3BOT_SKILLS") or settings.get("CONSTRUCT3_AGENT_SKILLS") or home.parent / "Construct3-Agent-Skills"), data_dir=data_dir / "copilot", python_executable=sys.executable)
        return _runtime
