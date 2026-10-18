"""One question and its answer, the same on every platform: the daily limit, the chat's recent turns, its session
folder, the call of application.handle and the line in the answer log. A platform receives the message, drops it
when Chats.acknowledged says it only says got it, passes it to Chats.admit and Chats.ask, sends what comes back
the way its platform can, then calls Chats.record with what it sent."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from functools import wraps
from pathlib import Path

from . import ack, answers as answer_log

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
    """What the application answered, ready to send: its text (FAILED when handle raised) and its files, with the
    turn id and the question the answer log keeps them under."""
    answer: answer_log.Answer
    text: str = ""
    files: list[Path] = field(default_factory=list)
    id: str = ""
    question: str = ""


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
        # kept on disk under sessions/_history: "给我做一个示例" after three restarts came without the question
        # it followed (2026-10-19)
        self.history: dict[str, deque] = {}
        self._asked: dict[tuple[str, date], int] = defaultdict(int)

    def recent(self, key: str) -> deque:
        """The chat's last turns, read from disk the first time the chat asks after a start."""
        if key not in self.history:
            turns = deque(maxlen=HISTORY_TURNS * 2)
            path = self.sessions / "_history" / f"{safe_name(key)}.json"
            try:
                turns.extend(m for m in json.loads(path.read_text(encoding="utf-8"))
                             if isinstance(m, dict) and isinstance(m.get("content"), str))
            except FileNotFoundError:
                pass
            except (OSError, ValueError, TypeError) as exc:
                log.warning("history of %s unreadable: %s", key, exc)
            self.history[key] = turns
        return self.history[key]

    def acknowledged(self, key: str, question: str, *, chat: str, attachments=()) -> bool:
        """Whether the message only says got it or thanks after the chat's last reply ("哦哦", "o了", "谢谢", "1";
        the words and signals are in ack.json). Such a message gets no reply and no model call, and counts neither
        against the day's questions nor in the history; it goes to skipped.jsonl with the last sentence of that
        reply, so a question dropped by mistake can be found. A message with a file is always answered.
        chat: "private", "group" or "cli", as for record."""
        if attachments:
            return False
        last = next((m["content"] for m in reversed(self.recent(key)) if m.get("role") == "assistant"), "")
        if not ack.acknowledges(question, last):
            return False
        log.info("%s ack: %s", key, question)
        self.log.skip(chat=chat, session=key, reason="ack", message=question, after=ack.last_sentence(last))
        return True

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
            "history": list(self.recent(key)), "group": group, "notify": notify, "attachments": attachments,
        }, usage=self.usage, receipt=self.receipt)
        turn_id = answer_log.new_turn_id()
        if answer.error is None:
            turn = Turn(answer, answer.result.get("text", ""), [Path(p) for p in answer.result.get("files", [])],
                        turn_id, question)
            trace = answer.result.get("trace", [])
        else:
            log.error("application failed", exc_info=answer.error)
            turn, trace = Turn(answer, FAILED, id=turn_id, question=question), []
        # the whole trace can be 100 KB; it goes to turns.jsonl with the answer's line
        log.info("%s tools: %s (python -m channels.logs --turn %s)", key, answer_log.trace_summary(trace), turn_id)
        log.info("%s reply: %s", key, turn.text.replace("\n", " / "))
        turns = self.recent(key)
        turns.extend([{"role": "user", "content": question}, {"role": "assistant", "content": turn.text}])
        path = self.sessions / "_history" / f"{safe_name(key)}.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(list(turns), ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            log.warning("history of %s not saved: %s", key, exc)
        return turn

    def record(self, turn: Turn, *, chat: str, session: str, files_in: list[dict], sent: set[Path]) -> dict:
        """The answer's line, written once the platform has sent what it could. chat: "private", "group" or "cli"."""
        return self.log.write(turn.answer, chat=chat, session=session, files_in=files_in,
                              turn=turn.id or None, question=turn.question, reply=turn.text,
                              files_out=[answer_log.file_fact(p.name, size_of(p), sent=p in sent) for p in turn.files])
