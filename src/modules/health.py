"""Module health checker — probes all downstream services."""
import logging
from typing import List

from src.llm.client import LLMClient
from src.modules.rag_client import RAGClient
from src.modules.clipboard_client import ClipboardClient
from src.modules.mcp_bridge import MCPBridge
from src.orchestrator.degradation import ModuleStatus
from src.schemas.api import ModuleHealth

logger = logging.getLogger(__name__)


class HealthChecker:

    def __init__(
        self,
        llm: LLMClient,
        rag: RAGClient,
        clipboard: ClipboardClient,
        mcp: MCPBridge,
    ):
        self.llm = llm
        self.rag = rag
        self.clipboard = clipboard
        self.mcp = mcp

    async def check_all(self) -> tuple[List[ModuleHealth], ModuleStatus]:
        """Check all modules and return health list + status flags."""
        results: List[ModuleHealth] = []
        status = ModuleStatus()

        # LLM
        ok, detail = await self.llm.check_health()
        status.llm = ok
        results.append(ModuleHealth(name="llm", available=ok, detail=detail))

        # RAG
        try:
            rag_ok = await self.rag.is_available()
            status.rag = rag_ok
            results.append(ModuleHealth(
                name="rag", available=rag_ok,
                detail="RAG online" if rag_ok else "RAG offline",
            ))
        except Exception as e:
            results.append(ModuleHealth(name="rag", available=False, detail=str(e)))

        # Clipboard
        try:
            clip_ok = await self.clipboard.is_available()
            status.clipboard = clip_ok
            results.append(ModuleHealth(
                name="clipboard", available=clip_ok,
                detail="Clipboard online" if clip_ok else "Clipboard offline",
            ))
        except Exception as e:
            results.append(ModuleHealth(name="clipboard", available=False, detail=str(e)))

        # MCP
        mcp_ok = await self.mcp.is_available()
        status.mcp = mcp_ok
        results.append(ModuleHealth(
            name="mcp", available=mcp_ok,
            detail="MCP online" if mcp_ok else "MCP offline (Phase 2)",
        ))

        return results, status
