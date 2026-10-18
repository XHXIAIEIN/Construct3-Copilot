"""The channel's record of each answer: <data>/logs/<channel>/answers.jsonl, one JSON object a line.

The channel writes the fields every application has (when, which chat, how long, how many model calls and
tokens, the files in and out, whether handle returned); the application's own record (handle's "record") goes
under "app" as it came, unread. How to count the "app" fields is the application's declaration, which
channels/app.py writes to <data>/runtime/app.json at startup.

Each answer has a turn id. The question, the reply as sent, the history the application was given and the full tool
trace go to <data>/logs/<channel>/turns.jsonl under that id, so answers.jsonl stays small for the panel's counts and
bot.log keeps one short line per step.

A message the channel drops without an answer (one that only says got it, channels/core/ack.py) goes to
<data>/logs/<channel>/skipped.jsonl with the reason, not to answers.jsonl: the panel's counts and the application's
grader read answers.jsonl as one line per answer given, and a skip is no answer and no failure.
read_answers, read_turns and read_skipped are the readers; python -m channels.logs prints them."""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .receipt import utc_now

log = logging.getLogger("channels.core.answers")

TURNS_BYTES = 32 * 1024 * 1024  # turns.jsonl moves to turns.1.jsonl past this; one older file is kept


@dataclass
class Answer:
    """What one call of application.handle came to, as the channel saw it."""
    result: dict = field(default_factory=dict)
    error: BaseException | None = None
    seconds: float = 0.0
    tokens: dict = field(default_factory=dict)


def handle(application, request: dict, *, usage=None, receipt=None) -> Answer:
    """Call application.handle in this thread, counting its model calls and, with a receipt, holding it as an
    active answer meanwhile. An exception comes back in Answer.error instead of being raised."""
    answer = Answer()
    tally = usage.watch() if usage is not None else {}
    started = time.monotonic()
    try:
        with receipt.answering() if receipt is not None else nullcontext():
            result = application.handle(request)
        answer.result = result if isinstance(result, dict) else {}
    except Exception as exc:  # the channel still replies
        answer.error = exc
    finally:
        answer.seconds = time.monotonic() - started
        answer.tokens = dict(tally)
        if usage is not None:
            usage.unwatch()
    return answer


def file_fact(name: str, size: int | None, **more) -> dict:
    """A file as the log keeps it: its type and size, not its name, since people send private files."""
    return {"type": Path(name or "").suffix.lower(), "bytes": size, **more}


def arrival(arrived: str | None, waited: int | None) -> dict:
    """The fields of when a message came and how long it waited; a line written without them (--cli, lines
    from before) did not measure them."""
    return {name: value for name, value in (("arrived", arrived), ("waited", waited)) if value is not None}


def new_turn_id() -> str:
    """Local time like bot.log's, so a turn is found next to its lines there, and a few random letters."""
    return f"{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


def trace_summary(trace: list) -> str:
    """The tool trace as bot.log keeps it: each step's name in order, a run of the same name as name×n."""
    names: list[list] = []
    for step in trace:
        found = re.match(r"[A-Za-z_][\w-]*", str(step))
        name = found.group(0) if found else str(step)[:20]
        if names and names[-1][0] == name:
            names[-1][1] += 1
        else:
            names.append([name, 1])
    return ", ".join(name if n == 1 else f"{name}×{n}" for name, n in names) or "-"


class AnswerLog:
    def __init__(self, data_dir: Path, channel: str) -> None:
        self.channel = channel
        self.path = data_dir / "logs" / channel / "answers.jsonl"
        self.turns = self.path.with_name("turns.jsonl")
        self.skipped = self.path.with_name("skipped.jsonl")
        self._lock = threading.Lock()

    def write(self, answer: Answer, *, chat: str, session: str, files_in: list[dict], files_out: list[dict],
              turn: str | None = None, question: str = "", reply: str | None = None, written: str | None = None,
              parts: tuple[int, int] | None = None, history: list | None = None, arrived: str | None = None,
              waited: int | None = None) -> dict:
        """Append the answer's line and its turn, and return the line. chat is "private", "group" or "cli";
        reply: the text sent, the application's text when None; written: the text the reply was cut from, kept in
        the turn as "written" when it is not what was sent; parts: how many of the messages the reply was cut into
        went out, and of how many, which the line keeps as reply_parts and reply_sent (absent for a terminal
        answer, which sends nothing); history: the messages the application was given before the question;
        arrived and waited: when the question came and the seconds it waited for the chat's running answer before
        handle started, left out when None."""
        turn = turn or new_turn_id()
        line = {"at": utc_now(), "turn": turn, "channel": self.channel, "chat": chat, "session": session,
                **arrival(arrived, waited),
                "seconds": round(answer.seconds), "calls": answer.tokens.get("calls", 0),
                "prompt": answer.tokens.get("prompt", 0), "completion": answer.tokens.get("completion", 0),
                "files_in": files_in, "files_out": files_out, "ok": answer.error is None}
        if parts is not None:
            line["reply_sent"], line["reply_parts"] = parts[0] == parts[1], list(parts)
        if answer.tokens.get("models"):
            line["model"] = ",".join(answer.tokens["models"])
        record = answer.result.get("record")
        if isinstance(record, dict):
            line["app"] = record
        elif record is not None:
            log.warning("application record is %s, not an object; left out", type(record).__name__)
        trace = answer.result.get("trace")
        content = {"turn": turn, "question": question,
                   "reply": answer.result.get("text", "") if reply is None else reply}
        if written is not None and written != content["reply"]:
            content["written"] = written
        if history is not None:
            content["history"] = history
        content["trace"] = [str(step) for step in trace] if isinstance(trace, list) else []
        try:
            text = json.dumps(line, ensure_ascii=False, default=str)
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(text + "\n")
        except (OSError, TypeError, ValueError) as exc:
            log.warning("answers.jsonl not written: %s", exc)
        try:
            text = json.dumps(content, ensure_ascii=False)
            with self._lock:
                self.turns.parent.mkdir(parents=True, exist_ok=True)
                if self.turns.exists() and self.turns.stat().st_size > TURNS_BYTES:
                    os.replace(self.turns, self.turns.with_name("turns.1.jsonl"))
                with self.turns.open("a", encoding="utf-8") as stream:
                    stream.write(text + "\n")
        except (OSError, TypeError, ValueError) as exc:
            log.warning("turns.jsonl not written: %s", exc)
        return line

    def skip(self, *, chat: str, session: str, reason: str, message: str, after: str, arrived: str | None = None,
             waited: int | None = None) -> dict:
        """Append the line of a message given no answer and return it. reason: why, "ack" for one that only says
        got it; after: the last sentence of the bot's message it followed, where the rule looks for a question or
        an offer; arrived and waited as for write."""
        line = {"at": utc_now(), "channel": self.channel, "chat": chat, "session": session,
                **arrival(arrived, waited), "skipped": reason, "message": message, "after": after}
        try:
            text = json.dumps(line, ensure_ascii=False)
            with self._lock:
                self.skipped.parent.mkdir(parents=True, exist_ok=True)
                with self.skipped.open("a", encoding="utf-8") as stream:
                    stream.write(text + "\n")
        except (OSError, TypeError, ValueError) as exc:
            log.warning("skipped.jsonl not written: %s", exc)
        return line


def _json_lines(path: Path):
    try:
        stream = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with stream:
        for raw in stream:
            try:
                item = json.loads(raw)
            except ValueError:
                continue  # a torn line
            if isinstance(item, dict):
                yield item


def read_answers(data_dir: Path, channel: str) -> list[dict]:
    """The answer lines of a channel, oldest first. Lines written before turn ids have no "turn"."""
    return list(_json_lines(data_dir / "logs" / channel / "answers.jsonl"))


def read_skipped(data_dir: Path, channel: str) -> list[dict]:
    """The messages a channel gave no answer, oldest first."""
    return list(_json_lines(data_dir / "logs" / channel / "skipped.jsonl"))


def read_turns(data_dir: Path, channel: str, ids) -> dict[str, dict]:
    """Question, reply and trace by turn id, for the ids asked for. A turn missing from the result was written
    before turns.jsonl existed or has been rotated out."""
    wanted, found = set(ids), {}
    folder = data_dir / "logs" / channel
    for path in (folder / "turns.1.jsonl", folder / "turns.jsonl"):
        try:
            stream = path.open(encoding="utf-8", errors="replace")
        except OSError:
            continue
        with stream:
            for raw in stream:
                head = raw[:60]  # "turn" is the first key, and a whole line can be a long trace
                if not any(f'"{turn}"' in head for turn in wanted):
                    continue
                try:
                    item = json.loads(raw)
                except ValueError:
                    continue
                if item.get("turn") in wanted:
                    found[item["turn"]] = item
    return found


def write_description(data_dir: Path, description: dict) -> Path:
    """Put the application's declaration where the panel reads it; it stays there while the channel is stopped."""
    path = data_dir / "runtime" / "app.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    draft.write_text(json.dumps(description, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(draft, path)
    return path
