"""What the panel does: show the model and the QQ channel's state, start Ollama, load a model, and switch the model
by rewriting .env and restarting the channel, restoring both when the switch does not finish.

The parts it drives: ollama.py (the local service), envfile.py (.env), gateway.py (the channel's process)."""
from __future__ import annotations

import os
import subprocess
import threading
import urllib.parse
from pathlib import Path

from .. import settings as channel_settings
from ..core.receipt import utc_now
from ..model import settings as model_settings
from .base import ControlError, digest
from .envfile import EnvFile
from .gateway import Gateway
from .ollama import Ollama, local_url

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()

__all__ = ["ControlError", "ModelControl"]


class ModelControl:
    LOAD_TIMEOUT = 120

    def __init__(self, home: Path, repo: Path | None = None):
        self.home = Path(home).resolve()  # channels/: .env and var/
        self.repo = Path(repo).resolve() if repo else self.home.parent  # the checkout that holds .venv/ and channels/
        self.envfile = EnvFile(self.home)
        self.ollama = Ollama(self.home, self.env)
        self.gateway = Gateway(self.home, self.repo, self.env, self.data_dir)
        with _locks_guard:
            self.lock = _locks.setdefault(os.path.normcase(str(self.home)), threading.RLock())

    @property
    def env_path(self) -> Path:
        return self.envfile.path

    @property
    def config_path(self) -> Path:
        return self.ollama.config_path

    @property
    def python(self) -> Path:
        return self.gateway.python

    def env(self) -> dict:
        """.env as written, without the process environment: what the channel will read once restarted."""
        return self.envfile.values()

    def data_dir(self) -> Path:
        return channel_settings.data_dir(self.env(), self.home)

    def status(self) -> dict:
        config, env = self.ollama.config(), self.env()
        models, online = self.ollama.models(config)
        receipt = self.gateway.receipt()
        try:
            alive = bool(self.gateway.identity(receipt))
            verified = alive
        except ControlError:
            alive, verified = False, False
        try:
            model = model_settings.from_settings(env)
        except ValueError:
            raise ControlError(".env 的 C3BOT_EXTRA_BODY 不是有效的 JSON。") from None
        base = urllib.parse.urlsplit(model.base_url)
        public_base = urllib.parse.urlunsplit((base.scheme, base.netloc.rsplit("@", 1)[-1], base.path, "", ""))
        from .api_profiles import ApiProfiles
        registry = ApiProfiles(self)
        return {"apis": registry.public(), "api_key_names": registry.key_names(),
                "current": {"base_url": public_base, "model": model.model,
                            "reasoning": env.get("C3BOT_REASONING", "none")},
                "ollama": {"online": online, "url": local_url(config["url"])}, "models": models,
                "gateway": {**receipt, "alive": alive, "identity_verified": verified,
                            **({"code_change": self.gateway.code_change(receipt)} if alive else {})}, "config_path": str(self.config_path)}

    def start(self) -> dict:
        with self.lock:
            try:
                running = self.ollama.serve(self.ollama.config(), self.data_dir() / "logs" / "ollama")
                return {"ok": True, "message": "Ollama 已运行。" if running else "Ollama 已启动。", "status": self.status()}
            except (ControlError, OSError, subprocess.SubprocessError) as exc:
                return {"ok": False, "message": str(exc) if isinstance(exc, ControlError) else "Ollama 启动未完成。"}

    def warm(self, model: str) -> dict:
        with self.lock:
            try:
                config = self.ollama.config()
                self.ollama.validate(config, model)
                self.gateway.assert_idle()
                result = self.ollama.request(config, "/api/generate", {"model": model, "stream": False, "keep_alive": "10m"},
                                             timeout=self.LOAD_TIMEOUT)
                if result.get("done") is not True:
                    raise ControlError("模型加载尚未确认，请刷新模型状态。")
                return {"ok": True, "message": "模型已预热。", "status": self.status()}
            except (ControlError, OSError) as exc:
                return {"ok": False, "message": str(exc) if isinstance(exc, ControlError) else "模型预热未完成。"}

    def restart(self) -> dict:
        """Restart the channel on .env as it is, e.g. to load new code. A running answer holds it; a process that
        is not the verified one is left alone."""
        gateway = self.gateway
        with self.lock:
            try:
                gateway.assert_idle()
                receipt = gateway.receipt()
                identities = gateway.identity(receipt) if receipt else []
                if not identities and gateway.candidates():
                    raise ControlError("检测到尚未核验的 QQ 启动进程，请先检查其启动收据。")
                gateway.stop(identities)
                launched = utc_now()
                gateway.wait_ready(gateway.launch(), launched)
                return {"ok": True, "message": "QQ 助手已重启并收到就绪事件。", "status": self.status()}
            except Exception as exc:
                return {"ok": False, "message": str(exc) if isinstance(exc, ControlError) else
                        "QQ 助手重启未完成，请检查本地日志。"}

    def switch(self, model: str, *, api=None) -> dict:
        """Point .env at the local model, or at the API profile api, and restart the channel on it."""
        gateway = self.gateway
        with self.lock:
            original = updated = None
            process = None
            stopped = False
            wrote = False
            receipt = {}
            try:
                config = self.ollama.config()
                if api is None:
                    self.ollama.validate(config, model)
                gateway.assert_idle()
                receipt = gateway.receipt()
                identities = gateway.identity(receipt) if receipt else []
                if not identities and gateway.candidates():
                    raise ControlError("检测到尚未核验的 QQ 启动进程，请先检查其启动收据。")
                original = self.envfile.read()
                updated = (self.envfile.with_local_model(original, local_url(config["url"]), model) if api is None
                           else self.envfile.with_api(original, api))
                self.envfile.backup(original, self.data_dir() / "backups" / "models")
                self.envfile.write(updated, digest(original))
                wrote = True
                gateway.assert_idle()
                stopped = bool(identities)
                gateway.stop(identities)
                launched = utc_now()
                process = gateway.launch()
                gateway.wait_ready(process, launched)
                return {"ok": True, "message": "模型已切换，QQ 助手已收到就绪事件。", "status": self.status()}
            except Exception as exc:
                message = str(exc) if isinstance(exc, ControlError) else "模型切换未完成，请检查本地配置和日志。"
                if wrote:
                    restored_config = False
                    try:
                        self.envfile.write(original, digest(updated))
                        restored_config = True
                        if process is not None:
                            gateway.stop_launched(process)
                        if stopped and not gateway.identity(receipt):
                            restored_at = utc_now()
                            restored = gateway.launch()
                            gateway.wait_ready(restored, restored_at)
                        message += " 已恢复原配置。"
                    except Exception:
                        message += (" 已恢复原配置；QQ 重启尚未确认，请检查服务。" if restored_config else
                                    " 自动恢复未完成；当前配置已保留，请检查 QQ 服务。")
                return {"ok": False, "message": message}
