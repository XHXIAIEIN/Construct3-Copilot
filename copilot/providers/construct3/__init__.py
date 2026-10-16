"""Construct tools, generation and project edits for a Copilot host."""
from importlib import import_module
from . import services


def load(runtime, *, data_dir, rag, locale="zh-CN", source="local", options=None):
    """Bind one host before loading the provider's tools and prompts."""
    services.configure(runtime, data_dir=data_dir, rag=rag, locale=locale, source=source, options=options)
    return import_module(__name__ + ".plugin")
