"""Execute installed scripts and keep the result attached to its task and project."""
from __future__ import annotations

import contextlib
import contextvars
import json
import math
import os
import signal
import subprocess
import sys
from pathlib import Path

from .locks import BusyError, ResourceLock
from .provider import ConstructProvider, fingerprint, project_info
from .store import DuplicateRequestError, Store, now

_active = contextvars.ContextVar("copilot_task", default=None)


def terminate(process):
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, timeout=10)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()


class TaskSession:
    def __init__(self, runtime, source, session_id, project=None, request_id=None, metadata=None):
        self.runtime = runtime
        self.source, self.session_id = source, session_id
        self.project = Path(project).resolve() if project else None
        self.request_id, self.metadata = request_id, metadata or {}
        self.task_id = None
        self.finished = False
        self.lock = ResourceLock(runtime.data_dir / "locks", f"session:{source}:{session_id}")

    def __enter__(self):
        self.lock.__enter__()
        try:
            self.task_id = self.runtime.store.create("conversation", {
                "project": str(self.project) if self.project else None, "metadata": self.metadata,
            }, self.source, self.session_id, self.request_id)
            self.token = _active.set(self)
            return self
        except BaseException:
            self.lock.__exit__()
            raise

    def finish(self, status="completed", summary="", artifacts=()):
        if status not in {"completed", "failed", "interrupted"}:
            raise ValueError(f"Unsupported session status: {status}")
        files = []
        for path in artifacts:
            path = Path(path).resolve()
            if not path.is_file():
                raise ValueError(f"Delivery artifact does not exist: {path}")
            files.append(fingerprint(path))
        result = {"task_id": self.task_id, "status": status, "summary": summary, "artifacts": files}
        self.runtime.store.finish(self.task_id, result)
        self.finished = True
        return result

    def __exit__(self, exc_type, exc, tb):
        try:
            if not self.finished:
                self.finish("failed", str(exc) if exc else "Session ended without an explicit result")
        finally:
            _active.reset(self.token)
            self.lock.__exit__()


class Runtime:
    def __init__(self, skills_root, data_dir, python_executable=sys.executable):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.provider = ConstructProvider(Path(skills_root))
        self.skills_root = self.provider.root
        self.script_root = self.provider.scripts
        self.python_executable = str(python_executable)
        self.store = Store(self.data_dir / "tasks.sqlite3")

    def capabilities(self):
        return self.provider.capabilities()

    def get_task(self, task_id):
        return {**self.store.get(task_id), "children": self.store.children(task_id)}

    def session(self, source, session_id, project=None, request_id=None, metadata=None):
        return TaskSession(self, source, session_id, project, request_id, metadata)

    def run_script(self, name, args, *, project=None, locale=None, limit=None, timeout=90,
                   source="cli", session_id="local", request_id=None, parent_id=None):
        if not isinstance(name, str) or not isinstance(args, (list, tuple)) or not all(isinstance(v, str) and "\0" not in v for v in args):
            raise ValueError("Capability name and argument strings are required")
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0 or timeout > 900:
            raise ValueError("timeout must be between 0 and 900 seconds")
        if locale is not None and not isinstance(locale, str):
            raise ValueError("locale must be a string")
        if limit is not None and (not isinstance(limit, int) or limit < 0):
            raise ValueError("limit must be a non-negative integer")
        project = Path(project).expanduser().resolve() if project else None
        active = _active.get()
        if active and active.runtime.store.path == self.store.path:
            source, session_id, parent_id = active.source, active.session_id, active.task_id
        request = {"capability": name, "args": list(args), "project": str(project) if project else None,
                   "locale": locale, "limit": limit, "timeout": timeout}
        try:
            task_id = self.store.create(name, request, source, session_id, request_id, parent_id)
        except DuplicateRequestError as exc:
            if exc.task["result"] is not None:
                return exc.task["result"]
            return {"task_id": exc.task["task_id"], "status": "running", "exit_code": None,
                    "stdout": "", "stderr": "", "reason": "The original request is still running; it was not re-executed"}
        result = {"task_id": task_id, "parent_id": parent_id, "capability": name,
                  "status": "failed", "exit_code": None, "stdout": "", "stderr": "", "reason": "",
                  "provider": None, "project": None, "artifacts": [], "created_at": now()}
        try:
            cap, script = self.provider.resolve(name)
            if cap.project_required and project is None:
                raise ValueError(f"{cap.name} requires an explicit project folder")
            if cap.name == "new_project" and project is not None:
                raise ValueError("new_project takes its target folder as the first script argument")
            if cap.name == "new_project" and args and args[0].startswith("-"):
                raise ValueError("Put the new project target folder before its options")
            if cap.name == "pack_project":
                options = iter(args)
                for arg in options:
                    if arg in {"--out", "--keep", "--rag"}:
                        next(options, None)
                    elif not arg.startswith("-"):
                        raise ValueError("Folder packing requires the project field; positional SOURCE is not supported")
            result["provider"] = self.provider.info(script)
            argv = [self.python_executable, str(script), *args]
            # The caller's project identity cannot be replaced by a flag in args.
            if "--project" in args or any(a.startswith("--project=") for a in args):
                raise ValueError("Pass project through the project field, not inside args")
            if project is not None:
                argv += ["--project", str(project)]
            if cap.supports_locale and locale is not None:
                argv += ["--locale", locale]
            if cap.supports_limit and limit is not None:
                argv += ["--limit", str(limit)]
            resource = os.path.normcase(str(project)) if project else None
            if cap.name == "new_project" and args:
                resource = os.path.normcase(str(Path(args[0]).expanduser().resolve()))
            lock = ResourceLock(self.data_dir / "locks", "project:" + resource) if resource else contextlib.nullcontext()
            with lock:
                result["project"] = project_info(project)
                self._execute(argv, project, timeout, result)
                if cap.browser and result["exit_code"] == 5:
                    result.update(status="busy", reason="Provider browser profile is in use")
                if result["status"] == "completed":
                    for flag in ("--out", "--plan-only"):
                        output = next((a[len(flag) + 1:] for a in args if a.startswith(flag + "=")), None)
                        if flag in args and args.index(flag) + 1 < len(args):
                            output = args[args.index(flag) + 1]
                        if output:
                            path = Path(output)
                            path = (project or Path.cwd()) / path if not path.is_absolute() else path
                            if path.is_file():
                                result["artifacts"].append(fingerprint(path.resolve()))
                    result["project_after"] = project_info(project)
        except BusyError as exc:
            result.update(status="busy", reason=str(exc))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            result.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
        except BaseException as exc:
            result.update(status="interrupted", reason=type(exc).__name__)
            self.store.finish(task_id, result)
            raise
        return self.store.finish(task_id, result)

    def _execute(self, argv, project, timeout, result):
        env = dict(os.environ)
        env.update(PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(argv, cwd=str(project or Path.cwd()), env=env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            result.update(status="timed_out", reason=f"Script exceeded {timeout:g} seconds")
            try:
                terminate(process)
            except (OSError, subprocess.SubprocessError) as exc:
                result["reason"] += f"; process cleanup failed: {exc}"
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired as exc:
                stdout, stderr = exc.output or b"", exc.stderr or b""
                result["reason"] += "; descendant output handles remained open after cleanup"
        except BaseException:
            terminate(process)
            process.communicate(timeout=10)
            raise
        else:
            result.update(status="completed" if process.returncode == 0 else "failed",
                          reason="" if process.returncode == 0 else f"Script exited with {process.returncode}")
        result.update(exit_code=process.returncode, stdout=stdout.decode("utf-8", errors="replace"),
                      stderr=stderr.decode("utf-8", errors="replace"))
        folder = self.data_dir / "runs" / result["task_id"]
        folder.mkdir(parents=True, exist_ok=True)
        for stream in ("stdout", "stderr"):
            (folder / (stream + ".txt")).write_text(result[stream], encoding="utf-8", newline="")
