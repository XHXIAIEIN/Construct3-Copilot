"""The post-answer ACE check: it looks ACEs up by plugin, reports an unresolvable object once, and tags its
own lookups in the task store."""
import sqlite3
from unittest.mock import patch

from copilot import Runtime
from copilot.providers.construct3 import acecheck, services, tools

SPRITE = "action set-position - 设置位置 [sprite]\ncondition is-visible - 可见 [sprite]"
MISS = "'{0}' is not an object of this project, System, or the id or display name of a plugin, behavior or effect"


def fake_lookups(calls):
    def run(name, args, project=None, limit=6000, locale="zh-CN", request_id=None):
        calls.append((args, request_id))
        return SPRITE if args[0] == "Sprite" else MISS.format(args[0])
    return run


def test_plugin_is_looked_up_and_object_only_shown():
    calls = []
    with patch.object(acecheck, "run_script", fake_lookups(calls)):
        missing = acecheck.missing_aces([{"object": "SnakeHead", "plugin": "Sprite", "name": "设置位置",
                                          "written_as": "action"}])
    assert missing == []
    assert calls and all(args[0] == "Sprite" for args, _ in calls)
    assert all(request_id.startswith(acecheck.CHECK_REQUEST) for _, request_id in calls)


def test_entry_without_plugin_is_looked_up_by_object():
    calls = []
    with patch.object(acecheck, "run_script", fake_lookups(calls)):
        assert acecheck.missing_aces([{"object": "Sprite", "name": "设置位置"}]) == []
        missing = acecheck.missing_aces([{"object": "Sprite", "name": "可见", "written_as": "action"}])
    assert missing == ["Sprite: 可见 is a condition, but the answer writes it as an action; "
                       "a condition goes before the arrow, an action after it"]


def test_miss_shows_object_with_its_plugin():
    calls = []
    with patch.object(acecheck, "run_script", fake_lookups(calls)):
        missing = acecheck.missing_aces([{"object": "Food", "plugin": "Sprite", "name": "飞走"}])
    assert len(missing) == 1 and missing[0].startswith("Food (Sprite): 飞走")


def test_object_that_is_no_plugin_is_reported_once_without_name_lookups():
    calls = []
    aces = [{"object": "SnakeHead", "name": "设置位置"}, {"object": "SnakeHead", "name": "移动"},
            {"object": "Food", "plugin": "Sprite", "name": "设置位置"}]
    with patch.object(acecheck, "run_script", fake_lookups(calls)):
        missing = acecheck.missing_aces(aces)
    assert missing == ["SnakeHead is not a plugin or behavior, so its ACE names could not be checked; name the "
                       "plugin or behavior that has them (e.g. Sprite, Text, 8Direction)"]
    snake = [args for args, _ in calls if args[0] == "SnakeHead"]
    assert snake == [["SnakeHead"], ["SnakeHead"]]  # the whole-object lookup in two locales, no per-name ones


def test_check_lookups_are_tagged_in_the_task_store(tmp_path):
    scripts = tmp_path / "provider/skills/construct3-agent-plugin/scripts"
    scripts.mkdir(parents=True)
    (scripts / "lookup_ace.py").write_text("print('action set-position - 设置位置 [sprite]')", encoding="utf-8")
    runtime = Runtime(tmp_path / "provider", tmp_path / "state")
    with patch.object(services, "get_runtime", return_value=runtime):
        assert acecheck.missing_aces([{"object": "SnakeHead", "plugin": "Sprite", "name": "设置位置"}]) == []
        tools.lookup_ace("Sprite", ["设置位置"])  # the model's own tool call
    with sqlite3.connect(runtime.store.path) as db:
        rows = db.execute("SELECT request_id FROM tasks WHERE capability='lookup_ace'").fetchall()
        tagged = db.execute(f"SELECT count(*) FROM tasks WHERE capability='lookup_ace' "
                            f"AND request_id LIKE '{acecheck.CHECK_REQUEST}%'").fetchone()[0]
    assert len(rows) == 3 and tagged == 2
    assert [r for r in rows if r[0] is None] == [(None,)]
