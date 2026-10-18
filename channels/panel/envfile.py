"""channels/.env as the panel changes it: the model settings it manages, replaced in place, the rest of the file
kept line for line, and a write that refuses when the file changed since it was read."""
from __future__ import annotations

import io
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from dotenv.parser import parse_stream

from .base import ControlError, digest

MANAGED = {"C3BOT_BASE_URL", "C3BOT_MODEL", "C3BOT_API_KEY", "C3BOT_REASONING", "C3BOT_EXTRA_BODY", "C3BOT_API_PROFILE", "C3BOT_API_KEY_ENV", "C3BOT_API_PROTOCOL"}


class EnvFile:
    def __init__(self, home: Path):
        self.home = home
        self.path = home / ".env"

    def values(self) -> dict:
        return dict(dotenv_values(self.path, interpolate=False))

    def read(self) -> bytes:
        return self.path.read_bytes()

    @staticmethod
    def _kept(original: bytes) -> str:
        """Every line of the file but the managed settings, ending with a newline."""
        kept = []
        for binding in parse_stream(io.StringIO(original.decode("utf-8-sig"))):
            if binding.error:
                raise ControlError(".env 有无法解析的配置，请先修复该文件。")
            if binding.key not in MANAGED:
                kept.append(binding.original.string)
        text = "".join(kept)
        if text and not text.endswith("\n"):
            text += "\n"
        return text

    def with_local_model(self, original: bytes, url: str, model: str) -> bytes:
        return (self._kept(original) + f"C3BOT_BASE_URL={url}/v1\nC3BOT_MODEL={model}\n"
                "C3BOT_API_KEY=ollama\nC3BOT_REASONING=none\n").encode("utf-8")

    def with_api(self, original: bytes, api: dict) -> bytes:
        """Unlike a local model, an API profile switch keeps lines the parser cannot read, as it always has."""
        bindings = parse_stream(io.StringIO(original.decode("utf-8-sig")))
        kept = "".join(b.original.string for b in bindings if b.key not in MANAGED)
        if not kept.endswith("\n"):
            kept += "\n"
        values = {"C3BOT_BASE_URL": api["base_url"], "C3BOT_MODEL": api["model"],
                  "C3BOT_API_PROFILE": api["id"], "C3BOT_API_KEY_ENV": api["api_key_env"],
                  "C3BOT_API_PROTOCOL": api.get("protocol", "auto")}
        return (kept + "".join(k + "=" + json.dumps(v) + "\n" for k, v in values.items())).encode("utf-8")

    def write(self, data: bytes, expected: str) -> None:
        """Replace the file with data, when its contents still have the digest expected."""
        if digest(self.path.read_bytes()) != expected:
            raise ControlError("配置已被另一处修改，已保留其内容，请刷新后重试。")
        scratch = self.home / "var" / "runtime"
        scratch.mkdir(parents=True, exist_ok=True)
        draft = scratch / f"model-env-{uuid.uuid4().hex}.tmp"
        try:
            with draft.open("xb") as stream:
                stream.write(data)
            os.replace(draft, self.path)
        finally:
            draft.unlink(missing_ok=True)

    @staticmethod
    def backup(original: bytes, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        backup = folder / f"env-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}.env"
        backup.write_bytes(original)
        return backup
