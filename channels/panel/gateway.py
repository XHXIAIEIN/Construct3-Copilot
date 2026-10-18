"""The process of the platform the panel runs (channels/platforms PANEL, now QQ): find it, check it is the one its receipt names, stop it, start it and wait for ready.

The channel writes <data>/runtime/gateway.json (channels/core/receipt.py); the panel trusts it only for a process
that is alive, runs this checkout's Python and was created when the receipt says it started."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import time
from pathlib import Path

from ..core.receipt import utc_now
from ..platforms import PANEL, PLATFORMS, Platform
from .base import ControlError, detached, parse_date, same_path


def _command_args(command: str) -> list[str]:
    if os.name != "nt":
        import shlex
        return shlex.split(command)
    count = ctypes.c_int()
    parser = ctypes.windll.shell32.CommandLineToArgvW
    parser.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parser.restype = ctypes.POINTER(ctypes.c_wchar_p)
    result = parser(command, ctypes.byref(count))
    if not result:
        return []
    try:
        return [result[i] for i in range(count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(result)


class Gateway:
    READY_TIMEOUT = 20

    def __init__(self, home: Path, repo: Path, env, data, platform: Platform = PLATFORMS[PANEL]):
        """env and data: callables returning the current .env values and data folder, which a switch changes."""
        self.platform = platform
        self.home = home
        self.repo = repo
        self.python = repo / ".venv" / "Scripts" / "python.exe"
        self.env = env
        self.data = data

    def process(self, pid: int) -> dict | None:
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            return None
        script = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new();"
                  f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; if($p){{"
                  "$p | Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,"
                  "@{Name='created_at';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress}")
        try:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                    capture_output=True, text=True, encoding="utf-8", timeout=8,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                raise ValueError()
            return json.loads(result.stdout) if result.stdout.strip() else None
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ControlError("无法核验本机进程，已保留现有服务。") from None

    def children(self, pid: int) -> list[dict]:
        script = (f"@(Get-CimInstance Win32_Process -Filter 'ParentProcessId={int(pid)}' | "
                  "Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress")
        try:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                    capture_output=True, text=True, timeout=8,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                raise ValueError()
            pids = json.loads(result.stdout) if result.stdout.strip() else []
            pids = pids if isinstance(pids, list) else [pids]
            return [process for pid in pids if (process := self.process(pid)) is not None]
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ControlError("无法核验启动进程的子进程，已保留该进程。") from None

    def candidates(self) -> list[dict]:
        executable = str(self.python).replace("'", "''")
        script = ("@(Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -eq '"
                  + executable + "'} | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress")
        try:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                    capture_output=True, text=True, timeout=8,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                raise ValueError()
            pids = json.loads(result.stdout) if result.stdout.strip() else []
            pids = pids if isinstance(pids, list) else [pids]
            return [p for pid in pids if (p := self.process(pid)) and self.is_channel(p)]
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ControlError("无法确认 QQ 是否已运行，已保留现有服务。") from None

    def is_channel(self, process: dict) -> bool:
        """python -m with the platform's module or one it had before a move, or the bot.py of the qqbot checkout
        this folder used to be."""
        args = _command_args(process.get("CommandLine") or "")[1:]
        if args and args[0] == "-u":
            args = args[1:]
        if args[:1] == ["-m"] and len(args) == 2 and args[1] in (self.platform.module, *self.platform.legacy_modules):
            return True
        if args == ["bot.py"]:
            return True
        return len(args) == 1 and Path(args[0]).is_absolute() and same_path(args[0], self.home / "bot.py")

    def receipt(self) -> dict:
        try:
            value = json.loads((self.data() / "runtime" / "gateway.json").read_text(encoding="utf-8"))
            return {key: value[key] for key in ("status", "pid", "started_at", "ready_at", "active_answers") if key in value}
        except (OSError, ValueError, TypeError):
            return {}

    def identity(self, receipt: dict) -> list[dict]:
        if not isinstance(receipt.get("pid"), int) or isinstance(receipt.get("pid"), bool) or receipt["pid"] <= 0:
            raise ControlError("QQ 启动收据中的进程信息无效。")
        try:
            started = parse_date(receipt["started_at"])
        except (KeyError, TypeError, ValueError):
            raise ControlError("QQ 启动收据中的时间无效。") from None
        process = self.process(receipt.get("pid"))
        if process is None:
            return []
        try:
            created = parse_date(process["created_at"])
            if not 0 <= (started - created).total_seconds() <= 60 or not self.is_channel(process):
                raise ValueError()
            if process.get("ExecutablePath") and same_path(process["ExecutablePath"], self.python):
                return [process]
            parent = self.process(process.get("ParentProcessId"))
            if (parent and parent.get("ExecutablePath") and same_path(parent["ExecutablePath"], self.python)
                    and self.is_channel(parent)
                    and 0 <= (created - parse_date(parent["created_at"])).total_seconds() <= 5):
                return [process, parent]
        except (KeyError, TypeError, ValueError):
            pass
        raise ControlError("QQ 进程身份与启动收据不符，已保留该进程。")

    def assert_idle(self) -> None:
        """The channel counts the answers it is giving in its receipt; a count left by a process that is gone
        (killed mid-answer) is stale and does not hold the switch."""
        receipt = self.receipt()
        active = receipt.get("active_answers")
        if not active:
            return
        if not isinstance(active, int) or isinstance(active, bool) or active < 0:
            raise ControlError("无法确认会话是否空闲，已保留现有服务。")
        try:
            alive = bool(self.identity(receipt))
        except ControlError:
            raise ControlError("无法确认会话是否空闲，已保留现有服务。") from None
        if alive:
            raise ControlError("QQ 助手仍有运行中的会话，请等回答完成后再切换。")

    def stop(self, processes: list[dict]) -> None:
        checked = []
        for expected in processes:
            actual = self.process(expected["ProcessId"])
            if actual is None:
                continue
            if any(actual.get(key) != expected.get(key) for key in ("created_at", "ExecutablePath", "CommandLine")):
                raise ControlError("QQ 进程身份发生变化，已保留该进程。")
            checked.append(expected)
        for expected in checked:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                                     f"Stop-Process -Id {int(expected['ProcessId'])} -Force -ErrorAction Stop"],
                                    capture_output=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode and self.process(expected["ProcessId"]) is not None:
                raise ControlError("QQ 进程未能停止，请检查本地服务。")

    def launch(self):
        """Start python -m <the platform's module> with the .env settings removed from its environment, so it
        reads .env."""
        entry = self.repo.joinpath(*self.platform.module.split("."), "__main__.py")
        if not self.python.is_file() or not entry.is_file():
            raise ControlError("QQ 启动文件或项目 Python 不完整。")
        env = os.environ.copy()
        for key in set(self.env()) | {key for key in env if key.startswith(("C3BOT_", "QQBOT_"))}:
            env.pop(key, None)
        env.update(PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONPATH=str(self.repo))
        logs = self.data() / self.platform.process_logs
        started = utc_now()
        process = detached([str(self.python), "-u", "-m", self.platform.module], env,
                           logs / "model-control.out.log", logs / "model-control.err.log", cwd=self.home)
        process._control_started_at = started
        return process

    def wait_ready(self, process, launched_at: str) -> dict:
        deadline = time.monotonic() + self.READY_TIMEOUT
        while time.monotonic() < deadline:
            receipt = self.receipt()
            try:
                fresh = (parse_date(receipt["started_at"]) >= parse_date(launched_at)
                         and parse_date(receipt["ready_at"]) >= parse_date(receipt["started_at"]))
                identities = self.identity(receipt) if fresh and receipt.get("status") == "ready" else []
                if any(item["ProcessId"] == process.pid for item in identities):
                    return receipt
            except (KeyError, TypeError, ValueError, ControlError):
                pass
            if process.poll() is not None:
                raise ControlError("QQ 启动进程已退出，未收到新的就绪事件。")
            time.sleep(.25)
        raise ControlError("20 秒内未收到新 QQ 进程的就绪事件。")

    def stop_launched(self, process) -> None:
        identity = self.process(process.pid)
        children = self.children(process.pid)
        try:
            launched = parse_date(process._control_started_at)
            if identity and (not identity.get("ExecutablePath") or not same_path(identity["ExecutablePath"], self.python)
                             or not self.is_channel(identity) or not 0 <= (parse_date(identity["created_at"]) - launched).total_seconds() <= 10):
                raise ValueError()
            for child in children:
                if not self.is_channel(child) or not 0 <= (parse_date(child["created_at"]) - launched).total_seconds() <= 10:
                    raise ValueError()
        except (AttributeError, KeyError, TypeError, ValueError):
            raise ControlError("启动进程身份无法确认，请检查 QQ 服务。") from None
        self.stop(children + ([identity] if identity else []))
