"""Adapt Copilot's Construct provider to the QQ bot host."""
from importlib import import_module
from pathlib import Path


def create_application(*, home, data_dir, settings):
    from .runtime import get_runtime
    from qqbot.model_client import create_client
    from openai import BadRequestError
    from qqbot import usage
    from qqbot.config import MODEL, NO_THINK, TIMEOUT
    runtime = get_runtime(home=home, data_dir=data_dir, settings=settings)
    provider = import_module("copilot.providers.construct3")
    options = {"quick": settings.get("C3BOT_QUICK") == "1",
               "editor_check": settings.get("C3BOT_EDITOR_CHECK", "1") != "0",
               "template_copy": settings.get("C3BOT_TEMPLATE_COPY") == "1",
               "profile": settings.get("C3BOT_PROFILE"), "examples": settings.get("C3_EXAMPLES")}
    rag = Path(settings.get("CONSTRUCT3_RAG") or home.parent / "Construct3-RAG")
    provider.load(runtime, data_dir=data_dir, rag=rag, locale=settings.get("C3BOT_LOCALE", "zh-CN"),
                         source="qqbot", options=options)

    module = import_module("copilot.providers.construct3.application")
    return module.Application(create_client(), model=MODEL, request_options=NO_THINK, timeout=TIMEOUT, usage=usage, bad_request_error=BadRequestError)
