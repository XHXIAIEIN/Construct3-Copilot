"""One question and its answer, the same on every platform: the daily limit, the chat's recent turns, its session
folder, the call of application.handle and the line in the answer log. A platform takes Chats.arrive as a message
comes, before the message waits for its chat's running answer; once its turn comes, it drops the message when
Chats.acknowledged says it only says got it, passes it to Chats.admit and Chats.ask, sends what comes back the way
its platform can, then calls Chats.record with what it sent: the history and the answer log keep the text the
person received, not the text the application wrote."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

from . import ack, answers as answer_log
from .receipt import utc_now

log = logging.getLogger("channels.core.chat")

HISTORY_TURNS = 3
# a question this long after the chat's last answer starts without its turns, so a person back the next day does not
# bring yesterday's into a new question. A restart takes minutes; the longest pause inside one topic was 87 minutes
# (2026-10-16)
HISTORY_HOURS = 6
DAILY_LIMIT = 30  # questions per chat and day
FAILED = "出错了，过几分钟再问一次。"
# the history's reply when none of it went out. The question stays, since the person asked it and a "怎么没回" after
# it needs it; the reply does not, so the model does not go on from an answer the person never saw
UNSENT = "（这条回复没有发出去。）"


def safe_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", key)


def within_hours(at, hours: float) -> bool:
    """Whether at, a time utc_now wrote, is at most hours ago; a missing or unreadable time is not."""
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(at) <= timedelta(hours=hours)
    except (TypeError, ValueError):
        return False


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
class Arrival:
    """A message as it came, before it waited for its chat's running answer: when (as utc_now writes it and as
    time.monotonic counts it), and seen, the bot's message it follows as Chats.last_sent found it then, which
    acknowledged judges it against. A "好的" sent during a build answers the busy note it saw, not the reply that
    came while it waited."""
    seen: str = ""
    at: str = field(default_factory=utc_now)
    clock: float = field(default_factory=time.monotonic)

    def waited(self) -> int:
        """Whole seconds since the message came."""
        return round(time.monotonic() - self.clock)


@dataclass
class Turn:
    """What the application answered, ready to send: its text (FAILED when handle raised) and its files, with the
    turn id and the question the answer log keeps them under, the history the application was given, and when the
    question came and how many seconds it waited before handle started (both None without an arrival)."""
    answer: answer_log.Answer
    text: str = ""
    files: list[Path] = field(default_factory=list)
    id: str = ""
    question: str = ""
    history: list[dict] = field(default_factory=list)
    arrived: str | None = None
    waited: int | None = None


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
        self.answered: dict[str, str | None] = {}  # when each chat's last answer came, as utc_now wrote it
        # the chats whose answer is being made, each with the busy note that answer sent ("" before one): the
        # note is set from handle's thread and read by arrive on the event loop
        self.answering: dict[str, str] = {}
        self._asked: dict[tuple[str, date], int] = defaultdict(int)

    def recent(self, key: str) -> deque:
        """The chat's last turns, read from disk the first time the chat asks after a start; none once the last
        answer is more than HISTORY_HOURS ago."""
        if key not in self.history:
            turns, at = deque(maxlen=HISTORY_TURNS * 2), None
            path = self.sessions / "_history" / f"{safe_name(key)}.json"
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                # a list is a file from before the time was kept: its age is unknown, so it counts as too old
                if isinstance(saved, dict):
                    at = saved.get("at")
                    turns.extend(m for m in saved.get("turns", [])
                                 if isinstance(m, dict) and isinstance(m.get("content"), str))
            except FileNotFoundError:
                pass
            except (OSError, ValueError, TypeError) as exc:
                log.warning("history of %s unreadable: %s", key, exc)
            self.history[key], self.answered[key] = turns, at
        turns = self.history[key]
        if turns and not within_hours(self.answered.get(key), HISTORY_HOURS):
            log.info("%s starts without the history of its last answer at %s", key, self.answered.get(key))
            turns.clear()
        return turns

    def last_sent(self, key: str) -> str:
        """The bot's message that the chat's next message follows. While an answer is being made, it is that
        answer's busy note: the person saw the note, and it is no question or offer, so a "好的" after it is got it.
        Before a note it is nothing, since the question being answered came after the last reply and already
        answered it. Otherwise it is the last reply in recent."""
        if key in self.answering:
            return self.answering[key]
        return next((m["content"] for m in reversed(self.recent(key)) if m.get("role") == "assistant"), "")

    def arrive(self, key: str) -> Arrival:
        """The message's time and the bot's message it follows, taken as it comes, before it waits for the chat's
        running answer; acknowledged and ask take it once the message's turn comes."""
        return Arrival(seen=self.last_sent(key))

    def acknowledged(self, key: str, question: str, *, chat: str, attachments=(),
                     arrival: Arrival | None = None) -> bool:
        """Whether the message only says got it or thanks after the bot's message it follows ("哦哦", "o了", "谢谢",
        "1"; the words and signals are in ack.json): arrival.seen, or last_sent now without an arrival. Such a
        message gets no reply and no model call, and counts neither against the day's questions nor in the history;
        it goes to skipped.jsonl with the last sentence of that message and how long it waited, so a question
        dropped by mistake can be found. A message with a file is always answered.
        chat: "private", "group" or "cli", as for record."""
        if attachments:
            return False
        last = self.last_sent(key) if arrival is None else arrival.seen
        if not ack.acknowledges(question, last):
            return False
        log.info("%s ack: %s", key, question)
        self.log.skip(chat=chat, session=key, reason="ack", message=question, after=ack.last_sentence(last),
                      arrived=None if arrival is None else arrival.at,
                      waited=None if arrival is None else arrival.waited())
        return True

    def admit(self, key: str, question: str) -> str | None:
        """Count the question; the reply to send instead of an answer once the chat has used up today's."""
        log.info("%s asks: %s", key, question)
        self._asked[(key, date.today())] += 1
        if self._asked[(key, date.today())] > self.daily_limit:
            log.info("daily limit reached for %s", key)
            return f"今天的 {self.daily_limit} 个问题已经用完，明天再来。"
        return None

    async def ask(self, key: str, question: str, *, group: bool, attachments: list[dict], notify,
                  arrival: Arrival | None = None) -> Turn:
        """Run application.handle in a worker thread. attachments: filename, url, content_type and size each;
        notify(note) is called from that thread for a note the application sends while it works. arrival: the
        question's, from arrive; the turn keeps when it came and how long it waited before handle started. The turn
        goes into the history in record, with what was sent; the chat is answering until then, so a message that
        comes while the reply is being sent follows the busy note, not the reply before it."""
        waited = None if arrival is None else arrival.waited()
        history = list(self.recent(key))

        def noted(note: str) -> None:
            self.answering[key] = note
            notify(note)
        self.answering[key] = ""
        try:
            answer = await asyncio.to_thread(answer_log.handle, self.application, {
                "text": question, "session_id": key, "session_dir": self.sessions / safe_name(key),
                "history": list(history), "group": group, "notify": noted if notify else None,
                "attachments": attachments,
            }, usage=self.usage, receipt=self.receipt)
        except BaseException:  # cancelled: no record will end the answering
            self.answering.pop(key, None)
            raise
        turn_id = answer_log.new_turn_id()
        if answer.error is None:
            turn = Turn(answer, answer.result.get("text", ""), [Path(p) for p in answer.result.get("files", [])],
                        turn_id, question, history)
            trace = answer.result.get("trace", [])
        else:
            log.error("application failed", exc_info=answer.error)
            turn, trace = Turn(answer, FAILED, id=turn_id, question=question, history=history), []
        turn.arrived, turn.waited = None if arrival is None else arrival.at, waited
        # the whole trace can be 100 KB; it goes to turns.jsonl with the answer's line
        log.info("%s tools: %s (python -m channels.logs --turn %s)", key, answer_log.trace_summary(trace), turn_id)
        log.info("%s reply: %s", key, turn.text.replace("\n", " / "))
        return turn

    def record(self, turn: Turn, *, chat: str, session: str, files_in: list[dict], sent: set[Path],
               parts: list[str], parts_sent: int) -> dict:
        """Put the turn in the chat's history and write the answer's line, once the platform has sent what it
        could. chat: "private", "group" or "cli"; session: the chat's key as given to ask; sent: the files that went
        out. parts: the messages the platform cut turn.text into to send, after its own limits; parts_sent: how many
        of them went out, first ones first. The history and the turn's reply are those joined as they are, so a
        split that drops what it cuts at drops it there too; a reply none of which went out is UNSENT in the history."""
        parts_sent = max(0, min(parts_sent, len(parts)))
        said = "".join(parts[:parts_sent])
        if parts_sent < len(parts):
            log.warning("%s reply sent %d of %d parts", session, parts_sent, len(parts))
        # not recent() for a chat that asked: the turns this answer went with stay even when it took long
        turns = self.history[session] if session in self.history else self.recent(session)
        turns.extend([{"role": "user", "content": turn.question}, {"role": "assistant", "content": said or UNSENT}])
        self.answered[session] = utc_now()
        # nothing above gives way to the event loop, so the next message's arrive finds this reply in the history
        self.answering.pop(session, None)
        path = self.sessions / "_history" / f"{safe_name(session)}.json"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"at": self.answered[session], "turns": list(turns)}, ensure_ascii=False),
                            encoding="utf-8")
        except OSError as exc:
            log.warning("history of %s not saved: %s", session, exc)
        return self.log.write(turn.answer, chat=chat, session=session, files_in=files_in,
                              turn=turn.id or None, question=turn.question, reply=said, written=turn.text,
                              parts=(parts_sent, len(parts)), history=turn.history,
                              files_out=[answer_log.file_fact(p.name, size_of(p), sent=p in sent) for p in turn.files],
                              arrived=turn.arrived, waited=turn.waited)
