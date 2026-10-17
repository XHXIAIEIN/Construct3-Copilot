"""Read the tail of the bot's and the panel's own logs, with the credentials the panel knows about removed."""
from __future__ import annotations

import json
import re

from .api_profiles import SEEDS, key_names

# The only files the panel shows: (id, label, base, path). "data" is the bot's data folder (QQBOT_DATA, default var/),
# "home" the project folder. Clients name a log by id and never send a path.
LOGS = [
    ("bot", "QQ 对话", "data", "logs/bot/bot.log"),
    ("bot-output", "QQ 进程输出", "data", "logs/bot/model-control.err.log"),
    ("bot-service", "QQ 进程输出（start.ps1）", "data", "logs/bot/service.stderr.log"),
    ("botpy", "QQ 连接", "data", "logs/bot/botpy.log"),
    ("usage", "用量", "data", "logs/bot/usage.log"),
    ("panel", "面板", "home", "var/logs/models/panel.log"),
    ("panel-output", "面板错误输出", "home", "var/logs/models/panel.stderr.log"),
    ("ollama", "Ollama（面板启动）", "data", "logs/ollama/model-control.err.log"),
]
TAIL_BYTES = 256 * 1024
MAX_LINES = 1000
LINE_CHARS = 1000
# Values shorter than this are placeholders such as C3BOT_API_KEY=ollama; replacing them would blank ordinary words.
MIN_SECRET = 8
BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]{8,}")


def _path(control, ident):
    entry = next((e for e in LOGS if e[0] == ident), None)
    if entry is None:
        raise KeyError(ident)
    base = control._data() if entry[2] == "data" else control.home
    return entry, base / entry[3]


def catalog(control):
    result = []
    for entry in LOGS:
        _, path = _path(control, entry[0])
        # No modified time: Windows may not update it while the writer keeps the file open, so it would mislead.
        try:
            size = path.stat().st_size
        except OSError:
            size = None
        result.append({"id": entry[0], "label": entry[1], "file": path.name, "exists": size is not None, "size": size})
    return result


def secrets(control):
    """Values of the .env entries the panel treats as credentials: the bot's QQ secret, C3BOT_API_KEY, every name the
    key list shows, every provider key name it seeds, and every profile's api_key_env. Longest first, so a value that
    contains another is replaced whole."""
    env = control._env()
    names = {"QQ_SECRET", "C3BOT_API_KEY"} | set(key_names(env)) | {k for seed in SEEDS for k in seed[2]}
    try:
        profiles = json.loads((control.home / "var" / "apis.json").read_text(encoding="utf-8-sig"))["profiles"]
        names |= {p["api_key_env"] for p in profiles if isinstance(p, dict) and isinstance(p.get("api_key_env"), str)}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    found = {env[n]: n for n in sorted(names) if isinstance(env.get(n), str) and len(env[n].strip()) >= MIN_SECRET}
    return sorted(((value.strip(), name) for value, name in found.items()), key=lambda item: -len(item[0]))


def redact(line, hidden):
    for value, name in hidden:
        if value in line:
            line = line.replace(value, f"‹已隐藏 {name}›")
    return BEARER.sub(r"\1‹已隐藏›", line)


def read(control, ident, after=None):
    """Lines appended since byte offset `after`, or the recent tail when `after` is missing, stale or too far back.
    Only complete lines are returned; `offset` is where the next read continues."""
    entry, path = _path(control, ident)
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, 2)
            reset = after is None or not 0 <= after <= size or size - after > TAIL_BYTES
            start = max(0, size - TAIL_BYTES) if reset else after
            stream.seek(start)
            data = stream.read(size - start)
    except OSError:
        return {"id": ident, "label": entry[1], "exists": False, "offset": 0, "size": 0, "reset": True, "lines": []}
    end = data.rfind(b"\n") + 1
    offset = start + end
    data = data[:end]
    if reset and start > 0:
        data = data[data.find(b"\n") + 1:]  # the first line began before the tail
    lines = data.decode("utf-8", errors="replace").splitlines()
    clipped = reset and len(lines) > MAX_LINES
    hidden = secrets(control)
    shown = []
    for line in lines[-MAX_LINES:]:
        line = redact(line, hidden)
        if len(line) > LINE_CHARS:
            line = line[:LINE_CHARS] + f" …（截断，整行 {len(line)} 字）"
        shown.append(line)
    return {"id": ident, "label": entry[1], "exists": True, "offset": offset, "size": size, "reset": reset,
            "clipped": clipped or (reset and start > 0), "lines": shown}
