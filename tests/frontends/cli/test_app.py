"""Tests for CopilotApp — application state container."""
import pytest
from pathlib import Path

from frontends.cli.app import CopilotApp


class TestInit:
    def test_default_state(self):
        app = CopilotApp(host="localhost", port=8767)
        assert app.session_id is None
        assert app.project_path is None
        assert app.project_name is None
        assert app.stream_enabled is True
        assert app.turn_count == 0
        assert app.client is not None

    def test_with_project(self, tmp_path):
        proj_file = tmp_path / "MyGame.c3proj"
        proj_file.write_text("{}")
        app = CopilotApp(host="localhost", port=8767, project_path=str(tmp_path))
        assert app.project_path == str(tmp_path)
        assert app.project_name == "MyGame"

    def test_with_invalid_project_path(self):
        app = CopilotApp(host="localhost", port=8767, project_path="/nonexistent")
        assert app.project_path == "/nonexistent"
        assert app.project_name is None

    def test_no_stream(self):
        app = CopilotApp(host="localhost", port=8767, stream_enabled=False)
        assert app.stream_enabled is False


class TestContext:
    def test_build_context_with_project(self, tmp_path):
        proj_file = tmp_path / "MyGame.c3proj"
        proj_file.write_text("{}")
        app = CopilotApp(host="localhost", port=8767, project_path=str(tmp_path))
        ctx = app.build_context()
        assert ctx["has_local_project"] is True
        assert ctx["project_path"] == str(tmp_path)

    def test_build_context_without_project(self):
        app = CopilotApp(host="localhost", port=8767)
        ctx = app.build_context()
        assert ctx["has_local_project"] is False


class TestUpdateSession:
    def test_update_from_response(self):
        app = CopilotApp(host="localhost", port=8767)
        app.update_from_response({"session_id": "abc123", "type": "direct_answer"})
        assert app.session_id == "abc123"
        assert app.turn_count == 1

    def test_preserves_existing_session_id(self):
        app = CopilotApp(host="localhost", port=8767)
        app.update_from_response({"session_id": "abc123", "type": "direct_answer"})
        app.update_from_response({"session_id": "abc123", "type": "direct_answer"})
        assert app.turn_count == 2
