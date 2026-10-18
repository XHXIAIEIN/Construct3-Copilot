"""The message platforms, one folder each. A platform's __main__.py calls channels.core.entry.main with its own
run (connect, receive, send) and uses channels.core.chat for everything that is not the platform's own.

This file is the list the panel reads, plain data only: importing it never imports a platform or its SDK.
Adding a platform: a folder here, its requirements.txt included from channels/requirements.txt, an entry below."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Platform:
    name: str  # the channel name in the answer log: <data>/logs/<name>/answers.jsonl
    label: str
    module: str  # python -m <module> connects
    legacy_modules: tuple[str, ...] = ()  # how a process started before a move was launched; still recognised
    process_logs: str = ""  # under <data>: where the panel sends the stdout and stderr of a process it starts
    logs: list[tuple[str, str, str]] = field(default_factory=list)  # (id, label, path under <data>) the panel shows


PLATFORMS = {
    "qq": Platform(
        name="qq", label="QQ", module="channels.platforms.qq", legacy_modules=("channels.qq",),
        process_logs="logs/bot",  # bot/ is the folder name from qqbot; the data layout is kept as it was
        logs=[("bot", "QQ 对话", "logs/bot/bot.log"),
              ("answers", "QQ 回答记录", "logs/qq/answers.jsonl"),
              ("bot-output", "QQ 进程输出", "logs/bot/model-control.err.log"),
              ("bot-service", "QQ 进程输出（start.ps1）", "logs/bot/service.stderr.log"),
              ("botpy", "QQ 连接", "logs/bot/botpy.log")]),
}

# The platform the panel starts, stops and restarts on a model switch. Running several at once needs a receipt
# per platform (runtime/gateway.json is one file) and is left for when a second platform exists.
PANEL = "qq"
