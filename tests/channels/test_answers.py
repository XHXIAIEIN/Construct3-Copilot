"""Verify the channel's answer log: base fields from the channel, the application's record under "app" as it came,
the receipt's active answers while handle runs, and the application's declaration in runtime/app.json."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from channels.core import answers
from channels.core.receipt import GatewayReceipt
from channels.model.usage import Usage

REPO = Path(__file__).resolve().parents[2]


class Recording:
    """An application that makes two model calls through the channel's counter and returns what it is given."""

    def __init__(self, usage=None, record=None, fail=False, receipt=None):
        self.usage, self.record, self.fail, self.receipt, self.seen = usage, record, fail, receipt, []

    def handle(self, request):
        if self.receipt:
            self.seen.append(json.loads(self.receipt.path.read_text(encoding="utf-8"))["active_answers"])
        for prompt, completion in ((100, 5), (200, 7)):
            if self.usage:
                self.usage.count(SimpleNamespace(usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion)))
        if self.fail:
            raise RuntimeError("application placeholder failure")
        result = {"text": "reply", "files": [], "trace": []}
        if self.record is not None:
            result["record"] = self.record
        return result


class AnswerLogTests(unittest.TestCase):
    def setUp(self):
        root = REPO / ".tmp" / "answer-tests"
        root.mkdir(parents=True, exist_ok=True)
        folder = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(folder.cleanup)
        self.data = Path(folder.name)
        self.log = answers.AnswerLog(self.data, "qq")

    def lines(self):
        return [json.loads(line) for line in self.log.path.read_text(encoding="utf-8").splitlines()]

    def test_line_has_base_fields_and_the_record_as_it_came(self):
        usage = Usage(self.data)
        record = {"build": "ok", "fixes": 2, "tools": [{"name": "x", "ok": False}], "nested": {"kept": [1, 2]}}
        answer = answers.handle(Recording(usage, record), {"text": "q"}, usage=usage)
        self.log.write(answer, chat="group", session="group:G1:M2", files_in=[answers.file_fact("Private Name.C3P", 1234)],
                       files_out=[answers.file_fact("made.c3p", 74488, sent=True)])
        line = self.lines()[0]
        self.assertRegex(line.pop("at"), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*Z$")
        self.assertEqual(line, {"channel": "qq", "chat": "group", "session": "group:G1:M2", "seconds": 0, "calls": 2,
                                "prompt": 300, "completion": 12, "files_in": [{"type": ".c3p", "bytes": 1234}],
                                "files_out": [{"type": ".c3p", "bytes": 74488, "sent": True}], "ok": True, "app": record})
        self.assertNotIn("Private", self.log.path.read_text(encoding="utf-8"))
        self.assertEqual(usage.path.exists(), False)  # usage.log is the application's line, not the channel's

    def test_no_record_no_app(self):
        for record in (None, "not an object"):
            with self.subTest(record=record):
                self.log.write(answers.handle(Recording(record=record), {}), chat="private", session="c2c:A",
                               files_in=[], files_out=[])
                self.assertNotIn("app", self.lines()[-1])

    def test_failure_is_recorded_and_returned(self):
        answer = answers.handle(Recording(fail=True), {})
        self.assertIsInstance(answer.error, RuntimeError)
        self.log.write(answer, chat="private", session="c2c:A", files_in=[], files_out=[])
        self.assertEqual((self.lines()[0]["ok"], "app" in self.lines()[0]), (False, False))

    def test_receipt_counts_active_answers(self):
        receipt = GatewayReceipt(self.data)
        receipt.starting()
        application = Recording(receipt=receipt)
        answers.handle(application, {}, receipt=receipt)
        answers.handle(Recording(fail=True), {}, receipt=receipt)  # a failed answer is let go too
        self.assertEqual(application.seen, [1])
        self.assertEqual(json.loads(receipt.path.read_text(encoding="utf-8"))["active_answers"], 0)

    def test_cli_writes_its_answer_and_leaves_the_receipt(self):
        from channels.core.entry import ask_cli
        usage = Usage(self.data)
        with redirect_stdout(io.StringIO()):
            ask_cli(Recording(usage, {"tools": []}), "example", channel="qq", data_dir=self.data, usage=usage)
        line = self.lines()[0]
        self.assertEqual((line["chat"], line["session"], line["calls"], line["app"]), ("cli", "cli", 2, {"tools": []}))
        self.assertFalse((self.data / "runtime" / "gateway.json").exists())
        with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            ask_cli(Recording(fail=True), "example", channel="qq", data_dir=self.data)
        self.assertEqual(self.lines()[-1]["ok"], False)

    def test_qq_message_writes_one_line_after_its_file_is_sent(self):
        import botpy
        from channels.platforms.qq import bot
        clients, usage = [], Usage(self.data)
        made = self.data / "made.c3p"
        made.write_bytes(b"x" * 10)

        class Delivering(Recording):
            def handle(self, request):
                result = super().handle(request)
                return {**result, "files": [str(made)]}

        def close_logs():  # bot.log and botpy.log, so the folder can go
            for logger in [logging.getLogger(), *map(logging.getLogger, list(logging.Logger.manager.loggerDict))]:
                for handler in list(logger.handlers):
                    if str(getattr(handler, "baseFilename", "")).startswith(str(self.data)):
                        handler.close()
                        logger.removeHandler(handler)
        self.addCleanup(close_logs)
        with patch.object(botpy.Client, "run", lambda self, **kw: clients.append(self)):
            bot.run_qq(Delivering(usage, {"build": "ok"}), settings={"QQ_APPID": "1", "QQ_SECRET": "s"},
                       data_dir=self.data, usage=usage)
        client = clients[0]
        replies = []

        async def reply(**kwargs):
            replies.append(kwargs)

        message = SimpleNamespace(id="m1", content="做个游戏", reply=reply, attachments=[
            SimpleNamespace(filename="mine.zip", url="", content_type="file", size=99)],
            author=SimpleNamespace(user_openid="OPENID"))

        async def sent(*args, **kwargs):
            return None

        with patch.object(bot.qqfile, "send_file", sent), patch.object(bot.qqfile, "token_auth", lambda token: None):
            asyncio.run(client.on_c2c_message_create(message))
        line = self.lines()[0]
        self.assertEqual((line["chat"], line["session"], line["calls"], line["app"]),
                         ("private", "c2c:OPENID", 2, {"build": "ok"}))
        self.assertEqual((line["files_in"], line["files_out"]),
                         ([{"type": ".zip", "bytes": 99}], [{"type": ".c3p", "bytes": 10, "sent": True}]))
        receipt = json.loads((self.data / "runtime" / "gateway.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["active_answers"], 0)


class DescriptionTests(unittest.TestCase):
    def test_create_application_writes_the_declaration(self):
        from channels import app
        with tempfile.TemporaryDirectory(dir=REPO / ".tmp") as folder, patch("copilot.Runtime"), \
                patch("copilot.providers.construct3.load"):
            data = Path(folder)
            application = app.create_application(settings={"C3BOT_API_KEY": "placeholder-key"}, data_dir=data)
            written = json.loads((data / "runtime" / "app.json").read_text(encoding="utf-8"))
        self.assertEqual(written, application.describe())
        self.assertTrue(written["metrics"])
