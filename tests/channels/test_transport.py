"""Check gateway receipts and message serialization."""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import asyncio
from channels.core import chat
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
            self.assertEqual(starting, {"status": "starting", "pid": os.getpid(), "started_at": "2026-01-01T00:00:00Z",
                                        "active_answers": 0})
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


if __name__ == "__main__":
    unittest.main()
