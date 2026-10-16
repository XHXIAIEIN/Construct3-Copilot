"""Select installed Ollama models and restart the configured QQ gateway."""
from __future__ import annotations

import ctypes
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from dotenv.parser import parse_stream

MANAGED = {"C3BOT_BASE_URL", "C3BOT_MODEL", "C3BOT_API_KEY", "C3BOT_REASONING", "C3BOT_EXTRA_BODY"}
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


class ControlError(RuntimeError):
    """An actionable message that contains no transport credentials."""


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _same_path(left, right) -> bool:
    return os.path.normcase(str(Path(left).resolve())) == os.path.normcase(str(Path(right).resolve()))


def _registry_models() -> str | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value = winreg.QueryValueEx(key, "OLLAMA_MODELS")[0]
        return os.path.expandvars(value) if isinstance(value, str) and value else None
    except (ImportError, OSError):
        return None


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


class ModelControl:
    READY_TIMEOUT = 20
    LOAD_TIMEOUT = 120

    def __init__(self, home: Path):
        self.home = Path(home).resolve()
        self.config_path = self.home / "var" / "models.json"
        self.env_path = self.home / ".env"
        self.python = self.home / ".venv" / "Scripts" / "python.exe"
        self._config_lock = threading.Lock()
        with _locks_guard:
            self._lock = _locks.setdefault(os.path.normcase(str(self.home)), threading.RLock())

    def _env(self) -> dict:
        return dict(dotenv_values(self.env_path, interpolate=False))

    def _data(self) -> Path:
        configured = self._env().get("QQBOT_DATA") or self._env().get("C3BOT_DATA")
        return (self.home / configured).resolve() if configured else self.home / "var"

    def _config(self) -> dict:
        with self._config_lock:
            if not self.config_path.exists():
                local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
                executable = shutil.which("ollama") or str(local / "Programs" / "Ollama" / "ollama.exe")
                models = _registry_models() or os.environ.get("OLLAMA_MODELS") or str(Path.home() / ".ollama" / "models")
                base = self._env().get("C3BOT_BASE_URL") or "http://127.0.0.1:11434/v1"
                try:
                    service = self._local_url(base.removesuffix("/v1"))
                except ControlError:
                    service = "http://127.0.0.1:11434"
                defaults = {"ollama": {"url": service, "executable": executable, "models_dir": models}}
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    with self.config_path.open("x", encoding="utf-8") as stream:
                        json.dump(defaults, stream, ensure_ascii=False, indent=2)
                except FileExistsError:
                    pass
            try:
                value = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
                ollama = value["ollama"]
                self._local_url(ollama["url"])
                if not all(isinstance(ollama.get(k), str) and ollama[k] for k in ("executable", "models_dir")):
                    raise ValueError()
                return ollama
            except (KeyError, TypeError, ValueError):
                raise ControlError("models.json 的 Ollama 配置无效，请检查地址、程序和模型目录。") from None

    @staticmethod
    def _local_url(value: str) -> str:
        try:
            parsed = urllib.parse.urlsplit(value)
            if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
                raise ValueError()
            parsed.port
        except (TypeError, ValueError):
            raise ControlError("Ollama 地址必须是本机 HTTP 地址。") from None
        return value.rstrip("/")

    def _request(self, config: dict, endpoint: str, payload=None, timeout=3) -> dict:
        url = self._local_url(config["url"]) + endpoint
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=timeout) as response:
                data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError()
            value = json.loads(data)
            if not isinstance(value, dict) or value.get("error"):
                raise ValueError()
            return value
        except (OSError, ValueError, urllib.error.URLError):
            raise ControlError("Ollama 请求未完成，请检查本地服务和所选模型。") from None

    def _process(self, pid: int) -> dict | None:
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

    def _children(self, pid: int) -> list[dict]:
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
            return [process for pid in pids if (process := self._process(pid)) is not None]
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ControlError("无法核验启动进程的子进程，已保留该进程。") from None

    def _gateway_candidates(self) -> list[dict]:
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
            return [p for pid in pids if (p := self._process(pid)) and self._bot_command(p)]
        except (OSError, ValueError, subprocess.SubprocessError):
            raise ControlError("无法确认 QQ 是否已运行，已保留现有服务。") from None

    def _bot_command(self, process: dict) -> bool:
        args = _command_args(process.get("CommandLine") or "")[1:]
        if args and args[0] == "-u":
            args = args[1:]
        if args == ["-m", "qqbot.qq"] or args == ["bot.py"]:
            return True
        return len(args) == 1 and Path(args[0]).is_absolute() and _same_path(args[0], self.home / "bot.py")

    def _receipt(self) -> dict:
        try:
            value = json.loads((self._data() / "runtime" / "gateway.json").read_text(encoding="utf-8"))
            return {key: value[key] for key in ("status", "pid", "started_at", "ready_at") if key in value}
        except (OSError, ValueError, TypeError):
            return {}

    def _gateway_identity(self, receipt: dict) -> list[dict]:
        if not isinstance(receipt.get("pid"), int) or isinstance(receipt.get("pid"), bool) or receipt["pid"] <= 0:
            raise ControlError("QQ 启动收据中的进程信息无效。")
        try:
            started = _date(receipt["started_at"])
        except (KeyError, TypeError, ValueError):
            raise ControlError("QQ 启动收据中的时间无效。") from None
        process = self._process(receipt.get("pid"))
        if process is None:
            return []
        try:
            created = _date(process["created_at"])
            if not 0 <= (started - created).total_seconds() <= 60 or not self._bot_command(process):
                raise ValueError()
            if process.get("ExecutablePath") and _same_path(process["ExecutablePath"], self.python):
                return [process]
            parent = self._process(process.get("ParentProcessId"))
            if (parent and parent.get("ExecutablePath") and _same_path(parent["ExecutablePath"], self.python)
                    and self._bot_command(parent)
                    and 0 <= (created - _date(parent["created_at"])).total_seconds() <= 5):
                return [process, parent]
        except (KeyError, TypeError, ValueError):
            pass
        raise ControlError("QQ 进程身份与启动收据不符，已保留该进程。")

    def status(self) -> dict:
        config, env = self._config(), self._env()
        models, online = [], False
        try:
            tags = self._request(config, "/api/tags").get("models", [])
            online = True
            try:
                loaded = {m.get("name") or m.get("model") for m in self._request(config, "/api/ps").get("models", [])}
            except ControlError:
                loaded = set()
            for item in tags:
                details = item.get("details") or {}
                models.append({"name": item.get("name") or item.get("model"), "size": item.get("size"),
                               "parameter_size": details.get("parameter_size"),
                               "quantization": details.get("quantization_level"),
                               "loaded": (item.get("name") or item.get("model")) in loaded})
        except ControlError:
            pass
        receipt = self._receipt()
        try:
            alive = bool(self._gateway_identity(receipt))
            verified = alive
        except ControlError:
            alive, verified = False, False
        base = urllib.parse.urlsplit(env.get("C3BOT_BASE_URL") or "https://api.deepseek.com")
        public_base = urllib.parse.urlunsplit((base.scheme, base.netloc.rsplit("@", 1)[-1], base.path, "", ""))
        return {"current": {"base_url": public_base,
                            "model": env.get("C3BOT_MODEL") or env.get("DEEPSEEK_MODEL", "deepseek-flash"),
                            "reasoning": env.get("C3BOT_REASONING", "none")},
                "ollama": {"online": online, "url": self._local_url(config["url"])}, "models": models,
                "gateway": {**receipt, "alive": alive, "identity_verified": verified}, "config_path": str(self.config_path)}

    def _detached(self, argv, env, stdout: Path, stderr: Path):
        stdout.parent.mkdir(parents=True, exist_ok=True)
        startup = subprocess.STARTUPINFO() if os.name == "nt" else None
        if startup:
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = subprocess.SW_HIDE
        flags = (getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                 | getattr(subprocess, "CREATE_NO_WINDOW", 0))
        with stdout.open("ab") as out, stderr.open("ab") as err:
            return subprocess.Popen(argv, cwd=self.home, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                    close_fds=True, startupinfo=startup, creationflags=flags)

    def start(self) -> dict:
        with self._lock:
            try:
                config = self._config()
                try:
                    self._request(config, "/api/tags")
                    return {"ok": True, "message": "Ollama 已运行。", "status": self.status()}
                except ControlError:
                    pass
                executable = (self.home / Path(os.path.expandvars(config["executable"])).expanduser()).resolve()
                if not executable.is_file():
                    raise ControlError("找不到 Ollama 程序，请在 models.json 中填写 executable。")
                env = os.environ.copy()
                env.update(OLLAMA_HOST=urllib.parse.urlsplit(config["url"]).netloc,
                           OLLAMA_MODELS=str((self.home / Path(os.path.expandvars(config["models_dir"])).expanduser()).resolve()))
                logs = self._data() / "logs" / "ollama"
                process = self._detached([str(executable), "serve"], env, logs / "model-control.out.log", logs / "model-control.err.log")
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise ControlError("Ollama 启动失败，请检查本地服务日志。")
                    try:
                        self._request(config, "/api/tags", timeout=1)
                        return {"ok": True, "message": "Ollama 已启动。", "status": self.status()}
                    except ControlError:
                        time.sleep(.25)
                raise ControlError("Ollama 启动尚未确认，请检查本地服务日志。")
            except (ControlError, OSError, subprocess.SubprocessError) as exc:
                return {"ok": False, "message": str(exc) if isinstance(exc, ControlError) else "Ollama 启动未完成。"}

    def _validate(self, config: dict, model: str) -> None:
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model):
            raise ControlError("请选择模型列表中的名称。")
        installed = {m.get("name") or m.get("model") for m in self._request(config, "/api/tags").get("models", [])}
        if model not in installed:
            raise ControlError("该模型尚未安装，请选择列表中的本地模型。")
        capabilities = self._request(config, "/api/show", {"model": model}).get("capabilities", [])
        if not {"completion", "tools"}.issubset(capabilities):
            raise ControlError("该模型未声明文本生成和工具调用能力，不能用于 QQ 助手。")

    def warm(self, model: str) -> dict:
        with self._lock:
            try:
                config = self._config()
                self._validate(config, model)
                self._assert_idle()
                result = self._request(config, "/api/generate", {"model": model, "stream": False, "keep_alive": "10m"}, timeout=self.LOAD_TIMEOUT)
                if result.get("done") is not True:
                    raise ControlError("模型加载尚未确认，请刷新模型状态。")
                return {"ok": True, "message": "模型已预热。", "status": self.status()}
            except (ControlError, OSError) as exc:
                return {"ok": False, "message": str(exc) if isinstance(exc, ControlError) else "模型预热未完成。"}

    def _assert_idle(self) -> None:
        database = self._data() / "copilot" / "tasks.sqlite3"
        if not database.exists():
            return
        try:
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
                active = db.execute("SELECT count(*) FROM tasks WHERE capability='conversation' AND status='running'").fetchone()[0]
        except sqlite3.Error:
            raise ControlError("无法确认会话是否空闲，已保留现有服务。") from None
        if active:
            raise ControlError("QQ 助手仍有运行中的会话，请等回答完成后再切换。")

    def _updated_env(self, original: bytes, config: dict, model: str) -> bytes:
        kept = []
        for binding in parse_stream(io.StringIO(original.decode("utf-8-sig"))):
            if binding.error:
                raise ControlError(".env 有无法解析的配置，请先修复该文件。")
            if binding.key not in MANAGED:
                kept.append(binding.original.string)
        text = "".join(kept)
        if text and not text.endswith("\n"):
            text += "\n"
        text += (f"C3BOT_BASE_URL={self._local_url(config['url'])}/v1\nC3BOT_MODEL={model}\n"
                 "C3BOT_API_KEY=ollama\nC3BOT_REASONING=none\n")
        return text.encode("utf-8")

    def _write_env(self, data: bytes, expected: str) -> None:
        if _digest(self.env_path.read_bytes()) != expected:
            raise ControlError("配置已被另一处修改，已保留其内容，请刷新后重试。")
        scratch = self.home / "var" / "runtime"
        scratch.mkdir(parents=True, exist_ok=True)
        draft = scratch / f"model-env-{uuid.uuid4().hex}.tmp"
        try:
            with draft.open("xb") as stream:
                stream.write(data)
            os.replace(draft, self.env_path)
        finally:
            draft.unlink(missing_ok=True)

    def _stop(self, processes: list[dict]) -> None:
        checked = []
        for expected in processes:
            actual = self._process(expected["ProcessId"])
            if actual is None:
                continue
            if any(actual.get(key) != expected.get(key) for key in ("created_at", "ExecutablePath", "CommandLine")):
                raise ControlError("QQ 进程身份发生变化，已保留该进程。")
            checked.append(expected)
        for expected in checked:
            result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                                     f"Stop-Process -Id {int(expected['ProcessId'])} -Force -ErrorAction Stop"],
                                    capture_output=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode and self._process(expected["ProcessId"]) is not None:
                raise ControlError("QQ 进程未能停止，请检查本地服务。")

    def _launch_bot(self):
        if not self.python.is_file() or not (self.home / "src" / "qqbot" / "qq.py").is_file():
            raise ControlError("QQ 启动文件或项目 Python 不完整。")
        env = os.environ.copy()
        for key in set(self._env()) | {key for key in env if key.startswith(("C3BOT_", "QQBOT_"))}:
            env.pop(key, None)
        env.update(PYTHONUNBUFFERED="1", PYTHONUTF8="1", PYTHONPATH=str(self.home / "src"))
        logs = self._data() / "logs" / "bot"
        started = _utc()
        process = self._detached([str(self.python), "-u", "-m", "qqbot.qq"], env,
                                 logs / "model-control.out.log", logs / "model-control.err.log")
        process._control_started_at = started
        return process

    def _wait_ready(self, process, launched_at: str) -> dict:
        deadline = time.monotonic() + self.READY_TIMEOUT
        while time.monotonic() < deadline:
            receipt = self._receipt()
            try:
                fresh = (_date(receipt["started_at"]) >= _date(launched_at)
                         and _date(receipt["ready_at"]) >= _date(receipt["started_at"]))
                identities = self._gateway_identity(receipt) if fresh and receipt.get("status") == "ready" else []
                if any(item["ProcessId"] == process.pid for item in identities):
                    return receipt
            except (KeyError, TypeError, ValueError, ControlError):
                pass
            if process.poll() is not None:
                raise ControlError("QQ 启动进程已退出，未收到新的就绪事件。")
            time.sleep(.25)
        raise ControlError("20 秒内未收到新 QQ 进程的就绪事件。")

    def _stop_launched(self, process) -> None:
        identity = self._process(process.pid)
        children = self._children(process.pid)
        try:
            launched = _date(process._control_started_at)
            if identity and (not identity.get("ExecutablePath") or not _same_path(identity["ExecutablePath"], self.python)
                             or not self._bot_command(identity) or not 0 <= (_date(identity["created_at"]) - launched).total_seconds() <= 10):
                raise ValueError()
            for child in children:
                if not self._bot_command(child) or not 0 <= (_date(child["created_at"]) - launched).total_seconds() <= 10:
                    raise ValueError()
        except (AttributeError, KeyError, TypeError, ValueError):
            raise ControlError("启动进程身份无法确认，请检查 QQ 服务。") from None
        self._stop(children + ([identity] if identity else []))

    def switch(self, model: str) -> dict:
        with self._lock:
            original = updated = None
            process = None
            stopped = False
            wrote = False
            receipt = {}
            try:
                config = self._config()
                self._validate(config, model)
                self._assert_idle()
                receipt = self._receipt()
                identities = self._gateway_identity(receipt) if receipt else []
                if not identities and self._gateway_candidates():
                    raise ControlError("检测到尚未核验的 QQ 启动进程，请先检查其启动收据。")
                original = self.env_path.read_bytes()
                updated = self._updated_env(original, config, model)
                backups = self._data() / "backups" / "models"
                backups.mkdir(parents=True, exist_ok=True)
                backup = backups / f"env-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}.env"
                backup.write_bytes(original)
                self._write_env(updated, _digest(original))
                wrote = True
                self._assert_idle()
                stopped = bool(identities)
                self._stop(identities)
                launched = _utc()
                process = self._launch_bot()
                self._wait_ready(process, launched)
                return {"ok": True, "message": "模型已切换，QQ 助手已收到就绪事件。", "status": self.status()}
            except Exception as exc:
                message = str(exc) if isinstance(exc, ControlError) else "模型切换未完成，请检查本地配置和日志。"
                if wrote:
                    restored_config = False
                    try:
                        self._write_env(original, _digest(updated))
                        restored_config = True
                        if process is not None:
                            self._stop_launched(process)
                        if stopped and not self._gateway_identity(receipt):
                            restored_at = _utc()
                            restored = self._launch_bot()
                            self._wait_ready(restored, restored_at)
                        message += " 已恢复原配置。"
                    except Exception:
                        message += (" 已恢复原配置；QQ 重启尚未确认，请检查服务。" if restored_config else
                                    " 自动恢复未完成；当前配置已保留，请检查 QQ 服务。")
                return {"ok": False, "message": message}
