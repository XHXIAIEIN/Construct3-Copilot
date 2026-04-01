"""Async HTTP client for Copilot Core API.

Follows the same lazy-init pattern as ClipboardClient in src/modules/.
"""
import json
from typing import AsyncIterator, Optional

import httpx


class CopilotClient:
    """HTTP wrapper for Copilot Core endpoints."""

    def __init__(self, base_url: str = "http://localhost:8767"):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-init httpx client. Recreates if closed."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url, timeout=120.0,
            )
        return self._client

    async def health(self) -> dict:
        """GET /health — returns parsed JSON."""
        resp = await self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def is_available(self) -> bool:
        """Check if Core is reachable."""
        try:
            await self.health()
            return True
        except Exception:
            return False

    async def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> dict:
        """POST /chat — synchronous chat, returns full response dict."""
        payload = {
            "message": message,
            "session_id": session_id,
            "context": context or {},
        }
        resp = await self.client.post("/chat", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> AsyncIterator:
        """POST /chat/stream — yields str tokens or dict (JSON track fallback).

        SSE format from Core:
        - Regular token: "data: <text>\\n\\n" → yield str
        - JSON fallback:  "data: {\\"session_id\\": ...}\\n\\n" → yield dict
        - End marker:     "data: [DONE]\\n\\n" → stop
        """
        payload = {
            "message": message,
            "session_id": session_id,
            "context": context or {},
        }
        resp = await self.client.post("/chat/stream", json=payload)
        resp.raise_for_status()
        for line in resp.text.split("\n"):
            line = line.strip()
            if not line.startswith("data: "):
                continue
            data = line[6:]  # strip "data: "
            if data == "[DONE]":
                return
            # Try JSON parse — if it looks like a full ChatResponse dict
            if data.startswith("{"):
                try:
                    parsed = json.loads(data)
                    if "session_id" in parsed:
                        yield parsed
                        continue
                except json.JSONDecodeError:
                    pass
            yield data

    async def get_session(self, session_id: str) -> dict:
        """GET /session/{id} — returns session state dict."""
        resp = await self.client.get(f"/session/{session_id}")
        resp.raise_for_status()
        return resp.json()

    async def delete_session(self, session_id: str) -> bool:
        """DELETE /session/{id} — returns True if deleted, False if not found."""
        resp = await self.client.delete(f"/session/{session_id}")
        if resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    async def close(self):
        """Close the underlying httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None
