"""
LLM Client — async unified interface for language model inference.

Supports three providers:
- claude:  Anthropic Claude API (default)
- openai:  OpenAI-compatible API (OpenAI, DeepSeek, Kimi, etc.)
- ollama:  Local Ollama service
"""
import logging
from typing import AsyncIterator, List, Dict

from src.llm.providers.base import LLMProvider
from src.llm.providers.claude import ClaudeProvider
from src.llm.providers.openai import OpenAIProvider
from src.llm.providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)


class LLMClient:

    def __init__(
        self,
        provider: str = "claude",
        model: str = "",
        base_url: str = "",
        api_key: str = "",
        anthropic_api_key: str = "",
    ):
        self.provider_name = provider
        self._provider: LLMProvider = self._create_provider(
            provider, model, base_url, api_key, anthropic_api_key,
        )

    @staticmethod
    def _create_provider(
        provider: str, model: str, base_url: str,
        api_key: str, anthropic_api_key: str,
    ) -> LLMProvider:
        if provider == "claude":
            return ClaudeProvider(
                model=model or "claude-sonnet-4-20250514",
                api_key=anthropic_api_key,
            )
        elif provider == "ollama":
            return OllamaProvider(
                model=model or "qwen2.5:7b",
                base_url=base_url or "http://localhost:11434",
            )
        else:  # openai-compatible
            return OpenAIProvider(
                model=model or "gpt-4o",
                base_url=base_url or "https://api.openai.com/v1",
                api_key=api_key,
            )

    @classmethod
    def from_config(cls) -> "LLMClient":
        """Create client from environment / config.py settings."""
        from src.config import (
            LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL,
            LLM_API_KEY, ANTHROPIC_API_KEY,
        )
        return cls(
            provider=LLM_PROVIDER,
            model=LLM_MODEL,
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            anthropic_api_key=ANTHROPIC_API_KEY,
        )

    # ── Public API ───────────────────────────────────────────────────────

    async def chat(self, messages: List[Dict[str, str]]) -> str:
        return await self._provider.chat(messages)

    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        async for token in self._provider.stream(messages):
            yield token

    async def generate(self, prompt: str, system: str = "") -> str:
        """Single-turn convenience method."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages)

    async def check_health(self) -> tuple[bool, str]:
        return await self._provider.check_health()

    @property
    def is_available(self) -> bool:
        """Synchronous availability flag — call check_health() to refresh."""
        # This is a quick check; for actual status, use await check_health()
        return self._provider is not None
