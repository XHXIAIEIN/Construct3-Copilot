"""Tests for slash command dispatch."""
import pytest
from unittest.mock import AsyncMock
from io import StringIO
from rich.console import Console

from frontends.cli.commands import dispatch_command, COMMANDS
from frontends.cli.app import CopilotApp


@pytest.fixture
def app():
    return CopilotApp(host="localhost", port=8767)


@pytest.fixture
def console():
    buf = StringIO()
    return Console(file=buf, force_terminal=True, width=80), buf


class TestDispatch:
    @pytest.mark.asyncio
    async def test_help_command(self, app, console):
        con, buf = console
        await dispatch_command(app, "/help", console=con)
        output = buf.getvalue()
        assert "/help" in output
        assert "/health" in output

    @pytest.mark.asyncio
    async def test_unknown_command(self, app, console):
        con, buf = console
        await dispatch_command(app, "/foobar", console=con)
        output = buf.getvalue()
        assert "/help" in output

    @pytest.mark.asyncio
    async def test_health_command(self, app, console):
        con, buf = console
        app.client.health = AsyncMock(return_value={
            "status": "ok",
            "version": "2.0.0",
            "modules": [{"name": "llm", "available": True, "detail": "claude"}],
        })
        await dispatch_command(app, "/health", console=con)
        output = buf.getvalue()
        assert "llm" in output

    @pytest.mark.asyncio
    async def test_health_command_core_down(self, app, console):
        con, buf = console
        app.client.health = AsyncMock(side_effect=Exception("Connection refused"))
        await dispatch_command(app, "/health", console=con)
        output = buf.getvalue()
        assert len(output) > 0

    @pytest.mark.asyncio
    async def test_session_command(self, app, console):
        con, buf = console
        app.session_id = "test-123"
        app.turn_count = 5
        app.project_name = "MyGame"
        await dispatch_command(app, "/session", console=con)
        output = buf.getvalue()
        assert "test-123" in output

    @pytest.mark.asyncio
    async def test_clear_resets_session(self, app, console):
        con, buf = console
        app.session_id = "old-session"
        app.turn_count = 3
        app.client.delete_session = AsyncMock(return_value=True)
        await dispatch_command(app, "/clear", console=con)
        assert app.session_id is None
        assert app.turn_count == 0

    @pytest.mark.asyncio
    async def test_quit_raises_systemexit(self, app, console):
        con, buf = console
        with pytest.raises(SystemExit):
            await dispatch_command(app, "/quit", console=con)

    @pytest.mark.asyncio
    async def test_exit_alias(self, app, console):
        con, buf = console
        with pytest.raises(SystemExit):
            await dispatch_command(app, "/exit", console=con)


class TestCommandRegistry:
    def test_all_commands_registered(self):
        expected = {"/help", "/health", "/session", "/clear", "/new", "/quit", "/exit"}
        assert expected == set(COMMANDS.keys())
