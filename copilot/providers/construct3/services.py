"""Bind Construct tools to a host's runtime, paths and active task."""
from __future__ import annotations

import os
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from ...runtime import Runtime, _active

REPOSITORY = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get("COPILOT_PROVIDER_DATA") or Path.cwd() / ".local/construct3").resolve()
RAG = Path(os.environ.get("COPILOT_RAG") or REPOSITORY.parent / "Construct3-RAG").resolve()
LOCALE = os.environ.get("COPILOT_LOCALE", "zh-CN")
SOURCE = os.environ.get("COPILOT_SOURCE", "local")
OPTIONS = json.loads(os.environ.get("COPILOT_C3_OPTIONS", "{}"))
_runtime = None
_binding = None


def configure(runtime, *, data_dir, rag, locale="zh-CN", source="local", options=None):
    global _runtime, _binding, DATA, RAG, LOCALE, SOURCE, OPTIONS
    binding = (str(Path(data_dir).resolve()), str(Path(rag).resolve()), locale, source,
               str(runtime.skills_root), str(runtime.data_dir), json.dumps(options or {}, sort_keys=True))
    if _binding is not None and _binding != binding:
        raise RuntimeError("Construct provider already belongs to another host; use a separate process")
    _binding = binding
    _runtime = runtime
    DATA, RAG, LOCALE, SOURCE = Path(binding[0]), Path(binding[1]), locale, source
    OPTIONS = dict(options or {})


def get_runtime():
    global _runtime
    if _runtime is None:
        skills = Path(os.environ.get("COPILOT_SKILLS_ROOT") or REPOSITORY.parent / "Construct3-Agent-Skills")
        data = Path(os.environ.get("COPILOT_DATA") or DATA / "copilot")
        _runtime = Runtime(skills, data, python_executable=sys.executable)
    return _runtime


def temporary_directory():
    scratch = DATA / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=scratch)


def child_environment():
    runtime = get_runtime()
    env = os.environ.copy()
    env.update(COPILOT_SKILLS_ROOT=str(runtime.skills_root), COPILOT_DATA=str(runtime.data_dir),
               COPILOT_PROVIDER_DATA=str(DATA), COPILOT_RAG=str(RAG), COPILOT_LOCALE=LOCALE,
               COPILOT_SOURCE=SOURCE, COPILOT_C3_OPTIONS=json.dumps(OPTIONS))
    active = _active.get()
    if active:
        env.update(COPILOT_PARENT_TASK=active.task_id, COPILOT_SESSION=active.session_id)
    return env


def run_script(name, args, project=None, *, locale=None, limit=None, timeout=90, rag=None):
    runtime = get_runtime()
    args = list(args)
    if "--rag" not in args:
        args += ["--rag", str(runtime.skills_root if name == "search_guides" else rag or RAG)]
    context = {}
    if _active.get() is None and os.environ.get("COPILOT_PARENT_TASK"):
        context = {"parent_id": os.environ["COPILOT_PARENT_TASK"],
                   "session_id": os.environ.get("COPILOT_SESSION", "local")}
    result = runtime.run_script(name, args, project=project, locale=locale, limit=limit,
                                timeout=timeout, source=SOURCE, **context)
    code = result.get("exit_code")
    if code is None:
        code = {"timed_out": 124, "busy": 5, "running": 75}.get(result["status"], 1)
    stdout, stderr = result.get("stdout") or "", result.get("stderr") or ""
    if result["status"] != "completed":
        stdout = f"copilot {result['status']}: {result.get('reason') or 'skill execution failed'}\n{stdout}"
        if code == 0:
            code = 1
    return subprocess.CompletedProcess([name, *args], code, stdout, stderr)
