"""Sibling repo discovery for Construct3-Copilot plugin scripts.

Lookup order for each repo:
1. Environment variable ($C3_RAG_ROOT, $C3_CLIPBOARD_ROOT)
2. Sibling directory convention ({copilot_repo}/../{SiblingName}/)
3. Exit 1 with JSON error and clone suggestion
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Known sibling repos
# ---------------------------------------------------------------------------
_SIBLINGS: dict[str, dict] = {
    "Construct3-RAG": {
        "env": "C3_RAG_ROOT",
        "url": "https://github.com/<org>/Construct3-RAG.git",
    },
    "Construct3-Clipboard": {
        "env": "C3_CLIPBOARD_ROOT",
        "url": "https://github.com/<org>/Construct3-Clipboard.git",
    },
    "Construct3-Manual": {
        "env": "C3_MANUAL_ROOT",
        "url": "https://github.com/<org>/Construct3-Manual.git",
    },
}

# ---------------------------------------------------------------------------
# Path anchors
# ---------------------------------------------------------------------------
# _resolve.py lives at:
#   <repo>/  .claude/  plugins/  construct3-copilot/  scripts/  _resolve.py
#
# So repo root = scripts/ -> construct3-copilot/ -> plugins/ -> .claude/ -> repo root
#              = parent ** 5
_PLUGIN_SCRIPTS_DIR: Path = Path(__file__).resolve().parent
_COPILOT_REPO_ROOT: Path = _PLUGIN_SCRIPTS_DIR.parent.parent.parent.parent


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _exit_error(message: str, suggestion: str) -> None:
    """Print a JSON error to stdout and exit with code 1."""
    payload = {"error": message, "suggestion": suggestion}
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def resolve_repo(name: str) -> Path:
    """Resolve a sibling repo by *name*.

    1. Check environment variable.
    2. Check sibling directory convention.
    3. Exit 1 with JSON error.
    """
    info = _SIBLINGS.get(name)
    if info is None:
        _exit_error(
            f"Unknown sibling repo: {name}",
            f"Valid names: {', '.join(_SIBLINGS)}",
        )

    # 1. Environment variable
    env_val = os.environ.get(info["env"])
    if env_val:
        p = Path(env_val).resolve()
        if p.is_dir():
            return p
        _exit_error(
            f"${info['env']} is set to '{env_val}' but the directory does not exist",
            f"Fix the path or unset ${info['env']} to use sibling discovery",
        )

    # 2. Sibling directory convention
    sibling = (_COPILOT_REPO_ROOT / ".." / name).resolve()
    if sibling.is_dir():
        return sibling

    # 3. Not found
    _exit_error(
        f"{name} not found",
        f"git clone {info['url']} \"{_COPILOT_REPO_ROOT / '..' / name}\" "
        f"or set ${info['env']}",
    )
    # unreachable, but keeps type checkers happy
    raise SystemExit(1)  # pragma: no cover


def resolve_rag_root() -> Path:
    """Shorthand for ``resolve_repo('Construct3-RAG')``."""
    return resolve_repo("Construct3-RAG")


def resolve_clipboard_root() -> Path:
    """Shorthand for ``resolve_repo('Construct3-Clipboard')``."""
    return resolve_repo("Construct3-Clipboard")


def resolve_rag_schemas(lang: str = "en-US") -> Path:
    """Return ``{rag_root}/data/c3-schemas/{lang}/``.

    Exits with JSON error if the directory does not exist.
    """
    schemas = resolve_rag_root() / "data" / "c3-schemas" / lang
    if not schemas.is_dir():
        _exit_error(
            f"Schema directory not found: {schemas}",
            f"Ensure Construct3-RAG has data/c3-schemas/{lang}/ populated",
        )
    return schemas
