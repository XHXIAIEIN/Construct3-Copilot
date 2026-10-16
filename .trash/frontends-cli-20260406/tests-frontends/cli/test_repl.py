"""Tests for REPL message handling logic."""
import json
import pytest
from unittest.mock import AsyncMock, patch
from io import StringIO
from rich.console import Console

from frontends.cli.app import CopilotApp
from frontends.cli.repl import handle_message


@pytest.fixture
def app():
    return CopilotApp(host="localhost", port=8767)


@pytest.fixture
def console():
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=80), buf


class TestHandleMessageNonStreaming:
    @pytest.mark.asyncio
    async def test_direct_answer(self, app, console):
        con, buf = console
        app.stream_enabled = False
        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "direct_answer",
            "message": "This is the **answer**.",
            "modules_used": ["rag"],
        })
        await handle_message(app, "how do I use Platform?", console=con)
        output = buf.getvalue()
        assert "answer" in output
        assert app.session_id == "s1"
        assert app.turn_count == 1

    @pytest.mark.asyncio
    async def test_generation_copies_to_clipboard(self, app, console):
        con, buf = console
        app.stream_enabled = False
        clipboard_data = {"c3type": "events", "items": []}
        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "generation",
            "message": "Here's your event sheet.",
            "data": {
                "delivery": "clipboard",
                "clipboard_json": clipboard_data,
            },
            "modules_used": ["llm"],
        })
        with patch("frontends.cli.repl.copy_json", return_value=True) as mock_copy:
            await handle_message(app, '{"c3type":"events"} add collision', console=con)
            mock_copy.assert_called_once_with(clipboard_data)

    @pytest.mark.asyncio
    async def test_error_response(self, app, console):
        con, buf = console
        app.stream_enabled = False
        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "error",
            "message": "LLM error: timeout",
            "modules_used": [],
        })
        await handle_message(app, "do something", console=con)
        output = buf.getvalue()
        assert "error" in output.lower() or "LLM" in output

    @pytest.mark.asyncio
    async def test_connection_error(self, app, console):
        con, buf = console
        app.stream_enabled = False
        app.client.chat = AsyncMock(side_effect=Exception("Connection refused"))
        await handle_message(app, "hello", console=con)
        output = buf.getvalue()
        assert len(output) > 0


class TestHandleMessageStreaming:
    @pytest.mark.asyncio
    async def test_stream_tokens(self, app, console):
        con, buf = console
        app.stream_enabled = True

        async def fake_stream(*args, **kwargs):
            for token in ["Hello", " ", "world"]:
                yield token

        app.client.chat_stream = fake_stream
        await handle_message(app, "hi", console=con)
        output = buf.getvalue()
        assert "Hello" in output
        assert "world" in output

    @pytest.mark.asyncio
    async def test_stream_json_fallback(self, app, console):
        con, buf = console
        app.stream_enabled = True
        response_dict = {
            "session_id": "s1",
            "type": "generation",
            "message": "Generated.",
            "data": {"delivery": "clipboard", "clipboard_json": {"c3type": "events"}},
            "modules_used": ["llm"],
        }

        async def fake_stream(*args, **kwargs):
            yield response_dict

        app.client.chat_stream = fake_stream
        with patch("frontends.cli.repl.copy_json", return_value=True):
            await handle_message(app, '{"c3type":"events"}', console=con)
        assert app.session_id == "s1"
