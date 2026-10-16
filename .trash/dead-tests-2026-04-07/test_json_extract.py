"""Tests for JSON extraction from LLM replies."""
import pytest
from src.orchestrator.json_extract import extract_clipboard_json_from_reply


class TestExtractClipboardJsonFromReply:

    def test_json_in_code_block(self):
        reply = 'Here is the fix:\n```json\n{"is-c3-clipboard-data":true,"type":"events","items":[]}\n```\nDone.'
        result = extract_clipboard_json_from_reply(reply)
        assert result is not None
        assert result["is-c3-clipboard-data"] is True

    def test_no_json_in_reply(self):
        reply = "The JSON looks fine. No issues found."
        result = extract_clipboard_json_from_reply(reply)
        assert result is None

    def test_non_clipboard_json_ignored(self):
        reply = '```json\n{"foo": "bar"}\n```'
        result = extract_clipboard_json_from_reply(reply)
        assert result is None

    def test_multiple_code_blocks_picks_clipboard(self):
        reply = (
            '```json\n{"example": true}\n```\n'
            'And the fixed version:\n'
            '```json\n{"is-c3-clipboard-data":true,"type":"events","items":[]}\n```'
        )
        result = extract_clipboard_json_from_reply(reply)
        assert result is not None
        assert result["type"] == "events"

    def test_bare_json_without_code_block(self):
        reply = 'Fixed:\n{"is-c3-clipboard-data":true,"type":"events","items":[]}'
        result = extract_clipboard_json_from_reply(reply)
        assert result is not None
