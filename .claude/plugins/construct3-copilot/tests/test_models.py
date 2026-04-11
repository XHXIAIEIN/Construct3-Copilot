"""Tests for clipboard JSON Pydantic models."""
import sys
from pathlib import Path
import pytest

# Allow importing from scripts/generate
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "generate"))

from models import ClipboardData, EventItem, ACERef


def test_valid_events_clipboard():
    data = {
        "is-c3-clipboard-data": True,
        "type": "events",
        "items": [
            {
                "eventType": "block",
                "conditions": [{"type": "sprite", "id": "on-created", "parameters": {}}],
                "actions": [{"type": "sprite", "id": "set-position", "parameters": {"0": "100", "1": "200"}}],
            }
        ],
    }
    clip = ClipboardData(**data)
    assert clip.type == "events"
    assert clip.is_c3_clipboard_data is True
    assert len(clip.items) == 1


def test_missing_clipboard_flag():
    data = {"type": "events", "items": []}
    with pytest.raises(Exception):
        ClipboardData(**data)


def test_invalid_type():
    data = {"is-c3-clipboard-data": True, "type": "bananas", "items": []}
    with pytest.raises(Exception):
        ClipboardData(**data)


def test_false_clipboard_flag():
    data = {"is-c3-clipboard-data": False, "type": "events", "items": []}
    with pytest.raises(Exception):
        ClipboardData(**data)


def test_event_item_valid_types():
    for t in ("block", "comment", "variable", "group", "function-block"):
        item = EventItem(eventType=t)
        assert item.eventType == t


def test_event_item_invalid_type():
    with pytest.raises(Exception):
        EventItem(eventType="invalid-type")


def test_ace_ref_basic():
    ref = ACERef(type="sprite", id="set-position", parameters={"0": "100"})
    assert ref.type == "sprite"
    assert ref.id == "set-position"


def test_ace_ref_with_behavior():
    ref = ACERef(type="sprite", id="set-speed", behaviorType="8Direction")
    assert ref.behaviorType == "8Direction"


def test_all_valid_clipboard_types():
    for t in ("events", "conditions", "actions", "object-types", "world-instances", "layouts", "event-sheets"):
        clip = ClipboardData(**{"is-c3-clipboard-data": True, "type": t, "items": []})
        assert clip.type == t
