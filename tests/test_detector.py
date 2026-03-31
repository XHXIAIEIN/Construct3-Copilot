"""Tests for clipboard JSON detection in user messages."""
import pytest
from src.orchestrator.detector import detect_clipboard_json, DetectionResult


class TestDetectClipboardJson:
    """Test clipboard JSON detection from user messages."""

    def test_plain_text_no_json(self):
        result = detect_clipboard_json("Sprite 的 Set animation 怎么用？")
        assert result.found is False
        assert result.clipboard_json is None
        assert result.clipboard_type is None
        assert result.user_instruction == "Sprite 的 Set animation 怎么用？"

    def test_pure_clipboard_json(self):
        msg = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert result.clipboard_json == {"is-c3-clipboard-data": True, "type": "events", "items": []}
        assert result.clipboard_type == "events"
        assert result.user_instruction.strip() == ""

    def test_json_with_instruction(self):
        msg = '帮我看看这段 JSON 有什么问题：\n{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert result.clipboard_type == "events"
        assert "帮我看看" in result.user_instruction

    def test_json_in_code_block(self):
        msg = '检查一下：\n```json\n{"is-c3-clipboard-data":true,"type":"object-types","items":[]}\n```'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert result.clipboard_type == "object-types"

    def test_non_clipboard_json(self):
        msg = '{"name": "test", "value": 42}'
        result = detect_clipboard_json(msg)
        assert result.found is False

    def test_invalid_json_syntax(self):
        msg = '{"is-c3-clipboard-data":true, broken}'
        result = detect_clipboard_json(msg)
        assert result.found is False

    def test_multiple_json_blocks_picks_clipboard(self):
        msg = '第一个：{"foo":1}\n第二个：{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert result.clipboard_type == "events"

    def test_preserves_raw_json_str(self):
        json_str = '{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        msg = f"看看这个：{json_str}"
        result = detect_clipboard_json(msg)
        assert result.raw_json_str is not None
        assert "is-c3-clipboard-data" in result.raw_json_str

    def test_nested_json_with_events(self):
        msg = '{"is-c3-clipboard-data":true,"type":"events","items":[{"eventType":"block","conditions":[{"id":"on-start-of-layout","objectClass":"System","parameters":{}}],"actions":[]}]}'
        result = detect_clipboard_json(msg)
        assert result.found is True
        assert len(result.clipboard_json["items"]) == 1
