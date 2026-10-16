"""Paths of the Construct 3 tools, their data and the official examples."""
from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent
AGENT_SKILLS = Path(os.environ.get("CONSTRUCT3_AGENT_SKILLS") or HOME.parent / "Construct3-Agent-Skills")
PLUGIN_ROOT = AGENT_SKILLS / "plugin" if (AGENT_SKILLS / "plugin").is_dir() else AGENT_SKILLS
SKILL_ROOT = PLUGIN_ROOT / "skills" / "construct3-agent-plugin"
SCRIPTS = SKILL_ROOT / "scripts"
# CONSTRUCT3_RAG selects source data independently of the tools.
RAG = Path(os.environ.get("CONSTRUCT3_RAG") or PLUGIN_ROOT)


@lru_cache(maxsize=1)
def shared():
    """The tool owner's path and bundled-data helpers."""
    path = SCRIPTS / "c3project.py"
    if not path.is_file():
        raise FileNotFoundError(f"Construct 3 tools not found at {path}; set CONSTRUCT3_AGENT_SKILLS to the clone or plugin folder")
    spec = importlib.util.spec_from_file_location("qqbot_c3project", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def examples_root() -> Path:
    """The caller's explicit clone, or the clone beside the tools repository."""
    override = os.environ.get("C3_EXAMPLES")
    return Path(override) if override else shared().siblings_folder(PLUGIN_ROOT) / "Construct-Example-Projects"
