"""Pydantic models for Construct 3 clipboard JSON — local pre-validation.

These mirror the constants from Construct3-Clipboard's structural.py
so we can catch basic errors without hitting the remote service.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, model_validator

VALID_CLIPBOARD_TYPES = {
    "events", "conditions", "actions",
    "object-types", "world-instances", "layouts", "event-sheets",
}
VALID_EVENT_TYPES = {"comment", "variable", "group", "block", "function-block"}
VALID_VARIABLE_TYPES = {"number", "string", "boolean"}


class ACERef(BaseModel):
    """An action, condition, or expression reference."""
    type: str
    id: str
    parameters: dict[str, Any] | None = None
    behaviorType: str | None = None

    model_config = {"extra": "allow"}


class EventItem(BaseModel):
    """One event block / comment / variable / group / function-block."""
    eventType: str

    conditions: list[ACERef] | None = None
    actions: list[ACERef] | None = None
    children: list[EventItem] | None = None

    name: str | None = None
    type: str | None = None
    initialValue: Any = None
    comment: str | None = None

    model_config = {"extra": "allow"}

    @model_validator(mode="after")
    def _check_event_type(self):
        if self.eventType not in VALID_EVENT_TYPES:
            raise ValueError(
                f"eventType '{self.eventType}' not in {sorted(VALID_EVENT_TYPES)}"
            )
        return self


class ClipboardData(BaseModel):
    """Top-level Construct 3 clipboard JSON structure."""
    is_c3_clipboard_data: bool = Field(alias="is-c3-clipboard-data")
    type: str
    items: list[dict[str, Any]] = []

    model_config = {"extra": "allow", "populate_by_name": True}

    @model_validator(mode="after")
    def _check_header(self):
        if not self.is_c3_clipboard_data:
            raise ValueError("'is-c3-clipboard-data' must be true")
        if self.type not in VALID_CLIPBOARD_TYPES:
            raise ValueError(
                f"type '{self.type}' not in {sorted(VALID_CLIPBOARD_TYPES)}"
            )
        return self
