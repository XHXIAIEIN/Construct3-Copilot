"""One question and its answer, the same on every platform: the daily limit, the chat's recent turns, its session
folder, the call of application.handle and the line in the answer log. A platform receives the message, passes it
to Chats.admit and Chats.ask, sends what comes back the way its platform can, then calls Chats.record with what
it sent."""
from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from functools import wraps
from pathlib import Path

from . import answers as answer_log

log = logging.getLogger("channels.core.chat")

HISTORY_TURNS = 3
DAILY_LIMIT = 30  # questions per chat and day
FAILED = "应用处理失败，请稍后重试。"


def safe_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", key)


def size_of(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def serialized_sessions(handler):
    """Keep a chat's attachment, project and reply changes in message order."""
    locks: dict[str, asyncio.Lock] = {}

    @wraps(handler)
    async def locked(key: str, *args, **kwargs):
        async with locks.setdefault(key, asyncio.Lock()):
            return await handler(key, *args, **kwargs)

    return locked


@dataclass
class Turn:
    """What the application answered, ready to send: its text (FAILED when handle raised) and its files."""
    answer: answer_log.Answer
    text: str = ""
    files: list[Path] = field(default_factory=list)


class Chats:
    def __init__(self, application, *, data_dir: Path, channel: str, usage=None, receipt=None,
                 daily_limit: int = DAILY_LIMIT) -> None:
        """usage: the model client's token counter, which the answer log reads; None leaves the counts at 0.
        receipt: the platform's GatewayReceipt, which counts the answers being given."""
        self.application = application
        self.sessions = data_dir / "sessions"
        self.usage = usage
        self.receipt = receipt
        self.daily_limit = daily_limit
        self.log = answer_log.AnswerLog(data_dir, channel)
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=HISTORY_TURNS * 2))
        self._asked: dict[tuple[str, date], int] = defaultdict(int)

    def admit(self, key: str, question: str) -> str | None:
        """Count the question; the reply to send instead of an answer once the chat has used up today's."""
        log.info("%s asks: %s", key, question)
        self._asked[(key, date.today())] += 1
        if self._asked[(key, date.today())] > self.daily_limit:
            log.info("daily limit reached for %s", key)
            return f"今天的 {self.daily_limit} 个问题已经用完，明天再来。"
        return None

    async def ask(self, key: str, question: str, *, group: bool, attachments: list[dict], notify) -> Turn:
        """Run application.handle in a worker thread. attachments: filename, url, content_type and size each;
        notify(note) is called from that thread for a note the application sends while it works."""
        answer = await asyncio.to_thread(answer_log.handle, self.application, {
            "text": question, "session_id": key, "session_dir": self.sessions / safe_name(key),
            "history": list(self.history[key]), "group": group, "notify": notify, "attachments": attachments,
        }, usage=self.usage, receipt=self.receipt)
        if answer.error is None:
            turn = Turn(answer, answer.result.get("text", ""), [Path(p) for p in answer.result.get("files", [])])
            trace = answer.result.get("trace", [])
        else:
            log.error("application failed", exc_info=answer.error)
            turn, trace = Turn(answer, FAILED), []
        log.info("%s tools: %s", key, trace)
        log.info("%s reply: %s", key, turn.text.replace("\n", " / "))
        self.history[key].extend([{"role": "user", "content": question}, {"role": "assistant", "content": turn.text}])
        return turn

    def record(self, turn: Turn, *, chat: str, session: str, files_in: list[dict], sent: set[Path]) -> dict:
        """The answer's line, written once the platform has sent what it could. chat: "private", "group" or "cli"."""
        return self.log.write(turn.answer, chat=chat, session=session, files_in=files_in,
                              files_out=[answer_log.file_fact(p.name, size_of(p), sent=p in sent) for p in turn.files])
