"""The one place that wires the channels to Copilot: channels.model makes the model client, Copilot makes the
Construct application around it. Every other module under channels/ works with any object that has
handle(request), and none of them imports copilot."""
from __future__ import annotations

import sys
from pathlib import Path

from .model import settings as model_settings
from .model.client import create_client
from .model.usage import Usage
from .settings import REPO


def create_application(*, settings: dict, data_dir: Path):
    from openai import BadRequestError
    from copilot import Runtime
    from copilot.providers import construct3 as provider
    from copilot.providers.construct3.application import Application

    # trusted local checkouts; default: sibling folders of this Copilot checkout
    skills = Path(settings.get("C3BOT_SKILLS") or settings.get("CONSTRUCT3_AGENT_SKILLS")
                  or REPO.parent / "Construct3-Agent-Skills")
    rag = Path(settings.get("CONSTRUCT3_RAG") or REPO.parent / "Construct3-RAG")
    runtime = Runtime(skills_root=skills, data_dir=data_dir / "copilot", python_executable=sys.executable)
    options = {"quick": settings.get("C3BOT_QUICK") == "1",
               "editor_check": settings.get("C3BOT_EDITOR_CHECK", "1") != "0",
               "template_copy": settings.get("C3BOT_TEMPLATE_COPY") == "1",
               "profile": settings.get("C3BOT_PROFILE"), "examples": settings.get("C3_EXAMPLES")}
    provider.load(runtime, data_dir=data_dir, rag=rag, locale=settings.get("C3BOT_LOCALE", "zh-CN"),
                  source="qqbot", options=options)

    model = model_settings.from_settings(settings)
    usage = Usage(data_dir)
    return Application(create_client(model, settings, usage), model=model.model, request_options=model.request_options,
                       timeout=model.timeout, usage=usage, bad_request_error=BadRequestError)
