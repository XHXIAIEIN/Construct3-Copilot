"""Degradation strategy — graceful fallback when modules are unavailable."""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModuleStatus:
    rag: bool = False
    clipboard: bool = False
    mcp: bool = False
    llm: bool = False


def assess_capabilities(status: ModuleStatus) -> dict:
    """Return what the system can and cannot do given current module status.

    Degradation table from spec:
    - RAG down     → skip knowledge retrieval, rely on LLM knowledge
    - Clipboard down → cannot generate clipboard JSON, suggest MCP
    - MCP down     → cannot direct-write, fall back to clipboard
    - LLM down     → service unavailable
    - All down     → return error
    """
    if not status.llm:
        return {
            "operational": False,
            "reason": "LLM service unavailable",
            "can_chat": False,
            "can_generate": False,
        }

    can_generate_clipboard = status.clipboard
    can_generate_mcp = status.mcp

    return {
        "operational": True,
        "can_chat": True,
        "can_search": status.rag,
        "can_generate": can_generate_clipboard or can_generate_mcp,
        "can_clipboard": can_generate_clipboard,
        "can_mcp": can_generate_mcp,
        "warnings": _build_warnings(status),
    }


def _build_warnings(status: ModuleStatus) -> list[str]:
    warnings = []
    if not status.rag:
        warnings.append("RAG offline — using LLM knowledge only, accuracy may be reduced")
    if not status.clipboard:
        warnings.append("Clipboard service offline — cannot generate clipboard JSON")
    if not status.mcp:
        warnings.append("construct3-mcp offline — cannot direct-write to project")
    return warnings
