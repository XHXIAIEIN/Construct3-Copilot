"""The local Ollama service: its settings in var/models.json, its HTTP API, its installed models and starting it."""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .base import ControlError, detached


def _registry_models() -> str | None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value = winreg.QueryValueEx(key, "OLLAMA_MODELS")[0]
        return os.path.expandvars(value) if isinstance(value, str) and value else None
    except (ImportError, OSError):
        return None


def local_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError()
        parsed.port
    except (TypeError, ValueError):
        raise ControlError("Ollama 地址必须是本机 HTTP 地址。") from None
    return value.rstrip("/")


class Ollama:
    def __init__(self, home: Path, env):
        """env: a callable returning the current .env values, for the first config's service address."""
        self.home = home
        self.env = env
        self.config_path = home / "var" / "models.json"
        self._config_lock = threading.Lock()

    def config(self) -> dict:
        with self._config_lock:
            if not self.config_path.exists():
                local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
                executable = shutil.which("ollama") or str(local / "Programs" / "Ollama" / "ollama.exe")
                models = _registry_models() or os.environ.get("OLLAMA_MODELS") or str(Path.home() / ".ollama" / "models")
                base = self.env().get("C3BOT_BASE_URL") or "http://127.0.0.1:11434/v1"
                try:
                    service = local_url(base.removesuffix("/v1"))
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
                local_url(ollama["url"])
                if not all(isinstance(ollama.get(k), str) and ollama[k] for k in ("executable", "models_dir")):
                    raise ValueError()
                return ollama
            except (KeyError, TypeError, ValueError):
                raise ControlError("models.json 的 Ollama 配置无效，请检查地址、程序和模型目录。") from None

    def request(self, config: dict, endpoint: str, payload=None, timeout=3) -> dict:
        url = local_url(config["url"]) + endpoint
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

    def models(self, config: dict) -> tuple[list[dict], bool]:
        """The installed models with whether each is loaded, and whether the service answered."""
        models = []
        try:
            tags = self.request(config, "/api/tags").get("models", [])
        except ControlError:
            return models, False
        try:
            loaded = {m.get("name") or m.get("model") for m in self.request(config, "/api/ps").get("models", [])}
        except ControlError:
            loaded = set()
        for item in tags:
            details = item.get("details") or {}
            models.append({"name": item.get("name") or item.get("model"), "size": item.get("size"),
                           "parameter_size": details.get("parameter_size"),
                           "quantization": details.get("quantization_level"),
                           "loaded": (item.get("name") or item.get("model")) in loaded})
        return models, True

    def validate(self, config: dict, model: str) -> None:
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model):
            raise ControlError("请选择模型列表中的名称。")
        installed = {m.get("name") or m.get("model") for m in self.request(config, "/api/tags").get("models", [])}
        if model not in installed:
            raise ControlError("该模型尚未安装，请选择列表中的本地模型。")
        capabilities = self.request(config, "/api/show", {"model": model}).get("capabilities", [])
        if not {"completion", "tools"}.issubset(capabilities):
            raise ControlError("该模型未声明文本生成和工具调用能力，不能用于 QQ 助手。")

    def serve(self, config: dict, logs: Path) -> bool:
        """Start ollama serve when it is not answering; True when it was already running."""
        try:
            self.request(config, "/api/tags")
            return True
        except ControlError:
            pass
        executable = (self.home / Path(os.path.expandvars(config["executable"])).expanduser()).resolve()
        if not executable.is_file():
            raise ControlError("找不到 Ollama 程序，请在 models.json 中填写 executable。")
        env = os.environ.copy()
        env.update(OLLAMA_HOST=urllib.parse.urlsplit(config["url"]).netloc,
                   OLLAMA_MODELS=str((self.home / Path(os.path.expandvars(config["models_dir"])).expanduser()).resolve()))
        process = detached([str(executable), "serve"], env, logs / "model-control.out.log", logs / "model-control.err.log",
                           cwd=self.home)
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise ControlError("Ollama 启动失败，请检查本地服务日志。")
            try:
                self.request(config, "/api/tags", timeout=1)
                return False
            except ControlError:
                time.sleep(.25)
        raise ControlError("Ollama 启动尚未确认，请检查本地服务日志。")

