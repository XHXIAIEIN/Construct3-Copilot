"""Read the tail of the bot's and the panel's own logs, with the credentials the panel knows about removed."""
from __future__ import annotations

import json
from datetime import datetime
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
# One line an answer, as qqbot.usage.write_usage writes it (not imported: that module loads the bot's config).
USAGE = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) (\S+) calls (\d+) prompt (\d+) \(cache hit \d+\) completion (\d+) in (\d+) s")


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


USAGE_BYTES = 2 * 1024 * 1024  # about 20 000 answers
BOT_BYTES = 8 * 1024 * 1024
# copilot's attachments.PROJECT_SUFFIXES: the files it unpacks as a project (copied, copilot is another checkout)
PROJECTS = {".c3p", ".zip", ".capx", ".rar", ".7z", ".tar", ".tgz", ".gz"}
# bot.log lines as qqbot.qq and copilot's construct3 application write them; free text, so a reworded message
# drops out of the counts instead of breaking the page.
STAMPED_LINE = re.compile(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+ \S+ (?:INFO|WARNING|ERROR) (.*)")
# A chat's own lines start with its session key ("c2c:<openid>" or "group:<group>:<member>"); newer bots also key
# the attachment and send lines, older logs do not.
KEYED = re.compile(r"((c2c|group):\S+) (.*)")
TOOLS = re.compile(r"tools: (.*)")
# One build in a tool trace: copilot's tool_trace keeps the first four lines of its result after " -> ", at most
# 600 characters, so a long list of fixes is counted short.
BUILD = re.compile(r"""(?:new_project_from_\w+|patch_spec)\(.*?\) -> (.*?)(?=['"](?:, ['"]|\]$))""")
ATTACHMENT = re.compile(r"attachment: name-md5 \w+, \w+, (\d+) bytes, (\S*)")
SENT = re.compile(r"sent file (\d+) bytes")
# Unkeyed lines are placed by order: an answer runs from "<key> asks" to "<key> reply" and sends its file right
# after the reply, so a line belongs to the one chat in that state, or to no chat when two overlap.
SEND_WINDOW = 120


def _tail(path, cap):
    with path.open("rb") as stream:
        size = stream.seek(0, 2)
        stream.seek(max(0, size - cap))
        return stream.read().decode("utf-8", errors="replace"), size > cap


def events(control):
    """Project files received and sent, and project builds, from bot.log, each with its chat ("private",
    "group", or None when the log cannot tell)."""
    received, sent, builds = [], [], []
    try:
        text, clipped = _tail(_path(control, "bot")[1], BOT_BYTES)
    except OSError:
        return {"received": received, "sent": sent, "builds": builds, "clipped": False}
    chat = lambda key: "private" if key.startswith("c2c:") else "group"
    answering, replied = set(), {}  # keys between asks and reply; keys that replied, with when
    for line in text.splitlines():
        stamped = STAMPED_LINE.match(line)
        if not stamped:
            continue
        at, message = stamped.groups()
        when = datetime.strptime(at, "%Y-%m-%d %H:%M:%S")
        keyed = KEYED.match(message)
        key, body = (keyed[1], keyed[3]) if keyed else (None, message)
        if body.startswith("asks: ") and key:
            answering.add(key)
        elif body.startswith("reply: ") and key:
            answering.discard(key)
            replied[key] = when
        elif body.startswith("daily limit reached for "):
            answering.discard(body.removeprefix("daily limit reached for "))
        elif body == "QQ gateway connection starting":
            answering.clear()
            replied.clear()
        elif (tools := TOOLS.match(body)) and key:
            for result in BUILD.findall(tools[1]):
                # The trace keeps four result lines; with four fixes or more the outcome line is cut, so neither
                # "built" nor a failure shows and the build is "unknown". A fix is a spec error the builder
                # corrected, counted whatever the build's outcome.
                outcome = ("failed" if re.search(r"(^| / )(refused|copilot failed)", result)
                           else "built" if re.search(r"(^| / )built:", result) else "unknown")
                builds.append({"at": at, "chat": chat(key), "outcome": outcome, "fixes": result.count("fixed: ")})
        elif attachment := ATTACHMENT.match(body):
            owner = key or (next(iter(answering)) if len(answering) == 1 else None)
            if attachment[2].lower() in PROJECTS:
                received.append({"at": at, "chat": owner and chat(owner), "bytes": int(attachment[1])})
        elif (sending := SENT.match(body)) or body.startswith("file send failed"):
            recent = [k for k, t in replied.items() if (when - t).total_seconds() <= SEND_WINDOW]
            owner = key or (recent[0] if len(recent) == 1 else None)
            replied.pop(owner, None)  # an answer sends one file
            sent.append({"at": at, "chat": owner and chat(owner), "bytes": int(sending[1]) if sending else 0,
                         "ok": bool(sending)})
    return {"received": received, "sent": sent, "builds": builds, "clipped": clipped}


def usage(control):
    """Every answer usage.log records (QQ ones only, not terminal runs), oldest first, and the project events of
    bot.log. A person is a session name, sent as a number so the page never sees an openid; the same person in a
    group and in private counts twice."""
    people, answers = {}, []
    try:
        text, clipped = _tail(_path(control, "usage")[1], USAGE_BYTES)
    except OSError:
        text, clipped = "", False
    for line in text.splitlines():
        match = USAGE.fullmatch(line.strip())
        if not match or not match[2].startswith(("c2c_", "group_")):
            continue
        answers.append({"at": match[1], "who": people.setdefault(match[2], len(people)),
                        "chat": "private" if match[2].startswith("c2c_") else "group", "calls": int(match[3]),
                        "prompt": int(match[4]), "completion": int(match[5]), "seconds": int(match[6])})
    found = events(control)
    return {"clipped": clipped or found.pop("clipped"), "answers": answers, **found}
