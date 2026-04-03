"""
MCP Bridge — stub for construct3-mcp integration.

construct3-mcp (by liauw-media) provides direct project file operations
via MCP stdio protocol. This bridge will wrap those calls for the pipeline.

Phase 1: interface only, no implementation.
Phase 2: full MCP client integration.
"""
import logging

logger = logging.getLogger(__name__)


class MCPBridge:
    """Bridge to construct3-mcp for direct project operations."""

    def __init__(self):
        self._available = False

    async def is_available(self) -> bool:
        # Phase 1: always unavailable (MCP integration comes in Phase 2)
        return self._available

    async def execute(self, intent_ir: dict, project_path: str) -> dict:
        """Execute IR against a local C3 project via MCP.

        Phase 1: raises NotImplementedError.
        """
        raise NotImplementedError("MCP bridge not yet implemented (Phase 2)")
