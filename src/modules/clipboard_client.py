"""
Async HTTP client for the Construct 3 Clipboard service.

Clipboard service handles deterministic C3 JSON generation from Intent IR.
It runs on a separate repo/service (Construct3-Clipboard :8766).
"""
import logging
from typing import Optional

import httpx

from src.config import CLIPBOARD_API_URL

logger = logging.getLogger(__name__)

_TIMEOUT = 60.0  # generation can take a moment


class ClipboardClient:

    def __init__(self, base_url: str = CLIPBOARD_API_URL):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=_TIMEOUT,
            )
        return self._client

    async def health(self) -> dict:
        resp = await self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def generate(self, intent_ir: dict, ace_context: dict = None, options: dict = None) -> dict:
        """Call Clipboard /generate to produce C3 clipboard JSON from IR."""
        payload = {"intent_ir": intent_ir}
        if ace_context:
            payload["ace_context"] = ace_context
        if options:
            payload["options"] = options

        resp = await self.client.post("/generate", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def validate(self, json_data: dict) -> dict:
        """Call Clipboard /validate to check existing JSON."""
        resp = await self.client.post("/validate", json=json_data)
        resp.raise_for_status()
        return resp.json()

    async def is_available(self) -> bool:
        try:
            await self.health()
            return True
        except Exception:
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
