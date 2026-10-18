"""The channel's record of each answer: <data>/logs/<channel>/answers.jsonl, one JSON object a line.

The channel writes the fields every application has (when, which chat, how long, how many model calls and
tokens, the files in and out, whether handle returned); the application's own record (handle's "record") goes
under "app" as it came, unread. How to count the "app" fields is the application's declaration, which
channels/app.py writes to <data>/runtime/app.json at startup."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from .receipt import utc_now

log = logging.getLogger("channels.core.answers")


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


class AnswerLog:
    def __init__(self, data_dir: Path, channel: str) -> None:
        self.channel = channel
        self.path = data_dir / "logs" / channel / "answers.jsonl"
        self._lock = threading.Lock()

    def write(self, answer: Answer, *, chat: str, session: str, files_in: list[dict], files_out: list[dict]) -> dict:
        """Append the answer's line and return it. chat is "private", "group" or "cli"."""
        line = {"at": utc_now(), "channel": self.channel, "chat": chat, "session": session,
                "seconds": round(answer.seconds), "calls": answer.tokens.get("calls", 0),
                "prompt": answer.tokens.get("prompt", 0), "completion": answer.tokens.get("completion", 0),
                "files_in": files_in, "files_out": files_out, "ok": answer.error is None}
        record = answer.result.get("record")
        if isinstance(record, dict):
            line["app"] = record
        elif record is not None:
            log.warning("application record is %s, not an object; left out", type(record).__name__)
        try:
            text = json.dumps(line, ensure_ascii=False, default=str)
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(text + "\n")
        except (OSError, TypeError, ValueError) as exc:
            log.warning("answers.jsonl not written: %s", exc)
        return line


def write_description(data_dir: Path, description: dict) -> Path:
    """Put the application's declaration where the panel reads it; it stays there while the channel is stopped."""
    path = data_dir / "runtime" / "app.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    draft = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    draft.write_text(json.dumps(description, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(draft, path)
    return path
