"""Ollama provider — local model inference."""
import logging
from typing import AsyncIterator, List, Dict

from src.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):

    def __init__(self, model: str, base_url: str = DEFAULT_OLLAMA_URL):
        self.model = model
        self.base_url = base_url
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from ollama import AsyncClient
            self._client = AsyncClient(host=self.base_url)
        return self._client

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        response = await self.client.chat(model=self.model, messages=messages)
        return response["message"]["content"]

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        response = await self.client.chat(
            model=self.model, messages=messages, stream=True,
        )
        async for chunk in response:
            if "message" in chunk and "content" in chunk["message"]:
                yield chunk["message"]["content"]

    async def check_health(self) -> tuple[bool, str]:
        try:
            await self.client.list()
            return True, f"Ollama ({self.model}) OK"
        except Exception as e:
            return False, f"Ollama error: {e}"
