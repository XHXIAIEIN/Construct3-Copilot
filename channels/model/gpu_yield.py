"""Gives the GPU to the TTS server while it generates: the local model waits and is unloaded.

The TTS page submits POST /api/jobs and then polls GET /api/jobs every 0.4 s until
its jobs end, so its uvicorn log is written several times a second exactly while it generates. That log has no
timestamps; its modification time plus a jobs line in its tail is the signal.
C3BOT_YIELD_LOGS lists the logs to watch, separated by ";"; the model settings pass them in.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from pathlib import Path

FRESH = 5  # seconds since the log's last write that still count as generating
POLL = 2
MARKS = (b"/api/jobs", b"/api/tts", b"/api/concat")

log = logging.getLogger("channels.model.gpu_yield")
_missing_said: set[Path] = set()


def tts_busy(logs) -> bool:
    now = time.time()
    for path in map(Path, logs):
        try:
            st = path.stat()
            if now - st.st_mtime > FRESH:
                continue
            with path.open("rb") as f:
                f.seek(max(0, st.st_size - 2048))
                tail = f.read()
        except FileNotFoundError:
            if path not in _missing_said:
                log.warning("yield: %s not found, the TTS server cannot be watched there", path)
                _missing_said.add(path)
            continue
        except OSError:
            continue
        if any(m in tail for m in MARKS):
            return True
    return False


def unload(base_url: str, model: str) -> None:
    """Frees the model's VRAM now (Ollama's keep_alive 0); the next call loads it again."""
    root = base_url.rstrip("/").removesuffix("/v1")
    req = urllib.request.Request(f"{root}/api/generate", data=json.dumps({"model": model, "keep_alive": 0}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except OSError as exc:
        log.warning("yield: unload failed: %s", exc)


def wait_for_tts(base_url: str, model: str, logs) -> None:
    """Called before every local model call; returns at once when the TTS server is idle."""
    if not logs or not tts_busy(logs):
        return
    started = time.time()
    log.info("yield: TTS is generating, unloading %s and waiting", model)
    unload(base_url, model)
    while tts_busy(logs):
        time.sleep(POLL)
    log.info("yield: TTS idle again after %d s", time.time() - started)
