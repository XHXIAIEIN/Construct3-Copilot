"""Check the application boundary independently of QQ and model services."""
import io
import re
from pathlib import Path
from unittest.mock import Mock, patch
import zipfile

import pytest

from copilot.providers.construct3.application import Application, load_archive
from copilot.providers.construct3.reply import is_build_ask


def test_whole_game_question_is_distinct_from_build_request():
    assert not is_build_ask("System Wait 会阻塞整个游戏吗？", False)
    assert not is_build_ask("这个设置会影响整个项目吗？", False)
    assert not is_build_ask("整个游戏都会暂停吗？", False)
    assert is_build_ask("整个小游戏", False)
    assert is_build_ask("给我整个例子", False)


def test_request_context_reaches_agent_and_files_survive_late_failure(tmp_path):
    application = Application(Mock(), model="model-placeholder")
    artifact = tmp_path / "output.c3p"

    def answer(question, history, project, group, outbox, session, notify):
        assert question == "example"
        assert history == [{"role": "user", "content": "earlier"}]
        assert group is True
        assert session == tmp_path
        outbox.append(artifact)
        raise RuntimeError("after file preparation")

    application.agent.answer = answer
    result = application.handle({"text": "example", "session_id": "session-placeholder",
                                 "session_dir": tmp_path, "group": True,
                                 "history": [{"role": "user", "content": "earlier"}]})
    assert result["files"] == [artifact]
    assert "做好的部分" in result["text"]


def test_unsafe_archive_preserves_existing_project(tmp_path):
    project = tmp_path / "project.c3proj"
    project.write_text("original", encoding="utf-8")
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("project.c3proj", "candidate")
        zf.writestr("../outside", "unsafe")
    with pytest.raises(ValueError, match="不安全"):
        load_archive(archive.getvalue(), "example.c3p", tmp_path)
    assert project.read_text(encoding="utf-8") == "original"


def test_model_json_mode_fallback_uses_injected_error_type():
    class UnsupportedMode(Exception):
        pass
    client = Mock()
    client.chat.completions.create.side_effect = [UnsupportedMode(),
        Mock(choices=[Mock(message=Mock(content='{"valid": true}'))])]
    application = Application(client, model="model-placeholder", bad_request_error=UnsupportedMode)
    assert application.agent._json([]) == {"valid": True}
    assert client.chat.completions.create.call_count == 2


def test_attachment_log_leads_with_session_key(tmp_path, caplog):
    application = Application(Mock(), model="model-placeholder")
    application.agent.answer = Mock(return_value="ok")
    attachment = {"filename": "photo.png", "content_type": "image", "size": 123, "url": ""}
    with caplog.at_level("INFO", logger="copilot.construct3"):
        application.handle({"text": "example", "session_id": "group:g-placeholder:m-placeholder",
                            "session_dir": tmp_path, "attachments": [attachment]})
    line = next(r.getMessage() for r in caplog.records if "attachment:" in r.getMessage())
    assert re.fullmatch(r"(c2c|group):\S+ attachment: name-md5 \w+, \w+, (\d+) bytes, (\S*)", line)
    assert line.startswith("group:g-placeholder:m-placeholder attachment: name-md5 ")
    assert "photo" not in line
    assert line.endswith(", image, 123 bytes, .png")
