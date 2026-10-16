"""Local API profiles with dotenv key references and explicit balance evidence."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import io
import json
import os
from pathlib import Path
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid

from dotenv.parser import parse_stream

from .control import ControlError, _date, _digest, _utc

MARKS = {"unknown", "available", "low", "empty"}
_registry_lock = threading.RLock()
SEEDS = [
    ("deepseek", "DeepSeek", ["DEEPSEEK_API_KEY"], "https://api.deepseek.com", "deepseek-flash"),
    ("zhipu", "智谱", ["ZHIPU_API_KEY", "BIGMODEL_KEY"], "https://open.bigmodel.cn/api/paas/v4", "glm-4.5-flash"),
    ("siliconflow", "硅基流动", ["SILICONFLOW_API_KEY", "SILICONFLOW_KEY"], "https://api.siliconflow.cn/v1", ""),
    ("gemini", "Gemini", ["GEMINI_API_KEY", "GEMINI_KEY"], "https://generativelanguage.googleapis.com/v1beta/openai", ""),
    ("claude", "Claude", ["ANTHROPIC_API_KEY", "CLAUDE_KEY"], "", ""),
]


def api_url(value):
    parsed = urllib.parse.urlsplit(value)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.scheme not in {"http", "https"}
            or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})):
        raise ControlError("填写 HTTPS 服务地址，本机接口可使用 HTTP。")
    return value.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ControlError("接口返回重定向，请核对服务地址。")


def fetch_json(url, key):
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + key, "Accept": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=12) as response:
            data = response.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise ControlError("接口返回内容过大。")
        return json.loads(data)
    except urllib.error.HTTPError as exc:
        raise ControlError(f"接口返回 HTTP {exc.code}，请检查凭据或权限。") from None
    except (OSError, ValueError):
        raise ControlError("接口查询失败，请检查网络和配置。") from None


class ApiProfiles:
    def __init__(self, control):
        self.control = control
        self.path = control.home / "var" / "apis.json"

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            folder = self.control._data() / "backups" / "apis"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (uuid.uuid4().hex + ".json")).write_bytes(self.path.read_bytes())
        draft = self.path.with_suffix("." + uuid.uuid4().hex + ".tmp")
        try:
            draft.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(draft, self.path)
        finally:
            draft.unlink(missing_ok=True)

    def _load(self):
        if not self.path.exists():
            env, profiles = self.control._env(), []
            for ident, name, keys, base, model in SEEDS:
                key = next((k for k in keys if env.get(k)), None)
                if key:
                    profiles.append({"id": ident, "name": name, "base_url": base,
                                     "model": env.get(name.upper() + "_MODEL") or model,
                                     "api_key_env": key, "balance_mark": "unknown"})
            self._save({"profiles": profiles})
        try:
            data = json.loads(self.path.read_text(encoding="utf-8-sig"))
            if not isinstance(data["profiles"], list):
                raise ValueError()
            return data
        except (OSError, ValueError, KeyError, TypeError):
            raise ControlError("apis.json 无法读取，请从本地备份恢复。") from None

    def _find(self, data, ident):
        return next((p for p in data["profiles"] if p["id"] == ident), None)

    def public(self):
        with _registry_lock:
            env = self.control._env()
            profiles = []
            for profile in self._load()["profiles"]:
                p = {k: profile[k] for k in ("id", "name", "base_url", "model", "balance_mark", "balance") if k in profile}
                p["has_key"] = bool(env.get(profile.get("api_key_env")))
                p["active"] = env.get("C3BOT_API_PROFILE") == p["id"]
                p["ready"] = bool(p.get("base_url") and p.get("model") and p["has_key"])
                profiles.append(p)
            return profiles

    def save(self, values):
        with self.control._lock:
            data = self._load()
            ident = values.get("id") or uuid.uuid4().hex
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", ident):
                raise ControlError("接口编号无效。")
            old = self._find(data, ident)
            if old and self.control._env().get("C3BOT_API_PROFILE") == ident:
                raise ControlError("请先切换到其他配置，再编辑当前接口。")
            name = str(values.get("name", "")).strip()
            model = str(values.get("model", "")).strip()
            base = str(values.get("base_url", "")).strip()
            if not name or len(name) > 80 or len(model) > 200 or any(c in model for c in "\r\n"):
                raise ControlError("填写接口名称，模型名称不能包含换行。")
            if base:
                base = api_url(base)
            mark = values.get("balance_mark", "unknown")
            if mark not in MARKS:
                raise ControlError("余额标记无效。")
            profile = {**(old or {}), "id": ident, "name": name, "base_url": base, "model": model,
                       "balance_mark": mark, "api_key_env": (old or {}).get("api_key_env") or "QQBOT_API_" + ident.upper()}
            secret = values.get("api_key")
            if secret:
                if not isinstance(secret, str) or len(secret) > 8192 or any(c in secret for c in "\r\n"):
                    raise ControlError("密钥格式无效。")
                original = self.control.env_path.read_bytes()
                key = profile["api_key_env"]
                kept = "".join(b.original.string for b in parse_stream(io.StringIO(original.decode("utf-8-sig"))))
                if not kept.endswith("\n"):
                    kept += "\n"
                # A profile owns its key, so editing cannot replace another application's shared key.
                key = "QQBOT_API_" + ident.upper()
                profile["api_key_env"] = key
                kept = "".join(b.original.string for b in parse_stream(io.StringIO(kept)) if b.key != key)
                updated = kept + key + "=" + json.dumps(secret) + "\n"
                backup = self.control._data() / "backups" / "apis"
                backup.mkdir(parents=True, exist_ok=True)
                (backup / (uuid.uuid4().hex + ".env")).write_bytes(original)
                self.control._write_env(updated.encode("utf-8"), _digest(original))
            if old:
                data["profiles"][data["profiles"].index(old)] = profile
            else:
                data["profiles"].append(profile)
            self._save(data)
            return {"ok": True, "message": "接口已保存。"}

    def delete(self, ident):
        with self.control._lock:
            data = self._load()
            if self.control._env().get("C3BOT_API_PROFILE") == ident:
                raise ControlError("请先切换到其他配置，再删除当前接口。")
            old = self._find(data, ident)
            if old is None:
                raise ControlError("接口不存在，请刷新列表。")
            data["profiles"].remove(old)
            self._save(data)
            return {"ok": True, "message": "接口已删除，本地备份可恢复。"}

    def balance(self, ident):
        with self.control._lock:
            data = self._load()
            profile = self._find(data, ident)
            if profile is None:
                raise ControlError("接口不存在，请刷新列表。")
            balance = {"state": "unsupported", "checked_at": _utc(), "message": "此接口使用手动余额标记。"}
            if profile.get("base_url", "").rstrip("/") in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
                key = self.control._env().get(profile["api_key_env"])
                try:
                    if not key:
                        raise ControlError("缺少接口密钥。")
                    result = fetch_json("https://api.deepseek.com/user/balance", key)
                    entries = [{"currency": str(i["currency"]), "amount": str(Decimal(i["total_balance"]))} for i in result["balance_infos"]]
                    if not entries or any(not Decimal(i["amount"]).is_finite() for i in entries) or not isinstance(result.get("is_available"), bool):
                        raise ValueError()
                    balance.update(state="available" if result["is_available"] else "unavailable", entries=entries,
                                   message="官方查询结果")
                except ControlError as exc:
                    balance.update(state="error", message=str(exc))
                except (ValueError, TypeError, KeyError, InvalidOperation):
                    balance.update(state="error", message="余额响应格式无法识别。")
            profile["balance"] = balance
            self._save(data)
            return {"ok": True, "message": balance["message"]}

    def selection(self, ident):
        profile = self._find(self._load(), ident)
        if profile is None or not profile.get("base_url") or not profile.get("model"):
            raise ControlError("请先补全接口地址和模型名称。")
        api_url(profile["base_url"])
        if not self.control._env().get(profile["api_key_env"]):
            raise ControlError("接口尚未配置密钥。")
        if profile.get("balance_mark") == "empty":
            raise ControlError("此接口已标记余额耗尽，请更新标记后再切换。")
        return profile
