"""Base class for LLM providers."""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict


class LLMProvider(ABC):
    """All providers implement async chat + stream + health check."""

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]]) -> str:
        """Send messages, return assistant reply text."""

    @abstractmethod
    async def stream(self, messages: List[Dict[str, str]]) -> AsyncIterator[str]:
        """Send messages, yield assistant reply tokens."""

    @abstractmethod
    async def check_health(self) -> tuple[bool, str]:
        """Return (ok, detail_message)."""
