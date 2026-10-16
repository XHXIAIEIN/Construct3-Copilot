"""Offline checks for task attribution, delivery failures and chat serialization."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bot
from c3bot import copilot
from c3bot.agent import Agent, NO_FILE
from c3bot.gateway import GatewayReceipt
from plugins.construct3 import newproject, tools


class AdapterTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / ".tmp" / "adapter-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = Mock(skills_root=self.root / "plugin")
        self.runtime.run_script.return_value = dict(status="completed", exit_code=0, stdout="ok", stderr="", reason=None)
        self.mock_runtime = patch.object(copilot, "get_runtime", return_value=self.runtime)
        self.mock_runtime.start()
        self.addCleanup(self.mock_runtime.stop)
        self.data = patch.object(copilot, "DATA", self.root / "data")
        self.data.start()
        self.addCleanup(self.data.stop)

    def test_real_exit_code_and_failure_reason_reach_handler(self):
        self.runtime.run_script.return_value.update(status="failed", exit_code=7, reason="schema refused", stdout="detail")
        proc = copilot.run_script("check_project", [], self.root)
        self.assertEqual(proc.returncode, 7)
        self.assertIn("schema refused", proc.stdout)
        self.assertIn("detail", proc.stdout)

    def test_supervisor_timeout_cannot_become_success(self):
        self.runtime.run_script.return_value.update(status="timed_out", exit_code=None, reason="deadline")
        self.assertEqual(copilot.run_script("play_design", []).returncode, 124)

    def test_failed_status_overrides_zero_exit(self):
        self.runtime.run_script.return_value.update(status="failed", exit_code=0, reason="incomplete")
        self.assertNotEqual(copilot.run_script("check_project", []).returncode, 0)

    def test_current_prompts_and_rag_data_have_distinct_roots(self):
        copilot.run_script("search_guides", ["timer"], rag=self.root / "data-clone")
        self.assertEqual(self.runtime.run_script.call_args.args[1][-1], str(self.runtime.skills_root))
        copilot.run_script("lookup_ace", ["System"], rag=self.root / "data-clone")
        self.assertEqual(self.runtime.run_script.call_args.args[1][-1], str(self.root / "data-clone"))

    def test_child_context_is_scoped_to_subprocess_environment(self):
        task = SimpleNamespace(task_id="task-placeholder")
        token = copilot._active.set((task, "session-placeholder"))
        self.addCleanup(copilot._active.reset, token)
        before = dict(os.environ)
        env = copilot.child_environment()
        self.assertEqual(env["C3BOT_COPILOT_PARENT"], task.task_id)
        self.assertEqual(env["C3BOT_COPILOT_SESSION"], "session-placeholder")
        self.assertEqual(dict(os.environ), before)

    def test_child_calls_carry_parent_without_opening_another_session(self):
        with patch.dict(os.environ, {"C3BOT_COPILOT_PARENT": "parent-placeholder", "C3BOT_COPILOT_SESSION": "child-placeholder"}):
            copilot.run_script("check_project", [], self.root)
        self.assertEqual(self.runtime.run_script.call_args.kwargs["parent_id"], "parent-placeholder")
        self.assertEqual(self.runtime.run_script.call_args.kwargs["session_id"], "child-placeholder")

    def test_answer_records_prepared_files_and_reports_failure(self):
        task = Mock(task_id="task-placeholder")

        @contextmanager
        def fake_session(*args):
            yield task

        agent = Agent.__new__(Agent)
        with patch.object(copilot, "session", fake_session), patch.object(agent, "_answer_in_session", return_value=(NO_FILE, ["pack failed: refused"])):
            self.assertEqual(agent.answer("make an example", outbox=[])[0], NO_FILE)
        self.assertEqual(task.finish.call_args.kwargs["status"], "failed")
        self.assertEqual(task.finish.call_args.kwargs["artifacts"], [])

    def test_pack_failure_clears_delivery_claim(self):
        run = SimpleNamespace(project=self.root, trace=[], send=True, edits_before=0)
        with patch("c3bot.agent.kb.is_new", return_value=False), patch("c3bot.agent.kb.pack", side_effect=RuntimeError("refused")), patch("c3bot.agent.edits.edit_count", return_value=0):
            text = Agent.__new__(Agent)._finish(run, "项目文件随后发给你。", [])
        self.assertEqual(text, NO_FILE)
        self.assertFalse(run.send)

    def test_preview_nonzero_and_timeout_are_refusals(self):
        with patch.object(newproject, "EDITOR_CHECK", True):
            for code in (1, 2, 3, 124):
                with self.subTest(code=code), patch.object(copilot, "run_script", return_value=subprocess.CompletedProcess([], code, "cannot run", "")):
                    self.assertIn("refused", newproject.play_tests(self.root, self.root))
            with patch.object(copilot, "run_script", side_effect=subprocess.TimeoutExpired("preview", 1)):
                self.assertIn("timed out", newproject.play_tests(self.root, self.root))

    def test_editor_failure_keeps_the_checker_record(self):
        record = self.root / ".tmp" / "check-project.json"
        record.parent.mkdir()
        record.write_text("checked", encoding="utf-8")
        with patch.object(newproject, "EDITOR_CHECK", True), patch.object(copilot, "run_script", return_value=subprocess.CompletedProcess([], 2, "cannot run", "")):
            newproject.play_tests(self.root, self.root)
        self.assertEqual(record.read_text(encoding="utf-8"), "checked")

    def test_runtime_evidence_expires_after_project_changes(self):
        project = self.root / "project"
        project.mkdir()
        (project / "project.c3proj").write_text(json.dumps({"uniqueId": "placeholder"}), encoding="utf-8")
        with patch.object(newproject, "MARKS", self.root / "marks"):
            newproject._mark(project, "spec", verified=True)
            self.assertTrue(newproject.runtime_verified(project))
            (project / "logic.js").write_text("changed", encoding="utf-8")
            self.assertFalse(newproject.runtime_verified(project))

    def test_failed_preview_preserves_the_previous_project(self):
        project = self.root / "session"
        project.mkdir()
        original = project / "project.c3proj"
        original.write_text("original", encoding="utf-8")
        marks = self.root / "marks"
        marks.mkdir()

        def built(argv, **kwargs):
            candidate = Path(argv[argv.index("--out") + 1])
            candidate.mkdir()
            (candidate / "project.c3proj").write_text("candidate", encoding="utf-8")
            return subprocess.CompletedProcess(argv, 0, "checked", "")

        with patch.object(newproject, "MARKS", marks), patch.object(newproject, "QUICK", False), patch.object(newproject, "_again", return_value=None), patch.object(newproject.subprocess, "run", side_effect=built), patch.object(newproject, "play_tests", return_value="refused: preview failed"):
            newproject._design_file(project).write_text("{}", encoding="utf-8")
            made, reason = newproject.from_spec({"name": "Placeholder"}, project, self.root, "zh-CN")
        self.assertIsNone(made)
        self.assertIn("preview failed", reason)
        self.assertEqual(original.read_text(encoding="utf-8"), "original")

    def test_failed_template_check_preserves_the_previous_project(self):
        project = self.root / "session"
        project.mkdir()
        original = project / "project.c3proj"
        original.write_text("original", encoding="utf-8")
        examples = self.root / "examples"
        template = examples / "example-projects" / "template-placeholder"
        template.mkdir(parents=True)
        (template / "project.c3proj").write_text("{}", encoding="utf-8")
        with patch.object(newproject, "EXAMPLES", examples), patch.object(copilot, "run_script", return_value=subprocess.CompletedProcess([], 1, "refused", "")):
            made, reason = newproject.from_template("template-placeholder", "Placeholder", project, self.root, "zh-CN")
        self.assertIsNone(made)
        self.assertIn("failed", reason)
        self.assertEqual(original.read_text(encoding="utf-8"), "original")

    def test_undo_refreshes_structural_check_before_delivery(self):
        with patch.object(tools.edits, "edit_count", return_value=2), patch.object(tools.edits, "undo", return_value=1), patch.object(tools, "check_project", return_value="checked") as check:
            changed, text = tools.undo_edit(self.root)
        self.assertTrue(changed)
        self.assertIn("checked", text)
        check.assert_called_once_with(self.root)

    def test_gateway_receipt_records_current_process_and_utc_events(self):
        receipt = GatewayReceipt(self.root)
        with patch("c3bot.gateway.utc_now", side_effect=["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"]):
            receipt.starting()
            starting = json.loads(receipt.path.read_text(encoding="utf-8"))
            self.assertEqual(starting, {"status": "starting", "pid": os.getpid(), "started_at": "2026-01-01T00:00:00Z"})
            receipt.ready()
        ready = json.loads(receipt.path.read_text(encoding="utf-8"))
        self.assertEqual(ready, {**starting, "status": "ready", "ready_at": "2026-01-01T00:00:01Z"})
        self.assertEqual(list(receipt.path.parent.glob("*.tmp")), [])

    def test_gateway_restart_replaces_previous_ready_event(self):
        first = GatewayReceipt(self.root)
        first.starting()
        first.ready()
        second = GatewayReceipt(self.root)
        second.starting()
        record = json.loads(second.path.read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "starting")
        self.assertNotIn("ready_at", record)

    def test_invalid_copilot_configuration_fails_before_gateway_start(self):
        self.runtime = None
        with patch.object(copilot, "get_runtime", side_effect=ImportError("missing configured checkout")), patch.object(bot, "GatewayReceipt") as receipt:
            with self.assertRaisesRegex(ImportError, "missing configured checkout"):
                bot.run_qq(Mock())
        receipt.assert_not_called()


class ChatSerializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_chat_waits_before_any_handler_work(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        order = []

        @bot.serialized_sessions
        async def handle(key, label):
            order.append(label)
            if label == "first":
                entered.set()
                await release.wait()

        first = asyncio.create_task(handle("chat", "first"))
        await entered.wait()
        second = asyncio.create_task(handle("chat", "second"))
        other = asyncio.create_task(handle("other", "other"))
        await other
        self.assertEqual(order, ["first", "other"])
        release.set()
        await asyncio.gather(first, second)
        self.assertEqual(order, ["first", "other", "second"])


if __name__ == "__main__":
    unittest.main()
