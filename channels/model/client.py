"""Create the configured model client: every call waits for a TTS server sharing the GPU and is counted."""
from openai import OpenAI

from . import gpu_yield
from .settings import ModelSettings, api_key


def create_client(model: ModelSettings, settings: dict, usage):
    key = api_key(model, settings)
    if not key:
        raise ValueError("Configure a model API key in .env")
    if model.protocol == "anthropic":
        from .anthropic_client import AnthropicClient
        client = AnthropicClient(api_key=key, base_url=model.base_url)
    else:
        client = OpenAI(api_key=key, base_url=model.base_url, max_retries=10 if model.zhipu else 2)
    create = client.chat.completions.create

    def counted(*args, **kwargs):
        if model.local:
            gpu_yield.wait_for_tts(model.base_url, model.model, model.yield_logs)
        response = create(*args, **kwargs)
        usage.count(response)
        return response

    client.chat.completions.create = counted
    return client
