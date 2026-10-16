"""Tests for clipboard JSON validation."""
import json
from pathlib import Path

import pytest
from src.orchestrator.validator import (
    validate_local,
    ValidationReport,
    ValidationIssue,
)


class TestStructuralValidation:
    """Test Layer 1: structural format checks."""

    def test_valid_events_minimal(self):
        data = {"is-c3-clipboard-data": True, "type": "events", "items": []}
        report = validate_local(data)
        assert report.passed is True
        assert len([i for i in report.issues if i.level == "error"]) == 0

    def test_missing_clipboard_marker(self):
        data = {"type": "events", "items": []}
        report = validate_local(data)
        assert report.passed is False
        assert any(i.code == "MISSING_CLIPBOARD_MARKER" for i in report.issues)

    def test_invalid_type(self):
        data = {"is-c3-clipboard-data": True, "type": "invalid", "items": []}
        report = validate_local(data)
        assert report.passed is False
        assert any(i.code == "INVALID_TYPE" for i in report.issues)

    def test_missing_items(self):
        data = {"is-c3-clipboard-data": True, "type": "events"}
        report = validate_local(data)
        assert report.passed is False
        assert any(i.code == "MISSING_ITEMS" for i in report.issues)

    def test_valid_event_types(self):
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0", "comment": ""},
                {"eventType": "comment", "text": "Init"},
                {"eventType": "block", "conditions": [], "actions": []},
            ],
        }
        report = validate_local(data)
        assert report.passed is True

    def test_invalid_event_type(self):
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [{"eventType": "unknown"}],
        }
        report = validate_local(data)
        assert any(i.code == "INVALID_EVENT_TYPE" for i in report.issues)


class TestKnownPitfalls:
    """Test Layer 2: known C3 pitfalls."""

    def test_empty_parameters_object(self):
        """Empty parameters {} should be omitted entirely."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {
                    "eventType": "block",
                    "conditions": [
                        {"id": "on-start-of-layout", "objectClass": "System", "parameters": {}}
                    ],
                    "actions": [],
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "EMPTY_PARAMS" for i in report.issues)

    def test_variable_missing_comment(self):
        """Variable events must have a comment field."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {"eventType": "variable", "name": "Score", "type": "number", "initialValue": "0"}
            ],
        }
        report = validate_local(data)
        assert any(i.code == "VARIABLE_MISSING_COMMENT" for i in report.issues)

    def test_deprecated_behavior_id_solid(self):
        """Solid (uppercase) is V1, should be solid (lowercase)."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Wall",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [{"behaviorId": "Solid", "name": "Solid", "sid": 1}],
                    "instanceVariables": [],
                    "effectTypes": [],
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "DEPRECATED_BEHAVIOR_V1" for i in report.issues)

    def test_effect_types_as_object(self):
        """effectTypes must be array, not object with items/subfolders."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Player",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [],
                    "instanceVariables": [],
                    "effectTypes": {"items": [], "subfolders": []},
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "EFFECT_TYPES_NOT_ARRAY" for i in report.issues)

    def test_duplicate_sids(self):
        """SIDs must be unique across the entire JSON."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {
                    "eventType": "block",
                    "conditions": [{"id": "on-start-of-layout", "objectClass": "System", "sid": 100}],
                    "actions": [{"id": "wait", "objectClass": "System", "sid": 100}],
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "DUPLICATE_SID" for i in report.issues)

    def test_trigger_in_children(self):
        """Trigger conditions (on-*) cannot appear in children (sub-events)."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {
                    "eventType": "block",
                    "conditions": [{"id": "every-tick", "objectClass": "System"}],
                    "actions": [],
                    "children": [
                        {
                            "eventType": "block",
                            "conditions": [{"id": "on-start-of-layout", "objectClass": "System"}],
                            "actions": [],
                        }
                    ],
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "TRIGGER_IN_CHILDREN" for i in report.issues)

    def test_instance_variables_as_object(self):
        """instanceVariables must be array, not object."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Player",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [],
                    "instanceVariables": {"items": [], "subfolders": []},
                    "effectTypes": [],
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "INSTANCE_VARS_NOT_ARRAY" for i in report.issues)

    def test_multiple_triggers_in_block(self):
        """A single block can have at most one trigger condition."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "events",
            "items": [
                {
                    "eventType": "block",
                    "conditions": [
                        {"id": "on-start-of-layout", "objectClass": "System"},
                        {"id": "on-key-pressed", "objectClass": "Keyboard", "parameters": {"key": 32}},
                    ],
                    "actions": [],
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "MULTIPLE_TRIGGERS" for i in report.issues)

    def test_destroy_outside_layout_deprecated(self):
        """DestroyOutsideLayout behavior is removed in V2."""
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Bullet",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [{"behaviorId": "DestroyOutsideLayout", "name": "DOL", "sid": 1}],
                    "instanceVariables": [],
                    "effectTypes": [],
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "DEPRECATED_BEHAVIOR_REMOVED" for i in report.issues)

    def test_deprecated_behavior_id_scrollto(self):
        data = {
            "is-c3-clipboard-data": True,
            "type": "object-types",
            "items": [
                {
                    "name": "Camera",
                    "plugin-id": "Sprite",
                    "behaviorTypes": [{"behaviorId": "ScrollTo", "name": "ScrollTo", "sid": 1}],
                    "instanceVariables": [],
                    "effectTypes": [],
                    "animations": {"items": [{"frames": [{}], "sid": 1, "name": "Default"}], "subfolders": []},
                }
            ],
        }
        report = validate_local(data)
        assert any(i.code == "DEPRECATED_BEHAVIOR_V1" for i in report.issues)


FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXAMPLES_DIR = Path(__file__).parent / "examples"


class TestRealFixtures:
    """Validate real C3 clipboard JSON fixtures."""

    def test_events_basic_fixture(self):
        data = json.loads((FIXTURES_DIR / "events_basic.json").read_text())
        report = validate_local(data)
        # Known issue: events_basic.json has empty parameters {} on on-start-of-layout
        assert any(i.code == "EMPTY_PARAMS" for i in report.issues)

    def test_breakout_events(self):
        data = json.loads((EXAMPLES_DIR / "breakout_events.json").read_text())
        report = validate_local(data)
        assert isinstance(report.passed, bool)
        assert isinstance(report.issues, list)

    def test_platformer_events(self):
        data = json.loads((EXAMPLES_DIR / "platformer_events.json").read_text())
        report = validate_local(data)
        assert isinstance(report.passed, bool)

    def test_breakout_layout(self):
        data = json.loads((EXAMPLES_DIR / "breakout_layout.json").read_text())
        report = validate_local(data)
        assert isinstance(report.passed, bool)

    def test_platformer_layout(self):
        data = json.loads((EXAMPLES_DIR / "platformer_layout.json").read_text())
        report = validate_local(data)
        assert isinstance(report.passed, bool)
