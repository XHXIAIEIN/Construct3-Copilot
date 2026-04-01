"""Tests for display module — rich rendering functions."""
import json
import pytest
from io import StringIO
from rich.console import Console

from frontends.cli.display import (
    render_markdown,
    render_json,
    render_health,
    print_status,
    print_welcome,
)


@pytest.fixture
def capture_console():
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=80)
    return console, buf


class TestRenderMarkdown:
    def test_renders_markdown_text(self, capture_console):
        console, buf = capture_console
        render_markdown("**bold** and *italic*", console=console)
        output = buf.getvalue()
        assert "bold" in output

    def test_handles_empty_string(self, capture_console):
        console, buf = capture_console
        render_markdown("", console=console)


class TestRenderJson:
    def test_renders_json_with_syntax_highlighting(self, capture_console):
        console, buf = capture_console
        render_json({"key": "value"}, console=console)
        output = buf.getvalue()
        assert "key" in output
        assert "value" in output


class TestRenderHealth:
    def test_renders_health_table(self, capture_console):
        console, buf = capture_console
        modules = [
            {"name": "llm", "available": True, "detail": "claude"},
            {"name": "rag", "available": False, "detail": "unreachable"},
        ]
        render_health(status="degraded", version="2.0.0", modules=modules, console=console)
        output = buf.getvalue()
        assert "llm" in output
        assert "rag" in output


class TestPrintStatus:
    def test_success_style(self, capture_console):
        console, buf = capture_console
        print_status("Done!", style="success", console=console)
        output = buf.getvalue()
        assert "Done!" in output

    def test_error_style(self, capture_console):
        console, buf = capture_console
        print_status("Failed", style="error", console=console)
        output = buf.getvalue()
        assert "Failed" in output


class TestPrintWelcome:
    def test_welcome_with_project(self, capture_console):
        console, buf = capture_console
        print_welcome(version="0.1.0", core_ok=True, project_name="MyGame", console=console)
        output = buf.getvalue()
        assert "MyGame" in output
        assert "0.1.0" in output

    def test_welcome_without_project(self, capture_console):
        console, buf = capture_console
        print_welcome(version="0.1.0", core_ok=False, project_name=None, console=console)
        output = buf.getvalue()
        assert "0.1.0" in output
