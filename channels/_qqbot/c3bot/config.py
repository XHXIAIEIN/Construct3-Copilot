"""Settings read from the environment once, when the bot starts: where the RAG clone is, which model answers and
how it is called. bot.py loads .env before it imports anything that imports this module."""
from __future__ import annotations

import json
import os
from pathlib import Path

HOME = Path(__file__).resolve().parent.parent  # the bot folder: .env, logs/, sessions/
RAG = Path(os.environ.get("CONSTRUCT3_RAG", r"D:\Users\Administrator\Documents\GitHub\Construct3-RAG"))
LOCALE = os.environ.get("C3BOT_LOCALE", "zh-CN")
# C3BOT_BASE_URL points at any OpenAI-compatible server, e.g. Ollama's http://localhost:11434/v1
BASE_URL = os.environ.get("C3BOT_BASE_URL", "https://api.deepseek.com")
SILICONFLOW = "siliconflow" in BASE_URL  # hosted Chinese models, for comparison runs (2026-10-09)
ZHIPU = "bigmodel.cn" in BASE_URL  # glm-4.7-flash, free (2026-10-09)
LOCAL = "api.deepseek.com" not in BASE_URL and not SILICONFLOW and not ZHIPU
MODEL = os.environ.get("C3BOT_MODEL") or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
TIMEOUT = 600 if LOCAL else 300 if SILICONFLOW or ZHIPU else 120  # a local model reads a long prompt slowly
# thinking off: DeepSeek reads "thinking", Ollama reads reasoning_effort "none", SiliconFlow reads enable_thinking;
# C3BOT_EXTRA_BODY (JSON) replaces it for a model that wants another switch
NO_THINK = ({"reasoning_effort": os.environ.get("C3BOT_REASONING", "none"), "max_tokens": 6000} if LOCAL
            else {"enable_thinking": False, "max_tokens": 6000} if SILICONFLOW
            else {"thinking": {"type": "disabled"}, "max_tokens": 6000} if ZHIPU
            else {"thinking": {"type": "disabled"}})
if os.environ.get("C3BOT_EXTRA_BODY"):
    NO_THINK = json.loads(os.environ["C3BOT_EXTRA_BODY"])
MAX_STEPS = 10
