"""Session data model — tracks multi-turn conversation state."""
import time
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

from src.schemas.intent_ir import IntentIR


class SessionState(BaseModel):
    """Persistent state for a single conversation session."""
    session_id: str
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    # Conversation history (LLM message format)
    messages: List[Dict[str, str]] = Field(default_factory=list)

    # Current intent being refined
    current_ir: Optional[IntentIR] = None

    # Pipeline stage: "idle" | "intent" | "clarify" | "refine" | "execute"
    stage: str = "idle"

    # Project context from the frontend
    has_local_project: bool = False
    project_path: Optional[str] = None

    def touch(self):
        self.updated_at = time.time()
