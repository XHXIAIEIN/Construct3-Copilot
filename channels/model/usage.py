"""Token counting: every model call of an answer adds to the thread's tally, and the answer ends with one
line in usage.log. The panel reads that file by its path and line format, so both stay as they are."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

log = logging.getLogger("qqbot.agent")


class Usage:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "logs" / "bot" / "usage.log"  # one line an answer, QQ and --cli alike
        self._tally = threading.local()  # the token count of the answer this thread is giving

    def begin(self) -> dict:
        """Start the tally of the answer this thread gives; return it."""
        self._tally.now = {"calls": 0, "prompt": 0, "completion": 0, "cache_hit": 0}
        return self._tally.now

    def end(self) -> None:
        self._tally.now = None

    def count(self, resp) -> None:
        """Add one model response to the thread's tally, when an answer is being given."""
        tally, usage = getattr(self._tally, "now", None), getattr(resp, "usage", None)
        if tally is not None and usage is not None:
            tally["calls"] += 1
            tally["prompt"] += usage.prompt_tokens or 0
            tally["completion"] += usage.completion_tokens or 0
            tally["cache_hit"] += getattr(usage, "prompt_cache_hit_tokens", 0) or 0

    def write_usage(self, session: Path | None, tally: dict, seconds: float) -> None:
        """Terminal runs (--cli, the plugin's e2e runs) do not write bot.log, so every answer also goes to usage.log."""
        line = (f"{session.name if session else '-'} calls {tally['calls']} prompt {tally['prompt']} "
                f"(cache hit {tally['cache_hit']}) completion {tally['completion']} in {seconds:.0f} s")
        log.info("usage: %s", line)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
        except OSError as exc:
            log.warning("usage.log not written: %s", exc)
