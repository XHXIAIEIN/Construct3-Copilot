"""Data models for the Copilot pipeline."""
from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class CopilotResponse:
    """Response from the Copilot pipeline."""
    answer: str
    sources: List[Dict[str, Any]]
    query_type: str  # "qa" | "code" | "lookup"
    confidence: str = "unknown"  # high | medium | low
    verification_notes: str = ""
    route: str = ""  # RAG route: "lookup" | "semantic" | etc.
    trace: list = field(default_factory=list)
