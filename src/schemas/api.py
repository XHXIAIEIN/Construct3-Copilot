"""API request/response models for Copilot Core."""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    """Optional context about the user's local project."""
    has_local_project: bool = False
    project_path: Optional[str] = None


class ChatRequest(BaseModel):
    """POST /chat request body."""
    session_id: Optional[str] = None
    message: str
    context: ChatContext = Field(default_factory=ChatContext)


class GenerationData(BaseModel):
    """Data payload when type=generation."""
    delivery: Literal["clipboard", "mcp"]
    clipboard_json: Optional[dict] = None
    validation: Optional[dict] = None
    input_validation: Optional[dict] = None
    metadata: Optional[dict] = None


class ChatResponse(BaseModel):
    """POST /chat response body."""
    session_id: str
    type: Literal["clarification", "generation", "direct_answer", "error"]
    message: str
    data: Optional[GenerationData] = None
    modules_used: List[str] = Field(default_factory=list)


class ModuleHealth(BaseModel):
    """Health status of a single module."""
    name: str
    available: bool
    detail: str = ""


class HealthResponse(BaseModel):
    """GET /health response body."""
    status: Literal["ok", "degraded", "error"]
    version: str
    modules: List[ModuleHealth] = Field(default_factory=list)
