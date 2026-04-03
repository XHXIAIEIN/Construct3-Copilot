"""Claude provider — Anthropic SDK."""
import logging
from typing import AsyncIterator, List, Dict

from src.llm.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    def _split_system(self, messages: List[Dict[str, str]]) -> tuple[str, list]:
        """Extract system message (Anthropic uses a separate param)."""
        system = ""
        chat_msgs = []
        for m in messages:
            if m["role"] == "system":
                system = m["content"]
            else:
                chat_msgs.append(m)
        return system, chat_msgs

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        system, chat_msgs = self._split_system(messages)
        kwargs = {"model": self.model, "max_tokens": 4096, "messages": chat_msgs}
        if system:
            kwargs["system"] = system
        response = await self.client.messages.create(**kwargs)
        return response.content[0].text

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        system, chat_msgs = self._split_system(messages)
        kwargs = {"model": self.model, "max_tokens": 4096, "messages": chat_msgs}
        if system:
            kwargs["system"] = system
        async with self.client.messages.stream(**kwargs) as s:
            async for text in s.text_stream:
                yield text

    async def check_health(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "ANTHROPIC_API_KEY not set"
        try:
            # Minimal call to verify connectivity
            await self.client.messages.create(
                model=self.model, max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True, f"Claude ({self.model}) OK"
        except Exception as e:
            return False, f"Claude error: {e}"
