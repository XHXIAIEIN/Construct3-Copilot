"""Resolve an installed Construct provider and its explicit script capabilities."""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(frozen=True)
class Capability:
    name: str
    project_required: bool = False
    supports_locale: bool = True
    supports_limit: bool = True
    changes_project: bool = False
    browser: bool = False


CAPABILITIES = {c.name: c for c in [
    Capability("lookup_ace"), Capability("lookup_script_api"), Capability("search_guides"),
    Capability("print_sheet", True), Capability("print_layout", True),
    Capability("check_project", True), Capability("review_design", True),
    Capability("check_design"), Capability("edit_sheet", True, changes_project=True),
    Capability("new_project", supports_locale=False, supports_limit=False, changes_project=True),
    Capability("pack_project", True, supports_locale=False, supports_limit=False),
    Capability("open_in_editor", True, browser=True), Capability("preview_project", True, browser=True),
    Capability("play_design", True, changes_project=True, browser=True),
    Capability("review_look", True, supports_locale=False, browser=True),
    Capability("screenshot_sheet", True, supports_locale=False, supports_limit=False, browser=True),
    Capability("prepare_art", True, changes_project=True), Capability("check_look", True),
    Capability("export_project", True, supports_locale=False, supports_limit=False, changes_project=True, browser=True),
    Capability("advanced_random", supports_locale=False),
]}


def fingerprint(path: Path) -> dict:
    return {"path": str(path), "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class ConstructProvider:
    def __init__(self, root: Path):
        root = Path(root).expanduser().resolve()
        candidates = [root / "plugin", root, root.parent.parent]
        self.root = next((p for p in candidates if
                          (p / "skills/construct3-agent-plugin/scripts/lookup_ace.py").is_file()), None)
        if self.root is None and (root / "scripts/lookup_ace.py").is_file():
            self.root = root.parent.parent
        if self.root is None:
            raise ValueError(f"No Agent-Skills installation at {root}. Pass its repository, plugin, or skill folder.")
        self.scripts = self.root / "skills/construct3-agent-plugin/scripts"
        if not self.scripts.is_dir():
            raise ValueError(f"Installation has no script directory: {self.scripts}")
        try:
            rev = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                                 capture_output=True, text=True, timeout=5)
            self.revision = rev.stdout.strip() if rev.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            self.revision = None

    def resolve(self, name):
        name = name.removesuffix(".py")
        if name not in CAPABILITIES:
            raise ValueError(f"Unknown capability {name!r}; use capabilities to list installed tools")
        script = self.scripts / (name + ".py")
        if not script.is_file() or script.resolve().parent != self.scripts.resolve():
            raise ValueError(f"Capability is not installed as a regular provider script: {name}")
        return CAPABILITIES[name], script

    def info(self, script):
        return {"id": "construct3-agent-skills", "root": str(self.root),
                "revision": self.revision, "script": fingerprint(script)}

    def capabilities(self):
        return [{**asdict(c), "available": (self.scripts / (c.name + ".py")).is_file()}
                for c in CAPABILITIES.values()]


def project_info(path: Path | None):
    if path is None:
        return None
    root = path.expanduser().resolve()
    manifest = root / "project.c3proj"
    if not manifest.is_file():
        raise ValueError(f"No project.c3proj in {root}")
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"project.c3proj must contain an object: {manifest}")
    return {"path": str(root), "unique_id": data.get("uniqueId"),
            "manifest": fingerprint(manifest)}
