"""Output router — decides delivery method based on context."""
import logging
from typing import Literal

from src.schemas.session import SessionState

logger = logging.getLogger(__name__)


def decide_delivery(session: SessionState) -> Literal["clipboard", "mcp"]:
    """Determine output route based on session context.

    Rules from spec:
    - has_local_project=true → construct3-mcp direct write
    - has_local_project=false → Clipboard JSON generation
    """
    if session.has_local_project and session.project_path:
        return "mcp"
    return "clipboard"
