"""
HTTP client for the Construct 3 RAG retrieval service.

All knowledge retrieval goes through this module — Copilot never
accesses Qdrant or embedding models directly.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from src.config import RAG_API_URL

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0  # seconds


@dataclass
class SearchResult:
    """A single result from the RAG search API."""
    text: str
    score: float
    collection: str
    source: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Full response from the RAG /search endpoint."""
    results: List[SearchResult]
    route: str  # "lookup" | "semantic" | "plugin_filter" | "collection_filter"
    total_candidates: int = 0
    after_rerank: int = 0
    after_threshold: int = 0
    latency_ms: float = 0.0
    lookup_detail: Optional[dict] = None


class RAGClient:
    """HTTP client for the RAG retrieval service."""

    def __init__(self, base_url: str = RAG_API_URL):
        self.base_url = base_url.rstrip("/")
        self._client = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=_TIMEOUT,
            )
        return self._client

    def health(self) -> dict:
        """Check RAG service health."""
        resp = self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def search(
        self,
        query: str,
        top_k: int = 10,
        collections: Optional[List[str]] = None,
        plugin: Optional[str] = None,
        section_types: Optional[List[str]] = None,
        apply_threshold: bool = True,
        skip_lookup: bool = False,
    ) -> SearchResponse:
        """
        Search for relevant documents via RAG API.

        Internally tries structured lookup first, then falls back
        to semantic search (unless skip_lookup=True).
        """
        payload: dict = {
            "query": query,
            "top_k": top_k,
            "apply_threshold": apply_threshold,
            "skip_lookup": skip_lookup,
        }
        if collections:
            payload["collections"] = collections
        if plugin:
            payload["plugin"] = plugin
        if section_types:
            payload["section_types"] = section_types

        resp = self.client.post("/search", json=payload)
        resp.raise_for_status()
        data = resp.json()

        diag = data.get("diagnostics", {})
        results = [
            SearchResult(
                text=r["text"],
                score=r["score"],
                collection=r["collection"],
                source=r["source"],
                metadata=r.get("metadata", {}),
            )
            for r in data.get("results", [])
        ]

        return SearchResponse(
            results=results,
            route=diag.get("route", "unknown"),
            total_candidates=diag.get("total_candidates", 0),
            after_rerank=diag.get("after_rerank", 0),
            after_threshold=diag.get("after_threshold", 0),
            latency_ms=diag.get("latency_ms", 0.0),
            lookup_detail=diag.get("lookup_detail"),
        )

    def is_available(self) -> bool:
        """Check if RAG service is reachable."""
        try:
            info = self.health()
            return info.get("qdrant", False)
        except Exception:
            return False

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
