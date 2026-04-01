"""Integration smoke test — full CLI flow with mocked Core."""
import json
import pytest
from unittest.mock import AsyncMock, patch
from io import StringIO
from rich.console import Console

from frontends.cli.app import CopilotApp
from frontends.cli.repl import handle_message
from frontends.cli.commands import dispatch_command


@pytest.fixture
def app():
    return CopilotApp(host="localhost", port=8767)


@pytest.fixture
def console():
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=80), buf


class TestFullFlow:
    @pytest.mark.asyncio
    async def test_qa_then_clear_then_qa(self, app, console):
        """Simulate: ask question → /clear → ask again."""
        con, buf = console
        app.stream_enabled = False

        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "direct_answer",
            "message": "Platform behavior docs...",
            "modules_used": ["rag"],
        })
        await handle_message(app, "how to add Platform?", console=con)
        assert app.session_id == "s1"
        assert app.turn_count == 1

        app.client.delete_session = AsyncMock(return_value=True)
        await dispatch_command(app, "/clear", console=con)
        assert app.session_id is None
        assert app.turn_count == 0

        app.client.chat = AsyncMock(return_value={
            "session_id": "s2",
            "type": "direct_answer",
            "message": "Solid behavior docs...",
            "modules_used": [],
        })
        await handle_message(app, "how to add Solid?", console=con)
        assert app.session_id == "s2"
        assert app.turn_count == 1

    @pytest.mark.asyncio
    async def test_json_generation_flow(self, app, console):
        """Simulate: paste JSON → get generation → clipboard copy."""
        con, buf = console
        app.stream_enabled = False
        clipboard_json = {"c3type": "events", "items": [{"type": "event"}]}

        app.client.chat = AsyncMock(return_value={
            "session_id": "s1",
            "type": "generation",
            "message": "Added collision event.",
            "data": {
                "delivery": "clipboard",
                "clipboard_json": clipboard_json,
            },
            "modules_used": ["llm", "rag"],
        })

        with patch("frontends.cli.repl.copy_json", return_value=True) as mock_copy:
            await handle_message(app, '{"c3type":"events"} add collision', console=con)
            mock_copy.assert_called_once_with(clipboard_json)

        output = buf.getvalue()
        assert "collision" in output.lower() or "已复制" in output
