"""Token counting: every model call of an answer adds to the thread's tally, and the answer ends with one
line in usage.log. The panel's log page reads that line up to its seconds, so the path and that part stay fixed and
anything more goes at the end. The channel that asked keeps a count of its own for the same answer (watch), for its
answer log."""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

log = logging.getLogger("channels.model.usage")


def cache_counts(usage) -> tuple[int | None, int | None]:
    """The prompt tokens a response read from the server's cache and wrote to it, None for a count it does not
    report. Reads: DeepSeek's prompt_cache_hit_tokens, else OpenAI's prompt_tokens_details.cached_tokens, where the
    Anthropic client puts them too. Writes: only the Anthropic client's prompt_cache_write_tokens."""
    read = getattr(usage, "prompt_cache_hit_tokens", None)
    if read is None:
        read = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", None)
    return read, getattr(usage, "prompt_cache_write_tokens", None)


def new_tally() -> dict:
    # cache_read and cache_write stay None until a response reports them: unknown, not none
    return {"calls": 0, "prompt": 0, "completion": 0, "cache_read": None, "cache_write": None, "models": []}


class Usage:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "logs" / "bot" / "usage.log"  # one line an answer, QQ and --cli alike
        self._tally = threading.local()  # the token count of the answer this thread is giving

    def begin(self) -> dict:
        """Start the tally of the answer this thread gives; return it."""
        self._tally.now = new_tally()
        return self._tally.now

    def end(self) -> None:
        self._tally.now = None

    def watch(self) -> dict:
        """Start the channel's own count of the calls this thread makes, beside the application's tally; return it."""
        self._tally.watched = new_tally()
        return self._tally.watched

    def unwatch(self) -> None:
        self._tally.watched = None

    def count(self, resp) -> None:
        """Add one model response to the thread's tally, when an answer is being given. The model is the one the
        response names, which can differ from the configured name (an alias, a dated version)."""
        usage = getattr(resp, "usage", None)
        model = getattr(resp, "model", None)
        read, write = cache_counts(usage) if usage is not None else (None, None)
        for tally in (getattr(self._tally, "now", None), getattr(self._tally, "watched", None)):
            if tally is not None and isinstance(model, str) and model and model not in tally.setdefault("models", []):
                tally["models"].append(model)
            if tally is not None and usage is not None:
                tally["calls"] += 1
                tally["prompt"] += usage.prompt_tokens or 0
                tally["completion"] += usage.completion_tokens or 0
                for key, value in (("cache_read", read), ("cache_write", write)):
                    if value is not None:
                        tally[key] = (tally.get(key) or 0) + value

    def write_usage(self, session: Path | None, tally: dict, seconds: float) -> None:
        """Terminal runs (--cli, the plugin's e2e runs) do not write bot.log, so every answer also goes to usage.log.
        The cache writes, which only Anthropic's server reports, go at the end of the line."""
        line = (f"{session.name if session else '-'} calls {tally['calls']} prompt {tally['prompt']} "
                f"(cache hit {tally.get('cache_read') or 0}) completion {tally['completion']} in {seconds:.0f} s")
        written = f" (cache write {tally['cache_write']})" if tally.get("cache_write") is not None else ""
        models = ",".join(tally.get("models") or [])
        # bot.log only; the panel reads its model right after the seconds
        log.info("usage: %s%s%s", line, f" model {models}" if models else "", written)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}{written}\n")
        except OSError as exc:
            log.warning("usage.log not written: %s", exc)
