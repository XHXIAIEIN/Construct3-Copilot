"""Check which answers ask the model to think: the tool loop of a build or an edit does, the rest does not."""
from unittest.mock import Mock, patch

from channels.model.settings import from_settings
from copilot.providers.construct3.agent import Agent, Run


def test_each_provider_thinks_for_projects_only():
    deepseek = from_settings({})
    assert deepseek.request_options == {"thinking": {"type": "disabled"}}
    assert deepseek.project_options["thinking"] == {"type": "enabled"}
    claude = from_settings({"C3BOT_BASE_URL": "https://api.anthropic.com/v1"})
    assert claude.request_options == {}
    assert claude.project_options["output_config"] == {"effort": "high"}
    assert claude.project_timeout == 600 and claude.timeout == 120
    local = from_settings({"C3BOT_BASE_URL": "http://localhost:11434/v1"})
    assert (local.request_options["reasoning_effort"], local.project_options["reasoning_effort"]) == ("none", "medium")
    assert from_settings({"C3BOT_BASE_URL": "https://example.invalid/v1"}).project_options == {}


def test_thinking_mode_and_hand_set_switches():
    assert from_settings({"C3BOT_THINKING": "off"}).project_options == {"thinking": {"type": "disabled"}}
    assert from_settings({"C3BOT_THINKING": "on"}).request_options["thinking"] == {"type": "enabled"}
    hand = from_settings({"C3BOT_EXTRA_BODY": '{"x": 1}'})
    assert hand.request_options == hand.project_options == {"x": 1}
    assert hand.project_timeout == hand.timeout
    both = from_settings({"C3BOT_EXTRA_BODY": '{"x": 1}', "C3BOT_EXTRA_BODY_PROJECT": '{"x": 2}'})
    assert (both.request_options, both.project_options) == ({"x": 1}, {"x": 2})


def asked_options(build: bool) -> dict:
    client = Mock()
    client.chat.completions.create.return_value = Mock(choices=[Mock(message=Mock(tool_calls=None, content="ok"))])
    agent = Agent(client, model="model-placeholder", request_options={"light": 1}, timeout=120,
                  project_options={"deep": 1}, project_timeout=600)
    agent._presearch = lambda run: None
    run = Run("question", None, None, False, None, None)
    run.build = build
    with patch("copilot.providers.construct3.agent.kb.check", return_value=[]):
        assert agent._answer(run) == "ok"
    kwargs = client.chat.completions.create.call_args.kwargs
    assert ("thinking on" in run.trace) is build
    return kwargs["extra_body"], kwargs["timeout"]


def test_build_loop_uses_the_project_options():
    assert asked_options(True) == ({"deep": 1}, 600)
    assert asked_options(False) == ({"light": 1}, 120)


def test_a_held_project_or_a_build_ask_marks_the_run(tmp_path):
    assert not Run("这个条件在哪？", None, None, False, tmp_path, None).build
    assert Run("给我做个小游戏", None, None, False, tmp_path, None).build
    assert Run("改一下跳跃高度", None, tmp_path / "project", False, tmp_path, None).build
