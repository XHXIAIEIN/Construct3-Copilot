"""Check the application boundary independently of QQ and model services."""
import io
import re
from pathlib import Path
from unittest.mock import Mock, patch
import zipfile

import pytest

from copilot.providers.construct3.application import EARLIER_IMAGE_TURNS, Application, load_archive
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

    def answer(question, history, project, group, outbox, session, notify, record=None, images=None):
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


def test_image_reaches_a_model_that_reads_images(tmp_path):
    application = Application(Mock(), model="model-placeholder", vision=True)
    application.agent.answer = Mock(return_value=("ok", []))
    attachment = {"filename": "photo.png", "content_type": "image/png", "size": 5, "url": "https://example.test/p"}
    with patch("copilot.providers.construct3.attachments.download", return_value=b"image") as download:
        application.handle({"text": "这种斜切效果怎么做", "session_id": "c2c:placeholder", "session_dir": tmp_path,
                            "attachments": [attachment]})
    download.assert_called_once()
    question = application.agent.answer.call_args.args[0]
    assert question == "这种斜切效果怎么做（随这条消息发来了图片）"
    assert application.agent.answer.call_args.kwargs["images"] == [{"media_type": "image/png", "data": "aW1hZ2U="}]


def test_image_goes_with_the_questions_after_it(tmp_path):
    application = Application(Mock(), model="model-placeholder", vision=True)
    application.agent.answer = Mock(return_value=("ok", []))
    attachment = {"filename": "photo.png", "content_type": "image/png", "size": 5, "url": "https://example.test/p"}
    request = {"session_id": "c2c:placeholder", "session_dir": tmp_path}
    with patch("copilot.providers.construct3.attachments.download", return_value=b"image"):
        application.handle({**request, "text": "这种斜切效果怎么做", "attachments": [attachment]})
    image = [{"media_type": "image/png", "data": "aW1hZ2U="}]
    for _ in range(EARLIER_IMAGE_TURNS):
        application.handle({**request, "text": "帮我做一个示例，还原一模一样的效果图"})
        assert application.agent.answer.call_args.kwargs["images"] == image
        assert "image sent earlier" in application.agent.answer.call_args.args[0]
    application.handle({**request, "text": "再改一下颜色"})
    assert application.agent.answer.call_args.kwargs["images"] == []
    application.handle({"session_id": "c2c:other", "session_dir": tmp_path, "text": "这种斜切效果怎么做"})
    assert application.agent.answer.call_args.kwargs["images"] == []


def test_image_is_a_note_for_a_text_model(tmp_path):
    application = Application(Mock(), model="model-placeholder")
    application.agent.answer = Mock(return_value=("ok", []))
    attachment = {"filename": "photo.png", "content_type": "image/png", "size": 5, "url": "https://example.test/p"}
    with patch("copilot.providers.construct3.attachments.download") as download:
        application.handle({"text": "这种斜切效果怎么做", "session_id": "c2c:placeholder", "session_dir": tmp_path,
                            "attachments": [attachment]})
    download.assert_not_called()
    assert "a .png file that you cannot read" in application.agent.answer.call_args.args[0]
    assert application.agent.answer.call_args.kwargs["images"] == []


def test_run_sends_images_after_the_question():
    from copilot.providers.construct3.agent import Run
    from copilot.providers.construct3.reply import LENGTH_NOTE
    run = Run("question", [], None, False, None, None, [{"media_type": "image/jpeg", "data": "eA=="}])
    assert run.messages[-1]["content"] == [
        {"type": "text", "text": "question" + LENGTH_NOTE},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,eA=="}}]
    assert Run("question", [], None, False, None, None).messages[-1]["content"] == "question" + LENGTH_NOTE


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


def test_reply_limit_steps_up_with_what_the_reply_needs():
    from copilot.providers.construct3.reply import EVENTS_MAX, REPLY_MAX, STEPS_MAX, has_steps, shorten
    asked = []
    complete = lambda messages: asked.append(messages[-1]["content"]) or "短"
    assert shorten(complete, [], "用网格变形。", []) == "用网格变形。"
    shorten(complete, [], "长" * (REPLY_MAX + 1), [])
    assert f"under {REPLY_MAX} characters" in asked[-1]
    steps = "1. 设置网格大小。2. 设置网格点，X 填 0.2。" + "长" * 60
    assert has_steps(steps) and not has_steps("X 填 0.2，r506.2 版本")
    assert shorten(complete, [], steps, []) == steps
    events = "\n".join(["开始 → 设置网格大小", "每帧 → 设置网格点", "点击 → 切换"] + ["长" * 200])
    assert len(events) > STEPS_MAX
    assert shorten(complete, [], events, [], asked=True) == events
    shorten(complete, [], events + "长" * EVENTS_MAX, [], asked=True)
    assert f"under {EVENTS_MAX} characters" in asked[-1]
