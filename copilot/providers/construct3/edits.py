"""What the bot changed in a user's project: the original upload, a snapshot before each edit, and the packed copy.

Kept outside the project folder, under sessions/_edits/<hash of the folder's path>/:
    steps/<n>/     eventSheets/, layouts/ and project.c3proj as they were before edit n; edit_sheet.py writes
                   nothing else (layouts/ only with --new), so steps/1/ is the original upload's part that edits change
    out/           the packed .c3p sent back
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from .services import DATA
from . import services as copilot

ROOT = DATA / "sessions" / "_edits"
SNAPSHOT = ("eventSheets", "layouts", "project.c3proj")  # what edit_sheet.py writes


def side(project: Path) -> Path:
    return ROOT / hashlib.md5(str(project.resolve()).lower().encode()).hexdigest()[:16]


def reset(project: Path) -> None:
    """Forget the edits of an earlier upload to the same folder."""
    shutil.rmtree(side(project), ignore_errors=True)


def _copy(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _steps(project: Path) -> list[Path]:
    folder = side(project) / "steps"
    return sorted((p for p in folder.iterdir() if p.name.isdigit()), key=lambda p: int(p.name)) if folder.is_dir() else []


def snapshot(project: Path) -> None:
    """Keep the sheets before this edit."""
    steps = _steps(project)
    step = side(project) / "steps" / str(int(steps[-1].name) + 1 if steps else 1)
    for name in SNAPSHOT:
        _copy(project / name, step / name)


def drop_snapshot(project: Path) -> None:
    """Forget the last snapshot, after an edit that wrote nothing."""
    steps = _steps(project)
    if steps:
        shutil.rmtree(steps[-1])


def edit_count(project: Path) -> int:
    return len(_steps(project))


def undo(project: Path, everything: bool = False) -> int:
    """Put back the sheets before the last edit, or before the first; return the edits left."""
    steps = _steps(project)
    if not steps:
        return 0
    back = steps[0] if everything else steps[-1]
    for name in SNAPSHOT:
        target = project / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        _copy(back / name, target)
    for step in steps if everything else steps[-1:]:
        shutil.rmtree(step)
    return 0 if everything else len(steps) - 1


def project_name(project: Path) -> str:
    try:
        name = json.loads((project / "project.c3proj").read_text(encoding="utf-8-sig")).get("name") or ""
    except (OSError, json.JSONDecodeError):
        name = ""
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("._") or project.name


def pack(project: Path, rag: Path) -> Path:
    """Pack the project through Copilot as out/<name>-edited.c3p."""
    out = side(project) / "out"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    target = out / f"{project_name(project)}-edited.c3p"
    proc = copilot.run_script("pack_project", ["--out", str(target)], project, timeout=120, rag=rag)
    if proc.returncode != 0 or not target.is_file():
        raise RuntimeError(f"pack_project.py exit {proc.returncode}: {(proc.stdout + proc.stderr).strip()[-500:]}")
    return target
