"""OpenAI-compatible provider — works with OpenAI, DeepSeek, Kimi, etc."""
import logging
from typing import AsyncIterator, List, Dict

from src.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):

    def __init__(self, model: str, base_url: str, api_key: str):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key)
        return self._client

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages,
        )
        return response.choices[0].message.content

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True,
        )
        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def check_health(self) -> tuple[bool, str]:
        try:
            await self.client.models.list()
            return True, f"OpenAI-compatible ({self.model}) OK"
        except Exception as e:
            return False, f"OpenAI error: {e}"
