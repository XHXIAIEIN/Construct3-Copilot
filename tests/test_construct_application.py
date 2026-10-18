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
        application.handle({"text": "这种斜切效果怎么做", "session_id": "c2c:placeholder", "session_dir": tmp_path / "c2c_placeholder",
                            "attachments": [attachment]})
    download.assert_called_once()
    question = application.agent.answer.call_args.args[0]
    assert question == "这种斜切效果怎么做（随这条消息发来了图片）"
    assert application.agent.answer.call_args.kwargs["images"] == [{"media_type": "image/png", "data": "aW1hZ2U="}]


def test_image_goes_with_the_questions_after_it(tmp_path):
    application = Application(Mock(), model="model-placeholder", vision=True)
    application.agent.answer = Mock(return_value=("ok", []))
    attachment = {"filename": "photo.png", "content_type": "image/png", "size": 5, "url": "https://example.test/p"}
    request = {"session_id": "c2c:placeholder", "session_dir": tmp_path / "c2c_placeholder"}
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


def test_image_outlives_a_restart(tmp_path):
    attachment = {"filename": "photo.png", "content_type": "image/png", "size": 5, "url": "https://example.test/p"}
    request = {"session_id": "c2c:placeholder", "session_dir": tmp_path / "c2c_placeholder"}
    before = Application(Mock(), model="model-placeholder", vision=True)
    before.agent.answer = Mock(return_value=("ok", []))
    with patch("copilot.providers.construct3.attachments.download", return_value=b"image"):
        before.handle({**request, "text": "这种斜切效果怎么做", "attachments": [attachment]})
    after = Application(Mock(), model="model-placeholder", vision=True)
    after.agent.answer = Mock(return_value=("ok", []))
    after.handle({**request, "text": "给我做一个示例"})
    assert after.agent.answer.call_args.kwargs["images"] == [{"media_type": "image/png", "data": "aW1hZ2U="}]


def test_image_is_a_note_for_a_text_model(tmp_path):
    application = Application(Mock(), model="model-placeholder")
    application.agent.answer = Mock(return_value=("ok", []))
    attachment = {"filename": "photo.png", "content_type": "image/png", "size": 5, "url": "https://example.test/p"}
    with patch("copilot.providers.construct3.attachments.download") as download:
        application.handle({"text": "这种斜切效果怎么做", "session_id": "c2c:placeholder", "session_dir": tmp_path / "c2c_placeholder",
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


def test_build_with_an_image_asks_for_what_the_image_shows(tmp_path):
    from copilot.providers.construct3.agent import Run
    from copilot.providers.construct3.reply import BUILD_NOTE, IMAGE_BUILD_NOTE
    run = Run("给我做一个示例", [], None, False, tmp_path, None, [{"media_type": "image/png", "data": "eA=="}])
    assert run.messages[-1]["content"][0]["text"] == "给我做一个示例" + BUILD_NOTE + IMAGE_BUILD_NOTE
    assert Run("给我做一个示例", [], None, False, tmp_path, None).messages[-1]["content"] == "给我做一个示例" + BUILD_NOTE


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


def test_a_how_to_question_is_shown_in_an_example(tmp_path):
    from copilot.providers.construct3.agent import Run
    from copilot.providers.construct3.reply import IMAGE_BUILD_NOTE, LENGTH_NOTE, SHOW_NOTE
    run = Run("怎么做斜切效果？", [], None, False, tmp_path, None)
    assert run.show_example() and run.build and run.shown
    assert run.messages[-1]["content"] == "怎么做斜切效果？" + SHOW_NOTE and "show ask" in run.trace
    pictured = Run("这种效果怎么做？", [], None, False, tmp_path, None, [{"media_type": "image/png", "data": "eA=="}])
    assert pictured.show_example() and pictured.messages[-1]["content"][0]["text"].endswith(SHOW_NOTE + IMAGE_BUILD_NOTE)
    # no folder to make it in, a project of their own, or an example already asked for
    assert not Run("怎么做斜切效果？", [], None, False, None, None).show_example()
    held = Run("怎么做斜切效果？", [], tmp_path, False, tmp_path, None)
    assert not held.show_example() and held.messages[-1]["content"].endswith(LENGTH_NOTE)
    assert not Run("做个斜切的例子", [], None, False, tmp_path, None).show_example()


def test_presearch_says_whether_to_show():
    from unittest.mock import patch
    from copilot.providers.construct3 import plugin
    with patch.object(plugin, "run_script", return_value="found"):
        assert plugin.presearch("怎么做斜切效果呢？", lambda m: {"words": ["mesh"], "show": True}) == (
            ["mesh"], "found", True)
        assert plugin.presearch("lerp 受帧率影响吗？", lambda m: {"words": ["lerp"]})[2] is False
        assert plugin.presearch("lerp 受帧率影响吗？", lambda m: {"words": ["lerp"], "show": "yes"})[2] is False


def test_numbered_steps_each_take_a_line():
    from copilot.providers.construct3.reply import step_lines
    inline = "要用网格变形：1. 右键精灵 → 网格，行列都填 2。2. 把上边两点往里拖。3、如果有接缝，就把行数调多。"
    assert step_lines(inline) == ("要用网格变形：\n1. 右键精灵 → 网格，行列都填 2。\n2. 把上边两点往里拖。\n"
                                  "3、如果有接缝，就把行数调多。")
    assert step_lines("1. 加鼠标。\n2. 加事件。") == "1. 加鼠标。\n2. 加事件。"
    assert step_lines("X 填 0.2。1、2 两个点不动。") == "X 填 0.2。1、2 两个点不动。"
