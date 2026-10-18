"""Verify the answer record Copilot hands its host: builds, fixes and tools from its own execution, and the ACE
check told apart from the model's lookups. These cases were the panel's, when it parsed them out of bot.log."""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from copilot.providers.construct3 import services as copilot
from copilot.providers.construct3.agent import Agent, Run
from copilot.providers.construct3.application import Application
from copilot.providers.construct3.record import ACE_CHECK, DESCRIPTION, settle


def call(call_id, name, arguments="{}"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def bare_run():
    run = Run.__new__(Run)
    run.calls, run.notify, run.told, run.send, run.project, run.handlers = [], None, False, False, None, {}
    return run


@pytest.fixture
def runtime():
    fake = Mock(skills_root=Path("plugin-placeholder"))
    fake.run_script.return_value = dict(status="completed", exit_code=0, stdout="ok", stderr="", reason=None)
    with patch.object(copilot, "get_runtime", return_value=fake):
        yield fake


def test_builds_count_outcomes_and_every_fix():
    run = bare_run()
    results = [(None, "refused, nothing was built:\nfixed: a\nspec: bad"),
               (Path("project"), "fixed: spec.objects[1].size: x\nfixed: spec.objects[4].align: y\nbuilt: 2 object types"),
               (None, "-- the call JSON had brackets out of order\ncopilot failed: Script exited with 1"),
               # five fixes: the old trace kept four lines and lost the outcome; the record does not
               (Path("project"), "fixed: a\nfixed: b\nfixed: c\nfixed: d\nfixed: e\nbuilt: 1 object type")]
    with patch.object(Run, "use_project"):
        for index, result in enumerate(results):
            run.calls.append({"id": f"c{index}", "name": "patch_spec", "ok": True})
            run.made(result)
    record = settle(run.calls, [])
    assert [t["ok"] for t in record["tools"]] == [False, True, False, True]
    assert (record["build"], record["fixes"]) == ("ok", 8)
    assert settle(run.calls[:1], [])["build"] == "failed"


def test_no_build_leaves_build_and_fixes_out():
    assert settle([{"id": "c1", "name": "search_guides", "ok": True}], []) == {
        "tools": [{"name": "search_guides", "ok": True}]}


def test_ace_check_is_apart_from_the_model_lookup(runtime):
    agent = Agent.__new__(Agent)
    run = bare_run()
    run.handlers["lookup_ace"] = lambda object, words=(): copilot.run_script("lookup_ace", [object, *words]).stdout
    agent._call(run, call("call_1", "lookup_ace", json.dumps({"object": "Sprite"})))
    model_request = runtime.run_script.call_args.kwargs["request_id"]
    assert model_request.startswith("tool:call_1:")
    from copilot.providers.construct3 import acecheck
    acecheck._lookup(["Sprite", "x"], None)
    check_request = runtime.run_script.call_args.kwargs["request_id"]
    assert check_request.startswith("acecheck:")
    children = [{"request_id": model_request, "status": "failed"}, {"request_id": check_request, "status": "completed"},
                {"request_id": None, "status": "failed"}]  # presearch and other rows of no call
    assert settle(run.calls, children)["tools"] == [{"name": "lookup_ace", "ok": False}, {"name": ACE_CHECK, "ok": True}]


def test_tool_errors_fail_the_call(runtime):
    agent = Agent.__new__(Agent)
    run = bare_run()
    run.handlers["print_sheet"] = Mock(side_effect=OSError("gone"))
    agent._call(run, call("c1", "print_sheet"))
    agent._call(run, call("c2", "print_sheet", "{not json"))
    agent._call(run, call("c3", "no_such_tool"))
    assert [c["ok"] for c in run.calls] == [False, False, False]


def test_answer_fills_the_record_even_when_it_fails():
    task = Mock(task_id="task-placeholder")

    @contextmanager
    def fake_session(*args):
        yield task

    def fails(*args):
        args[-1].append({"id": "c1", "name": "new_project_from_spec", "ok": True, "built": True, "fixes": 1})
        raise RuntimeError("after the build")

    agent, record = Agent.__new__(Agent), {}
    children = [{"request_id": "acecheck:1", "status": "completed"}]
    with patch.object(copilot, "session", fake_session), patch.object(copilot, "children", return_value=children), \
            patch.object(agent, "_answer_in_session", side_effect=fails), pytest.raises(RuntimeError):
        agent.answer("make an example", outbox=[], record=record)
    assert record == {"tools": [{"name": "new_project_from_spec", "ok": True}, {"name": ACE_CHECK, "ok": True}],
                      "build": "ok", "fixes": 1}


def test_handle_returns_the_record_and_describe_declares_it(tmp_path):
    application = Application(Mock(), model="model-placeholder")

    def answer(*args, record=None):
        record["tools"] = [{"name": "lookup_ace", "ok": True}]
        return "ok", []

    application.agent.answer = answer
    result = application.handle({"text": "example", "session_id": "s", "session_dir": tmp_path})
    assert result["record"] == {"tools": [{"name": "lookup_ace", "ok": True}]}
    assert "record" not in application.handle({"text": "", "session_id": "s", "session_dir": tmp_path})
    description = application.describe()
    assert description == DESCRIPTION and description is not DESCRIPTION
    fields = {f["id"] for f in description["fields"]}
    for metric in description["metrics"]:
        for path in (metric.get("field"), metric.get("each"), metric.get("by") if not metric.get("each") else None):
            assert path is None or path in fields, path
    json.dumps(description)
