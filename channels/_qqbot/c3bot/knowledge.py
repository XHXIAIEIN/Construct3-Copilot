"""Load the domain provider from the configured Copilot installation."""
from importlib import import_module
from functools import lru_cache
import os

from .config import DATA, RAG, LOCALE, PLUGIN
from .copilot import get_runtime


@lru_cache(maxsize=1)
def get_plugin():
    if PLUGIN != "construct3":
        raise ValueError("This host supports the construct3 provider")
    runtime = get_runtime()
    provider = import_module("copilot.providers.construct3")
    options = {"quick": os.environ.get("C3BOT_QUICK") == "1",
               "editor_check": os.environ.get("C3BOT_EDITOR_CHECK", "1") != "0",
               "template_copy": os.environ.get("C3BOT_TEMPLATE_COPY") == "1",
               "profile": os.environ.get("C3BOT_PROFILE"), "examples": os.environ.get("C3_EXAMPLES")}
    return provider.load(runtime, data_dir=DATA, rag=RAG, locale=LOCALE, source="qqbot", options=options)
