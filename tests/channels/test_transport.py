"""Check gateway receipts and message serialization."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import asyncio
from channels.core import answers, chat
from channels.platforms.qq import bot
from channels.core.receipt import GatewayReceipt


class GatewayTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[2] / ".tmp" / "transport-tests"
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_gateway_receipt_records_current_process_and_utc_events(self):
        receipt = GatewayReceipt(self.root)
        with patch("channels.core.receipt.utc_now", side_effect=["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"]):
            receipt.starting()
            starting = json.loads(receipt.path.read_text(encoding="utf-8"))
            self.assertRegex(starting.pop("code"), r"^[0-9a-f]{16}$")
            self.assertEqual(starting, {"status": "starting", "pid": os.getpid(), "started_at": "2026-01-01T00:00:00Z",
                                        "active_answers": 0})
            starting["code"] = receipt.code
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



class ChatSerializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_chat_waits_before_any_handler_work(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        order = []

        @chat.serialized_sessions
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


async def answered(chats, key, question, parts=None, parts_sent=None):
    """Ask, then record the reply as a platform does: sent whole, or cut into parts of which parts_sent went out."""
    turn = await chats.ask(key, question, group=False, attachments=[], notify=None)
    parts = [turn.text] if parts is None else parts
    chats.record(turn, chat="private", session=key, files_in=[], sent=set(), parts=parts,
                 parts_sent=len(parts) if parts_sent is None else parts_sent)
    return turn


class ChatHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_outlives_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            application = Mock()
            application.handle.return_value = {"text": "用网格变形"}
            before = chat.Chats(application, data_dir=Path(tmp), channel="qq")
            await answered(before, "c2c:placeholder", "这种斜切效果怎么做")
            after = chat.Chats(application, data_dir=Path(tmp), channel="qq")
            await answered(after, "c2c:placeholder", "给我做一个示例")
            self.assertEqual(application.handle.call_args.args[0]["history"], [
                {"role": "user", "content": "这种斜切效果怎么做"}, {"role": "assistant", "content": "用网格变形"}])
            await answered(after, "c2c:other", "你好")
            self.assertEqual(application.handle.call_args.args[0]["history"], [])

    async def test_history_keeps_what_was_sent(self):
        """A reply QQ refused part way is in the history as far as it went, and one it refused whole as UNSENT
        after its question; the answer log and the "got it" rule read the same text."""
        written = "改成 lerp(a,b,1-0.01^dt)。要我做个示例吗？"
        parts = ["改成 lerp(a,b,1-0.01^dt)。", "要我做个示例吗？"]
        with tempfile.TemporaryDirectory() as tmp:
            application = Mock()
            application.handle.return_value = {"text": written}
            chats = chat.Chats(application, data_dir=Path(tmp), channel="qq")
            await answered(chats, "c2c:a", "lerp 受帧率影响吗", parts=parts, parts_sent=1)
            # the offer never reached the person, so "好的" only says got it
            self.assertTrue(chats.acknowledged("c2c:a", "好的", chat="private"))
            self.assertEqual(answers.read_skipped(Path(tmp), "qq")[0]["after"], "改成 lerp(a,b,1-0.01^dt)。")
            await answered(chats, "c2c:a", "dt 是什么", parts=parts, parts_sent=0)
            sent_first = [{"role": "user", "content": "lerp 受帧率影响吗"},
                          {"role": "assistant", "content": "改成 lerp(a,b,1-0.01^dt)。"}]
            restarted = chat.Chats(application, data_dir=Path(tmp), channel="qq")
            await answered(restarted, "c2c:a", "怎么没回")
            self.assertEqual(application.handle.call_args.args[0]["history"], sent_first + [
                {"role": "user", "content": "dt 是什么"}, {"role": "assistant", "content": chat.UNSENT}])

            lines = answers.read_answers(Path(tmp), "qq")
            self.assertEqual([(l["reply_sent"], l["reply_parts"]) for l in lines],
                             [(False, [1, 2]), (False, [0, 2]), (True, [1, 1])])
            turns = answers.read_turns(Path(tmp), "qq", [l["turn"] for l in lines])
            first, second, third = (turns[l["turn"]] for l in lines)
            self.assertEqual((first["reply"], first["written"], first["history"]), (parts[0], written, []))
            self.assertEqual((second["reply"], second["written"], second["history"]), ("", written, sent_first))
            self.assertEqual((third["reply"], "written" in third, len(third["history"])), (written, False, 4))

    async def test_history_ends_hours_after_the_last_answer(self):
        def hours_ago(hours):
            return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        first = [{"role": "user", "content": "这种斜切效果怎么做"}, {"role": "assistant", "content": "用网格变形"}]
        with tempfile.TemporaryDirectory() as tmp:
            application = Mock()
            application.handle.return_value = {"text": "用网格变形"}
            path = Path(tmp) / "sessions" / "_history" / "c2c_placeholder.json"
            for saved, carried in [({"at": hours_ago(chat.HISTORY_HOURS - 1), "turns": first}, first),
                                   ({"at": hours_ago(chat.HISTORY_HOURS + 1), "turns": first}, []),
                                   (first, [])]:  # a file from before the time was kept
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
                after_restart = chat.Chats(application, data_dir=Path(tmp), channel="qq")
                await answered(after_restart, "c2c:placeholder", "给我做一个示例")
                self.assertEqual(application.handle.call_args.args[0]["history"], carried)
                written = json.loads(path.read_text(encoding="utf-8"))
                self.assertTrue(chat.within_hours(written["at"], 0.1))
                self.assertEqual(written["turns"][-2:], [{"role": "user", "content": "给我做一个示例"},
                                                         {"role": "assistant", "content": "用网格变形"}])

            running = chat.Chats(application, data_dir=Path(tmp), channel="qq")
            with patch("channels.core.chat.utc_now", return_value=hours_ago(chat.HISTORY_HOURS + 1)):
                await answered(running, "c2c:other", "这种斜切效果怎么做")
            await answered(running, "c2c:other", "怎么存档")
            self.assertEqual(application.handle.call_args.args[0]["history"], [])


class CodeStampTests(unittest.TestCase):
    """The receipt's code stamp against the files on disk: the panel's reminder that a restart is due."""

    def setUp(self):
        root = Path(__file__).resolve().parents[2] / ".tmp" / "transport-tests"
        root.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        for name in ("channels/core/chat.py", "copilot/agent.py", "channels/panel/server.py", "channels/var/x.py"):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text("a = 1\n", encoding="utf-8")

    def gateway(self):
        from channels.panel.gateway import Gateway
        return Gateway(self.repo, self.repo, env=dict, data=lambda: self.repo / "channels" / "var")

    def test_stamp_follows_content_of_the_code_the_channel_runs(self):
        from channels.core.codestamp import CodeStamp, python_files
        self.assertEqual([p.relative_to(self.repo).as_posix() for p in python_files(self.repo)],
                         ["channels/core/chat.py", "copilot/agent.py"])
        stamp = CodeStamp(self.repo)
        before = stamp.stamp()
        (self.repo / "channels/panel/server.py").write_text("changed = 1\n", encoding="utf-8")
        self.assertEqual(stamp.stamp(), before)  # the panel's own code is not the channel's
        (self.repo / "copilot/agent.py").write_text("a = 2\n", encoding="utf-8")
        self.assertNotEqual(stamp.stamp(), before)

    def test_code_change_compares_the_stamp_or_falls_back_to_modified_files(self):
        from channels.core.codestamp import CodeStamp
        gateway = self.gateway()
        current = CodeStamp(self.repo).stamp()
        old_start, new_start = "2000-01-01T00:00:00Z", "2999-01-01T00:00:00Z"
        self.assertEqual(gateway.code_change({"started_at": old_start, "code": current}), {"stale": False, "changed": []})
        stale = gateway.code_change({"started_at": old_start, "code": "0" * 16})
        self.assertEqual((stale["stale"], sorted(stale["changed"])), (True, ["channels/core/chat.py", "copilot/agent.py"]))
        self.assertTrue(gateway.code_change({"started_at": old_start})["stale"])  # a receipt from before stamps
        self.assertFalse(gateway.code_change({"started_at": new_start})["stale"])
        self.assertFalse(gateway.code_change({"started_at": None})["stale"])


if __name__ == "__main__":
    unittest.main()
