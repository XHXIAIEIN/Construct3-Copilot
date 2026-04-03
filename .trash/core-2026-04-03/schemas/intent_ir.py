"""Intent IR — intermediate representation of user intent.

This is the contract between Copilot Core (LLM-powered semantic understanding)
and Clipboard service (deterministic JSON generation).
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class BehaviorRef(BaseModel):
    """Reference to a behavior attached to an object."""
    object: str
    type: str  # e.g. "Platform", "8Direction"


class EventParam(BaseModel):
    """A single parameter in a condition or action."""
    name: str
    value: str


class EventNode(BaseModel):
    """A condition or action in an event."""
    ace_id: str  # e.g. "on-start-of-layout", "set-position"
    object_class: str
    behavior_type: Optional[str] = None
    parameters: List[EventParam] = Field(default_factory=list)


class EventBlock(BaseModel):
    """A single event block: conditions → actions."""
    conditions: List[EventNode] = Field(default_factory=list)
    actions: List[EventNode] = Field(default_factory=list)
    children: List["EventBlock"] = Field(default_factory=list)


class IntentIR(BaseModel):
    """Structured representation of the user's game development intent."""
    type: str  # "event_sheet" | "object_types" | "layout" | "mixed"
    description: str
    objects: List[str] = Field(default_factory=list)
    behaviors: List[BehaviorRef] = Field(default_factory=list)
    events: List[EventBlock] = Field(default_factory=list)
    variables: List[dict] = Field(default_factory=list)
