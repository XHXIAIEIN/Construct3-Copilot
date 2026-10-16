"""Create the configured model client for applications that request one."""
import os
from urllib.parse import urlsplit
from openai import OpenAI

from . import usage, gpu_yield
from .config import BASE_URL, LOCAL, MODEL, ZHIPU


def create_client():
    reference = os.environ.get("C3BOT_API_KEY_ENV")
    key = os.environ.get(reference) if reference else os.environ.get("C3BOT_API_KEY") or os.environ.get("QQBOT_API_KEY")
    if not key:
        key = (os.environ.get("ZHIPU_API_KEY") if ZHIPU else
               os.environ.get("SILICONFLOW_API_KEY") if "siliconflow" in BASE_URL else
               "ollama" if LOCAL else os.environ.get("DEEPSEEK_API_KEY"))
    if not key:
        raise ValueError("Configure a model API key in .env")
    protocol = os.environ.get("C3BOT_API_PROTOCOL", "auto")
    if protocol == "anthropic" or (protocol == "auto" and urlsplit(BASE_URL).hostname == "api.anthropic.com"):
        from .anthropic_client import AnthropicClient
        client = AnthropicClient(api_key=key, base_url=BASE_URL)
    else:
        client = OpenAI(api_key=key, base_url=BASE_URL, max_retries=10 if ZHIPU else 2)
    create = client.chat.completions.create

    def counted(*args, **kwargs):
        if LOCAL:
            gpu_yield.wait_for_tts(BASE_URL, MODEL)
        response = create(*args, **kwargs)
        usage.count(response)
        return response

    client.chat.completions.create = counted
    return client
